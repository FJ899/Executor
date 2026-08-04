from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.p1_verifier.verify_candidate import verify

ROOT = Path(__file__).resolve().parents[1]
BASELINE_SHA = "f1188f9edd20f67a96494e33a109381f1a5bf331"
BASELINE_TEST_PATH = "tests/test_p1_verifier.py"


def _load_baseline_fixture_module():
    completed = subprocess.run(
        ["git", "show", f"{BASELINE_SHA}:{BASELINE_TEST_PATH}"],
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
        prefix="p1-verifier-baseline-",
        delete=False,
    )
    try:
        temporary.write(completed.stdout)
        temporary.close()
        path = Path(temporary.name)
        spec = importlib.util.spec_from_file_location(
            "p1_verifier_baseline_fixture",
            path,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load baseline verifier fixture")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        module.ROOT = ROOT
        module.WORKFLOW = ROOT / ".github/workflows/manual-exact-ref-verify.yml"
        module.VERIFIER = ROOT / "tools/p1_verifier/verify_candidate.py"
        module.ACCEPTANCE = ROOT / "tools/p1_verifier/acceptance_manifest.json"
        return module, path
    except Exception:
        Path(temporary.name).unlink(missing_ok=True)
        raise


class RawDockerApiFalseSuccessTest(unittest.TestCase):
    def test_untracked_nested_daemon_registry_request_is_rejected(self):
        """Daemon-originated registry traffic cannot be invisible to authority."""
        baseline, module_path = _load_baseline_fixture_module()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                fixture = baseline.VerifierFixture(Path(temporary))
                baseline._write_json(
                    fixture.execution / "untracked-docker-api-request.json",
                    {
                        "method": "GET",
                        "path": "/distribution/attacker.example/image/json",
                        "daemon_network_request": True,
                        "container_or_image_event": False,
                    },
                )
                baseline._hash_manifest(fixture.execution)
                report = verify(
                    acceptance_path=fixture.acceptance,
                    controller_dir=fixture.controller,
                    execution_dir=fixture.execution,
                    candidate_dir=fixture.candidate,
                    source_anchor_root=fixture.source_anchors,
                    output_dir=fixture.output,
                )
        finally:
            module_path.unlink(missing_ok=True)

        self.assertEqual(report["authoritative_result"], "FAIL", report)
        self.assertTrue(
            any(
                "raw Docker Engine API" in error
                or "Docker command broker" in error
                for error in report["errors"]
            ),
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
