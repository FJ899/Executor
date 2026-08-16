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


class P4EvidenceArtifactTests(unittest.TestCase):
    CASES = (
        ("scriptops", 65, "scriptops-solution-candidate.json"),
        ("reconstructor", 64, "reconstructor-solution-candidate-corrected.json"),
    )

    def test_request_candidate_and_intelligence_provenance_are_bound(self):
        for name, issue_number, candidate_name in self.CASES:
            with self.subTest(name=name):
                request = json.loads(
                    (ROOT / f"evidence/p4/requests/{name}-request.json").read_text()
                )
                candidate = json.loads(
                    (ROOT / "evidence/p4/candidates" / candidate_name).read_text()
                )
                provenance = json.loads(
                    (ROOT / f"evidence/p4/intelligence/{name}-provenance.json").read_text()
                )
                prompt = (ROOT / f"evidence/p4/intelligence/{name}-prompt.txt").read_bytes()

                issue_url = (
                    f"https://api.github.com/repos/{PROFILE.intake_repository}/issues/"
                    f"{issue_number}"
                )
                commit_url = (
                    f"https://api.github.com/repos/{request['target']['repository']}"
                    f"/git/commits/{request['target']['commit']}"
                )
                issue = {
                    "url": issue_url,
                    "repository_url": f"https://api.github.com/repos/{PROFILE.intake_repository}",
                    "number": issue_number,
                    "id": issue_number + 1000,
                    "node_id": f"I_test_{name}",
                    "state": "open",
                    "body": json.dumps(request, sort_keys=True),
                    "created_at": "2026-08-16T18:00:00Z",
                    "updated_at": "2026-08-16T18:00:00Z",
                    "author_association": "OWNER",
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
                            "sha": request["target"]["commit"],
                            "tree": {"sha": request["target"]["tree"]},
                        },
                    }
                )
                verified = verify_github_request(
                    source,
                    profile=PROFILE,
                    issue_number=issue_number,
                    now=NOW,
                )
                draft = build_pilot_draft(verified)
                self.assertEqual(len(pilot_draft_sha256(draft)), 64)
                self.assertEqual(candidate["repository"], request["target"]["repository"])
                self.assertEqual(candidate["source_commit"], request["target"]["commit"])
                self.assertEqual(candidate["source_tree"], request["target"]["tree"])
                self.assertLessEqual(
                    len(candidate["mutations"]), request["task"]["max_production_files"]
                )
                self.assertEqual(
                    candidate["evidence_plan"],
                    request["task"]["postcondition_argv"] + request["task"]["regression_argv"],
                )
                commands = request["task"]["precondition_argv"] + candidate["evidence_plan"]
                for argv in commands:
                    if argv[:2] == ["python", "-c"]:
                        compile(argv[2], f"<{name}-evidence>", "exec")
                for mutation in candidate["mutations"]:
                    self.assertEqual(
                        hashlib.sha256(mutation["replacement_text"].encode("utf-8")).hexdigest(),
                        mutation["expected_after_sha256"],
                    )
                    self.assertIn(mutation["path"], request["task"]["allowed_paths"])

                self.assertEqual(provenance["producer_role"], "EXTERNAL_INTELLIGENCE")
                self.assertEqual(provenance["human_solution_edits"], 0)
                self.assertEqual(provenance["effect_capability"], "NONE")
                self.assertEqual(provenance["request"]["repository"], PROFILE.intake_repository)
                self.assertEqual(provenance["request"]["issue_number"], issue_number)
                self.assertEqual(provenance["source"], request["target"])
                self.assertEqual(
                    provenance["prompt_sha256"], hashlib.sha256(prompt).hexdigest()
                )


if __name__ == "__main__":
    unittest.main()
