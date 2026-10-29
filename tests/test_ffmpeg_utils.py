"""FFmpeg command construction and binary discovery."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _loader import load_module

config = load_module("config")
ffmpeg_utils = load_module("ffmpeg_utils")


class CommandTests(unittest.TestCase):
    def test_default_extraction_command(self):
        command = ffmpeg_utils.build_extract_command(
            "ffmpeg", "in.mp4", "out.wav", 16000, True
        )
        self.assertEqual(
            command,
            [
                "ffmpeg", "-hide_banner", "-nostdin", "-y",
                "-i", "in.mp4",
                "-map", "0:a:0", "-vn",
                "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                "out.wav",
            ],
        )

    def test_chunking_uses_input_seek_and_output_duration(self):
        command = ffmpeg_utils.build_extract_command(
            "ffmpeg", "in.mp4", "out.wav", 16000, True,
            start_s=1.5, duration_s=2.0,
        )
        self.assertLess(command.index("-ss"), command.index("-i"))
        self.assertEqual(command[command.index("-ss") + 1], "1.500")
        self.assertEqual(command[command.index("-t") + 1], "2.000")

    def test_stereo_uses_two_channels(self):
        command = ffmpeg_utils.build_extract_command(
            "ffmpeg", "in.mp4", "out.wav", 44100, False
        )
        self.assertEqual(command[command.index("-ac") + 1], "2")
        self.assertEqual(command[command.index("-ar") + 1], "44100")


class DiscoveryTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop(config.ENV_FFMPEG_BINARY, None)
        ffmpeg_utils.find_ffmpeg.cache_clear()
        ffmpeg_utils.find_ffprobe.cache_clear()

    def test_environment_override_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "ffmpeg-custom"
            fake.write_bytes(b"")
            with mock.patch.dict(
                os.environ, {config.ENV_FFMPEG_BINARY: str(fake)}
            ):
                ffmpeg_utils.find_ffmpeg.cache_clear()
                self.assertEqual(ffmpeg_utils.find_ffmpeg(), str(fake))

    def test_missing_override_is_reported(self):
        with mock.patch.dict(
            os.environ,
            {config.ENV_FFMPEG_BINARY: "C:/definitely/not/here/ffmpeg.exe"},
        ):
            ffmpeg_utils.find_ffmpeg.cache_clear()
            with self.assertRaises(ffmpeg_utils.FFmpegError):
                ffmpeg_utils.find_ffmpeg()


if __name__ == "__main__":
    unittest.main()
