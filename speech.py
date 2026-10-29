"""Speech activity detection.

Two backends:

* ``ffmpeg`` uses FFmpeg's ``silencedetect`` filter (fast, no model, works on
  any media file the rest of the pipeline accepts).
* ``funasr`` uses FunASR's ``fsmn-vad`` model and is more accurate on noisy or
  varied audio, at the cost of loading another model.

Both return plain ``(start, end)`` pairs in seconds.
"""

from __future__ import annotations

import json
import re
import threading

from . import audio, config, ffmpeg_utils, funasr_utils
from .sanitize import coerce_choice, to_text

_SILENCE_PATTERN = re.compile(r"silence_(start|end):\s*(-?\d+(?:\.\d+)?)")

_VAD_MODELS: dict[str, object] = {}
_VAD_LOCK = threading.Lock()


def parse_silencedetect(stderr: str, duration: float) -> list[tuple[float, float]]:
    """Return the silence intervals reported by ``silencedetect``."""
    events = _SILENCE_PATTERN.findall(stderr or "")
    silences: list[tuple[float, float]] = []
    current: float | None = None

    limit = max(0.0, float(duration or 0.0))
    for kind, raw_value in events:
        value = max(0.0, float(raw_value))
        if kind == "start":
            current = value
        elif current is not None:
            end = min(value, limit) if limit else value
            if end > current:
                silences.append((current, end))
            current = None

    if current is not None and limit and current < limit:
        # The file ended while still in silence.
        silences.append((current, limit))

    return silences


def speech_from_silences(duration: float,
                         silences: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Complement the silence intervals over ``[0, duration]``."""
    duration = max(0.0, float(duration or 0.0))
    if duration <= 0:
        return []

    regions: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in sorted(silences):
        start = max(0.0, min(float(start), duration))
        end = max(start, min(float(end), duration))
        if start > cursor:
            regions.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < duration:
        regions.append((cursor, duration))
    return regions


def refine_segments(segments, *, min_speech_ms: int = 250, pad_ms: int = 200,
                    max_segment_seconds: float = 30.0,
                    duration: float | None = None) -> list[tuple[float, float]]:
    """Filter, pad, merge and cap raw speech regions."""
    min_speech = max(0.0, float(min_speech_ms) / 1000.0)
    pad = max(0.0, float(pad_ms) / 1000.0)
    limit = max(0.0, float(duration)) if duration is not None else None

    padded: list[tuple[float, float]] = []
    for start, end in segments:
        start = max(0.0, float(start))
        end = max(start, float(end))
        if end - start < min_speech or end <= start:
            continue
        start = max(0.0, start - pad)
        end = end + pad
        if limit is not None:
            end = min(end, limit)
        if end > start:
            padded.append((start, end))

    padded.sort()
    merged: list[tuple[float, float]] = []
    for start, end in padded:
        if merged and start <= merged[-1][1] + 1e-6:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    return cap_segments(merged, max_segment_seconds)


def cap_segments(segments, max_seconds: float) -> list[tuple[float, float]]:
    """Split regions longer than ``max_seconds`` into consecutive chunks."""
    max_seconds = float(max_seconds)
    capped: list[tuple[float, float]] = []
    for start, end in segments:
        start = max(0.0, float(start))
        end = max(start, float(end))
        if end <= start:
            continue
        if max_seconds <= 0 or end - start <= max_seconds:
            capped.append((start, end))
            continue
        cursor = start
        while cursor < end - 1e-6:
            nxt = min(cursor + max_seconds, end)
            capped.append((cursor, nxt))
            cursor = nxt
    return capped


def normalize_speech_segments(value) -> list[tuple[float, float]]:
    """Accept a SPEECH_SEGMENTS dict (or a pair list) as valid regions."""
    if isinstance(value, dict):
        raw = value.get("segments")
    else:
        raw = value
    if not isinstance(raw, (list, tuple)):
        raise ValueError(
            "speech_segments must come from the VAD node; reconnect the input."
        )

    segments: list[tuple[float, float]] = []
    for entry in raw:
        if isinstance(entry, dict):
            start, end = entry.get("start"), entry.get("end")
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            start, end = entry[0], entry[1]
        else:
            continue
        try:
            start_f, end_f = float(start), float(end)
        except (TypeError, ValueError):
            continue
        if end_f <= start_f:
            continue
        segments.append((max(0.0, start_f), end_f))

    segments.sort()
    merged: list[tuple[float, float]] = []
    for start, end in segments:
        # Merge overlaps only. Adjacent regions (end == next start) are
        # deliberate VAD chunk boundaries and must stay separate.
        if merged and start < merged[-1][1] - 1e-6:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def ffmpeg_vad(path, *, threshold_db: float = -35.0, min_silence_ms: int = 400,
               min_speech_ms: int = 250, pad_ms: int = 200,
               max_segment_seconds: float = 30.0,
               timeout: float | None = None) -> list[tuple[float, float]]:
    """Detect speech by finding silences with FFmpeg's silencedetect."""
    path = str(path)
    duration = audio.audio_duration(path)
    if duration <= 0:
        raise ValueError(
            f"Could not determine the duration of '{path}'. Check that the "
            "file contains a valid audio stream."
        )

    command = [
        ffmpeg_utils.find_ffmpeg(),
        "-hide_banner", "-nostdin",
        "-i", path,
        "-vn", "-sn", "-dn",
        "-af",
        f"silencedetect=noise={float(threshold_db):.1f}dB:"
        f"d={max(1, int(min_silence_ms)) / 1000.0:.3f}",
        "-f", "null", "-",
    ]
    process = ffmpeg_utils.run(
        command,
        timeout=timeout if timeout is not None else max(300.0, duration * 3.0),
        what="ffmpeg silencedetect",
    )
    silences = parse_silencedetect(process.stderr, duration)
    regions = speech_from_silences(duration, silences)
    return refine_segments(
        regions,
        min_speech_ms=min_speech_ms,
        pad_ms=pad_ms,
        max_segment_seconds=max_segment_seconds,
        duration=duration,
    )


def funasr_vad(path, *, device: str = "cpu", max_segment_seconds: float = 30.0,
               pad_ms: int = 200) -> list[tuple[float, float]]:
    """Detect speech with FunASR's fsmn-vad model."""
    funasr = funasr_utils.require_funasr()
    resolved_device = funasr_utils.resolve_device(device)
    model = _get_vad_model(funasr, resolved_device)

    duration = audio.audio_duration(path)
    result = model.generate(
        input=str(path),
        max_single_segment_time=int(max(1.0, float(max_segment_seconds)) * 1000),
    )
    pairs = _parse_vad_result(result)

    regions = [
        (max(0.0, start - pad_ms / 1000.0),
         min(duration, end + pad_ms / 1000.0) if duration else end + pad_ms / 1000.0)
        for start, end in pairs
    ]
    return refine_segments(
        regions,
        min_speech_ms=0,
        pad_ms=0,
        max_segment_seconds=max_segment_seconds,
        duration=duration or None,
    )


def detect(path, *, backend: str = config.DEFAULT_VAD_BACKEND,
           threshold_db: float = -35.0, min_silence_ms: int = 400,
           min_speech_ms: int = 250, pad_ms: int = 200,
           max_segment_seconds: float = 30.0,
           device: str = "cpu") -> dict:
    """Run the selected VAD backend and return a SPEECH_SEGMENTS dict."""
    backend = coerce_choice(backend, config.VAD_BACKENDS, config.DEFAULT_VAD_BACKEND)
    if backend == "funasr":
        segments = funasr_vad(
            path,
            device=device,
            max_segment_seconds=max_segment_seconds,
            pad_ms=pad_ms,
        )
    else:
        segments = ffmpeg_vad(
            path,
            threshold_db=threshold_db,
            min_silence_ms=min_silence_ms,
            min_speech_ms=min_speech_ms,
            pad_ms=pad_ms,
            max_segment_seconds=max_segment_seconds,
        )

    duration = audio.audio_duration(path)
    speech_seconds = sum(end - start for start, end in segments)
    return {
        "audio_path": str(path),
        "duration": round(float(duration or 0.0), 3),
        "backend": backend,
        "segments": [[round(start, 3), round(end, 3)] for start, end in segments],
        "speech_seconds": round(float(speech_seconds), 3),
        "params": {
            "threshold_db": float(threshold_db),
            "min_silence_ms": int(min_silence_ms),
            "min_speech_ms": int(min_speech_ms),
            "pad_ms": int(pad_ms),
            "max_segment_seconds": float(max_segment_seconds),
            "device": to_text(device, "cpu"),
        },
        "chunks": [],
    }


def _get_vad_model(funasr, device: str):
    with _VAD_LOCK:
        model = _VAD_MODELS.get(device)
        if model is None:
            model = funasr.AutoModel(
                model="fsmn-vad",
                device=device,
                disable_update=True,
            )
            _VAD_MODELS[device] = model
    return model


def _parse_vad_result(result) -> list[tuple[float, float]]:
    if isinstance(result, dict):
        result = [result]
    if not isinstance(result, (list, tuple)) or not result:
        raise RuntimeError(f"FunASR VAD returned no result: {result!r}")

    item = result[0]
    if not isinstance(item, dict):
        raise RuntimeError(f"Unexpected FunASR VAD result: {item!r}")

    values = item.get("value")
    if values is None:
        values = item.get("segments")
    if isinstance(values, str):
        try:
            values = json.loads(values)
        except json.JSONDecodeError:
            values = []

    pairs: list[tuple[float, float]] = []
    try:
        entries = list(values or [])
    except TypeError:
        entries = []
    for entry in entries:
        if isinstance(entry, (str, bytes, dict)):
            continue
        try:
            start, end = float(entry[0]) / 1000.0, float(entry[1]) / 1000.0
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        if end > start:
            pairs.append((start, end))
    return pairs


__all__ = [
    "cap_segments",
    "detect",
    "ffmpeg_vad",
    "funasr_vad",
    "normalize_speech_segments",
    "parse_silencedetect",
    "refine_segments",
    "speech_from_silences",
]
