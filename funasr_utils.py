"""Lazy FunASR import and device resolution.

FunASR is imported only when a node actually runs, so ComfyUI can load this
package (and show the nodes) before the optional ASR dependencies are installed.
"""

from __future__ import annotations

import sys

from . import config


def require_funasr():
    """Import funasr or raise an actionable installation error."""
    try:
        import funasr  # type: ignore

        return funasr
    except Exception as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError(
            "FunASR is not available in this Python environment. Install it in "
            "the SAME environment that launches ComfyUI:\n"
            f'  "{sys.executable}" -m pip install -U "funasr>=1.3.0"\n'
            f"Python: {sys.executable}\n"
            f"Reason: {exc}"
        ) from exc


def resolve_device(device) -> str:
    """Resolve ``auto``/``cuda``/``cpu`` to a FunASR device string."""
    text = (device or "").strip().lower() if isinstance(device, str) else ""
    if text in {"", "auto"}:
        return "cuda:0" if _cuda_available() else "cpu"
    if text == "cuda":
        if not _cuda_available():
            raise RuntimeError(
                "device is set to 'cuda', but this Python environment has no "
                "usable CUDA device. Select 'cpu' or install a CUDA build of "
                "PyTorch in ComfyUI's environment."
            )
        return "cuda:0"
    return "cpu"


def _cuda_available() -> bool:
    try:
        import torch  # type: ignore

        return bool(torch.cuda.is_available())
    except Exception:
        return False


__all__ = ["require_funasr", "resolve_device"]
