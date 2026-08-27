from __future__ import annotations

from types import SimpleNamespace

import pytest

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


def test_crash_immediately_before_consumption_is_block_with_proven_zero_writes(monkeypatch) -> None:
    pre_repo = _repo()
    pre_git = _git()
    monkeypatch.setattr("executor.stage3_runtime._safe_post_manifests", lambda: (pre_repo, pre_git))
    monkeypatch.setattr("executor.stage3_runtime._write_terminal_receipt", lambda *a, **k: None)
    result = _block_or_unknown(initial_repo=pre_repo, initial_git=pre_git, detail="injected before consume")
    assert result.terminal_status is Stage3TerminalStatus.BLOCK
    assert result.authority_consumed is False
    assert result.repository_write_count_claim == 0


def test_crash_after_consumption_before_first_target_write_is_fail() -> None:
    status, writes = _classify_post_consumption_exception(
        pre_repo=_repo(), pre_git=_git(), post_repo=_repo(), post_git=_git(), mutation=_mutation()
    )
    assert status is Stage3TerminalStatus.FAIL
    assert writes == 0


def test_crash_during_replacement_with_partial_or_wrong_target_is_fail() -> None:
    status, writes = _classify_post_consumption_exception(
        pre_repo=_repo(),
        pre_git=_git(),
        post_repo=_repo("partial"),
        post_git=_git(),
        mutation=_mutation(),
    )
    assert status is Stage3TerminalStatus.FAIL
    assert writes == 1


def test_crash_after_exact_flush_before_observer_or_terminal_closure_is_unknown() -> None:
    status, writes = _classify_post_consumption_exception(
        pre_repo=_repo(),
        pre_git=_git(),
        post_repo=_repo("after"),
        post_git=_git(),
        mutation=_mutation(),
    )
    assert status is Stage3TerminalStatus.UNKNOWN
    assert writes == 1


def test_crash_with_second_path_or_git_metadata_effect_is_fail() -> None:
    status, _ = _classify_post_consumption_exception(
        pre_repo=_repo(),
        pre_git=_git(),
        post_repo=_repo("after", extra=True),
        post_git=_git(),
        mutation=_mutation(),
    )
    assert status is Stage3TerminalStatus.FAIL
    status, _ = _classify_post_consumption_exception(
        pre_repo=_repo(),
        pre_git=_git("a" * 64),
        post_repo=_repo("after"),
        post_git=_git("b" * 64),
        mutation=_mutation(),
    )
    assert status is Stage3TerminalStatus.FAIL


def test_crash_with_unavailable_independent_post_state_is_unknown() -> None:
    status, writes = _classify_post_consumption_exception(
        pre_repo=_repo(), pre_git=_git(), post_repo=None, post_git=None, mutation=_mutation()
    )
    assert status is Stage3TerminalStatus.UNKNOWN
    assert writes is None


def test_fail_unknown_never_mean_safe_retry() -> None:
    assert Stage3TerminalStatus.FAIL.value != "BLOCK"
    assert Stage3TerminalStatus.UNKNOWN.value != "BLOCK"
    assert "RETRY" not in {item.value for item in Stage3TerminalStatus}


def test_terminal_allocation_replay_blocks_without_second_write(monkeypatch, tmp_path) -> None:
    import executor.stage3_runtime as runtime

    terminal = tmp_path / "stage3-terminal.json"
    terminal.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(runtime, "TERMINAL_RECEIPT", terminal)
    result = runtime.Stage3MutationRuntime().execute()
    assert result.terminal_status is Stage3TerminalStatus.BLOCK
    assert result.authority_consumed is False
    assert result.repository_write_count_claim == 0
    assert "retry/replay" in result.detail
