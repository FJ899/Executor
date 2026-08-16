from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from executor.checkpoints import build_snapshot
from executor.contracts import validate_test_contract
from executor.governance import validate_project_bundle, validate_task_bundle
from executor.policy import PolicyEngine
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
    build_pilot_draft,
    pilot_draft_sha256,
)
from executor.pilot_runtime import PilotBlocked, PilotRuntime
from executor.solution_proposal import (
    SolutionProposalError,
    materialize_solution_candidate,
)
from executor.repository_reader import read_wrapped_repository_file
from executor.repository_roots import parse_repository_roots
from executor.request_to_contract import FormationError, RequestToContract001
from executor.authority_ledger import AuthorityLedgerError, AtomicAuthorityLedger
from executor.state_machine import InvalidTransition, RunIntegrityError, RunState, RunStore
from executor.strict_json import load_json_object


def _print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _snapshot_from_args(args: argparse.Namespace):
    return build_snapshot(
        executor_version=args.executor_version,
        policy=load_json_object(args.policy),
        project_contract=load_json_object(args.project),
        task_contract=load_json_object(args.task),
        test_contract=load_json_object(args.test_contract),
        prompt_bundle={"version": args.prompt_version},
        model_id=args.model_id,
        repository_shas={"target": args.repository_sha},
        inputs={"input": args.input},
        workspace=args.workspace,
    )


def _add_snapshot_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--policy", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--test-contract", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--repository-sha", required=True)
    parser.add_argument("--executor-version", default="0.2.0")
    parser.add_argument("--prompt-version", default="none")
    parser.add_argument("--model-id", default="none")


def _add_governance_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--policy", required=True)
    parser.add_argument("--base-dir", default=".")


def _git_head(root: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", root, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise FormationError(f"cannot resolve Executor commit: {exc}") from exc
    return result.stdout.strip()


def _github_profile(path: str) -> GitHubTrustProfile:
    return GitHubTrustProfile.from_dict(load_json_object(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="creative-os-executor")
    sub = parser.add_subparsers(dest="command", required=True)

    p_project = sub.add_parser("validate-project")
    p_project.add_argument("path")
    _add_governance_args(p_project)

    p_test = sub.add_parser("validate-test")
    p_test.add_argument("path")
    p_test.add_argument("--base-dir", default=None)
    p_test.add_argument("--holdout-evidence", default=None)

    p_task = sub.add_parser("validate-task")
    p_task.add_argument("path")
    _add_governance_args(p_task)
    p_task.add_argument("--repository-root", action="append", default=[])

    p_policy = sub.add_parser("policy-check")
    p_policy.add_argument("project")
    _add_governance_args(p_policy)
    p_policy.add_argument("--path")
    p_policy.add_argument("--allowed", action="append", default=[])
    p_policy.add_argument("--repository-root", default=None)
    p_policy.add_argument("--network", action="store_true")
    p_policy.add_argument("--secret", action="append", default=[])
    p_policy.add_argument("--command-line", default=None)
    p_policy.add_argument("--public-api-change", action="store_true")
    p_policy.add_argument("--data-schema-change", action="store_true")
    p_policy.add_argument("--result-semantics-change", action="store_true")

    p_read = sub.add_parser("repository-read")
    p_read.add_argument("--project", required=True)
    _add_governance_args(p_read)
    p_read.add_argument("--repository", required=True)
    p_read.add_argument("--commit", required=True)
    p_read.add_argument("--root", required=True)
    p_read.add_argument("--path", required=True)

    p_form = sub.add_parser(
        "form-gp001-request",
        help="form a non-executable canonical GP001 authorization request",
    )
    p_form.add_argument("--request-id", required=True)
    p_form.add_argument("--request", required=True)
    p_form.add_argument("--understood-objective", required=True)
    p_form.add_argument("--executor-root", default=".")
    p_form.add_argument("--executor-commit", default=None)
    p_form.add_argument("--out-of-scope", action="append", default=[])
    p_form.add_argument("--open-question", action="append", default=[])

    p_pilot_draft = sub.add_parser(
        "github-pilot-draft",
        help="verify a governed GitHub request and emit its exact non-executable draft",
    )
    p_pilot_draft.add_argument("--profile", required=True)
    p_pilot_draft.add_argument("--issue", required=True, type=int)

    p_pilot_decide = sub.add_parser(
        "github-pilot-decide",
        help="consume a fresh exact GitHub decision and freeze or stop the pilot",
    )
    p_pilot_decide.add_argument("--profile", required=True)
    p_pilot_decide.add_argument("--issue", required=True, type=int)
    p_pilot_decide.add_argument("--comment", required=True, type=int)
    p_pilot_decide.add_argument("--ledger", required=True)

    p_pilot_run = sub.add_parser(
        "run-pilot",
        help="run one frozen externally proposed bounded pilot",
    )
    p_pilot_run.add_argument("--profile", required=True)
    p_pilot_run.add_argument("--issue", required=True, type=int)
    p_pilot_run.add_argument("--comment", required=True, type=int)
    p_pilot_run.add_argument("--frozen", required=True)
    p_pilot_run.add_argument("--proposal", required=True)
    p_pilot_run.add_argument("--ledger", required=True)
    p_pilot_run.add_argument("--workspace", required=True)
    p_pilot_run.add_argument("--runs-root", required=True)
    p_pilot_run.add_argument("--run-id", required=True)
    p_pilot_run.add_argument("--image", required=True)
    p_pilot_run.add_argument("--executor-root", default=".")
    p_pilot_run.add_argument("--executor-commit", default=None)
    p_pilot_run.add_argument("--docker-binary", default="docker")

    p_materialize = sub.add_parser(
        "materialize-pilot-proposal",
        help="bind an external solution candidate to one exact frozen contract",
    )
    p_materialize.add_argument("--candidate", required=True)
    p_materialize.add_argument("--frozen", required=True)

    p_create = sub.add_parser("run-create")
    p_create.add_argument("--runs-root", default="runs")
    p_create.add_argument("--run-id", default=None)
    _add_snapshot_args(p_create)

    p_transition = sub.add_parser("run-transition")
    p_transition.add_argument("run_id")
    p_transition.add_argument("state", choices=[state.value for state in RunState])
    p_transition.add_argument("--reason", required=True)
    p_transition.add_argument("--runs-root", default="runs")
    _add_snapshot_args(p_transition)

    p_status = sub.add_parser("run-status")
    p_status.add_argument("run_id")
    p_status.add_argument("--runs-root", default="runs")

    p_revalidate = sub.add_parser("run-revalidate")
    p_revalidate.add_argument("run_id")
    p_revalidate.add_argument("--runs-root", default="runs")
    _add_snapshot_args(p_revalidate)

    args = parser.parse_args(argv)
    try:
        if args.command == "validate-project":
            result = validate_project_bundle(load_json_object(args.path), executor_policy=load_json_object(args.policy), base_dir=args.base_dir)
            _print(result.to_dict())
            return 0 if result.ok else 2
        if args.command == "validate-test":
            evidence = load_json_object(args.holdout_evidence) if args.holdout_evidence else None
            result = validate_test_contract(load_json_object(args.path), base_dir=args.base_dir, holdout_evidence=evidence)
            _print(result.to_dict())
            return 0 if result.ok else 2
        if args.command == "validate-task":
            result = validate_task_bundle(
                load_json_object(args.path),
                executor_policy=load_json_object(args.policy),
                base_dir=args.base_dir,
                repository_roots=parse_repository_roots(args.repository_root),
            )
            _print(result.to_dict())
            return 0 if result.ok else 2
        if args.command == "policy-check":
            project = load_json_object(args.project)
            policy = load_json_object(args.policy)
            validation = validate_project_bundle(project, executor_policy=policy, base_dir=args.base_dir)
            if not validation.ok:
                _print(validation.to_dict())
                return 2
            engine = PolicyEngine(project, policy)
            results = []
            if args.path:
                results.append(engine.check_path_change(args.path, public_api_change=args.public_api_change, data_schema_change=args.data_schema_change, result_semantics_change=args.result_semantics_change).to_dict())
                if args.allowed:
                    results.append(engine.check_forbidden_path(args.path, args.allowed, repository_root=args.repository_root).to_dict())
            results.extend(o.to_dict() for o in engine.check_capabilities(network=args.network, secrets=args.secret, command=args.command_line))
            _print({"objections": results})
            return 2 if any(item["kind"] in {"HARD_VETO", "POLICY_VETO"} for item in results) else 0
        if args.command == "repository-read":
            project = load_json_object(args.project)
            policy = load_json_object(args.policy)
            validation = validate_project_bundle(project, executor_policy=policy, base_dir=args.base_dir)
            if not validation.ok:
                _print(validation.to_dict())
                return 2
            wrapped = read_wrapped_repository_file(
                repository=args.repository,
                commit=args.commit,
                root=args.root,
                path=args.path,
                project_contract=project,
            )
            _print(wrapped)
            return 0
        if args.command == "form-gp001-request":
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
        if args.command == "github-pilot-draft":
            request = verify_github_request(
                GitHubRestClient(),
                profile=_github_profile(args.profile),
                issue_number=args.issue,
            )
            draft = build_pilot_draft(request)
            _print(
                {
                    "schema_version": "executor-pilot-draft-result/1.0",
                    "status": "AWAITING_VERIFIED_GITHUB_DECISION",
                    "draft": draft,
                    "draft_sha256": pilot_draft_sha256(draft),
                    "executable": False,
                }
            )
            return 0
        if args.command == "github-pilot-decide":
            profile = _github_profile(args.profile)
            source = GitHubRestClient()
            request = verify_github_request(
                source,
                profile=profile,
                issue_number=args.issue,
            )
            draft = build_pilot_draft(request)
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
                ledger=AtomicAuthorityLedger(args.ledger),
            )
            _print(result)
            return 0 if result["status"] == "AUTHORIZED_AND_FROZEN" else 2
        if args.command == "run-pilot":
            profile = _github_profile(args.profile)
            source = GitHubRestClient()
            request = verify_github_request(
                source,
                profile=profile,
                issue_number=args.issue,
            )
            frozen = load_json_object(args.frozen)
            decision = verify_github_decision(
                source,
                profile=profile,
                request=request,
                comment_id=args.comment,
                draft_sha256=frozen.get("draft_sha256", ""),
            )
            commit = args.executor_commit or _git_head(args.executor_root)
            runtime = PilotRuntime(
                executor_root=args.executor_root,
                executor_commit=commit,
                frozen_result=frozen,
                proposal=load_json_object(args.proposal),
                verified_request=request,
                verified_decision=decision,
                ledger_path=args.ledger,
                runs_root=args.runs_root,
                image=args.image,
                docker_binary=args.docker_binary,
            )
            result = runtime.execute(
                workspace=args.workspace,
                run_id=args.run_id,
            )
            _print(result)
            return 0 if result["status"] == "ACTION_COMPLETED_REVIEW_REQUIRED" else 2
        if args.command == "materialize-pilot-proposal":
            proposal = materialize_solution_candidate(
                load_json_object(args.candidate),
                frozen_result=load_json_object(args.frozen),
            )
            _print(proposal)
            return 0
        if args.command == "run-create":
            store = RunStore(args.runs_root)
            run_id = store.create(_snapshot_from_args(args), run_id=args.run_id)
            _print(store.load_state(run_id))
            return 0
        if args.command == "run-transition":
            event = RunStore(args.runs_root).transition(args.run_id, args.state, _snapshot_from_args(args), reason=args.reason)
            _print(event)
            return 0
        if args.command == "run-status":
            _print(RunStore(args.runs_root).load_state(args.run_id))
            return 0
        if args.command == "run-revalidate":
            result = RunStore(args.runs_root).revalidate(args.run_id, _snapshot_from_args(args))
            _print(result.to_dict())
            return 0 if result.unchanged else 3
    except (
        AuthorityLedgerError,
        FormationError,
        GitHubTrustError,
        PilotBlocked,
        PilotContractError,
        SolutionProposalError,
        InvalidTransition,
        RunIntegrityError,
        OSError,
        ValueError,
    ) as exc:
        _print({"status": "BLOCKED", "error": str(exc)})
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
