from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from executor.github_effect_transaction import (
    GitHubEffectGateway,
    GitHubEffectTransaction,
    ProviderReadResult,
    ProviderWriteResult,
    canonical_effect_bytes,
)
from executor.github_authority import GovernedAuthorityLedger, ResultBindingRecoveryRequired


class DraftPrEffectError(RuntimeError):
    pass


_BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


def _git(root: Path, *args: str, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if check and result.returncode != 0:
        raise DraftPrEffectError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json(value: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(value.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DraftPrEffectError(f"provider response is not JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise DraftPrEffectError("provider response must be an object")
    return parsed


def _effect_payload(effect_bytes: bytes) -> dict[str, Any]:
    value = _json(effect_bytes)
    return value


@dataclass(frozen=True)
class PreparedCommit:
    repository: str
    source_commit: str
    commit_sha: str
    tree_sha: str
    head_branch: str
    patch_sha256: str
    changed_paths: tuple[str, ...]


class GitHubDraftPrGateway(GitHubEffectGateway):
    """Bounded GitHub provider gateway for branch publication and draft PR creation.

    Git writes are never retried. A failed/timeout write is followed only by the
    transaction's fresh observation path. Git authentication is passed through a
    child environment rather than command-line credentials.
    """

    def __init__(
        self,
        *,
        repository: str,
        workspace: str | Path,
        token: str,
        timeout_seconds: int = 20,
    ) -> None:
        if not token:
            raise DraftPrEffectError("GitHub effect token is required")
        if repository.count("/") != 1:
            raise DraftPrEffectError("repository must use owner/name form")
        self.repository = repository
        self.workspace = Path(workspace).resolve()
        self.token = token
        self.timeout_seconds = timeout_seconds
        self.owner, self.repo = repository.split("/", 1)
        self.api = f"https://api.github.com/repos/{repository}"

    def _request(self, method: str, url: str, payload: dict[str, Any] | None = None) -> tuple[int, bytes, dict[str, str]]:
        if not url.startswith(self.api):
            raise DraftPrEffectError("GitHub effect URL escaped the bound repository")
        raw = None if payload is None else json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=raw,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "creative-os-executor/1.0",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return response.status, response.read(), dict(response.headers.items())
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), dict(exc.headers.items())
        except (OSError, urllib.error.URLError) as exc:
            raise DraftPrEffectError(f"GitHub effect request outcome is unknown: {exc}") from exc

    def _git_push(self, *, sha: str, ref: str) -> ProviderWriteResult:
        env = dict(os.environ)
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = "http.extraHeader"
        env["GIT_CONFIG_VALUE_0"] = f"Authorization: Bearer {self.token}"
        remote = f"https://github.com/{self.repository}.git"
        result = _git(
            self.workspace,
            "push",
            "--porcelain",
            remote,
            f"{sha}:{ref}",
            check=False,
            env=env,
        )
        raw = (result.stdout + "\n" + result.stderr).encode("utf-8", errors="replace")
        if result.returncode == 0:
            return ProviderWriteResult(
                provider_status=200,
                provider_message="Git protocol accepted ref publication",
                raw_response=raw,
                object_id=sha,
                object_url=f"https://github.com/{self.repository}/commit/{sha}",
            )
        # 599 is a trusted-gateway normalization for an indeterminate non-HTTP
        # Git transport failure. Recovery MUST decide by provider read-back.
        return ProviderWriteResult(
            provider_status=599,
            provider_message="Git protocol result requires provider reconciliation",
            raw_response=raw,
        )

    def write(
        self,
        *,
        action_kind: str,
        target: str,
        effect_bytes: bytes,
        correlation_id: str,
    ) -> ProviderWriteResult:
        payload = _effect_payload(effect_bytes)
        if action_kind == "CREATE_GIT_REF":
            expected_target = f"{self.repository}@{payload.get('ref')}"
            if target != expected_target or payload.get("repository") != self.repository:
                raise DraftPrEffectError("push intent differs from bound target")
            sha = payload.get("sha")
            ref = payload.get("ref")
            if not isinstance(sha, str) or _SHA40.fullmatch(sha) is None or not isinstance(ref, str):
                raise DraftPrEffectError("push intent contains invalid SHA/ref")
            return self._git_push(sha=sha, ref=ref)

        if action_kind == "CREATE_PULL_REQUEST":
            if target != self.repository or payload.get("repository") != self.repository:
                raise DraftPrEffectError("PR intent differs from bound repository")
            request_payload = {
                "title": payload["title"],
                "head": payload["head"],
                "base": payload["base"],
                "body": payload["body"],
                "draft": True,
            }
            status, raw, _ = self._request("POST", f"{self.api}/pulls", request_payload)
            if 200 <= status < 300:
                value = _json(raw)
                number = value.get("number")
                html_url = value.get("html_url")
                if not isinstance(number, int) or number <= 0 or not isinstance(html_url, str):
                    raise DraftPrEffectError("GitHub PR response lacks durable identity")
                return ProviderWriteResult(
                    provider_status=status,
                    provider_message="Draft pull request created",
                    raw_response=raw,
                    object_id=str(number),
                    object_url=html_url,
                )
            return ProviderWriteResult(
                provider_status=status,
                provider_message="GitHub rejected or could not complete draft PR creation",
                raw_response=raw,
            )
        raise DraftPrEffectError(f"unsupported gateway write: {action_kind}")

    def _observe_ref(self, payload: dict[str, Any]) -> ProviderReadResult:
        ref = payload["ref"]
        suffix = urllib.parse.quote(ref.removeprefix("refs/"), safe="/")
        status, raw, _ = self._request("GET", f"{self.api}/git/ref/{suffix}")
        if status == 404:
            return ProviderReadResult(complete=True, exists=False, raw_response=raw)
        if status != 200:
            return ProviderReadResult(complete=False, exists=False, raw_response=raw)
        value = _json(raw)
        obj = value.get("object")
        sha = obj.get("sha") if isinstance(obj, dict) else None
        if not isinstance(sha, str) or _SHA40.fullmatch(sha) is None:
            return ProviderReadResult(complete=False, exists=False, raw_response=raw)
        observed_payload = {
            "schema_version": "executor-git-ref-effect/1.0",
            "repository": self.repository,
            "ref": ref,
            "sha": sha,
        }
        return ProviderReadResult(
            complete=True,
            exists=True,
            raw_response=raw,
            observed_effect_bytes=canonical_effect_bytes(observed_payload),
            object_id=sha,
            object_url=f"https://github.com/{self.repository}/commit/{sha}",
        )

    def _observe_pr(self, payload: dict[str, Any]) -> ProviderReadResult:
        matches: list[dict[str, Any]] = []
        page = 1
        all_raw: list[bytes] = []
        while True:
            query = urllib.parse.urlencode(
                {
                    "state": "all",
                    "head": f"{self.owner}:{payload['head']}",
                    "base": payload["base"],
                    "per_page": 100,
                    "page": page,
                }
            )
            status, raw, _ = self._request("GET", f"{self.api}/pulls?{query}")
            all_raw.append(raw)
            if status != 200:
                return ProviderReadResult(complete=False, exists=False, raw_response=b"\n".join(all_raw))
            try:
                values = json.loads(raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                return ProviderReadResult(complete=False, exists=False, raw_response=b"\n".join(all_raw))
            if not isinstance(values, list):
                return ProviderReadResult(complete=False, exists=False, raw_response=b"\n".join(all_raw))
            for value in values:
                if not isinstance(value, dict):
                    continue
                head = value.get("head")
                base = value.get("base")
                if (
                    value.get("title") == payload["title"]
                    and value.get("body") == payload["body"]
                    and value.get("draft") is True
                    and isinstance(head, dict)
                    and head.get("ref") == payload["head"]
                    and isinstance(base, dict)
                    and base.get("ref") == payload["base"]
                ):
                    matches.append(value)
            if len(values) < 100:
                break
            page += 1
            if page > 100:
                return ProviderReadResult(complete=False, exists=False, raw_response=b"\n".join(all_raw))
        combined = b"\n".join(all_raw)
        if not matches:
            return ProviderReadResult(complete=True, exists=False, raw_response=combined)
        if len(matches) != 1:
            return ProviderReadResult(complete=False, exists=True, raw_response=combined)
        value = matches[0]
        number, html_url = value.get("number"), value.get("html_url")
        if not isinstance(number, int) or number <= 0 or not isinstance(html_url, str):
            return ProviderReadResult(complete=False, exists=True, raw_response=combined)
        observed_payload = {
            "schema_version": "executor-draft-pr-effect/1.0",
            "repository": self.repository,
            "base": payload["base"],
            "head": payload["head"],
            "title": payload["title"],
            "body": payload["body"],
            "draft": True,
        }
        return ProviderReadResult(
            complete=True,
            exists=True,
            raw_response=combined,
            observed_effect_bytes=canonical_effect_bytes(observed_payload),
            object_id=str(number),
            object_url=html_url,
        )

    def observe(
        self,
        *,
        action_kind: str,
        target: str,
        effect_sha256: str,
        correlation_id: str,
    ) -> ProviderReadResult:
        # The transaction hashes the canonical effect bytes; the gateway is
        # constructed for one executor run, so the exact expected payload is
        # reloaded from the persisted local intent by the effect executor and
        # installed immediately before this call.
        payload = getattr(self, "_active_effect_payload", None)
        if not isinstance(payload, dict):
            raise DraftPrEffectError("active effect payload is not bound for observation")
        if _sha256_text(canonical_effect_bytes(payload).decode("utf-8")) != effect_sha256:
            raise DraftPrEffectError("active effect payload hash differs from transaction")
        if action_kind == "CREATE_GIT_REF":
            return self._observe_ref(payload)
        if action_kind == "CREATE_PULL_REQUEST":
            return self._observe_pr(payload)
        raise DraftPrEffectError(f"unsupported gateway observation: {action_kind}")

    def bind_effect_payload(self, payload: dict[str, Any]) -> None:
        self._active_effect_payload = json.loads(json.dumps(payload))


class DraftPrEffectExecutor:
    def __init__(
        self,
        *,
        frozen_result: dict[str, Any],
        pilot_report: dict[str, Any],
        ledger: GovernedAuthorityLedger,
        evidence_directory: str | Path,
        base_branch: str = "main",
    ) -> None:
        if frozen_result.get("status") != "AUTHORIZED_AND_FROZEN":
            raise DraftPrEffectError("draft PR publication requires a frozen ACCEPT")
        contract = frozen_result.get("contract")
        if not isinstance(contract, dict):
            raise DraftPrEffectError("frozen contract is missing")
        boundary = contract.get("authority_boundary")
        if (
            not isinstance(boundary, dict)
            or boundary.get("effect") != "BOUNDED_DRAFT_PR_ONLY"
            or boundary.get("merge") is not False
            or boundary.get("deploy") is not False
            or boundary.get("release") is not False
        ):
            raise DraftPrEffectError("frozen authority does not permit bounded draft PR publication")
        if pilot_report.get("status") != "ACTION_COMPLETED_REVIEW_REQUIRED":
            raise DraftPrEffectError("only a successful review-required pilot may be published")
        if pilot_report.get("contract_sha256") != frozen_result.get("contract_sha256"):
            raise DraftPrEffectError("pilot report is bound to a different frozen contract")
        request = pilot_report.get("draft_pr_request")
        if not isinstance(request, dict) or request.get("draft") is not True or request.get("merge_allowed") is not False:
            raise DraftPrEffectError("pilot report has no bounded draft PR request")
        self.frozen_result = frozen_result
        self.contract = contract
        self.report = pilot_report
        self.request = request
        self.ledger = ledger
        self.evidence_directory = Path(evidence_directory)
        self.base_branch = base_branch

    def prepare_commit(self, workspace: str | Path) -> PreparedCommit:
        root = Path(workspace).resolve()
        source = self.report["source_commit"]
        if _git(root, "rev-parse", "HEAD").stdout.strip() != source:
            raise DraftPrEffectError("publication workspace HEAD differs from pilot source commit")
        changed = tuple(
            line[3:] for line in _git(root, "status", "--porcelain=v1", "--untracked-files=all").stdout.splitlines() if line
        )
        expected = tuple(self.report.get("changed_paths", []))
        if tuple(sorted(changed)) != tuple(sorted(expected)):
            raise DraftPrEffectError("publication workspace change set differs from verified pilot report")
        patch = _git(root, "diff", "--no-ext-diff", "--no-textconv", "--binary", source).stdout
        patch_sha = _sha256_text(patch)
        patch_record = self.report.get("patch")
        if not isinstance(patch_record, dict) or patch_record.get("sha256") != patch_sha:
            raise DraftPrEffectError("publication patch differs from verified pilot patch")
        if not expected:
            raise DraftPrEffectError("successful pilot has no changed paths")
        _git(root, "add", "--", *expected)
        title = self.request["title"]
        _git(
            root,
            "-c",
            "user.name=Creative OS Executor",
            "-c",
            "user.email=executor@localhost",
            "commit",
            "--no-gpg-sign",
            "-m",
            title,
        )
        commit_sha = _git(root, "rev-parse", "HEAD").stdout.strip()
        tree_sha = _git(root, "rev-parse", "HEAD^{tree}").stdout.strip()
        parent = _git(root, "rev-parse", "HEAD^").stdout.strip()
        if parent != source or _SHA40.fullmatch(commit_sha) is None or _SHA40.fullmatch(tree_sha) is None:
            raise DraftPrEffectError("prepared publication commit has invalid lineage")
        if _git(root, "status", "--porcelain=v1", "--untracked-files=all").stdout:
            raise DraftPrEffectError("publication workspace is not clean after commit")
        branch = self.request["head_branch"]
        if not isinstance(branch, str) or _BRANCH.fullmatch(branch) is None or ".." in branch or branch.endswith("/"):
            raise DraftPrEffectError("draft PR head branch is invalid")
        existing = _git(root, "show-ref", "--verify", f"refs/heads/{branch}", check=False)
        if existing.returncode == 0:
            raise DraftPrEffectError("local draft PR branch already exists; reconciliation required")
        _git(root, "branch", branch, commit_sha)
        return PreparedCommit(
            repository=self.report["repository"],
            source_commit=source,
            commit_sha=commit_sha,
            tree_sha=tree_sha,
            head_branch=branch,
            patch_sha256=patch_sha,
            changed_paths=expected,
        )

    def _pr_body(self, prepared: PreparedCommit, push_result: dict[str, Any]) -> str:
        evidence = {
            **self.request["body_evidence"],
            "published_commit": prepared.commit_sha,
            "published_tree": prepared.tree_sha,
            "push_effect_status": push_result["status"],
            "human_acceptance": "PENDING",
            "merge_authorized": False,
            "deploy_authorized": False,
            "release_authorized": False,
            "tag_authorized": False,
        }
        return "Executor bounded pilot result. Human review is required.\n\n```json\n" + json.dumps(evidence, indent=2, sort_keys=True) + "\n```"

    def publish(self, *, workspace: str | Path, gateway: GitHubDraftPrGateway) -> dict[str, Any]:
        prepared = self.prepare_commit(workspace)
        if gateway.repository != prepared.repository or gateway.workspace != Path(workspace).resolve():
            raise DraftPrEffectError("gateway identity differs from prepared publication")
        expires_at = self.contract["decision_evidence"]["expires_at"]
        contract_sha = self.frozen_result["contract_sha256"]

        push_payload = {
            "schema_version": "executor-git-ref-effect/1.0",
            "repository": prepared.repository,
            "ref": f"refs/heads/{prepared.head_branch}",
            "sha": prepared.commit_sha,
        }
        push_bytes = canonical_effect_bytes(push_payload)
        gateway.bind_effect_payload(push_payload)
        push = GitHubEffectTransaction(
            run_id=self.report["run_id"],
            authority_key=f"draft-pr:{contract_sha}:PUSH_DRAFT_BRANCH",
            action_kind="CREATE_GIT_REF",
            target=f"{prepared.repository}@refs/heads/{prepared.head_branch}",
            effect_bytes=push_bytes,
            not_after=expires_at,
            evidence_directory=self.evidence_directory,
            ledger=self.ledger,
        ).execute(gateway)
        if push["status"] not in {"EFFECT_COMPLETED_AND_OBSERVED", "RECOVERED_EXTERNAL_EFFECT"}:
            return {
                "status": "DRAFT_PR_PUBLICATION_INCOMPLETE",
                "stage": "PUSH_DRAFT_BRANCH",
                "push": push,
                "automatic_retry_allowed": False,
            }

        pr_payload = {
            "schema_version": "executor-draft-pr-effect/1.0",
            "repository": prepared.repository,
            "base": self.base_branch,
            "head": prepared.head_branch,
            "title": self.request["title"],
            "body": self._pr_body(prepared, push),
            "draft": True,
        }
        gateway.bind_effect_payload(pr_payload)
        pr = GitHubEffectTransaction(
            run_id=self.report["run_id"],
            authority_key=f"draft-pr:{contract_sha}:CREATE_DRAFT_PR",
            action_kind="CREATE_PULL_REQUEST",
            target=prepared.repository,
            effect_bytes=canonical_effect_bytes(pr_payload),
            not_after=expires_at,
            evidence_directory=self.evidence_directory,
            ledger=self.ledger,
        ).execute(gateway)
        if pr["status"] not in {"EFFECT_COMPLETED_AND_OBSERVED", "RECOVERED_EXTERNAL_EFFECT"}:
            return {
                "status": "DRAFT_PR_PUBLICATION_INCOMPLETE",
                "stage": "CREATE_DRAFT_PR",
                "prepared": prepared.__dict__,
                "push": push,
                "pull_request": pr,
                "automatic_retry_allowed": False,
            }
        return {
            "schema_version": "executor-draft-pr-publication-result/1.0",
            "status": "DRAFT_PR_CREATED_REVIEW_REQUIRED",
            "prepared": prepared.__dict__,
            "push": push,
            "pull_request": pr,
            "human_review_required": True,
            "human_acceptance": "PENDING",
            "merge_allowed": False,
            "deploy_allowed": False,
            "release_allowed": False,
            "tag_allowed": False,
        }
