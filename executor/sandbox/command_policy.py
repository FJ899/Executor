from __future__ import annotations

from executor.sandbox.spec import CommandRule


class CommandDenied(RuntimeError):
    pass


def validate_argv(argv: list[str], rules: tuple[CommandRule, ...]) -> None:
    if not argv or not all(isinstance(item, str) and item for item in argv):
        raise CommandDenied("Command must be a non-empty argv list")
    if any(rule.matches(argv) for rule in rules):
        return
    allowed = [{"executable": rule.executable, "argv_prefix": list(rule.argv_prefix)} for rule in rules]
    raise CommandDenied(f"Command is outside allowlist: {argv!r}; allowed={allowed!r}")
