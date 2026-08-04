from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.p1_verifier.verify_candidate import verify

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/manual-exact-ref-verify.yml"
ACCEPTANCE = ROOT / "tools/p1_verifier/acceptance_manifest.json"
BASELINE_SHA = "f1188f9edd20f67a96494e33a109381f1a5bf331"
BASELINE_TEST_PATH = "tests/test_p1_verifier.py"
CANONICAL_URL = "https://github.com/litrgratis-pixel/executor-pilot-target.git"
BROKER_AUTHORITY = "TRUSTED_HOST_HARNESS"
BROKER_ENDPOINT = "UNIX_COMMAND_BROKER_ONLY"
BROKER_CLASSES = {
    "version",
    "image-inspect",
    "run-git-network",
    "run-git-offline",
    "create-sandbox",
    "ps-container",
    "inspect-container",
    "start-container",
    "kill-container",
    "wait-container",
    "remove-container",
}


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode())


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(value))


def _contains_raw_daemon_claim(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("daemon_network_request") is True:
            return True
        if value.get("raw_docker_api") is True:
            return True
        return any(_contains_raw_daemon_claim(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_raw_daemon_claim(item) for item in value)
    return False


def verify_broker_evidence(execution_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    ledger_path = execution_dir / "docker-command-ledger.json"
    network_path = execution_dir / "network-observation.json"
    observation_path = execution_dir / "observation-manifest.json"

    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except Exception as exc:
        ledger = {}
        errors.append(f"trusted Docker command broker ledger missing or invalid: {exc}")
    try:
        network = json.loads(network_path.read_text(encoding="utf-8"))
    except Exception as exc:
        network = {}
        errors.append(f"trusted broker network observation missing or invalid: {exc}")
    try:
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
    except Exception as exc:
        observation = {}
        errors.append(f"execution observation missing or invalid for broker verification: {exc}")

    if ledger.get("schema_version") != 1:
        errors.append("trusted Docker command broker ledger schema mismatch")
    if ledger.get("broker_authority") != BROKER_AUTHORITY:
        errors.append("trusted Docker command broker authority mismatch")
    if ledger.get("ready_before_candidate") is not True:
        errors.append("trusted Docker command broker was not ready before candidate execution")
    if ledger.get("complete") is not True:
        errors.append("trusted Docker command broker ledger is incomplete")
    if ledger.get("overflow") is not False:
        errors.append("trusted Docker command broker ledger overflowed")
    if ledger.get("broker_error") not in (None, ""):
        errors.append("trusted Docker command broker reported an error")
    if ledger.get("candidate_endpoint") != BROKER_ENDPOINT:
        errors.append("candidate Docker endpoint is not the trusted Unix command broker")
    if ledger.get("direct_daemon_endpoint_exposed") is not False:
        errors.append("raw Docker Engine endpoint was exposed to candidate")

    events = ledger.get("events")
    if not isinstance(events, list) or not events:
        errors.append("trusted Docker command broker ledger has no events")
        events = []
    if len(events) > 8192:
        errors.append("trusted Docker command broker ledger exceeds event limit")

    requests: dict[str, dict[str, Any]] = {}
    responses: dict[str, dict[str, Any]] = {}
    for expected_sequence, event in enumerate(events, 1):
        if not isinstance(event, dict):
            errors.append("trusted Docker command broker ledger contains a non-object event")
            continue
        if event.get("sequence") != expected_sequence:
            errors.append("trusted Docker command broker sequence is not contiguous")
        phase = event.get("phase")
        request_id = event.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            errors.append("trusted Docker command broker event lacks request identity")
            continue
        if phase == "request":
            if request_id in requests:
                errors.append("trusted Docker command broker request identity is duplicated")
            requests[request_id] = event
            argv = event.get("argv")
            if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
                errors.append("trusted Docker command broker request argv is invalid")
                continue
            if event.get("argv_sha256") != _sha256_bytes(_canonical_bytes(argv)):
                errors.append("trusted Docker command broker request argv hash mismatch")
            if event.get("decision") != "ALLOW":
                errors.append("trusted Docker command broker recorded a denied or unknown request")
            if event.get("command_class") not in BROKER_CLASSES:
                errors.append("trusted Docker command broker recorded an unknown command class")
            if any(item in {"-H", "--host"} or item.startswith("--host=") for item in argv):
                errors.append("candidate attempted to select a raw Docker Engine endpoint")
            urls = [item for item in argv if "://" in item]
            if any(item != CANONICAL_URL for item in urls):
                errors.append("trusted Docker command broker request contains an unapproved URL")
        elif phase == "response":
            if request_id in responses:
                errors.append("trusted Docker command broker response identity is duplicated")
            responses[request_id] = event
            if not isinstance(event.get("returncode"), int):
                errors.append("trusted Docker command broker response return code is invalid")
            for field in ("stdout_sha256", "stderr_sha256"):
                value = event.get(field)
                if not isinstance(value, str) or len(value) != 64:
                    errors.append(f"trusted Docker command broker response {field} is invalid")
        else:
            errors.append("trusted Docker command broker event phase is invalid")

    if set(requests) != set(responses):
        errors.append("trusted Docker command broker request/response sequence is incomplete")
    for request_id, request in requests.items():
        response = responses.get(request_id)
        if response is not None and response.get("request_argv_sha256") != request.get("argv_sha256"):
            errors.append("trusted Docker command broker response is not bound to its request")

    if network.get("candidate_network") not in {"internal-only", "none"}:
        errors.append("candidate network classification is invalid")
    if network.get("candidate_network_mode") != "none":
        errors.append("candidate container retained a network path to the nested Docker daemon")
    if network.get("candidate_docker_endpoint") != "TRUSTED_UNIX_COMMAND_BROKER":
        errors.append("candidate Docker endpoint was not the trusted Unix command broker")
    if network.get("candidate_direct_daemon_access") is not False:
        errors.append("candidate retained direct raw Docker Engine access")
    if network.get("broker_socket_mounted") is not True:
        errors.append("trusted broker socket mount was not observed")
    if network.get("nested_daemon_egress") is not True:
        errors.append("nested daemon egress required for controlled acquisition was not established")
    if observation.get("candidate_direct_daemon_access") is not False:
        errors.append("execution observation does not reject direct daemon access")
    if observation.get("docker_command_broker_authority") != BROKER_AUTHORITY:
        errors.append("execution observation lacks trusted Docker command broker authority")

    ignored = {
        "docker-command-ledger.json",
        "network-observation.json",
        "observation-manifest.json",
        "files-sha256.json",
    }
    for path in execution_dir.rglob("*.json"):
        relative = path.relative_to(execution_dir).as_posix()
        if relative in ignored or relative.startswith("results/"):
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if _contains_raw_daemon_claim(value):
            errors.append("raw Docker Engine API activity exists outside trusted broker ledger")

    return {
        "verified": not errors,
        "events": len(events),
        "requests": len(requests),
        "responses": len(responses),
        "errors": sorted(set(errors)),
    }


def apply_broker_gate(
    *, execution_dir: Path, gate_path: Path, output_path: Path
) -> dict[str, Any]:
    summary = verify_broker_evidence(execution_dir)
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
    except Exception as exc:
        gate = {
            "schema_version": 2,
            "authoritative_result": "FAIL",
            "errors": [f"authoritative gate missing before broker verification: {exc}"],
            "warnings": [],
        }
    errors = list(gate.get("errors") or [])
    errors.extend(summary["errors"])
    gate["errors"] = sorted(set(str(item) for item in errors))
    gate["docker_command_broker_summary"] = {
        key: value for key, value in summary.items() if key != "errors"
    }
    if gate["errors"]:
        gate["authoritative_result"] = "FAIL"
    _write_json(gate_path, gate)
    _write_json(output_path, summary)
    return gate


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
        mode="w", encoding="utf-8", suffix=".py", prefix="p1-verifier-baseline-", delete=False
    )
    try:
        temporary.write(completed.stdout)
        temporary.close()
        path = Path(temporary.name)
        spec = importlib.util.spec_from_file_location("p1_verifier_baseline_fixture", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load baseline verifier fixture")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        module.ROOT = ROOT
        module.WORKFLOW = WORKFLOW
        module.VERIFIER = ROOT / "tools/p1_verifier/verify_candidate.py"
        module.ACCEPTANCE = ACCEPTANCE
        return module, path
    except Exception:
        Path(temporary.name).unlink(missing_ok=True)
        raise


def _write_valid_broker(fixture: Any, baseline: Any) -> None:
    argv = ["version", "--format", "{{.Server.Version}}"]
    argv_hash = _sha256_bytes(_canonical_bytes(argv))
    ledger = {
        "schema_version": 1,
        "broker_authority": BROKER_AUTHORITY,
        "ready_before_candidate": True,
        "complete": True,
        "overflow": False,
        "broker_error": None,
        "candidate_endpoint": BROKER_ENDPOINT,
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
                "stdout_sha256": _sha256_text("27.5.1\n"),
                "stderr_sha256": _sha256_text(""),
            },
        ],
    }
    baseline._write_json(fixture.execution / "docker-command-ledger.json", ledger)
    network_path = fixture.execution / "network-observation.json"
    network = json.loads(network_path.read_text())
    network.update(
        candidate_network="internal-only",
        candidate_network_mode="none",
        candidate_docker_endpoint="TRUSTED_UNIX_COMMAND_BROKER",
        candidate_direct_daemon_access=False,
        broker_socket_mounted=True,
        nested_daemon_egress=True,
    )
    baseline._write_json(network_path, network)
    observation_path = fixture.execution / "observation-manifest.json"
    observation = json.loads(observation_path.read_text())
    observation.update(
        candidate_direct_daemon_access=False,
        docker_command_broker_authority=BROKER_AUTHORITY,
    )
    baseline._write_json(observation_path, observation)
    baseline._hash_manifest(fixture.execution)


class DockerCommandBrokerTests(unittest.TestCase):
    def _fixture(self):
        baseline, module_path = _load_baseline_fixture_module()
        temporary = tempfile.TemporaryDirectory()
        fixture = baseline.VerifierFixture(Path(temporary.name))
        return baseline, module_path, temporary, fixture

    def test_workflow_removes_direct_raw_docker_endpoint(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("TRUSTED_UNIX_COMMAND_BROKER", text)
        self.assertIn("docker-command-ledger.json", text)
        self.assertIn("--network none", text)
        self.assertIn("/broker/docker-command.sock", text)
        self.assertNotIn("--env DOCKER_HOST=tcp://p1-dind:2375", text)
        self.assertIn("trusted/tests/test_p1_verifier.py --verify-broker", text)

    def test_valid_broker_evidence_preserves_authoritative_pass(self):
        baseline, module_path, temporary, fixture = self._fixture()
        try:
            _write_valid_broker(fixture, baseline)
            report = verify(
                acceptance_path=fixture.acceptance,
                controller_dir=fixture.controller,
                execution_dir=fixture.execution,
                candidate_dir=fixture.candidate,
                source_anchor_root=fixture.source_anchors,
                output_dir=fixture.output,
            )
            self.assertEqual(report["authoritative_result"], "PASS", report)
            gate = apply_broker_gate(
                execution_dir=fixture.execution,
                gate_path=fixture.output / "authoritative-final-gate.json",
                output_path=fixture.output / "docker-command-broker-verification.json",
            )
            self.assertEqual(gate["authoritative_result"], "PASS", gate)
        finally:
            temporary.cleanup()
            module_path.unlink(missing_ok=True)

    def test_missing_broker_ledger_fails_closed(self):
        baseline, module_path, temporary, fixture = self._fixture()
        try:
            baseline._hash_manifest(fixture.execution)
            summary = verify_broker_evidence(fixture.execution)
            self.assertFalse(summary["verified"], summary)
            self.assertTrue(any("ledger missing" in error for error in summary["errors"]))
        finally:
            temporary.cleanup()
            module_path.unlink(missing_ok=True)

    def test_incomplete_broker_sequence_fails_closed(self):
        baseline, module_path, temporary, fixture = self._fixture()
        try:
            _write_valid_broker(fixture, baseline)
            path = fixture.execution / "docker-command-ledger.json"
            ledger = json.loads(path.read_text())
            ledger["events"] = ledger["events"][:1]
            baseline._write_json(path, ledger)
            baseline._hash_manifest(fixture.execution)
            summary = verify_broker_evidence(fixture.execution)
            self.assertFalse(summary["verified"], summary)
            self.assertTrue(any("incomplete" in error for error in summary["errors"]))
        finally:
            temporary.cleanup()
            module_path.unlink(missing_ok=True)

    def test_unknown_or_denied_broker_command_fails_closed(self):
        baseline, module_path, temporary, fixture = self._fixture()
        try:
            _write_valid_broker(fixture, baseline)
            path = fixture.execution / "docker-command-ledger.json"
            ledger = json.loads(path.read_text())
            ledger["events"][0]["decision"] = "DENY"
            ledger["events"][0]["command_class"] = "raw-api"
            baseline._write_json(path, ledger)
            baseline._hash_manifest(fixture.execution)
            summary = verify_broker_evidence(fixture.execution)
            self.assertFalse(summary["verified"], summary)
            self.assertTrue(any("denied or unknown" in error for error in summary["errors"]))
        finally:
            temporary.cleanup()
            module_path.unlink(missing_ok=True)

    def test_untracked_nested_daemon_registry_request_is_rejected(self):
        baseline, module_path, temporary, fixture = self._fixture()
        try:
            _write_valid_broker(fixture, baseline)
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
            self.assertEqual(report["authoritative_result"], "PASS", report)
            gate = apply_broker_gate(
                execution_dir=fixture.execution,
                gate_path=fixture.output / "authoritative-final-gate.json",
                output_path=fixture.output / "docker-command-broker-verification.json",
            )
            self.assertEqual(gate["authoritative_result"], "FAIL", gate)
            self.assertTrue(
                any("outside trusted broker ledger" in error for error in gate["errors"]),
                gate["errors"],
            )
        finally:
            temporary.cleanup()
            module_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-broker", action="store_true")
    parser.add_argument("--execution-dir", type=Path)
    parser.add_argument("--gate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not args.verify_broker:
        parser.error("--verify-broker is required")
    if args.execution_dir is None or args.gate is None or args.output is None:
        parser.error("--execution-dir, --gate and --output are required")
    gate = apply_broker_gate(
        execution_dir=args.execution_dir.resolve(),
        gate_path=args.gate.resolve(),
        output_path=args.output.resolve(),
    )
    print(json.dumps(gate, sort_keys=True, indent=2))
    return 0 if gate.get("authoritative_result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
