from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWED_BASELINE_SHA = "62a25e2c1f38f7986f484e78e50cc7e322ebf808"
BASELINE_PATH = "tests/test_p1_verifier.py"


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _load_reviewed_baseline():
    completed = subprocess.run(
        ["git", "show", f"{REVIEWED_BASELINE_SHA}:{BASELINE_PATH}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    temporary = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".py",
        prefix="p1-reviewed-baseline-",
        delete=False,
    )
    temporary.write(completed.stdout)
    temporary.close()
    path = Path(temporary.name)
    spec = importlib.util.spec_from_file_location("p1_reviewed_baseline", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load reviewed PR32 baseline")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.ROOT = ROOT
    module.WORKFLOW = ROOT / ".github/workflows/manual-exact-ref-verify.yml"
    module.ACCEPTANCE = ROOT / "tools/p1_verifier/acceptance_manifest.json"
    return module, path


BASELINE, _BASELINE_MODULE_PATH = _load_reviewed_baseline()


class AdversarialBrokerRegressionRedTests(unittest.TestCase):
    def _network_git_argv(self) -> list[str]:
        return BASELINE.DockerCommandBrokerTests()._network_git_argv()

    def test_classifier_rejects_root_writable_and_extra_runtime_authority(self):
        attacks = {
            "root-user": ["--user", "0:0"],
            "writable-root": ["--read-only=false"],
            "shadow-executor-run": ["--tmpfs", "/executor-run:rw"],
            "unapproved-runtime": ["--runtime", "runc"],
        }
        for label, extra in attacks.items():
            with self.subTest(label=label):
                argv = self._network_git_argv()
                image_index = argv.index("git-image")
                argv[image_index:image_index] = extra
                allowed, _, reason = BASELINE.classify_broker_argv(
                    argv,
                    git_image="git-image",
                    sandbox_image_id="sandbox-image-id",
                    canonical_url=BASELINE.CANONICAL_URL,
                    created=set(),
                )
                self.assertFalse(
                    allowed,
                    f"authority downgrade was accepted: {label}: {reason}",
                )

    def test_version_only_broker_ledger_cannot_preserve_authoritative_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            execution = Path(temporary)
            argv = ["version", "--format", "{{.Server.Version}}"]
            argv_hash = BASELINE._sha256_bytes(BASELINE._canonical_bytes(argv))
            _write_json(
                execution / "docker-command-ledger.json",
                {
                    "schema_version": 1,
                    "broker_authority": BASELINE.BROKER_AUTHORITY,
                    "ready_before_candidate": True,
                    "complete": True,
                    "overflow": False,
                    "broker_error": None,
                    "candidate_endpoint": BASELINE.BROKER_ENDPOINT,
                    "direct_daemon_endpoint_exposed": False,
                    "events": [
                        {
                            "sequence": 1,
                            "phase": "request",
                            "request_id": "request-000001",
                            "argv": argv,
                            "argv_sha256": argv_hash,
                            "decision": "ALLOW",
                            "command_class": "version",
                        },
                        {
                            "sequence": 2,
                            "phase": "response",
                            "request_id": "request-000001",
                            "request_argv_sha256": argv_hash,
                            "returncode": 0,
                            "stdout_sha256": BASELINE._sha256_text("27.5.1\n"),
                            "stderr_sha256": BASELINE._sha256_text(""),
                        },
                    ],
                },
            )
            _write_json(
                execution / "network-observation.json",
                {
                    "candidate_network": "internal-only",
                    "candidate_network_mode": "none",
                    "candidate_docker_endpoint": "TRUSTED_UNIX_COMMAND_BROKER",
                    "candidate_direct_daemon_access": False,
                    "broker_socket_mounted": True,
                    "nested_daemon_egress": True,
                },
            )
            _write_json(
                execution / "observation-manifest.json",
                {
                    "candidate_direct_daemon_access": False,
                    "docker_command_broker_authority": BASELINE.BROKER_AUTHORITY,
                },
            )
            _write_json(
                execution / "approved-nested-images.json",
                {
                    "images": {
                        BASELINE.GIT_IMAGE_REF: {"id": "sha256:" + "1" * 64},
                        BASELINE.SANDBOX_IMAGE_REF: {"id": "sha256:" + "2" * 64},
                    }
                },
            )
            gate_path = execution / "authoritative-final-gate.json"
            _write_json(
                gate_path,
                {
                    "schema_version": 2,
                    "authoritative_result": "PASS",
                    "errors": [],
                    "warnings": [],
                },
            )
            gate = BASELINE.apply_broker_gate(
                execution_dir=execution,
                gate_path=gate_path,
                output_path=execution / "docker-command-broker-verification.json",
            )
            self.assertEqual(
                gate["authoritative_result"],
                "FAIL",
                "version-only broker ledger cannot prove execution transcript",
            )
            self.assertTrue(
                any(
                    "execution transcript" in error.lower()
                    for error in gate["errors"]
                ),
                gate["errors"],
            )

    def test_network_fetch_cannot_trust_candidate_writable_git_configuration(self):
        argv = self._network_git_argv()
        allowed, _, _ = BASELINE.classify_broker_argv(
            argv,
            git_image="git-image",
            sandbox_image_id="sandbox-image-id",
            canonical_url=BASELINE.CANONICAL_URL,
            created=set(),
        )
        self.assertFalse(
            allowed,
            "candidate-writable repository.git/config can rewrite the effective HTTPS endpoint",
        )


if __name__ == "__main__":
    unittest.main()
