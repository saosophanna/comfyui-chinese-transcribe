"""Transcript segmentation and formatting (TXT / JSON / SRT / VTT)."""

from __future__ import annotations

import json
import unicodedata

from .sanitize import to_text

# Characters FunASR's punctuation model may add without giving them their own
# timestamp. They are attached to the surrounding cue instead.
PUNCTUATION = set(
    "，。！？；：、,.!?;:…—–-()（）《》〈〉【】[]{}“”‘’\"'·「」『』"
)

# End a subtitle cue after these characters.
SENTENCE_END = set("。！？!?；;…\n")

_MS_PER_SECOND = 1000.0


def group_char_timestamps(text: str, timestamps, *, offset_s: float = 0.0,
                          max_chars: int = 60,
                          max_seconds: float = 12.0) -> list[dict] | None:
    """Turn FunASR's character-level timestamps into readable cues.

    ``timestamps`` is a list of ``[start_ms, end_ms]`` pairs. FunASR adds
    punctuation after recognition, so the list may align to the text with or
    without punctuation. Returns ``None`` when no alignment can be found.
    """
    text = to_text(text)
    pairs = timestamp_pairs(timestamps)
    if not text.strip() or not pairs:
        return None

    mapping = _align_timestamps(text, pairs)
    if mapping is None:
        return None

    cues: list[dict] = []
    chars: list[str] = []
    cue_start: float | None = None
    cue_end: float | None = None
    timed_count = 0

    def flush() -> None:
        nonlocal chars, cue_start, cue_end, timed_count
        if cue_start is not None and cue_end is not None:
            cue_text = "".join(chars).strip()
            if cue_text:
                start_s = max(0.0, cue_start / _MS_PER_SECOND + offset_s)
                end_s = max(start_s + 0.05, cue_end / _MS_PER_SECOND + offset_s)
                cues.append({
                    "start": round(start_s, 3),
                    "end": round(end_s, 3),
                    "text": cue_text,
                })
        chars = []
        cue_start = None
        cue_end = None
        timed_count = 0

    for index, char in enumerate(text):
        pair = mapping.get(index)
        if pair is not None:
            if cue_start is None:
                cue_start = pair[0]
            cue_end = pair[1]
            timed_count += 1

        chars.append(char)

        if cue_start is None:
            continue

        elapsed = (cue_end - cue_start) / _MS_PER_SECOND
        if (
            char in SENTENCE_END
            or (max_chars > 0 and timed_count >= max_chars)
            or (max_seconds > 0 and elapsed >= max_seconds)
        ):
            flush()

    flush()
    return cues or None


def _align_timestamps(text: str, pairs: list[tuple[float, float]]):
    """Map timestamp pairs onto character positions, or return None."""
    candidates = (
        lambda char: True,
        lambda char: not char.isspace(),
        lambda char: not char.isspace() and char not in PUNCTUATION,
    )
    for predicate in candidates:
        positions = [index for index, char in enumerate(text) if predicate(char)]
        if len(positions) == len(pairs):
            return dict(zip(positions, pairs))
    return None


def timestamp_pairs(timestamps) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    if timestamps is None or isinstance(timestamps, (str, bytes, dict)):
        return pairs
    try:
        entries = list(timestamps)
    except TypeError:
        return pairs

    for entry in entries:
        if isinstance(entry, (str, bytes, dict)):
            continue
        try:
            start, end = float(entry[0]), float(entry[1])
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        if end >= start:
            pairs.append((start, end))
    return pairs


def normalize_segments(segments) -> list[dict]:
    """Coerce segment dicts/pairs into ``{start, end, text}`` records."""
    normalized: list[dict] = []
    if not isinstance(segments, (list, tuple)):
        return normalized

    for entry in segments:
        if isinstance(entry, dict):
            start, end = entry.get("start"), entry.get("end")
            text = entry.get("text")
            if text is None:
                text = entry.get("sentence")
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            start, end = entry[0], entry[1]
            text = entry[2] if len(entry) > 2 else ""
        else:
            continue

        try:
            start_f, end_f = float(start), float(end)
        except (TypeError, ValueError):
            continue
        if end_f < start_f:
            end_f = start_f
        if end_f - start_f < 0.05:
            end_f = start_f + 0.05

        cue_text = to_text(text).strip()
        if not cue_text:
            continue

        normalized.append({
            "start": round(max(0.0, start_f), 3),
            "end": round(end_f, 3),
            "text": cue_text,
        })
    return normalized


def format_timestamp(seconds: float, separator: str = ",") -> str:
    """Format seconds as ``HH:MM:SS,mmm`` (SRT) or ``HH:MM:SS.mmm`` (VTT)."""
    total_ms = int(round(max(0.0, float(seconds)) * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def wrap_cue_text(text: str, max_chars: int = 42) -> str:
    """Wrap subtitle text to a display width, preferring punctuation breaks.

    Width is measured in terminal-like columns: CJK/full-width characters
    count as 2, so the default 42 gives roughly 21 Chinese characters per line.
    """
    text = " ".join(to_text(text).split())
    if max_chars <= 0:
        return text
    if sum(_char_width(char) for char in text) <= max_chars:
        return text

    lines: list[str] = []
    line = ""
    width = 0
    last_break = -1
    last_break_width = -1
    for char in text:
        line += char
        width += _char_width(char)
        if char == " " or char in PUNCTUATION:
            last_break = len(line)
            last_break_width = width
        if width >= max_chars:
            if last_break >= 1 and last_break_width >= max_chars // 2:
                lines.append(line[:last_break].rstrip())
                line = line[last_break:].lstrip()
                width = sum(_char_width(item) for item in line)
            else:
                lines.append(line.strip())
                line = ""
                width = 0
            last_break = -1
            last_break_width = -1
    if line.strip():
        lines.append(line.strip())
    return "\n".join(line for line in lines if line)


def _char_width(char: str) -> int:
    return 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1


def format_srt(segments, max_line_chars: int = 42) -> str:
    cues = normalize_segments(segments)
    if not cues:
        raise ValueError(
            "SRT output needs timed segments, but the transcript has none. "
            "Use the paraformer-zh model (it returns sentence timestamps) or "
            "connect the VAD node to FunASR Transcribe for segment timing."
        )

    blocks = []
    for index, cue in enumerate(cues, start=1):
        text = wrap_cue_text(cue["text"], max_line_chars)
        blocks.append(
            f"{index}\n"
            f"{format_timestamp(cue['start'])} --> {format_timestamp(cue['end'])}\n"
            f"{text}"
        )
    return "\n\n".join(blocks) + "\n"


def format_vtt(segments, max_line_chars: int = 42) -> str:
    cues = normalize_segments(segments)
    if not cues:
        raise ValueError(
            "VTT output needs timed segments, but the transcript has none. "
            "Use the paraformer-zh model or connect the VAD node."
        )

    lines = ["WEBVTT", ""]
    for index, cue in enumerate(cues, start=1):
        lines.append(str(index))
        lines.append(
            f"{format_timestamp(cue['start'], separator='.')} --> "
            f"{format_timestamp(cue['end'], separator='.')}"
        )
        lines.append(wrap_cue_text(cue["text"], max_line_chars))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_txt(text: str, segments) -> str:
    body = to_text(text).strip()
    if not body:
        body = "\n".join(cue["text"] for cue in normalize_segments(segments))
    return body + "\n" if body else ""


def format_json(text: str, segments_data: dict) -> str:
    data = segments_data if isinstance(segments_data, dict) else {}
    cues = normalize_segments(data.get("segments"))
    body = to_text(text).strip()
    if not body:
        body = "".join(cue["text"] for cue in cues)
    payload = {
        "text": body,
        "language": to_text(data.get("language")),
        "model": to_text(data.get("model")),
        "duration": data.get("duration"),
        "segments": cues,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def format_transcript(fmt: str, text: str, segments_data, *,
                      max_line_chars: int = 42) -> str:
    """Format a transcript as ``txt``, ``json``, ``srt`` or ``vtt``."""
    fmt = to_text(fmt).strip().lower()
    data = segments_data if isinstance(segments_data, dict) else {}
    segments = data.get("segments") if data else segments_data

    if fmt == "srt":
        return format_srt(segments, max_line_chars)
    if fmt == "vtt":
        return format_vtt(segments, max_line_chars)
    if fmt == "json":
        return format_json(
            text,
            data or {"segments": segments},
        )
    if fmt == "txt":
        return format_txt(text, segments)
    raise ValueError(
        f"Unknown transcript format '{fmt}'. Choose one of: srt, vtt, txt, json."
    )


__all__ = [
    "PUNCTUATION",
    "SENTENCE_END",
    "format_json",
    "format_srt",
    "format_timestamp",
    "format_transcript",
    "format_txt",
    "format_vtt",
    "group_char_timestamps",
    "normalize_segments",
    "timestamp_pairs",
    "wrap_cue_text",
]
