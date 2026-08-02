import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from executor.action_authorization import (
    AuthorizationContext,
    packet_payload_sha256,
    validate_action_authorization_packet,
)
from executor.checkpoints import build_snapshot
from executor.contracts import (
    ValidationStatus,
    load_contract,
    validate_project_contract,
    validate_task_contract,
    validate_test_contract,
)
from executor.governance import validate_project_bundle, validate_task_bundle
from executor.sandbox.docker import DockerSandboxBackend, SandboxExecutionError
from executor.state_machine import InvalidTransition, RunState, RunStore


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
COMMIT = "1" * 40
HASH = "2" * 64
NOW = datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc)


class M0M2BEntryGateTest(unittest.TestCase):
    def test_structural_validity_never_claims_execution_readiness(self):
        project = load_contract(ROOT / "project_contracts/executor-self.yaml")
        task = load_contract(ROOT / "tasks/examples/GINSENG_TEST-003.yaml")
        for result in (
            validate_project_contract(project),
            validate_task_contract(task),
        ):
            self.assertEqual(result.status, ValidationStatus.VALID)
            self.assertFalse(result.authoritative)
            self.assertFalse(result.ready_for_model)
            self.assertEqual(result.execution_status, "BLOCKED_BEFORE_MODEL")

    def test_authoritative_project_is_ready_but_placeholder_task_is_blocked(self):
        project = load_contract(ROOT / "project_contracts/executor-self.yaml")
        policy = load_contract(ROOT / "EXECUTOR_POLICY.yaml")
        project_result = validate_project_bundle(
            project,
            executor_policy=policy,
            base_dir=ROOT,
        )
        self.assertEqual(project_result.status, ValidationStatus.VALID)
        self.assertTrue(project_result.ready_for_model)

        task = load_contract(ROOT / "tasks/examples/GINSENG_TEST-003.yaml")
        task_result = validate_task_bundle(
            task,
            executor_policy=policy,
            base_dir=ROOT,
        )
        self.assertEqual(task_result.status, ValidationStatus.INVALID)
        self.assertFalse(task_result.ready_for_model)
        codes = {issue.code for issue in task_result.issues}
        self.assertIn("UNLOCKED_REPOSITORY", codes)
        self.assertIn("UNLOCKED_TEST_CONTRACT", codes)

    def test_production_holdout_self_declaration_remains_fail_closed(self):
        contract = load_contract(ROOT / "test_contracts/examples/valid_test.yaml")
        contract["test_id"] = "EXECUTOR_SELF_TEST-001"
        location = contract["holdout"]["location"]
        payload = (FIXTURES / location).read_bytes()
        evidence = {
            "schema_version": "executor-holdout-evidence/1.0",
            "attestation_id": "self-declared",
            "test_id": contract["test_id"],
            "location": location,
            "artifact_sha256": hashlib.sha256(payload).hexdigest(),
            "visibility": "HIDDEN_FROM_IMPLEMENTER",
            "access": "REPLAY_ONLY",
            "verifier_role": "INDEPENDENT_HOLDOUT_VERIFIER",
            "verifier": "claimed-independent",
        }
        result = validate_test_contract(
            contract,
            base_dir=FIXTURES,
            holdout_evidence=evidence,
        )
        self.assertEqual(result.status, ValidationStatus.INSUFFICIENT_EVIDENCE)
        self.assertFalse(result.ready_for_model)
        self.assertIn(
            "INDEPENDENT_HOLDOUT_VERIFICATION_UNAVAILABLE",
            {issue.code for issue in result.issues},
        )

    def test_state_machine_cannot_reach_pass_before_m3(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "file.txt").write_text("one", encoding="utf-8")
            input_file = root / "input.json"
            input_file.write_text('{"value":1}\n', encoding="utf-8")
            snapshot = build_snapshot(
                executor_version="0.2.0",
                policy={"version": "1"},
                project_contract={"project": "x"},
                task_contract={"task": "x"},
                test_contract={"test": "x"},
                prompt_bundle={"prompt": "x"},
                model_id="none",
                repository_shas={"target": "abc"},
                inputs={"input": input_file},
                workspace=workspace,
            )
            store = RunStore(root / "runs")
            run_id = "ENTRY-GATE"
            store.create(snapshot, run_id=run_id)
            with self.assertRaises(InvalidTransition):
                store.transition(run_id, RunState.PASS, snapshot, reason="premature")

    def test_sandbox_rejects_unverified_policy_dictionary(self):
        with self.assertRaises(SandboxExecutionError):
            DockerSandboxBackend(policy_snapshot={"execution": {}})

    def test_self_declared_user_cannot_cross_terminal_action_boundary(self):
        context = AuthorizationContext(
            run_id="run-001",
            task_id="TASK-001",
            risk_class="HIGH_RISK",
            mode="BUILD_AND_TEST",
            executor_commit=COMMIT,
            policy_sha256=HASH,
            project_contract_sha256="3" * 64,
            task_contract_sha256="4" * 64,
            test_contract_sha256="5" * 64,
            repository_commits={"litrgratis-pixel/Executor": COMMIT},
            allowed_paths=("executor/**",),
            external_projects=False,
            auto_merge=False,
            default_network=False,
            default_secrets=(),
            verified_issuer_evidence={},
        )
        packet = {
            "schema_version": "executor-action-authorization/1.0",
            "packet_id": "packet-entry-gate",
            "run_id": "run-001",
            "issued_at": "2026-08-02T14:55:00Z",
            "expires_at": "2026-08-02T15:30:00Z",
            "issuer": {
                "role": "USER",
                "id": "self-declared",
                "evidence_ref": "invented",
            },
            "bindings": {
                "task_id": "TASK-001",
                "risk_class": "HIGH_RISK",
                "mode": "BUILD_AND_TEST",
                "executor_commit": COMMIT,
                "policy_sha256": HASH,
                "project_contract_sha256": "3" * 64,
                "task_contract_sha256": "4" * 64,
                "test_contract_sha256": "5" * 64,
                "repository_commits": {"litrgratis-pixel/Executor": COMMIT},
            },
            "action": {
                "kind": "WRITE_REPOSITORY",
                "argv": [],
                "paths": ["executor/file.py"],
                "network": False,
                "secrets": [],
                "external_project": False,
            },
            "decision": {
                "status": "AUTHORIZED",
                "reasons": ["self declared"],
            },
            "constraints": {
                "max_uses": 1,
                "max_duration_seconds": 3600,
                "manual_confirmation_required": False,
            },
            "integrity": {
                "algorithm": "SHA-256",
                "payload_sha256": "0" * 64,
            },
        }
        packet["integrity"]["payload_sha256"] = packet_payload_sha256(packet)
        result, decision = validate_action_authorization_packet(
            packet,
            context=context,
            now=NOW,
        )
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertEqual(result.action_status, "BLOCKED_BEFORE_ACTION")
        self.assertIsNone(decision)
        self.assertIn(
            "UNVERIFIED_AUTHORIZATION_ISSUER",
            {issue.code for issue in result.issues},
        )


if __name__ == "__main__":
    unittest.main()
