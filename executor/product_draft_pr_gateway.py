from __future__ import annotations

import base64
import os

from executor.draft_pr_effect import GitHubDraftPrGateway, ProviderWriteResult, _git


class ProductGitHubDraftPrGateway(GitHubDraftPrGateway):
    """Canonical product Git gateway with non-interactive GitHub HTTPS auth.

    GitHub's smart-HTTP Git endpoint expects HTTP Basic authentication for a
    token-backed push. The token is carried only in the child process
    environment via Git's in-memory config; it is never embedded in the remote
    URL or command-line arguments.
    """

    def _git_push(self, *, sha: str, ref: str) -> ProviderWriteResult:
        credentials = base64.b64encode(
            f"x-access-token:{self.token}".encode("utf-8")
        ).decode("ascii")
        env = dict(os.environ)
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = "http.https://github.com/.extraHeader"
        env["GIT_CONFIG_VALUE_0"] = f"Authorization: Basic {credentials}"
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
        raw = (result.stdout + "\n" + result.stderr).encode(
            "utf-8", errors="replace"
        )
        if result.returncode == 0:
            return ProviderWriteResult(
                provider_status=200,
                provider_message="Git protocol accepted ref publication",
                raw_response=raw,
                object_id=sha,
                object_url=f"https://github.com/{self.repository}/commit/{sha}",
            )
        return ProviderWriteResult(
            provider_status=599,
            provider_message="Git protocol result requires provider reconciliation",
            raw_response=raw,
        )
