from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from executor.authority_ledger import AtomicAuthorityLedger
from executor.github_authority import (
    GlobalAuthorityReplayError,
    GlobalAuthorityReservation,
    GovernedAuthorityLedger,
)
from executor.github_trust import canonical_json


class FakeGlobalAuthority:
    def __init__(self, shared: dict[str, dict[str, Any]] | None = None):
        self.shared = shared if shared is not None else {}

    def reserve(self, *, authority_key, payload_sha256, action_kind, run_id):
        if authority_key in self.shared:
            raise GlobalAuthorityReplayError(
                f"global authority already consumed: {authority_key}"
            )
        ref = "refs/heads/executor-authority/" + hashlib.sha256(
            authority_key.encode("utf-8")
        ).hexdigest()
        reservation_sha = hashlib.sha1(
            f"{authority_key}:{payload_sha256}:RESERVED".encode("utf-8")
        ).hexdigest()
        reservation = GlobalAuthorityReservation(
            authority_key=authority_key,
            payload_sha256=payload_sha256,
            action_kind=action_kind,
            run_id=run_id,
            ref=ref,
            reservation_sha=reservation_sha,
        )
        self.shared[authority_key] = {
            "reservation": reservation,
            "state": "RESERVED",
            "result_sha256": None,
        }
        return reservation

    def finalize(self, reservation, *, result):
        record = self.shared[reservation.authority_key]
        result_sha = hashlib.sha256(canonical_json(result).encode("utf-8")).hexdigest()
        if record["state"] == "FINAL" and record["result_sha256"] != result_sha:
            raise RuntimeError("global result differs")
        record["state"] = "FINAL"
        record["result_sha256"] = result_sha
        final_sha = hashlib.sha1(
            f"{reservation.authority_key}:{result_sha}:FINAL".encode("utf-8")
        ).hexdigest()
        return {
            **reservation.to_dict(),
            "state": "FINAL",
            "final_sha": final_sha,
            "result_sha256": result_sha,
        }


def governed_ledger(
    path: str | Path,
    *,
    shared: dict[str, dict[str, Any]] | None = None,
) -> GovernedAuthorityLedger:
    return GovernedAuthorityLedger(
        AtomicAuthorityLedger(path),
        FakeGlobalAuthority(shared),
    )


def provenance_for(frozen: dict[str, Any]) -> dict[str, Any]:
    contract = frozen["contract"]
    request = contract["request_evidence"]
    target = contract["target"]
    return {
        "schema_version": "executor-solution-provenance/1.0",
        "producer_role": "EXTERNAL_INTELLIGENCE",
        "provider": "OpenAI",
        "model": "GPT-5.6 Sol",
        "generated_at": "2026-08-16T00:02:00Z",
        "request": {
            "repository": request["repository"],
            "issue_number": request["issue_number"],
            "issue_node_id": request["issue_node_id"],
            "body_sha256": request["body_sha256"],
        },
        "source": {
            "repository": target["repository"],
            "commit": target["commit"],
            "tree": target["tree"],
        },
        "prompt_sha256": "a" * 64,
        "human_solution_edits": 0,
        "effect_capability": "NONE",
        "derivation": "REGENERATED_AFTER_HUMAN_REQUEST",
        "historical_candidate_relation": "NEW_FIX",
    }


def execution_environment(
    *,
    executor_commit: str = "e" * 40,
    image: str = "sha256:" + "1" * 64,
) -> dict[str, Any]:
    return {
        "schema_version": "executor-execution-environment/1.0",
        "provider": "GITHUB_ACTIONS",
        "repository": "JTJ07/Executor",
        "executor_commit": executor_commit,
        "workflow_path": ".github/workflows/p4-real-pilots-one-shot.yml",
        "workflow_sha256": "d" * 64,
        "workflow_run_id": "12345",
        "workflow_run_attempt": "1",
        "workflow_job": "scriptops-pilot",
        "sandbox_image_id": image,
    }
