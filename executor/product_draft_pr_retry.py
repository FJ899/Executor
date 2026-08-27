from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from executor.draft_pr_effect import (
    DraftPrEffectError,
    DraftPrEffectExecutor,
    PreparedCommit,
    _BRANCH,
    _SHA40,
    _git,
    _sha256_text,
)
from executor.github_effect_transaction import GitHubEffectTransaction, canonical_effect_bytes
from executor.github_trust import (
    GitHubEvidenceSource,
    GitHubTrustError,
    GitHubTrustProfile,
    _SAFE_ID,
    _SHA256,
    _exact_keys,
    _parse_utc,
    _verify_actor,
    sha256_text,
)
from executor.product_draft_pr_gateway import ProductGitHubDraftPrGateway
from executor.strict_json import StrictJsonError, loads_json_object


class DraftPrRetryError(RuntimeError):
    pass


_REAUTH_PROOF = object()


@dataclass(frozen=True)
class VerifiedDraftPrReauthorization:
    profile_id: str
    repository: str
    issue_number: int
    comment_id: int
    comment_node_id: str
    actor_login: str
    actor_id: int
    body_sha256: str
    contract_sha256: str
    pilot_run_id: str
    push_effect_sha256: str
    pull_request_effect_sha256: str
    created_at: str
    expires_at: str
    payload: dict[str, Any]
    _proof: object = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self._proof is not _REAUTH_PROOF:
            raise DraftPrRetryError("verified reauthorization must come from GitHub verifier")

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
            "contract_sha256": self.contract_sha256,
            "pilot_run_id": self.pilot_run_id,
            "push_effect_sha256": self.push_effect_sha256,
            "pull_request_effect_sha256": self.pull_request_effect_sha256,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


def _canonical_sha256(value: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_effect_bytes(value)).hexdigest()


def _prepared_record(prepared: PreparedCommit) -> dict[str, Any]:
    """Canonical JSON-safe identity for a Human-reviewed prepared commit."""

    return {
        "repository": prepared.repository,
        "source_commit": prepared.source_commit,
        "commit_sha": prepared.commit_sha,
        "tree_sha": prepared.tree_sha,
        "head_branch": prepared.head_branch,
        "patch_sha256": prepared.patch_sha256,
        "changed_paths": list(prepared.changed_paths),
    }


def _validate_prior_no_effect(
    prior_publication: dict[str, Any],
    *,
    contract_sha256: str,
    pilot_run_id: str,
) -> dict[str, Any]:
    if prior_publication.get("status") != "DRAFT_PR_PUBLICATION_INCOMPLETE":
        raise DraftPrRetryError("retry requires an incomplete prior publication")
    if prior_publication.get("stage") != "PUSH_DRAFT_BRANCH":
        raise DraftPrRetryError("retry supports only a confirmed no-effect push failure")
    if prior_publication.get("automatic_retry_allowed") is not False:
        raise DraftPrRetryError("prior publication did not fail closed")
    push = prior_publication.get("push")
    if not isinstance(push, dict) or push.get("status") != "NO_EFFECT_CONFIRMED":
        raise DraftPrRetryError("prior push is not NO_EFFECT_CONFIRMED")
    if push.get("automatic_retry_allowed") is not False or push.get("next_attempt_requires_new_authority") is not True:
        raise DraftPrRetryError("prior push does not require fresh Human authority")
    if push.get("provider") != "GITHUB" or push.get("action_kind") != "CREATE_GIT_REF":
        raise DraftPrRetryError("prior push provider/action identity differs")
    if not isinstance(push.get("effect_sha256"), str) or _SHA256.fullmatch(push["effect_sha256"]) is None:
        raise DraftPrRetryError("prior push effect hash is invalid")
    if not isinstance(push.get("attempt_id"), str) or not push["attempt_id"].startswith("ose-"):
        raise DraftPrRetryError("prior push attempt identity is invalid")
    absence = push.get("absence_observation")
    if not isinstance(absence, dict):
        raise DraftPrRetryError("prior push lacks independent absence observation")
    if absence.get("complete") is not True or absence.get("exists") is not False:
        raise DraftPrRetryError("prior provider observation does not prove no effect")
    if absence.get("action_kind") != "CREATE_GIT_REF" or absence.get("target") != push.get("target"):
        raise DraftPrRetryError("prior absence observation target differs")
    if absence.get("attempt_id") != push.get("attempt_id") or absence.get("effect_sha256") != push.get("effect_sha256"):
        raise DraftPrRetryError("prior absence observation is not bound to the failed attempt")
    if not isinstance(absence.get("evidence_sha256"), str) or _SHA256.fullmatch(absence["evidence_sha256"]) is None:
        raise DraftPrRetryError("prior absence evidence hash is invalid")
    binding = push.get("authority_result_binding")
    if not isinstance(binding, dict):
        raise DraftPrRetryError("prior push lacks final authority result binding")
    expected_key = f"draft-pr:{contract_sha256}:PUSH_DRAFT_BRANCH"
    if binding.get("authority_key") != expected_key:
        raise DraftPrRetryError("prior push authority key differs from frozen contract")
    if binding.get("run_id") != pilot_run_id or binding.get("payload_sha256") != push.get("effect_sha256"):
        raise DraftPrRetryError("prior push authority result binding differs from pilot/effect")
    if binding.get("state") != "FINAL" or binding.get("binding_scope") != "GLOBAL_AND_LOCAL_COMPOSITE":
        raise DraftPrRetryError("prior push authority result is not final and fully bound")
    if not isinstance(binding.get("result_sha256"), str) or _SHA256.fullmatch(binding["result_sha256"]) is None:
        raise DraftPrRetryError("prior push result hash is invalid")
    return push


def verify_draft_pr_reauthorization(
    source: GitHubEvidenceSource,
    *,
    profile: GitHubTrustProfile,
    frozen_result: dict[str, Any],
    pilot_report: dict[str, Any],
    prior_publication: dict[str, Any],
    retry_plan: dict[str, Any],
    comment_id: int,
    now: datetime | None = None,
) -> VerifiedDraftPrReauthorization:
    contract_sha = frozen_result.get("contract_sha256")
    if not isinstance(contract_sha, str) or _SHA256.fullmatch(contract_sha) is None:
        raise DraftPrRetryError("frozen contract hash is invalid")
    if pilot_report.get("contract_sha256") != contract_sha:
        raise DraftPrRetryError("pilot report differs from frozen contract")
    if pilot_report.get("status") != "ACTION_COMPLETED_REVIEW_REQUIRED":
        raise DraftPrRetryError("reauthorization requires a successful pilot")
    run_id = pilot_report.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise DraftPrRetryError("pilot run identity is invalid")
    prior_push = _validate_prior_no_effect(
        prior_publication,
        contract_sha256=contract_sha,
        pilot_run_id=run_id,
    )
    if retry_plan.get("schema_version") != "executor-draft-pr-retry-plan/1.0":
        raise DraftPrRetryError("unsupported retry plan")
    if retry_plan.get("contract_sha256") != contract_sha or retry_plan.get("pilot_run_id") != run_id:
        raise DraftPrRetryError("retry plan binding differs from frozen pilot")
    push_plan = retry_plan.get("push")
    pr_plan = retry_plan.get("pull_request")
    if not isinstance(push_plan, dict) or not isinstance(pr_plan, dict):
        raise DraftPrRetryError("retry plan lacks exact push/PR effects")
    for item, action in ((push_plan, "CREATE_GIT_REF"), (pr_plan, "CREATE_PULL_REQUEST")):
        if item.get("action_kind") != action:
            raise DraftPrRetryError("retry plan action kind differs")
        if not isinstance(item.get("effect_sha256"), str) or _SHA256.fullmatch(item["effect_sha256"]) is None:
            raise DraftPrRetryError("retry plan effect hash is invalid")
        payload = item.get("payload")
        if not isinstance(payload, dict) or _canonical_sha256(payload) != item["effect_sha256"]:
            raise DraftPrRetryError("retry plan payload hash differs")

    contract = frozen_result.get("contract")
    request_evidence = contract.get("request_evidence") if isinstance(contract, dict) else None
    if not isinstance(request_evidence, dict):
        raise DraftPrRetryError("frozen contract lacks request evidence")
    issue_number = request_evidence.get("issue_number")
    issue_node_id = request_evidence.get("issue_node_id")
    request_body_sha = request_evidence.get("body_sha256")
    if type(issue_number) is not int or issue_number <= 0 or not isinstance(issue_node_id, str) or not isinstance(request_body_sha, str):
        raise DraftPrRetryError("frozen request evidence identity is invalid")
    if type(comment_id) is not int or comment_id <= 0:
        raise DraftPrRetryError("reauthorization comment_id must be positive")

    api_url = f"https://api.github.com/repos/{profile.intake_repository}/issues/comments/{comment_id}"
    issue_url = f"https://api.github.com/repos/{profile.intake_repository}/issues/{issue_number}"
    comment = source.fetch_json(api_url)
    if comment.get("url") != api_url or comment.get("issue_url") != issue_url:
        raise DraftPrRetryError("reauthorization comment is attached to the wrong request")
    try:
        login, actor_id = _verify_actor(comment, profile=profile, label="effect reauthorization")
    except GitHubTrustError as exc:
        raise DraftPrRetryError(str(exc)) from exc
    body = comment.get("body")
    if not isinstance(body, str) or not body:
        raise DraftPrRetryError("effect reauthorization body is missing")
    try:
        payload = loads_json_object(body)
    except StrictJsonError as exc:
        raise DraftPrRetryError(f"effect reauthorization body is invalid: {exc}") from exc
    try:
        _exact_keys(
            payload,
            {
                "schema_version",
                "request",
                "contract_sha256",
                "pilot_run_id",
                "prior_no_effect",
                "authorized_effects",
                "decision",
                "valid_for_seconds",
                "nonce",
            },
            label="effect reauthorization payload",
        )
    except GitHubTrustError as exc:
        raise DraftPrRetryError(str(exc)) from exc
    if payload.get("schema_version") != "executor-github-effect-reauthorization/1.0":
        raise DraftPrRetryError("unsupported effect reauthorization schema")
    if payload.get("decision") != "REAUTHORIZE_NO_EFFECT":
        raise DraftPrRetryError("effect reauthorization decision must be REAUTHORIZE_NO_EFFECT")
    if payload.get("contract_sha256") != contract_sha or payload.get("pilot_run_id") != run_id:
        raise DraftPrRetryError("effect reauthorization frozen pilot binding differs")
    nonce = payload.get("nonce")
    if not isinstance(nonce, str) or _SAFE_ID.fullmatch(nonce) is None:
        raise DraftPrRetryError("effect reauthorization nonce is invalid")
    lifetime = payload.get("valid_for_seconds")
    if type(lifetime) is not int or not (60 <= lifetime <= profile.max_decision_lifetime_seconds):
        raise DraftPrRetryError("effect reauthorization lifetime exceeds trust profile")
    request_ref = payload.get("request")
    expected_request = {
        "repository": profile.intake_repository,
        "issue_number": issue_number,
        "issue_node_id": issue_node_id,
        "body_sha256": request_body_sha,
    }
    if request_ref != expected_request:
        raise DraftPrRetryError("effect reauthorization request binding differs")
    prior_ref = payload.get("prior_no_effect")
    expected_prior = {
        "action_kind": "CREATE_GIT_REF",
        "target": prior_push["target"],
        "effect_sha256": prior_push["effect_sha256"],
        "attempt_id": prior_push["attempt_id"],
        "result_sha256": prior_push["authority_result_binding"]["result_sha256"],
        "absence_evidence_sha256": prior_push["absence_observation"]["evidence_sha256"],
    }
    if prior_ref != expected_prior:
        raise DraftPrRetryError("effect reauthorization prior NO_EFFECT binding differs")
    authorized = payload.get("authorized_effects")
    expected_authorized = {
        "push": {
            "action_kind": "CREATE_GIT_REF",
            "target": push_plan["target"],
            "effect_sha256": push_plan["effect_sha256"],
        },
        "pull_request": {
            "action_kind": "CREATE_PULL_REQUEST",
            "target": pr_plan["target"],
            "effect_sha256": pr_plan["effect_sha256"],
            "draft": True,
        },
        "merge": False,
        "deploy": False,
        "release": False,
        "tag": False,
    }
    if authorized != expected_authorized:
        raise DraftPrRetryError("effect reauthorization authorized effects differ from exact retry plan")

    created_at = comment.get("created_at")
    updated_at = comment.get("updated_at")
    if created_at != updated_at:
        raise DraftPrRetryError("edited effect reauthorization is not accepted")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    try:
        created = _parse_utc(created_at, label="effect reauthorization created_at")
        prior_observed = _parse_utc(
            prior_push["absence_observation"]["observed_at"],
            label="prior absence observed_at",
        )
    except GitHubTrustError as exc:
        raise DraftPrRetryError(str(exc)) from exc
    expires = created + timedelta(seconds=lifetime)
    if created <= prior_observed:
        raise DraftPrRetryError("effect reauthorization predates confirmed NO_EFFECT")
    if created > current + timedelta(minutes=5) or expires <= current:
        raise DraftPrRetryError("effect reauthorization is not currently fresh")
    node_id = comment.get("node_id")
    if comment.get("id") != comment_id or not isinstance(node_id, str) or not node_id:
        raise DraftPrRetryError("effect reauthorization lacks immutable comment identity")

    return VerifiedDraftPrReauthorization(
        profile_id=profile.profile_id,
        repository=profile.intake_repository,
        issue_number=issue_number,
        comment_id=comment_id,
        comment_node_id=node_id,
        actor_login=login,
        actor_id=actor_id,
        body_sha256=sha256_text(body),
        contract_sha256=contract_sha,
        pilot_run_id=run_id,
        push_effect_sha256=push_plan["effect_sha256"],
        pull_request_effect_sha256=pr_plan["effect_sha256"],
        created_at=created_at,
        expires_at=expires.isoformat().replace("+00:00", "Z"),
        payload=copy.deepcopy(payload),
        _proof=_REAUTH_PROOF,
    )


class ProductDraftPrRetryExecutor(DraftPrEffectExecutor):
    """One-shot continuation after a fully observed NO_EFFECT push failure."""

    def prepare_commit(self, workspace: str | Path) -> PreparedCommit:
        root = Path(workspace).resolve()
        source = self.report["source_commit"]
        if _git(root, "rev-parse", "HEAD").stdout.strip() != source:
            raise DraftPrRetryError("retry workspace HEAD differs from pilot source commit")
        changed = tuple(
            line[3:]
            for line in _git(
                root,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ).stdout.splitlines()
            if line
        )
        expected = tuple(self.report.get("changed_paths", []))
        if tuple(sorted(changed)) != tuple(sorted(expected)):
            raise DraftPrRetryError("retry workspace change set differs from pilot report")
        patch = _git(root, "diff", "--no-ext-diff", "--no-textconv", "--binary", source).stdout
        patch_sha = _sha256_text(patch)
        patch_record = self.report.get("patch")
        if not isinstance(patch_record, dict) or patch_record.get("sha256") != patch_sha:
            raise DraftPrRetryError("retry patch differs from verified pilot patch")
        if not expected:
            raise DraftPrRetryError("successful pilot has no changed paths")
        _git(root, "add", "--", *expected)
        decision_evidence = self.contract.get("decision_evidence")
        stable_date = decision_evidence.get("created_at") if isinstance(decision_evidence, dict) else None
        if not isinstance(stable_date, str):
            raise DraftPrRetryError("frozen decision lacks stable commit timestamp")
        env = dict(os.environ)
        env["GIT_AUTHOR_DATE"] = stable_date
        env["GIT_COMMITTER_DATE"] = stable_date
        _git(
            root,
            "-c",
            "user.name=Creative OS Executor",
            "-c",
            "user.email=executor@localhost",
            "commit",
            "--no-gpg-sign",
            "-m",
            self.request["title"],
            env=env,
        )
        commit_sha = _git(root, "rev-parse", "HEAD").stdout.strip()
        tree_sha = _git(root, "rev-parse", "HEAD^{tree}").stdout.strip()
        parent = _git(root, "rev-parse", "HEAD^").stdout.strip()
        if parent != source or _SHA40.fullmatch(commit_sha) is None or _SHA40.fullmatch(tree_sha) is None:
            raise DraftPrRetryError("retry prepared commit has invalid lineage")
        if _git(root, "status", "--porcelain=v1", "--untracked-files=all").stdout:
            raise DraftPrRetryError("retry workspace is not clean after commit")
        branch = self.request["head_branch"]
        if not isinstance(branch, str) or _BRANCH.fullmatch(branch) is None or ".." in branch or branch.endswith("/"):
            raise DraftPrRetryError("draft PR head branch is invalid")
        existing = _git(root, "show-ref", "--verify", f"refs/heads/{branch}", check=False)
        if existing.returncode == 0:
            raise DraftPrRetryError("local retry branch already exists; reconciliation required")
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

    def plan_retry(
        self,
        *,
        workspace: str | Path,
        prior_publication: dict[str, Any],
    ) -> dict[str, Any]:
        contract_sha = self.frozen_result["contract_sha256"]
        _validate_prior_no_effect(
            prior_publication,
            contract_sha256=contract_sha,
            pilot_run_id=self.report["run_id"],
        )
        prepared = self.prepare_commit(workspace)
        push_payload = {
            "schema_version": "executor-git-ref-effect/1.0",
            "repository": prepared.repository,
            "ref": f"refs/heads/{prepared.head_branch}",
            "sha": prepared.commit_sha,
        }
        simulated_push = {"status": "EFFECT_COMPLETED_AND_OBSERVED"}
        pr_payload = {
            "schema_version": "executor-draft-pr-effect/1.0",
            "repository": prepared.repository,
            "base": self.base_branch,
            "head": prepared.head_branch,
            "title": self.request["title"],
            "body": self._pr_body(prepared, simulated_push),
            "draft": True,
        }
        return {
            "schema_version": "executor-draft-pr-retry-plan/1.0",
            "contract_sha256": contract_sha,
            "pilot_run_id": self.report["run_id"],
            "prepared": _prepared_record(prepared),
            "push": {
                "action_kind": "CREATE_GIT_REF",
                "target": f"{prepared.repository}@refs/heads/{prepared.head_branch}",
                "effect_sha256": _canonical_sha256(push_payload),
                "payload": push_payload,
            },
            "pull_request": {
                "action_kind": "CREATE_PULL_REQUEST",
                "target": prepared.repository,
                "effect_sha256": _canonical_sha256(pr_payload),
                "payload": pr_payload,
            },
            "automatic_retry_allowed": False,
            "requires_verified_human_reauthorization": True,
            "merge_allowed": False,
            "deploy_allowed": False,
            "release_allowed": False,
            "tag_allowed": False,
        }

    def publish_reauthorized(
        self,
        *,
        workspace: str | Path,
        prior_publication: dict[str, Any],
        retry_plan: dict[str, Any],
        reauthorization: VerifiedDraftPrReauthorization,
        gateway: ProductGitHubDraftPrGateway,
    ) -> dict[str, Any]:
        if reauthorization._proof is not _REAUTH_PROOF:
            raise DraftPrRetryError("effect retry requires verified Human reauthorization")
        if reauthorization.contract_sha256 != self.frozen_result["contract_sha256"] or reauthorization.pilot_run_id != self.report["run_id"]:
            raise DraftPrRetryError("reauthorization differs from frozen pilot")
        _validate_prior_no_effect(
            prior_publication,
            contract_sha256=reauthorization.contract_sha256,
            pilot_run_id=reauthorization.pilot_run_id,
        )
        prepared = self.prepare_commit(workspace)
        planned = retry_plan.get("prepared")
        if not isinstance(planned, dict) or _prepared_record(prepared) != planned:
            raise DraftPrRetryError("live retry prepared commit differs from Human-reviewed retry plan")
        push_plan = retry_plan["push"]
        pr_plan = retry_plan["pull_request"]
        if reauthorization.push_effect_sha256 != push_plan["effect_sha256"] or reauthorization.pull_request_effect_sha256 != pr_plan["effect_sha256"]:
            raise DraftPrRetryError("reauthorization effect hashes differ from retry plan")
        if gateway.repository != prepared.repository or gateway.workspace != Path(workspace).resolve():
            raise DraftPrRetryError("retry gateway identity differs from prepared publication")

        suffix = reauthorization.comment_node_id
        contract_sha = reauthorization.contract_sha256
        gateway.bind_effect_payload(push_plan["payload"])
        push = GitHubEffectTransaction(
            run_id=self.report["run_id"],
            authority_key=f"draft-pr:{contract_sha}:REAUTH:{suffix}:PUSH_DRAFT_BRANCH",
            action_kind="CREATE_GIT_REF",
            target=push_plan["target"],
            effect_bytes=canonical_effect_bytes(push_plan["payload"]),
            not_after=reauthorization.expires_at,
            evidence_directory=self.evidence_directory,
            ledger=self.ledger,
        ).execute(gateway)
        if push.get("status") != "EFFECT_COMPLETED_AND_OBSERVED":
            return {
                "status": "DRAFT_PR_REAUTHORIZED_PUBLICATION_INCOMPLETE",
                "stage": "PUSH_DRAFT_BRANCH",
                "push": push,
                "automatic_retry_allowed": False,
            }

        # The reviewed PR effect intentionally assumes direct, observed push
        # success. Any recovered/ambiguous push stops above instead of silently
        # changing the Human-reviewed PR body/effect hash.
        gateway.bind_effect_payload(pr_plan["payload"])
        pr = GitHubEffectTransaction(
            run_id=self.report["run_id"],
            authority_key=f"draft-pr:{contract_sha}:REAUTH:{suffix}:CREATE_DRAFT_PR",
            action_kind="CREATE_PULL_REQUEST",
            target=pr_plan["target"],
            effect_bytes=canonical_effect_bytes(pr_plan["payload"]),
            not_after=reauthorization.expires_at,
            evidence_directory=self.evidence_directory,
            ledger=self.ledger,
        ).execute(gateway)
        if pr.get("status") not in {"EFFECT_COMPLETED_AND_OBSERVED", "RECOVERED_EXTERNAL_EFFECT"}:
            return {
                "status": "DRAFT_PR_REAUTHORIZED_PUBLICATION_INCOMPLETE",
                "stage": "CREATE_DRAFT_PR",
                "prepared": _prepared_record(prepared),
                "push": push,
                "pull_request": pr,
                "automatic_retry_allowed": False,
            }
        return {
            "schema_version": "executor-draft-pr-publication-result/1.1",
            "status": "DRAFT_PR_CREATED_REVIEW_REQUIRED",
            "prepared": _prepared_record(prepared),
            "push": push,
            "pull_request": pr,
            "reauthorization": reauthorization.to_dict(),
            "human_review_required": True,
            "human_acceptance": "PENDING",
            "merge_allowed": False,
            "deploy_allowed": False,
            "release_allowed": False,
            "tag_allowed": False,
        }
