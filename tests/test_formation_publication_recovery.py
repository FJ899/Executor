from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from executor.formation_issue_effect import FormationIssueGateway
from executor.formation_publication_recovery import recover_formation_publication
from executor.github_effect_transaction import canonical_effect_bytes
from executor.github_trust import canonical_json


class FakeSource:
    def __init__(self, value: dict):
        self.value = value
        self.urls: list[str] = []

    def fetch_json(self, url: str) -> dict:
        self.urls.append(url)
        return json.loads(json.dumps(self.value))


class FormationPublicationRecoveryTests(unittest.TestCase):
    def test_zero_match_immediate_issue_observation_is_inconclusive(self) -> None:
        gateway = FormationIssueGateway(repository="FJ899/Executor", token="test-token")
        payload = {
            "schema_version": "executor-formation-authority-issue/1.0",
            "title": "Executor authority request: req-1",
            "body": "{}",
        }
        gateway.bind_effect_payload(payload)
        gateway._request = lambda method, url, payload=None: (200, b"[]")  # type: ignore[method-assign]
        result = gateway.observe(
            action_kind="CREATE_ISSUE",
            target="FJ899/Executor",
            effect_sha256="0" * 64,
            correlation_id="test",
        )
        self.assertFalse(result.complete)
        self.assertFalse(result.exists)

    def test_confirmed_201_issue_is_recovered_without_repeating_write(self) -> None:
        request_payload = {
            "schema_version": "executor-github-request/1.0",
            "request_id": "req-1",
            "target": {"repository": "FJ899/executor-pilot-target", "commit": "1" * 40, "tree": "2" * 40},
            "task": {},
            "expires_at": "2026-08-26T23:00:00Z",
            "nonce": "formation-test",
        }
        binding = {"draft_sha256": "3" * 64}
        canonical = {
            "formation_binding": binding,
            "github_request_payload": request_payload,
        }
        issue_payload = {
            "schema_version": "executor-formation-authority-issue/1.0",
            "title": "Executor authority request: req-1",
            "body": canonical_json(request_payload),
        }
        effect_sha = hashlib.sha256(canonical_effect_bytes(issue_payload)).hexdigest()
        provider_issue = {
            "url": "https://api.github.com/repos/FJ899/Executor/issues/88",
            "repository_url": "https://api.github.com/repos/FJ899/Executor",
            "html_url": "https://github.com/FJ899/Executor/issues/88",
            "id": 10088,
            "node_id": "I_recovery_88",
            "number": 88,
            "title": issue_payload["title"],
            "body": issue_payload["body"],
            "state": "open",
        }
        receipt = {
            "kind": "SYSTEM_WRITE_RECEIPT",
            "payload": {
                "provider": "GITHUB",
                "action_kind": "CREATE_ISSUE",
                "target": "FJ899/Executor",
                "effect_sha256": effect_sha,
                "provider_outcome": "SUCCESS",
                "provider_status": 201,
                "object_id": "88",
                "object_url": "https://github.com/FJ899/Executor/issues/88",
            },
            "provider_response_b64": base64.b64encode(
                json.dumps(provider_issue, separators=(",", ":")).encode("utf-8")
            ).decode("ascii"),
        }
        receipt_raw = json.dumps(receipt, separators=(",", ":")).encode("utf-8")
        receipt_sha = hashlib.sha256(receipt_raw).hexdigest()
        attempt_result = {
            "kind": "EXTERNAL_EFFECT_ATTEMPT_RESULT_BINDING",
            "payload": {
                "provider": "GITHUB",
                "action_kind": "CREATE_ISSUE",
                "target": "FJ899/Executor",
                "effect_sha256": effect_sha,
                "provider_outcome": "SUCCESS",
                "receipt_provider_status": 201,
                "receipt_evidence_sha256": receipt_sha,
                "attempt_id": "ose-test",
                "object_id": "88",
                "object_url": "https://github.com/FJ899/Executor/issues/88",
            },
        }
        incomplete = {
            "schema_version": "executor-formation-publication-result/1.1",
            "status": "FORMATION_PUBLICATION_INCOMPLETE",
            "canonical_contract_request": canonical,
            "formation_binding": binding,
            "github_request_payload": request_payload,
            "request_transport_provenance": {"authority": False},
            "publication_effect": {
                "status": "NO_EFFECT_CONFIRMED",
                "action_kind": "CREATE_ISSUE",
                "target": "FJ899/Executor",
                "effect_sha256": effect_sha,
                "automatic_retry_allowed": False,
                "authority_result_binding": {"result_sha256": "4" * 64},
            },
            "manual_request_rewrite_required": False,
            "executable": False,
        }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / f"system_write_receipt-{receipt_sha}.json").write_bytes(receipt_raw)
            (root / "external_effect_attempt_result-ose-test.json").write_text(
                json.dumps(attempt_result, separators=(",", ":")), encoding="utf-8"
            )
            source = FakeSource(provider_issue)
            recovered = recover_formation_publication(
                incomplete_publication=incomplete,
                evidence_directory=root,
                source=source,
            )

        self.assertEqual(recovered["status"], "AWAITING_VERIFIED_HUMAN_DECISION")
        self.assertEqual(recovered["publication_effect"]["status"], "RECOVERED_EXTERNAL_EFFECT")
        self.assertEqual(recovered["publication_effect"]["object_id"], "88")
        self.assertFalse(recovered["publication_effect"]["external_write_repeated"])
        self.assertFalse(recovered["request_transport_provenance"]["authority"])
        self.assertTrue(recovered["request_transport_provenance"]["historical_authority_result_unchanged"])
        self.assertEqual(source.urls, ["https://api.github.com/repos/FJ899/Executor/issues/88"])


if __name__ == "__main__":
    unittest.main()
