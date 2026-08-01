from __future__ import annotations

import argparse
import json

from executor.checkpoints import build_snapshot
from executor.contracts import ContractLoadError, load_contract, validate_project_contract, validate_task_contract, validate_test_contract
from executor.policy import PolicyEngine
from executor.state_machine import InvalidTransition, RunState, RunStore


def _print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _snapshot_from_args(args: argparse.Namespace):
    return build_snapshot(
        executor_version=args.executor_version,
        policy=load_contract(args.policy),
        project_contract=load_contract(args.project),
        task_contract=load_contract(args.task),
        test_contract=load_contract(args.test_contract),
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="creative-os-executor")
    sub = parser.add_subparsers(dest="command", required=True)

    p_project = sub.add_parser("validate-project")
    p_project.add_argument("path")

    p_test = sub.add_parser("validate-test")
    p_test.add_argument("path")
    p_test.add_argument("--base-dir", default=None)

    p_task = sub.add_parser("validate-task")
    p_task.add_argument("path")

    p_policy = sub.add_parser("policy-check")
    p_policy.add_argument("project")
    p_policy.add_argument("--path")
    p_policy.add_argument("--allowed", action="append", default=[])
    p_policy.add_argument("--network", action="store_true")
    p_policy.add_argument("--secret", action="append", default=[])
    p_policy.add_argument("--command-line", default=None)
    p_policy.add_argument("--public-api-change", action="store_true")
    p_policy.add_argument("--data-schema-change", action="store_true")
    p_policy.add_argument("--result-semantics-change", action="store_true")

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
            result = validate_project_contract(load_contract(args.path))
            _print(result.to_dict())
            return 0 if result.ok else 2
        if args.command == "validate-test":
            result = validate_test_contract(load_contract(args.path), base_dir=args.base_dir)
            _print(result.to_dict())
            return 0 if result.ok else 2
        if args.command == "validate-task":
            result = validate_task_contract(load_contract(args.path))
            _print(result.to_dict())
            return 0 if result.ok else 2
        if args.command == "policy-check":
            project = load_contract(args.project)
            validation = validate_project_contract(project)
            if not validation.ok:
                _print(validation.to_dict())
                return 2
            engine = PolicyEngine(project)
            results = []
            if args.path:
                results.append(engine.check_path_change(args.path, public_api_change=args.public_api_change, data_schema_change=args.data_schema_change, result_semantics_change=args.result_semantics_change).to_dict())
                if args.allowed:
                    results.append(engine.check_forbidden_path(args.path, args.allowed).to_dict())
            results.extend(o.to_dict() for o in engine.check_capabilities(network=args.network, secrets=args.secret, command=args.command_line))
            _print({"objections": results})
            return 2 if any(item["kind"] in {"HARD_VETO", "POLICY_VETO"} for item in results) else 0
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
    except (ContractLoadError, InvalidTransition, OSError, ValueError) as exc:
        _print({"status": "BLOCKED", "error": str(exc)})
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
