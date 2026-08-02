# M1 repository trust boundary

Repository paths are security inputs, not display strings.

The Executor now requires:

- normalized relative POSIX paths;
- no absolute, drive-qualified, backslash, empty, dot, parent or unstable Unicode segments;
- valid relative scope globs;
- repository containment for existing and prospective files;
- no symlink component in the repository root, parent chain or final file;
- no hard-linked input file;
- regular UTF-8 files opened with `O_NOFOLLOW` where supported;
- repository `origin`, expected commit and current `HEAD` to match before content is read;
- every production repository read to pass through `read_wrapped_repository_file`, which assigns `trusted_project_instruction`, `trusted_project_data` or `untrusted_data` and always records the higher-level policy/contract layers that content cannot override.

A path that is syntactically or physically unsafe produces deterministic `HARD_VETO / forbidden_path_modified`.

The project command policy explicitly allows `python -m executor.cli`, so the Executor no longer blocks its own validated commands while continuing to reject arbitrary Python entrypoints.
