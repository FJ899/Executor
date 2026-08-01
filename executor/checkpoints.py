from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from executor.hashing import hash_json, hash_tree


class CheckpointError(RuntimeError):
    pass


@dataclass(frozen=True)
class Snapshot:
    executor_version: str
    policy_hash: str
    project_contract_hash: str
    task_contract_hash: str
    test_contract_hash: str
    prompt_bundle_hash: str
    model_id: str
    repository_shas: dict[str, str]
    input_hashes: dict[str, str]
    workspace_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_snapshot(
    *,
    executor_version: str,
    policy: Any,
    project_contract: Any,
    task_contract: Any,
    test_contract: Any,
    prompt_bundle: Any,
    model_id: str,
    repository_shas: dict[str, str],
    inputs: dict[str, str | Path],
    workspace: str | Path,
) -> Snapshot:
    return Snapshot(
        executor_version=executor_version,
        policy_hash=hash_json(policy),
        project_contract_hash=hash_json(project_contract),
        task_contract_hash=hash_json(task_contract),
        test_contract_hash=hash_json(test_contract),
        prompt_bundle_hash=hash_json(prompt_bundle),
        model_id=model_id,
        repository_shas=dict(sorted(repository_shas.items())),
        input_hashes={name: hash_tree(path) for name, path in sorted(inputs.items())},
        workspace_hash=hash_tree(workspace),
    )


def atomic_write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
        try:
            directory_fd = os.open(target.parent, os.O_DIRECTORY)
        except (AttributeError, OSError):
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def append_jsonl(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    with target.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
