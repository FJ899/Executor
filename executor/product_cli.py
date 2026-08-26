from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from executor.authority_ledger import AtomicAuthorityLedger, AuthorityLedgerError
from executor.draft_pr_effect import DraftPrEffectError, DraftPrEffectExecutor, GitHubDraftPrGateway
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
from executor.request_to_contract import FormationError, RequestToContract001
from executor.strict_json import load_json_object


DEFAULT_PROFILE = "trust_profiles/github-product-gp001.json"
PRODUCT_BASE_BRANCH = "main"


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


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
    token = os.environ.get("EXECUTOR_GITHUB_EFFECT_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        raise RuntimeError("EXECUTOR_GITHUB_EFFECT_TOKEN or GITHUB_TOKEN is required for provider writes")
    return token


def _formation_request_from_artifact(value: dict) -> dict:
    canonical = value.get("canonical_contract_request")
    if not isinstance(canonical, dict):
        raise FormationError("formation artifact lacks canonical_contract_request")
    return canonical


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

    publish = sub.add_parser("publish-authority-request", help="publish the exact formation payload as a GitHub authority issue")
    publish.add_argument("--formation", required=True)
    publish.add_argument("--profile", default=DEFAULT_PROFILE)
    publish.add_argument("--ledger", required=True)
    publish.add_argument("--evidence-dir", required=True)

    decide = sub.add_parser("decide", help="verified GitHub ACCEPT/MODIFY/REJECT -> bound result")
    decide.add_argument("--formation", required=True)
    decide.add_argument("--profile", default=DEFAULT_PROFILE)
    decide.add_argument("--issue", required=True, type=int)
    decide.add_argument("--comment", required=True, type=int)
    decide.add_argument("--ledger", required=True)

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
            formation = _formation_request_from_artifact(load_json_object(args.formation))
            source = GitHubRestClient()
            request = verify_github_request(source, profile=profile, issue_number=args.issue)
            draft = build_pilot_draft_from_formation(formation, request)
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
            )
            _print(result)
            return 0 if result["status"] in {"AUTHORIZED_AND_FROZEN", "MODIFICATION_REQUIRED", "REJECTED"} else 2

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
        FormationError,
        FormationIssueEffectError,
        FrozenPilotAuthorityError,
        GitHubTrustError,
        GlobalAuthorityError,
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
