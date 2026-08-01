from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from executor.checkpoints import Snapshot, append_jsonl, atomic_write_json, utc_now
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
    RunState.REPLAYING: {RunState.PASS, RunState.BLOCKED, RunState.FAILED, RunState.STALE},
    RunState.PASS: set(),
    RunState.BLOCKED: set(),
    RunState.FAILED: set(),
    RunState.STALE: set(),
}


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
    def __init__(self, runs_root: str | Path):
        self.runs_root = Path(runs_root)

    def _dir(self, run_id: str) -> Path:
        return self.runs_root / run_id

    def _state_path(self, run_id: str) -> Path:
        return self._dir(run_id) / "state.json"

    def _events_path(self, run_id: str) -> Path:
        return self._dir(run_id) / "events.jsonl"

    def create(self, snapshot: Snapshot, *, run_id: str | None = None, reason: str = "run created") -> str:
        actual_id = run_id or f"RUN-{uuid.uuid4().hex[:12].upper()}"
        run_dir = self._dir(actual_id)
        if run_dir.exists():
            raise FileExistsError(actual_id)
        run_dir.mkdir(parents=True)
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
        self._persist(event)
        return actual_id

    def load_state(self, run_id: str) -> dict[str, Any]:
        try:
            return json.loads(self._state_path(run_id).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RunIntegrityError(f"Cannot load state for {run_id}: {exc}") from exc

    def events(self, run_id: str) -> list[dict[str, Any]]:
        path = self._events_path(run_id)
        try:
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, json.JSONDecodeError) as exc:
            raise RunIntegrityError(f"Cannot load events for {run_id}: {exc}") from exc
        self._verify_chain(rows)
        return rows

    def transition(self, run_id: str, new_state: RunState | str, snapshot: Snapshot, *, reason: str) -> dict[str, Any]:
        current = self.load_state(run_id)
        current_state = RunState(current["state"])
        target = RunState(new_state)
        if target not in _ALLOWED[current_state]:
            raise InvalidTransition(f"{current_state.value} -> {target.value} is not allowed")
        rows = self.events(run_id)
        event = self._build_event(
            sequence=len(rows) + 1,
            run_id=run_id,
            previous_state=current_state,
            state=target,
            reason=reason,
            snapshot=snapshot,
            previous_event_hash=rows[-1]["event_hash"],
        )
        self._persist(event)
        return event.to_dict()

    def revalidate(self, run_id: str, current_snapshot: Snapshot, *, mark_stale: bool = True) -> RevalidationResult:
        state = self.load_state(run_id)
        expected = state["snapshot"]
        actual = current_snapshot.to_dict()
        differences: dict[str, dict[str, Any]] = {}
        for key in sorted(set(expected) | set(actual)):
            if expected.get(key) != actual.get(key):
                differences[key] = {"expected": expected.get(key), "actual": actual.get(key)}
        if not differences:
            return RevalidationResult("UNCHANGED", {})
        current_state = RunState(state["state"])
        if mark_stale and current_state not in TERMINAL_STATES:
            self.transition(run_id, RunState.STALE, current_snapshot, reason="revalidation detected changed inputs")
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

    def _persist(self, event: RunEvent) -> None:
        run_id = event.run_id
        append_jsonl(self._events_path(run_id), event.to_dict())
        checkpoint = self._dir(run_id) / "checkpoints" / f"{event.sequence:04d}-{event.state}.json"
        atomic_write_json(checkpoint, event.to_dict())
        atomic_write_json(
            self._state_path(run_id),
            {
                "run_id": run_id,
                "state": event.state,
                "sequence": event.sequence,
                "event_hash": event.event_hash,
                "snapshot": event.snapshot,
                "updated_at": event.created_at,
            },
        )

    @staticmethod
    def _verify_chain(rows: list[dict[str, Any]]) -> None:
        previous_hash = None
        for expected_sequence, row in enumerate(rows, start=1):
            if row.get("sequence") != expected_sequence:
                raise RunIntegrityError("Event sequence is not contiguous")
            if row.get("previous_event_hash") != previous_hash:
                raise RunIntegrityError("Event hash chain is broken")
            stored_hash = row.get("event_hash")
            body = {key: value for key, value in row.items() if key != "event_hash"}
            if stored_hash != hash_json(body):
                raise RunIntegrityError("Event content hash mismatch")
            previous_hash = stored_hash
