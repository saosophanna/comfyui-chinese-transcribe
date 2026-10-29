"""WAV inspection and slicing helpers."""

from __future__ import annotations

import wave
from pathlib import Path

from . import ffmpeg_utils


def wav_info(path) -> dict | None:
    """Return basic WAV parameters, or None when the file is not a WAV."""
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
            return {
                "channels": handle.getnchannels(),
                "sample_width": handle.getsampwidth(),
                "sample_rate": rate,
                "frames": frames,
                "duration": frames / rate if rate else 0.0,
            }
    except (wave.Error, EOFError, OSError):
        return None


def audio_duration(path) -> float:
    """Duration in seconds for any media file."""
    info = wav_info(path)
    if info is not None:
        return float(info["duration"])

    from .media import probe_media  # local import keeps media a leaf module

    return float(probe_media(path).get("duration") or 0.0)


def slice_audio(src, dst, start_s: float, end_s: float,
                fallback_sample_rate: int = 16000) -> Path:
    """Write the ``[start_s, end_s)`` range of *src* to a WAV file.

    PCM WAV files are sliced with the standard library; anything else is
    normalised through ffmpeg first.
    """
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    start_s = max(0.0, float(start_s))
    end_s = max(start_s, float(end_s))
    duration = end_s - start_s
    if duration <= 0:
        raise ValueError(
            f"Cannot slice audio: end ({end_s:.3f}s) must be after start "
            f"({start_s:.3f}s)."
        )

    info = wav_info(src)
    if info is not None and info["sample_width"] == 2:
        rate = info["sample_rate"]
        first = min(int(round(start_s * rate)), info["frames"])
        last = min(int(round(end_s * rate)), info["frames"])
        frame_count = max(0, last - first)
        if frame_count == 0:
            raise ValueError(
                f"Audio slice {start_s:.3f}-{end_s:.3f}s is outside the file "
                f"(duration {info['duration']:.3f}s)."
            )

        with wave.open(str(src), "rb") as reader:
            reader.setpos(first)
            payload = reader.readframes(frame_count)
            params = reader.getparams()

        with wave.open(str(dst), "wb") as writer:
            writer.setnchannels(params.nchannels)
            writer.setsampwidth(params.sampwidth)
            writer.setframerate(params.framerate)
            writer.writeframes(payload)
        return dst

    ffmpeg_utils.extract_audio(
        src, dst,
        sample_rate=fallback_sample_rate,
        mono=True,
        start_s=start_s,
        duration_s=duration,
        timeout=max(120.0, duration * 4.0),
    )
    return dst


__all__ = ["audio_duration", "slice_audio", "wav_info"]
