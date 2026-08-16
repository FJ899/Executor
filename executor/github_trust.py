from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from urllib.parse import urlparse

from executor.repository_access import (
    RepositoryPathError,
    canonical_repository_path,
    validate_scope_pattern,
)
from executor.strict_json import StrictJsonError, loads_json_object


class GitHubTrustError(ValueError):
    pass


_REQUEST_SCHEMA = "executor-github-request/1.0"
_DECISION_SCHEMA = "executor-github-decision/1.0"
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_VERIFIED_EVIDENCE_PROOF = object()


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise GitHubTrustError(f"value is not canonical JSON: {exc}") from exc


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_utc(value: object, *, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise GitHubTrustError(f"{label} must be an RFC3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise GitHubTrustError(f"{label} is not a valid timestamp") from exc
    if parsed.utcoffset() != timedelta(0):
        raise GitHubTrustError(f"{label} must be UTC")
    return parsed.astimezone(timezone.utc)


def _exact_keys(value: dict[str, Any], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        raise GitHubTrustError(
            f"{label} keys differ; missing={sorted(expected - set(value))}, "
            f"additional={sorted(set(value) - expected)}"
        )


def _command_list(value: object, *, label: str) -> tuple[tuple[str, ...], ...]:
    if not isinstance(value, list) or not value:
        raise GitHubTrustError(f"{label} must be a non-empty list")
    commands: list[tuple[str, ...]] = []
    for index, command in enumerate(value):
        if (
            not isinstance(command, list)
            or not command
            or not all(
                isinstance(item, str) and item and "\x00" not in item
                for item in command
            )
        ):
            raise GitHubTrustError(
                f"{label}[{index}] must be a non-empty NUL-free argv list"
            )
        commands.append(tuple(command))
    return tuple(commands)


class GitHubEvidenceSource(Protocol):
    def fetch_json(self, url: str) -> dict[str, Any]:
        ...


class GitHubRestClient:
    """Fetch current GitHub evidence through the provider's HTTPS API."""

    def __init__(self, *, token: str | None = None, timeout_seconds: int = 15):
        self._token = token
        self._timeout_seconds = timeout_seconds

    def fetch_json(self, url: str) -> dict[str, Any]:
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "api.github.com"
            or not parsed.path.startswith("/repos/")
            or parsed.query
            or parsed.fragment
        ):
            raise GitHubTrustError("GitHub evidence URL is outside api.github.com/repos")
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "creative-os-executor/1.0",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                if response.status != 200:
                    raise GitHubTrustError(
                        f"GitHub evidence fetch returned HTTP {response.status}"
                    )
                raw = response.read()
        except (OSError, urllib.error.URLError) as exc:
            raise GitHubTrustError(f"GitHub evidence fetch failed: {exc}") from exc
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise GitHubTrustError("GitHub evidence response is not JSON") from exc
        if not isinstance(payload, dict):
            raise GitHubTrustError("GitHub evidence response must be an object")
        return payload


@dataclass(frozen=True)
class GitHubTrustProfile:
    profile_id: str
    intake_repository: str
    allowed_actor_login: str
    allowed_actor_id: int
    allowed_target_repositories: tuple[str, ...]
    max_decision_lifetime_seconds: int = 3600

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GitHubTrustProfile":
        _exact_keys(
            value,
            {
                "schema_version",
                "profile_id",
                "intake_repository",
                "allowed_actor",
                "allowed_target_repositories",
                "max_decision_lifetime_seconds",
            },
            label="GitHub trust profile",
        )
        if value.get("schema_version") != "executor-github-trust-profile/1.0":
            raise GitHubTrustError("unsupported GitHub trust profile schema")
        actor = value.get("allowed_actor")
        if not isinstance(actor, dict):
            raise GitHubTrustError("allowed_actor must be an object")
        _exact_keys(actor, {"login", "id"}, label="allowed_actor")
        profile_id = value.get("profile_id")
        intake = value.get("intake_repository")
        login = actor.get("login")
        actor_id = actor.get("id")
        targets = value.get("allowed_target_repositories")
        maximum = value.get("max_decision_lifetime_seconds")
        if not isinstance(profile_id, str) or _SAFE_ID.fullmatch(profile_id) is None:
            raise GitHubTrustError("profile_id is invalid")
        if not isinstance(intake, str) or _REPOSITORY.fullmatch(intake) is None:
            raise GitHubTrustError("intake_repository must use owner/name form")
        if not isinstance(login, str) or not login or type(actor_id) is not int:
            raise GitHubTrustError("allowed_actor login/id are invalid")
        if (
            not isinstance(targets, list)
            or not targets
            or not all(
                isinstance(item, str) and _REPOSITORY.fullmatch(item)
                for item in targets
            )
            or len({item.lower() for item in targets}) != len(targets)
        ):
            raise GitHubTrustError("allowed_target_repositories are invalid")
        if type(maximum) is not int or not 60 <= maximum <= 86400:
            raise GitHubTrustError(
                "max_decision_lifetime_seconds must be in 60..86400"
            )
        return cls(
            profile_id=profile_id,
            intake_repository=intake,
            allowed_actor_login=login,
            allowed_actor_id=actor_id,
            allowed_target_repositories=tuple(targets),
            max_decision_lifetime_seconds=maximum,
        )


@dataclass(frozen=True)
class VerifiedGitHubRequest:
    profile_id: str
    repository: str
    issue_number: int
    issue_id: int
    issue_node_id: str
    actor_login: str
    actor_id: int
    body_sha256: str
    created_at: str
    observed_at: str
    payload: dict[str, Any]
    _proof: object = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self._proof is not _VERIFIED_EVIDENCE_PROOF:
            raise GitHubTrustError(
                "VerifiedGitHubRequest must be created by verify_github_request"
            )

    @property
    def evidence_ref(self) -> str:
        return f"github:issue:{self.issue_node_id}:{self.body_sha256}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": "GITHUB",
            "profile_id": self.profile_id,
            "repository": self.repository,
            "issue_number": self.issue_number,
            "issue_id": self.issue_id,
            "issue_node_id": self.issue_node_id,
            "actor": {"login": self.actor_login, "id": self.actor_id},
            "body_sha256": self.body_sha256,
            "created_at": self.created_at,
            "observed_at": self.observed_at,
            "evidence_ref": self.evidence_ref,
        }


@dataclass(frozen=True)
class VerifiedGitHubDecision:
    profile_id: str
    repository: str
    issue_number: int
    comment_id: int
    comment_node_id: str
    actor_login: str
    actor_id: int
    body_sha256: str
    decision: str
    draft_sha256: str
    created_at: str
    expires_at: str
    observed_at: str
    payload: dict[str, Any]
    _proof: object = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self._proof is not _VERIFIED_EVIDENCE_PROOF:
            raise GitHubTrustError(
                "VerifiedGitHubDecision must be created by verify_github_decision"
            )

    @property
    def evidence_ref(self) -> str:
        return f"github:comment:{self.comment_node_id}:{self.body_sha256}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": "GITHUB",
            "profile_id": self.profile_id,
            "repository": self.repository,
            "issue_number": self.issue_number,
            "comment_id": self.comment_id,
            "comment_node_id": self.comment_node_id,
            "actor": {"login": self.actor_login, "id": self.actor_id},
            "body_sha256": self.body_sha256,
            "decision": self.decision,
            "draft_sha256": self.draft_sha256,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "observed_at": self.observed_at,
            "evidence_ref": self.evidence_ref,
        }


def _verify_actor(
    event: dict[str, Any],
    *,
    profile: GitHubTrustProfile,
    label: str,
) -> tuple[str, int]:
    actor = event.get("user")
    if not isinstance(actor, dict):
        raise GitHubTrustError(f"{label} has no GitHub actor")
    login = actor.get("login")
    actor_id = actor.get("id")
    if (
        actor.get("type") != "User"
        or login != profile.allowed_actor_login
        or actor_id != profile.allowed_actor_id
    ):
        raise GitHubTrustError(f"{label} actor is not the allowed GitHub user")
    if event.get("author_association") not in {"OWNER", "MEMBER", "COLLABORATOR"}:
        raise GitHubTrustError(f"{label} actor lacks governed repository association")
    return login, actor_id


def _validate_request_payload(
    payload: dict[str, Any],
    *,
    profile: GitHubTrustProfile,
    now: datetime,
) -> None:
    _exact_keys(
        payload,
        {
            "schema_version",
            "request_id",
            "target",
            "task",
            "expires_at",
            "nonce",
        },
        label="request payload",
    )
    if payload.get("schema_version") != _REQUEST_SCHEMA:
        raise GitHubTrustError("unsupported GitHub request schema")
    if not isinstance(payload.get("request_id"), str) or _SAFE_ID.fullmatch(
        payload["request_id"]
    ) is None:
        raise GitHubTrustError("request_id is invalid")
    if not isinstance(payload.get("nonce"), str) or _SAFE_ID.fullmatch(
        payload["nonce"]
    ) is None:
        raise GitHubTrustError("request nonce is invalid")
    expires = _parse_utc(payload.get("expires_at"), label="request expires_at")
    if expires <= now:
        raise GitHubTrustError("GitHub request has expired")

    target = payload.get("target")
    if not isinstance(target, dict):
        raise GitHubTrustError("request target must be an object")
    _exact_keys(target, {"repository", "commit", "tree"}, label="request target")
    repository = target.get("repository")
    if (
        not isinstance(repository, str)
        or repository.lower()
        not in {item.lower() for item in profile.allowed_target_repositories}
    ):
        raise GitHubTrustError("request target repository is outside the trust profile")
    for key in ("commit", "tree"):
        value = target.get(key)
        if not isinstance(value, str) or _GIT_SHA.fullmatch(value) is None:
            raise GitHubTrustError(f"request target {key} must be a Git SHA")

    task = payload.get("task")
    if not isinstance(task, dict):
        raise GitHubTrustError("request task must be an object")
    _exact_keys(
        task,
        {
            "class",
            "problem_statement",
            "allowed_paths",
            "protected_paths",
            "precondition_argv",
            "postcondition_argv",
            "regression_argv",
            "max_production_files",
            "max_patch_lines",
        },
        label="request task",
    )
    if task.get("class") != "BOUNDED_CORRECTNESS_OR_QUALITY_FIX":
        raise GitHubTrustError("request task class is unsupported")
    if not isinstance(task.get("problem_statement"), str) or not task[
        "problem_statement"
    ].strip():
        raise GitHubTrustError("request problem_statement is required")
    maximum = task.get("max_production_files")
    if type(maximum) is not int or not 1 <= maximum <= 3:
        raise GitHubTrustError("max_production_files must be in 1..3")
    patch_lines = task.get("max_patch_lines")
    if type(patch_lines) is not int or not 1 <= patch_lines <= 500:
        raise GitHubTrustError("max_patch_lines must be in 1..500")
    allowed = task.get("allowed_paths")
    if (
        not isinstance(allowed, list)
        or not 1 <= len(allowed) <= maximum
        or not all(isinstance(item, str) and item for item in allowed)
    ):
        raise GitHubTrustError("allowed_paths exceed the bounded task class")
    try:
        canonical_allowed = [canonical_repository_path(item) for item in allowed]
    except RepositoryPathError as exc:
        raise GitHubTrustError(f"invalid allowed path: {exc}") from exc
    if len(set(canonical_allowed)) != len(canonical_allowed):
        raise GitHubTrustError("allowed_paths must be unique")
    protected = task.get("protected_paths")
    if not isinstance(protected, list) or not all(
        isinstance(item, str) and item for item in protected
    ):
        raise GitHubTrustError("protected_paths must be a list")
    try:
        for pattern in protected:
            validate_scope_pattern(pattern)
    except RepositoryPathError as exc:
        raise GitHubTrustError(f"invalid protected path: {exc}") from exc
    _command_list(task.get("precondition_argv"), label="precondition_argv")
    _command_list(task.get("postcondition_argv"), label="postcondition_argv")
    _command_list(task.get("regression_argv"), label="regression_argv")


def verify_github_request(
    source: GitHubEvidenceSource,
    *,
    profile: GitHubTrustProfile,
    issue_number: int,
    now: datetime | None = None,
) -> VerifiedGitHubRequest:
    if type(issue_number) is not int or issue_number <= 0:
        raise GitHubTrustError("issue_number must be a positive integer")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    api_url = (
        f"https://api.github.com/repos/{profile.intake_repository}/issues/"
        f"{issue_number}"
    )
    issue = source.fetch_json(api_url)
    expected_repo_url = f"https://api.github.com/repos/{profile.intake_repository}"
    if (
        issue.get("url") != api_url
        or issue.get("repository_url") != expected_repo_url
        or issue.get("number") != issue_number
        or "pull_request" in issue
    ):
        raise GitHubTrustError("GitHub issue identity does not match the intake request")
    if issue.get("state") != "open":
        raise GitHubTrustError("GitHub request issue must remain open")
    login, actor_id = _verify_actor(issue, profile=profile, label="request")
    body = issue.get("body")
    if not isinstance(body, str) or not body:
        raise GitHubTrustError("GitHub request body is missing")
    try:
        payload = loads_json_object(body)
    except StrictJsonError as exc:
        raise GitHubTrustError(f"GitHub request body is invalid: {exc}") from exc
    _validate_request_payload(payload, profile=profile, now=current)
    target = payload["target"]
    commit_url = (
        f"https://api.github.com/repos/{target['repository']}/git/commits/"
        f"{target['commit']}"
    )
    commit = source.fetch_json(commit_url)
    commit_tree = commit.get("tree")
    if (
        commit.get("sha") != target["commit"]
        or not isinstance(commit_tree, dict)
        or commit_tree.get("sha") != target["tree"]
    ):
        raise GitHubTrustError(
            "GitHub request commit/tree binding does not match the provider"
        )
    created_at = issue.get("created_at")
    created = _parse_utc(created_at, label="request created_at")
    if created > current + timedelta(minutes=5):
        raise GitHubTrustError("GitHub request event is from the future")
    issue_id = issue.get("id")
    node_id = issue.get("node_id")
    if type(issue_id) is not int or not isinstance(node_id, str) or not node_id:
        raise GitHubTrustError("GitHub request lacks immutable event identity")
    return VerifiedGitHubRequest(
        profile_id=profile.profile_id,
        repository=profile.intake_repository,
        issue_number=issue_number,
        issue_id=issue_id,
        issue_node_id=node_id,
        actor_login=login,
        actor_id=actor_id,
        body_sha256=sha256_text(body),
        created_at=created_at,
        observed_at=current.isoformat().replace("+00:00", "Z"),
        payload=payload,
        _proof=_VERIFIED_EVIDENCE_PROOF,
    )


def verify_github_decision(
    source: GitHubEvidenceSource,
    *,
    profile: GitHubTrustProfile,
    request: VerifiedGitHubRequest,
    comment_id: int,
    draft_sha256: str,
    now: datetime | None = None,
) -> VerifiedGitHubDecision:
    if request.profile_id != profile.profile_id:
        raise GitHubTrustError("request was verified under a different trust profile")
    if type(comment_id) is not int or comment_id <= 0:
        raise GitHubTrustError("comment_id must be a positive integer")
    if _SHA256.fullmatch(draft_sha256) is None:
        raise GitHubTrustError("draft_sha256 is invalid")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    api_url = (
        f"https://api.github.com/repos/{profile.intake_repository}/issues/comments/"
        f"{comment_id}"
    )
    comment = source.fetch_json(api_url)
    issue_url = (
        f"https://api.github.com/repos/{profile.intake_repository}/issues/"
        f"{request.issue_number}"
    )
    if comment.get("url") != api_url or comment.get("issue_url") != issue_url:
        raise GitHubTrustError("GitHub decision is attached to the wrong request")
    login, actor_id = _verify_actor(comment, profile=profile, label="decision")
    if (login, actor_id) != (request.actor_login, request.actor_id):
        raise GitHubTrustError("request and decision actors differ")
    body = comment.get("body")
    if not isinstance(body, str) or not body:
        raise GitHubTrustError("GitHub decision body is missing")
    try:
        payload = loads_json_object(body)
    except StrictJsonError as exc:
        raise GitHubTrustError(f"GitHub decision body is invalid: {exc}") from exc
    _exact_keys(
        payload,
        {
            "schema_version",
            "request",
            "draft_sha256",
            "decision",
            "valid_for_seconds",
            "nonce",
        },
        label="decision payload",
    )
    if payload.get("schema_version") != _DECISION_SCHEMA:
        raise GitHubTrustError("unsupported GitHub decision schema")
    if payload.get("decision") not in {"ACCEPT", "MODIFY", "REJECT"}:
        raise GitHubTrustError("GitHub decision must be ACCEPT, MODIFY or REJECT")
    if payload.get("draft_sha256") != draft_sha256:
        raise GitHubTrustError("GitHub decision is bound to a different draft")
    if not isinstance(payload.get("nonce"), str) or _SAFE_ID.fullmatch(
        payload["nonce"]
    ) is None:
        raise GitHubTrustError("decision nonce is invalid")
    valid_for_seconds = payload.get("valid_for_seconds")
    if type(valid_for_seconds) is not int or not (
        60 <= valid_for_seconds <= profile.max_decision_lifetime_seconds
    ):
        raise GitHubTrustError(
            "decision valid_for_seconds exceeds the trust profile"
        )
    request_ref = payload.get("request")
    if not isinstance(request_ref, dict):
        raise GitHubTrustError("decision request binding must be an object")
    _exact_keys(
        request_ref,
        {"repository", "issue_number", "issue_node_id", "body_sha256"},
        label="decision request binding",
    )
    if request_ref != {
        "repository": request.repository,
        "issue_number": request.issue_number,
        "issue_node_id": request.issue_node_id,
        "body_sha256": request.body_sha256,
    }:
        raise GitHubTrustError("GitHub decision request binding is stale or mismatched")
    created_at = comment.get("created_at")
    updated_at = comment.get("updated_at")
    if created_at != updated_at:
        raise GitHubTrustError("edited GitHub decisions are not accepted")
    created = _parse_utc(created_at, label="decision created_at")
    expires = created + timedelta(seconds=valid_for_seconds)
    if created > current + timedelta(minutes=5) or expires <= current:
        raise GitHubTrustError("GitHub decision is not currently fresh")
    comment_node_id = comment.get("node_id")
    if type(comment.get("id")) is not int or not isinstance(comment_node_id, str):
        raise GitHubTrustError("GitHub decision lacks immutable event identity")
    return VerifiedGitHubDecision(
        profile_id=profile.profile_id,
        repository=request.repository,
        issue_number=request.issue_number,
        comment_id=comment["id"],
        comment_node_id=comment_node_id,
        actor_login=login,
        actor_id=actor_id,
        body_sha256=sha256_text(body),
        decision=payload["decision"],
        draft_sha256=draft_sha256,
        created_at=created_at,
        expires_at=expires.isoformat().replace("+00:00", "Z"),
        observed_at=current.isoformat().replace("+00:00", "Z"),
        payload=payload,
        _proof=_VERIFIED_EVIDENCE_PROOF,
    )
