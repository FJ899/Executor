from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import stat
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from executor.action_authorization import AuthorizationDecision
from executor.hashing import hash_json


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class AuthorizationReplayError(RuntimeError):
    pass


class AuthorizationLedgerIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ConsumptionReceipt:
    schema_version: str
    consumption_id: str
    packet_id: str
    payload_sha256: str
    run_id: str
    action_kind: str
    action_binding_sha256: str
    consumed_at: str
    previous_event_hash: str | None
    event_hash: str
    event_authentication_tag: str
    result_binding_token_sha256: str
    result_binding_token: str

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("result_binding_token")
        return value


@dataclass(frozen=True)
class ActionResult:
    status: str
    exit_code: int | None
    stdout_sha256: str
    stderr_sha256: str
    output_sha256: str
    completed_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BoundResultReceipt:
    schema_version: str
    consumption_id: str
    packet_id: str
    action_result: dict[str, Any]
    action_result_sha256: str
    previous_event_hash: str
    event_hash: str
    event_authentication_tag: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AuthorizationConsumptionLedger:
    """Durable one-use AAP ledger with authenticated event history."""

    def __init__(self, root: str | Path, *, authentication_key: bytes, key_id: str):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise AuthorizationLedgerIntegrityError("Ledger root must be a directory")
        if stat.S_IMODE(self.root.stat().st_mode) & 0o077:
            raise AuthorizationLedgerIntegrityError("Ledger root must be private")
        if not isinstance(authentication_key, bytes) or len(authentication_key) < 32:
            raise ValueError("authentication_key must contain at least 32 bytes")
        if not key_id:
            raise ValueError("key_id is required")
        self._key = authentication_key
        self.key_id = key_id
        self.database = self.root / "authorization-ledger.sqlite3"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA trusted_schema=OFF")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS consumptions (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    consumption_id TEXT NOT NULL UNIQUE,
                    packet_id TEXT NOT NULL UNIQUE,
                    payload_sha256 TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    action_kind TEXT NOT NULL,
                    action_binding_sha256 TEXT NOT NULL,
                    consumed_at TEXT NOT NULL,
                    result_binding_token_sha256 TEXT NOT NULL,
                    previous_event_hash TEXT,
                    event_hash TEXT NOT NULL,
                    event_authentication_tag TEXT NOT NULL,
                    result_json TEXT,
                    action_result_sha256 TEXT,
                    result_event_hash TEXT,
                    result_authentication_tag TEXT
                )
                """
            )
        os.chmod(self.database, 0o600)

    def _tag(self, event_hash: str) -> str:
        return hmac.new(self._key, event_hash.encode("ascii"), hashlib.sha256).hexdigest()

    def consume(
        self,
        decision: AuthorizationDecision,
        *,
        run_id: str,
        action_binding: dict[str, Any],
    ) -> ConsumptionReceipt:
        if not decision.ready_for_atomic_consumption:
            raise AuthorizationLedgerIntegrityError("Authorization is not eligible for consumption")
        if action_binding.get("kind") != decision.action_kind:
            raise AuthorizationLedgerIntegrityError("Action kind does not match authorization decision")
        action_binding_sha256 = hash_json(action_binding)
        consumption_id = f"CON-{secrets.token_hex(16).upper()}"
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        consumed_at = _utc_now()
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                previous = connection.execute(
                    "SELECT event_hash, result_event_hash FROM consumptions ORDER BY sequence DESC LIMIT 1"
                ).fetchone()
                previous_event_hash = None
                if previous is not None:
                    previous_event_hash = previous["result_event_hash"] or previous["event_hash"]
                event_payload = {
                    "schema_version": "executor-authorization-consumption/1.0",
                    "consumption_id": consumption_id,
                    "packet_id": decision.packet_id,
                    "payload_sha256": decision.payload_sha256,
                    "run_id": run_id,
                    "action_kind": decision.action_kind,
                    "action_binding_sha256": action_binding_sha256,
                    "consumed_at": consumed_at,
                    "result_binding_token_sha256": token_hash,
                    "previous_event_hash": previous_event_hash,
                    "key_id": self.key_id,
                }
                event_hash = hash_json(event_payload)
                tag = self._tag(event_hash)
                connection.execute(
                    """
                    INSERT INTO consumptions (
                        consumption_id, packet_id, payload_sha256, run_id,
                        action_kind, action_binding_sha256, consumed_at,
                        result_binding_token_sha256, previous_event_hash,
                        event_hash, event_authentication_tag
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        consumption_id,
                        decision.packet_id,
                        decision.payload_sha256,
                        run_id,
                        decision.action_kind,
                        action_binding_sha256,
                        consumed_at,
                        token_hash,
                        previous_event_hash,
                        event_hash,
                        tag,
                    ),
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise AuthorizationReplayError("AUTHORIZATION_REPLAY") from exc
        return ConsumptionReceipt(
            schema_version="executor-authorization-consumption/1.0",
            consumption_id=consumption_id,
            packet_id=decision.packet_id,
            payload_sha256=decision.payload_sha256,
            run_id=run_id,
            action_kind=decision.action_kind,
            action_binding_sha256=action_binding_sha256,
            consumed_at=consumed_at,
            previous_event_hash=previous_event_hash,
            event_hash=event_hash,
            event_authentication_tag=tag,
            result_binding_token_sha256=token_hash,
            result_binding_token=token,
        )

    def verify_evidence_binding(
        self,
        consumption: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        self.verify_integrity()
        packet_id = consumption.get("packet_id")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM consumptions WHERE packet_id = ?", (packet_id,)
            ).fetchone()
        if row is None or row["result_json"] is None:
            raise AuthorizationLedgerIntegrityError("Evidence references an incomplete consumption")
        expected_consumption = {
            "schema_version": "executor-authorization-consumption/1.0",
            "consumption_id": row["consumption_id"],
            "packet_id": row["packet_id"],
            "payload_sha256": row["payload_sha256"],
            "run_id": row["run_id"],
            "action_kind": row["action_kind"],
            "action_binding_sha256": row["action_binding_sha256"],
            "consumed_at": row["consumed_at"],
            "previous_event_hash": row["previous_event_hash"],
            "event_hash": row["event_hash"],
            "event_authentication_tag": row["event_authentication_tag"],
            "result_binding_token_sha256": row["result_binding_token_sha256"],
        }
        stored_result = json_loads(row["result_json"])
        expected_result = {
            "schema_version": "executor-action-result-binding/1.0",
            "consumption_id": row["consumption_id"],
            "packet_id": row["packet_id"],
            "action_result": stored_result,
            "action_result_sha256": row["action_result_sha256"],
            "previous_event_hash": row["event_hash"],
            "event_hash": row["result_event_hash"],
            "event_authentication_tag": row["result_authentication_tag"],
        }
        if consumption != expected_consumption or result != expected_result:
            raise AuthorizationLedgerIntegrityError("Evidence does not match the ledger binding")

    def bind_result(
        self,
        *,
        packet_id: str,
        result_binding_token: str,
        result: ActionResult,
    ) -> BoundResultReceipt:
        self._validate_result(result)
        token_hash = hashlib.sha256(result_binding_token.encode("utf-8")).hexdigest()
        result_payload = result.to_dict()
        action_result_sha256 = hash_json(result_payload)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM consumptions WHERE packet_id = ?", (packet_id,)
            ).fetchone()
            if row is None:
                connection.rollback()
                raise AuthorizationLedgerIntegrityError("Unknown authorization consumption")
            if not hmac.compare_digest(token_hash, row["result_binding_token_sha256"]):
                connection.rollback()
                raise AuthorizationLedgerIntegrityError("Invalid result-binding token")
            if row["result_json"] is not None:
                connection.rollback()
                raise AuthorizationLedgerIntegrityError("Action result is already bound")
            event_payload = {
                "schema_version": "executor-action-result-binding/1.0",
                "consumption_id": row["consumption_id"],
                "packet_id": packet_id,
                "action_result": result_payload,
                "action_result_sha256": action_result_sha256,
                "previous_event_hash": row["event_hash"],
                "key_id": self.key_id,
            }
            event_hash = hash_json(event_payload)
            tag = self._tag(event_hash)
            updated = connection.execute(
                """
                UPDATE consumptions
                SET result_json = ?, action_result_sha256 = ?,
                    result_event_hash = ?, result_authentication_tag = ?
                WHERE packet_id = ? AND result_json IS NULL
                """,
                (
                    json_dumps(result_payload),
                    action_result_sha256,
                    event_hash,
                    tag,
                    packet_id,
                ),
            ).rowcount
            if updated != 1:
                connection.rollback()
                raise AuthorizationLedgerIntegrityError("Action result binding race was lost")
            connection.commit()
        return BoundResultReceipt(
            schema_version="executor-action-result-binding/1.0",
            consumption_id=row["consumption_id"],
            packet_id=packet_id,
            action_result=result_payload,
            action_result_sha256=action_result_sha256,
            previous_event_hash=row["event_hash"],
            event_hash=event_hash,
            event_authentication_tag=tag,
        )

    def verify_integrity(self) -> None:
        previous_hash = None
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM consumptions ORDER BY sequence").fetchall()
        for row in rows:
            if row["previous_event_hash"] != previous_hash:
                raise AuthorizationLedgerIntegrityError("Ledger chain linkage mismatch")
            consumption_payload = {
                "schema_version": "executor-authorization-consumption/1.0",
                "consumption_id": row["consumption_id"],
                "packet_id": row["packet_id"],
                "payload_sha256": row["payload_sha256"],
                "run_id": row["run_id"],
                "action_kind": row["action_kind"],
                "action_binding_sha256": row["action_binding_sha256"],
                "consumed_at": row["consumed_at"],
                "result_binding_token_sha256": row["result_binding_token_sha256"],
                "previous_event_hash": row["previous_event_hash"],
                "key_id": self.key_id,
            }
            event_hash = hash_json(consumption_payload)
            if not hmac.compare_digest(event_hash, row["event_hash"]) or not hmac.compare_digest(
                self._tag(event_hash), row["event_authentication_tag"]
            ):
                raise AuthorizationLedgerIntegrityError("Consumption event integrity mismatch")
            previous_hash = event_hash
            if row["result_json"] is not None:
                try:
                    result = json_loads(row["result_json"])
                except ValueError as exc:
                    raise AuthorizationLedgerIntegrityError("Stored action result is invalid") from exc
                result_hash = hash_json(result)
                result_payload = {
                    "schema_version": "executor-action-result-binding/1.0",
                    "consumption_id": row["consumption_id"],
                    "packet_id": row["packet_id"],
                    "action_result": result,
                    "action_result_sha256": result_hash,
                    "previous_event_hash": event_hash,
                    "key_id": self.key_id,
                }
                result_event_hash = hash_json(result_payload)
                if (
                    not hmac.compare_digest(result_hash, row["action_result_sha256"])
                    or not hmac.compare_digest(result_event_hash, row["result_event_hash"])
                    or not hmac.compare_digest(
                        self._tag(result_event_hash), row["result_authentication_tag"]
                    )
                ):
                    raise AuthorizationLedgerIntegrityError("Result event integrity mismatch")
                previous_hash = result_event_hash

    @staticmethod
    def _validate_result(result: ActionResult) -> None:
        if result.status not in {"SUCCEEDED", "FAILED", "BLOCKED"}:
            raise AuthorizationLedgerIntegrityError("Unsupported action result status")
        if isinstance(result.exit_code, bool) or (
            result.exit_code is not None and not isinstance(result.exit_code, int)
        ):
            raise AuthorizationLedgerIntegrityError("Invalid action result exit code")
        for value in (result.stdout_sha256, result.stderr_sha256, result.output_sha256):
            if _SHA256.fullmatch(value) is None or set(value) == {"0"}:
                raise AuthorizationLedgerIntegrityError("Invalid action result hash")
        if not result.completed_at.endswith("Z"):
            raise AuthorizationLedgerIntegrityError("Action completion time must be UTC")


def json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def json_loads(value: str) -> dict[str, Any]:
    import json

    result = json.loads(value, parse_constant=lambda constant: (_ for _ in ()).throw(ValueError(constant)))
    if not isinstance(result, dict):
        raise ValueError("Expected object")
    return result
