from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_json(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def hash_file(path: str | Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def hash_tree(path: str | Path) -> str:
    root = Path(path)
    if not root.exists():
        return sha256_bytes(b"<missing>")
    if root.is_file():
        return hash_file(root)
    entries: list[dict[str, str]] = []
    for child in sorted(p for p in root.rglob("*") if p.is_file()):
        entries.append({"path": child.relative_to(root).as_posix(), "sha256": hash_file(child)})
    return hash_json(entries)
