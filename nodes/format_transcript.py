"""Format Transcript node: write TXT / JSON / SRT / VTT."""

from __future__ import annotations

from .. import config, paths
from .. import transcript as transcript_utils
from ..sanitize import (
    clean_text,
    coerce_choice,
    coerce_encoding,
    coerce_int,
)
from .common import log, write_text
from .inputs import (
    combo_input,
    encoding_input,
    int_input,
    output_dir_input,
    string_input,
)


class ChineseTranscribeFormatTranscript:
    """Turn a FunASR transcript into a subtitle or text file."""

    CATEGORY = config.CATEGORY
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("formatted_text", "output_path")
    FUNCTION = "format"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Formats the transcript and writes it under ComfyUI's output folder. "
        "SRT/VTT need timed segments: use paraformer-zh or connect the VAD "
        "node. The formatted text is also returned for preview."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "transcript": string_input(
                    "",
                    multiline=True,
                    tooltip="Connect the FunASR Transcribe transcript output.",
                ),
                "segments": (
                    config.TYPE_SEGMENTS,
                    {"tooltip": "Connect the FunASR Transcribe segments output."},
                ),
                "format": combo_input(
                    config.TRANSCRIPT_FORMATS,
                    "srt",
                    tooltip="srt/vtt need timed segments; txt/json always work.",
                ),
                "filename": string_input(
                    "transcript",
                    tooltip="File name without the extension.",
                ),
                "output_dir": output_dir_input("transcribe"),
                "max_line_chars": int_input(
                    42, 10, 200,
                    tooltip=(
                        "Maximum display width per subtitle line; CJK and "
                        "full-width characters count as 2 columns."
                    ),
                ),
                "encoding": encoding_input("utf-8-sig"),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Always rewrite: a cached save would leave no file after the user
        # deletes the previous output.
        return float("nan")

    def format(self, transcript, segments, format, filename, output_dir,
               max_line_chars, encoding):
        if not isinstance(segments, dict):
            raise ValueError(
                "segments must come from the FunASR Transcribe node. "
                "Reconnect the segments input."
            )

        fmt = coerce_choice(format, config.TRANSCRIPT_FORMATS, "srt")
        text = clean_text(transcript)
        if not text:
            text = clean_text(segments.get("text"))

        formatted = transcript_utils.format_transcript(
            fmt,
            text,
            segments,
            max_line_chars=coerce_int(max_line_chars, 42, 10, 200),
        )

        output_path = paths.resolve_output_file(
            output_dir, filename, "transcript", f".{fmt}"
        )
        chosen_encoding = coerce_encoding(encoding, config.ENCODINGS, "utf-8-sig")
        write_text(output_path, formatted, chosen_encoding)

        cue_count = len(transcript_utils.normalize_segments(segments.get("segments")))
        log(
            f"Wrote {fmt.upper()} ({cue_count} cues, {len(formatted)} chars, "
            f"{chosen_encoding}) -> {output_path}"
        )
        return (formatted, str(output_path))


__all__ = ["ChineseTranscribeFormatTranscript"]
