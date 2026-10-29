"""Widget-value sanitizers.

ComfyUI saves widget values positionally in the workflow JSON. A workflow that
predates a widget can therefore deliver a boolean where a string is expected
(seen as ``path: True``) or junk into numeric widgets. These helpers keep the
nodes from acting on such values.
"""

from __future__ import annotations

from typing import Iterable, Sequence

_JUNK_TEXT = {"true", "false", "none", "null", "undefined"}

_TRUE = {"true", "1", "yes", "on", "y"}
_FALSE = {"false", "0", "no", "off", "n"}


def to_text(value, default: str = "") -> str:
    """Return *value* when it is a string, otherwise *default*."""
    return value if isinstance(value, str) else default


def clean_text(value, default: str = "") -> str:
    """Return trimmed text, treating shifted boolean artifacts as empty."""
    text = to_text(value, default)
    text = text.strip()
    if not text or text.lower() in _JUNK_TEXT:
        return default
    return text


def coerce_int(value, default: int, minimum: int | None = None,
               maximum: int | None = None) -> int:
    """Parse an int, ignoring booleans and clamping to the given range."""
    if isinstance(value, bool):
        return _clamp(int(default), minimum, maximum)
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        number = int(default)
    return _clamp(number, minimum, maximum)


def coerce_float(value, default: float, minimum: float | None = None,
                 maximum: float | None = None) -> float:
    """Parse a float, ignoring booleans and clamping to the given range."""
    if isinstance(value, bool):
        return _clamp(float(default), minimum, maximum)
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)
    return _clamp(number, minimum, maximum)


def coerce_bool(value, default: bool = True) -> bool:
    """Parse a bool from ComfyUI's boolean or legacy string widgets."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
    return bool(default)


def coerce_choice(value, choices: Iterable[str], default: str) -> str:
    """Return a canonical choice, matching case-insensitively."""
    options = tuple(choices)
    text = to_text(value).strip()
    if text in options:
        return text
    lowered = text.lower()
    for option in options:
        if option.lower() == lowered:
            return option
    return default


def coerce_encoding(value, choices: Sequence[str], default: str) -> str:
    """Return a usable text encoding name."""
    text = coerce_choice(value, choices, default)
    try:
        "".encode(text)
    except LookupError:
        return default
    return text


def _clamp(number: float, minimum, maximum):
    if minimum is not None and number < minimum:
        number = minimum
    if maximum is not None and number > maximum:
        number = maximum
    return number


__all__ = [
    "clean_text",
    "coerce_bool",
    "coerce_choice",
    "coerce_encoding",
    "coerce_float",
    "coerce_int",
    "to_text",
]
