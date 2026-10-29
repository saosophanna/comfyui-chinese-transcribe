"""Path resolution, filename safety and output layout."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _loader import load_module

config = load_module("config")
paths = load_module("paths")


class SafeFilenameTests(unittest.TestCase):
    def test_replaces_illegal_characters(self):
        self.assertEqual(
            paths.safe_filename('a<b>c:d"e/f\\g|h?i*j'), "a_b_c_d_e_f_g_h_i_j"
        )

    def test_keeps_cjk_and_spaces(self):
        self.assertEqual(paths.safe_filename("中文 字幕.srt"), "中文 字幕.srt")

    def test_empty_uses_fallback(self):
        self.assertEqual(paths.safe_filename("   ", fallback="transcript"), "transcript")
        self.assertEqual(paths.safe_filename("...", fallback="transcript"), "transcript")

    def test_reserved_windows_names_are_prefixed(self):
        self.assertEqual(paths.safe_filename("CON.txt"), "_CON.txt")
        self.assertEqual(paths.safe_filename("LPT1"), "_LPT1")

    def test_long_names_keep_the_extension(self):
        name = paths.safe_filename("字" * 300 + ".srt")
        self.assertLessEqual(len(name), 120)
        self.assertTrue(name.endswith(".srt"))


class ExtensionTests(unittest.TestCase):
    def test_known_extension_is_replaced(self):
        self.assertEqual(paths.with_extension("clip.mp4", ".wav"), "clip.wav")

    def test_same_extension_is_kept(self):
        self.assertEqual(paths.with_extension("clip.wav", "wav"), "clip.wav")

    def test_unknown_suffix_is_kept(self):
        self.assertEqual(paths.with_extension("subs.en", ".srt"), "subs.en.srt")

    def test_missing_suffix_is_appended(self):
        self.assertEqual(paths.with_extension("transcript", ".srt"), "transcript.srt")


class OutputDirTests(unittest.TestCase):
    def test_relative_dir_stays_under_output_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {config.ENV_OUTPUT_DIR: tmp}):
                resolved = paths.resolve_output_dir("transcribe/audio")
                self.assertEqual(resolved, Path(tmp) / "transcribe" / "audio")

    def test_empty_uses_default_subdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {config.ENV_OUTPUT_DIR: tmp}):
                self.assertEqual(
                    paths.resolve_output_dir(""),
                    Path(tmp) / config.DEFAULT_OUTPUT_SUBDIR,
                )

    def test_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {config.ENV_OUTPUT_DIR: tmp}):
                with self.assertRaises(ValueError):
                    paths.resolve_output_dir("../escape")

    def test_absolute_dir_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            absolute = Path(tmp) / "elsewhere"
            self.assertEqual(
                paths.resolve_output_dir(str(absolute)), absolute
            )

    def test_output_file_is_created_in_named_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {config.ENV_OUTPUT_DIR: tmp}):
                path = paths.resolve_output_file(
                    "sub", "subs.en", "transcript", ".srt"
                )
                self.assertEqual(path, Path(tmp) / "sub" / "subs.en.srt")
                self.assertTrue(path.parent.is_dir())


class InputPathTests(unittest.TestCase):
    def test_relative_path_is_found_in_input_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            clip = Path(tmp) / "clip.wav"
            clip.write_bytes(b"x")
            with mock.patch.dict(os.environ, {config.ENV_INPUT_DIR: tmp}):
                self.assertEqual(paths.resolve_input_path("clip.wav"), clip.resolve())

    def test_absolute_path_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            clip = Path(tmp) / "clip.wav"
            clip.write_bytes(b"x")
            self.assertEqual(paths.resolve_input_path(str(clip)), clip.resolve())

    def test_missing_file_lists_search_locations(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {config.ENV_INPUT_DIR: tmp}):
                with self.assertRaises(ValueError) as caught:
                    paths.resolve_input_path("missing.wav")
                self.assertIn("Looked in", str(caught.exception))

    def test_empty_path_is_rejected(self):
        with self.assertRaises(ValueError):
            paths.resolve_input_path("   ")

    def test_file_state_changes_with_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            clip = Path(tmp) / "clip.wav"
            clip.write_bytes(b"x")
            first = paths.file_state(clip)
            clip.write_bytes(b"xy")
            second = paths.file_state(clip)
            self.assertNotEqual(first, second)
            self.assertEqual(paths.file_state(Path(tmp) / "missing"), "missing")


if __name__ == "__main__":
    unittest.main()
