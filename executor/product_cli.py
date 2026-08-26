from __future__ import annotations

import argparse
import dataclasses
import json
import os
import subprocess
from pathlib import Path

from executor.authority_ledger import AtomicAuthorityLedger, AuthorityLedgerError
from executor.draft_pr_effect import DraftPrEffectError, DraftPrEffectExecutor, GitHubDraftPrGateway
from executor.execution_environment import ExecutionEnvironmentError, build_github_actions_environment
from executor.formation_issue_effect import (
    FormationIssueEffectError,
    FormationIssueGateway,
    FormationRequestPublisher,
)
from executor.frozen_pilot_authority import FrozenPilotAuthorityError, validate_frozen_pilot_authority
from executor.github_authority import GlobalAuthorityError, GitHubGlobalAuthority, GovernedAuthorityLedger
from executor.github_trust import (
    GitHubRestClient,
    GitHubTrustError,
    GitHubTrustProfile,
    verify_github_decision,
    verify_github_request,
)
from executor.pilot_contract import (
    PilotContractError,
    apply_github_decision,
    build_pilot_draft_from_formation,
    pilot_draft_sha256,
)
from executor.pilot_runtime import PilotBlocked, PilotRuntime
from executor.product_state import state_from_pilot_status
from executor.request_to_contract import FormationError, RequestToContract001
from executor.strict_json import load_json_object


DEFAULT_PROFILE = "trust_profiles/github-product-gp001.json"
PRODUCT_BASE_BRANCH = "main"


def _json_default(value: object) -> object:
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=_json_default))


def _git_head(root: str) -> str:
    result = subprocess.run(
        ["git", "-C", root, "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    )
    return result.stdout.strip()


def _profile(path: str) -> GitHubTrustProfile:
    return GitHubTrustProfile.from_dict(load_json_object(path))


def _ledger(path: str, profile: GitHubTrustProfile) -> GovernedAuthorityLedger:
    return GovernedAuthorityLedger(
        AtomicAuthorityLedger(path),
        GitHubGlobalAuthority.from_environment(expected_repository=profile.intake_repository),
    )


def _token() -> str:
    token = os.environ.get("EXECUTOR_GITHUB_EFFECT_TOKEN", "")
    if not token:
        raise RuntimeError("EXECUTOR_GITHUB_EFFECT_TOKEN is required for consequential GitHub writes")
    return token


def _publication_inputs(value: dict) -> tuple[dict, int]:
    if value.get("schema_version") != "executor-formation-publication-result/1.1":
        raise FormationError("decide requires executor-formation-publication-result/1.1")
    if value.get("status") != "AWAITING_VERIFIED_HUMAN_DECISION":
        raise FormationError("formation publication is not awaiting human decision")
    canonical = value.get("canonical_contract_request")
    effect = value.get("publication_effect")
    transport = value.get("request_transport_provenance")
    if not isinstance(canonical, dict) or not isinstance(effect, dict) or not isinstance(transport, dict):
        raise FormationError("formation publication lacks canonical request/effect/provenance")
    if transport.get("origin") != "FORMATION_PUBLISHED_REQUEST" or transport.get("authority") is not False:
        raise FormationError("published request transport provenance is invalid")
    object_id = effect.get("object_id")
    if not isinstance(object_id, str) or not object_id.isdecimal() or int(object_id) <= 0:
        raise FormationError("formation publication lacks a durable GitHub issue identity")
    if transport.get("object_id") != object_id:
        raise FormationError("transport provenance does not bind the published issue")
    return canonical, int(object_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="creative-os-product",
        description="Canonical Executor product path; historical proof CLIs are intentionally excluded.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    form = sub.add_parser("form", help="natural request -> validated non-executable formation artifact")
    form.add_argument("--request-id", required=True)
    form.add_argument("--request", required=True)
    form.add_argument("--understood-objective", required=True)
    form.add_argument("--executor-root", default=".")
    form.add_argument("--executor-commit", default=None)
    form.add_argument("--out-of-scope", action="append", default=[])
    form.add_argument("--open-question", action="append", default=[])

    publish = sub.add_parser("publish-authority-request", help="publish the exact formation payload as a zero-authority GitHub transport issue")
    publish.add_argument("--formation", required=True)
    publish.add_argument("--profile", default=DEFAULT_PROFILE)
    publish.add_argument("--ledger", required=True)
    publish.add_argument("--evidence-dir", required=True)

    decide = sub.add_parser("decide", help="publication artifact + verified GitHub ACCEPT/MODIFY/REJECT -> bound result")
    decide.add_argument("--publication", required=True)
    decide.add_argument("--profile", default=DEFAULT_PROFILE)
    decide.add_argument("--comment", required=True, type=int)
    decide.add_argument("--ledger", required=True)

    execute = sub.add_parser("execute", help="exact frozen contract + validated proposal -> bounded pilot execution")
    execute.add_argument("--frozen", required=True)
    execute.add_argument("--proposal", required=True)
    execute.add_argument("--profile", default=DEFAULT_PROFILE)
    execute.add_argument("--ledger", required=True)
    execute.add_argument("--workspace", required=True)
    execute.add_argument("--runs-root", required=True)
    execute.add_argument("--run-id", required=True)
    execute.add_argument("--image", required=True)
    execute.add_argument("--executor-root", default=".")
    execute.add_argument("--executor-commit", default=None)
    execute.add_argument("--docker-binary", default="docker")

    publish_pr = sub.add_parser("publish-draft-pr", help="successful pilot -> commit -> branch -> push -> observed draft PR")
    publish_pr.add_argument("--frozen", required=True)
    publish_pr.add_argument("--pilot-report", required=True)
    publish_pr.add_argument("--profile", default=DEFAULT_PROFILE)
    publish_pr.add_argument("--ledger", required=True)
    publish_pr.add_argument("--evidence-dir", required=True)
    publish_pr.add_argument("--workspace", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "form":
            commit = args.executor_commit or _git_head(args.executor_root)
            formation = RequestToContract001(
                executor_root=Path(args.executor_root),
                executor_commit=commit,
                request_id=args.request_id,
                user_request=args.request,
            )
            formation.propose_canonical_gp001(
                understood_objective=args.understood_objective,
                out_of_scope_discoveries=args.out_of_scope,
                open_questions=args.open_question,
            )
            formation.create_draft()
            formation.critique()
            surface = formation.present_for_authorization()
            if surface["status"] != "AWAITING_VERIFIED_HUMAN_AUTHORIZATION":
                _print(surface)
                return 2
            _print(formation.export_human_authorization_request())
            return 0

        profile = _profile(args.profile)
        governed = _ledger(args.ledger, profile)

        if args.command == "publish-authority-request":
            artifact = load_json_object(args.formation)
            result = FormationRequestPublisher(
                ledger=governed,
                evidence_directory=Path(args.evidence_dir),
            ).publish(
                authorization_request=artifact,
                gateway=FormationIssueGateway(
                    repository=profile.intake_repository,
                    token=_token(),
                ),
            )
            _print(result)
            return 0 if result["status"] == "AWAITING_VERIFIED_HUMAN_DECISION" else 3

        if args.command == "decide":
            publication = load_json_object(args.publication)
            formation, issue_number = _publication_inputs(publication)
            source = GitHubRestClient()
            request = verify_github_request(source, profile=profile, issue_number=issue_number)
            draft = build_pilot_draft_from_formation(
                formation,
                request,
                formation_publication=publication,
            )
            decision = verify_github_decision(
                source,
                profile=profile,
                request=request,
                comment_id=args.comment,
                draft_sha256=pilot_draft_sha256(draft),
            )
            result = apply_github_decision(
                draft=draft,
                decision=decision,
                source=source,
                profile=profile,
                ledger=governed,
                formation_request=formation,
                formation_publication=publication,
            )
            _print(result)
            return 0 if result["status"] in {"AUTHORIZED_AND_FROZEN", "MODIFICATION_REQUIRED", "REJECTED"} else 2

        if args.command == "execute":
            frozen = load_json_object(args.frozen)
            request, decision = validate_frozen_pilot_authority(frozen)
            commit = args.executor_commit or _git_head(args.executor_root)
            environment = build_github_actions_environment(
                image_id=args.image,
                executor_root=args.executor_root,
                executor_commit=commit,
            )
            runtime = PilotRuntime(
                executor_root=args.executor_root,
                executor_commit=commit,
                frozen_result=frozen,
                proposal=load_json_object(args.proposal),
                verified_request=request,
                verified_decision=decision,
                ledger=governed,
                runs_root=args.runs_root,
                image=args.image,
                execution_environment=environment,
                docker_binary=args.docker_binary,
            )
            result = runtime.execute(workspace=args.workspace, run_id=args.run_id)
            result["product_state"] = state_from_pilot_status(result["status"]).to_dict()
            _print(result)
            return 0 if result["status"] == "ACTION_COMPLETED_REVIEW_REQUIRED" else 2

        if args.command == "publish-draft-pr":
            frozen = load_json_object(args.frozen)
            report = load_json_object(args.pilot_report)
            validate_frozen_pilot_authority(frozen)
            contract = frozen.get("contract")
            target = contract.get("target") if isinstance(contract, dict) else None
            if not isinstance(target, dict) or report.get("repository") != target.get("repository"):
                raise DraftPrEffectError("pilot report repository differs from frozen target repository")
            publisher = DraftPrEffectExecutor(
                frozen_result=frozen,
                pilot_report=report,
                ledger=governed,
                evidence_directory=args.evidence_dir,
                base_branch=PRODUCT_BASE_BRANCH,
            )
            gateway = GitHubDraftPrGateway(
                repository=report["repository"],
                workspace=args.workspace,
                token=_token(),
            )
            result = publisher.publish(workspace=args.workspace, gateway=gateway)
            _print(result)
            return 0 if result["status"] == "DRAFT_PR_CREATED_REVIEW_REQUIRED" else 3
    except (
        AuthorityLedgerError,
        DraftPrEffectError,
        ExecutionEnvironmentError,
        FormationError,
        FormationIssueEffectError,
        FrozenPilotAuthorityError,
        GitHubTrustError,
        GlobalAuthorityError,
        PilotBlocked,
        PilotContractError,
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        _print({"status": "BLOCKED", "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
