"""URL download nodes probe the saved file before returning it."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _loader import load_module

config = load_module("config")
media = load_module("media")
nodes = load_module("nodes")

MAPPINGS = nodes.NODE_CLASS_MAPPINGS

VIDEO_ONLY = {
    "has_audio": False,
    "has_video": True,
    "format": "mov,mp4,m4a,3gp,3g2,mj2",
}
MUXED = {
    "has_audio": True,
    "has_video": True,
    "format": "mov,mp4,m4a,3gp,3g2,mj2",
}
AUDIO_ONLY = {"has_audio": True, "has_video": False, "format": "wav"}


def fake_download(name="clip.mp4"):
    """Stand-in for media.download_media that writes a real file."""

    def download(url, dest_dir, **kwargs):
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / name
        path.write_bytes(b"\0" * 64)
        return {
            "path": str(path),
            "bytes": 64,
            "content_type": "video/mp4",
            "url": url,
        }

    return download


class DownloadMediaNodeTests(unittest.TestCase):
    def test_video_only_download_is_rejected(self):
        node = MAPPINGS["ChineseTranscribeDownloadMedia"]()
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {config.ENV_OUTPUT_DIR: tmp}):
                with mock.patch.object(
                    media, "download_media", fake_download()
                ), mock.patch.object(
                    media, "probe_media", return_value=VIDEO_ONLY
                ):
                    with self.assertRaises(ValueError) as caught:
                        node.download(
                            "https://cdn.example/media-video-hvc1.mp4"
                            "?sign=secret",
                            "downloads", 10, 10,
                        )

        message = str(caught.exception)
        self.assertIn("video-only", message)
        self.assertIn("cdn.example/media-video-hvc1.mp4", message)
        self.assertNotIn("secret", message)

    def test_muxed_and_audio_only_downloads_pass(self):
        node = MAPPINGS["ChineseTranscribeDownloadMedia"]()
        for info, name in ((MUXED, "clip.mp4"), (AUDIO_ONLY, "clip.wav")):
            with self.subTest(format=info["format"]):
                with tempfile.TemporaryDirectory() as tmp:
                    with mock.patch.dict(
                        os.environ, {config.ENV_OUTPUT_DIR: tmp}
                    ):
                        with mock.patch.object(
                            media, "download_media", fake_download(name)
                        ), mock.patch.object(
                            media, "probe_media", return_value=info
                        ):
                            path, size = node.download(
                                "https://example.com/clip", "downloads", 10, 10
                            )
                    self.assertEqual(Path(path).name, name)
                    self.assertEqual(size, 64)


class ResolveMediaNodeTests(unittest.TestCase):
    def test_video_only_download_is_rejected(self):
        source = media.make_media_source(
            "url", "https://cdn.example/media-video-hvc1.mp4", ""
        )
        node = MAPPINGS["ChineseTranscribeResolveMedia"]()
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {config.ENV_OUTPUT_DIR: tmp}):
                with mock.patch.object(
                    media, "download_media", fake_download()
                ), mock.patch.object(
                    media, "probe_media", return_value=VIDEO_ONLY
                ):
                    with self.assertRaises(ValueError) as caught:
                        node.resolve(source, "downloads", 10, 10)
        self.assertIn("video-only", str(caught.exception))

    def test_muxed_download_passes(self):
        source = media.make_media_source(
            "url", "https://example.com/clip.mp4", ""
        )
        node = MAPPINGS["ChineseTranscribeResolveMedia"]()
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {config.ENV_OUTPUT_DIR: tmp}):
                with mock.patch.object(
                    media, "download_media", fake_download()
                ), mock.patch.object(
                    media, "probe_media", return_value=MUXED
                ):
                    path, kind = node.resolve(source, "downloads", 10, 10)
        self.assertEqual(kind, "url")
        self.assertEqual(Path(path).name, "clip.mp4")

    def test_local_files_bypass_the_download_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            clip = Path(tmp) / "clip.wav"
            clip.write_bytes(b"RIFF")
            source = {
                "type": "file",
                "url": "",
                "path": str(clip),
                "label": clip.name,
            }
            node = MAPPINGS["ChineseTranscribeResolveMedia"]()
            with mock.patch.object(media, "probe_media") as probe:
                path, kind = node.resolve(source, "downloads", 10, 10)
        probe.assert_not_called()
        self.assertEqual(kind, "file")
        self.assertEqual(Path(path), clip.resolve())


if __name__ == "__main__":
    unittest.main()
