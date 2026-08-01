import json
import tempfile
import unittest
from pathlib import Path

from executor.checkpoints import build_snapshot
from executor.state_machine import InvalidTransition, RunIntegrityError, RunState, RunStore


class StateMachineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runs = self.root / "runs"
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        (self.workspace / "file.txt").write_text("one", encoding="utf-8")
        self.input = self.root / "input.json"
        self.input.write_text('{"value": 1}\n', encoding="utf-8")
        self.policy = {"version": "1"}
        self.project = {"project": "x"}
        self.task = {"task": "x"}
        self.test_contract = {"test": "x"}
        self.prompt = {"prompt": "x"}

    def tearDown(self):
        self.temp.cleanup()

    def snapshot(self, **changes):
        values = dict(
            executor_version="0.2.0",
            policy=self.policy,
            project_contract=self.project,
            task_contract=self.task,
            test_contract=self.test_contract,
            prompt_bundle=self.prompt,
            model_id="none",
            repository_shas={"target": "abc"},
            inputs={"input": self.input},
            workspace=self.workspace,
        )
        values.update(changes)
        return build_snapshot(**values)

    def create(self):
        store = RunStore(self.runs)
        run_id = store.create(self.snapshot(), run_id="RUN-TEST")
        return store, run_id

    def test_valid_transition(self):
        store, run_id = self.create()
        store.transition(run_id, RunState.CONTRACT_VALIDATED, self.snapshot(), reason="contracts pass")
        self.assertEqual(store.load_state(run_id)["state"], "CONTRACT_VALIDATED")

    def test_skip_transition_blocked(self):
        store, run_id = self.create()
        with self.assertRaises(InvalidTransition):
            store.transition(run_id, RunState.PLANNED, self.snapshot(), reason="skip")

    def test_terminal_state_is_immutable(self):
        store, run_id = self.create()
        store.transition(run_id, RunState.BLOCKED, self.snapshot(), reason="blocked")
        with self.assertRaises(InvalidTransition):
            store.transition(run_id, RunState.FAILED, self.snapshot(), reason="change terminal")

    def test_pass_requires_replaying(self):
        store, run_id = self.create()
        for state in (RunState.CONTRACT_VALIDATED, RunState.NORMALIZED, RunState.PLANNED, RunState.APPROVED, RunState.EXECUTING, RunState.VERIFYING):
            store.transition(run_id, state, self.snapshot(), reason=state.value)
        with self.assertRaises(InvalidTransition):
            store.transition(run_id, RunState.PASS, self.snapshot(), reason="premature pass")
        store.transition(run_id, RunState.REPLAYING, self.snapshot(), reason="replay started")
        store.transition(run_id, RunState.PASS, self.snapshot(), reason="replay verified")
        self.assertEqual(store.load_state(run_id)["state"], "PASS")

    def test_unchanged_resume(self):
        store, run_id = self.create()
        result = store.revalidate(run_id, self.snapshot())
        self.assertEqual(result.status, "UNCHANGED")
        self.assertEqual(store.load_state(run_id)["state"], "CREATED")

    def test_repository_sha_change_marks_stale(self):
        store, run_id = self.create()
        result = store.revalidate(run_id, self.snapshot(repository_shas={"target": "def"}))
        self.assertEqual(result.status, "STALE")
        self.assertIn("repository_shas", result.differences)
        self.assertEqual(store.load_state(run_id)["state"], "STALE")

    def test_contract_change_marks_stale(self):
        store, run_id = self.create()
        result = store.revalidate(run_id, self.snapshot(test_contract={"test": "changed"}))
        self.assertIn("test_contract_hash", result.differences)

    def test_policy_change_marks_stale(self):
        store, run_id = self.create()
        result = store.revalidate(run_id, self.snapshot(policy={"version": "2"}))
        self.assertIn("policy_hash", result.differences)

    def test_workspace_change_marks_stale(self):
        store, run_id = self.create()
        (self.workspace / "file.txt").write_text("two", encoding="utf-8")
        result = store.revalidate(run_id, self.snapshot())
        self.assertIn("workspace_hash", result.differences)

    def test_input_change_marks_stale(self):
        store, run_id = self.create()
        self.input.write_text('{"value": 2}\n', encoding="utf-8")
        result = store.revalidate(run_id, self.snapshot())
        self.assertIn("input_hashes", result.differences)

    def test_event_chain_verifies(self):
        store, run_id = self.create()
        store.transition(run_id, RunState.CONTRACT_VALIDATED, self.snapshot(), reason="ok")
        rows = store.events(run_id)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["previous_event_hash"], rows[0]["event_hash"])

    def test_event_tampering_detected(self):
        store, run_id = self.create()
        path = self.runs / run_id / "events.jsonl"
        row = json.loads(path.read_text().splitlines()[0])
        row["reason"] = "tampered"
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        with self.assertRaises(RunIntegrityError):
            store.events(run_id)

    def test_corrupt_state_detected(self):
        store, run_id = self.create()
        (self.runs / run_id / "state.json").write_text("{bad", encoding="utf-8")
        with self.assertRaises(RunIntegrityError):
            store.load_state(run_id)

    def test_atomic_checkpoint_exists(self):
        store, run_id = self.create()
        checkpoints = list((self.runs / run_id / "checkpoints").glob("*.json"))
        self.assertEqual(len(checkpoints), 1)
        self.assertFalse(list((self.runs / run_id).glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
