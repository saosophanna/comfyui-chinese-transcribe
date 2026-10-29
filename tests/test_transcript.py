"""Transcript grouping and TXT/JSON/SRT/VTT formatting."""

from __future__ import annotations

import json
import unicodedata
import unittest

from _loader import load_module

transcript = load_module("transcript")

SEGMENTS = [
    {"start": 0.0, "end": 1.5, "text": "你好。"},
    {"start": 1.5, "end": 3.25, "text": "世界。"},
]


def display_width(text: str) -> int:
    return sum(
        2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        for char in text
    )


class TimestampTests(unittest.TestCase):
    def test_srt_and_vtt_timestamps(self):
        self.assertEqual(transcript.format_timestamp(0), "00:00:00,000")
        self.assertEqual(transcript.format_timestamp(3661.234), "01:01:01,234")
        self.assertEqual(
            transcript.format_timestamp(1.5, separator="."), "00:00:01.500"
        )

    def test_negative_times_are_clamped(self):
        self.assertEqual(transcript.format_timestamp(-2.0), "00:00:00,000")


class SrtTests(unittest.TestCase):
    def test_formats_cues(self):
        expected = (
            "1\n"
            "00:00:00,000 --> 00:00:01,500\n"
            "你好。\n"
            "\n"
            "2\n"
            "00:00:01,500 --> 00:00:03,250\n"
            "世界。\n"
        )
        self.assertEqual(transcript.format_srt(SEGMENTS), expected)

    def test_wraps_long_cue_text(self):
        long_text = "这是一段很长的中文字幕文本，用来测试自动换行功能是否正常工作。"
        output = transcript.format_srt(
            [{"start": 0, "end": 5, "text": long_text}], max_line_chars=12
        )
        body = output.split("\n", 2)[2].strip()
        for line in body.splitlines():
            self.assertLessEqual(display_width(line), 12)

    def test_cjk_counts_as_two_columns(self):
        text = "中文" * 15
        wrapped = transcript.wrap_cue_text(text, 20)
        for line in wrapped.splitlines():
            self.assertLessEqual(display_width(line), 20)

    def test_empty_segments_raise_a_helpful_error(self):
        with self.assertRaises(ValueError) as caught:
            transcript.format_srt([])
        self.assertIn("paraformer-zh", str(caught.exception))


class VttTests(unittest.TestCase):
    def test_header_and_dot_timestamps(self):
        output = transcript.format_vtt(SEGMENTS)
        self.assertTrue(output.startswith("WEBVTT\n\n"))
        self.assertIn("00:00:00.000 --> 00:00:01.500", output)
        self.assertNotIn("00:00:00,000", output)

    def test_empty_segments_raise(self):
        with self.assertRaises(ValueError):
            transcript.format_vtt([])


class TxtJsonTests(unittest.TestCase):
    def test_txt_uses_text_then_segments(self):
        self.assertEqual(transcript.format_txt("", SEGMENTS), "你好。\n世界。\n")
        self.assertEqual(transcript.format_txt("一次转录。", []), "一次转录。\n")

    def test_json_round_trips_unicode(self):
        data = {
            "language": "zh",
            "model": "paraformer-zh",
            "duration": 3.25,
            "segments": SEGMENTS,
        }
        payload = json.loads(transcript.format_json("你好。世界。", data))
        self.assertEqual(payload["text"], "你好。世界。")
        self.assertEqual(payload["language"], "zh")
        self.assertEqual(len(payload["segments"]), 2)
        self.assertEqual(payload["segments"][1]["text"], "世界。")

    def test_dispatch(self):
        data = {"segments": SEGMENTS}
        self.assertTrue(
            transcript.format_transcript("srt", "", data).startswith("1\n")
        )
        self.assertIn("WEBVTT", transcript.format_transcript("vtt", "", data))
        self.assertEqual(transcript.format_transcript("txt", "", data), "你好。\n世界。\n")
        with self.assertRaises(ValueError):
            transcript.format_transcript("docx", "", data)


class NormalizeTests(unittest.TestCase):
    def test_skips_empty_and_repairs_short_cues(self):
        cues = transcript.normalize_segments([
            {"start": 1, "end": 1, "text": "a"},
            {"start": 2, "end": 3, "text": "   "},
            {"start": 4, "end": 5, "sentence": "b"},
            (6, 7, "c"),
            "not a cue",
        ])
        self.assertEqual([cue["text"] for cue in cues], ["a", "b", "c"])
        self.assertGreater(cues[0]["end"], cues[0]["start"])


class CharTimestampTests(unittest.TestCase):
    def test_groups_chinese_sentences(self):
        text = "你好。世界。"
        timestamps = [[0, 200], [200, 400], [400, 700], [700, 900]]
        cues = transcript.group_char_timestamps(text, timestamps)
        self.assertEqual(
            cues,
            [
                {"start": 0.0, "end": 0.4, "text": "你好。"},
                {"start": 0.4, "end": 0.9, "text": "世界。"},
            ],
        )

    def test_applies_offset(self):
        cues = transcript.group_char_timestamps(
            "你好。世界。",
            [[0, 200], [200, 400], [400, 700], [700, 900]],
            offset_s=10.0,
        )
        self.assertEqual(cues[0]["start"], 10.0)
        self.assertEqual(cues[1]["start"], 10.4)

    def test_direct_alignment_when_counts_match(self):
        cues = transcript.group_char_timestamps(
            "AB", [[0, 100], [100, 250]]
        )
        self.assertEqual(cues, [{"start": 0.0, "end": 0.25, "text": "AB"}])

    def test_mismatch_returns_none(self):
        self.assertIsNone(
            transcript.group_char_timestamps("你好", [[0, 100]])
        )
        self.assertIsNone(transcript.group_char_timestamps("", [[0, 100]]))


if __name__ == "__main__":
    unittest.main()
