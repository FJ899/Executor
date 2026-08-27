from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from executor.stage3_evidence import Manifest
from executor.stage3_runtime import (
    Stage3TerminalStatus,
    _block_or_unknown,
    _classify_post_consumption_exception,
)


def _repo(content: str = "before", *, extra: bool = False) -> Manifest:
    entries = [
        {
            "path": "target.txt",
            "mode": 0o644,
            "uid": 1000,
            "gid": 1000,
            "nlink": 1,
            "size": 6,
            "type": "regular",
            "content_sha256": content,
        }
    ]
    if extra:
        entries.append(
            {
                "path": "second.txt",
                "mode": 0o644,
                "uid": 1000,
                "gid": 1000,
                "nlink": 1,
                "size": 1,
                "type": "regular",
                "content_sha256": "second",
            }
        )
    return Manifest("repository-plane-excluding-git", tuple(entries), "r" * 64)


def _git(root: str = "g" * 64) -> Manifest:
    return Manifest("git-metadata", tuple(), root)


def _mutation() -> SimpleNamespace:
    return SimpleNamespace(path="target.txt", expected_after_sha256="after")


class Stage3CrashSemanticsTests(unittest.TestCase):
    def test_crash_immediately_before_consumption_is_block_with_proven_zero_writes(self) -> None:
        pre_repo = _repo()
        pre_git = _git()
        with patch("executor.stage3_runtime._safe_post_manifests", return_value=(pre_repo, pre_git)), patch(
            "executor.stage3_runtime._write_terminal_receipt", return_value=None
        ):
            result = _block_or_unknown(
                initial_repo=pre_repo,
                initial_git=pre_git,
                detail="injected before consume",
            )
        self.assertIs(result.terminal_status, Stage3TerminalStatus.BLOCK)
        self.assertIs(result.authority_consumed, False)
        self.assertEqual(result.repository_write_count_claim, 0)

    def test_crash_after_consumption_before_first_target_write_is_fail(self) -> None:
        status, writes = _classify_post_consumption_exception(
            pre_repo=_repo(),
            pre_git=_git(),
            post_repo=_repo(),
            post_git=_git(),
            mutation=_mutation(),
        )
        self.assertIs(status, Stage3TerminalStatus.FAIL)
        self.assertEqual(writes, 0)

    def test_crash_during_partial_or_wrong_target_replacement_is_fail(self) -> None:
        status, writes = _classify_post_consumption_exception(
            pre_repo=_repo(),
            pre_git=_git(),
            post_repo=_repo("partial"),
            post_git=_git(),
            mutation=_mutation(),
        )
        self.assertIs(status, Stage3TerminalStatus.FAIL)
        self.assertEqual(writes, 1)

    def test_crash_after_exact_flush_before_observer_or_terminal_closure_is_unknown(self) -> None:
        status, writes = _classify_post_consumption_exception(
            pre_repo=_repo(),
            pre_git=_git(),
            post_repo=_repo("after"),
            post_git=_git(),
            mutation=_mutation(),
        )
        self.assertIs(status, Stage3TerminalStatus.UNKNOWN)
        self.assertEqual(writes, 1)

    def test_crash_with_second_path_effect_is_fail(self) -> None:
        status, writes = _classify_post_consumption_exception(
            pre_repo=_repo(),
            pre_git=_git(),
            post_repo=_repo("after", extra=True),
            post_git=_git(),
            mutation=_mutation(),
        )
        self.assertIs(status, Stage3TerminalStatus.FAIL)
        self.assertGreaterEqual(writes, 1)

    def test_crash_with_git_metadata_effect_is_fail(self) -> None:
        status, writes = _classify_post_consumption_exception(
            pre_repo=_repo(),
            pre_git=_git("a" * 64),
            post_repo=_repo("after"),
            post_git=_git("b" * 64),
            mutation=_mutation(),
        )
        self.assertIs(status, Stage3TerminalStatus.FAIL)
        self.assertEqual(writes, 1)

    def test_crash_with_unavailable_independent_post_state_is_unknown(self) -> None:
        status, writes = _classify_post_consumption_exception(
            pre_repo=_repo(),
            pre_git=_git(),
            post_repo=None,
            post_git=None,
            mutation=_mutation(),
        )
        self.assertIs(status, Stage3TerminalStatus.UNKNOWN)
        self.assertIsNone(writes)

    def test_fail_and_unknown_never_mean_safe_retry(self) -> None:
        self.assertNotEqual(Stage3TerminalStatus.FAIL.value, "BLOCK")
        self.assertNotEqual(Stage3TerminalStatus.UNKNOWN.value, "BLOCK")
        self.assertNotIn("RETRY", {item.value for item in Stage3TerminalStatus})

    def test_terminal_allocation_replay_blocks_with_zero_second_write(self) -> None:
        import executor.stage3_runtime as runtime

        with tempfile.TemporaryDirectory() as temp_dir:
            terminal = Path(temp_dir) / "stage3-terminal.json"
            terminal.write_text("{}", encoding="utf-8")
            with patch.object(runtime, "TERMINAL_RECEIPT", terminal):
                result = runtime.Stage3MutationRuntime().execute()
        self.assertIs(result.terminal_status, Stage3TerminalStatus.BLOCK)
        self.assertIs(result.authority_consumed, False)
        self.assertEqual(result.repository_write_count_claim, 0)
        self.assertIn("retry/replay", result.detail)


if __name__ == "__main__":
    unittest.main()
