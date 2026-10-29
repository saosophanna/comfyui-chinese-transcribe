"""FFmpeg/ffprobe discovery and helpers.

FFmpeg is a hard requirement for audio extraction and the silence-based VAD.
ffprobe is preferred for media inspection; when it is missing but ComfyUI's
bundled PyAV is available, ``media.probe_media`` falls back to PyAV.
"""

from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
from pathlib import Path

from . import config


class FFmpegError(RuntimeError):
    """An ffmpeg or ffprobe command failed."""


class FFprobeUnavailable(FFmpegError):
    """ffprobe could not be found; callers may try a PyAV fallback."""


# Hide console windows when ComfyUI runs these tools on Windows.
_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _executable_name(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


@functools.lru_cache(maxsize=1)
def find_ffmpeg() -> str:
    """Locate the ffmpeg executable or raise a helpful error."""
    override = os.environ.get(config.ENV_FFMPEG_BINARY)
    if override:
        path = _check_override(override, "FFMPEG_BINARY")
        if path is not None:
            return path

    found = shutil.which("ffmpeg")
    if found:
        return found

    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    raise FFmpegError(
        "ffmpeg was not found. Install FFmpeg and add it to PATH, or set the "
        "FFMPEG_BINARY environment variable to the ffmpeg executable.\n"
        "Windows: winget install Gyan.FFmpeg (or download from ffmpeg.org).\n"
        "Then restart ComfyUI so the new PATH is visible."
    )


@functools.lru_cache(maxsize=1)
def find_ffprobe() -> str | None:
    """Locate ffprobe, returning None when it is not installed."""
    override = os.environ.get(config.ENV_FFPROBE_BINARY)
    if override:
        path = _check_override(override, "FFPROBE_BINARY")
        if path is not None:
            return path

    found = shutil.which("ffprobe")
    if found:
        return found

    # imageio-ffmpeg ships ffmpeg only; check for a sibling anyway.
    try:
        sibling = Path(find_ffmpeg()).with_name(_executable_name("ffprobe"))
        if sibling.is_file():
            return str(sibling)
    except FFmpegError:
        pass
    return None


def _check_override(value: str, variable: str) -> str | None:
    text = os.path.expandvars(os.path.expanduser(str(value).strip()))
    if not text:
        return None
    path = Path(text)
    if path.is_file():
        return str(path)
    found = shutil.which(text)
    if found:
        return found
    raise FFmpegError(
        f"{variable} is set to '{text}', but that file does not exist."
    )


def run(command, *, timeout: float = 600.0, what: str = "ffmpeg",
        check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess without a console window and wrap failures."""
    try:
        process = subprocess.run(
            [str(part) for part in command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
    except FileNotFoundError as exc:
        raise FFmpegError(
            f"Cannot run {what}: executable not found ({command[0]})."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(
            f"{what} timed out after {timeout:.0f}s. The media may be very "
            f"long or the process may be stuck."
        ) from exc

    if check and process.returncode != 0:
        detail = _tail(process.stderr) or _tail(process.stdout) or "(no output)"
        raise FFmpegError(f"{what} failed (exit {process.returncode}):\n{detail}")
    return process


def probe_json(path, *, timeout: float = 60.0) -> dict:
    """Return ffprobe's JSON for *path*."""
    ffprobe = find_ffprobe()
    if ffprobe is None:
        raise FFprobeUnavailable(
            "ffprobe was not found, so the media file cannot be inspected."
        )
    process = run(
        [
            ffprobe,
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        timeout=timeout,
        what="ffprobe",
    )
    try:
        return json.loads(process.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise FFmpegError(
            f"ffprobe returned data that is not JSON: {process.stdout[:500]}"
        ) from exc


def build_extract_command(ffmpeg, input_path, output_path, sample_rate: int,
                          mono: bool, start_s: float | None = None,
                          duration_s: float | None = None) -> list[str]:
    """Build the audio-extraction command (pure, used by the tests)."""
    command = [str(ffmpeg), "-hide_banner", "-nostdin", "-y"]
    if start_s is not None:
        # Input seeking keeps long-file chunking fast and is frame accurate
        # when the output is re-encoded.
        command += ["-ss", f"{max(0.0, float(start_s)):.3f}"]
    command += [
        "-i", str(input_path),
        "-map", "0:a:0",
        "-vn",
        "-ac", "1" if mono else "2",
        "-ar", str(int(sample_rate)),
        "-c:a", "pcm_s16le",
    ]
    if duration_s is not None:
        command += ["-t", f"{max(0.001, float(duration_s)):.3f}"]
    command.append(str(output_path))
    return command


def extract_audio(input_path, output_path, *, sample_rate: int = 16000,
                  mono: bool = True, start_s: float | None = None,
                  duration_s: float | None = None,
                  timeout: float | None = None) -> Path:
    """Extract/normalise the first audio stream to a PCM WAV file."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    if not input_path.is_file():
        raise FFmpegError(f"Input media does not exist: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if timeout is None:
        timeout = max(300.0, float(duration_s or 0.0) * 4.0)

    command = build_extract_command(
        find_ffmpeg(), input_path, output_path, sample_rate, mono,
        start_s=start_s, duration_s=duration_s,
    )
    run(command, timeout=timeout, what="ffmpeg audio extraction")

    if not output_path.is_file() or output_path.stat().st_size <= 44:
        raise FFmpegError(
            f"ffmpeg finished but produced no usable audio file at: {output_path}"
        )
    return output_path


def _tail(text: str | None, lines: int = 20) -> str:
    if not text:
        return ""
    return "\n".join(text.strip().splitlines()[-lines:])


__all__ = [
    "FFmpegError",
    "FFprobeUnavailable",
    "build_extract_command",
    "extract_audio",
    "find_ffmpeg",
    "find_ffprobe",
    "probe_json",
    "run",
]
