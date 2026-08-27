from __future__ import annotations

import json
import os
import platform
from pathlib import Path

import pytest

from executor.github_trust import canonical_json
from executor.stage3_runtime import (
    CONTROL_PLANE,
    EVIDENCE_BUNDLE_OUTPUT,
    REPOSITORY_PLANE,
    Stage3MutationRuntime,
    Stage3TerminalStatus,
)


def test_frozen_trust_profiles_are_canonical_and_closed() -> None:
    root = Path(__file__).resolve().parents[1]
    policy_path = root / "trust_profiles/stage3_generation_identity_policy.json"
    trust_path = root / "trust_profiles/stage3_generation_attestation_root.jsonl"
    assert policy_path.is_file()
    assert trust_path.is_file()
    policy_raw = policy_path.read_bytes()
    policy = json.loads(policy_raw)
    assert policy_raw == canonical_json(policy).encode("utf-8")
    assert set(policy) == {
        "schema_version",
        "oidc_issuer",
        "repository",
        "signer_reusable_workflow",
        "signer_digest",
        "accepted_predicate_type",
        "accepted_evidence_schema",
        "verification_method",
        "trusted_root_sha256",
    }
    assert policy["oidc_issuer"] == "https://token.actions.githubusercontent.com"
    assert policy["repository"] == "FJ899/Executor"
    assert policy["signer_reusable_workflow"] == ".github/workflows/stage3-generation-verifier-attestation.yml"
    assert len(policy["signer_digest"]) == 40
    assert policy["accepted_evidence_schema"] == "executor-provider-generation-evidence/1.0"
    assert policy["verification_method"] == "OPENAI_RESPONSES_RETRIEVE_V1"
    lines = trust_path.read_text(encoding="utf-8").splitlines()
    assert lines and all(json.loads(line) for line in lines)


def test_real_linux_observable_effect_evidence() -> None:
    if os.environ.get("STAGE3_REQUIRE_REAL_EFFECT_EVIDENCE") != "1":
        pytest.skip("P4 enables STAGE3_REQUIRE_REAL_EFFECT_EVIDENCE=1 for the mandatory real effect run")
    assert platform.system() == "Linux"
    assert platform.machine() in {"x86_64", "AMD64"}
    assert REPOSITORY_PLANE == Path("/workspace/repo")
    assert CONTROL_PLANE == Path("/workspace/.stage3-control")

    result = Stage3MutationRuntime().execute()
    assert result.terminal_status is Stage3TerminalStatus.MUTATION_APPLIED_REVIEW_REQUIRED
    assert result.authority_consumed is True
    assert result.repository_write_count_claim == 1
    assert EVIDENCE_BUNDLE_OUTPUT.is_file()
    evidence = json.loads(EVIDENCE_BUNDLE_OUTPUT.read_text(encoding="utf-8"))
    assert evidence["effect_and_post_state"]["changed_paths"] == [
        evidence["effect_and_post_state"]["mutation_path"]
    ]
    assert evidence["effect_and_post_state"]["terminal_status"] == "MUTATION_APPLIED_REVIEW_REQUIRED"
    assert evidence["effect_and_post_state"]["control_inputs_unchanged"] is True
    assert evidence["effect_and_post_state"]["host_observer"]["network_effect_count"] == 0
    assert evidence["effect_and_post_state"]["host_observer"]["secret_exposure_count"] == 0
    assert evidence["effect_and_post_state"]["host_observer"]["task_command_exec_count"] == 0
    assert evidence["environment_and_source"]["pre_git_identities"] == evidence["effect_and_post_state"]["post_git_identities"]

    # The same allocation is terminal. A second invocation is a read-only replay attempt.
    replay = Stage3MutationRuntime().execute()
    assert replay.terminal_status is Stage3TerminalStatus.BLOCK
    assert replay.authority_consumed is False
    assert replay.repository_write_count_claim == 0
