import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from executor.pilot_case_001 import case_001_sandbox_spec, execute_case_001
from tests.test_pilot_case_001 import FakeSandboxBackend, PilotRepository


class PilotGitIsolationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixture = PilotRepository(self.root)
        self.spec = case_001_sandbox_spec("sha256:" + "1" * 64)

    def tearDown(self):
        self.temp.cleanup()

    def execute(self):
        return execute_case_001(
            repository_root=self.fixture.source,
            runs_root=self.fixture.runs,
            sandbox_backend=FakeSandboxBackend(),
            sandbox_spec=self.spec,
            contract=self.fixture.contract,
        )

    def _marker_program(self, name: str, *, passthrough: bool = True) -> tuple[Path, Path]:
        marker = self.root / f"{name}-executed"
        program = self.root / f"{name}.sh"
        lines = ["#!/bin/sh", f"printf executed > {marker}"]
        lines.append("cat" if passthrough else "exit 1")
        program.write_text("\n".join(lines) + "\n", encoding="utf-8")
        program.chmod(0o755)
        return marker, program

    def _set_filter_attributes(self, name: str) -> None:
        info_attributes = self.fixture.source / ".git/info/attributes"
        info_attributes.write_text(
            f"project_registry/registry.py filter={name}\n",
            encoding="utf-8",
        )

    def _included_filter_config(self, name: str, program: Path) -> Path:
        config = self.root / f"{name}.config"
        config.write_text(
            f'[filter "{name}"]\n'
            f"\tsmudge = {program}\n"
            "\tclean = cat\n",
            encoding="utf-8",
        )
        return config

    def test_executable_post_checkout_hook_cannot_run_on_host(self):
        marker = self.root / "host-hook-executed"
        hook = self.fixture.source / ".git/hooks/post-checkout"
        hook.write_text(
            "#!/bin/sh\nprintf executed > " + str(marker) + "\n",
            encoding="utf-8",
        )
        hook.chmod(0o755)

        report = self.execute()

        self.assertEqual(report["status"], "ACTION_COMPLETED_REVIEW_REQUIRED")
        self.assertFalse(marker.exists(), "Git post-checkout hook executed outside sandbox")

    def test_local_smudge_filter_cannot_run_on_host(self):
        marker, program = self._marker_program("smudge")
        self._set_filter_attributes("host-smudge")
        self.fixture._git("config", "filter.host-smudge.smudge", str(program))
        self.fixture._git("config", "filter.host-smudge.clean", "cat")

        self.execute()

        self.assertFalse(marker.exists(), "Git smudge filter executed outside sandbox")

    def test_local_clean_filter_cannot_run_on_host(self):
        marker, program = self._marker_program("clean")
        self._set_filter_attributes("host-clean")
        self.fixture._git("config", "filter.host-clean.smudge", "cat")
        self.fixture._git("config", "filter.host-clean.clean", str(program))

        self.execute()

        self.assertFalse(marker.exists(), "Git clean filter executed outside sandbox")

    def test_local_process_filter_cannot_start_on_host(self):
        marker, program = self._marker_program("process", passthrough=False)
        self._set_filter_attributes("host-process")
        self.fixture._git("config", "filter.host-process.process", str(program))

        self.execute()

        self.assertFalse(marker.exists(), "Git process filter started outside sandbox")

    def test_include_path_cannot_load_executable_filter_configuration(self):
        marker, program = self._marker_program("include-path")
        self._set_filter_attributes("included-filter")
        included = self._included_filter_config("included-filter", program)
        self.fixture._git("config", "include.path", str(included))

        self.execute()

        self.assertFalse(marker.exists(), "Git include.path loaded executable filter configuration")

    def test_include_if_cannot_load_executable_filter_configuration(self):
        marker, program = self._marker_program("include-if")
        self._set_filter_attributes("conditional-filter")
        included = self._included_filter_config("conditional-filter", program)
        git_dir_pattern = (self.fixture.source / ".git").resolve().as_posix() + "/**"
        config = self.fixture.source / ".git/config"
        with config.open("a", encoding="utf-8") as handle:
            handle.write(
                f'\n[includeIf "gitdir:{git_dir_pattern}"]\n'
                f"\tpath = {included}\n"
            )

        self.execute()

        self.assertFalse(marker.exists(), "Git includeIf loaded executable filter configuration")

    def test_executor_never_runs_git_against_input_checkout_or_git_dir(self):
        original_run = subprocess.run
        observed: list[tuple[tuple[str, ...], str | None, dict[str, str]]] = []

        def traced_run(*args, **kwargs):
            raw_command = args[0] if args else kwargs.get("args", ())
            command = tuple(os.fspath(item) for item in raw_command)
            executable = Path(command[0]).name if command else ""
            if executable == "git":
                cwd = kwargs.get("cwd")
                environment = dict(kwargs.get("env") or {})
                observed.append(
                    (
                        command,
                        os.fspath(cwd) if cwd is not None else None,
                        environment,
                    )
                )
            return original_run(*args, **kwargs)

        with patch("subprocess.run", side_effect=traced_run):
            self.execute()

        source = self.fixture.source.resolve()
        git_dir = (source / ".git").resolve()
        violations = []
        for command, cwd, environment in observed:
            argument_paths = {item for item in command[1:] if item}
            if str(source) in argument_paths or str(git_dir) in argument_paths:
                violations.append((command, cwd, "argument"))
            if cwd is not None:
                resolved_cwd = Path(cwd).resolve()
                if resolved_cwd == source or source in resolved_cwd.parents:
                    violations.append((command, cwd, "cwd"))
            for key in ("GIT_DIR", "GIT_WORK_TREE"):
                value = environment.get(key)
                if value and Path(value).resolve() in {source, git_dir}:
                    violations.append((command, cwd, key))

        self.assertEqual(
            violations,
            [],
            "Executor invoked Git against the untrusted input checkout: "
            + repr(violations),
        )

    def test_rejected_runs_root_does_not_dirty_source(self):
        runs_root = self.fixture.source / "runs"

        report = execute_case_001(
            repository_root=self.fixture.source,
            runs_root=runs_root,
            sandbox_backend=FakeSandboxBackend(),
            sandbox_spec=self.spec,
            contract=self.fixture.contract,
        )

        self.assertEqual(report["status"], "POLICY_BLOCKED")
        self.assertFalse(runs_root.exists())
        self.assertEqual(
            self.fixture._git("status", "--porcelain").stdout,
            "",
        )


if __name__ == "__main__":
    unittest.main()
