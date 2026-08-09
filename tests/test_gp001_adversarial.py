import hashlib
import inspect
import subprocess
import tempfile
import unittest
from pathlib import Path

from executor.gp001_runtime import AuthorizedFileMutation, GP001Blocked, GP001Runtime
from executor.sandbox.policy_snapshot import load_execution_policy_snapshot


ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "GP001-FIX-FAILING-TEST-CASE-001"
FIXTURE_REPOSITORY = "litrgratis-pixel/executor-pilot-target"
FIXTURE_COMMIT = "3934a94a5eebf750079200589d6dc40e024d44a0"
IMAGE = "sha256:" + "1" * 64


def _head() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _mutation(path: str) -> AuthorizedFileMutation:
    replacement = "adversarial replacement\n"
    return AuthorizedFileMutation(
        path=path,
        expected_before_sha256=hashlib.sha256(b"expected-before").hexdigest(),
        replacement_text=replacement,
        expected_after_sha256=hashlib.sha256(replacement.encode("utf-8")).hexdigest(),
    )


class GP001AdversarialAuthorityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.commit = _head()
        self.runtime = GP001Runtime(
            executor_root=ROOT,
            executor_commit=self.commit,
            runs_root=Path(self.temp.name) / "runs",
            image=IMAGE,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_controlled_fixture_policy_is_exact_task_repo_commit(self):
        policy = load_execution_policy_snapshot(ROOT, commit=self.commit)
        self.assertFalse(policy.external_projects)
        self.assertTrue(
            policy.authorizes_controlled_external_fixture(
                task=TASK_ID,
                repository=FIXTURE_REPOSITORY,
                commit=FIXTURE_COMMIT,
            )
        )
        attacks = (
            ("OTHER-TASK", FIXTURE_REPOSITORY, FIXTURE_COMMIT),
            (TASK_ID, "litrgratis-pixel/not-authorized", FIXTURE_COMMIT),
            (TASK_ID, FIXTURE_REPOSITORY, "1" * 40),
        )
        for task, repository, commit in attacks:
            with self.subTest(task=task, repository=repository, commit=commit):
                self.assertFalse(
                    policy.authorizes_controlled_external_fixture(
                        task=task,
                        repository=repository,
                        commit=commit,
                    )
                )

    def test_task_identity_tamper_cannot_cross_authorization_gate(self):
        self.runtime.task["id"] = "ATTACKER-TASK"
        with self.assertRaisesRegex(
            GP001Blocked,
            "frozen GP001 contract|Controlled External Fixture authority",
        ):
            self.runtime._authorize(
                run_id="attack-task",
                mutation=_mutation("project_registry/registry.py"),
                now=None,
            )

    def test_repository_identity_tamper_cannot_cross_authorization_gate(self):
        self.runtime.repository = "litrgratis-pixel/not-authorized"
        with self.assertRaisesRegex(GP001Blocked, "Controlled External Fixture authority"):
            self.runtime._authorize(
                run_id="attack-repository",
                mutation=_mutation("project_registry/registry.py"),
                now=None,
            )

    def test_commit_identity_tamper_cannot_cross_authorization_gate(self):
        self.runtime.input_commit = "1" * 40
        with self.assertRaisesRegex(GP001Blocked, "Controlled External Fixture authority"):
            self.runtime._authorize(
                run_id="attack-commit",
                mutation=_mutation("project_registry/registry.py"),
                now=None,
            )

    def test_post_validation_scope_tamper_cannot_mint_aap_for_protected_path(self):
        # Attack the cached runtime state after the canonical task and policy have
        # already validated. A task hash must not remain authoritative while a
        # caller widens the in-memory action scope underneath it.
        self.runtime.allowed = ("tests/test_registry.py",)
        self.runtime.protected = ()
        with self.assertRaisesRegex(
            GP001Blocked,
            "frozen GP001 contract|authoritative|scope|Controlled External Fixture",
        ):
            self.runtime._authorize(
                run_id="attack-scope",
                mutation=_mutation("tests/test_registry.py"),
                now=None,
            )

    def test_task_document_scope_edit_does_not_expand_cached_execution_scope(self):
        self.runtime.task["golden_path"]["scope"]["allowed_paths"] = [
            "project_registry/registry.py",
            "tests/test_registry.py",
        ]
        with self.assertRaisesRegex(GP001Blocked, "outside the frozen GP001 contract"):
            self.runtime._authorize(
                run_id="attack-task-scope",
                mutation=_mutation("tests/test_registry.py"),
                now=None,
            )

    def test_task_and_cached_scope_cannot_be_expanded_together(self):
        self.runtime.task["golden_path"]["scope"]["allowed_paths"] = [
            "tests/test_registry.py",
        ]
        self.runtime.task["golden_path"]["scope"]["protected_paths"] = []
        self.runtime.allowed = ("tests/test_registry.py",)
        self.runtime.protected = ()
        with self.assertRaisesRegex(GP001Blocked, "outside the frozen GP001 contract"):
            self.runtime._authorize(
                run_id="attack-task-and-cache",
                mutation=_mutation("tests/test_registry.py"),
                now=None,
            )

    def test_regression_commands_cannot_be_removed_after_validation(self):
        self.runtime.regression_commands = []
        with self.assertRaisesRegex(GP001Blocked, "execution state changed"):
            self.runtime._authorize(
                run_id="attack-regressions",
                mutation=_mutation("project_registry/registry.py"),
                now=None,
            )

    def test_backend_cannot_be_replaced_after_validation(self):
        self.runtime.backend = object()
        with self.assertRaisesRegex(GP001Blocked, "backend changed"):
            self.runtime._authorize(
                run_id="attack-backend",
                mutation=_mutation("project_registry/registry.py"),
                now=None,
            )

    def test_backend_scope_cache_cannot_be_widened_after_validation(self):
        self.runtime.backend.allowed = ("tests/test_registry.py",)
        self.runtime.backend.protected = ()
        with self.assertRaisesRegex(GP001Blocked, "backend authority state changed"):
            self.runtime._authorize(
                run_id="attack-backend-scope",
                mutation=_mutation("project_registry/registry.py"),
                now=None,
            )

    def test_public_api_has_no_task_authority_or_backend_override_parameters(self):
        init_parameters = inspect.signature(GP001Runtime.__init__).parameters
        execute_parameters = inspect.signature(GP001Runtime.execute).parameters
        for forbidden in (
            "task_path",
            "task_contract",
            "policy_snapshot",
            "authorization_context",
            "authorization_packet",
            "sandbox_backend",
        ):
            self.assertNotIn(forbidden, init_parameters)
            self.assertNotIn(forbidden, execute_parameters)

    def test_controlled_fixture_does_not_enable_generic_external_projects(self):
        policy = load_execution_policy_snapshot(ROOT, commit=self.commit)
        self.assertFalse(policy.external_projects)
        self.assertEqual(self.runtime.policy_snapshot.external_projects, False)
        self.assertTrue(
            self.runtime.policy_snapshot.authorizes_controlled_external_fixture(
                task=TASK_ID,
                repository=FIXTURE_REPOSITORY,
                commit=FIXTURE_COMMIT,
            )
        )


if __name__ == "__main__":
    unittest.main()
