"""Download Media node: direct URL to a local media file."""

from __future__ import annotations

from .. import config, media, paths
from ..sanitize import coerce_int, to_text
from .common import log
from .inputs import int_input, output_dir_input, string_input


class ChineseTranscribeDownloadMedia:
    """Download one direct HTTP(S) media URL into ComfyUI's output folder."""

    CATEGORY = config.CATEGORY
    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("media_path", "bytes")
    FUNCTION = "download"
    DESCRIPTION = (
        "Download a direct media URL (mp4, mkv, webm, mp3, wav, m4a, ...). "
        "Web pages from YouTube, Bilibili and similar sites are not media "
        "URLs; download those with yt-dlp first. HTML responses and oversized "
        "files are rejected."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": string_input(
                    "",
                    tooltip="Direct http(s) media URL, not a video-site page.",
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
                        "Optional local filename. Empty derives one from the URL "
                        "or Content-Disposition header."
                    ),
                ),
            },
        }

    def download(self, url, output_dir, max_download_mb, timeout_seconds,
                 filename=""):
        text = to_text(url).strip()
        if not text:
            raise ValueError("url is empty. Enter a direct http(s) media URL.")

        destination = paths.resolve_output_dir(output_dir)
        log(f"Downloading {media.display_url(text)}")
        result = media.download_media(
            text,
            destination,
            filename=filename,
            max_mb=coerce_int(max_download_mb, config.DEFAULT_DOWNLOAD_MAX_MB, 1),
            timeout=coerce_int(timeout_seconds, config.DEFAULT_DOWNLOAD_TIMEOUT, 5),
        )
        log(
            f"Saved {media.human_size(result['bytes'])} to {result['path']} "
            f"({result['content_type']})"
        )
        return (result["path"], int(result["bytes"]))


__all__ = ["ChineseTranscribeDownloadMedia"]
