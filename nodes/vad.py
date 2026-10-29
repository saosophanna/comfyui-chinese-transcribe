"""VAD node: detect speech regions and optionally write split chunks."""

from __future__ import annotations

from .. import audio, config, paths, speech
from ..sanitize import coerce_bool, coerce_choice, coerce_float, coerce_int
from .common import log, make_progress
from .inputs import (
    bool_input,
    combo_input,
    device_input,
    float_input,
    int_input,
    output_dir_input,
    string_input,
)


class ChineseTranscribeVAD:
    """Find speech regions with FFmpeg silencedetect or FunASR fsmn-vad."""

    CATEGORY = config.CATEGORY
    RETURN_TYPES = (config.TYPE_SPEECH_SEGMENTS, "INT", "FLOAT")
    RETURN_NAMES = ("speech_segments", "segment_count", "speech_seconds")
    FUNCTION = "detect"
    DESCRIPTION = (
        "Detects speech and splits long recordings at silence. Connect the "
        "output to FunASR Transcribe to transcribe each region and get "
        "segment-level subtitle timing even with models that return no "
        "timestamps. The FunASR transcribe node also has its own built-in "
        "VAD when this node is not connected."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio_path": string_input(
                    "",
                    tooltip="Audio file, typically the output of FFmpeg Extract Audio.",
                ),
                "backend": combo_input(
                    config.VAD_BACKENDS,
                    config.DEFAULT_VAD_BACKEND,
                    tooltip=(
                        "ffmpeg = fast silence detection, no model. "
                        "funasr = fsmn-vad model, better on noisy audio."
                    ),
                ),
                "threshold_db": float_input(
                    -35.0, -80.0, 0.0, step=1.0,
                    tooltip=(
                        "ffmpeg backend: audio quieter than this is silence. "
                        "Raise toward 0 for noisy rooms; lower for quiet speech."
                    ),
                ),
                "min_silence_ms": int_input(
                    400, 50, 10000,
                    tooltip="ffmpeg backend: shortest pause that ends a speech region.",
                ),
                "min_speech_ms": int_input(
                    250, 0, 10000,
                    tooltip="ffmpeg backend: shorter bursts are discarded as noise.",
                ),
                "pad_ms": int_input(
                    200, 0, 2000,
                    tooltip="Keep this much audio around each region so words are not clipped.",
                ),
                "max_segment_seconds": float_input(
                    30.0, 1.0, 300.0, step=1.0,
                    tooltip="Split longer speech regions into chunks of at most this length.",
                ),
                "device": device_input("auto"),
            },
            "optional": {
                "write_chunks": bool_input(
                    False,
                    tooltip="Write each speech region as its own WAV file.",
                ),
                "output_dir": output_dir_input("transcribe/chunks"),
            },
        }

    @classmethod
    def IS_CHANGED(cls, audio_path, backend, threshold_db, min_silence_ms,
                   min_speech_ms, pad_ms, max_segment_seconds, device,
                   write_chunks=False, output_dir="", **kwargs):
        return "|".join([
            paths.input_file_state(audio_path),
            str(backend), str(threshold_db), str(min_silence_ms),
            str(min_speech_ms), str(pad_ms), str(max_segment_seconds),
            str(device), str(write_chunks), str(output_dir),
        ])

    def detect(self, audio_path, backend, threshold_db, min_silence_ms,
               min_speech_ms, pad_ms, max_segment_seconds, device,
               write_chunks=False, output_dir="transcribe/chunks"):
        path = paths.resolve_input_path(audio_path)
        backend = coerce_choice(
            backend, config.VAD_BACKENDS, config.DEFAULT_VAD_BACKEND
        )

        payload = speech.detect(
            path,
            backend=backend,
            threshold_db=coerce_float(threshold_db, -35.0, -80.0, 0.0),
            min_silence_ms=coerce_int(min_silence_ms, 400, 50, 10000),
            min_speech_ms=coerce_int(min_speech_ms, 250, 0, 10000),
            pad_ms=coerce_int(pad_ms, 200, 0, 2000),
            max_segment_seconds=coerce_float(
                max_segment_seconds, 30.0, 1.0, 300.0
            ),
            device=coerce_choice(device, config.DEVICE_CHOICES, "auto"),
        )

        chunks: list[str] = []
        if coerce_bool(write_chunks, False) and payload["segments"]:
            destination = paths.resolve_output_dir(output_dir)
            destination.mkdir(parents=True, exist_ok=True)
            progress = make_progress(len(payload["segments"]))
            for index, (start, end) in enumerate(payload["segments"], start=1):
                chunk_path = destination / f"chunk_{index:04d}.wav"
                audio.slice_audio(path, chunk_path, start, end)
                chunks.append(str(chunk_path))
                if progress is not None:
                    progress.update(1)
            log(f"Wrote {len(chunks)} speech chunks to {destination}")

        payload["chunks"] = chunks
        count = len(payload["segments"])
        if count == 0:
            log(
                "Warning: no speech detected. Lower threshold_db, reduce "
                "min_speech_ms, or try the funasr backend."
            )
        else:
            log(
                f"VAD ({backend}): {count} regions, "
                f"{payload['speech_seconds']:.1f}s of speech in "
                f"{payload['duration']:.1f}s"
            )
        return (payload, count, float(payload["speech_seconds"]))


__all__ = ["ChineseTranscribeVAD"]
