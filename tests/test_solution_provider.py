from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from executor.github_trust import verify_github_decision, verify_github_request
from executor.pilot_contract import apply_github_decision, build_pilot_draft, pilot_draft_sha256
from executor.solution_provider import SolutionProvider, SolutionProviderError
from tests.p4_test_support import governed_ledger
from tests.test_github_trust import (
    COMMENT_URL,
    ISSUE_URL,
    NOW,
    FakeSource,
    comment,
    commit_evidence,
    commit_url,
    decision_payload,
    issue,
    profile,
    request_payload,
)


SOURCE_PATH = "phase6/scriptops-v2-hardening.py"
SOURCE_TEXT = "VALUE = 1\n"
REPLACEMENT_TEXT = "VALUE = 2\n"


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.stdout.strip()


class FakeGenerator:
    provider = "OpenAI"
    model = "GPT-5.6 Sol"

    def __init__(self, generation: dict | None = None) -> None:
        self.generation = generation or {
            "schema_version": "executor-solution-generation/1.0",
            "mutations": [
                {
                    "path": SOURCE_PATH,
                    "replacement_text": REPLACEMENT_TEXT,
                }
            ],
            "rationale": "Replace the bounded source with the corrected implementation.",
        }
        self.calls = 0
        self.last_prompt = None

    def generate(self, prompt):
        self.calls += 1
        self.last_prompt = copy.deepcopy(prompt)
        return copy.deepcopy(self.generation)


class SolutionProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.repo = base / "repo"
        self.repo.mkdir()
        _git(self.repo, "init")
        _git(self.repo, "config", "user.email", "tests@example.invalid")
        _git(self.repo, "config", "user.name", "Executor Tests")
        _git(self.repo, "remote", "add", "origin", "https://github.com/FJ899/scriptops.git")
        source = self.repo / SOURCE_PATH
        source.parent.mkdir(parents=True)
        source.write_text(SOURCE_TEXT, encoding="utf-8")
        _git(self.repo, "add", SOURCE_PATH)
        _git(self.repo, "commit", "-m", "fixture")
        self.commit = _git(self.repo, "rev-parse", "HEAD")
        self.tree = _git(self.repo, "rev-parse", "HEAD^{tree}")
        self.frozen = self._build_frozen(base / "ledger.sqlite3")

    def _build_frozen(self, ledger_path: Path):
        payload = request_payload()
        payload["target"]["commit"] = self.commit
        payload["target"]["tree"] = self.tree
        source = FakeSource(
            {
                ISSUE_URL: issue(json.dumps(payload, sort_keys=True)),
                commit_url(payload): commit_evidence(payload),
            }
        )
        request = verify_github_request(
            source,
            profile=profile(),
            issue_number=61,
            now=NOW,
        )
        draft = build_pilot_draft(request)
        draft_sha = pilot_draft_sha256(draft)
        source.values[COMMENT_URL] = comment(decision_payload(request, draft_sha))
        decision = verify_github_decision(
            source,
            profile=profile(),
            request=request,
            comment_id=9001,
            draft_sha256=draft_sha,
            now=NOW,
        )
        with patch("executor.pilot_contract._utc_now", return_value=NOW):
            return apply_github_decision(
                draft=draft,
                decision=decision,
                source=source,
                profile=profile(),
                ledger=governed_ledger(ledger_path),
            )

    def test_frozen_contract_to_validated_solution_proposal(self):
        generator = FakeGenerator()
        provider = SolutionProvider(generator)
        with patch(
            "executor.solution_provider._utc_now",
            return_value=NOW + timedelta(seconds=1),
        ):
            result = provider.provide(
                frozen_result=self.frozen,
                checkout_root=self.repo,
            )

        self.assertEqual(result.to_dict()["status"], "VALIDATED_SOLUTION_PROPOSAL")
        self.assertEqual(result.to_dict()["effect_capability"], "NONE")
        self.assertEqual(result.validated.contract_sha256, self.frozen["contract_sha256"])
        self.assertEqual(result.validated.repository, "FJ899/scriptops")
        self.assertEqual(result.validated.source_commit, self.commit)
        self.assertEqual(result.validated.source_tree, self.tree)
        self.assertEqual(len(result.validated.mutations), 1)
        mutation = result.validated.mutations[0]
        self.assertEqual(mutation.path, SOURCE_PATH)
        self.assertEqual(
            mutation.expected_before_sha256,
            hashlib.sha256(SOURCE_TEXT.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            mutation.expected_after_sha256,
            hashlib.sha256(REPLACEMENT_TEXT.encode("utf-8")).hexdigest(),
        )
        provenance = result.validated.provenance
        self.assertEqual(provenance["schema_version"], "executor-solution-provenance/1.1")
        self.assertEqual(
            provenance["frozen_contract_sha256"], self.frozen["contract_sha256"]
        )
        self.assertEqual(provenance["context_sha256"], result.context_sha256)
        self.assertEqual(provenance["prompt_sha256"], result.prompt_sha256)
        self.assertEqual(provenance["effect_capability"], "NONE")
        self.assertEqual(provenance["human_solution_edits"], 0)
        self.assertEqual(generator.calls, 1)
        self.assertEqual(
            generator.last_prompt["source_context"]["files"][0]["text"],
            SOURCE_TEXT,
        )
        self.assertEqual(
            generator.last_prompt["source_context"]["allowed_paths"],
            [SOURCE_PATH],
        )

    def test_scope_expansion_is_blocked_before_materialization(self):
        generator = FakeGenerator(
            {
                "schema_version": "executor-solution-generation/1.0",
                "mutations": [
                    {
                        "path": "tests/test_escape.py",
                        "replacement_text": "raise AssertionError\n",
                    }
                ],
                "rationale": "Attempt to change protected material.",
            }
        )
        with patch(
            "executor.solution_provider._utc_now",
            return_value=NOW + timedelta(seconds=1),
        ):
            with self.assertRaisesRegex(SolutionProviderError, "scope expansion"):
                SolutionProvider(generator).provide(
                    frozen_result=self.frozen,
                    checkout_root=self.repo,
                )

    def test_dirty_allowed_source_is_blocked_before_generator(self):
        generator = FakeGenerator()
        (self.repo / SOURCE_PATH).write_text("VALUE = 999\n", encoding="utf-8")
        with self.assertRaisesRegex(SolutionProviderError, "stale or differs"):
            SolutionProvider(generator).provide(
                frozen_result=self.frozen,
                checkout_root=self.repo,
            )
        self.assertEqual(generator.calls, 0)

    def test_wrong_repository_identity_is_blocked_before_generator(self):
        generator = FakeGenerator()
        _git(
            self.repo,
            "remote",
            "set-url",
            "origin",
            "https://github.com/FJ899/other-repository.git",
        )
        with self.assertRaisesRegex(SolutionProviderError, "identity mismatch"):
            SolutionProvider(generator).provide(
                frozen_result=self.frozen,
                checkout_root=self.repo,
            )
        self.assertEqual(generator.calls, 0)

    def test_generator_cannot_supply_hash_or_effect_metadata(self):
        generator = FakeGenerator(
            {
                "schema_version": "executor-solution-generation/1.0",
                "mutations": [
                    {
                        "path": SOURCE_PATH,
                        "replacement_text": REPLACEMENT_TEXT,
                        "expected_before_sha256": "0" * 64,
                    }
                ],
                "rationale": "Attempt to control Executor-owned binding.",
            }
        )
        with self.assertRaisesRegex(SolutionProviderError, "mutation 0 is malformed"):
            SolutionProvider(generator).provide(
                frozen_result=self.frozen,
                checkout_root=self.repo,
            )

    def test_generation_must_postdate_frozen_contract(self):
        generator = FakeGenerator()
        with patch("executor.solution_provider._utc_now", return_value=NOW):
            with self.assertRaisesRegex(SolutionProviderError, "postdate"):
                SolutionProvider(generator).provide(
                    frozen_result=self.frozen,
                    checkout_root=self.repo,
                )


if __name__ == "__main__":
    unittest.main()
