from __future__ import annotations

import argparse
import json

from executor.contracts import ContractLoadError, load_contract, validate_project_contract, validate_task_contract, validate_test_contract
from executor.policy import PolicyEngine


def _print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


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
    except ContractLoadError as exc:
        _print({"status": "BLOCKED_BEFORE_MODEL", "error": str(exc)})
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
