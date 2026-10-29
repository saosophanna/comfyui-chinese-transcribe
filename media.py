"""Media source resolution, downloading and inspection."""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import config, ffmpeg_utils, paths
from .sanitize import to_text

# Extensions that identify media rather than, say, a web page or script.
_MEDIA_EXTENSIONS = {
    ".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".ts", ".m4v",
    ".mpg", ".mpeg", ".wmv", ".3gp", ".mts", ".m2ts", ".ogv",
    ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma",
    ".amr", ".aiff", ".aif", ".caf",
}

_CONTENT_TYPE_EXTENSIONS = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/x-matroska": ".mkv",
    "video/x-msvideo": ".avi",
    "video/mp2t": ".ts",
    "video/3gpp": ".3gp",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/flac": ".flac",
    "audio/x-flac": ".flac",
    "audio/ogg": ".ogg",
    "audio/opus": ".opus",
    "application/ogg": ".ogg",
}

_HTML_PREFIXES = (b"<!doctype html", b"<html", b"<head", b"<body", b"<?xml")


def make_media_source(source_type: str, url: str, path: str) -> dict:
    """Build the MEDIA_SOURCE value produced by the Media Input node."""
    if source_type == "url":
        text = to_text(url).strip()
        if not text:
            raise ValueError("source_type is 'url', but the url field is empty.")
        _validate_url(text)
        return {"type": "url", "url": text, "path": "", "label": text}

    text = to_text(path).strip()
    if not text:
        raise ValueError("source_type is 'file', but the path field is empty.")
    resolved = paths.resolve_input_path(text)
    return {
        "type": "file",
        "url": "",
        "path": str(resolved),
        "label": resolved.name,
    }


def source_kind(source) -> str:
    """Return ``url``/``file`` from a MEDIA_SOURCE value."""
    if not isinstance(source, dict):
        raise ValueError(
            "Expected a MEDIA_SOURCE value from the Media Input node, got "
            f"{type(source).__name__}. Reconnect the media_source input."
        )
    return to_text(source.get("type")).strip().lower()


def probe_media(path) -> dict:
    """Inspect a media file and return a JSON-friendly MEDIA_INFO dict."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Media file does not exist: {path}")

    try:
        data = ffmpeg_utils.probe_json(path)
    except ffmpeg_utils.FFprobeUnavailable:
        return _probe_with_av(path)

    return _info_from_ffprobe(path, data)


def _info_from_ffprobe(path: Path, data: dict) -> dict:
    streams = data.get("streams") or []
    fmt = data.get("format") or {}

    audio = next(
        (stream for stream in streams if stream.get("codec_type") == "audio"),
        None,
    )
    video = next(
        (
            stream
            for stream in streams
            if stream.get("codec_type") == "video"
            and not (stream.get("disposition") or {}).get("attached_pic")
        ),
        None,
    )

    duration = _to_float(fmt.get("duration"))
    if not duration:
        durations = [_to_float(stream.get("duration")) for stream in streams]
        duration = max((value for value in durations if value), default=0.0)

    size = _to_int(fmt.get("size"))
    if not size:
        try:
            size = path.stat().st_size
        except OSError:
            size = 0

    return _media_info(
        path=path,
        duration=duration,
        size_bytes=size,
        format_name=to_text(fmt.get("format_name")) or path.suffix.lstrip("."),
        format_long=to_text(fmt.get("format_long_name")),
        audio=audio,
        video=video,
        stream_count=len(streams),
    )


def _probe_with_av(path: Path) -> dict:
    """Inspect a file with PyAV when ffprobe is unavailable."""
    try:
        import av  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "ffprobe was not found and PyAV is not installed, so the media "
            "file cannot be inspected. Install FFmpeg (it includes ffprobe) "
            "and make sure it is on PATH, or set FFPROBE_BINARY."
        ) from exc

    with av.open(str(path)) as container:
        duration = 0.0
        if container.duration:
            duration = float(container.duration) / av.time_base

        audio = None
        video = None
        for stream in container.streams:
            if stream.type == "audio" and audio is None:
                audio = {
                    "codec_name": getattr(stream.codec_context, "name", ""),
                    "sample_rate": stream.rate,
                    "channels": stream.channels,
                }
            elif stream.type == "video" and video is None:
                video = {
                    "codec_name": getattr(stream.codec_context, "name", ""),
                    "width": stream.width,
                    "height": stream.height,
                }
            if not duration and stream.duration and stream.time_base:
                duration = max(duration, float(stream.duration * stream.time_base))

        try:
            size = path.stat().st_size
        except OSError:
            size = 0

        return _media_info(
            path=path,
            duration=duration,
            size_bytes=size,
            format_name=to_text(getattr(container.format, "name", ""))
            or path.suffix.lstrip("."),
            format_long="",
            audio=audio,
            video=video,
            stream_count=len(container.streams),
        )


def _media_info(*, path: Path, duration: float, size_bytes: int,
                format_name: str, format_long: str, audio, video,
                stream_count: int) -> dict:
    return {
        "path": str(path),
        "name": path.name,
        "size_bytes": int(size_bytes or 0),
        "duration": round(float(duration or 0.0), 3),
        "format": format_name or "unknown",
        "format_long": format_long or format_name or "unknown",
        "stream_count": int(stream_count),
        "has_audio": audio is not None,
        "has_video": video is not None,
        "audio_codec": to_text((audio or {}).get("codec_name")),
        "sample_rate": _to_int((audio or {}).get("sample_rate")),
        "channels": _to_int((audio or {}).get("channels")),
        "video_codec": to_text((video or {}).get("codec_name")),
        "width": _to_int((video or {}).get("width")),
        "height": _to_int((video or {}).get("height")),
    }


def summarize_media_info(info: dict) -> str:
    """One-line human summary used in logs and the Load Media output."""
    parts = [to_text(info.get("name")) or "media"]

    duration = info.get("duration") or 0
    if duration:
        parts.append(human_duration(duration))

    size = info.get("size_bytes") or 0
    if size:
        parts.append(human_size(size))

    streams = []
    if info.get("has_video"):
        codec = info.get("video_codec") or "video"
        size_text = ""
        if info.get("width") and info.get("height"):
            size_text = f" {info['width']}x{info['height']}"
        streams.append(f"{codec}{size_text}")
    if info.get("has_audio"):
        codec = info.get("audio_codec") or "audio"
        detail = ""
        if info.get("sample_rate"):
            detail += f" {info['sample_rate']} Hz"
        if info.get("channels"):
            detail += f" {info['channels']} ch"
        streams.append(f"{codec}{detail}")
    if streams:
        parts.append(" + ".join(streams))

    return " | ".join(parts)


def require_audio_stream(path, *, source: str = "") -> dict:
    """Probe a downloaded file and reject media that has no audio.

    Direct downloads of DASH/CDN links often save a video-only track. Checking
    here fails at the URL node, before the graph reaches extraction, and names
    the input URL so the user knows which link to replace.
    """
    info = probe_media(path)
    if info.get("has_audio"):
        return info

    source_text = to_text(source).strip()
    label = display_url(source_text) if source_text else ""
    location = f" from {label}" if label else ""
    name = Path(path).name

    if info.get("has_video"):
        raise ValueError(
            f"The downloaded file{location} ({name}) is a video-only track: it "
            "has no audio stream, so there is nothing to transcribe. DASH/CDN "
            "links (common with Douyin, TikTok and YouTube) keep the audio in "
            "a separate stream. Use the platform page URL with Download Media "
            "(yt-dlp) in audio mode, or a direct URL whose file includes audio."
        )

    raise ValueError(
        f"The downloaded file{location} ({name}) contains no audio or video "
        f"streams (detected format: {info.get('format') or 'unknown'}), so "
        "there is nothing to transcribe. It may be a web page, an archive or "
        "an unsupported container."
    )


def download_media(url, dest_dir, *, filename: str = "",
                   max_mb: int = config.DEFAULT_DOWNLOAD_MAX_MB,
                   timeout: int = config.DEFAULT_DOWNLOAD_TIMEOUT,
                   session=None, progress=None) -> dict:
    """Download a direct HTTP(S) media URL to *dest_dir*.

    Returns a dict with ``path``, ``bytes``, ``content_type`` and ``url``.
    HTML responses, oversized files and empty responses are rejected. The
    file is written to a temporary ``.part`` file and renamed atomically.
    """
    text = to_text(url).strip()
    _validate_url(text)
    shown = display_url(text)

    max_bytes = max(1, int(max_mb)) * 1024 * 1024
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    if session is None:
        try:
            import requests  # imported lazily so ComfyUI loads without it
        except ImportError as exc:
            raise RuntimeError(
                "The 'requests' package is missing. Install it in ComfyUI's "
                "Python environment: python -m pip install requests"
            ) from exc

        session = requests.Session()

    try:
        response = session.get(
            text,
            stream=True,
            allow_redirects=True,
            timeout=(15, max(5, int(timeout))),
            headers={"User-Agent": config.USER_AGENT, "Accept": "*/*"},
        )
    except Exception as exc:
        raise RuntimeError(f"Download failed for {shown}: {exc}") from exc
    part_path = None
    try:
        status = getattr(response, "status_code", 0)
        if status and status >= 400:
            raise RuntimeError(
                f"Download failed: HTTP {status} for {shown}. "
                "The URL may be private, expired or blocked."
            )

        headers = getattr(response, "headers", {}) or {}
        content_type = (headers.get("Content-Type") or "").split(";")[0].strip().lower()

        if content_type.startswith("text/") or content_type in {
            "application/xhtml+xml", "application/json"
        }:
            raise RuntimeError(
                f"The URL returned '{content_type}', not media. Platform pages "
                "such as YouTube or Bilibili need a direct media URL; use a "
                "downloader such as yt-dlp first."
            )

        total = _to_int(headers.get("Content-Length"))
        if total and total > max_bytes:
            raise RuntimeError(
                f"Download is {human_size(total)}, above the "
                f"{max_mb} MB limit. Raise max_download_mb or download it "
                "outside ComfyUI."
            )

        name = filename_from_response(
            getattr(response, "url", text) or text,
            headers.get("Content-Disposition", ""),
            content_type,
            filename,
        )
        dest_path = dest_dir / name
        part_path = dest_path.with_name(f".{dest_path.name}.{uuid.uuid4().hex}.part")

        written = 0
        first_chunk = b""
        with part_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                if not first_chunk:
                    first_chunk = chunk[:4096]
                    if looks_like_html(first_chunk):
                        raise RuntimeError(
                            "The URL returned an HTML page instead of a media "
                            "file. Enable cookies or use a direct media URL."
                        )
                written += len(chunk)
                if written > max_bytes:
                    raise RuntimeError(
                        f"Download exceeded the {max_mb} MB limit; aborted."
                    )
                handle.write(chunk)
                if progress is not None:
                    progress.update(len(chunk))

        if written == 0:
            raise RuntimeError(f"The URL returned an empty response: {shown}")

        os.replace(part_path, dest_path)
        part_path = None
    finally:
        if part_path is not None:
            try:
                part_path.unlink()
            except OSError:
                pass
        close = getattr(response, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    return {
        "path": str(dest_path),
        "bytes": int(written),
        "content_type": content_type or "unknown",
        "url": getattr(response, "url", text) or text,
    }


def filename_from_response(url: str, content_disposition: str,
                           content_type: str, override: str = "") -> str:
    """Pick a safe local filename for a download."""
    url = to_text(url)
    inferred = _infer_extension(content_type, url)
    given = paths.clean_optional_text(override)
    if given:
        name = paths.safe_filename(given, fallback="media")
        if not Path(name).suffix:
            name += inferred
        return name

    candidate = _content_disposition_filename(content_disposition)
    if not candidate:
        candidate = unquote(Path(urlparse(url).path).name)
    candidate = paths.safe_filename(candidate, fallback="", max_length=120)

    if not candidate or candidate == "file":
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = f"download_{stamp}{inferred}"
        return candidate

    suffix = Path(candidate).suffix.lower()
    if suffix in _MEDIA_EXTENSIONS:
        return candidate
    if suffix:
        # Drop a non-media suffix such as .php or .html.
        return Path(candidate).stem + inferred
    return candidate + inferred


def _content_disposition_filename(value: str) -> str:
    text = to_text(value)
    if not text:
        return ""
    match = re.search(r"filename\*\s*=\s*([^;]+)", text, flags=re.IGNORECASE)
    if match:
        raw = match.group(1).strip().strip('"')
        if "''" in raw:
            raw = raw.split("''", 1)[1]
        return unquote(raw)
    match = re.search(r'filename\s*=\s*"([^"]+)"', text, flags=re.IGNORECASE)
    if match:
        return unquote(match.group(1))
    match = re.search(r"filename\s*=\s*([^;]+)", text, flags=re.IGNORECASE)
    if match:
        return unquote(match.group(1).strip().strip('"'))
    return ""


def _infer_extension(content_type: str, url: str) -> str:
    if content_type in _CONTENT_TYPE_EXTENSIONS:
        return _CONTENT_TYPE_EXTENSIONS[content_type]
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in _MEDIA_EXTENSIONS:
        return suffix
    return ".bin"


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(
            f"Expected a direct http:// or https:// media URL, got '{url}'."
        )


def display_url(url: str, max_length: int = 120) -> str:
    """Strip query/fragment tokens and shorten a URL for logs and errors."""
    text = to_text(url)
    parsed = urlparse(text)
    if parsed.scheme and parsed.netloc:
        text = parsed._replace(query="", fragment="").geturl()
    if len(text) > max_length:
        text = text[: max(1, max_length - 3)] + "..."
    return text


def looks_like_html(data: bytes) -> bool:
    """True when a response body starts like a web page."""
    prefix = data.lstrip()[:512].lower()
    return any(prefix.startswith(marker) for marker in _HTML_PREFIXES)


def human_size(num_bytes: float) -> str:
    value = float(num_bytes or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def human_duration(seconds: float) -> str:
    total = max(0, int(round(float(seconds or 0))))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


__all__ = [
    "display_url",
    "download_media",
    "filename_from_response",
    "human_duration",
    "human_size",
    "looks_like_html",
    "make_media_source",
    "probe_media",
    "require_audio_stream",
    "source_kind",
    "summarize_media_info",
]
