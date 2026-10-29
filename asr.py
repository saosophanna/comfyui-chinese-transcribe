"""FunASR model loading, inference and result parsing."""

from __future__ import annotations

import re
import shutil
import tempfile
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from . import audio, config, funasr_utils, paths, speech
from . import transcript as transcript_utils
from .sanitize import to_text

_MODELS: dict[tuple[str, str, str], object] = {}
_MODEL_LOCK = threading.Lock()

_TAG_PATTERN = re.compile(r"<\|[^|>]*\|>")
_CJK_PATTERN = re.compile(r"[㐀-鿿]")


def get_model(model_id: str, device: str, hub: str = "auto"):
    """Load (once) and return ``(model, resolved_device)``."""
    resolved = funasr_utils.resolve_device(device)
    key = (model_id, resolved, hub or "auto")
    with _MODEL_LOCK:
        model = _MODELS.get(key)
        if model is not None:
            return model, resolved

        _log(f"Loading FunASR model '{model_id}' on {resolved} ...")
        started = time.time()
        model = _build_model(model_id, resolved, hub)
        _MODELS[key] = model
        _log(f"Model ready in {time.time() - started:.1f}s")
    return model, resolved


def _build_model(model_id: str, device: str, hub: str):
    funasr = funasr_utils.require_funasr()

    kwargs = {"model": model_id, "device": device, "disable_update": True}
    if hub and hub != "auto":
        kwargs["hub"] = hub

    if model_id == config.DEFAULT_MODEL:
        # SenseVoice uses its own punctuation; VAD handles long recordings.
        kwargs.update(
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
        )
    elif "paraformer" in model_id.lower():
        kwargs.update(
            vad_model="fsmn-vad",
            punc_model="ct-punc",
        )
    elif model_id == "FunAudioLLM/Fun-ASR-Nano-2512":
        kwargs.update(
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            trust_remote_code=True,
        )
    else:
        kwargs.update(vad_model="fsmn-vad")

    return funasr.AutoModel(**kwargs)


def transcribe(audio_path, *, model: str = config.DEFAULT_MODEL,
               device: str = "auto", language: str = "zh",
               use_itn: bool = True, batch_size_s: int = 300,
               hotword: str = "", hub: str = "auto",
               speech_segments=None, max_segment_seconds: float = 30.0,
               keep_chunks: bool = False, progress=None) -> dict:
    """Transcribe an audio file and return a SEGMENTS value."""
    path = Path(audio_path)
    if not path.is_file():
        raise ValueError(f"Audio file does not exist: {path}")

    duration = audio.audio_duration(path)

    pairs = None
    if speech_segments is not None:
        pairs = speech.normalize_speech_segments(speech_segments)
        pairs = speech.cap_segments(pairs, max_segment_seconds)
        if duration:
            pairs = [(start, min(end, duration)) for start, end in pairs]
        pairs = [
            (start, end)
            for start, end in pairs
            if end - start >= 0.05
        ]
        if not pairs:
            raise ValueError(
                "The connected VAD found no usable speech segments. Lower the "
                "VAD threshold or disconnect speech_segments to let FunASR use "
                "its own VAD."
            )

    model_obj, resolved_device = get_model(model, device, hub)

    if pairs is not None:
        return _transcribe_chunks(
            path,
            model_obj,
            model_id=model,
            device=resolved_device,
            language=language,
            use_itn=use_itn,
            batch_size_s=batch_size_s,
            hotword=hotword,
            pairs=pairs,
            duration=duration,
            keep_chunks=keep_chunks,
            progress=progress,
        )

    started = time.time()
    result = _generate(
        model_obj, model, path,
        language=language,
        use_itn=use_itn,
        batch_size_s=batch_size_s,
        hotword=hotword,
    )
    text, segments, timing = parse_result(
        result,
        model_id=model,
        offset=0.0,
        fallback_end=duration or None,
    )
    if progress is not None:
        progress.update(1)

    _log(
        f"Transcribed {path.name} with {model} on {resolved_device} in "
        f"{time.time() - started:.1f}s ({len(segments)} segments)"
    )
    return _result(
        text=text,
        segments=segments,
        duration=duration,
        language=language,
        model_id=model,
        device=resolved_device,
        timing=timing,
        chunks=[],
    )


def _transcribe_chunks(path: Path, model_obj, *, model_id: str, device: str,
                       language: str, use_itn: bool, batch_size_s: int,
                       hotword: str, pairs, duration: float,
                       keep_chunks: bool, progress=None) -> dict:
    work_dir = _make_work_dir(keep_chunks)
    started = time.time()
    texts: list[str] = []
    segments: list[dict] = []
    chunks: list[str] = []
    timings: set[str] = set()

    try:
        for index, (start, end) in enumerate(pairs, start=1):
            chunk_path = work_dir / f"chunk_{index:04d}.wav"
            audio.slice_audio(path, chunk_path, start, end)
            result = _generate(
                model_obj, model_id, chunk_path,
                language=language,
                use_itn=use_itn,
                batch_size_s=batch_size_s,
                hotword=hotword,
            )
            text, chunk_segments, timing = parse_result(
                result,
                model_id=model_id,
                offset=start,
                fallback_end=end,
            )
            texts.append(text)
            segments.extend(chunk_segments)
            timings.add(timing)
            chunks.append(str(chunk_path))
            if progress is not None:
                progress.update(1)
    finally:
        if not keep_chunks:
            shutil.rmtree(work_dir, ignore_errors=True)

    joined = join_texts(texts, language)
    timing = "sentence" if "sentence" in timings else "vad"
    _log(
        f"Transcribed {path.name} in {len(pairs)} VAD chunks with {model_id} "
        f"on {device} in {time.time() - started:.1f}s "
        f"({len(segments)} segments)"
    )
    return _result(
        text=joined,
        segments=segments,
        duration=duration,
        language=language,
        model_id=model_id,
        device=device,
        timing=timing,
        chunks=chunks if keep_chunks else [],
    )


def _result(*, text: str, segments: list[dict], duration: float,
            language: str, model_id: str, device: str, timing: str,
            chunks: list[str]) -> dict:
    return {
        "text": text,
        "segments": segments,
        "duration": round(float(duration or 0.0), 3),
        "language": language,
        "model": model_id,
        "device": device,
        "timing": timing,
        "has_timestamps": timing in {"sentence", "vad"},
        "chunks": chunks,
    }


def _generate(model_obj, model_id: str, path: Path, *, language: str,
              use_itn: bool, batch_size_s: int, hotword: str):
    if model_id == config.DEFAULT_MODEL:
        return model_obj.generate(
            input=str(path),
            cache={},
            language=language,
            use_itn=bool(use_itn),
            batch_size_s=max(1, int(batch_size_s)),
            merge_vad=True,
            merge_length_s=15,
        )

    if "paraformer" in model_id.lower():
        kwargs = {
            "input": str(path),
            "batch_size_s": max(1, int(batch_size_s)),
            "sentence_timestamp": True,
        }
        if hotword:
            kwargs["hotword"] = hotword
        try:
            return model_obj.generate(**kwargs)
        except TypeError as exc:
            _log(
                "This FunASR build rejected sentence_timestamp "
                f"({exc}); retrying without sentence timestamps."
            )
            kwargs.pop("sentence_timestamp", None)
            return model_obj.generate(**kwargs)

    if model_id == "FunAudioLLM/Fun-ASR-Nano-2512":
        # The documented call is plain generate(input=...); timestamps are
        # available only through the optional VAD chunk path.
        return model_obj.generate(input=str(path))

    return model_obj.generate(
        input=str(path),
        batch_size_s=max(1, int(batch_size_s)),
    )


def parse_result(result, *, model_id: str, offset: float = 0.0,
                 fallback_end: float | None = None):
    """Parse a FunASR result into ``(text, segments, timing)``.

    ``timing`` is ``sentence`` (per-sentence times), ``vad`` (chunk times) or
    ``whole`` (one cue spanning the supplied range).
    """
    item = _first_result_item(result)
    raw_text = to_text(item.get("text")).strip()
    text = clean_asr_text(raw_text, model_id)

    segments: list[dict] = []
    timing = "whole"

    sentence_info = item.get("sentence_info")
    if sentence_info is not None and not isinstance(
        sentence_info, (str, bytes, dict)
    ):
        try:
            sentence_entries = list(sentence_info)
        except TypeError:
            sentence_entries = []
        parsed = _segments_from_sentence_info(sentence_entries, offset)
        if parsed:
            segments = parsed
            timing = "sentence"

    if not segments:
        grouped = transcript_utils.group_char_timestamps(
            text, item.get("timestamp"), offset_s=offset
        )
        if grouped:
            segments = grouped
            timing = "sentence"

    if not segments and text:
        start = max(0.0, float(offset))
        end = float(fallback_end) if fallback_end is not None else start
        end = max(end, start + 0.05)
        segments = [{
            "start": round(start, 3),
            "end": round(end, 3),
            "text": text,
        }]

    if not text and segments:
        text = "".join(segment["text"] for segment in segments)

    if not segments and not text:
        raise RuntimeError(
            f"FunASR returned an empty result for model '{model_id}': {item!r}"
        )

    segments = _clean_segments(segments, offset, fallback_end)
    if not segments and text:
        start = max(0.0, float(offset))
        end = float(fallback_end) if fallback_end is not None else start + 0.05
        end = max(end, start + 0.05)
        segments = [{
            "start": round(start, 3),
            "end": round(end, 3),
            "text": text,
        }]
        timing = "whole"
    return text, segments, timing


def clean_asr_text(text: str, model_id: str) -> str:
    """Remove SenseVoice tags and apply its official post-processing."""
    text = to_text(text).strip()
    if not text:
        return ""

    if model_id == config.DEFAULT_MODEL:
        try:
            from funasr.utils.postprocess_utils import (  # type: ignore
                rich_transcription_postprocess,
            )

            cleaned = rich_transcription_postprocess(text)
            if cleaned and cleaned.strip():
                return cleaned.strip()
        except Exception:
            pass

    return _TAG_PATTERN.sub("", text).strip()


def join_texts(texts, language: str) -> str:
    """Join per-chunk texts with the spacing appropriate for the language."""
    parts = [to_text(text).strip() for text in texts]
    parts = [part for part in parts if part]
    if not parts:
        return ""

    if language in {"zh", "yue", "ja"}:
        return "".join(parts)
    if language == "auto":
        if any(_CJK_PATTERN.search(part) for part in parts):
            return "".join(parts)
        return " ".join(parts)
    return " ".join(parts)


def _segments_from_sentence_info(info: list, offset: float) -> list[dict]:
    segments: list[dict] = []
    for entry in info:
        if not isinstance(entry, dict):
            continue

        text = to_text(entry.get("sentence") or entry.get("text")).strip()
        if not text:
            continue

        start = _pick_float(entry, ("start", "start_time", "timestamp_start"))
        end = _pick_float(entry, ("end", "end_time", "timestamp_end"))

        stamps = entry.get("timestamp")
        if (
            (start is None or end is None)
            and stamps is not None
            and not isinstance(stamps, (str, bytes, dict))
        ):
            pairs = transcript_utils.timestamp_pairs(stamps)
            if pairs:
                if start is None:
                    start = pairs[0][0]
                if end is None:
                    end = pairs[-1][1]

        if start is None:
            continue
        if end is None:
            end = start + 500.0

        start_s = start / 1000.0 + offset
        end_s = end / 1000.0 + offset
        if end_s <= start_s:
            end_s = start_s + 0.05

        segments.append({
            "start": round(start_s, 3),
            "end": round(end_s, 3),
            "text": text,
        })
    return segments


def _clean_segments(segments: list[dict], offset: float,
                    fallback_end: float | None) -> list[dict]:
    cleaned: list[dict] = []
    limit = float(fallback_end) if fallback_end is not None else None

    for segment in segments:
        text = to_text(segment.get("text")).strip()
        if not text:
            continue
        try:
            start = float(segment.get("start"))
            end = float(segment.get("end"))
        except (TypeError, ValueError):
            continue

        start = max(0.0, start)
        end = max(start + 0.05, end)
        if limit is not None:
            start = min(start, limit)
            end = min(end, limit)
        if end <= start:
            end = start + 0.05

        cleaned.append({
            "start": round(start, 3),
            "end": round(end, 3),
            "text": text,
        })

    cleaned.sort(key=lambda segment: segment["start"])
    return cleaned


def _first_result_item(result) -> dict:
    if isinstance(result, dict):
        return result
    if isinstance(result, (list, tuple)):
        if not result:
            raise RuntimeError("FunASR returned no result.")
        first = result[0]
        if isinstance(first, dict):
            return first
        if (
            isinstance(first, (list, tuple))
            and first
            and isinstance(first[0], dict)
        ):
            return first[0]
    raise RuntimeError(f"Unexpected FunASR result shape: {result!r}")


def _pick_float(entry: dict, keys) -> float | None:
    for key in keys:
        if key not in entry:
            continue
        value = entry[key]
        if isinstance(value, bool):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _make_work_dir(keep_chunks: bool) -> Path:
    if keep_chunks:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        directory = (
            paths.resolve_output_dir("transcribe/chunks")
            / f"asr_{stamp}_{uuid.uuid4().hex[:6]}"
        )
        directory.mkdir(parents=True, exist_ok=True)
        return directory
    return Path(tempfile.mkdtemp(prefix="comfy_transcribe_"))


def _log(message: str) -> None:
    print(f"{config.LOG_PREFIX} {message}", flush=True)


__all__ = [
    "clean_asr_text",
    "get_model",
    "join_texts",
    "parse_result",
    "transcribe",
]
