"""Download Media (yt-dlp) node."""

from __future__ import annotations

from pathlib import Path

from .. import config, paths, ytdlp_utils
from ..media import display_url, human_size
from ..sanitize import coerce_choice, to_text
from .common import log
from .inputs import combo_input, output_dir_input, string_input


class ChineseTranscribeYtDlp:
    """Download a platform page or media URL with yt-dlp."""

    CATEGORY = config.CATEGORY
    RETURN_TYPES = ("STRING", "STRING", "FLOAT")
    RETURN_NAMES = ("media_path", "title", "duration")
    FUNCTION = "download"
    DESCRIPTION = (
        "yt-dlp downloader for platform pages (Douyin, TikTok, YouTube, "
        "Bilibili, ...) and direct media URLs. Audio mode downloads the best "
        "audio and converts it to WAV; video mode merges the best video and "
        "audio tracks to MP4. Use the page URL, not a video-only CDN link."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": string_input(
                    "",
                    tooltip=(
                        "Platform page URL (douyin.com/video/..., "
                        "youtube.com/watch?v=..., bilibili.com/video/...) or "
                        "a direct media URL."
                    ),
                ),
                "mode": combo_input(
                    ytdlp_utils.MODES,
                    ytdlp_utils.DEFAULT_MODE,
                    tooltip=(
                        "audio = best audio track converted to WAV (recommended "
                        "for transcription); video = best video + audio merged "
                        "to MP4."
                    ),
                ),
                "output_dir": output_dir_input("transcribe/downloads"),
                "filename": string_input(
                    "",
                    tooltip=(
                        "Optional output stem. Empty uses the video title and "
                        "id; the extension is chosen by yt-dlp."
                    ),
                ),
            },
            "optional": {
                "cookies_file": string_input(
                    "",
                    tooltip=(
                        "Optional Netscape cookies.txt for login/region-locked "
                        "pages. Relative names are resolved in ComfyUI/input. "
                        "The file may contain account cookies; do not share it."
                    ),
                ),
            },
        }

    def download(self, url, mode, output_dir, filename="", cookies_file=""):
        text = to_text(url).strip()
        if not text:
            raise ValueError(
                "url is empty. Paste the platform page URL (not a video-only "
                "CDN link) or a direct media URL."
            )

        mode_choice = coerce_choice(
            mode, ytdlp_utils.MODES, ytdlp_utils.DEFAULT_MODE
        )
        destination = paths.resolve_output_dir(output_dir)

        cookies_path = None
        cookies_text = to_text(cookies_file).strip()
        if cookies_text:
            cookies_path = paths.resolve_input_path(cookies_text)

        log(f"yt-dlp: downloading {display_url(text)} ({mode_choice}) ...")
        result = ytdlp_utils.download_with_ytdlp(
            text,
            destination,
            mode=mode_choice,
            filename=filename,
            cookies_file=cookies_path,
        )

        path = Path(result["path"])
        try:
            size = human_size(path.stat().st_size)
        except OSError:
            size = "unknown size"
        log(
            f"yt-dlp saved {path.name} ({size}, {result['title']}, "
            f"{result['duration']:.1f}s) -> {path}"
        )
        return (str(path), result["title"], float(result["duration"]))


__all__ = ["ChineseTranscribeYtDlp"]
