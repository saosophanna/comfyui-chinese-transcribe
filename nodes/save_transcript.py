"""Save Transcript node: write arbitrary text to the output folder."""

from __future__ import annotations

from .. import config, paths
from ..sanitize import coerce_choice, coerce_encoding, to_text
from .common import log, write_text
from .inputs import combo_input, encoding_input, output_dir_input, string_input

_EXTENSIONS = ("txt", "srt", "vtt", "json", "md")


class ChineseTranscribeSaveTranscript:
    """Save any text output as a UTF-8 text file."""

    CATEGORY = config.CATEGORY
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_path",)
    FUNCTION = "save"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Writes text to a file under ComfyUI's output folder. Use Format "
        "Transcript when you need proper SRT/VTT/JSON formatting; this node "
        "simply saves the text you give it."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": string_input(
                    "",
                    multiline=True,
                    tooltip="Text to save. Connect Format Transcript or any STRING output.",
                ),
                "filename": string_input(
                    "transcript",
                    tooltip="File name without the extension.",
                ),
                "extension": combo_input(
                    _EXTENSIONS,
                    "txt",
                    tooltip="Extension appended when the filename has none.",
                ),
                "output_dir": output_dir_input("transcribe"),
                "encoding": encoding_input("utf-8-sig"),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Always rewrite: a cached save would leave no file after the user
        # deletes the previous output.
        return float("nan")

    def save(self, text, filename, extension, output_dir, encoding):
        body = to_text(text)
        if not body.strip():
            raise ValueError(
                "text is empty; there is nothing to save. Check that the "
                "transcription produced a transcript."
            )

        fmt = coerce_choice(extension, _EXTENSIONS, "txt")
        output_path = paths.resolve_output_file(
            output_dir, filename, "transcript", f".{fmt}"
        )
        chosen_encoding = coerce_encoding(encoding, config.ENCODINGS, "utf-8-sig")
        write_text(output_path, body, chosen_encoding)
        log(f"Saved {len(body)} chars ({chosen_encoding}) -> {output_path}")
        return (str(output_path),)


__all__ = ["ChineseTranscribeSaveTranscript"]
