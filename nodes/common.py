"""Shared logging, progress and file-writing helpers for the nodes."""

from __future__ import annotations

from pathlib import Path

from .. import config

try:  # only available inside ComfyUI
    from comfy.utils import ProgressBar  # type: ignore
except Exception:  # pragma: no cover - depends on the environment
    ProgressBar = None


def log(message: str) -> None:
    print(f"{config.LOG_PREFIX} {message}", flush=True)


def make_progress(total: int):
    """Return a ComfyUI progress bar, or None outside ComfyUI."""
    if ProgressBar is None or total <= 0:
        return None
    try:
        return ProgressBar(int(total))
    except Exception:  # pragma: no cover - defensive
        return None


def write_text(path, text: str, encoding: str) -> Path:
    """Write text with a clear error when the encoding cannot represent it."""
    path = Path(path)
    try:
        path.write_text(text, encoding=encoding)
    except UnicodeEncodeError as exc:
        raise RuntimeError(
            f"Cannot save the transcript as {encoding}: the text contains "
            "characters that this encoding does not support. Choose utf-8 or "
            "utf-8-sig instead."
        ) from exc
    return path


__all__ = ["log", "make_progress", "write_text"]
