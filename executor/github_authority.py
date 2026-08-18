from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import quote

from executor.authority_ledger import AtomicAuthorityLedger, AuthorityConsumption
from executor.github_trust import canonical_json


class GlobalAuthorityError(RuntimeError):
    pass


class GlobalAuthorityReplayError(GlobalAuthorityError):
    pass


class GlobalAuthorityExpiredError(GlobalAuthorityError):
    pass


class GlobalAuthorityHttpError(GlobalAuthorityError):
    def __init__(self, status: int, body: str):
        super().__init__(f"GitHub authority API returned HTTP {status}: {body[:500]}")
        self.status = status
        self.body = body


_AUTHORITY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")
_RECEIPT_PREFIX = "EXECUTOR_GLOBAL_AUTHORITY_RECEIPT_V1\n"


def _parse_provider_timestamp(value: str, *, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise GlobalAuthorityError(f"{label} must be a UTC Z timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise GlobalAuthorityError(f"{label} is invalid") from exc
    return parsed.astimezone(timezone.utc)


class GitHubAuthorityTransport(Protocol):
    def request_json(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...


class GitHubAuthorityRestClient:
    def __init__(self, *, token: str, timeout_seconds: int = 15):
        if not token:
            raise GlobalAuthorityError("global authority token is required")
        self._token = token
        self._timeout_seconds = timeout_seconds

    def request_json(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not url.startswith("https://api.github.com/repos/"):
            raise GlobalAuthorityError("global authority URL is outside GitHub repos API")
        raw = None
        if payload is not None:
            raw = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=raw,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "creative-os-executor/1.0",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                body = response.read().decode("utf-8")
                if not body:
                    return {}
                value = json.loads(body)
                if not isinstance(value, dict):
                    raise GlobalAuthorityError("GitHub authority response must be an object")
                return value
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise GlobalAuthorityHttpError(exc.code, body) from exc
        except (OSError, urllib.error.URLError, UnicodeError, json.JSONDecodeError) as exc:
            raise GlobalAuthorityError(f"GitHub authority request failed: {exc}") from exc


@dataclass(frozen=True)
class GlobalAuthorityReservation:
    authority_key: str
    payload_sha256: str
    action_kind: str
    run_id: str
    ref: str
    reservation_sha: str
    not_after: str | None = None
    provider_created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": "GITHUB_REF",
            "authority_key": self.authority_key,
            "payload_sha256": self.payload_sha256,
            "action_kind": self.action_kind,
            "run_id": self.run_id,
            "ref": self.ref,
            "reservation_sha": self.reservation_sha,
            "not_after": self.not_after,
            "provider_created_at": self.provider_created_at,
        }


class GitHubGlobalAuthority:
    """Provider-backed one-shot authority namespace shared by every runner/ledger."""

    def __init__(
        self,
        *,
        repository: str,
        transport: GitHubAuthorityTransport,
        parent_ref: str = "heads/main",
    ) -> None:
        if not repository or "/" not in repository:
            raise GlobalAuthorityError("authority repository must use owner/name form")
        self.repository = repository
        self.transport = transport
        self.parent_ref = parent_ref
        self.api = f"https://api.github.com/repos/{repository}"

    @classmethod
    def from_environment(cls, *, expected_repository: str) -> "GitHubGlobalAuthority":
        repository = os.environ.get("EXECUTOR_GLOBAL_AUTHORITY_REPOSITORY", "")
        token = os.environ.get("EXECUTOR_GLOBAL_AUTHORITY_TOKEN", "")
        if repository != expected_repository:
            raise GlobalAuthorityError(
                "global authority repository is missing or differs from the trust profile"
            )
        if not token:
            raise GlobalAuthorityError("global authority token is missing")
        return cls(
            repository=repository,
            transport=GitHubAuthorityRestClient(token=token),
        )

    @staticmethod
    def _validate(
        *, authority_key: str, payload_sha256: str, action_kind: str, run_id: str
    ) -> None:
        if _AUTHORITY_KEY.fullmatch(authority_key) is None:
            raise GlobalAuthorityError("global authority_key is invalid")
        if _SHA256.fullmatch(payload_sha256) is None:
            raise GlobalAuthorityError("global payload_sha256 is invalid")
        if _SAFE_VALUE.fullmatch(action_kind) is None or _SAFE_VALUE.fullmatch(run_id) is None:
            raise GlobalAuthorityError("global action_kind/run_id is invalid")

    @staticmethod
    def _ref_for(authority_key: str) -> str:
        digest = hashlib.sha256(authority_key.encode("utf-8")).hexdigest()
        return f"refs/heads/executor-authority/{digest}"

    def _get_ref(self, ref: str) -> dict[str, Any] | None:
        suffix = quote(ref.removeprefix("refs/"), safe="/")
        try:
            return self.transport.request_json("GET", f"{self.api}/git/ref/{suffix}")
        except GlobalAuthorityHttpError as exc:
            if exc.status == 404:
                return None
            raise

    def _get_commit(self, sha: str) -> dict[str, Any]:
        return self.transport.request_json("GET", f"{self.api}/git/commits/{sha}")

    @staticmethod
    def _receipt_message(receipt: dict[str, Any]) -> str:
        return _RECEIPT_PREFIX + canonical_json(receipt)

    @staticmethod
    def _parse_receipt(commit: dict[str, Any]) -> dict[str, Any]:
        message = commit.get("message")
        if not isinstance(message, str) or not message.startswith(_RECEIPT_PREFIX):
            raise GlobalAuthorityError("authority ref does not point to an Executor receipt")
        try:
            value = json.loads(message[len(_RECEIPT_PREFIX) :])
        except json.JSONDecodeError as exc:
            raise GlobalAuthorityError("authority receipt is not valid JSON") from exc
        if not isinstance(value, dict):
            raise GlobalAuthorityError("authority receipt is not an object")
        return value

    def _base_tree_and_parent(self) -> tuple[str, str]:
        ref = self.transport.request_json("GET", f"{self.api}/git/ref/{self.parent_ref}")
        obj = ref.get("object")
        if not isinstance(obj, dict) or not isinstance(obj.get("sha"), str):
            raise GlobalAuthorityError("cannot resolve authority parent ref")
        parent_sha = obj["sha"]
        commit = self._get_commit(parent_sha)
        tree = commit.get("tree")
        if not isinstance(tree, dict) or not isinstance(tree.get("sha"), str):
            raise GlobalAuthorityError("cannot resolve authority parent tree")
        return tree["sha"], parent_sha

    def reserve(
        self,
        *,
        authority_key: str,
        payload_sha256: str,
        action_kind: str,
        run_id: str,
        not_after: str | None = None,
    ) -> GlobalAuthorityReservation:
        deadline = (
            _parse_provider_timestamp(not_after, label="not_after")
            if not_after is not None
            else None
        )
        self._validate(
            authority_key=authority_key,
            payload_sha256=payload_sha256,
            action_kind=action_kind,
            run_id=run_id,
        )
        ref = self._ref_for(authority_key)
        if self._get_ref(ref) is not None:
            raise GlobalAuthorityReplayError(f"global authority already consumed: {authority_key}")
        receipt = {
            "schema_version": "executor-global-authority-receipt/1.0",
            "state": "RESERVED",
            "authority_key": authority_key,
            "payload_sha256": payload_sha256,
            "action_kind": action_kind,
            "run_id": run_id,
            "not_after": not_after,
            "result_sha256": None,
        }
        tree_sha, parent_sha = self._base_tree_and_parent()
        commit = self.transport.request_json(
            "POST",
            f"{self.api}/git/commits",
            {
                "message": self._receipt_message(receipt),
                "tree": tree_sha,
                "parents": [parent_sha],
            },
        )
        commit_sha = commit.get("sha")
        if not isinstance(commit_sha, str):
            raise GlobalAuthorityError("GitHub did not return reservation commit SHA")
        try:
            self.transport.request_json(
                "POST",
                f"{self.api}/git/refs",
                {"ref": ref, "sha": commit_sha},
            )
        except GlobalAuthorityHttpError as exc:
            if exc.status == 422 and self._get_ref(ref) is not None:
                raise GlobalAuthorityReplayError(
                    f"global authority already consumed: {authority_key}"
                ) from exc
            raise
        provider_created_at = None
        if deadline is not None:
            provider_commit = self._get_commit(commit_sha)
            committer = provider_commit.get("committer")
            if not isinstance(committer, dict):
                raise GlobalAuthorityError("provider reservation commit has no committer time")
            provider_created_at = committer.get("date")
            provider_time = _parse_provider_timestamp(
                provider_created_at,
                label="provider reservation time",
            )
            if provider_time >= deadline:
                # The one-shot ref is intentionally left spent. No local consumption or
                # consequential effect is allowed after the provider proves expiry.
                raise GlobalAuthorityExpiredError(
                    "global authority reservation occurred at or after authority expiry"
                )
        return GlobalAuthorityReservation(
            authority_key=authority_key,
            payload_sha256=payload_sha256,
            action_kind=action_kind,
            run_id=run_id,
            ref=ref,
            reservation_sha=commit_sha,
            not_after=not_after,
            provider_created_at=provider_created_at,
        )

    def finalize(
        self,
        reservation: GlobalAuthorityReservation,
        *,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        result_sha = hashlib.sha256(canonical_json(result).encode("utf-8")).hexdigest()
        current_ref = self._get_ref(reservation.ref)
        if current_ref is None:
            raise GlobalAuthorityError("global authority reservation disappeared")
        obj = current_ref.get("object")
        if not isinstance(obj, dict) or not isinstance(obj.get("sha"), str):
            raise GlobalAuthorityError("global authority ref has no commit")
        current_sha = obj["sha"]
        current_commit = self._get_commit(current_sha)
        current_receipt = self._parse_receipt(current_commit)
        expected = {
            "authority_key": reservation.authority_key,
            "payload_sha256": reservation.payload_sha256,
            "action_kind": reservation.action_kind,
            "run_id": reservation.run_id,
            "not_after": reservation.not_after,
        }
        for key, value in expected.items():
            if current_receipt.get(key) != value:
                raise GlobalAuthorityError(f"global authority receipt {key} mismatch")
        if current_receipt.get("state") == "FINAL":
            if current_receipt.get("result_sha256") == result_sha:
                return {
                    **reservation.to_dict(),
                    "state": "FINAL",
                    "final_sha": current_sha,
                    "result_sha256": result_sha,
                }
            raise GlobalAuthorityError("global authority result is already bound differently")
        if current_receipt.get("state") != "RESERVED":
            raise GlobalAuthorityError("global authority receipt state is invalid")
        tree = current_commit.get("tree")
        if not isinstance(tree, dict) or not isinstance(tree.get("sha"), str):
            raise GlobalAuthorityError("global reservation commit has no tree")
        final_receipt = {
            **current_receipt,
            "state": "FINAL",
            "result_sha256": result_sha,
        }
        final_commit = self.transport.request_json(
            "POST",
            f"{self.api}/git/commits",
            {
                "message": self._receipt_message(final_receipt),
                "tree": tree["sha"],
                "parents": [current_sha],
            },
        )
        final_sha = final_commit.get("sha")
        if not isinstance(final_sha, str):
            raise GlobalAuthorityError("GitHub did not return final receipt commit SHA")
        suffix = quote(reservation.ref.removeprefix("refs/"), safe="/")
        try:
            self.transport.request_json(
                "PATCH",
                f"{self.api}/git/refs/{suffix}",
                {"sha": final_sha, "force": False},
            )
        except GlobalAuthorityHttpError as exc:
            if exc.status != 422:
                raise
            # Concurrent exact finalization is allowed only if it reached the same result.
            latest = self._get_ref(reservation.ref)
            if latest is None:
                raise
            latest_obj = latest.get("object", {})
            latest_sha = latest_obj.get("sha")
            if not isinstance(latest_sha, str):
                raise
            latest_receipt = self._parse_receipt(self._get_commit(latest_sha))
            if latest_receipt.get("state") != "FINAL" or latest_receipt.get("result_sha256") != result_sha:
                raise GlobalAuthorityError("concurrent global result binding differs") from exc
            final_sha = latest_sha
        return {
            **reservation.to_dict(),
            "state": "FINAL",
            "final_sha": final_sha,
            "result_sha256": result_sha,
        }


@dataclass(frozen=True)
class GovernedAuthorityConsumption:
    local: AuthorityConsumption
    global_reservation: GlobalAuthorityReservation

    @property
    def execution_token(self) -> str:
        return self.local.execution_token

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.local.to_dict(),
            "global": self.global_reservation.to_dict(),
        }


class GovernedAuthorityLedger:
    """Global GitHub one-shot reservation plus local crash-safe SQLite binding."""

    def __init__(
        self,
        local: AtomicAuthorityLedger,
        global_authority: GitHubGlobalAuthority,
    ) -> None:
        self.local = local
        self.global_authority = global_authority

    def consume(
        self,
        *,
        authority_key: str,
        payload_sha256: str,
        action_kind: str,
        run_id: str,
        now: Any = None,
        not_after: str | None = None,
    ) -> GovernedAuthorityConsumption:
        reservation = self.global_authority.reserve(
            authority_key=authority_key,
            payload_sha256=payload_sha256,
            action_kind=action_kind,
            run_id=run_id,
            not_after=not_after,
        )
        local = self.local.consume(
            authority_key=authority_key,
            payload_sha256=payload_sha256,
            action_kind=action_kind,
            run_id=run_id,
            now=now,
        )
        return GovernedAuthorityConsumption(local=local, global_reservation=reservation)

    def bind_result(
        self,
        *,
        consumption: GovernedAuthorityConsumption,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        global_final = self.global_authority.finalize(
            consumption.global_reservation,
            result=result,
        )
        local_final = self.local.bind_result(
            execution_token=consumption.execution_token,
            result=result,
        )
        return {
            **local_final.to_dict(),
            "global": global_final,
        }

    def unresolved(self) -> tuple[AuthorityConsumption, ...]:
        return self.local.unresolved()
