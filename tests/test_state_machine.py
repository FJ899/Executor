import json
import multiprocessing
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from executor.checkpoints import build_snapshot
from executor.hashing import hash_json
from executor.state_machine import InvalidTransition, RunIntegrityError, RunState, RunStore


class PhaseFailureRunStore(RunStore):
    def __init__(self, runs_root, fail_after):
        super().__init__(runs_root)
        self.fail_after = fail_after

    def _after_persist_phase(self, phase, event):
        if event.sequence > 1 and phase == self.fail_after:
            raise OSError(f"injected failure after {phase}")


def transition_in_process(runs_root, run_id, snapshot, barrier, results):
    try:
        barrier.wait(timeout=10)
        RunStore(runs_root).transition(
            run_id,
            RunState.CONTRACT_VALIDATED,
            snapshot,
            reason="concurrent process",
        )
        results.put("committed")
    except InvalidTransition:
        results.put("rejected")
    except BaseException as exc:
        results.put(f"error:{type(exc).__name__}:{exc}")


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

    def create(self, run_id="RUN-TEST"):
        store = RunStore(self.runs)
        store.create(self.snapshot(), run_id=run_id)
        return store, run_id

    def write_event_rows(self, run_id, rows):
        content = "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        )
        (self.runs / run_id / "events.jsonl").write_text(content, encoding="utf-8")

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

    def test_pass_remains_blocked_after_replaying(self):
        store, run_id = self.create()
        for state in (
            RunState.CONTRACT_VALIDATED,
            RunState.NORMALIZED,
            RunState.PLANNED,
            RunState.APPROVED,
            RunState.EXECUTING,
            RunState.VERIFYING,
            RunState.REPLAYING,
        ):
            store.transition(run_id, state, self.snapshot(), reason=state.value)
        with self.assertRaisesRegex(InvalidTransition, "M3 replay gate"):
            store.transition(run_id, RunState.PASS, self.snapshot(), reason="replay verified")
        self.assertEqual(store.load_state(run_id)["state"], "REPLAYING")

    def test_direct_pass_is_blocked(self):
        store, run_id = self.create()
        with self.assertRaisesRegex(InvalidTransition, "M3 replay gate"):
            store.transition(run_id, RunState.PASS, self.snapshot(), reason="premature pass")
        self.assertEqual(store.load_state(run_id)["state"], "CREATED")

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
        self.write_event_rows(run_id, [row])
        with self.assertRaises(RunIntegrityError):
            store.events(run_id)

    def test_previous_state_must_match_preceding_event(self):
        store, run_id = self.create()
        store.transition(run_id, RunState.CONTRACT_VALIDATED, self.snapshot(), reason="ok")
        rows = store.events(run_id)
        rows[1]["previous_state"] = "PLANNED"
        body = {key: value for key, value in rows[1].items() if key != "event_hash"}
        rows[1]["event_hash"] = hash_json(body)
        self.write_event_rows(run_id, rows)
        checkpoint = self.runs / run_id / "checkpoints" / "0002-CONTRACT_VALIDATED.json"
        checkpoint.write_text(json.dumps(rows[1]), encoding="utf-8")
        state_path = self.runs / run_id / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["event_hash"] = rows[1]["event_hash"]
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(RunIntegrityError, "previous_state"):
            store.load_state(run_id)

    def test_state_must_match_last_verified_event(self):
        store, run_id = self.create()
        state_path = self.runs / run_id / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["sequence"] = 99
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(RunIntegrityError, "last verified event"):
            store.load_state(run_id)

    def test_tampered_state_cannot_fabricate_replaying_or_pass(self):
        store, run_id = self.create()
        state_path = self.runs / run_id / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["state"] = "REPLAYING"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(RunIntegrityError):
            store.transition(run_id, RunState.PASS, self.snapshot(), reason="fabricated replay")

    def test_tampered_state_cannot_suppress_stale(self):
        store, run_id = self.create()
        (self.workspace / "file.txt").write_text("changed", encoding="utf-8")
        changed = self.snapshot()
        state_path = self.runs / run_id / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["snapshot"] = changed.to_dict()
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(RunIntegrityError):
            store.revalidate(run_id, changed)

    def test_corrupt_state_detected(self):
        store, run_id = self.create()
        (self.runs / run_id / "state.json").write_text("{bad", encoding="utf-8")
        with self.assertRaises(RunIntegrityError):
            store.load_state(run_id)

    def test_changed_missing_and_malformed_checkpoints_are_blocked(self):
        damage_cases = ("changed", "missing", "malformed")
        for damage in damage_cases:
            with self.subTest(damage=damage):
                run_id = f"RUN-CHECKPOINT-{damage.upper()}"
                store, _ = self.create(run_id)
                checkpoint = self.runs / run_id / "checkpoints" / "0001-CREATED.json"
                if damage == "changed":
                    value = json.loads(checkpoint.read_text(encoding="utf-8"))
                    value["reason"] = "tampered"
                    checkpoint.write_text(json.dumps(value), encoding="utf-8")
                elif damage == "missing":
                    checkpoint.unlink()
                else:
                    checkpoint.write_text("{bad", encoding="utf-8")
                with self.assertRaises(RunIntegrityError):
                    store.load_state(run_id)

    def test_atomic_checkpoint_exists(self):
        _, run_id = self.create()
        checkpoints = list((self.runs / run_id / "checkpoints").glob("*.json"))
        self.assertEqual(len(checkpoints), 1)
        self.assertFalse(list((self.runs / run_id).glob("*.tmp")))
        self.assertFalse((self.runs / run_id / ".transaction.json").exists())

    def test_invalid_run_ids_are_rejected_before_file_creation(self):
        store = RunStore(self.runs)
        invalid_ids = (
            "../escaped-run",
            "RUN/ESCAPE",
            r"RUN\ESCAPE",
            "/absolute-run",
            ".",
            "..",
            "RUN.WITH.DOTS",
            "X" * 129,
        )
        for run_id in invalid_ids:
            with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                store.create(self.snapshot(), run_id=run_id)
        self.assertFalse((self.root / "escaped-run").exists())

    def test_run_directory_symlink_escape_is_rejected(self):
        self.runs.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (self.runs / "RUN-LINK").symlink_to(outside, target_is_directory=True)
        store = RunStore(self.runs)
        with self.assertRaises(RunIntegrityError):
            store.create(self.snapshot(), run_id="RUN-LINK")
        self.assertEqual(list(outside.iterdir()), [])

    def test_failure_after_each_persist_phase_rolls_back(self):
        for phase in ("journal", "checkpoint", "events", "state"):
            with self.subTest(phase=phase):
                run_id = f"RUN-FAIL-{phase.upper()}"
                base_store, _ = self.create(run_id)
                failing_store = PhaseFailureRunStore(self.runs, phase)
                with self.assertRaisesRegex(OSError, phase):
                    failing_store.transition(
                        run_id,
                        RunState.CONTRACT_VALIDATED,
                        self.snapshot(),
                        reason="injected",
                    )
                self.assertEqual(base_store.load_state(run_id)["state"], "CREATED")
                self.assertEqual(len(base_store.events(run_id)), 1)
                checkpoints = list((self.runs / run_id / "checkpoints").glob("*.json"))
                self.assertEqual([path.name for path in checkpoints], ["0001-CREATED.json"])
                self.assertFalse((self.runs / run_id / ".transaction.json").exists())

    def test_failure_before_journal_write_leaves_previous_state(self):
        store, run_id = self.create()
        with patch("executor.state_machine.atomic_write_json", side_effect=OSError("journal write failed")):
            with self.assertRaisesRegex(OSError, "journal write failed"):
                store.transition(
                    run_id,
                    RunState.CONTRACT_VALIDATED,
                    self.snapshot(),
                    reason="injected",
                )
        self.assertEqual(store.load_state(run_id)["state"], "CREATED")
        self.assertEqual(len(store.events(run_id)), 1)

    def test_forged_journal_cannot_roll_back_committed_terminal_state(self):
        for terminal_state in (RunState.STALE, RunState.BLOCKED):
            with self.subTest(terminal_state=terminal_state):
                run_id = f"RUN-FORGED-{terminal_state.value}"
                store, _ = self.create(run_id)
                if terminal_state == RunState.STALE:
                    (self.workspace / "file.txt").write_text("changed", encoding="utf-8")
                    terminal_snapshot = self.snapshot()
                    self.assertEqual(store.revalidate(run_id, terminal_snapshot).status, "STALE")
                else:
                    terminal_snapshot = self.snapshot()
                    store.transition(run_id, terminal_state, terminal_snapshot, reason="blocked")

                run_dir = self.runs / run_id
                rows = store.events(run_id)
                state_before = (run_dir / "state.json").read_bytes()
                events_before = (run_dir / "events.jsonl").read_bytes()
                transaction_body = {
                    "version": 1,
                    "run_id": run_id,
                    "previous_events": rows[:-1],
                    "event": rows[-1],
                }
                transaction = {
                    **transaction_body,
                    "transaction_hash": hash_json(transaction_body),
                }
                (run_dir / ".transaction.json").write_text(
                    json.dumps(transaction, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(RunIntegrityError, "cannot be authenticated after restart"):
                    store.load_state(run_id)
                with self.assertRaisesRegex(RunIntegrityError, "cannot be authenticated after restart"):
                    store.transition(
                        run_id,
                        RunState.CONTRACT_VALIDATED,
                        terminal_snapshot,
                        reason="must remain blocked",
                    )
                self.assertEqual((run_dir / "state.json").read_bytes(), state_before)
                self.assertEqual((run_dir / "events.jsonl").read_bytes(), events_before)
                self.assertTrue((run_dir / ".transaction.json").exists())

    def test_two_concurrent_transitions_cannot_commit_the_same_sequence(self):
        store, run_id = self.create()
        barrier = threading.Barrier(2)

        def transition_once():
            barrier.wait()
            try:
                RunStore(self.runs).transition(
                    run_id,
                    RunState.CONTRACT_VALIDATED,
                    self.snapshot(),
                    reason="concurrent",
                )
                return "committed"
            except InvalidTransition:
                return "rejected"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = sorted(pool.map(lambda _: transition_once(), range(2)))
        self.assertEqual(outcomes, ["committed", "rejected"])
        self.assertEqual(store.load_state(run_id)["state"], "CONTRACT_VALIDATED")
        rows = store.events(run_id)
        self.assertEqual([row["sequence"] for row in rows], [1, 2])
        self.assertEqual(len(list((self.runs / run_id / "checkpoints").glob("*.json"))), 2)

    @unittest.skipUnless(os.name == "posix", "inter-process lock uses POSIX flock")
    def test_two_processes_cannot_commit_the_same_sequence(self):
        store, run_id = self.create()
        context = multiprocessing.get_context("spawn")
        barrier = context.Barrier(2)
        results = context.Queue()
        snapshot = self.snapshot()
        processes = [
            context.Process(
                target=transition_in_process,
                args=(self.runs, run_id, snapshot, barrier, results),
            )
            for _ in range(2)
        ]
        try:
            for process in processes:
                process.start()
            for process in processes:
                process.join(timeout=15)
            self.assertTrue(all(not process.is_alive() for process in processes))
            self.assertTrue(all(process.exitcode == 0 for process in processes))
            outcomes = sorted(results.get(timeout=2) for _ in processes)
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)
                process.close()
            results.close()
        self.assertEqual(outcomes, ["committed", "rejected"])
        self.assertEqual(store.load_state(run_id)["state"], "CONTRACT_VALIDATED")
        self.assertEqual([row["sequence"] for row in store.events(run_id)], [1, 2])


if __name__ == "__main__":
    unittest.main()
