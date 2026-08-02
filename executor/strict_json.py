from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class StrictJsonError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJsonError(f"Duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise StrictJsonError(f"Non-standard JSON constant: {value}")


def loads_json_object(text: str) -> dict[str, Any]:
    try:
        result = json.loads(text, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise StrictJsonError(f"Invalid JSON: {exc.msg} at line {exc.lineno}") from exc
    if not isinstance(result, dict):
        raise StrictJsonError("JSON document must contain an object")
    return result


def load_json_object(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise StrictJsonError(f"Cannot read {source}: {exc}") from exc
    return loads_json_object(text)
