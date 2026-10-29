"""Media Input node: choose a direct URL or a local file."""

from __future__ import annotations

from .. import config
from ..media import display_url, make_media_source
from ..sanitize import coerce_choice
from .common import log
from .inputs import combo_input, string_input


class ChineseTranscribeMediaInput:
    """Declare one media source, either a direct URL or a local path."""

    CATEGORY = config.CATEGORY
    RETURN_TYPES = (config.TYPE_MEDIA_SOURCE, "STRING")
    RETURN_NAMES = ("media_source", "source_type")
    FUNCTION = "build"
    DESCRIPTION = (
        "Media source for the transcription pipeline. Set source_type to "
        "'url' for a direct http(s) media link, or 'file' for a local video "
        "or audio path. Local paths are resolved against ComfyUI's input "
        "directory."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "source_type": combo_input(
                    config.SOURCE_TYPES,
                    config.DEFAULT_SOURCE_TYPE,
                    tooltip=(
                        "file = path on this machine; url = direct media URL. "
                        "Video-site pages need yt-dlp first."
                    ),
                ),
                "url": string_input(
                    "",
                    tooltip="Direct http(s) media URL. Used only when source_type is 'url'.",
                ),
                "path": string_input(
                    "",
                    tooltip=(
                        "Local media path. Used only when source_type is 'file'. "
                        "Relative names are looked up in ComfyUI/input."
                    ),
                ),
            },
        }

    def build(self, source_type, url, path):
        kind = coerce_choice(
            source_type, config.SOURCE_TYPES, config.DEFAULT_SOURCE_TYPE
        )
        source = make_media_source(kind, url, path)

        label = display_url(source["label"])
        if len(label) > 140:
            label = label[:137] + "..."
        log(f"Media input ({kind}): {label}")
        return (source, kind)


__all__ = ["ChineseTranscribeMediaInput"]
