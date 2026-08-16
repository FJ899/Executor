from __future__ import annotations

import hashlib
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from executor.github_trust import GitHubTrustProfile, verify_github_request
from executor.pilot_contract import build_pilot_draft, pilot_draft_sha256


ROOT = Path(__file__).resolve().parents[1]
PROFILE = GitHubTrustProfile.from_dict(
    json.loads((ROOT / "trust_profiles/github-p4-pilots.json").read_text())
)
NOW = datetime(2026, 8, 16, 18, 22, tzinfo=timezone.utc)


class FakeSource:
    def __init__(self, values):
        self.values = values

    def fetch_json(self, url):
        return self.values[url]


CASES = (
    {
        "name": "scriptops",
        "issue_number": 65,
        "issue_id": 5165713461,
        "issue_node_id": "I_kwDOTpqUf88AAAABM-aINQ",
        "created_at": "2026-08-16T18:18:20Z",
        "body_sha256": "158ab5918c20802658b2c6649a63e6fb25511c0c0d745efcb170cf3577a022db",
        "draft_sha256": "cfdcfa2ac6b2d6ac7e3da59b0d7aece0e54d43e99f3c8977e8cd422285b50cf6",
    },
    {
        "name": "reconstructor",
        "issue_number": 64,
        "issue_id": 5165706947,
        "issue_node_id": "I_kwDOTpqUf88AAAABM-Zuww",
        "created_at": "2026-08-16T18:16:39Z",
        "body_sha256": "e662f7c25fc699b252abcc6a25254b510bd9de94d703116f23631994de1bccbc",
        "draft_sha256": "49f3ae5290220ed70db4d257f4abfec1ed67af67da9c9b9c4a1ff026a6a2863e",
    },
)


class CorrectedRequestHashTests(unittest.TestCase):
    def test_real_human_request_identity_and_draft_hashes_are_frozen(self):
        for case in CASES:
            with self.subTest(name=case["name"]):
                body = (
                    ROOT / f"evidence/p4/requests/{case['name']}-request.json"
                ).read_text(encoding="utf-8").rstrip("\n")
                self.assertEqual(
                    hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    case["body_sha256"],
                )
                payload = json.loads(body)
                issue_url = (
                    f"https://api.github.com/repos/{PROFILE.intake_repository}/issues/"
                    f"{case['issue_number']}"
                )
                commit_url = (
                    f"https://api.github.com/repos/{payload['target']['repository']}"
                    f"/git/commits/{payload['target']['commit']}"
                )
                issue = {
                    "url": issue_url,
                    "repository_url": f"https://api.github.com/repos/{PROFILE.intake_repository}",
                    "number": case["issue_number"],
                    "id": case["issue_id"],
                    "node_id": case["issue_node_id"],
                    "state": "open",
                    "body": body,
                    "created_at": case["created_at"],
                    "updated_at": case["created_at"],
                    "author_association": "OWNER",
                    "performed_via_github_app": None,
                    "user": {
                        "login": PROFILE.allowed_actor_login,
                        "id": PROFILE.allowed_actor_id,
                        "type": "User",
                    },
                }
                source = FakeSource(
                    {
                        issue_url: issue,
                        commit_url: {
                            "sha": payload["target"]["commit"],
                            "tree": {"sha": payload["target"]["tree"]},
                        },
                    }
                )
                verified = verify_github_request(
                    source,
                    profile=PROFILE,
                    issue_number=case["issue_number"],
                    now=NOW,
                )
                self.assertEqual(verified.body_sha256, case["body_sha256"])
                self.assertEqual(
                    pilot_draft_sha256(build_pilot_draft(verified)),
                    case["draft_sha256"],
                )


if __name__ == "__main__":
    unittest.main()
