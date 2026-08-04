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
VULNERABLE_WORKFLOW_SHA256 = "84bcee1cc9aa4c32d5036fcdce55bb102baa96441429c373940b0968dd09a1f7"
GIT_IMAGE = "alpine/git@sha256:0448d24b454392f9d115c6784343899e9d35a32de0ddc39a745263db34df94dd"
PYTHON_IMAGE = "python@sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba"
CANONICAL_URL = "https://github.com/litrgratis-pixel/executor-pilot-target.git"


def _canonical_bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _canonical_sha(value) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(value))


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


def _hash_manifest(root: Path) -> None:
    files = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == "files-sha256.json":
            continue
        files[relative] = _sha256(path)
    _write_json(root / "files-sha256.json", {"schema_version": 1, "files": files})


class WorkflowTrustBoundaryTests(unittest.TestCase):
    def test_vulnerable_baseline_is_not_current(self):
        self.assertTrue(WORKFLOW.is_file())
        self.assertNotEqual(_sha256(WORKFLOW), VULNERABLE_WORKFLOW_SHA256)

    def test_workflow_has_three_explicit_trust_domains(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for marker in (
            "trusted-controller:",
            "untrusted-candidate-execution:",
            "trusted-authoritative-verifier:",
            "UNTRUSTED_EXECUTION_OBSERVATION",
            "authoritative-final-gate.json",
        ):
            self.assertIn(marker, text)

    def test_trusted_collector_is_ready_before_candidate_execution(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        collector = text.index("Start trusted nested operation collector")
        candidate = text.index("Run candidate only inside the untrusted nested domain")
        finalize = text.index("Finalize trusted nested operation ledger")
        self.assertLess(collector, candidate)
        self.assertLess(candidate, finalize)
        self.assertIn("ready_before_candidate", text)
        self.assertIn("nested-operation-ledger.json", text)
        self.assertIn("approved-nested-images.json", text)

    def test_candidate_never_receives_host_authority_or_evidence_mounts(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("docker:27-dind-rootless@", text)
        self.assertNotIn("-v /var/run/docker.sock:/var/run/docker.sock", text)
        self.assertNotIn("--mount type=bind,src=$OBSERVATION", text)
        self.assertIn("candidate_tests_authority", text)
        self.assertIn("OBSERVATIONAL", text)

    def test_verifier_is_main_owned_and_candidate_status_is_ignored(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        verifier = VERIFIER.read_text(encoding="utf-8")
        self.assertIn("tools/p1_verifier/verify_candidate.py", workflow)
        self.assertIn("github.workflow_sha", workflow)
        self.assertIn("IGNORED_FOR_AUTHORITY", verifier)
        self.assertIn("_verify_nested_operation_ledger", verifier)

    def test_pinned_actionlint_accepts_manual_workflow_in_github_actions(self):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            self.skipTest("pinned actionlint integration runs in GitHub Actions")
        archive_sha = "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"
        url = (
            "https://github.com/rhysd/actionlint/releases/download/v1.7.12/"
            "actionlint_1.7.12_linux_amd64.tar.gz"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "actionlint.tar.gz"
            subprocess.run(
                [
                    "curl", "--fail", "--location", "--proto", "=https",
                    "--tlsv1.2", "--output", str(archive), url,
                ],
                check=True,
            )
            self.assertEqual(_sha256(archive), archive_sha)
            subprocess.run(
                ["tar", "-xzf", str(archive), "-C", str(root), "actionlint"],
                check=True,
            )
            completed = subprocess.run(
                [str(root / "actionlint"), "-shellcheck=", str(WORKFLOW)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)


class VerifierFixture:
    def __init__(self, root: Path):
        self.root = root
        self.controller = root / "controller"
        self.execution = root / "execution"
        self.candidate = root / "candidate"
        self.output = root / "output"
        self.source_anchors = root / "source-anchors"
        for path in (self.controller, self.execution, self.candidate, self.source_anchors):
            path.mkdir(parents=True)
        self._init_candidate()
        self._init_case_repositories()
        self._write_acceptance()
        self._write_controller()
        self._write_execution()

    def _init_candidate(self) -> None:
        _git(self.candidate, "init", "-q")
        (self.candidate / "base.txt").write_text("base\n")
        _git(self.candidate, "add", "base.txt")
        _git(self.candidate, "commit", "-qm", "trusted ADR")
        self.parent = _git(self.candidate, "rev-parse", "HEAD")
        (self.candidate / "candidate.txt").write_text("candidate\n")
        _git(self.candidate, "add", "candidate.txt")
        _git(self.candidate, "commit", "-qm", "candidate")
        self.candidate_sha = _git(self.candidate, "rev-parse", "HEAD")

    def _init_case_repositories(self) -> None:
        self.cases = {}
        for case_id in ("001", "002", "003"):
            repo = self.root / f"case-{case_id}"
            repo.mkdir()
            _git(repo, "init", "-q")
            registry = repo / "project_registry"
            registry.mkdir()
            target = registry / "registry.py"
            target.write_text(f"VALUE = {case_id!r}\n")
            (repo / "PILOT_CONTRACT.md").write_text("trusted contract\n")
            _git(repo, "add", ".")
            _git(repo, "commit", "-qm", f"case {case_id} input")
            input_commit = _git(repo, "rev-parse", "HEAD")
            target.write_text(f"VALUE = 'fixed-{case_id}'\n")
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

    def _write_acceptance(self) -> None:
        value = json.loads(ACCEPTANCE.read_text())
        value["required_parent_sha"] = self.parent
        value["allowed_changed_paths"] = ["candidate.txt"]
        value["required_contract_blob"] = _git(
            self.source_anchors / "case-001", "rev-parse", "HEAD:PILOT_CONTRACT.md"
        )
        value["cases"] = {
            case_id: {
                "input_commit": data["input_commit"],
                "allowed_path": "project_registry/registry.py",
                "required_status": "ACTION_COMPLETED_REVIEW_REQUIRED",
            }
            for case_id, data in self.cases.items()
        }
        self.acceptance = self.root / "acceptance.json"
        _write_json(self.acceptance, value)

    def _write_controller(self) -> None:
        bundle = self.controller / "candidate-source.bundle"
        _git(self.candidate, "bundle", "create", str(bundle), "--all")
        files = {
            "controller-workflow.yml": "trusted workflow\n",
            "candidate-verify.yml": "candidate workflow\n",
            "trusted-verifier.py": VERIFIER.read_text(),
            "acceptance-manifest.json": self.acceptance.read_text(),
        }
        for name, content in files.items():
            (self.controller / name).write_text(content)
        _write_json(self.controller / "controller-manifest.json", {
            "schema_version": 1,
            "event_name": "workflow_dispatch",
            "target_ref": "agent/pilot-runtime-replacement",
            "expected_sha": self.candidate_sha,
            "candidate_sha": self.candidate_sha,
            "parent_sha": self.parent,
            "workflow_sha": self.parent,
            "execution_mode": "verify-candidate",
            "candidate_bundle_sha256": _sha256(bundle),
            "candidate_tests_authority": "OBSERVATIONAL",
        })
        _write_json(self.controller / "scope-report.json", {
            "schema_version": 1,
            "status": "PASS",
            "changed_paths": ["candidate.txt"],
        })
        _write_json(self.controller / "workflow-identities.json", {
            key: {"artifact_path": path, "sha256": _sha256(self.controller / path)}
            for key, path in {
                "controller_workflow": "controller-workflow.yml",
                "candidate_workflow": "candidate-verify.yml",
                "trusted_verifier": "trusted-verifier.py",
                "acceptance_manifest": "acceptance-manifest.json",
            }.items()
        })
        _hash_manifest(self.controller)

    @staticmethod
    def _inspect(
        *, container_id: str, image_ref: str, image_id: str,
        network: str, command: list[str], mounts: list[dict] | None = None,
    ) -> dict:
        return {
            "Id": container_id,
            "Image": image_id,
            "Config": {"Image": image_ref, "Entrypoint": command[:1], "Cmd": command[1:], "Env": []},
            "HostConfig": {
                "NetworkMode": network,
                "Privileged": False,
                "CapAdd": None,
                "CapDrop": ["ALL"],
                "SecurityOpt": ["no-new-privileges"],
                "PidMode": "",
                "IpcMode": "private",
                "UTSMode": "",
                "CgroupnsMode": "private",
                "Devices": [],
                "DeviceRequests": [],
                "VolumesFrom": [],
            },
            "Mounts": mounts or [],
        }

    def _valid_ledger(self) -> tuple[dict, dict]:
        git_id = "sha256:" + "1" * 64
        python_id = "sha256:" + "2" * 64
        approved = {
            "schema_version": 1,
            "authority": "TRUSTED_HOST_HARNESS",
            "images": {
                GIT_IMAGE: {"id": git_id, "repo_digests": [GIT_IMAGE]},
                PYTHON_IMAGE: {"id": python_id, "repo_digests": [PYTHON_IMAGE]},
            },
        }
        containers = [
            self._inspect(
                container_id="a" * 64, image_ref=GIT_IMAGE, image_id=git_id, network="bridge",
                command=["/bin/busybox", "env", "-i", "PATH=/usr/bin:/bin",
                         "/usr/bin/git", "fetch", CANONICAL_URL, self.cases["001"]["input_commit"]],
                mounts=[{"Source": "/runs/case-001", "Destination": "/executor-run"}],
            ),
            self._inspect(
                container_id="b" * 64, image_ref=GIT_IMAGE, image_id=git_id, network="bridge",
                command=["/bin/busybox", "env", "-i", "PATH=/usr/bin:/bin",
                         "/usr/bin/git", "fetch", CANONICAL_URL, self.cases["002"]["input_commit"]],
                mounts=[{"Source": "/runs/case-002", "Destination": "/executor-run"}],
            ),
            self._inspect(
                container_id="c" * 64, image_ref=GIT_IMAGE, image_id=git_id, network="bridge",
                command=["/bin/busybox", "env", "-i", "PATH=/usr/bin:/bin",
                         "/usr/bin/git", "fetch", CANONICAL_URL, self.cases["003"]["input_commit"]],
                mounts=[{"Source": "/runs/case-003", "Destination": "/executor-run"}],
            ),
            self._inspect(
                container_id="d" * 64, image_ref=GIT_IMAGE, image_id=git_id, network="none",
                command=["/bin/busybox", "env", "-i", "/usr/bin/git", "fsck", "--strict"],
                mounts=[{"Source": "/runs/case-001", "Destination": "/executor-run"}],
            ),
            self._inspect(
                container_id="e" * 64, image_ref=PYTHON_IMAGE, image_id=python_id, network="none",
                command=["python", "-m", "unittest", "discover"],
                mounts=[{"Source": "/candidate", "Destination": "/source"},
                        {"Source": "/runs/workspace", "Destination": "/workspace"}],
            ),
        ]
        events = []
        sequence = 1
        time_nano = 1_000_000
        for inspect in containers:
            events.append({
                "sequence": sequence,
                "type": "container",
                "action": "create",
                "id": inspect["Id"],
                "time_nano": time_nano,
                "inspect": inspect,
                "inspect_sha256": _canonical_sha(inspect),
                "inspect_error": None,
            })
            sequence += 1
            time_nano += 1
            for action in ("start", "die", "destroy"):
                events.append({
                    "sequence": sequence,
                    "type": "container",
                    "action": action,
                    "id": inspect["Id"],
                    "time_nano": time_nano,
                })
                sequence += 1
                time_nano += 1
        ledger = {
            "schema_version": 1,
            "collector_authority": "TRUSTED_HOST_HARNESS",
            "ready_before_candidate": True,
            "complete": True,
            "overflow": False,
            "collector_error": None,
            "approved_images_sha256": "",
            "events": events,
        }
        return approved, ledger

    def _write_execution(self) -> None:
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
            content = f"trusted observation {relative}\n"
            if relative == "logs/trusted-probes.log":
                content = "TRUSTED_BLACK_BOX_PROBES: PASS\n"
            elif relative == "logs/sandbox.log":
                content = "Ran 10 tests in 1.0s\n\nOK\n"
            path.write_text(content)
        (self.execution / "nested-docker-security.json").write_text('["name=rootless"]\n')

        approved, ledger = self._valid_ledger()
        _write_json(self.execution / "approved-nested-images.json", approved)
        ledger["approved_images_sha256"] = _sha256(self.execution / "approved-nested-images.json")
        _write_json(self.execution / "nested-operation-ledger.json", ledger)

        _write_json(self.execution / "network-observation.json", {
            "candidate_network": "internal-only",
            "nested_daemon_egress": True,
            "host_docker_socket_mounted": False,
        })
        _write_json(self.execution / "results/source_acquisition.json", {
            "input_model": "CONTROLLED_HTTPS_FETCH_V1",
            "request": {"repository": "litrgratis-pixel/executor-pilot-target"},
            "origin_anchor": {
                "canonical_url": CANONICAL_URL,
                "local_checkout_used": False,
                "user_supplied_url_used": False,
            },
            "outcome": "ACQUIRED_REVIEW_REQUIRED",
        })
        _write_json(self.execution / "results/source_manifest.json", {"entries": []})
        _write_json(self.execution / "cleanup-state.json", {"cleanup_confirmed": True})

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
        _write_json(self.execution / "observation-manifest.json", {
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
            "candidate_environment_names": ["PATH", "DOCKER_HOST", "TMPDIR"],
            "candidate_mounts": [
                {"source": "candidate-source-volume", "destination": "/candidate"},
                {"source": "candidate-runs-volume", "destination": "/runs"},
            ],
            "candidate_declared_result": "ABSENT",
            "candidate_boundary_markers": [],
            "cases": cases,
        })
        _hash_manifest(self.execution)

    def rewrite_ledger(self, mutate) -> None:
        path = self.execution / "nested-operation-ledger.json"
        ledger = json.loads(path.read_text())
        mutate(ledger)
        _write_json(path, ledger)
        _hash_manifest(self.execution)


class AuthoritativeVerifierTests(unittest.TestCase):
    def _verify(self, fixture: VerifierFixture):
        return verify(
            acceptance_path=fixture.acceptance,
            controller_dir=fixture.controller,
            execution_dir=fixture.execution,
            candidate_dir=fixture.candidate,
            source_anchor_root=fixture.source_anchors,
            output_dir=fixture.output,
        )

    def test_valid_trusted_observation_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = VerifierFixture(Path(temporary))
            report = self._verify(fixture)
        self.assertEqual(report["authoritative_result"], "PASS", report["errors"])
        self.assertEqual(report["nested_operation_summary"]["network_enabled"], 3)

    def test_missing_trusted_nested_operation_ledger_is_rejected(self):
        """Plausible text evidence cannot replace daemon-owned operation provenance."""
        with tempfile.TemporaryDirectory() as temporary:
            fixture = VerifierFixture(Path(temporary))
            (fixture.execution / "nested-operation-ledger.json").unlink()
            _hash_manifest(fixture.execution)
            report = self._verify(fixture)
        self.assertEqual(report["authoritative_result"], "FAIL", report)
        self.assertTrue(
            any("nested operation ledger" in error.lower() for error in report["errors"]),
            report["errors"],
        )

    def test_unapproved_image_and_second_network_container_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = VerifierFixture(Path(temporary))
            def mutate(ledger):
                creates = [event for event in ledger["events"] if event["action"] == "create"]
                creates[3]["inspect"]["Config"]["Image"] = "attacker/image:latest"
                creates[3]["inspect"]["HostConfig"]["NetworkMode"] = "bridge"
                creates[3]["inspect_sha256"] = _canonical_sha(creates[3]["inspect"])
            fixture.rewrite_ledger(mutate)
            report = self._verify(fixture)
        joined = "\n".join(report["errors"])
        self.assertEqual(report["authoritative_result"], "FAIL")
        self.assertIn("unapproved image", joined)
        self.assertIn("network-enabled containers", joined)

    def test_privileged_capability_and_outside_mount_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = VerifierFixture(Path(temporary))
            def mutate(ledger):
                create = next(event for event in ledger["events"] if event["action"] == "create")
                inspect = create["inspect"]
                inspect["HostConfig"]["Privileged"] = True
                inspect["HostConfig"]["CapAdd"] = ["SYS_ADMIN"]
                inspect["Mounts"].append({"Source": "/etc", "Destination": "/host-etc"})
                create["inspect_sha256"] = _canonical_sha(inspect)
            fixture.rewrite_ledger(mutate)
            report = self._verify(fixture)
        joined = "\n".join(report["errors"])
        self.assertEqual(report["authoritative_result"], "FAIL")
        self.assertIn("is privileged", joined)
        self.assertIn("adds capabilities", joined)
        self.assertIn("outside isolated roots", joined)

    def test_missing_create_inspect_and_nested_exec_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = VerifierFixture(Path(temporary))
            def mutate(ledger):
                create = next(event for event in ledger["events"] if event["action"] == "create")
                create.pop("inspect")
                create.pop("inspect_sha256")
                ledger["events"].append({
                    "sequence": len(ledger["events"]) + 1,
                    "type": "container",
                    "action": "exec_create",
                    "id": "a" * 64,
                    "time_nano": 2_000_000,
                })
            fixture.rewrite_ledger(mutate)
            report = self._verify(fixture)
        joined = "\n".join(report["errors"])
        self.assertEqual(report["authoritative_result"], "FAIL")
        self.assertIn("create inspect missing", joined)
        self.assertIn("exec operations are forbidden", joined)

    def test_malicious_candidate_pass_and_boundary_writes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = VerifierFixture(Path(temporary))
            malicious = fixture.execution / "candidate-declared" / "final_gate.json"
            _write_json(malicious, {"status": "PASS"})
            path = fixture.execution / "observation-manifest.json"
            observation = json.loads(path.read_text())
            observation.update({
                "host_docker_socket_mounted": True,
                "controller_evidence_visible": True,
                "github_token_visible": True,
                "candidate_declared_result": "PASS",
                "candidate_boundary_markers": ["wrote-github-output"],
            })
            _write_json(path, observation)
            _hash_manifest(fixture.execution)
            report = self._verify(fixture)
        joined = "\n".join(report["errors"])
        self.assertEqual(report["authoritative_result"], "FAIL")
        self.assertEqual(report["candidate_declared_result_authority"], "IGNORED_FOR_AUTHORITY")
        self.assertIn("host Docker socket", joined)
        self.assertIn("terminal PASS observed and ignored", joined)

    def test_wrong_candidate_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = VerifierFixture(Path(temporary))
            path = fixture.controller / "controller-manifest.json"
            controller = json.loads(path.read_text())
            controller["expected_sha"] = "f" * 40
            _write_json(path, controller)
            _hash_manifest(fixture.controller)
            report = self._verify(fixture)
        self.assertIn("controller expected_sha does not equal candidate_sha", report["errors"])

    def test_wrong_contract_blob_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = VerifierFixture(Path(temporary))
            acceptance = json.loads(fixture.acceptance.read_text())
            acceptance["required_contract_blob"] = "f" * 40
            _write_json(fixture.acceptance, acceptance)
            shutil.copyfile(fixture.acceptance, fixture.controller / "acceptance-manifest.json")
            identities_path = fixture.controller / "workflow-identities.json"
            identities = json.loads(identities_path.read_text())
            identities["acceptance_manifest"]["sha256"] = _sha256(
                fixture.controller / "acceptance-manifest.json"
            )
            _write_json(identities_path, identities)
            _hash_manifest(fixture.controller)
            report = self._verify(fixture)
        self.assertTrue(any("contract blob mismatch" in error for error in report["errors"]))

    def test_missing_result_bundle_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = VerifierFixture(Path(temporary))
            (fixture.execution / "results/case-003.bundle").unlink()
            _hash_manifest(fixture.execution)
            report = self._verify(fixture)
        self.assertIn("CASE-003 result bundle missing", report["errors"])


if __name__ == "__main__":
    unittest.main()
