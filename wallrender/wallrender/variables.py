"""{{path}} substitution. Values are data, never code: no filters, no eval,
no attribute access. Only scalars print; a missing, empty or non-scalar value
(a dict or list, which could leak a whole Jamf subtree) becomes an empty
string. Each value and the final text are length-capped."""

from __future__ import annotations

from typing import Any

from .schema import MAX_TEXT, PLACEHOLDER

MAX_VALUE_CHARS = 200


def lookup(values: dict[str, Any], path: str) -> Any:
    current: Any = values
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def scalar_text(value: Any) -> str:
    """The printable form of a value, or '' for anything that is not a scalar."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        try:
            return str(value)[:MAX_VALUE_CHARS]
        except ValueError:  # e.g. an int too large to convert
            return ""
    return ""


def substitute(text: str, values: dict[str, Any], missing: list[str] | None = None) -> str:
    def replace(match):
        path = match.group(1).strip()
        printed = scalar_text(lookup(values, path))
        if not printed and missing is not None:
            missing.append(path)
        return printed

    return PLACEHOLDER.sub(replace, text)[:MAX_TEXT]
