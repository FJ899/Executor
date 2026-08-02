import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from executor.m3.holdout import HoldoutIntegrityError, IndependentHoldoutStore


class IndependentHoldoutStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.verifier_root = self.root / "verifier"
        self.workspace.mkdir(mode=0o700)
        self.verifier_root.mkdir(mode=0o700)
        self.key = b"k" * 32
        self.store = IndependentHoldoutStore(
            self.verifier_root,
            implementer_workspace=self.workspace,
            verifier_id="independent-verifier",
            verifier_key_id="key-1",
            authentication_key=self.key,
        )

    def tearDown(self):
        self.temp.cleanup()

    def payload(self, expected=True):
        return json.dumps(
            {
                "schema_version": "executor-independent-holdout/1.0",
                "test_id": "EXECUTOR_SELF_TEST-001",
                "assertions": [
                    {"selector": "$.result.ok", "operator": "==", "expected": expected}
                ],
            },
            sort_keys=True,
        ).encode()

    def test_root_must_be_private_and_outside_workspace(self):
        inside = self.workspace / "verifier"
        inside.mkdir(mode=0o700)
        with self.assertRaisesRegex(HoldoutIntegrityError, "independent"):
            IndependentHoldoutStore(
                inside,
                implementer_workspace=self.workspace,
                verifier_id="v",
                verifier_key_id="k",
                authentication_key=self.key,
            )
        broad = self.root / "broad"
        broad.mkdir(mode=0o755)
        os.chmod(broad, 0o755)
        with self.assertRaisesRegex(HoldoutIntegrityError, "group or other"):
            IndependentHoldoutStore(
                broad,
                implementer_workspace=self.workspace,
                verifier_id="v",
                verifier_key_id="k",
                authentication_key=self.key,
            )

    def test_provision_is_immutable_authenticated_and_does_not_return_plaintext(self):
        receipt = self.store.provision(
            test_id="EXECUTOR_SELF_TEST-001", holdout_payload=self.payload()
        )
        self.assertTrue(self.store.verify_receipt(receipt))
        self.assertNotIn("assertions", receipt.to_dict())
        self.assertNotIn("expected", receipt.to_dict())
        same = self.store.provision(
            test_id="EXECUTOR_SELF_TEST-001", holdout_payload=self.payload()
        )
        self.assertEqual(same.holdout_id, receipt.holdout_id)
        with self.assertRaisesRegex(HoldoutIntegrityError, "immutable"):
            self.store.provision(
                test_id="EXECUTOR_SELF_TEST-001", holdout_payload=self.payload(False)
            )

    def test_replay_binds_candidate_and_authenticates_pass_and_fail(self):
        provision = self.store.provision(
            test_id="EXECUTOR_SELF_TEST-001", holdout_payload=self.payload()
        )
        passed = self.store.replay(
            test_id="EXECUTOR_SELF_TEST-001",
            holdout_id=provision.holdout_id,
            candidate_result={"result": {"ok": True}},
        )
        failed = self.store.replay(
            test_id="EXECUTOR_SELF_TEST-001",
            holdout_id=provision.holdout_id,
            candidate_result={"result": {"ok": False}},
        )
        self.assertEqual(passed.verdict, "PASS")
        self.assertEqual(failed.verdict, "FAIL")
        self.assertNotEqual(passed.candidate_result_sha256, failed.candidate_result_sha256)
        self.assertTrue(self.store.verify_receipt(passed))
        self.assertTrue(self.store.verify_receipt(failed))

    def test_tamper_and_wrong_binding_are_blocked(self):
        provision = self.store.provision(
            test_id="EXECUTOR_SELF_TEST-001", holdout_payload=self.payload()
        )
        replay = self.store.replay(
            test_id="EXECUTOR_SELF_TEST-001",
            holdout_id=provision.holdout_id,
            candidate_result={"result": {"ok": True}},
        )
        self.assertFalse(self.store.verify_receipt(replace(replay, verdict="FAIL")))
        with self.assertRaisesRegex(HoldoutIntegrityError, "Unknown"):
            self.store.replay(
                test_id="WRONG",
                holdout_id=provision.holdout_id,
                candidate_result={"result": {"ok": True}},
            )

    def test_malformed_duplicate_and_wrong_test_holdouts_are_blocked(self):
        cases = (
            b"{bad",
            b'{"schema_version":"executor-independent-holdout/1.0","test_id":"EXECUTOR_SELF_TEST-001","test_id":"X","assertions":[]}',
            json.dumps(
                {
                    "schema_version": "executor-independent-holdout/1.0",
                    "test_id": "WRONG",
                    "assertions": [{"selector": "$", "operator": "==", "expected": {}}],
                }
            ).encode(),
        )
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(HoldoutIntegrityError):
                self.store.provision(
                    test_id="EXECUTOR_SELF_TEST-001", holdout_payload=payload
                )


if __name__ == "__main__":
    unittest.main()
