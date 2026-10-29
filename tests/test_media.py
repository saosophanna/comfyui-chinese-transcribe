"""Downloading, filenames and media-info summaries."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _loader import load_module

media = load_module("media")


class FakeResponse:
    def __init__(self, chunks, headers, status_code=200,
                 url="https://example.com/final/file"):
        self._chunks = list(chunks)
        self.headers = headers
        self.status_code = status_code
        self.url = url
        self.closed = False

    def iter_content(self, chunk_size=1):
        yield from self._chunks

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.requested = None
        self.kwargs = None

    def get(self, url, **kwargs):
        self.requested = url
        self.kwargs = kwargs
        return self.response


class FilenameTests(unittest.TestCase):
    def test_url_basename_is_used(self):
        self.assertEqual(
            media.filename_from_response(
                "https://example.com/a/b.mp4", "", "video/mp4"
            ),
            "b.mp4",
        )

    def test_content_disposition_wins(self):
        self.assertEqual(
            media.filename_from_response(
                "https://example.com/x",
                'attachment; filename="clip.mkv"',
                "video/x-matroska",
            ),
            "clip.mkv",
        )

    def test_utf8_content_disposition(self):
        self.assertEqual(
            media.filename_from_response(
                "https://example.com/x",
                "attachment; filename*=UTF-8''%E4%B8%AD%E6%96%87.mp4",
                "video/mp4",
            ),
            "中文.mp4",
        )

    def test_content_type_adds_extension(self):
        self.assertEqual(
            media.filename_from_response(
                "https://example.com/watch", "", "audio/wav"
            ),
            "watch.wav",
        )

    def test_non_media_suffix_is_replaced(self):
        self.assertEqual(
            media.filename_from_response(
                "https://example.com/watch.php", "", "video/mp4"
            ),
            "watch.mp4",
        )

    def test_override_without_suffix_gets_one(self):
        self.assertEqual(
            media.filename_from_response(
                "https://example.com/x", "", "audio/mpeg", "我的 音频"
            ),
            "我的 音频.mp3",
        )


class DownloadTests(unittest.TestCase):
    def test_streams_to_the_named_file(self):
        response = FakeResponse(
            [b"RIFF", b"1234"],
            {
                "Content-Type": "audio/wav",
                "Content-Length": "8",
                "Content-Disposition": 'attachment; filename="clip.wav"',
            },
        )
        session = FakeSession(response)

        with tempfile.TemporaryDirectory() as tmp:
            result = media.download_media(
                "https://example.com/clip", tmp, session=session, max_mb=1
            )
            path = Path(result["path"])
            self.assertEqual(path.read_bytes(), b"RIFF1234")
            self.assertEqual(result["bytes"], 8)
            self.assertEqual(path.name, "clip.wav")
            self.assertFalse(list(Path(tmp).glob("*.part")))
        self.assertTrue(response.closed)

    def test_html_content_type_is_rejected(self):
        session = FakeSession(FakeResponse(
            [b"<html>"], {"Content-Type": "text/html; charset=utf-8"}
        ))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError) as caught:
                media.download_media("https://example.com/page", tmp,
                                     session=session, max_mb=1)
            self.assertIn("not media", str(caught.exception))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_html_body_is_sniffed(self):
        session = FakeSession(FakeResponse(
            [b"  <!DOCTYPE html><html>"], {"Content-Type": "application/octet-stream"}
        ))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                media.download_media("https://example.com/page", tmp,
                                     session=session, max_mb=1)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_size_limit_is_enforced_before_and_during_download(self):
        session = FakeSession(FakeResponse(
            [], {"Content-Type": "video/mp4", "Content-Length": str(2 * 1024 * 1024)}
        ))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError) as caught:
                media.download_media("https://example.com/big", tmp,
                                     session=session, max_mb=1)
            self.assertIn("limit", str(caught.exception))

        session = FakeSession(FakeResponse(
            [b"x" * 1024 * 1024, b"x" * 1024 * 1024],
            {"Content-Type": "video/mp4"},
        ))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                media.download_media("https://example.com/big", tmp,
                                     session=session, max_mb=1)

    def test_http_error_is_reported(self):
        session = FakeSession(FakeResponse(
            [], {"Content-Type": "video/mp4"}, status_code=403
        ))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError) as caught:
                media.download_media("https://example.com/x", tmp,
                                     session=session, max_mb=1)
            self.assertIn("403", str(caught.exception))


class AudioGuardTests(unittest.TestCase):
    def test_video_only_download_is_rejected(self):
        info = {
            "has_audio": False,
            "has_video": True,
            "format": "mov,mp4,m4a,3gp,3g2,mj2",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media-video-hvc1.mp4"
            path.write_bytes(b"\0" * 32)
            with mock.patch.object(media, "probe_media", return_value=info):
                with self.assertRaises(ValueError) as caught:
                    media.require_audio_stream(
                        path, source="https://cdn.example/v.mp4?sign=secret"
                    )

        message = str(caught.exception)
        self.assertIn("video-only", message)
        self.assertIn("https://cdn.example/v.mp4", message)
        self.assertNotIn("sign=secret", message)
        self.assertIn("Download Media (yt-dlp)", message)

    def test_audio_stream_is_returned_unchanged(self):
        info = {"has_audio": True, "has_video": False, "format": "wav"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clip.wav"
            path.write_bytes(b"RIFF")
            with mock.patch.object(media, "probe_media", return_value=info):
                self.assertIs(
                    media.require_audio_stream(
                        path, source="https://example.com/clip.wav"
                    ),
                    info,
                )

    def test_container_without_av_streams_is_rejected(self):
        info = {"has_audio": False, "has_video": False, "format": "data"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "download.bin"
            path.write_bytes(b"\0" * 32)
            with mock.patch.object(media, "probe_media", return_value=info):
                with self.assertRaises(ValueError) as caught:
                    media.require_audio_stream(
                        path, source="https://example.com/download.bin"
                    )
        self.assertIn("no audio or video streams", str(caught.exception))


class SummaryTests(unittest.TestCase):
    def test_human_units(self):
        self.assertEqual(media.human_size(512), "512 B")
        self.assertEqual(media.human_size(1024 * 1024 * 5), "5.0 MB")
        self.assertEqual(media.human_duration(83.4), "01:23")
        self.assertEqual(media.human_duration(3725), "1:02:05")

    def test_display_url_hides_query_tokens(self):
        self.assertEqual(
            media.display_url(
                "https://example.com/v.mp4?token=secret&expires=1#frag"
            ),
            "https://example.com/v.mp4",
        )
        shortened = media.display_url("https://example.com/" + "a" * 300)
        self.assertLessEqual(len(shortened), 120)
        self.assertTrue(shortened.endswith("..."))

    def test_summary_lists_streams(self):
        info = {
            "name": "a.mp4",
            "duration": 83.4,
            "size_bytes": 1024 * 1024 * 5,
            "has_video": True,
            "video_codec": "h264",
            "width": 1920,
            "height": 1080,
            "has_audio": True,
            "audio_codec": "aac",
            "sample_rate": 48000,
            "channels": 2,
        }
        self.assertEqual(
            media.summarize_media_info(info),
            "a.mp4 | 01:23 | 5.0 MB | h264 1920x1080 + aac 48000 Hz 2 ch",
        )


if __name__ == "__main__":
    unittest.main()
