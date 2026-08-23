from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from executor.request_to_contract import (
    FormationError,
    FormationStatus,
    RequestToContract001,
)


ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "tasks" / "GP001_FIX_FAILING_TEST_CASE_001.yaml"
PROFILE_PATH = ROOT / "formation_profiles" / "REQUEST_TO_CONTRACT_001.json"
USER_REQUEST = "Napraw failing test dotyczący atomowości batcha."


def git_head(root: Path = ROOT) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def canonical_task() -> dict:
    return json.loads(TASK_PATH.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def session() -> RequestToContract001:
    return RequestToContract001(
        executor_root=ROOT,
        executor_commit=git_head(),
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


def prepare_clean_authorization_surface(current: RequestToContract001) -> dict:
    current.create_draft()
    findings = current.critique()
    if findings:
        raise AssertionError(f"unexpected critique findings: {findings}")
    return current.present_for_authorization()


class RequestToContract001Tests(unittest.TestCase):
    def test_request_is_preserved_and_never_executable_in_phase_one(self) -> None:
        current = session()
        self.assertEqual(current.status, FormationStatus.REQUEST_RECEIVED)
        with self.assertRaises(FormationError):
            current.frozen_task_contract()

        propose_canonical(current)
        surface = current.create_draft()

        self.assertEqual(surface["request"], USER_REQUEST)
        self.assertEqual(surface["status"], "DRAFT_CONTRACT_CREATED")
        self.assertFalse(surface["executable"])
        with self.assertRaises(FormationError):
            current.frozen_task_contract()

    def test_clean_draft_stops_at_verified_external_human_authority_boundary(self) -> None:
        current = session()
        propose_canonical(current)
        surface = prepare_clean_authorization_surface(current)

        self.assertEqual(
            surface["status"], "AWAITING_VERIFIED_HUMAN_AUTHORIZATION"
        )
        self.assertFalse(surface["executable"])
        request = current.export_human_authorization_request()
        self.assertEqual(
            request["required_authority"], "VERIFIED_EXTERNAL_HUMAN_AUTHORITY"
        )
        self.assertEqual(request["draft_sha256"], surface["draft_sha256"])
        self.assertEqual(request["allowed_decisions"], ["ACCEPT", "MODIFY", "REJECT"])
        with self.assertRaises(FormationError):
            current.frozen_task_contract()

    def test_self_declared_human_authority_cannot_create_executable_contract(self) -> None:
        current = session()
        propose_canonical(current)
        prepare_clean_authorization_surface(current)

        self.assertFalse(hasattr(current, "record_human_decision"))
        self.assertFalse(hasattr(current, "authorize"))
        self.assertFalse(hasattr(current, "freeze"))
        with self.assertRaisesRegex(FormationError, "verified external human authorization"):
            current.frozen_task_contract()

    def test_public_api_cannot_inject_user_facts_or_profile_override(self) -> None:
        constructor = inspect.signature(RequestToContract001)
        proposal = inspect.signature(RequestToContract001.propose_interpretation)

        self.assertNotIn("profile_path", constructor.parameters)
        self.assertNotIn("user_facts", proposal.parameters)
        self.assertNotIn("authority_source", proposal.parameters)
        self.assertNotIn("human_decision", proposal.parameters)
        self.assertIn("executor_commit", constructor.parameters)

    def test_only_verbatim_request_has_direct_user_provenance(self) -> None:
        current = session()
        propose_canonical(current)
        current.create_draft()
        surface = current.decision_surface()

        user_records = [item for item in surface["provenance"] if item["source"] == "USER"]
        model_records = [item for item in surface["provenance"] if item["source"] == "MODEL"]
        self.assertEqual(len(user_records), 1)
        self.assertEqual(user_records[0]["path"], "$.user_request")
        self.assertEqual(user_records[0]["value"], USER_REQUEST)
        self.assertGreaterEqual(len(model_records), 2)

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
        with self.assertRaises(FormationError):
            current.export_human_authorization_request()

    def test_open_question_blocks_instead_of_becoming_an_assumption(self) -> None:
        current = session()
        propose_canonical(current, questions=("Czy wolno rozszerzyć zmianę na tests/**?",))
        current.create_draft()
        findings = current.critique()
        surface = current.present_for_authorization()

        self.assertIn("OPEN_QUESTIONS_REQUIRE_CLARIFICATION", {item.code for item in findings})
        self.assertEqual(surface["status"], "NEEDS_CLARIFICATION")
        with self.assertRaises(FormationError):
            current.export_human_authorization_request()

    def test_discovery_remains_report_only_and_does_not_expand_contract(self) -> None:
        discovery = "Registry architecture could be refactored more broadly."
        current = session()
        propose_canonical(current, discoveries=(discovery,))
        surface = prepare_clean_authorization_surface(current)

        self.assertEqual(surface["discovered_but_out_of_scope"], [discovery])
        self.assertEqual(surface["proposed_write_scope"], ["project_registry/registry.py"])
        self.assertEqual(
            surface["status"], "AWAITING_VERIFIED_HUMAN_AUTHORIZATION"
        )

    def test_caller_cannot_skip_formation_states(self) -> None:
        current = session()
        with self.assertRaises(FormationError):
            current.create_draft()
        with self.assertRaises(FormationError):
            current.critique()
        with self.assertRaises(FormationError):
            current.present_for_authorization()
        with self.assertRaises(FormationError):
            current.export_human_authorization_request()

    def test_proposal_is_copied_before_caller_can_mutate_it(self) -> None:
        proposal = canonical_task()
        current = session()
        current.propose_interpretation(
            understood_objective="Naprawić regresję atomowości.",
            proposed_task_contract=proposal,
        )
        proposal["golden_path"]["scope"]["allowed_paths"].append("README.md")

        current.create_draft()
        self.assertEqual(current.critique(), ())
        surface = current.present_for_authorization()
        self.assertEqual(surface["proposed_write_scope"], ["project_registry/registry.py"])

    def test_decision_surface_is_defensive_copy(self) -> None:
        current = session()
        propose_canonical(current)
        prepare_clean_authorization_surface(current)

        first = current.decision_surface()
        first["target"]["name"] = "attacker/other"
        first["proposed_write_scope"].append("README.md")
        first["provenance"][0]["value"] = "forged request"

        second = current.decision_surface()
        self.assertEqual(second["target"]["name"], "litrgratis-pixel/executor-pilot-target")
        self.assertEqual(second["proposed_write_scope"], ["project_registry/registry.py"])
        self.assertEqual(second["provenance"][0]["value"], USER_REQUEST)

    def test_authorization_request_binds_executor_profile_task_and_draft_hashes(self) -> None:
        current = session()
        propose_canonical(current)
        surface = prepare_clean_authorization_surface(current)
        request = current.export_human_authorization_request()

        self.assertEqual(request["executor_repository"], "FJ899/Executor")
        self.assertEqual(request["executor_commit"], git_head())
        self.assertEqual(request["draft_sha256"], surface["draft_sha256"])
        self.assertEqual(request["formation_profile_sha256"], sha256_file(PROFILE_PATH))
        self.assertEqual(request["canonical_task_sha256"], sha256_file(TASK_PATH))
        self.assertFalse(request["decision_surface"]["executable"])

    def test_noncanonical_task_cannot_reach_clean_authorization_request(self) -> None:
        changed = canonical_task()
        changed["golden_path"]["problem"]["statement"] = (
            "Fix GP001 and refactor the whole registry architecture."
        )
        current = session()
        current.propose_interpretation(
            understood_objective="Naprawić test i przebudować registry.",
            proposed_task_contract=changed,
            model_inferences=[("$.broader_refactor", True, 0.9)],
        )
        current.create_draft()
        findings = current.critique()
        surface = current.present_for_authorization()

        self.assertIn(
            "CONTRACT_DIVERGENCE_FROM_ACCEPTED_GP001_PROFILE",
            {item.code for item in findings},
        )
        self.assertEqual(surface["status"], "NEEDS_CLARIFICATION")
        with self.assertRaises(FormationError):
            current.export_human_authorization_request()

    def test_non_authoritative_executor_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp)
            (fake / "formation_profiles").mkdir()
            (fake / "formation_profiles" / "REQUEST_TO_CONTRACT_001.json").write_text(
                PROFILE_PATH.read_text(encoding="utf-8"), encoding="utf-8"
            )
            with self.assertRaisesRegex(FormationError, "unverified Executor formation source"):
                RequestToContract001(
                    executor_root=fake,
                    executor_commit=git_head(),
                    request_id="forged",
                    user_request=USER_REQUEST,
                )


if __name__ == "__main__":
    unittest.main()
