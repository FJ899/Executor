import copy
import math
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from executor.action_authorization import (
    AuthorizationContext,
    packet_payload_sha256,
    validate_action_authorization_packet,
)
from executor.contracts import ValidationStatus


NOW = datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc)
COMMIT = "1" * 40
HASH = "2" * 64


class ActionAuthorizationTest(unittest.TestCase):
    def context(self, **changes):
        values = dict(
            run_id="run-001",
            task_id="TASK-001",
            risk_class="LOW_RISK",
            mode="BUILD_AND_TEST",
            executor_commit=COMMIT,
            policy_sha256=HASH,
            project_contract_sha256="3" * 64,
            task_contract_sha256="4" * 64,
            test_contract_sha256="5" * 64,
            repository_commits={"litrgratis-pixel/Executor": COMMIT},
            allowed_paths=("executor/**", "tests/**"),
            external_projects=False,
            auto_merge=False,
            default_network=False,
            default_secrets=(),
            verified_issuer_evidence={
                "evidence:policy-001": ("POLICY_VERIFIER", "policy-engine"),
                "evidence:user-001": ("USER", "user-001"),
            },
        )
        values.update(changes)
        return AuthorizationContext(**values)

    def packet(self, *, issuer_role="POLICY_VERIFIER", issuer_id="policy-engine", evidence_ref="evidence:policy-001", action_kind="SANDBOX_EXECUTION", **action_changes):
        action = {
            "kind": action_kind,
            "argv": ["python", "-m", "unittest"],
            "paths": ["executor/action_authorization.py"],
            "network": False,
            "secrets": [],
            "external_project": False,
        }
        action.update(action_changes)
        packet = {
            "schema_version": "executor-action-authorization/1.0",
            "packet_id": "packet-001",
            "run_id": "run-001",
            "issued_at": "2026-08-02T14:55:00Z",
            "expires_at": "2026-08-02T15:30:00Z",
            "issuer": {
                "role": issuer_role,
                "id": issuer_id,
                "evidence_ref": evidence_ref,
            },
            "bindings": {
                "task_id": "TASK-001",
                "risk_class": "LOW_RISK",
                "mode": "BUILD_AND_TEST",
                "executor_commit": COMMIT,
                "policy_sha256": HASH,
                "project_contract_sha256": "3" * 64,
                "task_contract_sha256": "4" * 64,
                "test_contract_sha256": "5" * 64,
                "repository_commits": {"litrgratis-pixel/Executor": COMMIT},
            },
            "action": action,
            "decision": {
                "status": "AUTHORIZED",
                "reasons": ["Action stays inside the approved task and policy"],
            },
            "constraints": {
                "max_uses": 1,
                "max_duration_seconds": 3600,
                "manual_confirmation_required": False,
            },
            "integrity": {
                "algorithm": "SHA-256",
                "payload_sha256": "0" * 64,
            },
        }
        self.rehash(packet)
        return packet

    def rehash(self, packet):
        packet["integrity"]["payload_sha256"] = packet_payload_sha256(packet)
        return packet

    def validate(self, packet, *, context=None, consumed=None, now=NOW):
        return validate_action_authorization_packet(
            packet,
            context=context or self.context(),
            now=now,
            consumed_packet_ids=consumed,
        )

    def codes(self, result):
        return {issue.code for issue in result.issues}

    def assert_blocked(self, packet, code, *, context=None, consumed=None, now=NOW, rehash=True):
        if rehash:
            self.rehash(packet)
        result, decision = self.validate(packet, context=context, consumed=consumed, now=now)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertEqual(result.action_status, "BLOCKED_BEFORE_ACTION")
        self.assertIsNone(decision)
        self.assertIn(code, self.codes(result))

    def test_valid_policy_verifier_packet_is_only_ready_for_atomic_consumption(self):
        packet = self.packet()
        result, decision = self.validate(packet)
        self.assertEqual(result.status, ValidationStatus.VALID)
        self.assertTrue(result.eligible_for_consumption)
        self.assertEqual(result.action_status, "READY_FOR_ATOMIC_CONSUMPTION")
        self.assertNotIn("READY_FOR_MODEL", result.to_dict().values())
        self.assertIsNotNone(decision)
        self.assertEqual(decision.payload_sha256, packet["integrity"]["payload_sha256"])
        self.assertTrue(decision.ready_for_atomic_consumption)

    def test_self_declared_user_without_verified_evidence_is_blocked(self):
        packet = self.packet(
            issuer_role="USER",
            issuer_id="attacker",
            evidence_ref="evidence:invented",
        )
        self.assert_blocked(packet, "UNVERIFIED_AUTHORIZATION_ISSUER")

    def test_verified_evidence_must_bind_exact_role_and_identity(self):
        for role, issuer_id, evidence in (
            ("USER", "policy-engine", "evidence:policy-001"),
            ("POLICY_VERIFIER", "user-001", "evidence:user-001"),
        ):
            with self.subTest(role=role, issuer_id=issuer_id):
                packet = self.packet(
                    issuer_role=role,
                    issuer_id=issuer_id,
                    evidence_ref=evidence,
                )
                self.assert_blocked(packet, "UNVERIFIED_AUTHORIZATION_ISSUER")

    def test_merge_requires_verified_user_and_manual_confirmation(self):
        policy_packet = self.packet(action_kind="MERGE_PULL_REQUEST", argv=[])
        self.assert_blocked(policy_packet, "USER_AUTHORIZATION_REQUIRED")

        user_packet = self.packet(
            issuer_role="USER",
            issuer_id="user-001",
            evidence_ref="evidence:user-001",
            action_kind="MERGE_PULL_REQUEST",
            argv=[],
        )
        self.assert_blocked(user_packet, "MANUAL_CONFIRMATION_REQUIRED")

        user_packet["constraints"]["manual_confirmation_required"] = True
        self.rehash(user_packet)
        result, decision = self.validate(user_packet)
        self.assertEqual(result.status, ValidationStatus.VALID)
        self.assertEqual(decision.action_kind, "MERGE_PULL_REQUEST")

    def test_high_risk_network_secret_and_external_actions_require_user(self):
        cases = (
            (self.packet(), self.context(risk_class="HIGH_RISK")),
            (
                self.packet(network=True),
                self.context(default_network=True),
            ),
            (
                self.packet(secrets=["TOKEN"]),
                self.context(default_secrets=("TOKEN",)),
            ),
            (
                self.packet(
                    action_kind="EXTERNAL_PROJECT_EXECUTION",
                    external_project=True,
                ),
                self.context(external_projects=True),
            ),
        )
        for packet, context in cases:
            with self.subTest(action=packet["action"]):
                packet["bindings"]["risk_class"] = context.risk_class
                self.assert_blocked(packet, "USER_AUTHORIZATION_REQUIRED", context=context)

    def test_packet_cannot_override_policy_capabilities(self):
        cases = (
            (self.packet(network=True), "AUTHORIZATION_CAPABILITY_DENIED"),
            (self.packet(secrets=["TOKEN"]), "AUTHORIZATION_CAPABILITY_DENIED"),
            (
                self.packet(
                    action_kind="EXTERNAL_PROJECT_EXECUTION",
                    external_project=True,
                ),
                "AUTHORIZATION_CAPABILITY_DENIED",
            ),
        )
        for packet, code in cases:
            with self.subTest(action=packet["action"]):
                self.assert_blocked(packet, code)

    def test_action_kind_and_external_flag_cannot_disagree(self):
        packet = self.packet(external_project=True)
        self.assert_blocked(packet, "INVALID_AUTHORIZATION_ACTION", context=self.context(external_projects=True))

        packet = self.packet(action_kind="EXTERNAL_PROJECT_EXECUTION")
        self.assert_blocked(packet, "INVALID_AUTHORIZATION_ACTION", context=self.context(external_projects=True))

    def test_replay_expiry_future_issue_and_lifetime_are_blocked(self):
        packet = self.packet()
        self.assert_blocked(packet, "AUTHORIZATION_REPLAY", consumed={"packet-001"})

        expired = self.packet()
        expired["expires_at"] = "2026-08-02T14:59:59Z"
        self.assert_blocked(expired, "AUTHORIZATION_EXPIRED")

        future = self.packet()
        future["issued_at"] = "2026-08-02T15:06:00Z"
        future["expires_at"] = "2026-08-02T15:30:00Z"
        self.assert_blocked(future, "AUTHORIZATION_NOT_YET_VALID")

        long_lived = self.packet()
        long_lived["issued_at"] = "2026-08-01T14:00:00Z"
        long_lived["expires_at"] = "2026-08-02T15:30:00Z"
        long_lived["constraints"]["max_duration_seconds"] = 86400
        self.assert_blocked(long_lived, "INVALID_AUTHORIZATION_LIFETIME")

    def test_packet_lifetime_cannot_exceed_declared_duration(self):
        packet = self.packet()
        packet["constraints"]["max_duration_seconds"] = 60
        self.assert_blocked(packet, "INVALID_AUTHORIZATION_CONSTRAINT")

    def test_context_bindings_and_repository_commits_are_exact(self):
        mutations = (
            ("run_id", "other-run"),
            ("bindings.executor_commit", "9" * 40),
            ("bindings.policy_sha256", "8" * 64),
            ("bindings.repository_commits", {"litrgratis-pixel/Executor": "7" * 40}),
        )
        for path, value in mutations:
            with self.subTest(path=path):
                packet = self.packet()
                if path == "run_id":
                    packet[path] = value
                else:
                    key = path.split(".", 1)[1]
                    packet["bindings"][key] = value
                self.assert_blocked(packet, "AUTHORIZATION_CONTEXT_MISMATCH")

    def test_path_expansion_traversal_and_duplicate_paths_are_blocked(self):
        outside = self.packet(paths=["README.md"])
        self.assert_blocked(outside, "AUTHORIZATION_PATH_OUT_OF_SCOPE")

        traversal = self.packet(paths=["executor/../README.md"])
        self.assert_blocked(traversal, "INVALID_AUTHORIZATION_PATH")

        duplicate = self.packet(paths=["executor/a.py", "executor/a.py"])
        self.assert_blocked(duplicate, "INVALID_AUTHORIZATION_ACTION")

    def test_integrity_tamper_and_unknown_fields_are_blocked(self):
        packet = self.packet()
        packet["action"]["argv"].append("unexpected")
        self.assert_blocked(packet, "AUTHORIZATION_INTEGRITY_MISMATCH", rehash=False)

        packet = self.packet()
        packet["surprise"] = "broaden"
        self.assert_blocked(packet, "INVALID_AUTHORIZATION_PACKET")

    def test_nan_and_boolean_integer_aliases_are_blocked(self):
        packet = self.packet()
        packet["decision"]["reasons"] = [math.nan]
        result, decision = self.validate(packet)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertIsNone(decision)
        self.assertIn("INVALID_AUTHORIZATION_CANONICAL_JSON", self.codes(result))

        packet = self.packet()
        packet["constraints"]["max_uses"] = True
        self.assert_blocked(packet, "AUTHORIZATION_MUST_BE_ONE_TIME")

        packet = self.packet()
        packet["constraints"]["max_duration_seconds"] = True
        self.assert_blocked(packet, "INVALID_AUTHORIZATION_CONSTRAINT")

    def test_denied_decision_never_authorizes(self):
        packet = self.packet()
        packet["decision"]["status"] = "DENIED"
        self.assert_blocked(packet, "AUTHORIZATION_DENIED")

    def test_external_user_packet_can_be_eligible_when_policy_allows(self):
        context = self.context(external_projects=True)
        packet = self.packet(
            issuer_role="USER",
            issuer_id="user-001",
            evidence_ref="evidence:user-001",
            action_kind="EXTERNAL_PROJECT_EXECUTION",
            external_project=True,
        )
        result, decision = self.validate(packet, context=context)
        self.assertEqual(result.status, ValidationStatus.VALID)
        self.assertEqual(decision.issuer_role, "USER")


if __name__ == "__main__":
    unittest.main()
