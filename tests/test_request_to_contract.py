from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from executor.gp001_contract import validate_gp001_task_contract
from executor.request_to_contract import (
    FormationError,
    FormationStatus,
    HumanDecisionReceipt,
    RequestToContract001,
)


ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "tasks" / "GP001_FIX_FAILING_TEST_CASE_001.yaml"
USER_REQUEST = "Napraw failing test dotyczący atomowości batcha."


def canonical_task() -> dict:
    return json.loads(TASK_PATH.read_text(encoding="utf-8"))


def session() -> RequestToContract001:
    return RequestToContract001(
        executor_root=ROOT,
        request_id="request-001",
        user_request=USER_REQUEST,
    )


def propose_canonical(
    current: RequestToContract001,
    *,
    discoveries: tuple[str, ...] = (),
    questions: tuple[str, ...] = (),
) -> None:
    current.propose_interpretation(
        understood_objective="Naprawić regresję atomowości ProjectRegistry.add_many.",
        proposed_task_contract=canonical_task(),
        user_facts=[("$.request.topic", "failing test")],
        model_inferences=[
            ("$.target.repository", "litrgratis-pixel/executor-pilot-target", 0.99),
            (
                "$.target.test",
                "tests.test_registry.ProjectRegistryTests.test_duplicate_batch_does_not_partially_mutate_registry",
                0.99,
            ),
        ],
        out_of_scope_discoveries=discoveries,
        open_questions=questions,
    )


def prepare_for_authorization(current: RequestToContract001) -> dict:
    current.create_draft()
    findings = current.critique()
    if findings:
        raise AssertionError(f"unexpected critique findings: {findings}")
    return current.present_for_authorization()


class RequestToContract001Tests(unittest.TestCase):
    def test_request_is_preserved_and_non_executable_before_authorization(self) -> None:
        current = session()
        self.assertEqual(current.status, FormationStatus.REQUEST_RECEIVED)
        with self.assertRaises(FormationError):
            current.frozen_task_contract()

        propose_canonical(current)
        surface = current.create_draft()

        self.assertEqual(surface["request"], USER_REQUEST)
        self.assertEqual(surface["status"], "DRAFT_CONTRACT_CREATED")
        self.assertFalse(surface["executable"])
        self.assertEqual(surface["provenance"][0]["source"], "USER")
        self.assertEqual(surface["provenance"][0]["value"], USER_REQUEST)
        self.assertTrue(any(item["source"] == "MODEL" for item in surface["provenance"]))

    def test_canonical_proposal_requires_hash_bound_human_accept_before_freeze(self) -> None:
        current = session()
        propose_canonical(current)
        surface = prepare_for_authorization(current)

        self.assertEqual(surface["status"], "AWAITING_HUMAN_AUTHORIZATION")
        self.assertFalse(surface["executable"])
        draft_sha = surface["draft_sha256"]
        self.assertIsNotNone(draft_sha)

        result = current.record_human_decision(
            HumanDecisionReceipt(
                decision="ACCEPT",
                draft_sha256=draft_sha,
                authority_source="HUMAN_AUTHORITY",
                authority_evidence_ref="human-gate:test-request-001",
            )
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["status"], "AUTHORIZED_AND_FROZEN")
        self.assertEqual(result["formation_evidence"]["authority_source"], "HUMAN_AUTHORITY")
        self.assertEqual(result["task_contract"], canonical_task())
        self.assertEqual(validate_gp001_task_contract(result["task_contract"]).status.value, "VALID")

    def test_model_cannot_be_declared_as_human_authority(self) -> None:
        with self.assertRaises(FormationError):
            HumanDecisionReceipt(
                decision="ACCEPT",
                draft_sha256="0" * 64,
                authority_source="MODEL",
                authority_evidence_ref="model-self-approval",
            )

    def test_stale_or_wrong_draft_hash_cannot_authorize(self) -> None:
        current = session()
        propose_canonical(current)
        prepare_for_authorization(current)

        with self.assertRaises(FormationError):
            current.record_human_decision(
                HumanDecisionReceipt(
                    decision="ACCEPT",
                    draft_sha256="0" * 64,
                    authority_source="HUMAN_AUTHORITY",
                    authority_evidence_ref="human-gate:stale",
                )
            )
        self.assertEqual(current.status, FormationStatus.AWAITING_HUMAN_AUTHORIZATION)

    def test_scope_expansion_is_blocked_by_critique(self) -> None:
        widened = canonical_task()
        widened["golden_path"]["scope"]["allowed_paths"].append("tests/test_registry.py")

        current = session()
        current.propose_interpretation(
            understood_objective="Napraw test i zmodyfikuj test acceptance.",
            proposed_task_contract=widened,
            model_inferences=[("$.scope.expansion", "tests/test_registry.py", 0.8)],
        )
        current.create_draft()
        findings = current.critique()
        surface = current.present_for_authorization()

        codes = {item.code for item in findings}
        self.assertIn("CONTRACT_DIVERGENCE_FROM_ACCEPTED_GP001_PROFILE", codes)
        self.assertEqual(surface["status"], "NEEDS_CLARIFICATION")
        self.assertFalse(surface["executable"])

    def test_open_question_blocks_authorization_instead_of_becoming_an_assumption(self) -> None:
        current = session()
        propose_canonical(current, questions=("Czy wolno rozszerzyć zmianę na tests/**?",))
        current.create_draft()
        findings = current.critique()
        surface = current.present_for_authorization()

        self.assertIn("OPEN_QUESTIONS_REQUIRE_CLARIFICATION", {item.code for item in findings})
        self.assertEqual(surface["status"], "NEEDS_CLARIFICATION")
        with self.assertRaises(FormationError):
            current.record_human_decision(
                HumanDecisionReceipt(
                    decision="ACCEPT",
                    draft_sha256=surface["draft_sha256"],
                    authority_source="HUMAN_AUTHORITY",
                    authority_evidence_ref="human-gate:cannot-accept-ambiguity",
                )
            )

    def test_discovery_remains_report_only_and_does_not_expand_contract(self) -> None:
        discovery = "Registry architecture could be refactored more broadly."
        current = session()
        propose_canonical(current, discoveries=(discovery,))
        surface = prepare_for_authorization(current)

        self.assertEqual(surface["discovered_but_out_of_scope"], [discovery])
        self.assertEqual(surface["proposed_write_scope"], ["project_registry/registry.py"])
        self.assertEqual(surface["status"], "AWAITING_HUMAN_AUTHORIZATION")

    def test_modify_invalidates_previous_review_and_requires_new_critique(self) -> None:
        widened = canonical_task()
        widened["golden_path"]["scope"]["allowed_paths"].append("README.md")

        current = session()
        current.propose_interpretation(
            understood_objective="Napraw test.",
            proposed_task_contract=widened,
            model_inferences=[("$.scope", ["project_registry/registry.py", "README.md"], 0.7)],
        )
        current.create_draft()
        current.critique()
        blocked_surface = current.present_for_authorization()
        old_sha = blocked_surface["draft_sha256"]

        current.record_human_decision(
            HumanDecisionReceipt(
                decision="MODIFY",
                draft_sha256=old_sha,
                authority_source="HUMAN_AUTHORITY",
                authority_evidence_ref="human-gate:remove-scope-expansion",
            ),
            modified_task_contract=canonical_task(),
            modification_note="Usuń rozszerzenie scope; pozostaw tylko GP001.",
        )

        self.assertEqual(current.status, FormationStatus.DRAFT_CONTRACT_CREATED)
        self.assertNotEqual(current.draft_sha256, old_sha)
        findings = current.critique()
        self.assertEqual(findings, ())
        surface = current.present_for_authorization()
        self.assertEqual(surface["status"], "AWAITING_HUMAN_AUTHORIZATION")
        self.assertTrue(
            any(
                item["source"] == "USER" and item["path"] == "$.proposed_task_contract"
                for item in surface["provenance"]
            )
        )

    def test_reject_is_terminal_and_creates_no_frozen_contract(self) -> None:
        current = session()
        propose_canonical(current)
        surface = prepare_for_authorization(current)

        current.record_human_decision(
            HumanDecisionReceipt(
                decision="REJECT",
                draft_sha256=surface["draft_sha256"],
                authority_source="HUMAN_AUTHORITY",
                authority_evidence_ref="human-gate:reject-request-001",
            )
        )

        self.assertEqual(current.status, FormationStatus.REJECTED)
        with self.assertRaises(FormationError):
            current.frozen_task_contract()

    def test_frozen_contract_is_returned_as_copy_not_mutable_authority_state(self) -> None:
        current = session()
        propose_canonical(current)
        surface = prepare_for_authorization(current)
        current.record_human_decision(
            HumanDecisionReceipt(
                decision="ACCEPT",
                draft_sha256=surface["draft_sha256"],
                authority_source="HUMAN_AUTHORITY",
                authority_evidence_ref="human-gate:copy-test",
            )
        )

        first = current.frozen_task_contract()
        first["id"] = "MUTATED-BY-CALLER"
        second = current.frozen_task_contract()
        self.assertEqual(second["id"], "GP001-FIX-FAILING-TEST-CASE-001")
        self.assertNotEqual(first, second)

    def test_caller_cannot_skip_formation_states(self) -> None:
        current = session()
        with self.assertRaises(FormationError):
            current.create_draft()
        with self.assertRaises(FormationError):
            current.critique()
        with self.assertRaises(FormationError):
            current.present_for_authorization()

    def test_user_request_and_model_inference_remain_distinct_provenance(self) -> None:
        current = session()
        propose_canonical(current)
        current.create_draft()
        surface = current.decision_surface()

        user_records = [item for item in surface["provenance"] if item["source"] == "USER"]
        model_records = [item for item in surface["provenance"] if item["source"] == "MODEL"]
        self.assertGreaterEqual(len(user_records), 2)
        self.assertGreaterEqual(len(model_records), 2)
        self.assertEqual(user_records[0]["value"], USER_REQUEST)
        self.assertNotEqual(user_records[0]["source"], model_records[0]["source"])


if __name__ == "__main__":
    unittest.main()
