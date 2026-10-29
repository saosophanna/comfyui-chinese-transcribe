"""yt-dlp option building and download orchestration (fake module)."""

from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from _loader import load_module

ytdlp_utils = load_module("ytdlp_utils")


class FakeDownloadError(Exception):
    pass


def fake_module(*, error=None, title="测试视频", duration=93.5,
                output_name="测试视频_123.wav"):
    state = {
        "options": [],
        "error": error,
        "title": title,
        "duration": duration,
        "output_name": output_name,
    }

    class FakeYoutubeDL:
        def __init__(self, options):
            self.options = options
            state["options"].append(options)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=True):
            if state["error"] is not None:
                raise state["error"]
            home = Path(self.options["paths"]["home"])
            target = home / state["output_name"]
            target.write_bytes(b"RIFF" + b"\0" * 64)
            return {
                "id": "123",
                "title": state["title"],
                "duration": state["duration"],
                "webpage_url": url,
                "requested_downloads": [{"filepath": str(target)}],
            }

        def prepare_filename(self, info):
            return str(
                Path(self.options["paths"]["home"]) / state["output_name"]
            )

    module = types.ModuleType("yt_dlp")
    module.YoutubeDL = FakeYoutubeDL
    module.utils = types.SimpleNamespace(DownloadError=FakeDownloadError)
    return module, state


class OptionTests(unittest.TestCase):
    def test_audio_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            options = ytdlp_utils.build_options(
                tmp, mode="audio", filename="my clip",
                cookies_file="/tmp/cookies.txt",
            )
        self.assertEqual(options["format"], "bestaudio/b")
        self.assertEqual(options["outtmpl"], "my clip.%(ext)s")
        self.assertEqual(
            options["postprocessors"][0]["preferredcodec"], "wav"
        )
        self.assertEqual(options["cookiefile"], "/tmp/cookies.txt")
        self.assertTrue(options["noplaylist"])

    def test_video_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            options = ytdlp_utils.build_options(tmp, mode="video")
        self.assertEqual(options["format"], "bv*+ba/b")
        self.assertEqual(options["merge_output_format"], "mp4")
        self.assertNotIn("postprocessors", options)
        self.assertEqual(options["outtmpl"], "%(title).80s_%(id)s.%(ext)s")

    def test_literal_percent_in_filename_is_escaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            options = ytdlp_utils.build_options(tmp, filename="100% done")
        self.assertEqual(options["outtmpl"], "100_ done.%(ext)s")


class DownloadTests(unittest.TestCase):
    def test_audio_download_returns_the_wav(self):
        module, state = fake_module()
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(sys.modules, {"yt_dlp": module}):
                result = ytdlp_utils.download_with_ytdlp(
                    "https://example.com/video", tmp, mode="audio"
                )

            self.assertEqual(Path(result["path"]).name, "测试视频_123.wav")
            self.assertEqual(result["title"], "测试视频")
            self.assertEqual(result["duration"], 93.5)
            self.assertTrue(Path(result["path"]).is_file())
            self.assertEqual(len(state["options"]), 1)

    def test_video_download_returns_the_mp4(self):
        module, _ = fake_module(output_name="测试视频_123.mp4")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(sys.modules, {"yt_dlp": module}):
                result = ytdlp_utils.download_with_ytdlp(
                    "https://example.com/video", tmp, mode="video"
                )

            self.assertEqual(Path(result["path"]).suffix, ".mp4")
            self.assertTrue(Path(result["path"]).is_file())

    def test_missing_ytdlp_is_reported(self):
        with mock.patch.dict(sys.modules, {"yt_dlp": None}):
            with self.assertRaises(ytdlp_utils.YtDlpError) as caught:
                ytdlp_utils.download_with_ytdlp(
                    "https://example.com/video", tempfile.gettempdir()
                )
        self.assertIn("yt-dlp is not installed", str(caught.exception))

    def test_download_error_is_wrapped_with_a_video_only_hint(self):
        module, _ = fake_module(
            error=FakeDownloadError("Postprocessing: does not contain any stream")
        )
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(sys.modules, {"yt_dlp": module}):
                with self.assertRaises(ytdlp_utils.YtDlpError) as caught:
                    ytdlp_utils.download_with_ytdlp(
                        "https://example.com/cdn.mp4", tmp
                    )
        message = str(caught.exception)
        self.assertIn("yt-dlp failed", message)
        self.assertIn("video-only", message)


if __name__ == "__main__":
    unittest.main()
