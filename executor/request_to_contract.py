from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from executor.gp001_contract import validate_gp001_task_contract


_PROFILE_SCHEMA = "executor-contract-formation-profile/1.0"


class FormationError(RuntimeError):
    pass


class FormationStatus(str, Enum):
    REQUEST_RECEIVED = "REQUEST_RECEIVED"
    INTERPRETATION_PROPOSED = "INTERPRETATION_PROPOSED"
    DRAFT_CONTRACT_CREATED = "DRAFT_CONTRACT_CREATED"
    DRAFT_CRITIQUED = "DRAFT_CRITIQUED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    AWAITING_VERIFIED_HUMAN_AUTHORIZATION = "AWAITING_VERIFIED_HUMAN_AUTHORIZATION"


@dataclass(frozen=True)
class ProvenanceRecord:
    path: str
    source: str
    value: Any
    note: str = ""
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.source not in {"USER", "MODEL"}:
            raise FormationError("provenance source must be USER or MODEL")
        if not self.path.strip():
            raise FormationError("provenance path must be non-empty")
        if self.source == "MODEL" and self.confidence is not None:
            if not 0.0 <= self.confidence <= 1.0:
                raise FormationError("model confidence must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "path": self.path,
            "source": self.source,
            "value": copy.deepcopy(self.value),
            "note": self.note,
        }
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        return payload


@dataclass(frozen=True)
class CritiqueFinding:
    code: str
    message: str
    blocking: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "blocking": self.blocking,
        }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FormationError(f"cannot load formation input {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FormationError(f"formation input must be an object: {path}")
    return payload


class RequestToContract001:
    """Govern one known GP001 request up to a verified human authority boundary.

    This slice deliberately stops before authorization/freeze. A process-local
    claim such as ``authority_source=HUMAN`` is not accepted as proof that a
    human authorized the draft. A later superior boundary must provide verified
    external evidence bound to the exact draft hash before executable authority
    can exist.
    """

    def __init__(
        self,
        *,
        executor_root: Path,
        request_id: str,
        user_request: str,
        profile_path: Path | None = None,
    ) -> None:
        self.executor_root = executor_root.resolve()
        self.request_id = request_id.strip()
        self.user_request = user_request.strip()
        if not self.request_id:
            raise FormationError("request_id is required")
        if not self.user_request:
            raise FormationError("user_request is required")

        profile_file = profile_path or (
            self.executor_root / "formation_profiles" / "REQUEST_TO_CONTRACT_001.json"
        )
        self._profile = _load_json(profile_file)
        if self._profile.get("schema_version") != _PROFILE_SCHEMA:
            raise FormationError("invalid request-to-contract formation profile schema")
        if self._profile.get("id") != "REQUEST_TO_CONTRACT_001":
            raise FormationError("unexpected formation profile id")

        target_path = str(self._profile.get("target_task_path", "")).strip()
        if not target_path:
            raise FormationError("formation profile target_task_path is required")
        target_file = (self.executor_root / target_path).resolve()
        try:
            target_file.relative_to(self.executor_root)
        except ValueError as exc:
            raise FormationError("formation profile target task escaped executor root") from exc

        self._canonical_task = _load_json(target_file)
        if self._canonical_task.get("id") != self._profile.get("expected_task_id"):
            raise FormationError("canonical task id does not match formation profile")
        validation = validate_gp001_task_contract(self._canonical_task)
        if validation.status.value != "VALID":
            raise FormationError("canonical GP001 task contract is not valid")

        self.status = FormationStatus.REQUEST_RECEIVED
        self._understood_objective: str | None = None
        self._proposed_task: dict[str, Any] | None = None
        self._provenance: list[ProvenanceRecord] = [
            ProvenanceRecord(
                path="$.user_request",
                source="USER",
                value=self.user_request,
                note="verbatim request supplied by the user",
            )
        ]
        self._out_of_scope_discoveries: list[str] = []
        self._open_questions: list[str] = []
        self._draft_sha256: str | None = None
        self._draft_snapshot: str | None = None
        self._critique: list[CritiqueFinding] = []

    @property
    def draft_sha256(self) -> str | None:
        return self._draft_sha256

    def propose_interpretation(
        self,
        *,
        understood_objective: str,
        proposed_task_contract: dict[str, Any],
        user_facts: Iterable[tuple[str, Any]] = (),
        model_inferences: Iterable[tuple[str, Any, float | None]] = (),
        out_of_scope_discoveries: Iterable[str] = (),
        open_questions: Iterable[str] = (),
    ) -> None:
        if self.status is not FormationStatus.REQUEST_RECEIVED:
            raise FormationError("interpretation may only be proposed from REQUEST_RECEIVED")
        objective = understood_objective.strip()
        if not objective:
            raise FormationError("understood_objective is required")
        if not isinstance(proposed_task_contract, dict):
            raise FormationError("proposed_task_contract must be an object")

        self._understood_objective = objective
        self._proposed_task = copy.deepcopy(proposed_task_contract)
        for path, value in user_facts:
            self._provenance.append(
                ProvenanceRecord(path=path, source="USER", value=copy.deepcopy(value))
            )
        for path, value, confidence in model_inferences:
            self._provenance.append(
                ProvenanceRecord(
                    path=path,
                    source="MODEL",
                    value=copy.deepcopy(value),
                    confidence=confidence,
                )
            )
        self._out_of_scope_discoveries = [
            item.strip() for item in out_of_scope_discoveries if item.strip()
        ]
        self._open_questions = [item.strip() for item in open_questions if item.strip()]
        self.status = FormationStatus.INTERPRETATION_PROPOSED

    def create_draft(self) -> dict[str, Any]:
        if self.status is not FormationStatus.INTERPRETATION_PROPOSED:
            raise FormationError("draft may only be created after interpretation proposal")
        if self._proposed_task is None:
            raise FormationError("no proposed task contract")
        payload = {
            "schema_version": "executor-contract-formation-draft/1.0",
            "profile_id": self._profile["id"],
            "request_id": self.request_id,
            "user_request": self.user_request,
            "understood_objective": self._understood_objective,
            "provenance": [record.to_dict() for record in self._provenance],
            "proposed_task_contract": self._proposed_task,
            "out_of_scope_discoveries": self._out_of_scope_discoveries,
            "open_questions": self._open_questions,
        }
        self._draft_snapshot = _canonical_json(payload)
        self._draft_sha256 = _sha256_text(self._draft_snapshot)
        self._critique = []
        self.status = FormationStatus.DRAFT_CONTRACT_CREATED
        return self.decision_surface()

    def critique(self) -> tuple[CritiqueFinding, ...]:
        if self.status is not FormationStatus.DRAFT_CONTRACT_CREATED:
            raise FormationError("critique requires DRAFT_CONTRACT_CREATED")
        if self._proposed_task is None:
            raise FormationError("no proposed task contract")

        findings: list[CritiqueFinding] = []
        validation = validate_gp001_task_contract(self._proposed_task)
        for issue in validation.issues:
            findings.append(
                CritiqueFinding(
                    code=f"GP001_{issue.code}",
                    message=f"{issue.path}: {issue.message}",
                )
            )
        if _canonical_json(self._proposed_task) != _canonical_json(self._canonical_task):
            findings.append(
                CritiqueFinding(
                    code="CONTRACT_DIVERGENCE_FROM_ACCEPTED_GP001_PROFILE",
                    message=(
                        "proposed executable contract differs from the accepted GP001 "
                        "contract and cannot be promoted by interpretation alone"
                    ),
                )
            )
        if self._open_questions:
            findings.append(
                CritiqueFinding(
                    code="OPEN_QUESTIONS_REQUIRE_CLARIFICATION",
                    message="unresolved questions must be resolved before authorization",
                )
            )

        self._critique = findings
        self.status = FormationStatus.DRAFT_CRITIQUED
        return tuple(findings)

    def present_for_authorization(self) -> dict[str, Any]:
        if self.status is not FormationStatus.DRAFT_CRITIQUED:
            raise FormationError("authorization surface requires a critiqued draft")
        if any(item.blocking for item in self._critique):
            self.status = FormationStatus.NEEDS_CLARIFICATION
        else:
            self.status = FormationStatus.AWAITING_VERIFIED_HUMAN_AUTHORIZATION
        return self.decision_surface()

    def decision_surface(self) -> dict[str, Any]:
        task = self._proposed_task or {}
        golden = task.get("golden_path", {}) if isinstance(task, dict) else {}
        problem = golden.get("problem", {}) if isinstance(golden, dict) else {}
        scope = golden.get("scope", {}) if isinstance(golden, dict) else {}
        success = golden.get("success", {}) if isinstance(golden, dict) else {}
        repositories = task.get("repositories", {}) if isinstance(task, dict) else {}
        return {
            "request_id": self.request_id,
            "request": self.user_request,
            "understood_objective": self._understood_objective,
            "target": copy.deepcopy(repositories.get("target")),
            "target_test": problem.get("target_test") if isinstance(problem, dict) else None,
            "proposed_write_scope": copy.deepcopy(scope.get("allowed_paths", []))
            if isinstance(scope, dict)
            else [],
            "protected_material": copy.deepcopy(scope.get("protected_paths", []))
            if isinstance(scope, dict)
            else [],
            "success_conditions": copy.deepcopy(success) if isinstance(success, dict) else {},
            "discovered_but_out_of_scope": list(self._out_of_scope_discoveries),
            "unresolved_assumptions": list(self._open_questions),
            "provenance": [record.to_dict() for record in self._provenance],
            "critique": [finding.to_dict() for finding in self._critique],
            "draft_sha256": self._draft_sha256,
            "status": self.status.value,
            "executable": False,
        }

    def export_human_authorization_request(self) -> dict[str, Any]:
        if self.status is not FormationStatus.AWAITING_VERIFIED_HUMAN_AUTHORIZATION:
            raise FormationError(
                "human authorization request requires a clean critiqued draft"
            )
        if self._draft_sha256 is None:
            raise FormationError("draft hash missing")
        return {
            "schema_version": "executor-human-formation-authorization-request/1.0",
            "request_id": self.request_id,
            "formation_profile": self._profile["id"],
            "draft_sha256": self._draft_sha256,
            "allowed_decisions": ["ACCEPT", "MODIFY", "REJECT"],
            "decision_surface": self.decision_surface(),
            "required_authority": "VERIFIED_EXTERNAL_HUMAN_AUTHORITY",
            "status": "AWAITING_VERIFIED_HUMAN_AUTHORIZATION",
        }

    def frozen_task_contract(self) -> dict[str, Any]:
        raise FormationError(
            "no executable contract exists: verified external human authorization "
            "and freeze are not implemented in REQUEST_TO_CONTRACT_001 phase 1"
        )
