from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.p1_verifier.verify_candidate import verify

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/manual-exact-ref-verify.yml"
VERIFIER = ROOT / "tools/p1_verifier/verify_candidate.py"
ACCEPTANCE = ROOT / "tools/p1_verifier/acceptance_manifest.json"

VULNERABLE_WORKFLOW_SHA = "d9747d83cea9de7a6886e0e4d17d61dcb5ab575a"
VULNERABLE_WORKFLOW_BLOB = "96f1b9480d6dac1e402638a2df2b3c8c4a4c4675"
VULNERABLE_WORKFLOW_SHA256 = "84bcee1cc9aa4c32d5036fcdce55bb102baa96441429c373940b0968dd09a1f7"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "P1 Verifier Test",
            "GIT_AUTHOR_EMAIL": "p1-verifier@example.invalid",
            "GIT_COMMITTER_NAME": "P1 Verifier Test",
            "GIT_COMMITTER_EMAIL": "p1-verifier@example.invalid",
        },
    )
    return completed.stdout.strip()


def _hash_manifest(root: Path, *, exclude: set[str] | None = None) -> None:
    excluded = exclude or {"files-sha256.json"}
    files = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        files[relative] = _sha256(path)
    _write_json(root / "files-sha256.json", {"schema_version": 1, "files": files})


class WorkflowTrustBoundaryTests(unittest.TestCase):
    def test_vulnerable_baseline_is_not_the_current_workflow(self):
        self.assertTrue(WORKFLOW.is_file())
        self.assertNotEqual(
            _sha256(WORKFLOW),
            VULNERABLE_WORKFLOW_SHA256,
            f"vulnerable workflow {VULNERABLE_WORKFLOW_SHA} is still active",
        )

    def test_workflow_has_three_explicit_trust_domains(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for job in (
            "trusted-controller:",
            "untrusted-candidate-execution:",
            "trusted-authoritative-verifier:",
        ):
            self.assertIn(job, text)
        self.assertIn("needs: trusted-controller", text)
        self.assertIn("needs: [trusted-controller, untrusted-candidate-execution]", text)
        self.assertIn("UNTRUSTED_EXECUTION_OBSERVATION", text)
        self.assertIn("authoritative-final-gate.json", text)

    def test_embedded_python_has_no_undefined_global_references(self):
        import builtins
        import symtable

        lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
        blocks = []
        index = 0
        while index < len(lines):
            if "<<'PY'" not in lines[index]:
                index += 1
                continue
            start = index + 1
            indent = len(lines[start]) - len(lines[start].lstrip())
            end = start
            while end < len(lines) and lines[end].strip() != "PY":
                end += 1
            self.assertLess(end, len(lines), f"unterminated Python heredoc at line {index + 1}")
            block = "\n".join(line[indent:] for line in lines[start:end]) + "\n"
            blocks.append((index + 1, block))
            index = end + 1

        self.assertGreaterEqual(len(blocks), 10)
        builtin_names = set(dir(builtins))
        for line_number, block in blocks:
            with self.subTest(line=line_number):
                compile(block, f"workflow-heredoc-{line_number}", "exec")
                table = symtable.symtable(block, f"workflow-heredoc-{line_number}", "exec")
                undefined = []
                for name in table.get_identifiers():
                    symbol = table.lookup(name)
                    if (
                        symbol.is_referenced()
                        and not symbol.is_assigned()
                        and not symbol.is_imported()
                        and not symbol.is_parameter()
                        and name not in builtin_names
                    ):
                        undefined.append(name)
                self.assertEqual(undefined, [], f"undefined globals in heredoc: {undefined}")

    def test_controller_manifest_does_not_claim_future_execution_results(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        start = text.index("controller={")
        end = text.index("(root/\"controller-manifest.json\")", start)
        controller_block = text[start:end]
        for field in (
            "trusted_probes_exit_code",
            "candidate_tests_exit_code",
            "sandbox_exit_code",
            "acquisition_exit_code",
        ):
            self.assertNotIn(field, controller_block)

    def test_candidate_never_receives_host_authority_or_evidence_mounts(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("docker:27-dind-rootless@", text)
        self.assertIn("nested_daemon_rootless", text)
        self.assertIn("host_docker_socket_mounted", text)
        self.assertNotIn("-v /var/run/docker.sock:/var/run/docker.sock", text)
        self.assertNotIn("--mount type=bind,src=$EVIDENCE", text)
        self.assertIn("candidate_tests_authority", text)
        self.assertIn("OBSERVATIONAL", text)

    def test_trusted_verifier_is_main_owned_and_candidate_status_is_ignored(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("tools/p1_verifier/verify_candidate.py", text)
        self.assertIn("tools/p1_verifier/acceptance_manifest.json", text)
        self.assertIn("github.workflow_sha", text)
        self.assertIn("candidate_declared_result", VERIFIER.read_text(encoding="utf-8"))
        self.assertIn("IGNORED_FOR_AUTHORITY", VERIFIER.read_text(encoding="utf-8"))


class VerifierFixture:
    def __init__(self, root: Path):
        self.root = root
        self.controller = root / "controller"
        self.execution = root / "execution"
        self.candidate = root / "candidate"
        self.output = root / "output"
        self.source_anchors = root / "source-anchors"
        self.source_anchors.mkdir()
        self.controller.mkdir()
        self.execution.mkdir()
        self.candidate.mkdir()
        self._init_candidate()
        self._init_case_repositories()
        self._write_acceptance()
        self._write_controller()
        self._write_execution()

    def _init_candidate(self):
        _git(self.candidate, "init", "-q")
        (self.candidate / "base.txt").write_text("base\n", encoding="utf-8")
        _git(self.candidate, "add", "base.txt")
        _git(self.candidate, "commit", "-qm", "trusted ADR")
        self.parent = _git(self.candidate, "rev-parse", "HEAD")
        (self.candidate / "candidate.txt").write_text("candidate\n", encoding="utf-8")
        _git(self.candidate, "add", "candidate.txt")
        _git(self.candidate, "commit", "-qm", "candidate")
        self.candidate_sha = _git(self.candidate, "rev-parse", "HEAD")

    def _init_case_repositories(self):
        self.cases = {}
        for case_id in ("001", "002", "003"):
            repo = self.root / f"case-{case_id}"
            repo.mkdir()
            _git(repo, "init", "-q")
            registry = repo / "project_registry"
            registry.mkdir()
            file_path = registry / "registry.py"
            file_path.write_text(f"VALUE = {case_id!r}\n", encoding="utf-8")
            (repo / "PILOT_CONTRACT.md").write_text("trusted contract\n", encoding="utf-8")
            _git(repo, "add", ".")
            _git(repo, "commit", "-qm", f"case {case_id} input")
            input_commit = _git(repo, "rev-parse", "HEAD")
            file_path.write_text(f"VALUE = 'fixed-{case_id}'\n", encoding="utf-8")
            _git(repo, "add", ".")
            _git(repo, "commit", "-qm", f"case {case_id} result")
            result_commit = _git(repo, "rev-parse", "HEAD")
            anchor = self.source_anchors / f"case-{case_id}"
            _git(self.source_anchors, "clone", "-q", str(repo), str(anchor))
            _git(anchor, "checkout", "-q", "--detach", input_commit)
            bundle = self.execution / "results" / f"case-{case_id}.bundle"
            bundle.parent.mkdir(parents=True, exist_ok=True)
            _git(repo, "bundle", "create", str(bundle), "--all")
            self.cases[case_id] = {
                "input_commit": input_commit,
                "result_commit": result_commit,
                "bundle": bundle,
            }

    def _write_acceptance(self):
        value = {
            "schema_version": 1,
            "authorized_target_ref": "agent/pilot-runtime-replacement",
            "required_parent_sha": self.parent,
            "candidate_tests_authority": "OBSERVATIONAL",
            "candidate_declared_result_authority": "IGNORED_FOR_AUTHORITY",
            "canonical_source_url": "https://github.com/litrgratis-pixel/executor-pilot-target.git",
            "source_repository": "litrgratis-pixel/executor-pilot-target",
            "contract_path": "PILOT_CONTRACT.md",
            "required_contract_blob": _git(next(iter(self.source_anchors.iterdir())), "rev-parse", "HEAD:PILOT_CONTRACT.md"),
            "allowed_changed_paths": ["candidate.txt"],
            "required_controller_files": [
                "controller-manifest.json",
                "workflow-identities.json",
                "scope-report.json",
                "candidate-source.bundle",
                "controller-workflow.yml",
                "candidate-verify.yml",
                "trusted-verifier.py",
                "acceptance-manifest.json",
            ],
            "required_execution_files": [
                "observation-manifest.json",
                "process-tree.txt",
                "network-observation.json",
                "cleanup-state.json",
                "nested-docker-security.json",
                "logs/trusted-probes.log",
                "logs/trusted-probes.log",
            "logs/candidate-tests.log",
                "logs/sandbox.log",
                "logs/acquisition.log",
                "logs/case-001.log",
                "logs/case-002.log",
                "logs/case-003.log",
                "traces/trusted-probes.execve",
                "traces/trusted-probes.execve",
            "traces/candidate-tests.execve",
                "traces/sandbox.execve",
                "traces/trusted-probes.execve",
                "traces/trusted-probes.execve",
            "traces/candidate-tests.execve",
            "traces/sandbox.execve",
            "traces/acquisition.execve",
                "traces/case-001.execve",
                "traces/case-002.execve",
                "traces/case-003.execve",
                "results/case-001.bundle",
                "results/case-002.bundle",
                "results/case-003.bundle",
                "results/source_acquisition.json",
                "results/source_manifest.json",
            ],
            "forbidden_candidate_environment": [
                "GITHUB_TOKEN",
                "GITHUB_ENV",
                "GITHUB_OUTPUT",
            ],
            "forbidden_candidate_mount_fragments": [
                "/var/run/docker.sock",
                "controller",
                "evidence",
                "p1_verifier",
            ],
            "cases": {
                case_id: {
                    "input_commit": data["input_commit"],
                    "allowed_path": "project_registry/registry.py",
                    "required_status": "ACTION_COMPLETED_REVIEW_REQUIRED",
                }
                for case_id, data in self.cases.items()
            },
        }
        self.acceptance = self.root / "acceptance.json"
        _write_json(self.acceptance, value)

    def _write_controller(self):
        bundle = self.controller / "candidate-source.bundle"
        _git(self.candidate, "bundle", "create", str(bundle), "--all")
        files = {
            "controller-workflow.yml": "trusted workflow\n",
            "candidate-verify.yml": "candidate workflow\n",
            "trusted-verifier.py": VERIFIER.read_text(encoding="utf-8"),
            "acceptance-manifest.json": self.acceptance.read_text(encoding="utf-8"),
        }
        for name, content in files.items():
            (self.controller / name).write_text(content, encoding="utf-8")
        _write_json(
            self.controller / "controller-manifest.json",
            {
                "schema_version": 1,
                "event_name": "workflow_dispatch",
                "target_ref": "agent/pilot-runtime-replacement",
                "expected_sha": self.candidate_sha,
                "candidate_sha": self.candidate_sha,
                "execution_mode": "verify-candidate",
                "parent_sha": self.parent,
                "workflow_sha": self.parent,
                "candidate_bundle_sha256": _sha256(bundle),
                "candidate_tests_authority": "OBSERVATIONAL",
                "trusted_probes_exit_code": 0,
                "candidate_tests_exit_code": 0,
                "sandbox_exit_code": 0,
                "acquisition_exit_code": 0,
            },
        )
        _write_json(
            self.controller / "scope-report.json",
            {"schema_version": 1, "status": "PASS", "changed_paths": ["candidate.txt"]},
        )
        _write_json(
            self.controller / "workflow-identities.json",
            {
                key: {
                    "artifact_path": path,
                    "sha256": _sha256(self.controller / path),
                }
                for key, path in {
                    "controller_workflow": "controller-workflow.yml",
                    "candidate_workflow": "candidate-verify.yml",
                    "trusted_verifier": "trusted-verifier.py",
                    "acceptance_manifest": "acceptance-manifest.json",
                }.items()
            },
        )
        _hash_manifest(self.controller)

    def _write_execution(self):
        for relative in (
            "process-tree.txt",
            "nested-docker-security.json",
            "logs/trusted-probes.log",
            "logs/candidate-tests.log",
            "logs/sandbox.log",
            "logs/acquisition.log",
            "logs/case-001.log",
            "logs/case-002.log",
            "logs/case-003.log",
            "traces/trusted-probes.execve",
            "traces/candidate-tests.execve",
            "traces/sandbox.execve",
            "traces/acquisition.execve",
            "traces/case-001.execve",
            "traces/case-002.execve",
            "traces/case-003.execve",
        ):
            path = self.execution / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            content=f"trusted observation {relative}\n"
            if relative == "logs/trusted-probes.log":
                content="TRUSTED_BLACK_BOX_PROBES: PASS\n"
            elif relative == "logs/sandbox.log":
                content="Ran 10 tests in 1.0s\n\nOK\n"
            elif relative == "traces/sandbox.execve":
                content='execve("docker", ["docker","run","--network","none"])\n'
            path.write_text(content, encoding="utf-8")
        (self.execution / "nested-docker-security.json").write_text("[\"name=rootless\"]\n", encoding="utf-8")
        (self.execution / "traces/acquisition.execve").write_text(
            'execve("docker", ["docker","run","--network","bridge","https://github.com/litrgratis-pixel/executor-pilot-target.git"])\n'
            'execve("docker", ["docker","run","--network","none"])\n', encoding="utf-8")
        for case_id in ("001", "002", "003"):
            (self.execution / "traces" / f"case-{case_id}.execve").write_text(
                'execve("docker", ["docker","run","--network","none"])\n', encoding="utf-8")
        _write_json(
            self.execution / "network-observation.json",
            {
                "candidate_network": "internal-only",
                "nested_daemon_egress": True,
                "host_docker_socket_mounted": False,
            },
        )
        _write_json(
            self.execution / "results/source_acquisition.json",
            {
                "input_model": "CONTROLLED_HTTPS_FETCH_V1",
                "request": {"repository": "litrgratis-pixel/executor-pilot-target"},
                "origin_anchor": {
                    "canonical_url": "https://github.com/litrgratis-pixel/executor-pilot-target.git",
                    "local_checkout_used": False,
                    "user_supplied_url_used": False,
                },
                "outcome": "ACQUIRED_REVIEW_REQUIRED",
            },
        )
        _write_json(self.execution / "results/source_manifest.json", {"entries": []})
        _write_json(
            self.execution / "cleanup-state.json",
            {"cleanup_confirmed": True},
        )
        cases = {}
        for case_id, data in self.cases.items():
            cases[case_id] = {
                "exit_code": 0,
                "skipped": False,
                "harness_status": "OBSERVED_COMPLETED",
                "log_path": f"logs/case-{case_id}.log",
                "trace_path": f"traces/case-{case_id}.execve",
                "bundle_path": f"results/case-{case_id}.bundle",
                "bundle_sha256": _sha256(data["bundle"]),
                "result_commit": data["result_commit"],
                "candidate_status": "ACTION_COMPLETED_REVIEW_REQUIRED",
            }
        _write_json(
            self.execution / "observation-manifest.json",
            {
                "schema_version": 1,
                "candidate_sha": self.candidate_sha,
                "execution_mode": "verify-candidate",
                "observation_authority": "TRUSTED_HOST_HARNESS",
                "candidate_process_domain": "UNTRUSTED_NESTED_CONTAINER",
                "nested_daemon_rootless": True,
                "candidate_direct_egress": False,
                "nested_daemon_egress": True,
                "host_docker_socket_mounted": False,
                "controller_evidence_visible": False,
                "verifier_bundle_visible": False,
                "github_token_visible": False,
                "secrets_visible": False,
                "cleanup_confirmed": True,
                "candidate_tests_authority": "OBSERVATIONAL",
                "trusted_probes_exit_code": 0,
                "candidate_tests_exit_code": 0,
                "sandbox_exit_code": 0,
                "acquisition_exit_code": 0,
                "candidate_environment_names": ["PATH", "DOCKER_HOST"],
                "candidate_mounts": [
                    {"source": "candidate-source-volume", "destination": "/candidate"},
                    {"source": "candidate-runs-volume", "destination": "/runs"},
                ],
                "candidate_declared_result": "ABSENT",
                "candidate_boundary_markers": [],
                "cases": cases,
            },
        )
        _hash_manifest(self.execution)


class AuthoritativeVerifierTests(unittest.TestCase):
    def test_valid_trusted_observation_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = VerifierFixture(Path(temporary))
            report = verify(
                acceptance_path=fixture.acceptance,
                controller_dir=fixture.controller,
                execution_dir=fixture.execution,
                candidate_dir=fixture.candidate,
                source_anchor_root=fixture.source_anchors,
                output_dir=fixture.output,
            )
        self.assertEqual(report["authoritative_result"], "PASS", report["errors"])
        self.assertEqual(
            report["candidate_declared_result_authority"],
            "IGNORED_FOR_AUTHORITY",
        )

    def test_malicious_candidate_cannot_influence_authoritative_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = VerifierFixture(Path(temporary))
            malicious = fixture.execution / "candidate-declared" / "final_gate.json"
            _write_json(malicious, {"status": "PASS", "result": "SUCCESS"})
            observation_path = fixture.execution / "observation-manifest.json"
            observation = json.loads(observation_path.read_text(encoding="utf-8"))
            observation.update(
                {
                    "host_docker_socket_mounted": True,
                    "controller_evidence_visible": True,
                    "github_token_visible": True,
                    "candidate_environment_names": [
                        "PATH",
                        "GITHUB_TOKEN",
                        "GITHUB_ENV",
                        "GITHUB_OUTPUT",
                    ],
                    "candidate_mounts": [
                        {
                            "source": "/var/run/docker.sock",
                            "destination": "/var/run/docker.sock",
                        },
                        {
                            "source": "/runner/controller-evidence",
                            "destination": "/evidence",
                        },
                    ],
                    "candidate_declared_result": "PASS",
                    "candidate_boundary_markers": [
                        "overwrote-manifest",
                        "wrote-github-output",
                        "restored-files-after-forgery",
                    ],
                }
            )
            _write_json(observation_path, observation)
            # A malicious candidate may recompute hashes for files it controls. The
            # authoritative verifier still rejects boundary exposure and ignores PASS.
            _hash_manifest(fixture.execution)
            report = verify(
                acceptance_path=fixture.acceptance,
                controller_dir=fixture.controller,
                execution_dir=fixture.execution,
                candidate_dir=fixture.candidate,
                source_anchor_root=fixture.source_anchors,
                output_dir=fixture.output,
            )
            final_gate = json.loads(
                (fixture.output / "authoritative-final-gate.json").read_text(
                    encoding="utf-8"
                )
            )
        self.assertEqual(report["authoritative_result"], "FAIL")
        self.assertEqual(final_gate["authoritative_result"], "FAIL")
        self.assertEqual(final_gate["candidate_declared_result"], "PASS")
        self.assertEqual(
            final_gate["candidate_declared_result_authority"],
            "IGNORED_FOR_AUTHORITY",
        )
        joined = "\n".join(final_gate["errors"])
        self.assertIn("host Docker socket", joined)
        self.assertIn("forbidden authority boundary", joined)
        self.assertIn("terminal PASS observed and ignored", joined)

    def test_wrong_candidate_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = VerifierFixture(Path(temporary))
            controller_path = fixture.controller / "controller-manifest.json"
            controller = json.loads(controller_path.read_text(encoding="utf-8"))
            controller["expected_sha"] = "f" * 40
            _write_json(controller_path, controller)
            _hash_manifest(fixture.controller)
            report = verify(
                acceptance_path=fixture.acceptance,
                controller_dir=fixture.controller,
                execution_dir=fixture.execution,
                candidate_dir=fixture.candidate,
                source_anchor_root=fixture.source_anchors,
                output_dir=fixture.output,
            )
        self.assertEqual(report["authoritative_result"], "FAIL")
        self.assertIn(
            "controller expected_sha does not equal candidate_sha",
            report["errors"],
        )

    def test_wrong_contract_blob_is_rejected_by_independent_anchor(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = VerifierFixture(Path(temporary))
            acceptance = json.loads(fixture.acceptance.read_text(encoding="utf-8"))
            acceptance["required_contract_blob"] = "f" * 40
            _write_json(fixture.acceptance, acceptance)
            # Keep the controller's trusted copy and identity coherent with the
            # intentionally wrong trusted acceptance input.
            shutil.copyfile(fixture.acceptance, fixture.controller / "acceptance-manifest.json")
            identities = json.loads(
                (fixture.controller / "workflow-identities.json").read_text(encoding="utf-8")
            )
            identities["acceptance_manifest"]["sha256"] = _sha256(
                fixture.controller / "acceptance-manifest.json"
            )
            _write_json(fixture.controller / "workflow-identities.json", identities)
            _hash_manifest(fixture.controller)
            report = verify(
                acceptance_path=fixture.acceptance,
                controller_dir=fixture.controller,
                execution_dir=fixture.execution,
                candidate_dir=fixture.candidate,
                source_anchor_root=fixture.source_anchors,
                output_dir=fixture.output,
            )
        self.assertEqual(report["authoritative_result"], "FAIL")
        self.assertTrue(
            any("independent contract blob mismatch" in error for error in report["errors"]),
            report["errors"],
        )

    def test_missing_trace_and_result_bundle_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = VerifierFixture(Path(temporary))
            (fixture.execution / "traces/case-002.execve").unlink()
            (fixture.execution / "results/case-003.bundle").unlink()
            _hash_manifest(fixture.execution)
            report = verify(
                acceptance_path=fixture.acceptance,
                controller_dir=fixture.controller,
                execution_dir=fixture.execution,
                candidate_dir=fixture.candidate,
                source_anchor_root=fixture.source_anchors,
                output_dir=fixture.output,
            )
        self.assertEqual(report["authoritative_result"], "FAIL")
        joined = "\n".join(report["errors"])
        self.assertIn("CASE-002 trace", joined)
        self.assertIn("CASE-003 result bundle missing", joined)


if __name__ == "__main__":
    unittest.main()
