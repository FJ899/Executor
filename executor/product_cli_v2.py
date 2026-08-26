from __future__ import annotations

import argparse
from pathlib import Path

from executor.authority_ledger import AuthorityLedgerError
from executor.draft_pr_effect import DraftPrEffectError, DraftPrEffectExecutor, GitHubDraftPrGateway
from executor.execution_environment import ExecutionEnvironmentError, build_github_actions_environment
from executor.formation_issue_effect import FormationIssueEffectError, FormationIssueGateway, FormationRequestPublisher
from executor.frozen_pilot_authority import FrozenPilotAuthorityError
from executor.github_authority import GlobalAuthorityError
from executor.github_trust import GitHubRestClient, GitHubTrustError
from executor.pilot_contract import PilotContractError, build_pilot_draft_from_formation, pilot_draft_sha256
from executor.pilot_runtime import PilotBlocked, PilotRuntime
from executor.product_cli import (
    DEFAULT_PROFILE,
    PRODUCT_BASE_BRANCH,
    _git_head,
    _ledger,
    _print,
    _profile,
    _publication_inputs,
    _token,
)
from executor.product_frozen_authority import validate_product_frozen_pilot_authority
from executor.product_github_authority import (
    apply_product_github_decision,
    verify_formation_published_request,
    verify_product_github_decision,
)
from executor.product_state import state_from_pilot_status
from executor.request_to_contract import FormationError, RequestToContract001
from executor.strict_json import load_json_object


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="creative-os-product",
        description="Canonical Executor product path; system request transport, Human decision authority.",
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

    publish = sub.add_parser(
        "publish-authority-request",
        help="publish the exact formation payload as a zero-authority GitHub transport issue",
    )
    publish.add_argument("--formation", required=True)
    publish.add_argument("--profile", default=DEFAULT_PROFILE)
    publish.add_argument("--ledger", required=True)
    publish.add_argument("--evidence-dir", required=True)

    decide = sub.add_parser(
        "decide",
        help="publication artifact + verified GitHub ACCEPT/MODIFY/REJECT -> bound result",
    )
    decide.add_argument("--publication", required=True)
    decide.add_argument("--profile", default=DEFAULT_PROFILE)
    decide.add_argument("--comment", required=True, type=int)
    decide.add_argument("--ledger", required=True)

    execute = sub.add_parser(
        "execute",
        help="exact frozen contract + validated proposal -> bounded pilot execution",
    )
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

    publish_pr = sub.add_parser(
        "publish-draft-pr",
        help="successful pilot -> commit -> branch -> push -> observed draft PR",
    )
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
            payload = formation.get("github_request_payload")
            if not isinstance(payload, dict):
                raise FormationError("canonical formation request lacks GitHub payload")
            source = GitHubRestClient()
            request = verify_formation_published_request(
                source,
                profile=profile,
                issue_number=issue_number,
                expected_payload=payload,
            )
            draft = build_pilot_draft_from_formation(
                formation,
                request,
                formation_publication=publication,
            )
            draft_sha = pilot_draft_sha256(draft)
            decision = verify_product_github_decision(
                source,
                profile=profile,
                request=request,
                comment_id=args.comment,
                draft_sha256=draft_sha,
            )
            result = apply_product_github_decision(
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
            request, decision = validate_product_frozen_pilot_authority(frozen)
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
            validate_product_frozen_pilot_authority(frozen)
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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
