from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from executor.gp001_runtime import AuthorizedFileMutation, GP001Runtime


TASK_ID = "GP001-FIX-FAILING-TEST-CASE-001"
FIXTURE_REPOSITORY = "FJ899/executor-pilot-target"
FIXTURE_COMMIT = "3934a94a5eebf750079200589d6dc40e024d44a0"
MUTATION_PATH = "project_registry/registry.py"

OLD_BLOCK = '''    def add_many(self, projects: Iterable[Project]) -> None:\n        """Add projects one by one, leaving earlier writes after a late duplicate."""\n\n        for project in projects:\n            if project.project_id in self._projects:\n                raise DuplicateProjectError(\n                    f"duplicate project_id: {project.project_id}"\n                )\n            self._projects[project.project_id] = project\n'''

NEW_BLOCK = '''    def add_many(self, projects: Iterable[Project]) -> None:\n        """Add a batch atomically after validating all project identifiers."""\n\n        batch = list(projects)\n        seen = set(self._projects)\n        for project in batch:\n            if project.project_id in seen:\n                raise DuplicateProjectError(\n                    f"duplicate project_id: {project.project_id}"\n                )\n            seen.add(project.project_id)\n        for project in batch:\n            self._projects[project.project_id] = project\n'''


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def build_replay_observation(
    *,
    plan: dict[str, object],
    report: dict[str, object],
    executor_commit: str,
    image: str,
) -> dict[str, object]:
    authorization = report["authorization"]
    commands = report["commands"]
    action_argv = authorization["action_argv"]
    require(isinstance(action_argv, list) and len(action_argv) >= 2, "authorization action binding missing")

    stable_commands = []
    execution_ids = []
    for command in commands:
        stable_commands.append(
            {
                "argv": command["argv"],
                "exit_code": command["exit_code"],
                "timed_out": command["timed_out"],
                "cleanup_verified": command["cleanup_verified"],
                "policy_sha256": command["policy_sha256"],
            }
        )
        execution_ids.append(command["execution_id"])

    return {
        "schema_version": "executor-gp001-replay-observation/1.0",
        "stable": {
            "executor_commit": executor_commit,
            "sandbox_image": image,
            "task_id": report["task_id"],
            "repository": report["repository"],
            "input_commit": report["input_commit"],
            "status": report["status"],
            "human_decision_required": report["human_decision_required"],
            "changed_paths": report["changed_paths"],
            "authorization": {
                "model": report["authorization_model"],
                "consumption": report["authorization_consumption"],
                "authority_class": authorization["authority_class"],
                "fixture_binding": authorization["fixture_binding"],
                "issuer_id": authorization["issuer_id"],
                "issuer_role": authorization["issuer_role"],
                "issuer_evidence_ref": authorization["issuer_evidence_ref"],
                "action_kind": action_argv[0],
                "action_path": action_argv[1],
            },
            "plan": {
                "task_id": plan["task_id"],
                "repository": plan["repository"],
                "commit": plan["commit"],
                "path": plan["path"],
                "scope_expansion": plan["scope_expansion"],
                "strategy": plan["strategy"],
            },
            "evidence": report["evidence"],
            "commands": stable_commands,
        },
        "ephemeral": {
            "run_id": report["run_id"],
            "packet_id": authorization["packet_id"],
            "execution_ids": execution_ids,
        },
        "observed_hashes": {
            "before_sha256": plan["before_sha256"],
            "after_sha256": plan["after_sha256"],
            "authorization_payload_sha256": authorization["payload_sha256"],
        },
    }


def main() -> int:
    executor_root = Path(os.environ["EXECUTOR_ROOT"]).resolve()
    workspace = Path(os.environ["GP001_WORKSPACE"]).resolve()
    runs_root = Path(os.environ["GP001_RUNS_ROOT"]).resolve()
    executor_commit = os.environ["EXECUTOR_COMMIT"]
    image = os.environ["GP001_IMAGE"]
    run_id = os.environ.get("GP001_RUN_ID", "gp001-real-e2e")

    require(git(workspace, "rev-parse", "HEAD") == FIXTURE_COMMIT, "fixture HEAD mismatch")
    require(
        git(workspace, "remote", "get-url", "origin").rstrip("/").removesuffix(".git")
        == f"https://github.com/{FIXTURE_REPOSITORY}",
        "fixture origin mismatch",
    )
    require(not git(workspace, "status", "--porcelain"), "fixture must start clean")

    target = workspace / MUTATION_PATH
    before = target.read_bytes()
    before_text = before.decode("utf-8")
    require(before_text.count(OLD_BLOCK) == 1, "bounded plan no longer matches pinned source")
    after_text = before_text.replace(OLD_BLOCK, NEW_BLOCK, 1)
    after = after_text.encode("utf-8")

    mutation = AuthorizedFileMutation(
        path=MUTATION_PATH,
        expected_before_sha256=sha256(before),
        replacement_text=after_text,
        expected_after_sha256=sha256(after),
    )

    runs_root.mkdir(parents=True, exist_ok=True)
    plan = {
        "schema_version": "executor-gp001-e2e-plan/1.0",
        "task_id": TASK_ID,
        "repository": FIXTURE_REPOSITORY,
        "commit": FIXTURE_COMMIT,
        "path": MUTATION_PATH,
        "before_sha256": mutation.expected_before_sha256,
        "after_sha256": mutation.expected_after_sha256,
        "scope_expansion": False,
        "strategy": "validate entire batch before mutating registry",
    }
    (runs_root / "bounded-plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    runtime = GP001Runtime(
        executor_root=executor_root,
        executor_commit=executor_commit,
        runs_root=runs_root,
        image=image,
    )
    report = runtime.execute(
        workspace=workspace,
        mutation=mutation,
        run_id=run_id,
    )

    require(report["task_id"] == TASK_ID, "report task mismatch")
    require(report["repository"] == FIXTURE_REPOSITORY, "report repository mismatch")
    require(report["input_commit"] == FIXTURE_COMMIT, "report commit mismatch")
    require(report["status"] == "ACTION_COMPLETED_REVIEW_REQUIRED", f"unexpected status: {report['status']}")
    require(report["status"] != "PASS", "runtime must not self-certify PASS")
    require(report["human_decision_required"] is True, "human review gate was lost")
    require(report["changed_paths"] == [MUTATION_PATH], f"scope mismatch: {report['changed_paths']}")
    require(report["authorization"]["authority_class"] == "CONTROLLED_EXTERNAL_FIXTURE", "authority class mismatch")
    require(
        report["authorization"]["fixture_binding"]
        == {"task": TASK_ID, "repository": FIXTURE_REPOSITORY, "commit": FIXTURE_COMMIT},
        "fixture binding mismatch",
    )

    expected_evidence = {
        "fixture_authority": "BOUND",
        "input_identity": "MATCH",
        "pre_change_target_test": "FAIL",
        "post_change_target_test": "PASS",
        "regression_checks": "PASS",
        "diff_scope": "ALLOWED",
        "protected_material": "UNCHANGED",
        "execution_limits": "RESPECTED",
        "result_artifact": "PRESENT",
    }
    require(report["evidence"] == expected_evidence, f"evidence mismatch: {report['evidence']}")
    require(git(workspace, "diff", "--name-only", FIXTURE_COMMIT) == MUTATION_PATH, "real diff escaped scope")

    observation = build_replay_observation(
        plan=plan,
        report=report,
        executor_commit=executor_commit,
        image=image,
    )
    observation_path = os.environ.get("GP001_OBSERVATION_PATH")
    if observation_path:
        resolved = Path(observation_path).resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(
            json.dumps(observation, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print("=== BOUNDED PLAN ===")
    print(json.dumps(plan, indent=2, sort_keys=True))
    print("=== GP001 REPORT ===")
    print(json.dumps(report, indent=2, sort_keys=True))
    if observation_path:
        print("=== REPLAY OBSERVATION ===")
        print(json.dumps(observation, indent=2, sort_keys=True))
    print("=== REAL DIFF ===")
    print(git(workspace, "diff", "--", MUTATION_PATH))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"GP001 REAL E2E FAILED: {exc}", file=sys.stderr)
        raise
