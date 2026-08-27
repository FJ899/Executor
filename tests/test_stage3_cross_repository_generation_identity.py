from __future__ import annotations

import copy
import unittest

from executor.github_trust import canonical_json
from executor.stage3_evidence import sha256_json
from executor.stage3_generation_trust import (
    Stage3GenerationTrustError,
    Stage3GenerationTrustProfile,
    _expected_request,
    _validate_evidence_semantics,
)


REQUEST_REPOSITORY = "FJ899/Executor"
TARGET_REPOSITORY = "FJ899/executor-pilot-target"


def _profile() -> Stage3GenerationTrustProfile:
    return Stage3GenerationTrustProfile(
        oidc_issuer="https://token.actions.githubusercontent.com",
        repository="FJ899/Executor",
        signer_reusable_workflow=".github/workflows/stage3-generation-verifier-attestation.yml",
        signer_digest="a" * 40,
        accepted_predicate_type="https://fj899.github.io/Executor/attestations/provider-generation-evidence/v1",
        accepted_evidence_schema="executor-provider-generation-evidence/1.0",
        verification_method="OPENAI_RESPONSES_RETRIEVE_V1",
        trusted_root_sha256="b" * 64,
        policy_sha256="c" * 64,
    )


def _inputs() -> tuple[dict, dict, dict, dict]:
    frozen = {
        "contract": {
            "request_evidence": {
                "repository": REQUEST_REPOSITORY,
                "issue_number": 97,
                "issue_node_id": "I_kwDOExecutor97",
                "body_sha256": "1" * 64,
            }
        },
        "decision_consumption": {
            "state": "FINAL",
            "terminal_success": True,
            "receipt": "gp001",
        },
    }
    proposal = {
        "contract_sha256": "2" * 64,
        "repository": TARGET_REPOSITORY,
        "source_commit": "3" * 40,
        "source_tree": "4" * 40,
        "provenance": {"generated_at": "2026-08-28T12:00:00Z"},
    }
    stage2 = {
        "provider": "OpenAI",
        "model": "gpt-5.6-sol",
        "generation_evidence_ref": "resp_gp001_cross_repository",
        "context_sha256": "5" * 64,
        "prompt_sha256": "6" * 64,
        "generation_response_sha256": "7" * 64,
        "generation_challenge_sha256": "8" * 64,
        "generation_challenge_issued_at": "2026-08-28T11:59:00Z",
        "proposal_sha256": "9" * 64,
    }
    request = _expected_request(
        frozen_result=frozen,
        stage2_result=stage2,
        proposal=proposal,
    )
    evidence = {
        "schema_version": "executor-provider-generation-evidence/1.0",
        "provider": request["provider"],
        "model": request["model"],
        "generation_evidence_ref": request["generation_evidence_ref"],
        "provider_record_id": request["generation_evidence_ref"],
        "provider_generation_timestamp": request["provider_generation_timestamp"],
        "frozen_task_contract_sha256": request["frozen_task_contract_sha256"],
        "repository": request["repository"],
        "source_commit": request["source_commit"],
        "source_tree": request["source_tree"],
        "source_context_sha256": request["source_context_sha256"],
        "prompt_sha256": request["prompt_sha256"],
        "response_sha256": request["response_sha256"],
        "generation_challenge_sha256": request["generation_challenge_sha256"],
        "generation_challenge_issued_at": request["generation_challenge_issued_at"],
        "terminal_freeze_receipt_sha256": request["terminal_freeze_receipt_sha256"],
        "proposal_payload_sha256": request["proposal_payload_sha256"],
        "verification_method": "OPENAI_RESPONSES_RETRIEVE_V1",
        "verifier_repository": "FJ899/Executor",
        "verifier_reusable_workflow_path": ".github/workflows/stage3-generation-verifier-attestation.yml",
        "verifier_workflow_source_commit": "a" * 40,
        "verification_request_sha256": sha256_json(request),
        "evidence_hash_construction": "SHA256_CANONICAL_JSON_WITHOUT_EVIDENCE_ARTIFACT_SHA256",
        "attestation_predicate_type": "https://fj899.github.io/Executor/attestations/provider-generation-evidence/v1",
        "evidence_artifact_sha256": "0" * 64,
    }
    material = dict(evidence)
    material.pop("evidence_artifact_sha256")
    evidence["evidence_artifact_sha256"] = sha256_json(material)
    return frozen, stage2, proposal, evidence


def _raw(evidence: dict) -> bytes:
    return canonical_json(evidence).encode("utf-8")


class Stage3CrossRepositoryGenerationIdentityTests(unittest.TestCase):
    def test_request_and_target_repository_are_independent_and_valid(self) -> None:
        frozen, stage2, proposal, evidence = _inputs()
        request = _expected_request(
            frozen_result=frozen,
            stage2_result=stage2,
            proposal=proposal,
        )
        self.assertEqual(request["request_binding"]["repository"], REQUEST_REPOSITORY)
        self.assertEqual(request["repository"], TARGET_REPOSITORY)
        self.assertNotEqual(
            request["request_binding"]["repository"],
            request["repository"],
        )
        request_sha = _validate_evidence_semantics(
            evidence,
            raw=_raw(evidence),
            profile=_profile(),
            frozen_result=frozen,
            stage2_result=stage2,
            proposal=proposal,
        )
        self.assertEqual(request_sha, sha256_json(request))

    def test_request_repository_substitution_is_fail_closed(self) -> None:
        frozen, stage2, proposal, evidence = _inputs()
        tampered_frozen = copy.deepcopy(frozen)
        tampered_frozen["contract"]["request_evidence"]["repository"] = TARGET_REPOSITORY
        with self.assertRaises(Stage3GenerationTrustError):
            _validate_evidence_semantics(
                evidence,
                raw=_raw(evidence),
                profile=_profile(),
                frozen_result=tampered_frozen,
                stage2_result=stage2,
                proposal=proposal,
            )

    def test_target_repository_substitution_is_fail_closed(self) -> None:
        frozen, stage2, proposal, evidence = _inputs()
        tampered_proposal = copy.deepcopy(proposal)
        tampered_proposal["repository"] = REQUEST_REPOSITORY
        with self.assertRaises(Stage3GenerationTrustError):
            _validate_evidence_semantics(
                evidence,
                raw=_raw(evidence),
                profile=_profile(),
                frozen_result=frozen,
                stage2_result=stage2,
                proposal=tampered_proposal,
            )

    def test_frozen_workflow_does_not_reintroduce_request_target_equality(self) -> None:
        from pathlib import Path

        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/stage3-generation-verifier-attestation.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn('rb["repository"] != req["repository"]', workflow)
        self.assertIn('text(rb["repository"], "request repository")', workflow)
        self.assertIn('target.get("repository") != req["repository"]', workflow)
        self.assertIn('ctx.get("repository")', workflow)


if __name__ == "__main__":
    unittest.main()
