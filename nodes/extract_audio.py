"""FFmpeg Extract Audio node."""

from __future__ import annotations

from pathlib import Path

from .. import audio, config, ffmpeg_utils, media, paths
from ..sanitize import coerce_bool, coerce_int
from .common import log
from .inputs import bool_input, combo_input, output_dir_input, string_input


class ChineseTranscribeExtractAudio:
    """Extract the first audio stream as mono/16 kHz PCM WAV."""

    CATEGORY = config.CATEGORY
    RETURN_TYPES = ("STRING", "FLOAT", "INT")
    RETURN_NAMES = ("audio_path", "duration", "sample_rate")
    FUNCTION = "extract"
    DESCRIPTION = (
        "Runs FFmpeg to remove video and write a PCM WAV audio track. The "
        "default (mono, 16 kHz, pcm_s16le) is what FunASR expects. The "
        "source file is never modified."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "media_path": string_input(
                    "",
                    tooltip="Video or audio file to extract audio from.",
                ),
                "sample_rate": combo_input(
                    ("16000", "8000", "22050", "44100", "48000"),
                    config.DEFAULT_SAMPLE_RATE,
                    tooltip="FunASR models expect 16000 Hz.",
                ),
                "mono": bool_input(
                    True,
                    tooltip="Down-mix to one channel, as ASR models expect.",
                ),
                "output_dir": output_dir_input("transcribe/audio"),
            },
            "optional": {
                "filename": string_input(
                    "",
                    tooltip=(
                        "Optional WAV filename. Empty uses <source>_<rate>_mono.wav."
                    ),
                ),
            },
        }

    @classmethod
    def IS_CHANGED(cls, media_path, sample_rate, mono, output_dir,
                   filename="", **kwargs):
        return "|".join([
            paths.input_file_state(media_path),
            str(sample_rate), str(mono), str(output_dir), str(filename),
        ])

    def extract(self, media_path, sample_rate, mono, output_dir,
                filename=""):
        source = paths.resolve_input_path(media_path)
        rate = coerce_int(sample_rate, 16000, 1000, 192000)
        downmix = coerce_bool(mono, True)

        info = media.probe_media(source)
        if not info.get("has_audio"):
            raise ValueError(
                f"'{source.name}' has no audio stream, so there is nothing to "
                "transcribe."
            )

        stem = Path(source).stem
        default_stem = f"{stem}_{rate}{'_mono' if downmix else ''}"
        output_path = paths.resolve_output_file(
            output_dir, filename, default_stem, ".wav"
        )
        if output_path.resolve() == source.resolve():
            raise ValueError(
                "The output WAV would overwrite the input media. Choose a "
                "different output_dir or filename."
            )

        if output_path.exists():
            log(f"Overwriting existing audio file: {output_path}")

        duration_hint = float(info.get("duration") or 0.0)
        log(
            f"Extracting audio from {source.name} "
            f"({media.human_duration(duration_hint)}) -> {output_path}"
        )
        ffmpeg_utils.extract_audio(
            source,
            output_path,
            sample_rate=rate,
            mono=downmix,
            timeout=max(300.0, duration_hint * 4.0),
        )

        duration = audio.audio_duration(output_path) or duration_hint
        log(
            f"Audio ready: {output_path.name} | "
            f"{media.human_duration(duration)} | "
            f"{rate} Hz | {'mono' if downmix else 'stereo'}"
        )
        return (str(output_path), float(duration), rate)


__all__ = ["ChineseTranscribeExtractAudio"]
