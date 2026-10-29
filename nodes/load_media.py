"""Load Media node: validate and probe a media file."""

from __future__ import annotations

from .. import config, media, paths
from .common import log
from .inputs import string_input


class ChineseTranscribeLoadMedia:
    """Probe a media file's duration, streams and codecs."""

    CATEGORY = config.CATEGORY
    RETURN_TYPES = ("STRING", config.TYPE_MEDIA_INFO, "STRING")
    RETURN_NAMES = ("media_path", "media_info", "summary")
    FUNCTION = "load"
    DESCRIPTION = (
        "Validates a media path and reads its duration and audio/video "
        "streams with ffprobe (PyAV is the fallback). This is the convergence "
        "point after Resolve Media or Download Media."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "media_path": string_input(
                    "",
                    tooltip=(
                        "Path to a video or audio file. Relative names are "
                        "looked up in ComfyUI/input."
                    ),
                ),
            },
        }

    @classmethod
    def IS_CHANGED(cls, media_path, **kwargs):
        return paths.input_file_state(media_path)

    def load(self, media_path):
        path = paths.resolve_input_path(media_path)
        info = media.probe_media(path)
        summary = media.summarize_media_info(info)

        if not info.get("has_audio") and not info.get("has_video"):
            raise ValueError(
                f"'{path.name}' contains no audio or video streams "
                f"(detected format: {info.get('format')}). It may be a web "
                "page, an archive, or an unsupported container."
            )

        log(f"Loaded {summary}")
        if not info.get("has_audio"):
            log(
                "Warning: this file has no audio stream; FFmpeg Extract Audio "
                "will fail. Video-only DASH/CDN downloads often omit audio; "
                "use yt-dlp to fetch a muxed file or the audio track."
            )
        return (str(path), info, summary)


__all__ = ["ChineseTranscribeLoadMedia"]
