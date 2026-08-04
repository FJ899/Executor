#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path.cwd()
TESTS = ROOT / "tests/test_p1_verifier.py"
VERIFIER = ROOT / "tools/p1_verifier/verify_candidate.py"
MANIFEST = ROOT / "tools/p1_verifier/acceptance_manifest.json"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


TEST_CLASS = r'''

class AdversarialReplayRegressionTests(unittest.TestCase):
    def _sandbox_argv(self, case_id: str = "001") -> list[str]:
        image = "sha256:" + "2" * 64
        return [
            "create", "--name", f"cos-executor-{case_id}",
            "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "16", "--memory", "64m", "--cpus", "1.0",
            "--user", "65534:65534", "--env", "HOME=/nonexistent",
            "--workdir", "/source", "--mount",
            f"type=bind,src=/candidate/case-{case_id}/tests/fixtures/sandbox,dst=/source,readonly",
            "--tmpfs", "/workspace:rw,nosuid,nodev,size=8m,mode=1777",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
            image, "python", "/source/sandbox_fixture.py", "read_source",
        ]

    def _network_argv(self, case_id: str) -> list[str]:
        commit = {"001": "1", "002": "2", "003": "3"}[case_id] * 40
        argv = AdversarialBrokerRegressionTests()._network_git_argv()
        argv = [
            item.replace("/runs/case-001/", f"/runs/case-{case_id}/")
            for item in argv
        ]
        argv[argv.index("git-image")] = GIT_IMAGE_REF
        argv[-1] = f"+{commit}:refs/executor/input"
        return argv

    def test_rejects_unapproved_supplementary_root_group(self):
        argv = self._sandbox_argv()
        image_index = argv.index("sha256:" + "2" * 64)
        argv[image_index:image_index] = ["--group-add", "0"]
        allowed, _, reason = classify_broker_argv(
            argv,
            git_image="git-image",
            sandbox_image_id="sha256:" + "2" * 64,
            canonical_url=CANONICAL_URL,
            created=set(),
        )
        self.assertFalse(allowed, f"supplementary root group accepted: {reason}")

    def test_failed_required_case_operations_force_authoritative_fail(self):
        events: list[dict[str, Any]] = []
        sequence = 0

        def pair(request_id: str, argv: list[str], command_class: str, case_id: str) -> None:
            nonlocal sequence
            argv_hash = _sha256_bytes(_canonical_bytes(argv))
            sequence += 1
            events.append({
                "sequence": sequence,
                "phase": "request",
                "request_id": request_id,
                "argv": argv,
                "argv_sha256": argv_hash,
                "decision": "ALLOW",
                "command_class": command_class,
                "reason": "",
                "case_id": case_id,
            })
            sequence += 1
            events.append({
                "sequence": sequence,
                "phase": "response",
                "request_id": request_id,
                "request_argv_sha256": argv_hash,
                "returncode": 125,
                "stdout_sha256": _sha256_text(""),
                "stderr_sha256": _sha256_text("failed"),
                "duration_seconds": 0.01,
                "inspection": None,
                "inspection_sha256": None,
            })

        for case_id in ("001", "002", "003"):
            pair(
                f"acquisition-{case_id}",
                self._network_argv(case_id),
                "broker-owned-acquisition",
                case_id,
            )
            pair(
                f"sandbox-{case_id}",
                self._sandbox_argv(case_id),
                "create-sandbox",
                case_id,
            )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_json(root / "docker-command-ledger.json", {
                "schema_version": 1,
                "broker_authority": BROKER_AUTHORITY,
                "ready_before_candidate": True,
                "complete": True,
                "overflow": False,
                "broker_error": None,
                "candidate_endpoint": BROKER_ENDPOINT,
                "direct_daemon_endpoint_exposed": False,
                "events": events,
            })
            _write_json(root / "approved-nested-images.json", {
                "images": {SANDBOX_IMAGE_REF: {"id": "sha256:" + "2" * 64}},
            })
            gate_path = root / "authoritative-final-gate.json"
            _write_json(gate_path, {
                "schema_version": 2,
                "authoritative_result": "PASS",
                "errors": [],
                "warnings": [],
            })
            gate = apply_broker_gate(
                execution_dir=root,
                gate_path=gate_path,
                output_path=root / "broker-verification.json",
            )
            self.assertEqual(gate["authoritative_result"], "FAIL", gate)
            self.assertTrue(
                any("returncode" in error.lower() for error in gate["errors"]),
                gate["errors"],
            )

    def test_verifier_accepts_only_exact_broker_owned_volume_contract(self):
        spec = importlib.util.spec_from_file_location(
            "p1_authoritative_verifier",
            ROOT / "tools/p1_verifier/verify_candidate.py",
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        pattern = r"^p1-acq-[0-9a-f]{24}$"
        valid = {
            "Type": "volume",
            "Name": "p1-acq-" + "a" * 24,
            "Source": "/rootless/docker/volumes/internal/_data",
            "Destination": "/trusted",
            "RW": True,
        }
        self.assertTrue(module._trusted_nested_mount_allowed(
            valid,
            allowed_bind_sources=["/candidate", "/runs"],
            trusted_volume_pattern=pattern,
            image_ref=GIT_IMAGE_REF,
            acquisition_image=GIT_IMAGE_REF,
        ))
        wrong_name = dict(valid, Name="candidate-volume")
        self.assertFalse(module._trusted_nested_mount_allowed(
            wrong_name,
            allowed_bind_sources=["/candidate", "/runs"],
            trusted_volume_pattern=pattern,
            image_ref=GIT_IMAGE_REF,
            acquisition_image=GIT_IMAGE_REF,
        ))
        wrong_image = dict(valid)
        self.assertFalse(module._trusted_nested_mount_allowed(
            wrong_image,
            allowed_bind_sources=["/candidate", "/runs"],
            trusted_volume_pattern=pattern,
            image_ref=SANDBOX_IMAGE_REF,
            acquisition_image=GIT_IMAGE_REF,
        ))
'''


def add_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import hashlib\n",
        "import hashlib\nimport importlib.util\n",
        "test import",
    )
    text = replace_once(
        text,
        "\ndef main(argv: list[str] | None = None) -> int:\n",
        TEST_CLASS + "\n\ndef main(argv: list[str] | None = None) -> int:\n",
        "test class insertion",
    )
    TESTS.write_text(text, encoding="utf-8")


def fix_tests_and_broker() -> None:
    text = TESTS.read_text(encoding="utf-8")
    exact_grammar = r'''

def _exact_option_grammar(
    argv: list[str], *, flags: set[str], value_options: set[str]
) -> tuple[bool, str]:
    if not argv:
        return False, "empty Docker command"
    index = 1
    while index < len(argv):
        token = argv[index]
        if token in flags:
            index += 1
            continue
        if token in value_options:
            if index + 1 >= len(argv):
                return False, f"missing value for {token}"
            index += 2
            continue
        if any(token.startswith(name + "=") for name in value_options):
            index += 1
            continue
        return False, f"unapproved Docker option or positional token before image: {token}"
    return True, ""
'''
    text = replace_once(
        text,
        "\ndef _case_id_from_argv(argv: list[str]) -> str | None:\n",
        exact_grammar + "\n\ndef _case_id_from_argv(argv: list[str]) -> str | None:\n",
        "exact grammar insertion",
    )
    old = '''def _strict_runtime_controls(argv: list[str], *, command: str) -> tuple[bool, str]:
    if command not in {"run-git", "create-sandbox"}:
        return True, ""
    if not _has_exact_flag(argv, "--read-only"):
'''
    new = '''def _strict_runtime_controls(argv: list[str], *, command: str) -> tuple[bool, str]:
    if command not in {"run-git", "create-sandbox"}:
        return True, ""
    if command == "run-git":
        grammar_ok, grammar_reason = _exact_option_grammar(
            argv,
            flags={"--rm", "--read-only"},
            value_options={
                "--platform", "--network", "--cap-drop", "--security-opt",
                "--pids-limit", "--memory", "--cpus", "--user", "--tmpfs",
                "--workdir", "--mount", "--entrypoint",
            },
        )
    else:
        grammar_ok, grammar_reason = _exact_option_grammar(
            argv,
            flags={"--read-only"},
            value_options={
                "--name", "--network", "--cap-drop", "--security-opt",
                "--pids-limit", "--memory", "--cpus", "--user", "--env",
                "--workdir", "--mount", "--tmpfs",
            },
        )
    if not grammar_ok:
        return False, grammar_reason
    if not _has_exact_flag(argv, "--read-only"):
'''
    text = replace_once(text, old, new, "strict grammar hook")
    text = replace_once(
        text,
        '        "runtime": host.get("Runtime") or "",\n',
        '        "runtime": host.get("Runtime") or "",\n        "group_add": host.get("GroupAdd") or [],\n',
        "inspect group summary",
    )
    text = replace_once(
        text,
        '    if inspection.get("readonly_rootfs") is not True:\n        errors.append(f"{label} root filesystem is writable")\n',
        '    if inspection.get("readonly_rootfs") is not True:\n        errors.append(f"{label} root filesystem is writable")\n    if inspection.get("group_add") not in (None, []):\n        errors.append(f"{label} has unapproved supplementary groups")\n',
        "inspect supplementary groups",
    )
    text = replace_once(
        text,
        '''                case_id = event.get("case_id") or _case_id_from_argv(argv)
                if case_id in CASE_IDS:
                    acquisition_cases.add(case_id)
''',
        "",
        "request acquisition counting",
    )
    text = replace_once(
        text,
        '''                if command_class == "create-sandbox":
                    case_id = event.get("case_id") or _case_id_from_argv(argv)
                    if case_id in CASE_IDS:
                        sandbox_cases.add(case_id)
''',
        "",
        "request sandbox counting",
    )
    old_response = '''                if event.get("returncode") == 0:
                    command_class = request.get("command_class")
                    if command_class == "create-sandbox":
                        _verify_inspection(
                            event.get("inspection"),
                            expected_user="65534:65534",
                            errors=errors,
                            label="sandbox",
                        )
                        names = _option(request.get("argv") or [], "--name")
                        if len(names) == 1:
                            created.add(names[0])
                    elif command_class == "broker-owned-acquisition":
                        _verify_inspection(
                            event.get("inspection"),
                            expected_user="1000:1000",
                            errors=errors,
                            label="network acquisition",
                        )
                    elif command_class == "remove-container":
                        argv = request.get("argv") or []
                        if argv:
                            created.discard(argv[-1])
'''
    new_response = '''                command_class = request.get("command_class")
                returncode = event.get("returncode")
                if not isinstance(returncode, int):
                    errors.append("broker response returncode is missing or invalid")
                elif command_class in {"create-sandbox", "broker-owned-acquisition"} and returncode != 0:
                    errors.append(
                        f"required CASE operation {command_class} returned nonzero returncode {returncode}"
                    )
                if returncode == 0:
                    case_id = request.get("case_id") or _case_id_from_argv(request.get("argv") or [])
                    if command_class == "create-sandbox":
                        _verify_inspection(
                            event.get("inspection"),
                            expected_user="65534:65534",
                            errors=errors,
                            label="sandbox",
                        )
                        if case_id in CASE_IDS:
                            sandbox_cases.add(case_id)
                        names = _option(request.get("argv") or [], "--name")
                        if len(names) == 1:
                            created.add(names[0])
                    elif command_class == "broker-owned-acquisition":
                        _verify_inspection(
                            event.get("inspection"),
                            expected_user="1000:1000",
                            errors=errors,
                            label="network acquisition",
                        )
                        if case_id in CASE_IDS:
                            acquisition_cases.add(case_id)
                    elif command_class == "remove-container":
                        argv = request.get("argv") or []
                        if argv:
                            created.discard(argv[-1])
'''
    text = replace_once(text, old_response, new_response, "response success binding")
    TESTS.write_text(text, encoding="utf-8")


def fix_verifier() -> None:
    text = VERIFIER.read_text(encoding="utf-8")
    helper = r'''

def _trusted_nested_mount_allowed(
    mount: Mapping[str, Any],
    *,
    allowed_bind_sources: Sequence[str],
    trusted_volume_pattern: str,
    image_ref: object,
    acquisition_image: object,
) -> bool:
    mount_type = mount.get("Type")
    destination = mount.get("Destination")
    if not isinstance(destination, str) or not destination.startswith("/"):
        return False
    if mount_type == "bind":
        source = mount.get("Source")
        return isinstance(source, str) and any(
            source == prefix or source.startswith(prefix.rstrip("/") + "/")
            for prefix in allowed_bind_sources
        )
    if mount_type == "volume":
        name = mount.get("Name")
        return (
            isinstance(name, str)
            and re.fullmatch(trusted_volume_pattern, name) is not None
            and destination == "/trusted"
            and image_ref == acquisition_image
        )
    return False
'''
    text = replace_once(
        text,
        "\ndef _verify_nested_operation_ledger(\n",
        helper + "\n\ndef _verify_nested_operation_ledger(\n",
        "mount helper insertion",
    )
    old_sources = '''    allowed_sources = acceptance.get("allowed_nested_mount_sources")
    if not isinstance(allowed_sources, list) or not all(isinstance(item, str) for item in allowed_sources):
        raise VerificationError("allowed_nested_mount_sources must be a string list")
'''
    new_sources = '''    allowed_sources = acceptance.get("allowed_nested_mount_sources")
    if not isinstance(allowed_sources, list) or not all(isinstance(item, str) for item in allowed_sources):
        raise VerificationError("allowed_nested_mount_sources must be a string list")
    trusted_volume_pattern = acceptance.get("trusted_broker_volume_name_pattern")
    if not isinstance(trusted_volume_pattern, str):
        raise VerificationError("trusted_broker_volume_name_pattern must be a string")
    try:
        re.compile(trusted_volume_pattern)
    except re.error as exc:
        raise VerificationError(f"trusted broker volume pattern is invalid: {exc}") from None
'''
    text = replace_once(text, old_sources, new_sources, "manifest volume contract")
    old_mount = '''            source = mount.get("Source")
            destination = mount.get("Destination")
            if not isinstance(source, str) or not any(
                source == prefix or source.startswith(prefix.rstrip("/") + "/")
                for prefix in allowed_sources
            ):
                errors.append(f"nested container {container_id} mount source is outside isolated roots: {source!r}")
            if not isinstance(destination, str) or not destination.startswith("/"):
                errors.append(f"nested container {container_id} mount destination is invalid")
'''
    new_mount = '''            if not _trusted_nested_mount_allowed(
                mount,
                allowed_bind_sources=allowed_sources,
                trusted_volume_pattern=trusted_volume_pattern,
                image_ref=image_ref,
                acquisition_image=acceptance.get("network_acquisition_image"),
            ):
                errors.append(
                    f"nested container {container_id} mount violates trusted storage contract: {mount!r}"
                )
'''
    text = replace_once(text, old_mount, new_mount, "mount verification")
    VERIFIER.write_text(text, encoding="utf-8")


def fix_manifest() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    data["trusted_broker_volume_name_pattern"] = r"^p1-acq-[0-9a-f]{24}$"
    MANIFEST.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("tests", "fix"))
    args = parser.parse_args()
    if args.mode == "tests":
        add_tests()
    else:
        fix_tests_and_broker()
        fix_verifier()
        fix_manifest()


if __name__ == "__main__":
    main()
