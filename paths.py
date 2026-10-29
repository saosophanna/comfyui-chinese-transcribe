"""Input/output path handling.

Relative output paths stay inside ComfyUI's output directory; absolute paths
are honoured because these nodes run on the user's own machine. Relative input
paths are looked up in ComfyUI's input directory, then its output directory,
then the current working directory.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from . import config
from .sanitize import to_text

_INVALID_FILENAME_CHARS = '<>:"/\\|?*'
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_KNOWN_EXTENSIONS = {
    ".txt", ".srt", ".vtt", ".json", ".md",
    ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus",
    ".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".ts", ".m4v",
    ".mpg", ".mpeg", ".wmv", ".3gp", ".mts", ".m2ts",
}


def output_root() -> Path:
    """ComfyUI's output directory, or a local fallback for headless use."""
    override = os.environ.get(config.ENV_OUTPUT_DIR)
    if override:
        return Path(override).expanduser().resolve()
    try:
        import folder_paths  # type: ignore

        return Path(folder_paths.get_output_directory()).resolve()
    except Exception:
        return (Path.cwd() / "output").resolve()


def input_root() -> Path:
    """ComfyUI's input directory, or a local fallback for headless use."""
    override = os.environ.get(config.ENV_INPUT_DIR)
    if override:
        return Path(override).expanduser().resolve()
    try:
        import folder_paths  # type: ignore

        return Path(folder_paths.get_input_directory()).resolve()
    except Exception:
        return (Path.cwd() / "input").resolve()


def resolve_output_dir(value) -> Path:
    """Resolve the ``output_dir`` widget to a directory path.

    Relative values must stay inside ComfyUI's output folder. Absolute values
    are used as given.
    """
    text = to_text(value).strip() or config.DEFAULT_OUTPUT_SUBDIR
    text = os.path.expandvars(os.path.expanduser(text))
    path = Path(text)
    if path.is_absolute():
        return path

    root = output_root()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ValueError(
            f"output_dir must stay inside ComfyUI's output directory "
            f"({root}) unless it is an absolute path; got '{text}'."
        ) from None
    return candidate


def resolve_output_file(output_dir, filename, default_stem: str,
                        extension: str) -> Path:
    """Build an output file path with a sanitized name and extension."""
    name = clean_optional_text(filename) or default_stem
    name = safe_filename(name, fallback=default_stem)
    name = with_extension(name, extension)
    directory = resolve_output_dir(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


def resolve_input_path(value) -> Path:
    """Resolve a media path from a ComfyUI widget or a node output."""
    text = to_text(value).strip()
    if not text:
        raise ValueError(
            "A local media path is required. Put the file in ComfyUI's input "
            "directory and enter its name, or use the Media Input node."
        )

    text = os.path.expandvars(os.path.expanduser(text))
    path = Path(text)
    if path.is_absolute():
        candidates = [path]
    else:
        candidates = [input_root() / path, output_root() / path, Path.cwd() / path]

    tried = []
    for candidate in candidates:
        candidate = candidate.resolve()
        tried.append(str(candidate))
        if candidate.is_file():
            return candidate

    searched = "\n  ".join(dict.fromkeys(tried))
    raise ValueError(
        f"Media file not found: '{text}'. Looked in:\n  {searched}\n"
        "Run 'Resolve Media' or 'Download Media' first, or check the path."
    )


def input_file_state(value) -> str:
    """Non-raising cache key for a file-path widget (used by IS_CHANGED)."""
    text = to_text(value).strip()
    if not text:
        return "empty"
    try:
        path = resolve_input_path(text)
    except ValueError:
        return f"{text}|missing"
    return f"{path}|{file_state(path)}"


def file_state(path) -> str:
    """mtime/size cache key for a file, or ``missing``."""
    try:
        stat = Path(path).stat()
    except OSError:
        return "missing"
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def safe_filename(name, fallback: str = "file", max_length: int = 120) -> str:
    """Strip path separators and Windows-illegal characters from a filename."""
    text = to_text(name).strip()
    for char in _INVALID_FILENAME_CHARS:
        text = text.replace(char, "_")
    text = _CONTROL_CHARS.sub("", text).strip().rstrip(" .")
    if not text:
        text = fallback

    if text.split(".")[0].upper() in _RESERVED_NAMES:
        text = "_" + text

    if len(text) > max_length:
        suffix = Path(text).suffix
        keep = max(1, max_length - len(suffix))
        text = text[:keep].rstrip(" .") + suffix

    return text or fallback


def with_extension(name: str, extension: str) -> str:
    """Return *name* ending in *extension*.

    A recognised extension is replaced (``subs.en.srt`` -> ``subs.srt``); an
    unrecognised suffix is kept and the extension appended instead.
    """
    ext = "." + extension.lstrip(".").lower()
    suffix = Path(name).suffix.lower()
    if suffix == ext:
        return name
    if suffix and suffix in _KNOWN_EXTENSIONS:
        return Path(name).stem + ext
    return name + ext


def clean_optional_text(value) -> str:
    """Trimmed text that ignores shifted boolean-like widget values."""
    text = to_text(value).strip()
    if not text or text.lower() in {"true", "false", "none", "null", "undefined"}:
        return ""
    return text


def is_known_extension(suffix: str) -> bool:
    return suffix.lower() in _KNOWN_EXTENSIONS


__all__ = [
    "clean_optional_text",
    "file_state",
    "input_file_state",
    "input_root",
    "is_known_extension",
    "output_root",
    "resolve_input_path",
    "resolve_output_dir",
    "resolve_output_file",
    "safe_filename",
    "with_extension",
]
