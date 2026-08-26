from __future__ import annotations

import copy
import hashlib
import inspect
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from executor.frozen_pilot_authority import validate_frozen_pilot_authority
from executor.github_trust import GitHubTrustError, GitHubTrustProfile
from executor.request_to_contract import (
    FormationError,
    FormationStatus,
    RequestToContract001,
)
from tests.p4_test_support import governed_ledger


ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "tasks" / "GP001_FIX_FAILING_TEST_CASE_001.yaml"
PROFILE_PATH = ROOT / "formation_profiles" / "REQUEST_TO_CONTRACT_001.json"
USER_REQUEST = "Napraw failing test dotyczący atomowości batcha."
TARGET_REPOSITORY = "FJ899/executor-pilot-target"
TARGET_COMMIT = "3934a94a5eebf750079200589d6dc40e024d44a0"
TARGET_TREE = "26d307afcbb3ce72b2911ca44936712c11558c4c"
INTAKE_REPOSITORY = "FJ899/Executor"
ISSUE_NUMBER = 71
ISSUE_URL = f"https://api.github.com/repos/{INTAKE_REPOSITORY}/issues/{ISSUE_NUMBER}"
NOW = datetime(2026, 8, 16, 2, 0, tzinfo=timezone.utc)


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
            ("$.target.repository", TARGET_REPOSITORY, 0.99),
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


def formation_profile() -> GitHubTrustProfile:
    return GitHubTrustProfile.from_dict(
        {
            "schema_version": "executor-github-trust-profile/1.0",
            "profile_id": "REQUEST-TO-CONTRACT-001",
            "intake_repository": INTAKE_REPOSITORY,
            "allowed_actor": {"login": "FJ899", "id": 275481581},
            "allowed_target_repositories": [TARGET_REPOSITORY],
            "max_decision_lifetime_seconds": 3600,
        }
    )


class FakeSource:
    def __init__(self, values: dict[str, dict] | None = None):
        self.values = values or {}

    def fetch_json(self, url: str) -> dict:
        if url not in self.values:
            raise GitHubTrustError(f"GitHub provider event is unavailable: {url}")
        return copy.deepcopy(self.values[url])


def target_commit_url() -> str:
    return f"https://api.github.com/repos/{TARGET_REPOSITORY}/git/commits/{TARGET_COMMIT}"


def authority_source(
    current: RequestToContract001,
    *,
    decision: str = "ACCEPT",
    comment_id: int = 9101,
    draft_sha256: str | None = None,
    edited: bool = False,
    comment_created_at: str | None = None,
    request_binding_override: dict | None = None,
) -> tuple[FakeSource, dict]:
    source = FakeSource(
        {
            target_commit_url(): {
                "sha": TARGET_COMMIT,
                "tree": {"sha": TARGET_TREE},
            }
        }
    )
    request_payload = current.build_github_authority_request(
        source=source,
        profile=formation_profile(),
        now=NOW,
    )
    request_body = json.dumps(request_payload, sort_keys=True)
    request_body_sha256 = hashlib.sha256(request_body.encode("utf-8")).hexdigest()
    source.values[ISSUE_URL] = {
        "url": ISSUE_URL,
        "repository_url": f"https://api.github.com/repos/{INTAKE_REPOSITORY}",
        "number": ISSUE_NUMBER,
        "id": 7101,
        "node_id": "I_kwDO-formation-request",
        "state": "open",
        "body": request_body,
        "created_at": "2026-08-16T00:00:00Z",
        "updated_at": "2026-08-16T00:00:00Z",
        "author_association": "OWNER",
        "performed_via_github_app": None,
        "user": {"login": "FJ899", "id": 275481581, "type": "User"},
    }
    request_binding = {
        "repository": INTAKE_REPOSITORY,
        "issue_number": ISSUE_NUMBER,
        "issue_node_id": "I_kwDO-formation-request",
        "body_sha256": request_body_sha256,
    }
    if request_binding_override:
        request_binding.update(request_binding_override)
    decision_payload = {
        "schema_version": "executor-github-decision/1.0",
        "request": request_binding,
        "draft_sha256": draft_sha256 or current.draft_sha256,
        "decision": decision,
        "valid_for_seconds": 1800,
        "nonce": f"formation-decision-{comment_id}",
    }
    created_at = comment_created_at or "2026-08-16T01:59:00Z"
    updated_at = "2026-08-16T01:59:01Z" if edited else created_at
    comment_url = (
        f"https://api.github.com/repos/{INTAKE_REPOSITORY}/issues/comments/{comment_id}"
    )
    source.values[comment_url] = {
        "url": comment_url,
        "issue_url": ISSUE_URL,
        "id": comment_id,
        "node_id": f"IC_kwDO-formation-{comment_id}",
        "body": json.dumps(decision_payload, sort_keys=True),
        "created_at": created_at,
        "updated_at": updated_at,
        "author_association": "OWNER",
        "performed_via_github_app": None,
        "user": {"login": "FJ899", "id": 275481581, "type": "User"},
    }
    return source, request_payload


def apply_authority(
    current: RequestToContract001,
    source: FakeSource,
    ledger_path: Path,
    *,
    comment_id: int = 9101,
):
    with patch("executor.pilot_contract._utc_now", return_value=NOW):
        return current.apply_github_authority_decision(
            source=source,
            profile=formation_profile(),
            issue_number=ISSUE_NUMBER,
            comment_id=comment_id,
            ledger=governed_ledger(ledger_path),
            now=NOW,
        )


class RequestToContract001Tests(unittest.TestCase):
    def test_request_is_preserved_and_not_executable_before_authority(self) -> None:
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
        self.assertEqual(surface["status"], "AWAITING_VERIFIED_HUMAN_AUTHORIZATION")
        self.assertFalse(surface["executable"])
        request = current.export_human_authorization_request()
        self.assertEqual(request["required_authority"], "VERIFIED_EXTERNAL_HUMAN_AUTHORITY")
        self.assertEqual(request["draft_sha256"], surface["draft_sha256"])
        self.assertEqual(request["allowed_decisions"], ["ACCEPT", "MODIFY", "REJECT"])

    def test_self_declared_human_authority_cannot_create_executable_contract(self) -> None:
        current = session()
        propose_canonical(current)
        prepare_clean_authorization_surface(current)
        self.assertFalse(hasattr(current, "record_human_decision"))
        self.assertFalse(hasattr(current, "authorize"))
        self.assertFalse(hasattr(current, "freeze"))
        with self.assertRaisesRegex(FormationError, "no authorized frozen result"):
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
        self.assertIn("CONTRACT_DIVERGENCE_FROM_ACCEPTED_GP001_PROFILE", {item.code for item in findings})
        self.assertEqual(surface["status"], "NEEDS_CLARIFICATION")
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

    def test_discovery_remains_report_only_and_does_not_expand_contract(self) -> None:
        discovery = "Registry architecture could be refactored more broadly."
        current = session()
        propose_canonical(current, discoveries=(discovery,))
        surface = prepare_clean_authorization_surface(current)
        self.assertEqual(surface["discovered_but_out_of_scope"], [discovery])
        self.assertEqual(surface["proposed_write_scope"], ["project_registry/registry.py"])

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
        first["invalidated_draft_sha256s"].append("f" * 64)
        second = current.decision_surface()
        self.assertEqual(second["target"]["name"], TARGET_REPOSITORY)
        self.assertEqual(second["proposed_write_scope"], ["project_registry/registry.py"])
        self.assertEqual(second["provenance"][0]["value"], USER_REQUEST)
        self.assertEqual(second["invalidated_draft_sha256s"], [])

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
        self.assertEqual(request["draft_version"], 1)
        self.assertFalse(request["decision_surface"]["executable"])

    def test_noncanonical_task_cannot_reach_clean_authorization_request(self) -> None:
        changed = canonical_task()
        changed["golden_path"]["problem"]["statement"] = "Fix GP001 and refactor the whole registry architecture."
        current = session()
        current.propose_interpretation(
            understood_objective="Naprawić test i przebudować registry.",
            proposed_task_contract=changed,
            model_inferences=[("$.broader_refactor", True, 0.9)],
        )
        current.create_draft()
        findings = current.critique()
        surface = current.present_for_authorization()
        self.assertIn("CONTRACT_DIVERGENCE_FROM_ACCEPTED_GP001_PROFILE", {item.code for item in findings})
        self.assertEqual(surface["status"], "NEEDS_CLARIFICATION")

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

    def test_github_authority_payload_is_generated_from_draft_and_live_tree(self) -> None:
        current = session()
        propose_canonical(current)
        prepare_clean_authorization_surface(current)
        source = FakeSource({target_commit_url(): {"sha": TARGET_COMMIT, "tree": {"sha": TARGET_TREE}}})
        payload = current.build_github_authority_request(source=source, profile=formation_profile(), now=NOW)
        repeated = current.build_github_authority_request(source=source, profile=formation_profile(), now=NOW + timedelta(minutes=5))
        self.assertEqual(repeated, payload)
        self.assertEqual(payload["request_id"], "request-001")
        self.assertEqual(payload["target"], {"repository": TARGET_REPOSITORY, "commit": TARGET_COMMIT, "tree": TARGET_TREE})
        self.assertEqual(payload["task"]["allowed_paths"], ["project_registry/registry.py"])
        self.assertEqual(payload["task"]["precondition_argv"], payload["task"]["postcondition_argv"])
        self.assertIn(current.draft_sha256[:24], payload["nonce"])

    def test_accept_exact_formation_draft_freezes_for_existing_p4_boundary(self) -> None:
        current = session()
        propose_canonical(current)
        prepare_clean_authorization_surface(current)
        draft_sha = current.draft_sha256
        source, generated_request = authority_source(current, decision="ACCEPT")
        with tempfile.TemporaryDirectory() as directory:
            result = apply_authority(current, source, Path(directory) / "ledger.sqlite3")
        self.assertEqual(result["status"], "AUTHORIZED_AND_FROZEN")
        self.assertEqual(current.status, FormationStatus.AUTHORIZED_AND_FROZEN)
        self.assertTrue(result["executable"])
        self.assertEqual(result["draft_sha256"], draft_sha)
        self.assertEqual(result["contract"]["draft_sha256"], draft_sha)
        self.assertEqual(result["contract"]["target"]["tree"], TARGET_TREE)
        binding = result["contract"]["formation_binding"]
        self.assertEqual(binding["draft_sha256"], draft_sha)
        self.assertEqual(binding["draft"]["request_id"], "request-001")
        self.assertEqual(binding["authority_request_payload"], generated_request)
        self.assertEqual(current.frozen_task_contract(), result["contract"])
        validate_frozen_pilot_authority(result)

    def test_modify_invalidates_old_draft_and_old_accept_cannot_freeze_revision(self) -> None:
        current = session()
        propose_canonical(current)
        prepare_clean_authorization_surface(current)
        old_draft = current.draft_sha256
        source, _ = authority_source(current, decision="MODIFY", comment_id=9102)
        with tempfile.TemporaryDirectory() as directory:
            result = apply_authority(current, source, Path(directory) / "modify-ledger.sqlite3", comment_id=9102)
            self.assertEqual(result["status"], "MODIFICATION_REQUIRED")
            self.assertEqual(current.status, FormationStatus.MODIFICATION_REQUIRED)
            revised = current.revise_after_modify(
                understood_objective="Ponownie przygotować ten sam bounded fix po MODIFY.",
                proposed_task_contract=canonical_task(),
            )
            self.assertEqual(revised["status"], "AWAITING_VERIFIED_HUMAN_AUTHORIZATION")
            self.assertEqual(revised["draft_version"], 2)
            self.assertEqual(revised["supersedes_draft_sha256"], old_draft)
            self.assertIn(old_draft, revised["invalidated_draft_sha256s"])
            self.assertNotEqual(current.draft_sha256, old_draft)
            stale_source, _ = authority_source(current, decision="ACCEPT", comment_id=9103, draft_sha256=old_draft)
            with self.assertRaisesRegex(FormationError, "different draft"):
                apply_authority(current, stale_source, Path(directory) / "stale-accept-ledger.sqlite3", comment_id=9103)

    def test_reject_never_creates_frozen_contract(self) -> None:
        current = session()
        propose_canonical(current)
        prepare_clean_authorization_surface(current)
        source, _ = authority_source(current, decision="REJECT", comment_id=9104)
        with tempfile.TemporaryDirectory() as directory:
            result = apply_authority(current, source, Path(directory) / "reject-ledger.sqlite3", comment_id=9104)
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(current.status, FormationStatus.REJECTED)
        self.assertFalse(result["executable"])
        self.assertNotIn("contract", result)
        with self.assertRaises(FormationError):
            current.frozen_result()

    def test_edited_expired_and_mismatched_decisions_block_freeze(self) -> None:
        cases = (
            {"name": "edited", "kwargs": {"edited": True, "comment_id": 9110}, "message": "edited"},
            {"name": "expired", "kwargs": {"comment_created_at": "2026-08-16T00:01:00Z", "comment_id": 9111}, "message": "not currently fresh"},
            {"name": "mismatched", "kwargs": {"request_binding_override": {"body_sha256": "f" * 64}, "comment_id": 9112}, "message": "stale or mismatched"},
        )
        for case in cases:
            with self.subTest(case=case["name"]), tempfile.TemporaryDirectory() as directory:
                current = session()
                propose_canonical(current)
                prepare_clean_authorization_surface(current)
                source, _ = authority_source(current, decision="ACCEPT", **case["kwargs"])
                with self.assertRaisesRegex(FormationError, case["message"]):
                    apply_authority(current, source, Path(directory) / "ledger.sqlite3", comment_id=case["kwargs"]["comment_id"])
                self.assertEqual(current.status, FormationStatus.AWAITING_VERIFIED_HUMAN_AUTHORIZATION)
                with self.assertRaises(FormationError):
                    current.frozen_result()


if __name__ == "__main__":
    unittest.main()
