from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

from executor.request_to_contract import FormationStatus, RequestToContract001
from executor.solution_provider import build_solution_provenance, generate_validated_solution


ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "tasks" / "GP001_FIX_FAILING_TEST_CASE_001.yaml"


def git_head() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def canonical_task() -> dict:
    return json.loads(TASK_PATH.read_text(encoding="utf-8"))


def clean_formation() -> RequestToContract001:
    current = RequestToContract001(
        executor_root=ROOT,
        executor_commit=git_head(),
        request_id="request-formation-e2e",
        user_request="Napraw failing test dotyczący atomowości batcha.",
    )
    current.propose_interpretation(
        understood_objective="Naprawić regresję atomowości ProjectRegistry.add_many.",
        proposed_task_contract=canonical_task(),
    )
    current.create_draft()
    if current.critique():
        raise AssertionError("canonical formation unexpectedly failed critique")
    current.present_for_authorization()
    return current


class FakeProvider:
    provider_name = "TEST_EXTERNAL_INTELLIGENCE"
    model_name = "test-model-1"

    def __init__(self, candidate: dict):
        self.candidate = candidate
        self.received_frozen = None
        self.received_prompt = None

    def generate_candidate(self, *, frozen_contract: dict, prompt: str) -> dict:
        self.received_frozen = frozen_contract
        self.received_prompt = prompt
        return self.candidate


class FormationToProviderFlowTests(unittest.TestCase):
    def test_form_result_contains_exact_canonical_github_request_payload(self) -> None:
        current = clean_formation()
        exported = current.export_human_authorization_request()
        canonical = exported["canonical_contract_request"]
        payload = canonical["github_request_payload"]

        self.assertEqual(canonical["schema_version"], "executor-canonical-contract-request/1.0")
        self.assertEqual(canonical["formation_binding"]["draft_sha256"], current.draft_sha256)
        self.assertEqual(payload["schema_version"], "executor-github-request/1.0")
        self.assertEqual(payload["request_id"], "request-formation-e2e")
        self.assertEqual(payload["target"]["repository"], "FJ899/executor-pilot-target")
        self.assertEqual(payload["target"]["commit"], "3934a94a5eebf750079200589d6dc40e024d44a0")
        self.assertEqual(payload["target"]["tree"], "26d307afcbb3ce72b2911ca44936712c11558c4c")
        self.assertEqual(payload["task"]["allowed_paths"], ["project_registry/registry.py"])
        self.assertEqual(payload["task"]["max_production_files"], 1)
        self.assertFalse(canonical["executable"])

    def test_modify_starts_a_new_revision_and_revalidation_cycle(self) -> None:
        current = clean_formation()
        first_hash = current.draft_sha256
        current.apply_authority_result(
            {"status": "MODIFICATION_REQUIRED", "draft_sha256": first_hash}
        )
        self.assertEqual(current.status, FormationStatus.MODIFICATION_REQUIRED)

        current.begin_revision(user_request="Napraw regresję atomowości bez zmiany testów.")
        self.assertEqual(current.status, FormationStatus.REQUEST_RECEIVED)
        self.assertEqual(current.revision, 2)
        current.propose_interpretation(
            understood_objective="Naprawić tę samą regresję w dozwolonym pliku.",
            proposed_task_contract=canonical_task(),
        )
        current.create_draft()
        self.assertNotEqual(current.draft_sha256, first_hash)
        self.assertEqual(current.critique(), ())
        current.present_for_authorization()
        self.assertEqual(current.status, FormationStatus.AWAITING_VERIFIED_HUMAN_AUTHORIZATION)

    def test_reject_is_terminal_and_non_executable(self) -> None:
        current = clean_formation()
        current.apply_authority_result(
            {"status": "REJECTED", "draft_sha256": current.draft_sha256}
        )
        self.assertEqual(current.status, FormationStatus.REJECTED)
        self.assertFalse(current.decision_surface()["executable"])

    def test_provider_boundary_builds_provenance_not_provider(self) -> None:
        replacement = "def run():\n    return 1\n"
        after = hashlib.sha256(replacement.encode("utf-8")).hexdigest()
        candidate = {
            "schema_version": "executor-solution-candidate/1.0",
            "status": "AWAITING_FROZEN_CONTRACT_SHA",
            "proposal_id": "provider-test-1",
            "repository": "FJ899/executor-pilot-target",
            "source_commit": "3934a94a5eebf750079200589d6dc40e024d44a0",
            "source_tree": "26d307afcbb3ce72b2911ca44936712c11558c4c",
            "mutations": [
                {
                    "path": "project_registry/registry.py",
                    "expected_before_sha256": "0" * 64,
                    "replacement_text": replacement,
                    "expected_after_sha256": after,
                }
            ],
            "rationale": "bounded test candidate",
            "evidence_plan": [
                [
                    "python",
                    "-m",
                    "unittest",
                    "tests.test_registry.ProjectRegistryTests.test_duplicate_batch_does_not_partially_mutate_registry",
                    "-v",
                ],
                ["python", "-m", "unittest", "discover", "-s", "tests", "-v"],
                ["python", "-m", "compileall", "-q", "project_registry", "tests"],
            ],
        }
        contract = {
            "request_id": "request-formation-e2e",
            "target": {
                "repository": "FJ899/executor-pilot-target",
                "commit": "3934a94a5eebf750079200589d6dc40e024d44a0",
                "tree": "26d307afcbb3ce72b2911ca44936712c11558c4c",
            },
            "task": {
                "allowed_paths": ["project_registry/registry.py"],
                "protected_paths": ["tests/**"],
                "postcondition_argv": [candidate["evidence_plan"][0]],
                "regression_argv": candidate["evidence_plan"][1:],
                "max_production_files": 1,
            },
            "request_evidence": {
                "repository": "FJ899/Executor",
                "issue_number": 1,
                "issue_node_id": "I_test",
                "body_sha256": "1" * 64,
                "created_at": "2026-08-26T10:00:00Z",
            },
        }
        frozen = {
            "status": "AUTHORIZED_AND_FROZEN",
            "contract": contract,
            "contract_sha256": "2" * 64,
        }
        provider = FakeProvider(candidate)
        prompt = "Produce a bounded candidate for the exact frozen contract."

        provenance = build_solution_provenance(
            provider=provider,
            frozen_result=frozen,
            prompt=prompt,
            generated_at="2026-08-26T11:00:00Z",
        )
        self.assertEqual(provenance["provider"], provider.provider_name)
        self.assertEqual(provenance["model"], provider.model_name)
        self.assertEqual(provenance["effect_capability"], "NONE")
        self.assertEqual(
            provenance["prompt_sha256"], hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        )

        validated = generate_validated_solution(
            provider=provider,
            frozen_result=frozen,
            prompt=prompt,
            generated_at="2026-08-26T11:00:00Z",
        )
        self.assertEqual(validated.proposal_id, "provider-test-1")
        self.assertEqual(validated.provenance["effect_capability"], "NONE")
        self.assertEqual(provider.received_prompt, prompt)


if __name__ == "__main__":
    unittest.main()
