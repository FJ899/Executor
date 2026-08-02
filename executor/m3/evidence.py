from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import stat
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from executor.checkpoints import Snapshot, atomic_write_json
from executor.hashing import hash_json, sha256_bytes
from executor.m3.authorization_ledger import AuthorizationConsumptionLedger
from executor.m3.holdout import IndependentHoldoutStore
from executor.strict_json import StrictJsonError, loads_json_object


_COMMIT = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


class EvidenceIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class EvidencePackageReceipt:
    schema_version: str
    package_id: str
    manifest_sha256: str
    manifest_authentication_tag: str
    key_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M3ReplayReceipt:
    schema_version: str
    replay_id: str
    package_id: str
    manifest_sha256: str
    run_id: str
    snapshot_sha256: str
    authorization_consumption_sha256: str
    action_result_sha256: str
    holdout_replay_receipt_sha256: str
    verdict: str
    replayed_at: str
    key_id: str
    receipt_sha256: str
    authentication_tag: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ReplayableEvidenceStore:
    def __init__(self, root: str | Path, *, authentication_key: bytes, key_id: str):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir() or stat.S_IMODE(self.root.stat().st_mode) & 0o077:
            raise EvidenceIntegrityError("Evidence root must be a private directory")
        if not isinstance(authentication_key, bytes) or len(authentication_key) < 32:
            raise ValueError("authentication_key must contain at least 32 bytes")
        if not key_id:
            raise ValueError("key_id is required")
        self._key = authentication_key
        self.key_id = key_id
        self.blobs = self.root / "blobs"
        self.packages = self.root / "packages"
        self.blobs.mkdir(mode=0o700, exist_ok=True)
        self.packages.mkdir(mode=0o700, exist_ok=True)

    def _tag(self, digest: str) -> str:
        return hmac.new(self._key, digest.encode("ascii"), hashlib.sha256).hexdigest()

    def _put_blob(self, payload: bytes) -> str:
        digest = sha256_bytes(payload)
        target = self.blobs / digest
        if target.exists():
            if target.is_symlink() or target.stat().st_nlink != 1:
                raise EvidenceIntegrityError("Evidence blob path is not a private regular file")
            if not hmac.compare_digest(sha256_bytes(target.read_bytes()), digest):
                raise EvidenceIntegrityError("Existing evidence blob is corrupt")
            return digest
        temp = self.blobs / f".{digest}.{secrets.token_hex(8)}.tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(temp, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, target)
        finally:
            if temp.exists():
                temp.unlink()
        return digest

    def create_package(
        self,
        *,
        run_id: str,
        snapshot: Snapshot,
        executor_commit: str,
        repository_commits: dict[str, str],
        packet_payload_sha256: str,
        consumption_receipt: dict[str, Any],
        action_result_receipt: dict[str, Any],
        holdout_provision_receipt: dict[str, Any],
        holdout_replay_receipt: dict[str, Any],
        artifacts: dict[str, bytes],
        observations: dict[str, Any],
    ) -> EvidencePackageReceipt:
        if not _COMMIT.fullmatch(executor_commit) or not repository_commits:
            raise EvidenceIntegrityError("Concrete commit bindings are required")
        if any(not name or not _COMMIT.fullmatch(commit) for name, commit in repository_commits.items()):
            raise EvidenceIntegrityError("Repository commit binding is invalid")
        if consumption_receipt.get("payload_sha256") != packet_payload_sha256:
            raise EvidenceIntegrityError("AAP payload does not match consumption")
        if consumption_receipt.get("run_id") != run_id:
            raise EvidenceIntegrityError("Consumption run binding mismatch")
        if action_result_receipt.get("consumption_id") != consumption_receipt.get("consumption_id"):
            raise EvidenceIntegrityError("Action result is not bound to consumption")
        if holdout_replay_receipt.get("candidate_result_sha256") != hash_json(observations):
            raise EvidenceIntegrityError("Holdout replay is not bound to observations")
        artifact_hashes = {name: self._put_blob(payload) for name, payload in sorted(artifacts.items())}
        if not artifact_hashes:
            raise EvidenceIntegrityError("Evidence package requires artifacts")
        manifest = {
            "schema_version": "executor-replayable-evidence/1.0",
            "run_id": run_id,
            "snapshot": snapshot.to_dict(),
            "snapshot_sha256": hash_json(snapshot.to_dict()),
            "executor_commit": executor_commit,
            "repository_commits": dict(sorted(repository_commits.items())),
            "packet_payload_sha256": packet_payload_sha256,
            "authorization_consumption": consumption_receipt,
            "action_result_binding": action_result_receipt,
            "holdout_provision_receipt": holdout_provision_receipt,
            "holdout_replay_receipt": holdout_replay_receipt,
            "artifacts": artifact_hashes,
            "observations": observations,
            "created_at": _utc_now(),
            "key_id": self.key_id,
        }
        manifest_sha256 = hash_json(manifest)
        package_id = f"EVP-{manifest_sha256.upper()}"
        package_dir = self.packages / package_id
        try:
            package_dir.mkdir(mode=0o700)
        except FileExistsError:
            existing = package_dir / "manifest.json"
            if not existing.is_file() or hash_json(loads_json_object(existing.read_text())) != manifest_sha256:
                raise EvidenceIntegrityError("Evidence package ID collision or corruption")
        else:
            atomic_write_json(package_dir / "manifest.json", manifest)
            os.chmod(package_dir / "manifest.json", 0o600)
        return EvidencePackageReceipt(
            schema_version="executor-evidence-package-receipt/1.0",
            package_id=package_id,
            manifest_sha256=manifest_sha256,
            manifest_authentication_tag=self._tag(manifest_sha256),
            key_id=self.key_id,
        )

    def replay(
        self,
        package: EvidencePackageReceipt,
        *,
        ledger: AuthorizationConsumptionLedger,
        holdout_store: IndependentHoldoutStore,
    ) -> M3ReplayReceipt:
        if package.package_id != f"EVP-{package.manifest_sha256.upper()}":
            raise EvidenceIntegrityError("Evidence package ID does not match manifest")
        if package.key_id != self.key_id or not hmac.compare_digest(
            package.manifest_authentication_tag, self._tag(package.manifest_sha256)
        ):
            raise EvidenceIntegrityError("Evidence package receipt authentication failed")
        manifest_path = self.packages / package.package_id / "manifest.json"
        try:
            if manifest_path.is_symlink() or manifest_path.stat().st_nlink != 1:
                raise EvidenceIntegrityError("Evidence manifest is not a private regular file")
            manifest = loads_json_object(manifest_path.read_text(encoding="utf-8"))
        except (OSError, StrictJsonError) as exc:
            raise EvidenceIntegrityError(f"Evidence manifest is unreadable: {exc}") from exc
        if hash_json(manifest) != package.manifest_sha256:
            raise EvidenceIntegrityError("Evidence manifest hash mismatch")
        if set(manifest) != {
            "schema_version", "run_id", "snapshot", "snapshot_sha256",
            "executor_commit", "repository_commits", "packet_payload_sha256",
            "authorization_consumption", "action_result_binding",
            "holdout_provision_receipt", "holdout_replay_receipt", "artifacts",
            "observations", "created_at", "key_id",
        }:
            raise EvidenceIntegrityError("Evidence manifest fields are not exact")
        if manifest["schema_version"] != "executor-replayable-evidence/1.0":
            raise EvidenceIntegrityError("Unsupported evidence schema")
        if hash_json(manifest["snapshot"]) != manifest["snapshot_sha256"]:
            raise EvidenceIntegrityError("Snapshot hash mismatch")
        for name, digest in manifest["artifacts"].items():
            blob = self.blobs / digest
            if (
                not name
                or not blob.is_file()
                or blob.is_symlink()
                or blob.stat().st_nlink != 1
                or not hmac.compare_digest(sha256_bytes(blob.read_bytes()), digest)
            ):
                raise EvidenceIntegrityError("Evidence blob integrity mismatch")
        ledger.verify_evidence_binding(
            manifest["authorization_consumption"], manifest["action_result_binding"]
        )
        if not holdout_store.verify_receipt(manifest["holdout_provision_receipt"]):
            raise EvidenceIntegrityError("Holdout provision receipt authentication failed")
        if not holdout_store.verify_receipt(manifest["holdout_replay_receipt"]):
            raise EvidenceIntegrityError("Holdout replay receipt authentication failed")
        provision = manifest["holdout_provision_receipt"]
        holdout_replay = manifest["holdout_replay_receipt"]
        if (
            provision.get("schema_version") != "executor-holdout-provision/1.0"
            or holdout_replay.get("schema_version") != "executor-holdout-replay/1.0"
            or provision.get("test_id") != holdout_replay.get("test_id")
            or provision.get("holdout_id") != holdout_replay.get("holdout_id")
            or provision.get("artifact_sha256") != holdout_replay.get("artifact_sha256")
            or holdout_replay.get("verdict") != "PASS"
            or holdout_replay.get("candidate_result_sha256") != hash_json(manifest["observations"])
        ):
            raise EvidenceIntegrityError("Independent holdout replay did not pass exact observations")
        result = manifest["action_result_binding"].get("action_result", {})
        if result.get("status") != "SUCCEEDED":
            raise EvidenceIntegrityError("Bound action result is not successful")
        observations = manifest["observations"]
        if not observations or any(value is not True for value in observations.values()):
            raise EvidenceIntegrityError("Acceptance observations are incomplete or failing")
        receipt_payload = {
            "schema_version": "executor-m3-replay-receipt/1.0",
            "replay_id": f"ERP-{secrets.token_hex(16).upper()}",
            "package_id": package.package_id,
            "manifest_sha256": package.manifest_sha256,
            "run_id": manifest["run_id"],
            "snapshot_sha256": manifest["snapshot_sha256"],
            "authorization_consumption_sha256": hash_json(manifest["authorization_consumption"]),
            "action_result_sha256": manifest["action_result_binding"]["action_result_sha256"],
            "holdout_replay_receipt_sha256": manifest["holdout_replay_receipt"]["receipt_sha256"],
            "verdict": "PASS",
            "replayed_at": _utc_now(),
            "key_id": self.key_id,
        }
        receipt_sha256 = hash_json(receipt_payload)
        return M3ReplayReceipt(
            **receipt_payload,
            receipt_sha256=receipt_sha256,
            authentication_tag=self._tag(receipt_sha256),
        )

    def verify_replay_receipt(
        self,
        receipt: M3ReplayReceipt,
        *,
        run_id: str,
        snapshot: Snapshot,
    ) -> None:
        payload = receipt.to_dict()
        supplied_hash = payload.pop("receipt_sha256")
        supplied_tag = payload.pop("authentication_tag")
        expected_hash = hash_json(payload)
        if (
            receipt.verdict != "PASS"
            or receipt.run_id != run_id
            or receipt.snapshot_sha256 != hash_json(snapshot.to_dict())
            or receipt.key_id != self.key_id
            or not hmac.compare_digest(supplied_hash, expected_hash)
            or not hmac.compare_digest(supplied_tag, self._tag(expected_hash))
        ):
            raise EvidenceIntegrityError("M3 replay receipt is invalid or stale")
