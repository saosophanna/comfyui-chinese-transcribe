"""FunASR result parsing and text joining."""

from __future__ import annotations

import unittest

from _loader import load_module

asr = load_module("asr")
config = load_module("config")


class CleanTextTests(unittest.TestCase):
    def test_sensevoice_tags_are_removed(self):
        text = asr.clean_asr_text(
            "<|zh|><|NEUTRAL|><|Speech|><|woitn|>你好世界",
            config.DEFAULT_MODEL,
        )
        self.assertEqual(text, "你好世界")

    def test_empty_text(self):
        self.assertEqual(asr.clean_asr_text("", config.DEFAULT_MODEL), "")


class ParseResultTests(unittest.TestCase):
    def test_whole_file_fallback_uses_the_duration(self):
        text, segments, timing = asr.parse_result(
            [{"text": "你好世界"}],
            model_id=config.DEFAULT_MODEL,
            fallback_end=2.5,
        )
        self.assertEqual(text, "你好世界")
        self.assertEqual(timing, "whole")
        self.assertEqual(
            segments,
            [{"start": 0.0, "end": 2.5, "text": "你好世界"}],
        )

    def test_sentence_info_is_used_and_offset(self):
        result = [{
            "text": "你好。世界。",
            "sentence_info": [
                {"start": 0, "end": 500, "sentence": "你好。"},
                {"start": 500, "end": 1200, "text": "世界。"},
            ],
        }]
        text, segments, timing = asr.parse_result(
            result, model_id="paraformer-zh", offset=10.0
        )
        self.assertEqual(timing, "sentence")
        self.assertEqual(text, "你好。世界。")
        self.assertEqual(segments[0]["start"], 10.0)
        self.assertEqual(segments[0]["end"], 10.5)
        self.assertEqual(segments[1]["start"], 10.5)
        self.assertEqual(segments[1]["end"], 11.2)

    def test_sentence_info_timestamp_field_is_supported(self):
        result = [{
            "sentence_info": [{
                "text": "你好",
                "timestamp": [[100, 300], [300, 900]],
            }],
        }]
        _, segments, timing = asr.parse_result(
            result, model_id="paraformer-zh"
        )
        self.assertEqual(timing, "sentence")
        self.assertEqual(segments, [{"start": 0.1, "end": 0.9, "text": "你好"}])

    def test_character_timestamps_are_grouped(self):
        result = [{
            "text": "你好。世界。",
            "timestamp": [[0, 200], [200, 400], [400, 700], [700, 900]],
        }]
        _, segments, timing = asr.parse_result(
            result, model_id="paraformer-zh"
        )
        self.assertEqual(timing, "sentence")
        self.assertEqual([cue["text"] for cue in segments], ["你好。", "世界。"])

    def test_empty_result_raises(self):
        with self.assertRaises(RuntimeError):
            asr.parse_result(
                [{"text": ""}], model_id=config.DEFAULT_MODEL
            )
        with self.assertRaises(RuntimeError):
            asr.parse_result([], model_id=config.DEFAULT_MODEL)


class JoinTests(unittest.TestCase):
    def test_chinese_is_joined_without_spaces(self):
        self.assertEqual(asr.join_texts(["你好", "世界"], "zh"), "你好世界")
        self.assertEqual(asr.join_texts(["你好", "世界"], "yue"), "你好世界")
        self.assertEqual(asr.join_texts(["今日は", "晴れ"], "ja"), "今日は晴れ")

    def test_spaced_languages(self):
        self.assertEqual(asr.join_texts(["Hello", "world"], "en"), "Hello world")
        self.assertEqual(asr.join_texts(["안녕", "하세요"], "ko"), "안녕 하세요")

    def test_auto_detects_cjk(self):
        self.assertEqual(asr.join_texts(["你好", "世界"], "auto"), "你好世界")
        self.assertEqual(asr.join_texts(["Hello", "world"], "auto"), "Hello world")

    def test_empty_parts_are_dropped(self):
        self.assertEqual(asr.join_texts(["", "   ", None], "zh"), "")


if __name__ == "__main__":
    unittest.main()
