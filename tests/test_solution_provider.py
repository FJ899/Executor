from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from executor.github_trust import canonical_json, verify_github_decision, verify_github_request
from executor.pilot_contract import apply_github_decision, build_pilot_draft, pilot_draft_sha256
from executor.solution_provider import (
    SolutionProvider,
    SolutionProviderError,
    VerifiedGenerationEvidence,
)
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
from unittest.mock import patch


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


def _response_sha256(generation: dict) -> str:
    payload = {
        "schema_version": generation["schema_version"],
        "mutations": copy.deepcopy(generation["mutations"]),
        "rationale": generation["rationale"],
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


class FakeGenerationVerifier:
    def __init__(self) -> None:
        self.records: dict[str, VerifiedGenerationEvidence] = {}
        self.calls: list[str] = []

    def publish(self, *, prompt: dict, generation: dict, provider: str, model: str, generated_at: str):
        source = prompt["source_context"]
        evidence_ref = generation["evidence_ref"]
        self.records[evidence_ref] = VerifiedGenerationEvidence(
            evidence_ref=evidence_ref,
            provider=provider,
            model=model,
            generated_at=generated_at,
            frozen_contract_sha256=prompt["frozen_contract_sha256"],
            repository=source["repository"],
            commit=source["commit"],
            tree=source["tree"],
            context_sha256=source["context_sha256"],
            prompt_sha256=hashlib.sha256(canonical_json(prompt).encode("utf-8")).hexdigest(),
            response_sha256=_response_sha256(generation),
            verification_method="FAKE_PROVIDER_RECORD_LOOKUP",
        )

    def verify(self, evidence_ref: str) -> VerifiedGenerationEvidence:
        self.calls.append(evidence_ref)
        if evidence_ref not in self.records:
            raise KeyError(evidence_ref)
        return self.records[evidence_ref]


class FakeGenerator:
    provider = "OpenAI"
    model = "GPT-5.6 Sol"

    def __init__(
        self,
        verifier: FakeGenerationVerifier,
        generation: dict | None = None,
        *,
        generated_at: str | None = None,
        publish_evidence: bool = True,
    ) -> None:
        self.verifier = verifier
        self.generation = generation or {
            "schema_version": "executor-solution-generation/1.1",
            "evidence_ref": "provider-generation:current",
            "mutations": [
                {
                    "path": SOURCE_PATH,
                    "replacement_text": REPLACEMENT_TEXT,
                }
            ],
            "rationale": "Replace the bounded source with the corrected implementation.",
        }
        self.generated_at = generated_at or (NOW + timedelta(seconds=1)).isoformat().replace(
            "+00:00", "Z"
        )
        self.publish_evidence = publish_evidence
        self.calls = 0
        self.last_prompt = None

    def generate(self, prompt):
        self.calls += 1
        self.last_prompt = copy.deepcopy(prompt)
        generation = copy.deepcopy(self.generation)
        if self.publish_evidence:
            self.verifier.publish(
                prompt=prompt,
                generation=generation,
                provider=self.provider,
                model=self.model,
                generated_at=self.generated_at,
            )
        return generation


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
        verifier = FakeGenerationVerifier()
        generator = FakeGenerator(verifier)
        result = SolutionProvider(generator, verifier).provide(
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
        self.assertEqual(provenance["schema_version"], "executor-solution-provenance/1.2")
        self.assertEqual(
            provenance["frozen_contract_sha256"], self.frozen["contract_sha256"]
        )
        self.assertEqual(provenance["context_sha256"], result.context_sha256)
        self.assertEqual(provenance["prompt_sha256"], result.prompt_sha256)
        self.assertEqual(provenance["generation_evidence_ref"], result.generation_evidence_ref)
        self.assertEqual(
            provenance["generation_response_sha256"], result.generation_response_sha256
        )
        self.assertEqual(
            provenance["generation_verification_method"], "FAKE_PROVIDER_RECORD_LOOKUP"
        )
        self.assertEqual(provenance["effect_capability"], "NONE")
        self.assertEqual(provenance["human_solution_edits"], 0)
        self.assertEqual(generator.calls, 1)
        self.assertEqual(verifier.calls, ["provider-generation:current"])
        self.assertEqual(
            generator.last_prompt["source_context"]["files"][0]["text"],
            SOURCE_TEXT,
        )
        self.assertEqual(
            generator.last_prompt["source_context"]["allowed_paths"],
            [SOURCE_PATH],
        )

    def test_scope_expansion_is_blocked_before_materialization(self):
        verifier = FakeGenerationVerifier()
        generator = FakeGenerator(
            verifier,
            {
                "schema_version": "executor-solution-generation/1.1",
                "evidence_ref": "provider-generation:scope-escape",
                "mutations": [
                    {
                        "path": "tests/test_escape.py",
                        "replacement_text": "raise AssertionError\n",
                    }
                ],
                "rationale": "Attempt to change protected material.",
            },
        )
        with self.assertRaisesRegex(SolutionProviderError, "scope expansion"):
            SolutionProvider(generator, verifier).provide(
                frozen_result=self.frozen,
                checkout_root=self.repo,
            )

    def test_dirty_allowed_source_is_blocked_before_generator(self):
        verifier = FakeGenerationVerifier()
        generator = FakeGenerator(verifier)
        (self.repo / SOURCE_PATH).write_text("VALUE = 999\n", encoding="utf-8")
        with self.assertRaisesRegex(SolutionProviderError, "stale or differs"):
            SolutionProvider(generator, verifier).provide(
                frozen_result=self.frozen,
                checkout_root=self.repo,
            )
        self.assertEqual(generator.calls, 0)

    def test_wrong_repository_identity_is_blocked_before_generator(self):
        verifier = FakeGenerationVerifier()
        generator = FakeGenerator(verifier)
        _git(
            self.repo,
            "remote",
            "set-url",
            "origin",
            "https://github.com/FJ899/other-repository.git",
        )
        with self.assertRaisesRegex(SolutionProviderError, "identity mismatch"):
            SolutionProvider(generator, verifier).provide(
                frozen_result=self.frozen,
                checkout_root=self.repo,
            )
        self.assertEqual(generator.calls, 0)

    def test_generator_cannot_supply_hash_or_effect_metadata(self):
        verifier = FakeGenerationVerifier()
        generator = FakeGenerator(
            verifier,
            {
                "schema_version": "executor-solution-generation/1.1",
                "evidence_ref": "provider-generation:metadata-forgery",
                "mutations": [
                    {
                        "path": SOURCE_PATH,
                        "replacement_text": REPLACEMENT_TEXT,
                        "expected_before_sha256": "0" * 64,
                    }
                ],
                "rationale": "Attempt to control Executor-owned binding.",
            },
        )
        with self.assertRaisesRegex(SolutionProviderError, "mutation 0 is malformed"):
            SolutionProvider(generator, verifier).provide(
                frozen_result=self.frozen,
                checkout_root=self.repo,
            )

    def test_verified_generation_must_postdate_frozen_contract(self):
        verifier = FakeGenerationVerifier()
        generator = FakeGenerator(
            verifier,
            generated_at=NOW.isoformat().replace("+00:00", "Z"),
        )
        with self.assertRaisesRegex(SolutionProviderError, "postdate"):
            SolutionProvider(generator, verifier).provide(
                frozen_result=self.frozen,
                checkout_root=self.repo,
            )

    def test_cached_generation_from_other_frozen_contract_cannot_be_rebound(self):
        verifier = FakeGenerationVerifier()
        original_generator = FakeGenerator(verifier)
        original_result = SolutionProvider(original_generator, verifier).provide(
            frozen_result=self.frozen,
            checkout_root=self.repo,
        )
        stale_generation = copy.deepcopy(original_generator.generation)
        stale_evidence_ref = original_result.generation_evidence_ref

        (self.repo / SOURCE_PATH).write_text("VALUE = 3\n", encoding="utf-8")
        _git(self.repo, "add", SOURCE_PATH)
        _git(self.repo, "commit", "-m", "second frozen source")
        self.commit = _git(self.repo, "rev-parse", "HEAD")
        self.tree = _git(self.repo, "rev-parse", "HEAD^{tree}")
        second_frozen = self._build_frozen(Path(self.temp.name) / "ledger-second.sqlite3")

        replay_generator = FakeGenerator(
            verifier,
            stale_generation,
            publish_evidence=False,
        )
        with self.assertRaisesRegex(
            SolutionProviderError,
            "generation evidence (frozen contract|source|context|prompt) mismatch",
        ):
            SolutionProvider(replay_generator, verifier).provide(
                frozen_result=second_frozen,
                checkout_root=self.repo,
            )
        self.assertEqual(stale_generation["evidence_ref"], stale_evidence_ref)

    def test_generation_content_cannot_be_changed_under_old_evidence_ref(self):
        verifier = FakeGenerationVerifier()
        original_generator = FakeGenerator(verifier)
        SolutionProvider(original_generator, verifier).provide(
            frozen_result=self.frozen,
            checkout_root=self.repo,
        )
        changed_generation = copy.deepcopy(original_generator.generation)
        changed_generation["mutations"][0]["replacement_text"] = "VALUE = 4\n"
        replay_generator = FakeGenerator(
            verifier,
            changed_generation,
            publish_evidence=False,
        )
        with self.assertRaisesRegex(SolutionProviderError, "response hash mismatch"):
            SolutionProvider(replay_generator, verifier).provide(
                frozen_result=self.frozen,
                checkout_root=self.repo,
            )


if __name__ == "__main__":
    unittest.main()
