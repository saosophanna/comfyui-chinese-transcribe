"""FunASR Transcribe node."""

from __future__ import annotations

import json
from pathlib import Path

from .. import asr, config, paths, speech
from ..sanitize import coerce_bool, coerce_choice, coerce_float, coerce_int, to_text
from .common import log, make_progress
from .inputs import (
    bool_input,
    combo_input,
    device_input,
    float_input,
    int_input,
    string_input,
)


class ChineseTranscribeFunASR:
    """Transcribe Chinese speech with FunASR."""

    CATEGORY = config.CATEGORY
    RETURN_TYPES = ("STRING", config.TYPE_SEGMENTS, "INT")
    RETURN_NAMES = ("transcript", "segments", "segment_count")
    FUNCTION = "transcribe"
    DESCRIPTION = (
        "Runs FunASR on a WAV file. SenseVoiceSmall is a fast multilingual "
        "baseline; paraformer-zh returns sentence timestamps (best for "
        "subtitles); Fun-ASR-Nano is a newer multilingual model without "
        "documented timestamps. Connect the VAD node to get timed segments "
        "from any model."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio_path": string_input(
                    "",
                    tooltip="WAV from FFmpeg Extract Audio (mono, 16 kHz is ideal).",
                ),
                "model": combo_input(
                    config.MODEL_CHOICES,
                    config.DEFAULT_MODEL,
                    tooltip=(
                        "SenseVoiceSmall: fast, zh/en/yue/ja/ko, no timestamps. "
                        "paraformer-zh: Mandarin with sentence timestamps. "
                        "Fun-ASR-Nano: newer multilingual model."
                    ),
                ),
                "device": device_input("auto"),
                "language": combo_input(
                    config.LANGUAGE_CHOICES,
                    "zh",
                    tooltip=(
                        "SenseVoice language hint. 'auto' detects. Ignored by "
                        "paraformer-zh and Fun-ASR-Nano."
                    ),
                ),
                "use_itn": bool_input(
                    True,
                    tooltip="SenseVoice: inverse text normalisation (numbers, dates).",
                ),
                "batch_size_s": int_input(
                    300, 1, 3600,
                    tooltip=(
                        "Audio batch size in seconds. SenseVoice examples use 60; "
                        "paraformer-zh examples use 300."
                    ),
                ),
                "max_segment_seconds": float_input(
                    30.0, 1.0, 300.0, step=1.0,
                    tooltip=(
                        "When speech_segments is connected, split any region "
                        "longer than this before recognition."
                    ),
                ),
            },
            "optional": {
                "speech_segments": (
                    config.TYPE_SPEECH_SEGMENTS,
                    {
                        "tooltip": (
                            "Optional VAD output. When connected, each speech "
                            "region is transcribed separately and its timing is "
                            "kept."
                        )
                    },
                ),
                "hotword": string_input(
                    "",
                    tooltip=(
                        "paraformer-zh only: space-separated hotwords, e.g. "
                        "'魔搭 20'. Ignored by the other models."
                    ),
                ),
                "hub": combo_input(
                    config.HUB_CHOICES,
                    "auto",
                    tooltip=(
                        "Model download source. auto lets FunASR decide; choose "
                        "ms (ModelScope) or hf (Hugging Face) if needed."
                    ),
                ),
                "keep_chunks": bool_input(
                    False,
                    tooltip=(
                        "Keep the temporary VAD chunk WAVs under "
                        "output/transcribe/chunks for debugging."
                    ),
                ),
            },
        }

    @classmethod
    def IS_CHANGED(cls, audio_path, model, device, language, use_itn,
                   batch_size_s, max_segment_seconds, speech_segments=None,
                   hotword="", hub="auto", keep_chunks=False, **kwargs):
        segments_key = ""
        if isinstance(speech_segments, dict):
            try:
                segments_key = json.dumps(
                    speech_segments.get("segments"), sort_keys=True, default=str
                )
            except (TypeError, ValueError):
                segments_key = str(speech_segments.get("segments"))
        return "|".join([
            paths.input_file_state(audio_path),
            str(model), str(device), str(language), str(use_itn),
            str(batch_size_s), str(max_segment_seconds), str(hotword),
            str(hub), str(keep_chunks), segments_key,
        ])

    def transcribe(self, audio_path, model, device, language, use_itn,
                   batch_size_s, max_segment_seconds, speech_segments=None,
                   hotword="", hub="auto", keep_chunks=False):
        path = paths.resolve_input_path(audio_path)
        model_id = coerce_choice(model, config.MODEL_CHOICES, config.DEFAULT_MODEL)
        device_choice = coerce_choice(device, config.DEVICE_CHOICES, "auto")
        language_choice = coerce_choice(
            language, config.LANGUAGE_CHOICES, "zh"
        )
        hub_choice = coerce_choice(hub, config.HUB_CHOICES, "auto")
        max_segment = coerce_float(
            max_segment_seconds, 30.0, 1.0, 300.0
        )
        hotword_text = to_text(hotword).strip()

        if hotword_text and "paraformer" not in model_id.lower():
            log(f"hotword is ignored by {model_id} (paraformer-zh only).")

        total = 1
        if speech_segments is not None:
            pairs = speech.normalize_speech_segments(speech_segments)
            total = max(1, len(speech.cap_segments(pairs, max_segment)))
            source_audio = (
                to_text(speech_segments.get("audio_path"))
                if isinstance(speech_segments, dict)
                else ""
            )
            if source_audio:
                try:
                    same = Path(source_audio).resolve() == path.resolve()
                except OSError:
                    same = False
                if not same:
                    log(
                        "Warning: speech_segments came from a different audio "
                        "file than audio_path. The connected audio_path wins."
                    )

        progress = make_progress(total)
        try:
            result = asr.transcribe(
                path,
                model=model_id,
                device=device_choice,
                language=language_choice,
                use_itn=coerce_bool(use_itn, True),
                batch_size_s=coerce_int(batch_size_s, 300, 1, 3600),
                hotword=hotword_text,
                hub=hub_choice,
                speech_segments=speech_segments,
                max_segment_seconds=max_segment,
                keep_chunks=coerce_bool(keep_chunks, False),
                progress=progress,
            )
        except Exception as exc:
            raise RuntimeError(
                f"FunASR transcription failed for '{path.name}' with model "
                f"'{model_id}': {exc}"
            ) from exc

        text = result["text"]
        if not text.strip():
            log(
                "Warning: FunASR returned empty text. Check that the audio "
                "contains speech and that the language/model match."
            )
        if result.get("timing") == "whole":
            log(
                "Note: this model returned no timestamps. Use paraformer-zh "
                "or connect the VAD node to get timed subtitle segments."
            )
        if result.get("chunks"):
            log(
                f"Kept {len(result['chunks'])} chunk WAVs under "
                f"{Path(result['chunks'][0]).parent}"
            )

        log(
            f"Transcript: {len(text)} chars, {len(result['segments'])} "
            f"segments, timing={result.get('timing')}, "
            f"device={result.get('device')}"
        )
        return (text, result, len(result["segments"]))


__all__ = ["ChineseTranscribeFunASR"]
