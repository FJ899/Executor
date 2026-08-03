from __future__ import annotations

import hashlib
import json
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


class WorkflowTrustBoundaryTests(unittest.TestCase):
    def test_vulnerable_baseline_is_not_current(self):
        self.assertNotEqual(
            sha256(WORKFLOW),
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
        self.assertIn("UNTRUSTED_EXECUTION_OBSERVATION", text)
        self.assertIn("authoritative-final-gate.json", text)
        self.assertIn("needs: trusted-controller", text)

    def test_candidate_has_no_host_authority_or_evidence_mount(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("docker:27-dind-rootless@", text)
        self.assertIn("nested_daemon_rootless", text)
        self.assertIn("host_docker_socket_mounted", text)
        self.assertNotIn("-v /var/run/docker.sock:/var/run/docker.sock", text)
        self.assertNotIn("--mount type=bind,src=$EVIDENCE", text)
        self.assertIn("candidate_tests_authority", text)
        self.assertIn("OBSERVATIONAL", text)

    def test_trusted_verifier_is_main_owned(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("tools/p1_verifier/verify_candidate.py", text)
        self.assertIn("tools/p1_verifier/acceptance_manifest.json", text)
        self.assertIn("github.workflow_sha", text)
        verifier = VERIFIER.read_text(encoding="utf-8")
        self.assertNotIn("import executor", verifier)
        self.assertIn("IGNORED_FOR_AUTHORITY", verifier)

    def test_scope_v2_manifest_is_closed(self):
        manifest = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["candidate_tests_authority"], "OBSERVATIONAL")
        self.assertEqual(set(manifest["cases"]), {"001", "002", "003"})
        self.assertEqual(len(manifest["allowed_changed_paths"]), 13)


class MaliciousCandidateVerifierTests(unittest.TestCase):
    def test_candidate_pass_and_boundary_writes_cannot_become_authoritative(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            controller = root / "controller"
            execution = root / "execution"
            candidate = root / "candidate"
            output = root / "output"
            controller.mkdir()
            execution.mkdir()
            candidate.mkdir()

            write_json(
                controller / "controller-manifest.json",
                {
                    "event_name": "workflow_dispatch",
                    "target_ref": "agent/pilot-runtime-replacement",
                    "expected_sha": "3f6e4196af4b9144ceaaba08f2b6637acdc1698d",
                    "candidate_sha": "3f6e4196af4b9144ceaaba08f2b6637acdc1698d",
                    "parent_sha": "bf18638caeb1a01cd2e14e625d72a20893a04bb3",
                    "workflow_sha": "0" * 40,
                    "candidate_tests_authority": "OBSERVATIONAL",
                },
            )
            write_json(controller / "scope-report.json", {"status": "FAIL", "changed_paths": []})
            write_json(controller / "workflow-identities.json", {})
            write_json(controller / "files-sha256.json", {"files": {}})

            write_json(
                execution / "observation-manifest.json",
                {
                    "candidate_sha": "3f6e4196af4b9144ceaaba08f2b6637acdc1698d",
                    "observation_authority": "TRUSTED_HOST_HARNESS",
                    "candidate_process_domain": "UNTRUSTED_NESTED_CONTAINER",
                    "nested_daemon_rootless": True,
                    "host_docker_socket_mounted": True,
                    "controller_evidence_visible": True,
                    "verifier_bundle_visible": True,
                    "github_token_visible": True,
                    "secrets_visible": True,
                    "cleanup_confirmed": False,
                    "candidate_tests_authority": "OBSERVATIONAL",
                    "candidate_environment_names": ["GITHUB_TOKEN", "GITHUB_ENV", "GITHUB_OUTPUT"],
                    "candidate_mounts": [
                        {"source": "/var/run/docker.sock", "destination": "/var/run/docker.sock"},
                        {"source": "/runner/controller", "destination": "/evidence"},
                    ],
                    "candidate_declared_result": "PASS",
                    "candidate_boundary_markers": [
                        "overwrote-manifest",
                        "changed-trace",
                        "wrote-github-output",
                        "restored-files-after-forgery",
                    ],
                    "cases": {},
                },
            )
            write_json(execution / "candidate-final-gate.json", {"status": "PASS"})
            write_json(execution / "files-sha256.json", {"files": {}})

            report = verify(
                acceptance_path=ACCEPTANCE,
                controller_dir=controller,
                execution_dir=execution,
                candidate_dir=candidate,
                output_dir=output,
            )
            final_gate = json.loads(
                (output / "authoritative-final-gate.json").read_text(encoding="utf-8")
            )

        self.assertEqual(report["authoritative_result"], "FAIL")
        self.assertEqual(final_gate["candidate_declared_result"], "PASS")
        self.assertEqual(
            final_gate["candidate_declared_result_authority"],
            "IGNORED_FOR_AUTHORITY",
        )
        errors = "\n".join(final_gate["errors"])
        self.assertIn("host Docker socket", errors)
        self.assertIn("forbidden authority boundary", errors)
        self.assertIn("terminal PASS observed and ignored", errors)


if __name__ == "__main__":
    unittest.main()
