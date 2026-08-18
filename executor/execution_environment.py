from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any


class ExecutionEnvironmentError(RuntimeError):
    pass


_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_github_actions_environment(
    *,
    image_id: str,
    executor_root: str | Path,
    executor_commit: str,
) -> dict[str, Any]:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    workflow_path = os.environ.get("EXECUTOR_WORKFLOW_PATH", "")
    workflow_run_id = os.environ.get("GITHUB_RUN_ID", "")
    workflow_run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    workflow_job = os.environ.get("GITHUB_JOB", "")
    if repository != "JTJ07/Executor":
        raise ExecutionEnvironmentError("P4 execution requires JTJ07/Executor GitHub Actions")
    if workflow_path != ".github/workflows/p4-real-pilots-one-shot.yml":
        raise ExecutionEnvironmentError("P4 execution workflow path is not canonical")
    if not workflow_run_id.isdigit() or not workflow_run_attempt.isdigit() or not workflow_job:
        raise ExecutionEnvironmentError("GitHub Actions run/job identity is incomplete")
    if _COMMIT.fullmatch(executor_commit) is None:
        raise ExecutionEnvironmentError("executor commit is invalid")
    if _IMAGE_ID.fullmatch(image_id) is None:
        raise ExecutionEnvironmentError("sandbox image must be an exact sha256 image ID")
    root = Path(executor_root).resolve(strict=True)
    workflow = (root / workflow_path).resolve(strict=True)
    try:
        workflow.relative_to(root)
    except ValueError as exc:
        raise ExecutionEnvironmentError("workflow path escapes Executor root") from exc
    workflow_sha = _file_sha256(workflow)
    return {
        "schema_version": "executor-execution-environment/1.0",
        "provider": "GITHUB_ACTIONS",
        "repository": repository,
        "executor_commit": executor_commit,
        "workflow_path": workflow_path,
        "workflow_sha256": workflow_sha,
        "workflow_run_id": workflow_run_id,
        "workflow_run_attempt": workflow_run_attempt,
        "workflow_job": workflow_job,
        "sandbox_image_id": image_id,
    }


def validate_execution_environment(
    value: dict[str, Any],
    *,
    executor_commit: str,
    image_id: str,
) -> dict[str, Any]:
    expected_keys = {
        "schema_version",
        "provider",
        "repository",
        "executor_commit",
        "workflow_path",
        "workflow_sha256",
        "workflow_run_id",
        "workflow_run_attempt",
        "workflow_job",
        "sandbox_image_id",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise ExecutionEnvironmentError("execution environment has invalid fields")
    if value["schema_version"] != "executor-execution-environment/1.0":
        raise ExecutionEnvironmentError("execution environment schema is invalid")
    if value["provider"] != "GITHUB_ACTIONS" or value["repository"] != "JTJ07/Executor":
        raise ExecutionEnvironmentError("execution environment provider/repository is invalid")
    if value["workflow_path"] != ".github/workflows/p4-real-pilots-one-shot.yml":
        raise ExecutionEnvironmentError("execution environment workflow is not canonical")
    if value["executor_commit"] != executor_commit:
        raise ExecutionEnvironmentError("execution environment Executor commit mismatch")
    if value["sandbox_image_id"] != image_id or _IMAGE_ID.fullmatch(image_id) is None:
        raise ExecutionEnvironmentError("execution environment sandbox image mismatch")
    if _SHA256_HEX.fullmatch(str(value["workflow_sha256"])) is None:
        raise ExecutionEnvironmentError("execution environment workflow hash is invalid")
    if not str(value["workflow_run_id"]).isdigit() or not str(value["workflow_run_attempt"]).isdigit():
        raise ExecutionEnvironmentError("execution environment workflow run identity is invalid")
    if not isinstance(value["workflow_job"], str) or not value["workflow_job"]:
        raise ExecutionEnvironmentError("execution environment workflow job is invalid")
    return dict(value)
