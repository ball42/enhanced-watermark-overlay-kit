"""{{path}} substitution. Values are data, never code: no filters, no eval,
no attribute access. A missing or empty value becomes an empty string."""

from __future__ import annotations

from typing import Any

from .schema import PLACEHOLDER


def lookup(values: dict[str, Any], path: str) -> Any:
    current: Any = values
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def substitute(text: str, values: dict[str, Any], missing: list[str] | None = None) -> str:
    def replace(match):
        path = match.group(1).strip()
        value = lookup(values, path)
        if value is None or value == "":
            if missing is not None:
                missing.append(path)
            return ""
        return str(value)

    return PLACEHOLDER.sub(replace, text)
