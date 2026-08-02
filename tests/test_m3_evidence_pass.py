import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from executor.action_authorization import AuthorizationDecision
from executor.checkpoints import build_snapshot
from executor.m3.authorization_ledger import ActionResult, AuthorizationConsumptionLedger
from executor.m3.evidence import EvidenceIntegrityError, ReplayableEvidenceStore
from executor.m3.holdout import IndependentHoldoutStore
from executor.state_machine import InvalidTransition, RunState, RunStore


class M3EvidencePassTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.verifier_root = self.root / "holdout"
        self.ledger_root = self.root / "ledger"
        self.evidence_root = self.root / "evidence"
        self.runs = self.root / "runs"
        for path in (self.workspace, self.verifier_root, self.ledger_root, self.evidence_root):
            path.mkdir(mode=0o700)
        (self.workspace / "result.txt").write_text("before", encoding="utf-8")
        self.input = self.root / "input.json"
        self.input.write_text('{"input":1}', encoding="utf-8")
        self.holdout = IndependentHoldoutStore(
            self.verifier_root,
            implementer_workspace=self.workspace,
            verifier_id="holdout-v",
            verifier_key_id="holdout-key",
            authentication_key=b"h" * 32,
        )
        self.ledger = AuthorizationConsumptionLedger(
            self.ledger_root,
            authentication_key=b"l" * 32,
            key_id="ledger-key",
        )
        self.evidence = ReplayableEvidenceStore(
            self.evidence_root,
            authentication_key=b"e" * 32,
            key_id="evidence-key",
        )
        self.snapshot = build_snapshot(
            executor_version="0.3.0",
            policy={"version": "1"},
            project_contract={"project": "executor"},
            task_contract={"task": "self-test"},
            test_contract={"test": "EXECUTOR_SELF_TEST-001"},
            prompt_bundle={"prompt": "self-test"},
            model_id="ai-agent",
            repository_shas={"Executor": "a" * 40},
            inputs={"input": self.input},
            workspace=self.workspace,
        )
        self.run_store = RunStore(self.runs)
        self.run_store.create(self.snapshot, run_id="RUN-SELF-TEST")
        for state in (
            RunState.CONTRACT_VALIDATED,
            RunState.NORMALIZED,
            RunState.PLANNED,
            RunState.APPROVED,
            RunState.EXECUTING,
            RunState.VERIFYING,
            RunState.REPLAYING,
        ):
            self.run_store.transition(
                "RUN-SELF-TEST", state, self.snapshot, reason=state.value
            )

    def tearDown(self):
        self.temp.cleanup()

    def _complete_package(self, observations=None, result_status="SUCCEEDED"):
        observations = observations or {
            "positive_control": True,
            "negative_control": True,
            "tamper_control": True,
            "unchanged_control": True,
        }
        holdout_payload = json.dumps(
            {
                "schema_version": "executor-independent-holdout/1.0",
                "test_id": "EXECUTOR_SELF_TEST-001",
                "assertions": [
                    {"selector": "$.positive_control", "operator": "==", "expected": True},
                    {"selector": "$.tamper_control", "operator": "==", "expected": True},
                ],
            },
            sort_keys=True,
        ).encode()
        provision = self.holdout.provision(
            test_id="EXECUTOR_SELF_TEST-001", holdout_payload=holdout_payload
        )
        replay = self.holdout.replay(
            test_id="EXECUTOR_SELF_TEST-001",
            holdout_id=provision.holdout_id,
            candidate_result=observations,
        )
        decision = AuthorizationDecision(
            packet_id="PACKET-SELF-TEST",
            payload_sha256="1" * 64,
            action_kind="WRITE_REPOSITORY",
            expires_at="2030-01-01T00:00:00Z",
            issuer_role="USER",
            issuer_id="user",
            issuer_evidence_ref="user-evidence",
        )
        consumed = self.ledger.consume(
            decision,
            run_id="RUN-SELF-TEST",
            action_binding={"kind": "WRITE_REPOSITORY", "paths": ["result.txt"]},
        )
        bound = self.ledger.bind_result(
            packet_id=decision.packet_id,
            result_binding_token=consumed.result_binding_token,
            result=ActionResult(
                status=result_status,
                exit_code=0 if result_status == "SUCCEEDED" else 1,
                stdout_sha256="a" * 64,
                stderr_sha256="1" * 64,
                output_sha256="2" * 64,
                completed_at="2026-08-02T16:00:00Z",
            ),
        )
        package = self.evidence.create_package(
            run_id="RUN-SELF-TEST",
            snapshot=self.snapshot,
            executor_commit="a" * 40,
            repository_commits={"Executor": "a" * 40},
            packet_payload_sha256=decision.payload_sha256,
            consumption_receipt=consumed.public_dict(),
            action_result_receipt=bound.to_dict(),
            holdout_provision_receipt=provision.to_dict(),
            holdout_replay_receipt=replay.to_dict(),
            artifacts={"before": b"before", "after": b"after", "log": b"ok"},
            observations=observations,
        )
        return package

    def test_complete_replay_is_the_only_path_to_pass(self):
        package = self._complete_package()
        replay = self.evidence.replay(
            package, ledger=self.ledger, holdout_store=self.holdout
        )
        event = self.run_store.transition_pass(
            "RUN-SELF-TEST",
            self.snapshot,
            replay_receipt=replay,
            replay_verifier=self.evidence,
        )
        self.assertEqual(event["state"], "PASS")
        self.assertEqual(self.run_store.load_state("RUN-SELF-TEST")["state"], "PASS")

    def test_direct_pass_and_forged_receipt_are_blocked(self):
        with self.assertRaises(InvalidTransition):
            self.run_store.transition(
                "RUN-SELF-TEST", RunState.PASS, self.snapshot, reason="direct"
            )
        package = self._complete_package()
        replay = self.evidence.replay(
            package, ledger=self.ledger, holdout_store=self.holdout
        )
        with self.assertRaisesRegex(InvalidTransition, "rejected"):
            self.run_store.transition_pass(
                "RUN-SELF-TEST",
                self.snapshot,
                replay_receipt=replace(replay, verdict="FAIL"),
                replay_verifier=self.evidence,
            )

    def test_blob_manifest_and_stale_snapshot_tampering_are_blocked(self):
        package = self._complete_package()
        blob = next(self.evidence.blobs.iterdir())
        blob.write_bytes(b"tampered")
        with self.assertRaisesRegex(EvidenceIntegrityError, "blob"):
            self.evidence.replay(
                package, ledger=self.ledger, holdout_store=self.holdout
            )

    def test_manifest_tamper_is_blocked(self):
        package = self._complete_package()
        manifest = self.evidence.packages / package.package_id / "manifest.json"
        value = json.loads(manifest.read_text(encoding="utf-8"))
        value["observations"]["positive_control"] = False
        manifest.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(EvidenceIntegrityError, "manifest hash"):
            self.evidence.replay(
                package, ledger=self.ledger, holdout_store=self.holdout
            )

    def test_replay_receipt_cannot_authorize_changed_snapshot(self):
        package = self._complete_package()
        replay = self.evidence.replay(
            package, ledger=self.ledger, holdout_store=self.holdout
        )
        changed = build_snapshot(
            executor_version="0.3.0",
            policy={"version": "changed"},
            project_contract={"project": "executor"},
            task_contract={"task": "self-test"},
            test_contract={"test": "EXECUTOR_SELF_TEST-001"},
            prompt_bundle={"prompt": "self-test"},
            model_id="ai-agent",
            repository_shas={"Executor": "a" * 40},
            inputs={"input": self.input},
            workspace=self.workspace,
        )
        with self.assertRaisesRegex(InvalidTransition, "stale"):
            self.run_store.transition_pass(
                "RUN-SELF-TEST",
                changed,
                replay_receipt=replay,
                replay_verifier=self.evidence,
            )

    def test_failed_action_or_failed_acceptance_cannot_replay(self):
        package = self._complete_package(result_status="FAILED")
        with self.assertRaisesRegex(EvidenceIntegrityError, "not successful"):
            self.evidence.replay(
                package, ledger=self.ledger, holdout_store=self.holdout
            )


if __name__ == "__main__":
    unittest.main()
