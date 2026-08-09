from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from typing import Any


OBSERVATION_SCHEMA = "executor-gp001-replay-observation/1.0"
COMPARISON_SCHEMA = "executor-gp001-replay-comparison/1.0"
EXPECTED_STATUS = "ACTION_COMPLETED_REVIEW_REQUIRED"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def decode_observation(payload: str) -> dict[str, Any]:
    try:
        raw = base64.b64decode(payload, validate=True)
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"invalid replay observation payload: {exc}") from exc
    require(isinstance(value, dict), "replay observation must be an object")
    require(value.get("schema_version") == OBSERVATION_SCHEMA, "replay observation schema mismatch")
    require(isinstance(value.get("stable"), dict), "stable replay projection missing")
    require(isinstance(value.get("ephemeral"), dict), "ephemeral replay projection missing")
    require(isinstance(value.get("observed_hashes"), dict), "observed hash projection missing")
    return value


def differing_paths(left: Any, right: Any, prefix: str = "stable") -> list[str]:
    if type(left) is not type(right):
        return [prefix]
    if isinstance(left, dict):
        paths: list[str] = []
        keys = sorted(set(left) | set(right))
        for key in keys:
            if key not in left or key not in right:
                paths.append(f"{prefix}.{key}")
                continue
            paths.extend(differing_paths(left[key], right[key], f"{prefix}.{key}"))
        return paths
    if isinstance(left, list):
        if len(left) != len(right):
            return [prefix]
        paths: list[str] = []
        for index, (left_item, right_item) in enumerate(zip(left, right, strict=True)):
            paths.extend(differing_paths(left_item, right_item, f"{prefix}[{index}]"))
        return paths
    return [] if left == right else [prefix]


def compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_stable = left["stable"]
    right_stable = right["stable"]
    differences = differing_paths(left_stable, right_stable)
    require(not differences, "contractual replay mismatch: " + ", ".join(differences))

    require(left_stable.get("status") == EXPECTED_STATUS, "left replay lost review-required terminal semantics")
    require(right_stable.get("status") == EXPECTED_STATUS, "right replay lost review-required terminal semantics")
    require(left_stable.get("human_decision_required") is True, "left replay lost human review gate")
    require(right_stable.get("human_decision_required") is True, "right replay lost human review gate")

    left_ephemeral = left["ephemeral"]
    right_ephemeral = right["ephemeral"]
    require(left_ephemeral.get("run_id") != right_ephemeral.get("run_id"), "replay run IDs are not independent")
    require(left_ephemeral.get("packet_id") != right_ephemeral.get("packet_id"), "replay packet IDs are not independent")

    left_execution_ids = left_ephemeral.get("execution_ids")
    right_execution_ids = right_ephemeral.get("execution_ids")
    require(isinstance(left_execution_ids, list) and left_execution_ids, "left replay execution IDs missing")
    require(isinstance(right_execution_ids, list) and right_execution_ids, "right replay execution IDs missing")
    require(
        set(left_execution_ids).isdisjoint(set(right_execution_ids)),
        "replay execution IDs are not independent",
    )

    return {
        "schema_version": COMPARISON_SCHEMA,
        "status": "CONTRACTUALLY_EQUIVALENT_REVIEW_REQUIRED",
        "contractual_equivalence": "EQUIVALENT",
        "ephemeral_independence": "DISTINCT",
        "observed_hash_identity": left["observed_hashes"] == right["observed_hashes"],
        "human_decision_required": True,
        "excluded_from_equivalence_gate": [
            "run_id",
            "packet_id",
            "execution_ids",
            "observed_hashes",
        ],
        "stable_projection": left_stable,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left-b64", default=os.environ.get("GP001_REPLAY_LEFT_B64"))
    parser.add_argument("--right-b64", default=os.environ.get("GP001_REPLAY_RIGHT_B64"))
    args = parser.parse_args()

    require(bool(args.left_b64), "left replay observation missing")
    require(bool(args.right_b64), "right replay observation missing")

    result = compare(
        decode_observation(args.left_b64),
        decode_observation(args.right_b64),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"GP001 REPLAY COMPARISON FAILED: {exc}", file=sys.stderr)
        raise
