from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from executor.authority_ledger import AtomicAuthorityLedger, AuthorityReplayError
from executor.github_trust import verify_github_decision, verify_github_request
from executor.pilot_contract import (
    apply_github_decision,
    build_pilot_draft,
    pilot_draft_sha256,
)
from executor.pilot_runtime import (
    PilotDockerSandboxBackend,
    PilotRuntime,
    build_pilot_sandbox_spec,
)
from executor.sandbox.policy_snapshot import load_execution_policy_snapshot
from executor.sandbox.spec import SandboxExecutionContext, SandboxResult
from executor.solution_proposal import validate_solution_proposal
from tests.test_github_trust import (
    COMMENT_URL,
    ISSUE_URL,
    FakeSource,
    NOW,
    comment,
    commit_evidence,
    commit_url,
    decision_payload,
    issue,
    profile,
    request_payload,
)


class SequenceBackend:
    def __init__(self, exit_codes):
        self.exit_codes = list(exit_codes)
        self.calls = []

    def run(self, *, spec, context, output_dir, argv, container_name=None):
        del spec, container_name
        self.calls.append((context, list(argv)))
        exit_code = self.exit_codes.pop(0)
        return SandboxResult(
            container_name="fake",
            execution_id=f"{len(self.calls):032x}",
            policy_sha256="b" * 64,
            argv=tuple(argv),
            exit_code=exit_code,
            stdout="ok\n" if exit_code == 0 else "",
            stderr="counterexample\n" if exit_code else "",
            timed_out=False,
            duration_seconds=0.01,
            output_dir=Path(output_dir),
            cleanup_verified=True,
        )


class PilotFixture:
    def __init__(self, root):
        self.root = root
        root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Pilot Test")
        self.git("config", "user.email", "pilot@example.invalid")
        self.git("remote", "add", "origin", "https://github.com/JTJ07/scriptops.git")
        (root / "phase6").mkdir()
        (root / "phase6/scriptops-v2-hardening.py").write_text(
            "VALUE = 1\n",
            encoding="utf-8",
        )
        self.git("add", ".")
        self.git("commit", "-q", "-m", "pilot input")
        self.commit = self.git("rev-parse", "HEAD").stdout.strip()
        self.tree = self.git("rev-parse", "HEAD^{tree}").stdout.strip()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            text=True,
            capture_output=True,
            check=True,
        )


class PilotRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.fixture = PilotFixture(root / "workspace")
        payload = request_payload()
        payload["target"]["commit"] = self.fixture.commit
        payload["target"]["tree"] = self.fixture.tree
        source = FakeSource(
            {
                ISSUE_URL: issue(json.dumps(payload, sort_keys=True)),
                commit_url(payload): commit_evidence(payload),
            }
        )
        self.request = verify_github_request(
            source,
            profile=profile(),
            issue_number=61,
            now=NOW,
        )
        draft = build_pilot_draft(self.request)
        source.values[COMMENT_URL] = comment(
            decision_payload(self.request, pilot_draft_sha256(draft))
        )
        self.decision = verify_github_decision(
            source,
            profile=profile(),
            request=self.request,
            comment_id=9001,
            draft_sha256=pilot_draft_sha256(draft),
            now=NOW,
        )
        self.ledger_path = root / "authority.sqlite3"
        self.frozen = apply_github_decision(
            draft=draft,
            decision=self.decision,
            ledger=AtomicAuthorityLedger(self.ledger_path),
        )
        before = (self.fixture.root / "phase6/scriptops-v2-hardening.py").read_bytes()
        replacement = "VALUE = 2\n"
        proposal = {
            "schema_version": "executor-solution-proposal/1.0",
            "proposal_id": "proposal-runtime-001",
            "contract_sha256": self.frozen["contract_sha256"],
            "repository": "JTJ07/scriptops",
            "source_commit": self.fixture.commit,
            "source_tree": self.fixture.tree,
            "mutations": [
                {
                    "path": "phase6/scriptops-v2-hardening.py",
                    "expected_before_sha256": hashlib.sha256(before).hexdigest(),
                    "replacement_text": replacement,
                    "expected_after_sha256": hashlib.sha256(
                        replacement.encode()
                    ).hexdigest(),
                }
            ],
            "rationale": "Repair the observed counterexample.",
            "evidence_plan": [
                ["python", "-c", "raise SystemExit(0)"],
                ["python", "-m", "unittest", "discover", "-s", "tests"],
            ],
        }
        self.validated = validate_solution_proposal(
            proposal,
            frozen_result=self.frozen,
        )
        self.root = root

    def tearDown(self):
        self.temp.cleanup()

    def runtime(self, exit_codes):
        runtime = object.__new__(PilotRuntime)
        runtime.executor_commit = "e" * 40
        runtime.policy_snapshot = SimpleNamespace(
            source_sha256="b" * 64,
            bounded_pilot_repositories=(
                SimpleNamespace(repository="JTJ07/scriptops"),
                SimpleNamespace(repository="JTJ07/creative-os-project-reconstructor"),
            ),
        )
        runtime.contract = self.frozen["contract"]
        runtime.contract_sha256 = self.frozen["contract_sha256"]
        runtime.proposal = self.validated
        runtime.verified_request = self.request
        runtime.verified_decision = self.decision
        runtime.ledger = AtomicAuthorityLedger(self.ledger_path)
        runtime.runs_root = self.root / "runs"
        runtime.backend = SequenceBackend(exit_codes)
        runtime.spec = build_pilot_sandbox_spec(
            runtime.contract,
            "sha256:" + "1" * 64,
        )
        return runtime

    def test_observed_failure_then_fix_produces_review_required_draft_request(self):
        runtime = self.runtime([1, 0, 0])
        report = runtime.execute(
            workspace=self.fixture.root,
            run_id="pilot-runtime-001",
            now=NOW,
        )
        self.assertEqual(report["status"], "ACTION_COMPLETED_REVIEW_REQUIRED")
        self.assertEqual(
            report["changed_paths"],
            ["phase6/scriptops-v2-hardening.py"],
        )
        self.assertTrue(report["human_review_required"])
        self.assertFalse(report["merge_allowed"])
        self.assertTrue(report["draft_pr_request"]["draft"])
        self.assertFalse(report["draft_pr_request"]["merge_allowed"])
        self.assertEqual(report["authority_consumption"]["state"], "FINAL")
        self.assertEqual(
            AtomicAuthorityLedger(self.ledger_path).unresolved(),
            (),
        )
        persisted = json.loads(Path(report["report_path"]).read_text())
        self.assertIn("draft_pr_request", persisted)

    def test_green_precondition_blocks_before_effect_authority(self):
        runtime = self.runtime([0])
        report = runtime.execute(
            workspace=self.fixture.root,
            run_id="pilot-green-001",
            now=NOW,
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("counterexample is not observable", report["error"])
        self.assertNotIn("authority_consumption", report)
        self.assertEqual(
            (self.fixture.root / "phase6/scriptops-v2-hardening.py").read_text(),
            "VALUE = 1\n",
        )

    def test_same_exact_action_authority_cannot_be_consumed_twice(self):
        runtime = self.runtime([])
        runtime._authorize_action(run_id="pilot-replay-001", now=NOW)
        with self.assertRaises(AuthorityReplayError):
            runtime._authorize_action(run_id="pilot-replay-001", now=NOW)

    def test_real_policy_authorizes_only_the_bound_pilot_checkout(self):
        executor_root = Path(__file__).resolve().parents[1]
        executor_commit = subprocess.run(
            ["git", "-C", str(executor_root), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        policy = load_execution_policy_snapshot(
            executor_root,
            commit=executor_commit,
        )
        backend = PilotDockerSandboxBackend(
            policy_snapshot=policy,
            contract=self.frozen["contract"],
        )
        backend.bind_proposal(self.validated)
        authorized = backend.authorize(
            SandboxExecutionContext(
                repository="JTJ07/scriptops",
                commit=self.fixture.commit,
                repository_root=self.fixture.root,
                source_dir=self.fixture.root,
                purpose="PILOT_PRECHANGE",
            )
        )
        self.assertEqual(authorized, self.fixture.root.resolve())


if __name__ == "__main__":
    unittest.main()
