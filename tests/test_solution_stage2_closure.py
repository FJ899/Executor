from __future__ import annotations

import copy
import hashlib
import inspect
import subprocess
import tempfile
import unittest
from pathlib import Path

from executor.github_trust import canonical_json
from executor.solution_proposal import SolutionProposalError, validate_solution_proposal
from executor.solution_provider import (
    SolutionProvider,
    SolutionProviderError,
    generate_validated_solution,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


class ContextProvider:
    provider_name = "TEST_STAGE2_PROVIDER"
    model_name = "test-stage2-model"

    def __init__(self, *, before_override: str | None = None, add_extra_effect_field: bool = False):
        self.before_override = before_override
        self.add_extra_effect_field = add_extra_effect_field
        self.calls = 0
        self.received_context: dict | None = None

    def generate_candidate(
        self,
        *,
        frozen_contract: dict,
        solution_context: dict,
        prompt: str,
    ) -> dict:
        del prompt
        self.calls += 1
        self.received_context = copy.deepcopy(solution_context)
        target = frozen_contract["contract"]["target"]
        task = frozen_contract["contract"]["task"]
        source_file = solution_context["required_files"][0]
        replacement = source_file["content"] + "# stage2-fix\n"
        candidate = {
            "schema_version": "executor-solution-candidate/1.0",
            "status": "AWAITING_FROZEN_CONTRACT_SHA",
            "proposal_id": "stage2-proposal-001",
            "repository": target["repository"],
            "source_commit": target["commit"],
            "source_tree": target["tree"],
            "mutations": [
                {
                    "path": source_file["path"],
                    "expected_before_sha256": self.before_override or source_file["sha256"],
                    "replacement_text": replacement,
                    "expected_after_sha256": hashlib.sha256(
                        replacement.encode("utf-8")
                    ).hexdigest(),
                }
            ],
            "rationale": "bounded Stage-2 candidate",
            "evidence_plan": [
                *copy.deepcopy(task["postcondition_argv"]),
                *copy.deepcopy(task["regression_argv"]),
            ],
        }
        if self.add_extra_effect_field:
            candidate["authority"] = {"decision": "ALLOW"}
        return candidate


class Stage2Fixture:
    def __init__(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        _git(self.root, "init", "-b", "main")
        _git(self.root, "config", "user.email", "stage2@example.invalid")
        _git(self.root, "config", "user.name", "Stage2 Test")
        _git(
            self.root,
            "remote",
            "add",
            "origin",
            "https://github.com/FJ899/executor-pilot-target.git",
        )
        source = self.root / "project_registry" / "registry.py"
        source.parent.mkdir(parents=True)
        source.write_text("VALUE = 1\n", encoding="utf-8")
        _git(self.root, "add", "project_registry/registry.py")
        _git(self.root, "commit", "-m", "pinned source")
        self.commit = _git(self.root, "rev-parse", "HEAD")
        self.tree = _git(self.root, "rev-parse", "HEAD^{tree}")
        self.before_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
        self.contract = {
            "request_id": "stage2-request-001",
            "target": {
                "repository": "FJ899/executor-pilot-target",
                "commit": self.commit,
                "tree": self.tree,
            },
            "task": {
                "allowed_paths": ["project_registry/registry.py"],
                "protected_paths": ["tests/**", ".github/**"],
                "postcondition_argv": [["python", "-c", "raise SystemExit(0)"]],
                "regression_argv": [["python", "-m", "unittest", "discover", "-s", "tests"]],
                "max_production_files": 1,
            },
            "request_evidence": {
                "repository": "FJ899/Executor",
                "issue_number": 97,
                "issue_node_id": "I_stage2",
                "body_sha256": "1" * 64,
                "created_at": "2026-08-26T10:00:00Z",
            },
        }
        self.contract_sha256 = hashlib.sha256(
            canonical_json(self.contract).encode("utf-8")
        ).hexdigest()
        self.frozen = {
            "status": "AUTHORIZED_AND_FROZEN",
            "contract": copy.deepcopy(self.contract),
            "contract_sha256": self.contract_sha256,
        }

    def close(self) -> None:
        self.temp.cleanup()


def _raw_proposal(validated) -> dict:
    return {
        "schema_version": "executor-solution-proposal/1.0",
        "proposal_id": validated.proposal_id,
        "contract_sha256": validated.contract_sha256,
        "repository": validated.repository,
        "source_commit": validated.source_commit,
        "source_tree": validated.source_tree,
        "mutations": [item.to_dict() for item in validated.mutations],
        "rationale": validated.rationale,
        "evidence_plan": [list(item) for item in validated.evidence_plan],
        "provenance": copy.deepcopy(validated.provenance),
    }


class SolutionStage2ClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = Stage2Fixture()
        self.addCleanup(self.fixture.close)

    def _generate(self, provider: ContextProvider):
        return generate_validated_solution(
            provider=provider,
            frozen_result=self.fixture.frozen,
            source_root=self.fixture.root,
            prompt="Produce the bounded fix from the exact frozen source context.",
            generated_at="2026-08-27T12:00:00Z",
        )

    def test_valid_provider_output_becomes_valid_proposal(self) -> None:
        provider = ContextProvider()
        validated = self._generate(provider)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(validated.repository, "FJ899/executor-pilot-target")
        self.assertEqual(validated.provenance["schema_version"], "executor-solution-provenance/1.1")
        self.assertEqual(validated.provenance["frozen_contract_sha256"], self.fixture.contract_sha256)
        self.assertEqual(validated.provenance["effect_capability"], "NONE")
        self.assertEqual(
            provider.received_context["solution_context_sha256"],
            validated.provenance["solution_context_sha256"],
        )

    def test_source_commit_mismatch_blocks_before_provider_call(self) -> None:
        provider = ContextProvider()
        frozen = copy.deepcopy(self.fixture.frozen)
        frozen["contract"]["target"]["commit"] = "1" * 40
        with self.assertRaises(SolutionProviderError):
            generate_validated_solution(
                provider=provider,
                frozen_result=frozen,
                source_root=self.fixture.root,
                prompt="exact source",
                generated_at="2026-08-27T12:00:00Z",
            )
        self.assertEqual(provider.calls, 0)

    def test_source_tree_mismatch_blocks_before_provider_call(self) -> None:
        provider = ContextProvider()
        frozen = copy.deepcopy(self.fixture.frozen)
        frozen["contract"]["target"]["tree"] = "2" * 40
        with self.assertRaises(SolutionProviderError):
            generate_validated_solution(
                provider=provider,
                frozen_result=frozen,
                source_root=self.fixture.root,
                prompt="exact source",
                generated_at="2026-08-27T12:00:00Z",
            )
        self.assertEqual(provider.calls, 0)

    def test_exact_before_hash_is_bound_to_observed_file(self) -> None:
        validated = self._generate(ContextProvider())
        self.assertEqual(
            validated.mutations[0].expected_before_sha256,
            self.fixture.before_sha256,
        )
        source_file = validated.provenance["source_files"][0]
        self.assertEqual(source_file["sha256"], self.fixture.before_sha256)

    def test_before_hash_mismatch_blocks(self) -> None:
        with self.assertRaisesRegex(SolutionProposalError, "before hash"):
            self._generate(ContextProvider(before_override="0" * 64))

    def test_solution_context_hash_tamper_blocks(self) -> None:
        validated = self._generate(ContextProvider())
        raw = _raw_proposal(validated)
        raw["provenance"]["solution_context_sha256"] = "f" * 64
        with self.assertRaisesRegex(SolutionProposalError, "context hash mismatch"):
            validate_solution_proposal(raw, frozen_result=self.fixture.frozen)

    def test_provider_interface_has_no_write_handles_and_extra_effect_fields_block(self) -> None:
        parameters = inspect.signature(SolutionProvider.generate_candidate).parameters
        self.assertEqual(
            list(parameters),
            ["self", "frozen_contract", "solution_context", "prompt"],
        )
        provider = ContextProvider()
        self._generate(provider)
        self.assertIsNotNone(provider.received_context)
        for forbidden in (
            "github_client",
            "repo_writer",
            "branch_handle",
            "pr_client",
            "effect_ledger",
        ):
            self.assertNotIn(forbidden, provider.received_context)
        with self.assertRaises(SolutionProposalError):
            self._generate(ContextProvider(add_extra_effect_field=True))


if __name__ == "__main__":
    unittest.main()
