from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuthorityLedgerError(RuntimeError):
    pass


class AuthorityReplayError(AuthorityLedgerError):
    pass


_AUTHORITY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
_SAFE_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(r"^[0-9a-f]{32}$")


def canonical_result_bytes(result: dict[str, Any]) -> bytes:
    if not isinstance(result, dict):
        raise AuthorityLedgerError("authority result must be an object")
    try:
        value = json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise AuthorityLedgerError(f"authority result is not canonical JSON: {exc}") from exc
    return value.encode("utf-8")


@dataclass(frozen=True)
class AuthorityConsumption:
    authority_key: str
    payload_sha256: str
    action_kind: str
    run_id: str
    execution_token: str
    consumed_at: str
    state: str
    result_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "authority_key": self.authority_key,
            "payload_sha256": self.payload_sha256,
            "action_kind": self.action_kind,
            "run_id": self.run_id,
            "execution_token": self.execution_token,
            "consumed_at": self.consumed_at,
            "state": self.state,
            "result_sha256": self.result_sha256,
        }


class AtomicAuthorityLedger:
    """Durably consume one exact authority and bind one exact terminal result."""

    def __init__(self, path: str | Path):
        candidate = Path(path)
        if candidate.is_symlink():
            raise AuthorityLedgerError("authority ledger path cannot be a symlink")
        parent = candidate.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
            resolved_parent = parent.resolve(strict=True)
        except OSError as exc:
            raise AuthorityLedgerError(f"cannot prepare authority ledger directory: {exc}") from exc
        if not resolved_parent.is_dir():
            raise AuthorityLedgerError("authority ledger parent must be a directory")
        self.path = resolved_parent / candidate.name
        if self.path.exists():
            meta = self.path.lstat()
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
                raise AuthorityLedgerError(
                    "authority ledger must be one regular non-linked file"
                )
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=10,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        last_locked: sqlite3.OperationalError | None = None
        for _ in range(40):
            try:
                with self._connect() as connection:
                    connection.execute("PRAGMA journal_mode = WAL")
                    connection.execute("PRAGMA synchronous = FULL")
                    connection.execute(
                        """
                        CREATE TABLE IF NOT EXISTS authority_consumptions (
                            authority_key TEXT PRIMARY KEY,
                            payload_sha256 TEXT NOT NULL,
                            action_kind TEXT NOT NULL,
                            run_id TEXT NOT NULL,
                            execution_token TEXT NOT NULL UNIQUE,
                            consumed_at TEXT NOT NULL,
                            state TEXT NOT NULL CHECK (state IN ('CONSUMED', 'FINAL')),
                            result_sha256 TEXT,
                            result_json BLOB,
                            CHECK (
                                (state = 'CONSUMED' AND result_sha256 IS NULL AND result_json IS NULL)
                                OR
                                (state = 'FINAL' AND result_sha256 IS NOT NULL AND result_json IS NOT NULL)
                            )
                        )
                        """
                    )
                return
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower():
                    raise
                last_locked = exc
                time.sleep(0.05)
        raise AuthorityLedgerError("authority ledger initialization remained locked") from last_locked

    @staticmethod
    def _validate_consume(
        *,
        authority_key: str,
        payload_sha256: str,
        action_kind: str,
        run_id: str,
    ) -> None:
        if _AUTHORITY_KEY.fullmatch(authority_key) is None:
            raise AuthorityLedgerError("authority_key is invalid")
        if _SHA256.fullmatch(payload_sha256) is None:
            raise AuthorityLedgerError("payload_sha256 is invalid")
        if _SAFE_VALUE.fullmatch(action_kind) is None:
            raise AuthorityLedgerError("action_kind is invalid")
        if _SAFE_VALUE.fullmatch(run_id) is None:
            raise AuthorityLedgerError("run_id is invalid")

    def consume(
        self,
        *,
        authority_key: str,
        payload_sha256: str,
        action_kind: str,
        run_id: str,
        now: datetime | None = None,
    ) -> AuthorityConsumption:
        self._validate_consume(
            authority_key=authority_key,
            payload_sha256=payload_sha256,
            action_kind=action_kind,
            run_id=run_id,
        )
        token = uuid.uuid4().hex
        consumed_at = (now or datetime.now(timezone.utc)).astimezone(
            timezone.utc
        ).isoformat().replace("+00:00", "Z")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO authority_consumptions (
                    authority_key, payload_sha256, action_kind, run_id,
                    execution_token, consumed_at, state
                ) VALUES (?, ?, ?, ?, ?, ?, 'CONSUMED')
                """,
                (
                    authority_key,
                    payload_sha256,
                    action_kind,
                    run_id,
                    token,
                    consumed_at,
                ),
            )
            connection.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            connection.execute("ROLLBACK")
            raise AuthorityReplayError(
                f"authority already consumed: {authority_key}"
            ) from exc
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
        return AuthorityConsumption(
            authority_key=authority_key,
            payload_sha256=payload_sha256,
            action_kind=action_kind,
            run_id=run_id,
            execution_token=token,
            consumed_at=consumed_at,
            state="CONSUMED",
        )

    def bind_result(
        self,
        *,
        execution_token: str,
        result: dict[str, Any],
    ) -> AuthorityConsumption:
        if _TOKEN.fullmatch(execution_token) is None:
            raise AuthorityLedgerError("execution_token is invalid")
        result_bytes = canonical_result_bytes(result)
        result_sha256 = hashlib.sha256(result_bytes).hexdigest()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM authority_consumptions
                WHERE execution_token = ?
                """,
                (execution_token,),
            ).fetchone()
            if row is None:
                raise AuthorityLedgerError("unknown authority execution token")
            if row["state"] == "FINAL":
                if (
                    row["result_sha256"] == result_sha256
                    and bytes(row["result_json"]) == result_bytes
                ):
                    connection.execute("COMMIT")
                    return self._row_to_consumption(row)
                raise AuthorityLedgerError(
                    "authority result is already bound to different content"
                )
            connection.execute(
                """
                UPDATE authority_consumptions
                SET state = 'FINAL', result_sha256 = ?, result_json = ?
                WHERE execution_token = ? AND state = 'CONSUMED'
                """,
                (result_sha256, result_bytes, execution_token),
            )
            updated = connection.execute(
                """
                SELECT * FROM authority_consumptions
                WHERE execution_token = ?
                """,
                (execution_token,),
            ).fetchone()
            connection.execute("COMMIT")
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
        if updated is None:
            raise AuthorityLedgerError("authority result binding disappeared")
        return self._row_to_consumption(updated)

    @staticmethod
    def _row_to_consumption(row: sqlite3.Row) -> AuthorityConsumption:
        return AuthorityConsumption(
            authority_key=row["authority_key"],
            payload_sha256=row["payload_sha256"],
            action_kind=row["action_kind"],
            run_id=row["run_id"],
            execution_token=row["execution_token"],
            consumed_at=row["consumed_at"],
            state=row["state"],
            result_sha256=row["result_sha256"],
        )

    def get(self, authority_key: str) -> AuthorityConsumption | None:
        if _AUTHORITY_KEY.fullmatch(authority_key) is None:
            raise AuthorityLedgerError("authority_key is invalid")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM authority_consumptions WHERE authority_key = ?",
                (authority_key,),
            ).fetchone()
        return self._row_to_consumption(row) if row is not None else None

    def unresolved(self) -> tuple[AuthorityConsumption, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM authority_consumptions
                WHERE state = 'CONSUMED'
                ORDER BY consumed_at, authority_key
                """
            ).fetchall()
        return tuple(self._row_to_consumption(row) for row in rows)
