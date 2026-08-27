from __future__ import annotations

import copy
import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from executor.github_trust import canonical_json
from executor.stage3_evidence import durable_write_json, sha256_json


class Stage3AuthorityError(ValueError):
    pass


P1_STAGE3_ID = "P1-STAGE3-001@1.0"
P1_STAGE3_SHA256 = "a72b505da9bbbf05e9a0b70affaf4e06b56374e6122699ac135d3d303a87b9d0"
STAGE3_ACTION = "APPLY_EXACTLY_ONE_VALIDATED_EXISTING_FILE_REPLACEMENT"
AUTH_SCHEMA = "executor-human-stage3-effect-authorization/1.0"
AUTH_HASH_CONSTRUCTION = "SHA256_CANONICAL_JSON_WITHOUT_AUTHORIZATION_PAYLOAD_SHA256"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,191}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class HumanStage3EffectAuthorization:
    authorization_id: str
    human_principal: dict[str, Any]
    human_principal_evidence_ref: str
    stage2_terminal_result_sha256: str
    repository: str
    source_commit: str
    source_tree: str
    proposal_id: str
    proposal_payload_sha256: str
    mutation_path: str
    before_sha256: str
    after_sha256: str
    provider_generation_binding_sha256: str
    runtime_trust_bundle_sha256: str
    bounded_environment_sha256: str
    workspace_instance_id: str
    issued_at: str
    expires_at: str
    payload_sha256: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class AuthorityConsumption:
    authorization_id: str
    effect_binding_sha256: str
    marker_path: str
    marker_sha256: str
    state: str = "CONSUMED_PENDING"

    def to_dict(self) -> dict[str, str]:
        return {
            "authorization_id": self.authorization_id,
            "effect_binding_sha256": self.effect_binding_sha256,
            "marker_path": self.marker_path,
            "marker_sha256": self.marker_sha256,
            "state": self.state,
        }


def _require_sha(value: Any, *, label: str, git: bool = False) -> str:
    pattern = _GIT_SHA if git else _SHA256
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise Stage3AuthorityError(f"{label} is invalid")
    return value


def _parse_utc(value: Any, *, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise Stage3AuthorityError(f"{label} must be RFC3339 UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise Stage3AuthorityError(f"{label} is invalid") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise Stage3AuthorityError(f"{label} must be UTC")
    return parsed.astimezone(timezone.utc)


def _authorization_hash(value: dict[str, Any]) -> str:
    material = copy.deepcopy(value)
    material.pop("authorization_payload_sha256", None)
    return hashlib.sha256(canonical_json(material).encode("utf-8")).hexdigest()


def validate_human_stage3_effect_authorization(
    value: dict[str, Any],
    *,
    frozen_result: dict[str, Any],
    stage2_terminal_result_sha256: str,
    repository: str,
    source_commit: str,
    source_tree: str,
    proposal_id: str,
    proposal_payload_sha256: str,
    mutation_path: str,
    before_sha256: str,
    after_sha256: str,
    provider_generation_binding_sha256: str,
    runtime_trust_bundle_sha256: str,
    bounded_environment_sha256: str,
    workspace_instance_id: str,
    now: datetime | None = None,
) -> HumanStage3EffectAuthorization:
    expected = {
        "schema_version", "authorization_id", "human_principal", "human_principal_evidence_ref",
        "frozen_task_contract_id", "frozen_task_contract_sha256", "stage2_terminal_result_sha256",
        "repository", "source_commit", "source_tree", "proposal_id", "proposal_payload_sha256",
        "mutation_path", "before_sha256", "after_sha256", "provider_generation_binding_sha256",
        "runtime_trust_bundle_sha256", "bounded_environment_sha256", "workspace_instance_id",
        "action", "issued_at", "expires_at", "authorization_hash_construction",
        "authorization_payload_sha256",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise Stage3AuthorityError("human Stage-3 effect authorization has invalid fields")
    if value.get("schema_version") != AUTH_SCHEMA:
        raise Stage3AuthorityError("human Stage-3 effect authorization schema mismatch")
    auth_id = value.get("authorization_id")
    if not isinstance(auth_id, str) or _SAFE_ID.fullmatch(auth_id) is None:
        raise Stage3AuthorityError("authorization_id is invalid")
    if value.get("frozen_task_contract_id") != P1_STAGE3_ID:
        raise Stage3AuthorityError("human authority is bound to a different Stage-3 Task Contract")
    if value.get("frozen_task_contract_sha256") != P1_STAGE3_SHA256:
        raise Stage3AuthorityError("human authority Stage-3 Task Contract hash mismatch")
    if value.get("action") != STAGE3_ACTION:
        raise Stage3AuthorityError("human authority action mismatch")
    if value.get("authorization_hash_construction") != AUTH_HASH_CONSTRUCTION:
        raise Stage3AuthorityError("human authority hash construction mismatch")
    expected_pairs = (
        ("stage2 terminal result", value.get("stage2_terminal_result_sha256"), stage2_terminal_result_sha256),
        ("repository", value.get("repository"), repository),
        ("source commit", value.get("source_commit"), source_commit),
        ("source tree", value.get("source_tree"), source_tree),
        ("proposal id", value.get("proposal_id"), proposal_id),
        ("proposal payload", value.get("proposal_payload_sha256"), proposal_payload_sha256),
        ("mutation path", value.get("mutation_path"), mutation_path),
        ("before hash", value.get("before_sha256"), before_sha256),
        ("after hash", value.get("after_sha256"), after_sha256),
        ("provider generation binding", value.get("provider_generation_binding_sha256"), provider_generation_binding_sha256),
        ("runtime trust bundle", value.get("runtime_trust_bundle_sha256"), runtime_trust_bundle_sha256),
        ("bounded environment", value.get("bounded_environment_sha256"), bounded_environment_sha256),
        ("workspace instance", value.get("workspace_instance_id"), workspace_instance_id),
    )
    for label, actual, required in expected_pairs:
        if actual != required:
            raise Stage3AuthorityError(f"human authority {label} mismatch")
    for field in (
        "stage2_terminal_result_sha256", "proposal_payload_sha256", "before_sha256", "after_sha256",
        "provider_generation_binding_sha256", "runtime_trust_bundle_sha256", "bounded_environment_sha256",
        "authorization_payload_sha256",
    ):
        _require_sha(value.get(field), label=field)
    _require_sha(value.get("source_commit"), label="source_commit", git=True)
    _require_sha(value.get("source_tree"), label="source_tree", git=True)
    if not isinstance(value.get("workspace_instance_id"), str) or _SAFE_ID.fullmatch(value["workspace_instance_id"]) is None:
        raise Stage3AuthorityError("workspace_instance_id is invalid")

    decision = frozen_result.get("decision_evidence")
    if not isinstance(decision, dict):
        contract = frozen_result.get("contract")
        decision = contract.get("decision_evidence") if isinstance(contract, dict) else None
    if not isinstance(decision, dict):
        raise Stage3AuthorityError("frozen human authority evidence is missing")
    actor = decision.get("actor")
    evidence_ref = decision.get("evidence_ref")
    principal = value.get("human_principal")
    expected_principal = {
        "provider": "GITHUB",
        "login": actor.get("login") if isinstance(actor, dict) else None,
        "id": actor.get("id") if isinstance(actor, dict) else None,
    }
    if principal != expected_principal:
        raise Stage3AuthorityError("human principal does not match frozen governance principal")
    if value.get("human_principal_evidence_ref") != evidence_ref:
        raise Stage3AuthorityError("human principal evidence reference mismatch")

    issued = _parse_utc(value.get("issued_at"), label="authorization issued_at")
    expires = _parse_utc(value.get("expires_at"), label="authorization expires_at")
    if expires <= issued:
        raise Stage3AuthorityError("human authority expiry must postdate issue time")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if issued > current:
        raise Stage3AuthorityError("human authority issue time is in the future")
    if expires <= current:
        raise Stage3AuthorityError("human authority has expired")
    payload_sha = _authorization_hash(value)
    if payload_sha != value.get("authorization_payload_sha256"):
        raise Stage3AuthorityError("human authority canonical payload hash mismatch")
    return HumanStage3EffectAuthorization(
        authorization_id=auth_id, human_principal=copy.deepcopy(principal), human_principal_evidence_ref=evidence_ref,
        stage2_terminal_result_sha256=stage2_terminal_result_sha256, repository=repository,
        source_commit=source_commit, source_tree=source_tree, proposal_id=proposal_id,
        proposal_payload_sha256=proposal_payload_sha256, mutation_path=mutation_path,
        before_sha256=before_sha256, after_sha256=after_sha256,
        provider_generation_binding_sha256=provider_generation_binding_sha256,
        runtime_trust_bundle_sha256=runtime_trust_bundle_sha256,
        bounded_environment_sha256=bounded_environment_sha256, workspace_instance_id=workspace_instance_id,
        issued_at=value["issued_at"], expires_at=value["expires_at"], payload_sha256=payload_sha,
        raw=copy.deepcopy(value),
    )


def authority_marker_path(control_root: str | Path, authorization_id: str) -> Path:
    digest = hashlib.sha256(authorization_id.encode("utf-8")).hexdigest()
    return Path(control_root) / "receipts" / "authority-consumption" / f"{digest}.json"


def authority_is_unused(control_root: str | Path, authorization_id: str) -> bool:
    return not authority_marker_path(control_root, authorization_id).exists()


def consume_authority_once(*, control_root: str | Path, authority: HumanStage3EffectAuthorization, effect_binding_sha256: str) -> AuthorityConsumption:
    _require_sha(effect_binding_sha256, label="effect binding")
    marker = authority_marker_path(control_root, authority.authorization_id)
    if marker.exists():
        raise Stage3AuthorityError("human Stage-3 effect authorization is already consumed")
    receipt = {
        "schema_version": "executor-stage3-authority-consumption/1.0",
        "authorization_id": authority.authorization_id,
        "authorization_payload_sha256": authority.payload_sha256,
        "effect_binding_sha256": effect_binding_sha256,
        "state_before": "UNUSED", "state_after": "CONSUMED_PENDING", "action": STAGE3_ACTION,
    }
    try:
        marker_sha = durable_write_json(marker, receipt, exclusive=True)
    except FileExistsError as exc:
        raise Stage3AuthorityError("human Stage-3 effect authorization replay detected") from exc
    return AuthorityConsumption(authority.authorization_id, effect_binding_sha256, str(marker), marker_sha)


def build_terminal_authority_receipt(*, control_root: str | Path, consumption: AuthorityConsumption, terminal_status: str, effect_evidence_sha256: str) -> str:
    _require_sha(effect_evidence_sha256, label="effect evidence")
    path = Path(control_root) / "receipts" / "authority-terminal" / (hashlib.sha256(consumption.authorization_id.encode("utf-8")).hexdigest() + ".json")
    value = {
        "schema_version": "executor-stage3-authority-terminal/1.0",
        "authorization_id": consumption.authorization_id,
        "consumption_marker_sha256": consumption.marker_sha256,
        "effect_binding_sha256": consumption.effect_binding_sha256,
        "state_before": "CONSUMED_PENDING", "state_after": "TERMINAL",
        "terminal_status": terminal_status, "effect_evidence_sha256": effect_evidence_sha256,
    }
    return durable_write_json(path, value, exclusive=True)
