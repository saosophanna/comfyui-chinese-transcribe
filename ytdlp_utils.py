"""yt-dlp downloader for platform pages and direct media URLs.

The normal downloader accepts direct media URLs only. Douyin, TikTok,
YouTube and Bilibili expose page URLs whose streams are often split into
separate video and audio tracks; yt-dlp resolves the page, selects both and
merges them (or extracts the audio).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import config, paths
from .media import display_url
from .sanitize import coerce_choice, to_text

MODES = ("audio", "video")
DEFAULT_MODE = "audio"

_MEDIA_SUFFIXES = {
    ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus",
    ".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".ts",
}


_DOUYIN_HOST = "douyin.com"
_DOUYIN_VIDEO_PATH = re.compile(r"^/video/\d+/?$")


class YtDlpError(RuntimeError):
    """yt-dlp is unavailable or a download failed."""


def normalize_url(url) -> str:
    """Rewrite page URLs that yt-dlp's extractors do not match directly.

    Douyin's feed modal links (``/jingxuan?modal_id=<id>``, ``/discover?...``)
    carry the video id in the query, while yt-dlp's Douyin extractor only
    matches ``https://www.douyin.com/video/<id>``. Everything else is returned
    unchanged.
    """
    text = to_text(url).strip()
    if not text:
        return text

    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if host != _DOUYIN_HOST and not host.endswith("." + _DOUYIN_HOST):
        return text
    if _DOUYIN_VIDEO_PATH.match(parsed.path):
        return text

    modal_id = (parse_qs(parsed.query).get("modal_id") or [""])[0].strip()
    if modal_id.isdigit():
        return f"https://www.douyin.com/video/{modal_id}"
    return text


def require_ytdlp():
    """Import yt-dlp or raise an actionable installation error."""
    try:
        import yt_dlp  # type: ignore

        return yt_dlp
    except Exception as exc:  # pragma: no cover - depends on the environment
        raise YtDlpError(
            "yt-dlp is not installed. Install it in the same Python "
            "environment that launches ComfyUI:\n"
            f'  "{sys.executable}" -m pip install -U yt-dlp\n'
            f"Reason: {exc}"
        ) from exc


def build_options(dest_dir, *, mode: str = DEFAULT_MODE,
                  filename: str = "", cookies_file=None) -> dict:
    """Build yt-dlp options (pure, used by the tests)."""
    mode = coerce_choice(mode, MODES, DEFAULT_MODE)
    options = {
        "paths": {"home": str(dest_dir)},
        "outtmpl": _output_template(filename),
        "noplaylist": True,
        "quiet": True,
        "noprogress": True,
        "overwrites": True,
        "windowsfilenames": True,
        "format": "bestaudio/b" if mode == "audio" else "bv*+ba/b",
    }

    if mode == "audio":
        options["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "0",
        }]
    else:
        options["merge_output_format"] = "mp4"

    if cookies_file:
        options["cookiefile"] = str(cookies_file)
    return options


def _output_template(filename: str) -> str:
    stem = paths.safe_filename(filename, fallback="")
    if stem and not stem.startswith("."):
        stem = Path(stem).stem or stem
        # A literal % would be parsed as an outtmpl field.
        stem = stem.replace("%", "_")
        return f"{stem}.%(ext)s"
    return "%(title).80s_%(id)s.%(ext)s"


def download_with_ytdlp(url, dest_dir, *, mode: str = DEFAULT_MODE,
                        filename: str = "", cookies_file=None) -> dict:
    """Download a page or media URL and return the resulting media path."""
    text = normalize_url(url)
    if not text:
        raise YtDlpError("url is empty. Paste a platform page or media URL.")

    mode = coerce_choice(mode, MODES, DEFAULT_MODE)
    yt_dlp = require_ytdlp()
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    options = build_options(
        dest_dir, mode=mode, filename=filename, cookies_file=cookies_file
    )

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(text, download=True)
            if not isinstance(info, dict):
                raise YtDlpError(
                    f"yt-dlp returned no information for {display_url(text)}."
                )

            entries = info.get("entries")
            if entries:
                entries = [entry for entry in entries if entry]
                if not entries:
                    raise YtDlpError(
                        f"yt-dlp found no downloadable entries at "
                        f"{display_url(text)}."
                    )
                info = entries[0]

            path = _resolve_output(ydl, info, dest_dir, mode)
    except YtDlpError:
        raise
    except Exception as exc:
        message = str(exc).strip()
        hint = ""
        lowered = message.lower()
        if "does not contain any stream" in lowered:
            hint = (
                " The URL is video-only (a DASH/CDN track). Use the platform "
                "page URL instead of the direct CDN link."
            )
        raise YtDlpError(
            f"yt-dlp failed for {display_url(text)}: {message}{hint}"
        ) from exc

    duration = info.get("duration")
    try:
        duration = float(duration or 0.0)
    except (TypeError, ValueError):
        duration = 0.0

    return {
        "path": str(path),
        "title": to_text(info.get("title")).strip() or path.stem,
        "duration": round(duration, 3),
        "id": to_text(info.get("id")),
        "url": to_text(info.get("webpage_url")) or text,
    }


def _resolve_output(ydl, info: dict, dest_dir: Path, mode: str) -> Path:
    candidates: list[Path] = []
    for item in info.get("requested_downloads") or []:
        if not isinstance(item, dict):
            continue
        for key in ("filepath", "_filename", "filename"):
            value = item.get(key)
            if value:
                candidates.append(Path(str(value)))

    try:
        prepared = ydl.prepare_filename(info)
        if prepared:
            candidates.append(Path(str(prepared)))
    except Exception:
        pass

    for key in ("filepath", "_filename", "filename"):
        value = info.get(key)
        if value:
            candidates.append(Path(str(value)))

    if mode == "audio":
        expanded: list[Path] = []
        for candidate in candidates:
            expanded.append(candidate)
            if candidate.suffix.lower() != ".wav":
                expanded.append(candidate.with_suffix(".wav"))
        candidates = expanded

    for candidate in candidates:
        candidate = candidate if candidate.is_absolute() else dest_dir / candidate
        if candidate.is_file():
            return candidate

    # Postprocessing can move the file, so fall back to the newest file with
    # one of the expected names.
    stems = {candidate.stem for candidate in candidates if candidate.stem}
    matches = []
    for candidate in dest_dir.iterdir():
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in _MEDIA_SUFFIXES:
            continue
        if stems and candidate.stem not in stems:
            continue
        matches.append(candidate)
    if matches:
        return max(matches, key=lambda item: item.stat().st_mtime_ns)

    raise YtDlpError(
        f"yt-dlp reported success but no media file was found in {dest_dir}."
    )


__all__ = [
    "DEFAULT_MODE",
    "MODES",
    "YtDlpError",
    "build_options",
    "download_with_ytdlp",
    "normalize_url",
    "require_ytdlp",
]
