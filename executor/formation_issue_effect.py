from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from executor.github_authority import GovernedAuthorityLedger
from executor.github_effect_transaction import (
    GitHubEffectGateway,
    GitHubEffectTransaction,
    ProviderReadResult,
    ProviderWriteResult,
    canonical_effect_bytes,
)
from executor.github_trust import canonical_json


class FormationIssueEffectError(RuntimeError):
    pass


@dataclass
class FormationIssueGateway(GitHubEffectGateway):
    repository: str
    token: str
    timeout_seconds: int = 20

    def __post_init__(self) -> None:
        if self.repository.count("/") != 1:
            raise FormationIssueEffectError("repository must use owner/name form")
        if not self.token:
            raise FormationIssueEffectError("GitHub token is required")
        self.owner, self.repo = self.repository.split("/", 1)
        self.api = f"https://api.github.com/repos/{self.repository}"
        self._active_effect_payload: dict[str, Any] | None = None

    def bind_effect_payload(self, payload: dict[str, Any]) -> None:
        self._active_effect_payload = json.loads(json.dumps(payload))

    def _request(self, method: str, url: str, payload: dict[str, Any] | None = None) -> tuple[int, bytes]:
        if not url.startswith(self.api):
            raise FormationIssueEffectError("GitHub URL escaped the bound repository")
        body = None if payload is None else json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
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
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()
        except (OSError, urllib.error.URLError) as exc:
            raise FormationIssueEffectError(f"GitHub request outcome is unknown: {exc}") from exc

    def write(
        self,
        *,
        action_kind: str,
        target: str,
        effect_bytes: bytes,
        correlation_id: str,
    ) -> ProviderWriteResult:
        if action_kind != "CREATE_ISSUE" or target != self.repository:
            raise FormationIssueEffectError("gateway only permits CREATE_ISSUE in its bound repository")
        try:
            payload = json.loads(effect_bytes.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise FormationIssueEffectError("formation issue effect is not JSON") from exc
        if payload != self._active_effect_payload:
            raise FormationIssueEffectError("effect bytes differ from bound formation issue payload")
        status, raw = self._request(
            "POST",
            f"{self.api}/issues",
            {"title": payload["title"], "body": payload["body"]},
        )
        if 200 <= status < 300:
            value = json.loads(raw.decode("utf-8"))
            number, url = value.get("number"), value.get("html_url")
            if not isinstance(number, int) or number <= 0 or not isinstance(url, str):
                raise FormationIssueEffectError("GitHub issue response lacks durable identity")
            return ProviderWriteResult(
                provider_status=status,
                provider_message="Canonical formation authority issue created",
                raw_response=raw,
                object_id=str(number),
                object_url=url,
            )
        return ProviderWriteResult(
            provider_status=status,
            provider_message="GitHub did not confirm authority issue creation",
            raw_response=raw,
        )

    def observe(
        self,
        *,
        action_kind: str,
        target: str,
        effect_sha256: str,
        correlation_id: str,
    ) -> ProviderReadResult:
        payload = self._active_effect_payload
        if action_kind != "CREATE_ISSUE" or target != self.repository or not isinstance(payload, dict):
            raise FormationIssueEffectError("formation issue observation is not bound")
        matches: list[dict[str, Any]] = []
        page = 1
        raw_pages: list[bytes] = []
        while True:
            query = urllib.parse.urlencode({"state": "all", "per_page": 100, "page": page})
            status, raw = self._request("GET", f"{self.api}/issues?{query}")
            raw_pages.append(raw)
            if status != 200:
                return ProviderReadResult(complete=False, exists=False, raw_response=b"\n".join(raw_pages))
            try:
                values = json.loads(raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                return ProviderReadResult(complete=False, exists=False, raw_response=b"\n".join(raw_pages))
            if not isinstance(values, list):
                return ProviderReadResult(complete=False, exists=False, raw_response=b"\n".join(raw_pages))
            for value in values:
                if not isinstance(value, dict) or "pull_request" in value:
                    continue
                if value.get("title") == payload["title"] and value.get("body") == payload["body"]:
                    matches.append(value)
            if len(values) < 100:
                break
            page += 1
            if page > 100:
                return ProviderReadResult(complete=False, exists=False, raw_response=b"\n".join(raw_pages))
        combined = b"\n".join(raw_pages)
        if not matches:
            return ProviderReadResult(complete=True, exists=False, raw_response=combined)
        if len(matches) != 1:
            return ProviderReadResult(complete=False, exists=True, raw_response=combined)
        value = matches[0]
        number, url = value.get("number"), value.get("html_url")
        if not isinstance(number, int) or number <= 0 or not isinstance(url, str):
            return ProviderReadResult(complete=False, exists=True, raw_response=combined)
        return ProviderReadResult(
            complete=True,
            exists=True,
            raw_response=combined,
            observed_effect_bytes=canonical_effect_bytes(payload),
            object_id=str(number),
            object_url=url,
        )


@dataclass
class FormationRequestPublisher:
    ledger: GovernedAuthorityLedger
    evidence_directory: Path

    def publish(
        self,
        *,
        authorization_request: dict[str, Any],
        gateway: FormationIssueGateway,
    ) -> dict[str, Any]:
        canonical = authorization_request.get("canonical_contract_request")
        if not isinstance(canonical, dict):
            raise FormationIssueEffectError("formation authorization request lacks canonical contract request")
        if canonical.get("status") != "AWAITING_VERIFIED_HUMAN_AUTHORIZATION" or canonical.get("executable") is not False:
            raise FormationIssueEffectError("only a non-executable awaiting formation request may be published")
        payload = canonical.get("github_request_payload")
        binding = canonical.get("formation_binding")
        if not isinstance(payload, dict) or not isinstance(binding, dict):
            raise FormationIssueEffectError("canonical request/binding is incomplete")
        if gateway.repository != "FJ899/Executor":
            raise FormationIssueEffectError("current GP001 intake authority is FJ899/Executor")

        issue_payload = {
            "schema_version": "executor-formation-authority-issue/1.0",
            "title": f"Executor authority request: {payload['request_id']}",
            # Body transport is byte-semantically derived from the formation payload.
            # The issue itself is NOT human authority; only a later verified decision is.
            "body": canonical_json(payload),
        }
        gateway.bind_effect_payload(issue_payload)
        effect_bytes = canonical_effect_bytes(issue_payload)
        draft_sha = binding.get("draft_sha256")
        expires_at = payload.get("expires_at")
        if not isinstance(draft_sha, str) or not isinstance(expires_at, str):
            raise FormationIssueEffectError("formation binding lacks draft/expiry")
        result = GitHubEffectTransaction(
            run_id=f"FORM-{payload['request_id']}",
            authority_key=f"formation:{draft_sha}:CREATE_AUTHORITY_ISSUE",
            action_kind="CREATE_ISSUE",
            target=gateway.repository,
            effect_bytes=effect_bytes,
            not_after=expires_at,
            evidence_directory=self.evidence_directory,
            ledger=self.ledger,
        ).execute(gateway)
        completed = result.get("status") in {
            "EFFECT_COMPLETED_AND_OBSERVED",
            "RECOVERED_EXTERNAL_EFFECT",
        }
        transport = {
            "origin": "FORMATION_PUBLISHED_REQUEST",
            "authority": False,
            "publisher": "EXECUTOR_FORMATION",
            "provider": "GITHUB",
            "action_kind": "CREATE_ISSUE",
            "target": gateway.repository,
            "object_id": result.get("object_id"),
            "object_url": result.get("object_url"),
            "effect_sha256": result.get("effect_sha256"),
            "observation_ref": result.get("observation_ref"),
            "human_decision_required": True,
        }
        return {
            "schema_version": "executor-formation-publication-result/1.1",
            "status": (
                "AWAITING_VERIFIED_HUMAN_DECISION"
                if completed
                else "FORMATION_PUBLICATION_INCOMPLETE"
            ),
            "canonical_contract_request": canonical,
            "formation_binding": binding,
            "github_request_payload": payload,
            "request_transport_provenance": transport,
            "publication_effect": result,
            "manual_request_rewrite_required": False,
            "executable": False,
        }
