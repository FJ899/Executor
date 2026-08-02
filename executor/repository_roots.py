from __future__ import annotations


def parse_repository_roots(values: list[str]) -> dict[str, str]:
    roots: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--repository-root must use NAME=PATH")
        name, path = value.split("=", 1)
        name, path = name.strip(), path.strip()
        if not name or not path:
            raise ValueError("--repository-root requires non-empty NAME and PATH")
        if name in roots and roots[name] != path:
            raise ValueError(f"Conflicting repository roots for {name}")
        roots[name] = path
    return roots
