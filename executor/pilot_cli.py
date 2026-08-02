from __future__ import annotations

import argparse
import json

from executor.pilot_case_001 import case_001_sandbox_spec, execute_case_001
from executor.pilot_case_002 import (
    CASE_002_CONTRACT,
    PilotCase002DockerSandboxBackend,
    case_002_sandbox_spec,
    execute_case_002,
)
from executor.sandbox.pilot import PilotCase001DockerSandboxBackend
from executor.sandbox.policy_snapshot import load_execution_policy_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="creative-os-executor-pilot")
    parser.add_argument("--case", choices=("001", "002"), default="001")
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--runs-root", required=True)
    parser.add_argument("--executor-root", default=".")
    parser.add_argument("--executor-commit", required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args(argv)

    snapshot = load_execution_policy_snapshot(
        args.executor_root,
        commit=args.executor_commit,
    )
    if args.case == "001":
        backend = PilotCase001DockerSandboxBackend(policy_snapshot=snapshot)
        report = execute_case_001(
            repository_root=args.repository_root,
            runs_root=args.runs_root,
            sandbox_backend=backend,
            sandbox_spec=case_001_sandbox_spec(args.image),
        )
    else:
        backend = PilotCase002DockerSandboxBackend(
            policy_snapshot=snapshot,
            contract=CASE_002_CONTRACT,
        )
        report = execute_case_002(
            repository_root=args.repository_root,
            runs_root=args.runs_root,
            sandbox_backend=backend,
            sandbox_spec=case_002_sandbox_spec(args.image),
        )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ACTION_COMPLETED_REVIEW_REQUIRED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
