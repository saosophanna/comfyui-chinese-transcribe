"""Shared INPUT_TYPES builders.

ComfyUI stores widget values positionally, so every node composes its widgets
here or in its own module in a fixed order. Append new widgets at the end.
"""

from __future__ import annotations

from .. import config


def _options(**kwargs) -> dict:
    return {key: value for key, value in kwargs.items() if value is not None}


def string_input(default: str = "", *, multiline: bool = False,
                 tooltip: str | None = None) -> tuple:
    return (
        "STRING",
        _options(default=default, multiline=bool(multiline), tooltip=tooltip),
    )


def int_input(default: int, minimum: int, maximum: int, *,
              step: int = 1, tooltip: str | None = None) -> tuple:
    return (
        "INT",
        _options(
            default=int(default),
            min=int(minimum),
            max=int(maximum),
            step=int(step),
            tooltip=tooltip,
        ),
    )


def float_input(default: float, minimum: float, maximum: float, *,
                step: float = 0.1, tooltip: str | None = None) -> tuple:
    return (
        "FLOAT",
        _options(
            default=float(default),
            min=float(minimum),
            max=float(maximum),
            step=float(step),
            tooltip=tooltip,
        ),
    )


def bool_input(default: bool, *, tooltip: str | None = None) -> tuple:
    return ("BOOLEAN", _options(default=bool(default), tooltip=tooltip))


def combo_input(choices, default: str, *,
                tooltip: str | None = None) -> tuple:
    values = list(choices)
    if default not in values:
        raise ValueError(f"Default '{default}' is not in the choices {values}.")
    return (values, _options(default=default, tooltip=tooltip))


def output_dir_input(default: str = config.DEFAULT_OUTPUT_SUBDIR) -> tuple:
    return string_input(
        default,
        tooltip=(
            "Folder under ComfyUI's output directory. An absolute path is "
            "used as-is."
        ),
    )


def encoding_input(default: str = "utf-8-sig") -> tuple:
    return combo_input(
        config.ENCODINGS,
        default,
        tooltip=(
            "utf-8-sig writes a BOM, which most players detect for Chinese "
            "subtitles. Use gbk only for older Windows players."
        ),
    )


def device_input(default: str = "auto") -> tuple:
    return combo_input(
        config.DEVICE_CHOICES,
        default,
        tooltip="auto uses CUDA when the ComfyUI environment can see a GPU.",
    )


__all__ = [
    "bool_input",
    "combo_input",
    "device_input",
    "encoding_input",
    "float_input",
    "int_input",
    "output_dir_input",
    "string_input",
]
