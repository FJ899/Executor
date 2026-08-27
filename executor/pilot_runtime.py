from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from executor.action_authorization import (
    AuthorizationContext,
    packet_payload_sha256,
    validate_action_authorization_packet,
)
from executor.authority_ledger import AuthorityLedgerError
from executor.contracts import ValidationStatus
from executor.execution_environment import (
    ExecutionEnvironmentError,
    validate_execution_environment,
)
from executor.github_authority import (
    GlobalAuthorityError,
    GlobalAuthorityExpiredError,
    GovernedAuthorityConsumption,
    GovernedAuthorityLedger,
)
from executor.github_trust import VerifiedGitHubDecision, VerifiedGitHubRequest, canonical_json
from executor.repository_access import canonical_repository_path, validate_scope_pattern
from executor.repository_identity import RepositoryIdentityError, repository_identity_from_remote
from executor.repository_snapshot import RepositorySnapshotError, verify_source_tree
from executor.sandbox.docker import (
    DockerSandboxBackend,
    SandboxExecutionError,
    SandboxUnavailable,
)
from executor.sandbox.policy_snapshot import (
    ExecutionPolicyError,
    ExecutionPolicySnapshot,
    load_execution_policy_snapshot,
)
from executor.sandbox.spec import (
    CommandRule,
    SandboxExecutionContext,
    SandboxResult,
    SandboxSpec,
)
from executor.solution_provider import (
    SolutionGenerationVerifier,
    SolutionProviderError,
    validate_authoritative_solution_proposal,
)
from executor.solution_proposal import (
    ProposedMutation,
    ValidatedSolutionProposal,
)


class PilotRuntimeError(RuntimeError):
    pass


class PilotBlocked(PilotRuntimeError):
    pass


_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_UNITTEST_COUNT = re.compile(r"\bRan\s+(\d+)\s+tests?\b")


def _utc_now() -> datetime:
    """Return the real UTC clock at the exact authority-consumption boundary."""
    return datetime.now(timezone.utc)


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise PilotRuntimeError(f"git {' '.join(args)} failed: {detail}")
    return result


def _changed_paths(root: Path) -> tuple[str, ...]:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        ],
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode:
        raise PilotRuntimeError("cannot inspect pilot working tree")
    records = result.stdout.split(b"\0")
    paths: set[str] = set()
    index = 0
    while index < len(records):
        record = records[index]
        if not record:
            index += 1
            continue
        if len(record) < 4:
            raise PilotRuntimeError(f"unexpected Git status record: {record!r}")
        status = record[:2]
        path = record[3:]
        if b"R" in status or b"C" in status:
            index += 1
            if index >= len(records) or not records[index]:
                raise PilotRuntimeError("incomplete Git rename/copy status")
            path = records[index]
        try:
            decoded = path.decode("utf-8")
        except UnicodeError as exc:
            raise PilotRuntimeError("pilot path is not UTF-8") from exc
        paths.add(canonical_repository_path(decoded))
        index += 1
    return tuple(sorted(paths))


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_pilot_checkout(
    root_value: str | Path,
    *,
    repository: str,
    source_tree: str,
) -> Path:
    root_input = Path(root_value)
    if root_input.is_symlink():
        raise RepositoryIdentityError("pilot repository root cannot be a symlink")
    root = root_input.resolve(strict=True)
    if not root.is_dir():
        raise RepositoryIdentityError("pilot repository root must be a directory")
    remote = _git(root, "remote", "get-url", "origin").stdout
    identity = repository_identity_from_remote(remote)
    if identity is None or identity[0] != "github.com" or identity[1].lower() != repository.lower():
        raise RepositoryIdentityError(f"pilot repository origin mismatch: {identity!r}")
    actual_tree = _git(root, "rev-parse", "HEAD^{tree}").stdout.strip()
    if actual_tree != source_tree:
        raise RepositoryIdentityError(
            f"pilot source tree is {actual_tree}, expected {source_tree}"
        )
    return root


def _result_payload(result: SandboxResult) -> dict[str, Any]:
    return {
        "argv": list(result.argv),
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timed_out": result.timed_out,
        "cleanup_verified": result.cleanup_verified,
        "execution_id": result.execution_id,
        "policy_sha256": result.policy_sha256,
    }


def _assert_nonempty_regression(argv: list[str], result: SandboxResult) -> None:
    if "unittest" not in argv or "discover" not in argv:
        return
    text = f"{result.stdout}\n{result.stderr}"
    match = _UNITTEST_COUNT.search(text)
    if match is None:
        raise PilotBlocked("unittest discovery produced no countable test evidence")
    if int(match.group(1)) == 0:
        raise PilotBlocked("unittest discovery ran zero tests")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def build_pilot_sandbox_spec(contract: dict[str, Any], image: str) -> SandboxSpec:
    task = contract["task"]
    commands = [
        *task["precondition_argv"],
        *task["postcondition_argv"],
        *task["regression_argv"],
    ]
    return SandboxSpec(
        image=image,
        command_rules=tuple(
            CommandRule(command[0], tuple(command[1:])) for command in commands
        ),
        timeout_seconds=300,
        max_cpu=1.0,
        max_memory_mb=512,
        max_disk_mb=64,
        pids_limit=128,
        network=False,
        secrets=(),
        home_access=False,
        labels={"creative-os-executor-pilot": "p4-bounded-real-pilot"},
    )


class PilotDockerSandboxBackend(DockerSandboxBackend):
    def __init__(
        self,
        *,
        policy_snapshot: ExecutionPolicySnapshot,
        contract: dict[str, Any],
        docker_binary: str = "docker",
    ) -> None:
        super().__init__(policy_snapshot=policy_snapshot, docker_binary=docker_binary)
        self.repository = contract["target"]["repository"]
        self.commit = contract["target"]["commit"]
        self.source_tree = contract["target"]["tree"]
        self.allowed = tuple(
            canonical_repository_path(path)
            for path in contract["task"]["allowed_paths"]
        )
        self.protected = tuple(
            validate_scope_pattern(path)
            for path in contract["task"]["protected_paths"]
        )
        profile = policy_snapshot.bounded_pilot_profile(repository=self.repository)
        if profile is None:
            raise SandboxExecutionError("repository is outside the bounded pilot policy")
        if len(self.allowed) > profile.max_production_files:
            raise SandboxExecutionError("pilot contract exceeds policy file limit")
        if not profile.draft_pr_only or policy_snapshot.auto_merge:
            raise SandboxExecutionError("pilot policy must remain draft-PR only")

    def authorize(self, context: SandboxExecutionContext) -> Path:
        policy = self._authoritative_policy()
        profile = policy.bounded_pilot_profile(repository=self.repository)
        if (
            profile is None
            or policy.external_projects
            or policy.auto_merge
            or policy.default_network
            or policy.default_secrets
        ):
            raise SandboxExecutionError("bounded pilot authority is absent or widened")
        if context.purpose not in {"PILOT_PRECHANGE", "PILOT_POSTCHANGE"}:
            raise SandboxExecutionError("unsupported bounded pilot purpose")
        if context.repository != self.repository or context.commit != self.commit:
            raise SandboxExecutionError("bounded pilot repository binding mismatch")
        try:
            root = _verify_pilot_checkout(
                context.repository_root,
                repository=self.repository,
                source_tree=self.source_tree,
            )
        except RepositoryIdentityError as exc:
            raise SandboxExecutionError(f"unverified pilot checkout: {exc}") from exc
        if Path(context.source_dir).resolve(strict=True) != root:
            raise SandboxExecutionError("pilot source must be the verified checkout root")
        changed = _changed_paths(root)
        if context.purpose == "PILOT_PRECHANGE":
            if changed:
                raise SandboxExecutionError(f"pilot checkout is dirty: {list(changed)}")
            try:
                head = _git(root, "rev-parse", "HEAD").stdout.strip()
                verify_source_tree(root, commit=head, source_dir=root)
            except RepositorySnapshotError as exc:
                raise SandboxExecutionError(f"pilot source mismatch: {exc}") from exc
        else:
            if changed != tuple(sorted(item.path for item in self._proposal.mutations)):
                raise SandboxExecutionError("pilot post-change scope mismatch")
            if any(fnmatch(path, pattern) for path in changed for pattern in self.protected):
                raise SandboxExecutionError("protected pilot material changed")
        return root

    def bind_proposal(self, proposal: ValidatedSolutionProposal) -> None:
        self._proposal = proposal

    def build_create_command(self, **kwargs: Any) -> list[str]:
        command = super().build_create_command(**kwargs)
        spec = kwargs["spec"]
        command[command.index("--workdir") + 1] = spec.source_mount
        image_index = command.index(spec.image)
        command[image_index:image_index] = [
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--env",
            f"PYTHONPYCACHEPREFIX={spec.workspace_mount}/pycache",
        ]
        return command


class PilotRuntime:
    """Execute one exact externally proposed fix under globally one-shot GitHub authority."""

    def __init__(
        self,
        *,
        executor_root: str | Path,
        executor_commit: str,
        frozen_result: dict[str, Any],
        proposal: dict[str, Any],
        verified_request: VerifiedGitHubRequest,
        verified_decision: VerifiedGitHubDecision,
        ledger: GovernedAuthorityLedger,
        runs_root: str | Path,
        image: str,
        execution_environment: dict[str, Any],
        generation_verifier: SolutionGenerationVerifier | None = None,
        docker_binary: str = "docker",
    ) -> None:
        if frozen_result.get("status") != "AUTHORIZED_AND_FROZEN":
            raise PilotBlocked("pilot runtime requires an authorized frozen contract")
        contract = frozen_result.get("contract")
        if not isinstance(contract, dict):
            raise PilotBlocked("frozen pilot contract is missing")
        request_evidence = contract.get("request_evidence", {})
        decision_evidence = contract.get("decision_evidence", {})
        if request_evidence.get("evidence_ref") != verified_request.evidence_ref:
            raise PilotBlocked("current GitHub request evidence differs from frozen evidence")
        if decision_evidence.get("evidence_ref") != verified_decision.evidence_ref:
            raise PilotBlocked("current GitHub decision evidence differs from frozen evidence")
        if verified_decision.decision != "ACCEPT":
            raise PilotBlocked("only an exact current GitHub ACCEPT can execute")
        if generation_verifier is not None:
            raise PilotBlocked(
                "solution generation evidence is not authoritative: "
                "caller-supplied solution-generation verifier is forbidden at the runtime trust boundary"
            )
        if generation_verifier is None:
            raise PilotBlocked(
                "pilot runtime requires independent solution-generation evidence verification; "
                "trusted provider-backed runtime verifier is not installed in Stage 2"
            )
        try:
            authoritative = validate_authoritative_solution_proposal(
                proposal,
                frozen_result=frozen_result,
                generation_verifier=generation_verifier,
            )
        except SolutionProviderError as exc:
            raise PilotBlocked(f"solution generation evidence is not authoritative: {exc}") from exc
        validated = authoritative.proposal
        try:
            policy = load_execution_policy_snapshot(executor_root, commit=executor_commit)
        except ExecutionPolicyError as exc:
            raise PilotBlocked(f"cannot load authoritative pilot policy: {exc}") from exc
        profile = policy.bounded_pilot_profile(
            repository=contract["target"]["repository"]
        )
        if (
            profile is None
            or policy.external_projects
            or policy.auto_merge
            or policy.default_network
            or policy.default_secrets
        ):
            raise PilotBlocked("Executor policy does not authorize this bounded pilot")
        if len(validated.mutations) > profile.max_production_files:
            raise PilotBlocked("proposal exceeds the policy production-file limit")
        try:
            environment = validate_execution_environment(
                execution_environment,
                executor_commit=executor_commit,
                image_id=image,
            )
        except ExecutionEnvironmentError as exc:
            raise PilotBlocked(f"execution environment is not authoritative: {exc}") from exc
        backend = PilotDockerSandboxBackend(
            policy_snapshot=policy,
            contract=contract,
            docker_binary=docker_binary,
        )
        backend.bind_proposal(validated)
        self.executor_commit = executor_commit
        self.policy_snapshot = policy
        self.contract = contract
        self.contract_sha256 = frozen_result["contract_sha256"]
        self.proposal = validated
        self.solution_generation_evidence = authoritative.generation_evidence
        self.solution_freeze_receipt_sha256 = authoritative.freeze_receipt_sha256
        self.verified_request = verified_request
        self.verified_decision = verified_decision
        self.ledger = ledger
        self.runs_root = Path(runs_root)
        self.backend = backend
        self.spec = build_pilot_sandbox_spec(contract, image)
        self.execution_environment = environment
        self.execution_environment_sha256 = hashlib.sha256(
            canonical_json(environment).encode("utf-8")
        ).hexdigest()

    def _run(
        self,
        root: Path,
        run_dir: Path,
        argv: list[str],
        *,
        before_change: bool,
        label: str,
    ) -> SandboxResult:
        return self.backend.run(
            spec=self.spec,
            context=SandboxExecutionContext(
                repository=self.proposal.repository,
                commit=self.proposal.source_commit,
                repository_root=root,
                source_dir=root,
                purpose="PILOT_PRECHANGE" if before_change else "PILOT_POSTCHANGE",
            ),
            output_dir=run_dir / label,
            argv=argv,
        )

    def _authorize_action(
        self,
        *,
        run_id: str,
    ) -> tuple[dict[str, Any], GovernedAuthorityConsumption]:
        # Freshness is evaluated immediately before provider reservation.
        # Caller-supplied or precondition-time clocks cannot authorize an effect.
        now = _utc_now().astimezone(timezone.utc)
        task = self.contract["task"]
        target = self.contract["target"]
        test_contract_sha = hashlib.sha256(
            canonical_json(
                {
                    "precondition_argv": task["precondition_argv"],
                    "postcondition_argv": task["postcondition_argv"],
                    "regression_argv": task["regression_argv"],
                }
            ).encode("utf-8")
        ).hexdigest()
        context = AuthorizationContext(
            run_id=run_id,
            task_id=self.contract["request_id"],
            risk_class="HIGH_RISK",
            mode="BUILD_AND_TEST",
            executor_commit=self.executor_commit,
            policy_sha256=self.policy_snapshot.source_sha256,
            project_contract_sha256=self.verified_request.body_sha256,
            task_contract_sha256=self.contract_sha256,
            test_contract_sha256=test_contract_sha,
            repository_commits={target["repository"]: target["commit"]},
            allowed_paths=tuple(task["allowed_paths"]),
            external_projects=False,
            auto_merge=False,
            default_network=False,
            default_secrets=(),
            verified_issuer_evidence={
                self.verified_decision.evidence_ref: (
                    "USER",
                    self.verified_decision.actor_login,
                )
            },
            bounded_external_repositories=tuple(
                item.repository
                for item in self.policy_snapshot.bounded_pilot_repositories
            ),
        )
        decision_expiry = datetime.fromisoformat(
            self.verified_decision.expires_at[:-1] + "+00:00"
        )
        expires = min(now + timedelta(minutes=10), decision_expiry)
        if expires <= now:
            raise PilotBlocked("GitHub ACCEPT expired before effect authorization")

        # One human decision can create exactly one effect key. Operator-controlled run_id
        # and proposal variation cannot mint a second authority namespace.
        effect_identity = canonical_json(
            {
                "decision_evidence_ref": self.verified_decision.evidence_ref,
                "contract_sha256": self.contract_sha256,
            }
        )
        packet_id = "pilot-" + hashlib.sha256(effect_identity.encode("utf-8")).hexdigest()[:48]
        packet = {
            "schema_version": "executor-action-authorization/1.0",
            "packet_id": packet_id,
            "run_id": run_id,
            "issued_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": expires.isoformat().replace("+00:00", "Z"),
            "issuer": {
                "role": "USER",
                "id": self.verified_decision.actor_login,
                "evidence_ref": self.verified_decision.evidence_ref,
            },
            "bindings": {
                "task_id": context.task_id,
                "risk_class": context.risk_class,
                "mode": context.mode,
                "executor_commit": context.executor_commit,
                "policy_sha256": context.policy_sha256,
                "project_contract_sha256": context.project_contract_sha256,
                "task_contract_sha256": context.task_contract_sha256,
                "test_contract_sha256": context.test_contract_sha256,
                "repository_commits": context.repository_commits,
            },
            "action": {
                "kind": "EXTERNAL_PROJECT_EXECUTION",
                "argv": [
                    "APPLY_SOLUTION_PROPOSAL",
                    self.proposal.proposal_id,
                    self.proposal.payload_sha256,
                    "EXECUTION_ENVIRONMENT_SHA256",
                    self.execution_environment_sha256,
                    "SOLUTION_PROVENANCE_SHA256",
                    self.proposal.provenance_sha256,
                ],
                "paths": [item.path for item in self.proposal.mutations],
                "network": False,
                "secrets": [],
                "external_project": True,
            },
            "decision": {
                "status": "AUTHORIZED",
                "reasons": [
                    "exact fresh GitHub ACCEPT binds the current frozen contract",
                    "repository and write scope match the bounded P4 pilot policy",
                    "global GitHub authority receipt enforces one effect per human decision",
                    "exact workflow, image and proposal provenance are integrity-bound",
                    "merge, deploy and release remain forbidden",
                ],
            },
            "constraints": {
                "max_uses": 1,
                "max_duration_seconds": 600,
                "manual_confirmation_required": False,
            },
            "integrity": {"algorithm": "SHA-256", "payload_sha256": ""},
        }
        packet["integrity"]["payload_sha256"] = packet_payload_sha256(packet)
        result, decision = validate_action_authorization_packet(
            packet,
            context=context,
            now=now,
        )
        if result.status != ValidationStatus.VALID or decision is None:
            raise PilotBlocked(f"pilot AAP rejected: {result.to_dict()}")
        try:
            consumption = self.ledger.consume(
                authority_key=f"aap:{decision.packet_id}",
                payload_sha256=decision.payload_sha256,
                action_kind=decision.action_kind,
                run_id=run_id,
                now=now,
                not_after=self.verified_decision.expires_at,
            )
        except GlobalAuthorityExpiredError as exc:
            raise PilotBlocked(str(exc)) from exc
        return packet, consumption

    def _apply_mutations(self, root: Path) -> None:
        prepared: list[tuple[Path, Path, ProposedMutation, int]] = []
        for mutation in self.proposal.mutations:
            path = root / mutation.path
            meta = path.lstat()
            if path.is_symlink() or not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
                raise PilotBlocked("pilot mutation target must be a regular non-linked file")
            if _file_sha256(path) != mutation.expected_before_sha256:
                raise PilotBlocked(f"pilot before hash mismatch: {mutation.path}")
            temporary = path.with_name(f".{path.name}.pilot-{uuid.uuid4().hex}")
            temporary.write_text(mutation.replacement_text, encoding="utf-8")
            os.chmod(temporary, stat.S_IMODE(meta.st_mode))
            if _file_sha256(temporary) != mutation.expected_after_sha256:
                temporary.unlink(missing_ok=True)
                raise PilotBlocked(f"pilot after hash mismatch: {mutation.path}")
            prepared.append((path, temporary, mutation, stat.S_IMODE(meta.st_mode)))
        try:
            for path, temporary, _, _ in prepared:
                os.replace(temporary, path)
        finally:
            for _, temporary, _, _ in prepared:
                temporary.unlink(missing_ok=True)

    def execute(
        self,
        *,
        workspace: str | Path,
        run_id: str,
    ) -> dict[str, Any]:
        if _RUN_ID.fullmatch(run_id) is None:
            raise PilotBlocked("run_id is invalid")
        run_dir = self.runs_root / run_id
        consumption: GovernedAuthorityConsumption | None = None
        report: dict[str, Any] = {
            "schema_version": "executor-p4-pilot-result/1.0",
            "run_id": run_id,
            "repository": self.proposal.repository,
            "source_commit": self.proposal.source_commit,
            "source_tree": self.proposal.source_tree,
            "contract_sha256": self.contract_sha256,
            "proposal_sha256": self.proposal.payload_sha256,
            "solution_provenance": self.proposal.provenance,
            "solution_provenance_sha256": self.proposal.provenance_sha256,
            "execution_environment": self.execution_environment,
            "execution_environment_sha256": self.execution_environment_sha256,
            "status": "FAILED",
            "error": None,
            "changed_paths": [],
            "commands": [],
            "evidence": {
                "github_request": "CURRENT",
                "github_decision": "CURRENT_ACCEPT",
                "input_identity": "UNKNOWN",
                "precondition": "UNKNOWN",
                "postcondition": "UNKNOWN",
                "regressions": "UNKNOWN",
                "scope": "UNKNOWN",
                "isolation": "UNKNOWN",
                "authority": "UNKNOWN",
                "execution_environment": "BOUND",
                "solution_provenance": "BOUND",
            },
            "human_review_required": True,
            "merge_allowed": False,
        }
        started = time.monotonic()
        try:
            root = _verify_pilot_checkout(
                workspace,
                repository=self.proposal.repository,
                source_tree=self.proposal.source_tree,
            )
            if _changed_paths(root):
                raise PilotBlocked("pilot workspace must start clean")
            report["evidence"]["input_identity"] = "MATCH"
            self.runs_root.mkdir(parents=True, exist_ok=True)
            run_dir.mkdir(mode=0o700)

            for index, command in enumerate(self.contract["task"]["precondition_argv"], 1):
                result = self._run(
                    root,
                    run_dir,
                    command,
                    before_change=True,
                    label=f"precondition-{index}",
                )
                report["commands"].append(_result_payload(result))
                if result.timed_out or not result.cleanup_verified:
                    raise PilotRuntimeError("precondition evidence is not trustworthy")
                if result.exit_code == 0:
                    raise PilotBlocked("approved counterexample is not observable")
            report["evidence"]["precondition"] = "OBSERVED_FAILURE"

            packet, consumption = self._authorize_action(run_id=run_id)
            report["authorization_packet"] = packet
            report["evidence"]["authority"] = "GLOBAL_GITHUB_RESERVED_AND_LOCAL_ATOMIC_CONSUMED"
            self._apply_mutations(root)

            for index, command in enumerate(self.contract["task"]["postcondition_argv"], 1):
                result = self._run(
                    root,
                    run_dir,
                    command,
                    before_change=False,
                    label=f"postcondition-{index}",
                )
                report["commands"].append(_result_payload(result))
                if not result.ok:
                    raise PilotRuntimeError("pilot postcondition failed")
            report["evidence"]["postcondition"] = "PASS"

            for index, command in enumerate(self.contract["task"]["regression_argv"], 1):
                result = self._run(
                    root,
                    run_dir,
                    command,
                    before_change=False,
                    label=f"regression-{index}",
                )
                report["commands"].append(_result_payload(result))
                if not result.ok:
                    raise PilotRuntimeError(f"pilot regression {index} failed")
                _assert_nonempty_regression(command, result)
            report["evidence"]["regressions"] = "PASS"

            changed = _changed_paths(root)
            expected = tuple(sorted(item.path for item in self.proposal.mutations))
            if changed != expected:
                raise PilotRuntimeError(
                    f"pilot diff scope mismatch: expected={expected}, actual={changed}"
                )
            report["changed_paths"] = list(changed)
            report["evidence"]["scope"] = "ALLOWED"
            report["evidence"]["isolation"] = "NO_NETWORK_NO_SECRETS_CLEANUP_VERIFIED"
            patch = _git(
                root,
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                "--binary",
                self.proposal.source_commit,
            ).stdout
            if len(patch.splitlines()) > self.contract["task"]["max_patch_lines"]:
                raise PilotBlocked("pilot patch exceeds the frozen line budget")
            patch_path = run_dir / "change.patch"
            patch_path.write_text(patch, encoding="utf-8")
            report["patch"] = {
                "path": str(patch_path),
                "sha256": hashlib.sha256(patch.encode("utf-8")).hexdigest(),
            }
            report["status"] = "ACTION_COMPLETED_REVIEW_REQUIRED"
        except PilotBlocked as exc:
            report["status"], report["error"] = "BLOCKED", str(exc)
        except (
            PilotRuntimeError,
            SandboxExecutionError,
            SandboxUnavailable,
            RepositoryIdentityError,
            AuthorityLedgerError,
            GlobalAuthorityError,
            ExecutionEnvironmentError,
            OSError,
            ValueError,
        ) as exc:
            report["status"], report["error"] = "FAILED", str(exc)

        report["duration_seconds"] = round(time.monotonic() - started, 6)
        terminal = {
            key: report[key]
            for key in (
                "schema_version",
                "run_id",
                "repository",
                "source_commit",
                "source_tree",
                "contract_sha256",
                "proposal_sha256",
                "solution_provenance_sha256",
                "execution_environment",
                "execution_environment_sha256",
                "status",
                "error",
                "changed_paths",
                "evidence",
                "human_review_required",
                "merge_allowed",
            )
        }
        if "patch" in report:
            terminal["patch_sha256"] = report["patch"]["sha256"]
        if consumption is not None:
            try:
                report["authority_consumption"] = self.ledger.bind_result(
                    consumption=consumption,
                    result=terminal,
                )
            except (AuthorityLedgerError, GlobalAuthorityError) as exc:
                report["status"] = "FAILED"
                report["error"] = f"authority result binding failed: {exc}"
                report["evidence"]["authority"] = "RESULT_BINDING_FAILED"
                terminal["status"] = "FAILED"
                terminal["error"] = report["error"]
                terminal["evidence"] = report["evidence"]
        report["terminal_result"] = terminal
        if report["status"] == "ACTION_COMPLETED_REVIEW_REQUIRED":
            global_receipt = report["authority_consumption"]["global"]
            report["draft_pr_request"] = {
                "schema_version": "executor-draft-pr-request/1.0",
                "repository": self.proposal.repository,
                "base_commit": self.proposal.source_commit,
                "source_tree": self.proposal.source_tree,
                "head_branch": f"executor-pilot/{run_id}",
                "title": f"[Executor pilot] {self.contract['task']['problem_statement']}",
                "body_evidence": {
                    "contract_sha256": self.contract_sha256,
                    "proposal_sha256": self.proposal.payload_sha256,
                    "solution_provenance_sha256": self.proposal.provenance_sha256,
                    "patch_sha256": report["patch"]["sha256"],
                    "authority_result_sha256": report["authority_consumption"]["result_sha256"],
                    "global_authority_ref": global_receipt["ref"],
                    "global_authority_final_sha": global_receipt["final_sha"],
                    "workflow_sha256": self.execution_environment["workflow_sha256"],
                    "sandbox_image_id": self.execution_environment["sandbox_image_id"],
                },
                "draft": True,
                "merge_allowed": False,
            }
        if run_dir.exists():
            report_path = run_dir / "report.json"
            report["report_path"] = str(report_path)
            _write_json(report_path, report)
        return report
