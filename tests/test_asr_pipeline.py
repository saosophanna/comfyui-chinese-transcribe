"""FunASR orchestration with a fake funasr module (no model downloads)."""

from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from _audio import write_wav
from _loader import load_module

asr = load_module("asr")
config = load_module("config")


class FakeAutoModel:
    def __init__(self, results, recorder, **kwargs):
        self._results = results
        self._recorder = recorder
        recorder["init"].append(kwargs)

    def generate(self, **kwargs):
        self._recorder["generate"].append(kwargs)
        index = self._recorder["calls"]
        self._recorder["calls"] += 1
        return self._results[min(index, len(self._results) - 1)]


def fake_funasr(results, recorder):
    module = types.ModuleType("funasr")
    module.AutoModel = lambda **kwargs: FakeAutoModel(results, recorder, **kwargs)
    return module


def new_recorder():
    return {"init": [], "generate": [], "calls": 0}


class ParaformerTests(unittest.TestCase):
    def setUp(self):
        asr._MODELS.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.wav = Path(self.temp.name) / "speech.wav"
        write_wav(self.wav, [(2.0, 0.4, 440)])

    def tearDown(self):
        self.temp.cleanup()
        asr._MODELS.clear()

    def test_whole_file_uses_sentence_info(self):
        recorder = new_recorder()
        results = [[{
            "text": "你好。世界。",
            "sentence_info": [
                {"start": 0, "end": 500, "sentence": "你好。"},
                {"start": 500, "end": 1200, "text": "世界。"},
            ],
        }]]
        with mock.patch.dict(sys.modules, {"funasr": fake_funasr(results, recorder)}):
            result = asr.transcribe(
                self.wav, model="paraformer-zh", device="cpu"
            )

        self.assertEqual(result["text"], "你好。世界。")
        self.assertEqual(result["timing"], "sentence")
        self.assertEqual(len(result["segments"]), 2)
        self.assertEqual(result["segments"][1]["start"], 0.5)

        init = recorder["init"][0]
        self.assertEqual(init["vad_model"], "fsmn-vad")
        self.assertEqual(init["punc_model"], "ct-punc")
        self.assertEqual(init["device"], "cpu")

        generate = recorder["generate"][0]
        self.assertTrue(generate["sentence_timestamp"])
        self.assertEqual(generate["batch_size_s"], 300)

    def test_model_is_cached_between_calls(self):
        recorder = new_recorder()
        results = [[{"text": "你好。"}]]
        with mock.patch.dict(sys.modules, {"funasr": fake_funasr(results, recorder)}):
            asr.transcribe(self.wav, model="paraformer-zh", device="cpu")
            asr.transcribe(self.wav, model="paraformer-zh", device="cpu")

        self.assertEqual(len(recorder["init"]), 1)
        self.assertEqual(len(recorder["generate"]), 2)

    def test_vad_chunks_are_offset_and_removed(self):
        recorder = new_recorder()
        results = [
            [{"text": "你好。", "sentence_info": [
                {"start": 0, "end": 400, "sentence": "你好。"}
            ]}],
            [{"text": "世界。", "sentence_info": [
                {"start": 0, "end": 500, "sentence": "世界。"}
            ]}],
        ]
        with mock.patch.dict(sys.modules, {"funasr": fake_funasr(results, recorder)}):
            result = asr.transcribe(
                self.wav,
                model="paraformer-zh",
                device="cpu",
                speech_segments={"segments": [[0.0, 1.0], [1.0, 2.0]]},
            )

        self.assertEqual(result["text"], "你好。世界。")
        self.assertEqual(result["timing"], "sentence")
        self.assertEqual(result["segments"][0]["start"], 0.0)
        self.assertEqual(result["segments"][0]["end"], 0.4)
        self.assertEqual(result["segments"][1]["start"], 1.0)
        self.assertEqual(result["segments"][1]["end"], 1.5)
        self.assertEqual(result["chunks"], [])

        chunk_inputs = [Path(call["input"]) for call in recorder["generate"]]
        self.assertEqual(len(chunk_inputs), 2)
        self.assertEqual(chunk_inputs[0].name, "chunk_0001.wav")
        self.assertEqual(chunk_inputs[1].name, "chunk_0002.wav")
        for chunk in chunk_inputs:
            self.assertFalse(chunk.exists())


class SenseVoiceTests(unittest.TestCase):
    def setUp(self):
        asr._MODELS.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.wav = Path(self.temp.name) / "speech.wav"
        write_wav(self.wav, [(1.5, 0.4, 440)])

    def tearDown(self):
        self.temp.cleanup()
        asr._MODELS.clear()

    def test_constructor_and_generate_arguments(self):
        recorder = new_recorder()
        results = [[{
            "text": "<|zh|><|NEUTRAL|><|Speech|><|woitn|>你好世界"
        }]]
        with mock.patch.dict(sys.modules, {"funasr": fake_funasr(results, recorder)}):
            result = asr.transcribe(
                self.wav,
                model=config.DEFAULT_MODEL,
                device="cpu",
                language="en",
                use_itn=False,
            )

        self.assertEqual(result["text"], "你好世界")
        self.assertEqual(result["timing"], "whole")
        self.assertFalse(result["has_timestamps"])

        init = recorder["init"][0]
        self.assertEqual(init["vad_model"], "fsmn-vad")
        self.assertNotIn("punc_model", init)
        self.assertEqual(
            init["vad_kwargs"], {"max_single_segment_time": 30000}
        )

        generate = recorder["generate"][0]
        self.assertEqual(generate["language"], "en")
        self.assertFalse(generate["use_itn"])
        self.assertTrue(generate["merge_vad"])
        self.assertEqual(generate["merge_length_s"], 15)
        self.assertEqual(generate["cache"], {})


if __name__ == "__main__":
    unittest.main()
