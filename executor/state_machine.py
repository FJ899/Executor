from __future__ import annotations

import json
import os
import re
import stat
import threading
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - the supported execution environment is POSIX
    fcntl = None

from executor.checkpoints import Snapshot, atomic_write_json, atomic_write_text, fsync_directory, utc_now
from executor.hashing import hash_json


class RunState(StrEnum):
    CREATED = "CREATED"
    CONTRACT_VALIDATED = "CONTRACT_VALIDATED"
    NORMALIZED = "NORMALIZED"
    PLANNED = "PLANNED"
    AWAITING_DECISION = "AWAITING_DECISION"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    REPLAYING = "REPLAYING"
    PASS = "PASS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    STALE = "STALE"


TERMINAL_STATES = {RunState.PASS, RunState.BLOCKED, RunState.FAILED, RunState.STALE}

_ALLOWED: dict[RunState, set[RunState]] = {
    RunState.CREATED: {RunState.CONTRACT_VALIDATED, RunState.BLOCKED, RunState.FAILED, RunState.STALE},
    RunState.CONTRACT_VALIDATED: {RunState.NORMALIZED, RunState.BLOCKED, RunState.FAILED, RunState.STALE},
    RunState.NORMALIZED: {RunState.PLANNED, RunState.BLOCKED, RunState.FAILED, RunState.STALE},
    RunState.PLANNED: {RunState.AWAITING_DECISION, RunState.APPROVED, RunState.BLOCKED, RunState.FAILED, RunState.STALE},
    RunState.AWAITING_DECISION: {RunState.APPROVED, RunState.BLOCKED, RunState.FAILED, RunState.STALE},
    RunState.APPROVED: {RunState.EXECUTING, RunState.BLOCKED, RunState.FAILED, RunState.STALE},
    RunState.EXECUTING: {RunState.VERIFYING, RunState.BLOCKED, RunState.FAILED, RunState.STALE},
    RunState.VERIFYING: {RunState.REPLAYING, RunState.BLOCKED, RunState.FAILED, RunState.STALE},
    # PASS remains locked until the separately approved M3 replay gate exists.
    RunState.REPLAYING: {RunState.BLOCKED, RunState.FAILED, RunState.STALE},
    RunState.PASS: set(),
    RunState.BLOCKED: set(),
    RunState.FAILED: set(),
    RunState.STALE: set(),
}

_RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_EVENT_FIELDS = frozenset(
    {
        "sequence",
        "run_id",
        "previous_state",
        "state",
        "reason",
        "created_at",
        "snapshot",
        "previous_event_hash",
        "event_hash",
    }
)
_TRANSACTION_FIELDS = frozenset(
    {"version", "run_id", "previous_events", "event", "transaction_hash"}
)
_PROCESS_LOCKS: dict[str, threading.RLock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


class InvalidTransition(RuntimeError):
    pass


class RunIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class RunEvent:
    sequence: int
    run_id: str
    previous_state: str | None
    state: str
    reason: str
    created_at: str
    snapshot: dict[str, Any]
    previous_event_hash: str | None
    event_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RevalidationResult:
    status: str
    differences: dict[str, dict[str, Any]]

    @property
    def unchanged(self) -> bool:
        return self.status == "UNCHANGED"

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "differences": self.differences}


class RunStore:
    """Fail-closed store whose canonical state is the verified event chain.

    ``state.json`` and checkpoint files are materialized integrity mirrors. Every
    public read or mutation verifies all three representations while holding the
    run lock. A transaction journal is the commit guard for multi-file writes.
    """

    def __init__(self, runs_root: str | Path):
        self.runs_root = Path(runs_root).absolute()

    def _root(self, *, create: bool = False) -> Path:
        if create:
            self.runs_root.mkdir(parents=True, exist_ok=True)
        try:
            root = self.runs_root.resolve(strict=True)
        except OSError as exc:
            raise RunIntegrityError(f"Cannot resolve runs root {self.runs_root}: {exc}") from exc
        if not root.is_dir():
            raise RunIntegrityError(f"Runs root is not a directory: {root}")
        return root

    @staticmethod
    def _validate_run_id(run_id: str) -> None:
        if not isinstance(run_id, str) or _RUN_ID_PATTERN.fullmatch(run_id) is None:
            raise ValueError(
                "Invalid run_id: use 1-128 ASCII letters, digits, underscores or hyphens; "
                "the first character must be alphanumeric"
            )

    def _dir(self, run_id: str, *, require_existing: bool = True, create_root: bool = False) -> Path:
        self._validate_run_id(run_id)
        root = self._root(create=create_root)
        candidate = root / run_id
        if candidate.is_symlink():
            raise RunIntegrityError(f"Run directory cannot be a symlink: {run_id}")
        resolved = candidate.resolve(strict=False)
        if resolved.parent != root:
            raise RunIntegrityError(f"Run directory escapes runs root: {run_id}")
        if require_existing:
            if not candidate.exists():
                raise RunIntegrityError(f"Run does not exist: {run_id}")
            if not candidate.is_dir():
                raise RunIntegrityError(f"Run path is not a directory: {run_id}")
        return candidate

    def _state_path(self, run_id: str) -> Path:
        return self._dir(run_id) / "state.json"

    def _events_path(self, run_id: str) -> Path:
        return self._dir(run_id) / "events.jsonl"

    def create(self, snapshot: Snapshot, *, run_id: str | None = None, reason: str = "run created") -> str:
        actual_id = run_id or f"RUN-{uuid.uuid4().hex[:12].upper()}"
        self._validate_run_id(actual_id)
        run_dir = self._dir(actual_id, require_existing=False, create_root=True)
        if run_dir.exists():
            raise FileExistsError(actual_id)
        run_dir.mkdir(parents=False)
        (run_dir / "checkpoints").mkdir()
        event = self._build_event(
            sequence=1,
            run_id=actual_id,
            previous_state=None,
            state=RunState.CREATED,
            reason=reason,
            snapshot=snapshot,
            previous_event_hash=None,
        )
        try:
            with self._run_lock(actual_id) as locked_dir:
                self._persist_event_locked(locked_dir, event, previous_rows=[])
                self._load_verified_locked(actual_id, locked_dir)
        except BaseException:
            self._cleanup_empty_failed_create(run_dir)
            raise
        return actual_id

    def load_state(self, run_id: str) -> dict[str, Any]:
        with self._run_lock(run_id) as run_dir:
            state, _ = self._load_verified_locked(run_id, run_dir)
            return state

    def events(self, run_id: str) -> list[dict[str, Any]]:
        with self._run_lock(run_id) as run_dir:
            _, rows = self._load_verified_locked(run_id, run_dir)
            return rows

    def transition(self, run_id: str, new_state: RunState | str, snapshot: Snapshot, *, reason: str) -> dict[str, Any]:
        target = RunState(new_state)
        with self._run_lock(run_id) as run_dir:
            current, rows = self._load_verified_locked(run_id, run_dir)
            current_state = RunState(current["state"])
            if target == RunState.PASS:
                raise InvalidTransition("PASS is locked until the deterministic M3 replay gate is implemented")
            if target not in _ALLOWED[current_state]:
                raise InvalidTransition(f"{current_state.value} -> {target.value} is not allowed")
            event = self._build_event(
                sequence=len(rows) + 1,
                run_id=run_id,
                previous_state=current_state,
                state=target,
                reason=reason,
                snapshot=snapshot,
                previous_event_hash=rows[-1]["event_hash"],
            )
            self._persist_event_locked(run_dir, event, previous_rows=rows)
            self._load_verified_locked(run_id, run_dir)
            return event.to_dict()

    def revalidate(self, run_id: str, current_snapshot: Snapshot, *, mark_stale: bool = True) -> RevalidationResult:
        with self._run_lock(run_id) as run_dir:
            state, rows = self._load_verified_locked(run_id, run_dir)
            expected = rows[-1]["snapshot"]
            actual = current_snapshot.to_dict()
            differences: dict[str, dict[str, Any]] = {}
            for key in sorted(set(expected) | set(actual)):
                if expected.get(key) != actual.get(key):
                    differences[key] = {"expected": expected.get(key), "actual": actual.get(key)}
            if not differences:
                return RevalidationResult("UNCHANGED", {})
            current_state = RunState(state["state"])
            if mark_stale and current_state not in TERMINAL_STATES:
                event = self._build_event(
                    sequence=len(rows) + 1,
                    run_id=run_id,
                    previous_state=current_state,
                    state=RunState.STALE,
                    reason="revalidation detected changed inputs",
                    snapshot=current_snapshot,
                    previous_event_hash=rows[-1]["event_hash"],
                )
                self._persist_event_locked(run_dir, event, previous_rows=rows)
                self._load_verified_locked(run_id, run_dir)
            return RevalidationResult("STALE", differences)

    def _build_event(
        self,
        *,
        sequence: int,
        run_id: str,
        previous_state: RunState | None,
        state: RunState,
        reason: str,
        snapshot: Snapshot,
        previous_event_hash: str | None,
    ) -> RunEvent:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Transition reason must be a non-empty string")
        body = {
            "sequence": sequence,
            "run_id": run_id,
            "previous_state": previous_state.value if previous_state else None,
            "state": state.value,
            "reason": reason,
            "created_at": utc_now(),
            "snapshot": snapshot.to_dict(),
            "previous_event_hash": previous_event_hash,
        }
        return RunEvent(event_hash=hash_json(body), **body)

    def _persist_event_locked(self, run_dir: Path, event: RunEvent, *, previous_rows: list[dict[str, Any]]) -> None:
        event_row = event.to_dict()
        rows = [*previous_rows, event_row]
        self._verify_chain(rows, expected_run_id=event.run_id)
        transaction_path = run_dir / ".transaction.json"
        if transaction_path.exists() or transaction_path.is_symlink():
            raise RunIntegrityError(f"Pending transaction blocks run {event.run_id}")
        transaction_body = {
            "version": 1,
            "run_id": event.run_id,
            "previous_events": previous_rows,
            "event": event_row,
        }
        transaction = {**transaction_body, "transaction_hash": hash_json(transaction_body)}
        checkpoint_path = self._checkpoint_path(run_dir, event_row)
        commit_complete = False
        try:
            atomic_write_json(transaction_path, transaction)
            self._after_persist_phase("journal", event)
            atomic_write_json(checkpoint_path, event_row)
            self._after_persist_phase("checkpoint", event)
            atomic_write_text(run_dir / "events.jsonl", self._serialize_events(rows))
            self._after_persist_phase("events", event)
            atomic_write_json(run_dir / "state.json", self._state_from_event(event_row))
            self._after_persist_phase("state", event)
            transaction_path.unlink()
            commit_complete = True
            fsync_directory(run_dir)
        except BaseException as exc:
            if transaction_path.exists() or transaction_path.is_symlink():
                try:
                    self._recover_pending_locked(event.run_id, run_dir)
                except Exception as recovery_exc:
                    raise RunIntegrityError(
                        f"Transition for {event.run_id} failed and rollback could not be verified: {recovery_exc}"
                    ) from exc
                raise
            # The journal removal is the commit point. If it completed before a
            # directory fsync error, accept only a fully verified new state.
            if not commit_complete:
                raise
            try:
                self._load_verified_locked(event.run_id, run_dir, recover=False)
            except Exception as verification_exc:
                raise RunIntegrityError(
                    f"Transition for {event.run_id} has an indeterminate commit: {verification_exc}"
                ) from exc

    def _after_persist_phase(self, phase: str, event: RunEvent) -> None:
        """Internal fault-injection seam used by transactional regression tests."""

    def _load_verified_locked(
        self,
        run_id: str,
        run_dir: Path,
        *,
        recover: bool = True,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if recover:
            self._recover_pending_locked(run_id, run_dir)
        else:
            transaction_path = run_dir / ".transaction.json"
            if transaction_path.exists() or transaction_path.is_symlink():
                raise RunIntegrityError(f"Pending transaction blocks run {run_id}")
        rows = self._read_events_file(run_dir / "events.jsonl", label="event log")
        self._verify_chain(rows, expected_run_id=run_id)
        state = self._read_json_object(run_dir / "state.json", label="state")
        expected_state = self._state_from_event(rows[-1])
        if state != expected_state:
            raise RunIntegrityError("state.json does not match the last verified event")
        self._verify_checkpoints(run_dir, rows)
        return state, rows

    def _recover_pending_locked(self, run_id: str, run_dir: Path) -> None:
        transaction_path = run_dir / ".transaction.json"
        if not transaction_path.exists() and not transaction_path.is_symlink():
            return
        transaction = self._read_json_object(transaction_path, label="transaction journal")
        if frozenset(transaction) != _TRANSACTION_FIELDS:
            raise RunIntegrityError("Transaction journal has unexpected fields")
        transaction_body = {key: value for key, value in transaction.items() if key != "transaction_hash"}
        if transaction.get("transaction_hash") != hash_json(transaction_body):
            raise RunIntegrityError("Transaction journal hash mismatch")
        if transaction.get("version") != 1 or transaction.get("run_id") != run_id:
            raise RunIntegrityError("Transaction journal identity mismatch")
        previous_rows = transaction.get("previous_events")
        event_row = transaction.get("event")
        if not isinstance(previous_rows, list) or not isinstance(event_row, dict):
            raise RunIntegrityError("Transaction journal payload is malformed")
        self._verify_chain(previous_rows, expected_run_id=run_id, allow_empty=True)
        target_rows = [*previous_rows, event_row]
        self._verify_chain(target_rows, expected_run_id=run_id)

        events_path = run_dir / "events.jsonl"
        current_rows = self._read_optional_events_file(events_path)
        permitted_rows: list[list[dict[str, Any]] | None] = [target_rows]
        permitted_rows.append(previous_rows if previous_rows else None)
        if current_rows not in permitted_rows:
            raise RunIntegrityError("Event log cannot be safely rolled back from pending transaction")

        state_path = run_dir / "state.json"
        current_state = self._read_optional_json_object(state_path, label="state")
        previous_state = self._state_from_event(previous_rows[-1]) if previous_rows else None
        target_state = self._state_from_event(event_row)
        if current_state not in (previous_state, target_state):
            raise RunIntegrityError("state.json cannot be safely rolled back from pending transaction")

        checkpoint_path = self._checkpoint_path(run_dir, event_row)
        checkpoint = self._read_optional_json_object(checkpoint_path, label="pending checkpoint")
        if checkpoint is not None and checkpoint != event_row:
            raise RunIntegrityError("Pending checkpoint cannot be safely rolled back")

        try:
            if previous_rows:
                if current_rows != previous_rows:
                    atomic_write_text(events_path, self._serialize_events(previous_rows))
                if current_state != previous_state:
                    atomic_write_json(state_path, previous_state)
            else:
                self._unlink_regular_file(events_path, label="event log")
                self._unlink_regular_file(state_path, label="state")
            self._unlink_regular_file(checkpoint_path, label="pending checkpoint")
            fsync_directory(run_dir / "checkpoints")
            transaction_path.unlink()
            fsync_directory(run_dir)
        except OSError as exc:
            raise RunIntegrityError(f"Cannot roll back pending transaction: {exc}") from exc

    def _verify_checkpoints(self, run_dir: Path, rows: list[dict[str, Any]]) -> None:
        checkpoints_dir = self._checkpoint_directory(run_dir)
        expected = {self._checkpoint_path(run_dir, row).name: row for row in rows}
        try:
            entries = list(checkpoints_dir.iterdir())
        except OSError as exc:
            raise RunIntegrityError(f"Cannot list checkpoints: {exc}") from exc
        actual_names = {entry.name for entry in entries}
        if actual_names != set(expected):
            missing = sorted(set(expected) - actual_names)
            unexpected = sorted(actual_names - set(expected))
            raise RunIntegrityError(f"Checkpoint set mismatch; missing={missing}, unexpected={unexpected}")
        for entry in entries:
            checkpoint = self._read_json_object(entry, label=f"checkpoint {entry.name}")
            if checkpoint != expected[entry.name]:
                raise RunIntegrityError(f"Checkpoint {entry.name} does not match its verified event")

    @staticmethod
    def _state_from_event(event: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_id": event["run_id"],
            "state": event["state"],
            "sequence": event["sequence"],
            "event_hash": event["event_hash"],
            "snapshot": event["snapshot"],
            "updated_at": event["created_at"],
        }

    def _checkpoint_path(self, run_dir: Path, event: dict[str, Any]) -> Path:
        return self._checkpoint_directory(run_dir) / f"{event['sequence']:04d}-{event['state']}.json"

    @staticmethod
    def _checkpoint_directory(run_dir: Path) -> Path:
        checkpoints_dir = run_dir / "checkpoints"
        if checkpoints_dir.is_symlink():
            raise RunIntegrityError("Checkpoint directory cannot be a symlink")
        try:
            resolved = checkpoints_dir.resolve(strict=True)
        except OSError as exc:
            raise RunIntegrityError(f"Cannot resolve checkpoint directory: {exc}") from exc
        if not resolved.is_dir() or resolved.parent != run_dir:
            raise RunIntegrityError("Checkpoint directory is missing or escapes the run directory")
        return checkpoints_dir

    @staticmethod
    def _serialize_events(rows: list[dict[str, Any]]) -> str:
        return "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        )

    def _read_events_file(self, path: Path, *, label: str) -> list[dict[str, Any]]:
        rows = self._read_optional_events_file(path)
        if rows is None or not rows:
            raise RunIntegrityError(f"Missing or empty {label}")
        return rows

    def _read_optional_events_file(self, path: Path) -> list[dict[str, Any]] | None:
        if not path.exists() and not path.is_symlink():
            return None
        self._require_regular_file(path, label="event log")
        try:
            content = path.read_text(encoding="utf-8")
            lines = content.splitlines()
            if not content.endswith("\n") or not lines or any(not line.strip() for line in lines):
                raise RunIntegrityError("Event log is not canonical JSONL")
            rows = [json.loads(line) for line in lines]
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RunIntegrityError(f"Cannot load event log: {exc}") from exc
        if any(not isinstance(row, dict) for row in rows):
            raise RunIntegrityError("Event log rows must be JSON objects")
        if content != self._serialize_events(rows):
            raise RunIntegrityError("Event log is not in canonical form")
        return rows

    def _read_json_object(self, path: Path, *, label: str) -> dict[str, Any]:
        value = self._read_optional_json_object(path, label=label)
        if value is None:
            raise RunIntegrityError(f"Missing {label}: {path.name}")
        return value

    def _read_optional_json_object(self, path: Path, *, label: str) -> dict[str, Any] | None:
        if not path.exists() and not path.is_symlink():
            return None
        self._require_regular_file(path, label=label)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RunIntegrityError(f"Cannot load {label}: {exc}") from exc
        if not isinstance(value, dict):
            raise RunIntegrityError(f"{label.capitalize()} must be a JSON object")
        return value

    @staticmethod
    def _require_regular_file(path: Path, *, label: str) -> None:
        if path.is_symlink():
            raise RunIntegrityError(f"{label.capitalize()} cannot be a symlink")
        try:
            metadata = path.stat(follow_symlinks=False)
        except OSError as exc:
            raise RunIntegrityError(f"Cannot inspect {label}: {exc}") from exc
        if not stat.S_ISREG(metadata.st_mode):
            raise RunIntegrityError(f"{label.capitalize()} is not a regular file")
        if metadata.st_nlink != 1:
            raise RunIntegrityError(f"{label.capitalize()} cannot be hard-linked")

    def _unlink_regular_file(self, path: Path, *, label: str) -> None:
        if not path.exists() and not path.is_symlink():
            return
        self._require_regular_file(path, label=label)
        path.unlink()

    @staticmethod
    def _verify_chain(
        rows: list[dict[str, Any]],
        *,
        expected_run_id: str | None = None,
        allow_empty: bool = False,
    ) -> None:
        if not rows:
            if allow_empty:
                return
            raise RunIntegrityError("Event chain is empty")
        previous_hash = None
        previous_state: RunState | None = None
        for expected_sequence, row in enumerate(rows, start=1):
            if not isinstance(row, dict) or frozenset(row) != _EVENT_FIELDS:
                raise RunIntegrityError("Event has unexpected or missing fields")
            sequence = row.get("sequence")
            if type(sequence) is not int or sequence != expected_sequence:
                raise RunIntegrityError("Event sequence is not contiguous")
            run_id = row.get("run_id")
            if not isinstance(run_id, str) or (expected_run_id is not None and run_id != expected_run_id):
                raise RunIntegrityError("Event run_id mismatch")
            try:
                state_value = RunState(row.get("state"))
            except (TypeError, ValueError) as exc:
                raise RunIntegrityError("Event contains an unknown state") from exc
            expected_previous_state = previous_state.value if previous_state is not None else None
            if row.get("previous_state") != expected_previous_state:
                raise RunIntegrityError("Event previous_state does not match the preceding event")
            if row.get("previous_event_hash") != previous_hash:
                raise RunIntegrityError("Event hash chain is broken")
            if expected_sequence == 1:
                if state_value != RunState.CREATED:
                    raise RunIntegrityError("First event must be CREATED")
            elif state_value not in _ALLOWED[previous_state]:
                if state_value == RunState.PASS:
                    raise RunIntegrityError("PASS cannot be verified before the M3 replay gate exists")
                raise RunIntegrityError(
                    f"Stored transition {previous_state.value} -> {state_value.value} is not allowed"
                )
            if not isinstance(row.get("reason"), str) or not row["reason"].strip():
                raise RunIntegrityError("Event reason must be a non-empty string")
            if not isinstance(row.get("created_at"), str) or not row["created_at"]:
                raise RunIntegrityError("Event created_at must be a non-empty string")
            if not isinstance(row.get("snapshot"), dict):
                raise RunIntegrityError("Event snapshot must be an object")
            stored_hash = row.get("event_hash")
            if not isinstance(stored_hash, str) or re.fullmatch(r"[a-f0-9]{64}", stored_hash) is None:
                raise RunIntegrityError("Event hash has an invalid format")
            body = {key: value for key, value in row.items() if key != "event_hash"}
            if stored_hash != hash_json(body):
                raise RunIntegrityError("Event content hash mismatch")
            previous_hash = stored_hash
            previous_state = state_value

    @contextmanager
    def _run_lock(self, run_id: str) -> Iterator[Path]:
        if fcntl is None:
            raise RunIntegrityError("Inter-process run locking is unavailable on this platform")
        run_dir = self._dir(run_id)
        lock_path = run_dir / ".lock"
        key = str(run_dir)
        with _PROCESS_LOCKS_GUARD:
            process_lock = _PROCESS_LOCKS.setdefault(key, threading.RLock())
        with process_lock:
            if lock_path.is_symlink():
                raise RunIntegrityError("Run lock cannot be a symlink")
            flags = os.O_RDWR | os.O_CREAT
            for optional_flag in ("O_CLOEXEC", "O_NOFOLLOW", "O_NONBLOCK"):
                flags |= getattr(os, optional_flag, 0)
            try:
                descriptor = os.open(lock_path, flags, 0o600)
            except OSError as exc:
                raise RunIntegrityError(f"Cannot open run lock for {run_id}: {exc}") from exc
            try:
                lock_metadata = os.fstat(descriptor)
                if not stat.S_ISREG(lock_metadata.st_mode):
                    raise RunIntegrityError("Run lock is not a regular file")
                if lock_metadata.st_nlink != 1:
                    raise RunIntegrityError("Run lock cannot be hard-linked")
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                if self._dir(run_id) != run_dir:
                    raise RunIntegrityError("Run directory changed while acquiring its lock")
                yield run_dir
            finally:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                finally:
                    os.close(descriptor)

    @staticmethod
    def _cleanup_empty_failed_create(run_dir: Path) -> None:
        checkpoints_dir = run_dir / "checkpoints"
        protected = [run_dir / "events.jsonl", run_dir / "state.json", run_dir / ".transaction.json"]
        if any(path.exists() or path.is_symlink() for path in protected):
            return
        try:
            if checkpoints_dir.is_symlink() or (checkpoints_dir.exists() and any(checkpoints_dir.iterdir())):
                return
            lock_path = run_dir / ".lock"
            if lock_path.exists() and not lock_path.is_symlink() and lock_path.is_file():
                lock_path.unlink()
            if checkpoints_dir.exists():
                checkpoints_dir.rmdir()
            run_dir.rmdir()
            fsync_directory(run_dir.parent)
        except OSError:
            # The failed create remains unusable and therefore fail-closed.
            return
