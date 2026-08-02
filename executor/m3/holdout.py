from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import stat
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from executor.hashing import canonical_json_bytes, hash_json, sha256_bytes
from executor.strict_json import StrictJsonError, loads_json_object


class HoldoutIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProvisionReceipt:
    schema_version: str
    test_id: str
    holdout_id: str
    artifact_sha256: str
    verifier_id: str
    verifier_key_id: str
    visibility: str
    access: str
    provisioned_at: str
    receipt_sha256: str
    authentication_tag: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HoldoutReplayReceipt:
    schema_version: str
    replay_id: str
    test_id: str
    holdout_id: str
    artifact_sha256: str
    candidate_result_sha256: str
    verdict: str
    checks_total: int
    checks_passed: int
    verifier_id: str
    verifier_key_id: str
    replayed_at: str
    receipt_sha256: str
    authentication_tag: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_within(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
    except ValueError:
        return False
    return True


def _selector(value: Any, selector: str) -> Any:
    if selector == "$":
        return value
    if not isinstance(selector, str) or not selector.startswith("$."):
        raise HoldoutIntegrityError("Unsupported holdout selector")
    current = value
    for part in selector[2:].split("."):
        if not part or not isinstance(current, dict) or part not in current:
            raise HoldoutIntegrityError("Holdout selector target is missing")
        current = current[part]
    return current


class IndependentHoldoutStore:
    """Verifier-owned immutable holdout store.

    The root and authentication key are deployment inputs. The public methods do
    not expose stored payloads. OS/process isolation remains a deployment duty.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        implementer_workspace: str | Path,
        verifier_id: str,
        verifier_key_id: str,
        authentication_key: bytes,
    ):
        if not verifier_id or not verifier_key_id:
            raise ValueError("verifier_id and verifier_key_id are required")
        if not isinstance(authentication_key, bytes) or len(authentication_key) < 32:
            raise ValueError("authentication_key must contain at least 32 bytes")
        self.root = Path(root).resolve(strict=True)
        workspace = Path(implementer_workspace).resolve(strict=True)
        if not self.root.is_dir() or not workspace.is_dir():
            raise HoldoutIntegrityError("Holdout root and workspace must be directories")
        if _is_within(self.root, workspace) or _is_within(workspace, self.root):
            raise HoldoutIntegrityError("Verifier root must be independent from implementer workspace")
        mode = stat.S_IMODE(self.root.stat().st_mode)
        if mode & 0o077:
            raise HoldoutIntegrityError("Verifier root must not grant group or other access")
        self.verifier_id = verifier_id
        self.verifier_key_id = verifier_key_id
        self._key = authentication_key
        self._database = self.root / "holdouts.sqlite3"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA trusted_schema=OFF")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS holdouts (
                    test_id TEXT PRIMARY KEY,
                    holdout_id TEXT NOT NULL UNIQUE,
                    artifact_sha256 TEXT NOT NULL,
                    payload BLOB NOT NULL,
                    provisioned_at TEXT NOT NULL
                )
                """
            )
        os.chmod(self._database, 0o600)

    def _authenticate(self, payload: dict[str, Any]) -> tuple[str, str]:
        receipt_sha256 = hash_json(payload)
        tag = hmac.new(
            self._key,
            receipt_sha256.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        return receipt_sha256, tag

    def _receipt_valid(self, receipt: dict[str, Any]) -> bool:
        if not isinstance(receipt, dict):
            return False
        supplied_hash = receipt.get("receipt_sha256")
        supplied_tag = receipt.get("authentication_tag")
        if not isinstance(supplied_hash, str) or not isinstance(supplied_tag, str):
            return False
        payload = {
            key: value
            for key, value in receipt.items()
            if key not in {"receipt_sha256", "authentication_tag"}
        }
        expected_hash, expected_tag = self._authenticate(payload)
        return hmac.compare_digest(supplied_hash, expected_hash) and hmac.compare_digest(
            supplied_tag, expected_tag
        )

    def verify_receipt(self, receipt: ProvisionReceipt | HoldoutReplayReceipt | dict[str, Any]) -> bool:
        payload = receipt.to_dict() if hasattr(receipt, "to_dict") else receipt
        return self._receipt_valid(payload)

    def provision(self, *, test_id: str, holdout_payload: bytes) -> ProvisionReceipt:
        if not test_id or not isinstance(holdout_payload, bytes) or not holdout_payload:
            raise ValueError("test_id and non-empty holdout_payload are required")
        try:
            document = loads_json_object(holdout_payload.decode("utf-8"))
        except (UnicodeDecodeError, StrictJsonError) as exc:
            raise HoldoutIntegrityError(f"Holdout must be strict UTF-8 JSON: {exc}") from exc
        self._validate_holdout_document(document, test_id=test_id)
        artifact_sha256 = sha256_bytes(holdout_payload)
        provisioned_at = _utc_now()
        holdout_id = f"HLD-{secrets.token_hex(16).upper()}"
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM holdouts WHERE test_id = ?", (test_id,)
            ).fetchone()
            if existing is not None:
                if not hmac.compare_digest(existing["artifact_sha256"], artifact_sha256):
                    connection.rollback()
                    raise HoldoutIntegrityError("An immutable holdout already exists for this test")
                holdout_id = existing["holdout_id"]
                provisioned_at = existing["provisioned_at"]
            else:
                connection.execute(
                    "INSERT INTO holdouts VALUES (?, ?, ?, ?, ?)",
                    (test_id, holdout_id, artifact_sha256, holdout_payload, provisioned_at),
                )
            connection.commit()
        payload = {
            "schema_version": "executor-holdout-provision/1.0",
            "test_id": test_id,
            "holdout_id": holdout_id,
            "artifact_sha256": artifact_sha256,
            "verifier_id": self.verifier_id,
            "verifier_key_id": self.verifier_key_id,
            "visibility": "HIDDEN_FROM_IMPLEMENTER",
            "access": "REPLAY_ONLY",
            "provisioned_at": provisioned_at,
        }
        receipt_sha256, tag = self._authenticate(payload)
        return ProvisionReceipt(**payload, receipt_sha256=receipt_sha256, authentication_tag=tag)

    def replay(
        self,
        *,
        test_id: str,
        holdout_id: str,
        candidate_result: dict[str, Any],
    ) -> HoldoutReplayReceipt:
        try:
            candidate_hash = hash_json(candidate_result)
        except (TypeError, ValueError) as exc:
            raise HoldoutIntegrityError(f"Candidate result is not canonical JSON: {exc}") from exc
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM holdouts WHERE test_id = ? AND holdout_id = ?",
                (test_id, holdout_id),
            ).fetchone()
        if row is None:
            raise HoldoutIntegrityError("Unknown holdout or test binding")
        payload = bytes(row["payload"])
        if not hmac.compare_digest(sha256_bytes(payload), row["artifact_sha256"]):
            raise HoldoutIntegrityError("Stored holdout integrity mismatch")
        try:
            document = loads_json_object(payload.decode("utf-8"))
        except (UnicodeDecodeError, StrictJsonError) as exc:
            raise HoldoutIntegrityError("Stored holdout is not strict JSON") from exc
        self._validate_holdout_document(document, test_id=test_id)
        assertions = document["assertions"]
        passed = 0
        for assertion in assertions:
            try:
                actual = _selector(candidate_result, assertion["selector"])
            except HoldoutIntegrityError:
                continue
            operator = assertion["operator"]
            expected = assertion["expected"]
            if (operator == "==" and actual == expected and type(actual) is type(expected)) or (
                operator == "!=" and (actual != expected or type(actual) is not type(expected))
            ):
                passed += 1
        verdict = "PASS" if passed == len(assertions) else "FAIL"
        receipt_payload = {
            "schema_version": "executor-holdout-replay/1.0",
            "replay_id": f"HRP-{secrets.token_hex(16).upper()}",
            "test_id": test_id,
            "holdout_id": holdout_id,
            "artifact_sha256": row["artifact_sha256"],
            "candidate_result_sha256": candidate_hash,
            "verdict": verdict,
            "checks_total": len(assertions),
            "checks_passed": passed,
            "verifier_id": self.verifier_id,
            "verifier_key_id": self.verifier_key_id,
            "replayed_at": _utc_now(),
        }
        receipt_sha256, tag = self._authenticate(receipt_payload)
        return HoldoutReplayReceipt(
            **receipt_payload,
            receipt_sha256=receipt_sha256,
            authentication_tag=tag,
        )

    @staticmethod
    def _validate_holdout_document(document: dict[str, Any], *, test_id: str) -> None:
        if set(document) != {"schema_version", "test_id", "assertions"}:
            raise HoldoutIntegrityError("Holdout document has unexpected fields")
        if document.get("schema_version") != "executor-independent-holdout/1.0":
            raise HoldoutIntegrityError("Unsupported holdout schema")
        if document.get("test_id") != test_id:
            raise HoldoutIntegrityError("Holdout test binding mismatch")
        assertions = document.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            raise HoldoutIntegrityError("Holdout requires assertions")
        for assertion in assertions:
            if not isinstance(assertion, dict) or set(assertion) != {
                "selector",
                "operator",
                "expected",
            }:
                raise HoldoutIntegrityError("Invalid holdout assertion")
            if assertion.get("operator") not in {"==", "!="}:
                raise HoldoutIntegrityError("Unsupported holdout operator")
            _selector({}, assertion.get("selector", "")) if assertion.get("selector") == "$" else None
