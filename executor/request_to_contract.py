from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from executor.github_authority import GovernedAuthorityLedger
from executor.github_trust import (
    GitHubEvidenceSource,
    GitHubTrustError,
    GitHubTrustProfile,
    canonical_json,
    verify_github_decision,
    verify_github_request,
)
from executor.gp001_contract import validate_gp001_task_contract
from executor.pilot_contract import (
    PilotContractError,
    apply_github_decision,
    build_pilot_draft,
)
from executor.repository_identity import RepositoryIdentityError, verify_repository_checkout
from executor.repository_snapshot import RepositorySnapshotError, verify_worktree_file


_PROFILE_SCHEMA = "executor-contract-formation-profile/1.0"
_PROFILE_PATH = "formation_profiles/REQUEST_TO_CONTRACT_001.json"
_EXECUTOR_REPOSITORY = "FJ899/Executor"
_FORMATION_BINDING_SCHEMA = "executor-contract-formation-binding/1.0"


class FormationError(RuntimeError):
    pass


class FormationStatus(str, Enum):
    REQUEST_RECEIVED = "REQUEST_RECEIVED"
    INTERPRETATION_PROPOSED = "INTERPRETATION_PROPOSED"
    DRAFT_CONTRACT_CREATED = "DRAFT_CONTRACT_CREATED"
    DRAFT_CRITIQUED = "DRAFT_CRITIQUED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    AWAITING_VERIFIED_HUMAN_AUTHORIZATION = "AWAITING_VERIFIED_HUMAN_AUTHORIZATION"
    MODIFICATION_REQUIRED = "MODIFICATION_REQUIRED"
    REJECTED = "REJECTED"
    AUTHORIZED_AND_FROZEN = "AUTHORIZED_AND_FROZEN"


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


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _decode_object(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FormationError(f"cannot decode {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FormationError(f"{label} must be an object")
    return payload


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RequestToContract001:
    """Govern one known GP001 request through verified human freeze.

    Formation preserves the original request/model provenance boundary and may
    only become executable through the existing provider-verified GitHub
    authority path. No caller-created object can self-declare human authority.
    """

    def __init__(
        self,
        *,
        executor_root: Path,
        executor_commit: str,
        request_id: str,
        user_request: str,
    ) -> None:
        self.request_id = request_id.strip()
        self.user_request = user_request.strip()
        if not self.request_id:
            raise FormationError("request_id is required")
        if not self.user_request:
            raise FormationError("user_request is required")

        try:
            root = verify_repository_checkout(
                executor_root,
                repository=_EXECUTOR_REPOSITORY,
                commit=executor_commit,
                require_head=True,
            )
            profile_raw = verify_worktree_file(
                root,
                commit=executor_commit,
                path=_PROFILE_PATH,
            )
        except (RepositoryIdentityError, RepositorySnapshotError) as exc:
            raise FormationError(f"unverified Executor formation source: {exc}") from exc

        self.executor_root = root
        self.executor_commit = executor_commit.lower()
        self._profile = _decode_object(profile_raw, label="formation profile")
        self._profile_sha256 = _sha256_bytes(profile_raw)
        if self._profile.get("schema_version") != _PROFILE_SCHEMA:
            raise FormationError("invalid request-to-contract formation profile schema")
        if self._profile.get("id") != "REQUEST_TO_CONTRACT_001":
            raise FormationError("unexpected formation profile id")

        target_path = str(self._profile.get("target_task_path", "")).strip()
        if not target_path:
            raise FormationError("formation profile target_task_path is required")
        try:
            task_raw = verify_worktree_file(
                root,
                commit=executor_commit,
                path=target_path,
            )
        except RepositorySnapshotError as exc:
            raise FormationError(f"unverified canonical task source: {exc}") from exc

        self._canonical_task = _decode_object(task_raw, label="canonical GP001 task")
        self._canonical_task_sha256 = _sha256_bytes(task_raw)
        if self._canonical_task.get("id") != self._profile.get("expected_task_id"):
            raise FormationError("canonical task id does not match formation profile")
        validation = validate_gp001_task_contract(self._canonical_task)
        if validation.status.value != "VALID":
            raise FormationError("canonical GP001 task contract is not valid")

        self.status = FormationStatus.REQUEST_RECEIVED
        self._draft_version = 1
        self._supersedes_draft_sha256: str | None = None
        self._invalidated_draft_sha256s: list[str] = []
        self._understood_objective: str | None = None
        self._proposed_task: dict[str, Any] | None = None
        self._provenance: list[ProvenanceRecord] = self._base_provenance()
        self._out_of_scope_discoveries: list[str] = []
        self._open_questions: list[str] = []
        self._draft_sha256: str | None = None
        self._draft_payload: dict[str, Any] | None = None
        self._critique: list[CritiqueFinding] = []
        self._github_authority_request_payload: dict[str, Any] | None = None
        self._last_decision_result: dict[str, Any] | None = None
        self._frozen_result: dict[str, Any] | None = None

    def _base_provenance(self) -> list[ProvenanceRecord]:
        return [
            ProvenanceRecord(
                path="$.user_request",
                source="USER",
                value=self.user_request,
                note="verbatim request supplied by the user",
            )
        ]

    @property
    def draft_sha256(self) -> str | None:
        return self._draft_sha256

    @property
    def draft_version(self) -> int:
        return self._draft_version

    def propose_interpretation(
        self,
        *,
        understood_objective: str,
        proposed_task_contract: dict[str, Any],
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
        self._provenance.append(
            ProvenanceRecord(
                path="$.understood_objective",
                source="MODEL",
                value=objective,
                note="interpretation proposal; not authoritative user intent",
            )
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

    def propose_canonical_gp001(
        self,
        *,
        understood_objective: str,
        out_of_scope_discoveries: Iterable[str] = (),
        open_questions: Iterable[str] = (),
    ) -> None:
        repositories = self._canonical_task.get("repositories", {})
        golden_path = self._canonical_task.get("golden_path", {})
        target = repositories.get("target", {}) if isinstance(repositories, dict) else {}
        problem = golden_path.get("problem", {}) if isinstance(golden_path, dict) else {}
        self.propose_interpretation(
            understood_objective=understood_objective,
            proposed_task_contract=self._canonical_task,
            model_inferences=(
                ("$.target.repository", target.get("name"), None),
                ("$.target.commit", target.get("commit"), None),
                ("$.target.test", problem.get("target_test"), None),
            ),
            out_of_scope_discoveries=out_of_scope_discoveries,
            open_questions=open_questions,
        )

    def create_draft(self) -> dict[str, Any]:
        if self.status is not FormationStatus.INTERPRETATION_PROPOSED:
            raise FormationError("draft may only be created after interpretation proposal")
        if self._proposed_task is None:
            raise FormationError("no proposed task contract")
        payload = {
            "schema_version": "executor-contract-formation-draft/1.0",
            "executor_repository": _EXECUTOR_REPOSITORY,
            "executor_commit": self.executor_commit,
            "profile_id": self._profile["id"],
            "profile_sha256": self._profile_sha256,
            "canonical_task_sha256": self._canonical_task_sha256,
            "request_id": self.request_id,
            "draft_version": self._draft_version,
            "supersedes_draft_sha256": self._supersedes_draft_sha256,
            "user_request": self.user_request,
            "understood_objective": self._understood_objective,
            "provenance": [record.to_dict() for record in self._provenance],
            "proposed_task_contract": self._proposed_task,
            "out_of_scope_discoveries": self._out_of_scope_discoveries,
            "open_questions": self._open_questions,
        }
        self._draft_payload = copy.deepcopy(payload)
        self._draft_sha256 = _sha256_text(_canonical_json(payload))
        self._github_authority_request_payload = None
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
            "draft_version": self._draft_version,
            "supersedes_draft_sha256": self._supersedes_draft_sha256,
            "invalidated_draft_sha256s": list(self._invalidated_draft_sha256s),
            "draft_sha256": self._draft_sha256,
            "status": self.status.value,
            "executable": self.status is FormationStatus.AUTHORIZED_AND_FROZEN,
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
            "executor_repository": _EXECUTOR_REPOSITORY,
            "executor_commit": self.executor_commit,
            "formation_profile": self._profile["id"],
            "formation_profile_sha256": self._profile_sha256,
            "canonical_task_sha256": self._canonical_task_sha256,
            "draft_version": self._draft_version,
            "supersedes_draft_sha256": self._supersedes_draft_sha256,
            "draft_sha256": self._draft_sha256,
            "allowed_decisions": ["ACCEPT", "MODIFY", "REJECT"],
            "decision_surface": self.decision_surface(),
            "required_authority": "VERIFIED_EXTERNAL_HUMAN_AUTHORITY",
            "status": "AWAITING_VERIFIED_HUMAN_AUTHORIZATION",
        }

    def _github_task_projection(self) -> dict[str, Any]:
        if self._proposed_task is None:
            raise FormationError("no proposed task contract")
        golden = self._proposed_task.get("golden_path")
        budgets = self._proposed_task.get("budgets")
        if not isinstance(golden, dict) or not isinstance(budgets, dict):
            raise FormationError("GP001 task lacks golden path or budgets")
        problem = golden.get("problem")
        scope = golden.get("scope")
        commands = golden.get("commands")
        if not all(isinstance(item, dict) for item in (problem, scope, commands)):
            raise FormationError("GP001 task cannot be projected into GitHub authority request")
        allowed_paths = copy.deepcopy(scope.get("allowed_paths"))
        protected_paths = copy.deepcopy(scope.get("protected_paths"))
        target_test = copy.deepcopy(commands.get("target_test_argv"))
        regression = copy.deepcopy(commands.get("regression_argv"))
        if not isinstance(allowed_paths, list) or not 1 <= len(allowed_paths) <= 3:
            raise FormationError("GP001 authority request exceeds the bounded file limit")
        if not isinstance(target_test, list) or not target_test:
            raise FormationError("GP001 target test command is missing")
        if not isinstance(regression, list) or not regression:
            raise FormationError("GP001 regression commands are missing")
        return {
            "class": "BOUNDED_CORRECTNESS_OR_QUALITY_FIX",
            "problem_statement": problem.get("statement"),
            "allowed_paths": allowed_paths,
            "protected_paths": protected_paths,
            "precondition_argv": [target_test],
            "postcondition_argv": [copy.deepcopy(target_test)],
            "regression_argv": regression,
            "max_production_files": len(allowed_paths),
            "max_patch_lines": budgets.get("max_patch_lines"),
        }

    def build_github_authority_request(
        self,
        *,
        source: GitHubEvidenceSource,
        profile: GitHubTrustProfile,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Build the exact provider request payload from the governed draft.

        The target tree and request lifetime are derived by the system. Callers
        no longer hand-author a second GitHub request JSON between formation and
        verified authority.
        """

        if self.status is not FormationStatus.AWAITING_VERIFIED_HUMAN_AUTHORIZATION:
            raise FormationError("GitHub authority request requires a clean current draft")
        if self._draft_sha256 is None or self._draft_payload is None:
            raise FormationError("current formation draft is missing")
        if self._github_authority_request_payload is not None:
            return copy.deepcopy(self._github_authority_request_payload)
        if self._draft_sha256 in self._invalidated_draft_sha256s:
            raise FormationError("invalidated formation draft cannot request authority")

        repositories = self._proposed_task.get("repositories", {}) if self._proposed_task else {}
        target = repositories.get("target", {}) if isinstance(repositories, dict) else {}
        repository = target.get("name") if isinstance(target, dict) else None
        commit = target.get("commit") if isinstance(target, dict) else None
        if not isinstance(repository, str) or not isinstance(commit, str):
            raise FormationError("formation target repository/commit is missing")
        if repository.lower() not in {
            item.lower() for item in profile.allowed_target_repositories
        }:
            raise FormationError("formation target repository is outside the trust profile")

        commit_url = f"https://api.github.com/repos/{repository}/git/commits/{commit}"
        try:
            commit_evidence = source.fetch_json(commit_url)
        except GitHubTrustError as exc:
            raise FormationError(f"target commit evidence is unavailable: {exc}") from exc
        tree = commit_evidence.get("tree")
        if (
            commit_evidence.get("sha") != commit
            or not isinstance(tree, dict)
            or not isinstance(tree.get("sha"), str)
        ):
            raise FormationError("target commit/tree provider binding is invalid")

        current = (now or _utc_now()).astimezone(timezone.utc)
        expires = current + timedelta(seconds=profile.max_decision_lifetime_seconds)
        nonce = f"formation-{self._draft_version}-{self._draft_sha256[:24]}"
        payload = {
            "schema_version": "executor-github-request/1.0",
            "request_id": self.request_id,
            "target": {
                "repository": repository,
                "commit": commit,
                "tree": tree["sha"],
            },
            "task": self._github_task_projection(),
            "expires_at": expires.isoformat().replace("+00:00", "Z"),
            "nonce": nonce,
        }
        self._github_authority_request_payload = copy.deepcopy(payload)
        return copy.deepcopy(payload)

    def _formation_binding(self) -> dict[str, Any]:
        if (
            self._draft_sha256 is None
            or self._draft_payload is None
            or self._github_authority_request_payload is None
        ):
            raise FormationError("formation binding cannot be built before authority request")
        return {
            "schema_version": _FORMATION_BINDING_SCHEMA,
            "executor_repository": _EXECUTOR_REPOSITORY,
            "executor_commit": self.executor_commit,
            "formation_profile": self._profile["id"],
            "formation_profile_sha256": self._profile_sha256,
            "canonical_task_sha256": self._canonical_task_sha256,
            "request_id": self.request_id,
            "draft_version": self._draft_version,
            "supersedes_draft_sha256": self._supersedes_draft_sha256,
            "draft_sha256": self._draft_sha256,
            "draft": copy.deepcopy(self._draft_payload),
            "authority_request_payload": copy.deepcopy(
                self._github_authority_request_payload
            ),
            "authority_request_payload_sha256": hashlib.sha256(
                canonical_json(self._github_authority_request_payload).encode("utf-8")
            ).hexdigest(),
            "invalidated_draft_sha256s": list(self._invalidated_draft_sha256s),
        }

    def apply_github_authority_decision(
        self,
        *,
        source: GitHubEvidenceSource,
        profile: GitHubTrustProfile,
        issue_number: int,
        comment_id: int,
        ledger: GovernedAuthorityLedger,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Verify one provider decision and transition formation fail-closed."""

        if self.status is not FormationStatus.AWAITING_VERIFIED_HUMAN_AUTHORIZATION:
            raise FormationError("only the current authorization-ready draft may be decided")
        if self._draft_sha256 is None or self._github_authority_request_payload is None:
            raise FormationError("GitHub authority request has not been built for this draft")
        if self._draft_sha256 in self._invalidated_draft_sha256s:
            raise FormationError("invalidated formation draft cannot be authorized")

        try:
            request = verify_github_request(
                source,
                profile=profile,
                issue_number=issue_number,
                now=now,
            )
            if request.payload != self._github_authority_request_payload:
                raise FormationError(
                    "verified GitHub request does not equal the generated formation request"
                )
            decision = verify_github_decision(
                source,
                profile=profile,
                request=request,
                comment_id=comment_id,
                draft_sha256=self._draft_sha256,
                now=now,
            )
            result = apply_github_decision(
                draft=build_pilot_draft(request),
                decision=decision,
                source=source,
                profile=profile,
                ledger=ledger,
                authority_draft_sha256=self._draft_sha256,
                expected_request_payload=self._github_authority_request_payload,
                formation_binding=self._formation_binding(),
            )
        except (GitHubTrustError, PilotContractError) as exc:
            raise FormationError(f"verified human decision blocked: {exc}") from exc

        self._last_decision_result = copy.deepcopy(result)
        if result.get("status") == "MODIFICATION_REQUIRED":
            if self._draft_sha256 not in self._invalidated_draft_sha256s:
                self._invalidated_draft_sha256s.append(self._draft_sha256)
            self._supersedes_draft_sha256 = self._draft_sha256
            self._github_authority_request_payload = None
            self.status = FormationStatus.MODIFICATION_REQUIRED
        elif result.get("status") == "REJECTED":
            self.status = FormationStatus.REJECTED
        elif result.get("status") == "AUTHORIZED_AND_FROZEN":
            self._frozen_result = copy.deepcopy(result)
            self.status = FormationStatus.AUTHORIZED_AND_FROZEN
        else:
            raise FormationError("unexpected verified formation decision result")
        return copy.deepcopy(result)

    def revise_after_modify(
        self,
        *,
        understood_objective: str,
        proposed_task_contract: dict[str, Any],
        model_inferences: Iterable[tuple[str, Any, float | None]] = (),
        out_of_scope_discoveries: Iterable[str] = (),
        open_questions: Iterable[str] = (),
    ) -> dict[str, Any]:
        """Create a new non-authorized draft after a verified MODIFY decision."""

        if self.status is not FormationStatus.MODIFICATION_REQUIRED:
            raise FormationError("revision requires a verified MODIFY decision")
        self._draft_version += 1
        self._understood_objective = None
        self._proposed_task = None
        self._provenance = self._base_provenance()
        self._out_of_scope_discoveries = []
        self._open_questions = []
        self._draft_sha256 = None
        self._draft_payload = None
        self._critique = []
        self._github_authority_request_payload = None
        self._frozen_result = None
        self.status = FormationStatus.REQUEST_RECEIVED
        self.propose_interpretation(
            understood_objective=understood_objective,
            proposed_task_contract=proposed_task_contract,
            model_inferences=model_inferences,
            out_of_scope_discoveries=out_of_scope_discoveries,
            open_questions=open_questions,
        )
        self.create_draft()
        self.critique()
        return self.present_for_authorization()

    def frozen_result(self) -> dict[str, Any]:
        if (
            self.status is not FormationStatus.AUTHORIZED_AND_FROZEN
            or self._frozen_result is None
        ):
            raise FormationError("no authorized frozen result exists")
        return copy.deepcopy(self._frozen_result)

    def frozen_task_contract(self) -> dict[str, Any]:
        result = self.frozen_result()
        contract = result.get("contract")
        if not isinstance(contract, dict):
            raise FormationError("authorized frozen contract is missing")
        return copy.deepcopy(contract)
