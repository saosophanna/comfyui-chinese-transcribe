"""Resolve Media node: conditional download-or-validate routing."""

from __future__ import annotations

from .. import config, media, paths
from ..sanitize import coerce_int, to_text
from .common import log
from .inputs import int_input, output_dir_input, string_input


class ChineseTranscribeResolveMedia:
    """Send URLs through the downloader and local files straight through."""

    CATEGORY = config.CATEGORY
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("media_path", "source_kind")
    FUNCTION = "resolve"
    DESCRIPTION = (
        "Conditional router for a MEDIA_SOURCE. A URL is downloaded to the "
        "output folder; a local path is validated. Both routes return one "
        "media file path, so the rest of the graph has a single flow."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "media_source": (
                    config.TYPE_MEDIA_SOURCE,
                    {"tooltip": "Connect the Media Input node here."},
                ),
                "output_dir": output_dir_input("transcribe/downloads"),
                "max_download_mb": int_input(
                    config.DEFAULT_DOWNLOAD_MAX_MB, 1, 20480,
                    tooltip="Abort downloads larger than this size.",
                ),
                "timeout_seconds": int_input(
                    config.DEFAULT_DOWNLOAD_TIMEOUT, 5, 3600,
                    tooltip="Per-read network timeout in seconds.",
                ),
            },
            "optional": {
                "filename": string_input(
                    "",
                    tooltip=(
                        "Optional download filename. Empty derives one from the "
                        "URL or Content-Disposition header."
                    ),
                ),
            },
        }

    def resolve(self, media_source, output_dir, max_download_mb,
                timeout_seconds, filename=""):
        kind = media.source_kind(media_source)

        if kind == "url":
            url = to_text(media_source.get("url")).strip()
            if not url:
                raise ValueError("MEDIA_SOURCE has no URL. Reconnect Media Input.")
            destination = paths.resolve_output_dir(output_dir)
            result = media.download_media(
                url,
                destination,
                filename=filename,
                max_mb=coerce_int(max_download_mb, config.DEFAULT_DOWNLOAD_MAX_MB, 1),
                timeout=coerce_int(timeout_seconds, config.DEFAULT_DOWNLOAD_TIMEOUT, 5),
            )
            log(
                f"Resolved URL -> {result['path']} "
                f"({media.human_size(result['bytes'])})"
            )
            return (result["path"], "url")

        if kind != "file":
            raise ValueError(
                "MEDIA_SOURCE has an unknown type. Reconnect the Media Input "
                "node and pick 'file' or 'url'."
            )

        path_text = to_text(media_source.get("path")).strip()
        path = paths.resolve_input_path(path_text)
        log(f"Resolved local file -> {path}")
        return (str(path), "file")


__all__ = ["ChineseTranscribeResolveMedia"]
