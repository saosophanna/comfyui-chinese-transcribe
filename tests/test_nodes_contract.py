"""The ComfyUI contract: registration, widget order and end-to-end files."""

from __future__ import annotations

import os
import inspect
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _audio import write_wav
from _loader import load_module

config = load_module("config")
ffmpeg_utils = load_module("ffmpeg_utils")
nodes = load_module("nodes")

MAPPINGS = nodes.NODE_CLASS_MAPPINGS
DISPLAY_NAMES = nodes.NODE_DISPLAY_NAME_MAPPINGS

EXPECTED_IDS = {
    "ChineseTranscribeMediaInput": "Media Input (URL / File)",
    "ChineseTranscribeResolveMedia": "Resolve Media",
    "ChineseTranscribeDownloadMedia": "Download Media (Direct URL)",
    "ChineseTranscribeYtDlp": "Download Media (yt-dlp)",
    "ChineseTranscribeLoadMedia": "Load Media (Probe)",
    "ChineseTranscribeExtractAudio": "FFmpeg Extract Audio",
    "ChineseTranscribeVAD": "VAD (Detect Speech)",
    "ChineseTranscribeFunASR": "FunASR Transcribe (Chinese)",
    "ChineseTranscribeFormatTranscript": "Format Transcript (TXT/JSON/SRT/VTT)",
    "ChineseTranscribeSaveTranscript": "Save Transcript",
}

EXPECTED_REQUIRED = {
    "ChineseTranscribeMediaInput": ["source_type", "url", "path"],
    "ChineseTranscribeResolveMedia": [
        "media_source", "output_dir", "max_download_mb", "timeout_seconds",
    ],
    "ChineseTranscribeDownloadMedia": [
        "url", "output_dir", "max_download_mb", "timeout_seconds",
    ],
    "ChineseTranscribeYtDlp": ["url", "mode", "output_dir", "filename"],
    "ChineseTranscribeLoadMedia": ["media_path"],
    "ChineseTranscribeExtractAudio": [
        "media_path", "sample_rate", "mono", "output_dir",
    ],
    "ChineseTranscribeVAD": [
        "audio_path", "backend", "threshold_db", "min_silence_ms",
        "min_speech_ms", "pad_ms", "max_segment_seconds", "device",
    ],
    "ChineseTranscribeFunASR": [
        "audio_path", "model", "device", "language", "use_itn",
        "batch_size_s", "max_segment_seconds",
    ],
    "ChineseTranscribeFormatTranscript": [
        "transcript", "segments", "format", "filename", "output_dir",
        "max_line_chars", "encoding",
    ],
    "ChineseTranscribeSaveTranscript": [
        "text", "filename", "extension", "output_dir", "encoding",
    ],
}

EXPECTED_OPTIONAL = {
    "ChineseTranscribeMediaInput": [],
    "ChineseTranscribeResolveMedia": ["filename"],
    "ChineseTranscribeDownloadMedia": ["filename"],
    "ChineseTranscribeYtDlp": ["cookies_file"],
    "ChineseTranscribeLoadMedia": [],
    "ChineseTranscribeExtractAudio": ["filename"],
    "ChineseTranscribeVAD": ["write_chunks", "output_dir"],
    "ChineseTranscribeFunASR": [
        "speech_segments", "hotword", "hub", "keep_chunks",
    ],
    "ChineseTranscribeFormatTranscript": [],
    "ChineseTranscribeSaveTranscript": [],
}

PRIMITIVE_TYPES = {"STRING", "INT", "FLOAT", "BOOLEAN"}


def ffmpeg_available() -> bool:
    try:
        ffmpeg_utils.find_ffmpeg()
        return True
    except Exception:
        return False


class RegistrationTests(unittest.TestCase):
    def test_classes_and_display_names(self):
        self.assertEqual(set(MAPPINGS), set(EXPECTED_IDS))
        self.assertEqual(DISPLAY_NAMES, EXPECTED_IDS)
        self.assertEqual(set(DISPLAY_NAMES), set(MAPPINGS))

    def test_node_contract(self):
        for node_id, cls in MAPPINGS.items():
            with self.subTest(node=node_id):
                self.assertEqual(cls.CATEGORY, config.CATEGORY)
                self.assertTrue(hasattr(cls, cls.FUNCTION))
                self.assertEqual(len(cls.RETURN_TYPES), len(cls.RETURN_NAMES))
                self.assertTrue(cls.DESCRIPTION)

    def test_widget_order_is_stable(self):
        for node_id, expected in EXPECTED_REQUIRED.items():
            spec = MAPPINGS[node_id].INPUT_TYPES()
            with self.subTest(node=node_id):
                self.assertEqual(list(spec.get("required", {})), expected)
                self.assertEqual(
                    list(spec.get("optional", {})),
                    EXPECTED_OPTIONAL[node_id],
                )

    def test_method_signatures_match_the_socket_names(self):
        for node_id, cls in MAPPINGS.items():
            spec = cls.INPUT_TYPES()
            expected = list(spec.get("required", {})) + list(
                spec.get("optional", {})
            )
            parameters = list(
                inspect.signature(getattr(cls, cls.FUNCTION)).parameters
            )
            with self.subTest(node=node_id):
                self.assertEqual(parameters[0], "self")
                self.assertEqual(parameters[1:], expected)

    def test_widgets_have_valid_defaults(self):
        for node_id, cls in MAPPINGS.items():
            spec = cls.INPUT_TYPES()
            for section in ("required", "optional"):
                for name, definition in spec.get(section, {}).items():
                    input_type, options = definition[0], definition[1]
                    with self.subTest(node=node_id, widget=name):
                        if isinstance(input_type, list):
                            self.assertIn(options["default"], input_type)
                        elif input_type in PRIMITIVE_TYPES:
                            self.assertIn("default", options)
                        else:
                            self.assertTrue(input_type.isupper())

    def test_input_types_are_json_serializable(self):
        # ComfyUI sends INPUT_TYPES to the frontend as JSON.
        payload = {
            node_id: cls.INPUT_TYPES() for node_id, cls in MAPPINGS.items()
        }
        json.dumps(payload)

    def test_file_writing_nodes_are_output_nodes(self):
        self.assertTrue(
            MAPPINGS["ChineseTranscribeFormatTranscript"].OUTPUT_NODE
        )
        self.assertTrue(
            MAPPINGS["ChineseTranscribeSaveTranscript"].OUTPUT_NODE
        )

    def test_file_writing_nodes_always_rerun(self):
        for node_id in (
            "ChineseTranscribeFormatTranscript",
            "ChineseTranscribeSaveTranscript",
        ):
            with self.subTest(node=node_id):
                self.assertTrue(math.isnan(MAPPINGS[node_id].IS_CHANGED()))


class IsChangedTests(unittest.TestCase):
    def test_file_nodes_include_the_file_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            clip = Path(tmp) / "clip.wav"
            write_wav(clip, [(0.2, 0.3, 440)])

            load_key = MAPPINGS["ChineseTranscribeLoadMedia"].IS_CHANGED(
                media_path=str(clip)
            )
            extract_key = MAPPINGS["ChineseTranscribeExtractAudio"].IS_CHANGED(
                media_path=str(clip),
                sample_rate="16000",
                mono=True,
                output_dir="audio",
            )
            vad_key = MAPPINGS["ChineseTranscribeVAD"].IS_CHANGED(
                audio_path=str(clip),
                backend="ffmpeg",
                threshold_db=-35.0,
                min_silence_ms=400,
                min_speech_ms=250,
                pad_ms=200,
                max_segment_seconds=30.0,
                device="cpu",
            )
            asr_key = MAPPINGS["ChineseTranscribeFunASR"].IS_CHANGED(
                audio_path=str(clip),
                model=config.DEFAULT_MODEL,
                device="auto",
                language="zh",
                use_itn=True,
                batch_size_s=300,
                max_segment_seconds=30.0,
            )

            self.assertIn(str(clip), load_key)
            self.assertIn("16000", extract_key)
            self.assertIn("ffmpeg", vad_key)
            self.assertIn(config.DEFAULT_MODEL, asr_key)


@unittest.skipUnless(ffmpeg_available(), "ffmpeg is not available")
class PipelineTests(unittest.TestCase):
    def test_file_route_through_srt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()
            output_dir.mkdir()

            wav = input_dir / "speech.wav"
            write_wav(wav, [(0.5, 0.0, 0), (1.2, 0.5, 440), (0.5, 0.0, 0)])

            environment = {
                config.ENV_INPUT_DIR: str(input_dir),
                config.ENV_OUTPUT_DIR: str(output_dir),
            }
            with mock.patch.dict(os.environ, environment):
                source, kind = MAPPINGS["ChineseTranscribeMediaInput"]().build(
                    "file", "", "speech.wav"
                )
                self.assertEqual(kind, "file")
                self.assertEqual(source["type"], "file")

                media_path, source_kind = MAPPINGS[
                    "ChineseTranscribeResolveMedia"
                ]().resolve(source, "downloads", 10, 10)
                self.assertEqual(source_kind, "file")
                self.assertEqual(Path(media_path), wav.resolve())

                loaded, info, summary = MAPPINGS[
                    "ChineseTranscribeLoadMedia"
                ]().load(media_path)
                self.assertTrue(info["has_audio"])
                self.assertIn("speech.wav", summary)

                audio_path, duration, rate = MAPPINGS[
                    "ChineseTranscribeExtractAudio"
                ]().extract(loaded, "16000", True, "audio")
                self.assertEqual(rate, 16000)
                self.assertAlmostEqual(duration, 2.2, places=1)
                self.assertTrue(Path(audio_path).is_file())

                speech_value, count, speech_seconds = MAPPINGS[
                    "ChineseTranscribeVAD"
                ]().detect(
                    audio_path, "ffmpeg", -35.0, 300, 100, 100, 30.0, "cpu"
                )
                self.assertGreaterEqual(count, 1)
                self.assertGreater(speech_seconds, 0)
                self.assertEqual(len(speech_value["segments"]), count)

                segments = {
                    "text": "你好。",
                    "segments": [{"start": 0.0, "end": 1.2, "text": "你好。"}],
                    "language": "zh",
                    "model": "paraformer-zh",
                    "duration": 2.2,
                }
                formatted, srt_path = MAPPINGS[
                    "ChineseTranscribeFormatTranscript"
                ]().format(
                    "你好。", segments, "srt", "subs", "transcripts", 42,
                    "utf-8-sig",
                )
                self.assertIn("00:00:00,000 --> 00:00:01,200", formatted)
                raw = Path(srt_path).read_bytes()
                self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
                self.assertIn("你好。", raw.decode("utf-8-sig"))
                self.assertTrue(str(Path(srt_path)).startswith(str(output_dir)))

                saved_path = MAPPINGS[
                    "ChineseTranscribeSaveTranscript"
                ]().save(
                    "你好。", "notes", "txt", "transcripts", "utf-8-sig"
                )[0]
                self.assertEqual(Path(saved_path).read_text("utf-8-sig"), "你好。")


if __name__ == "__main__":
    unittest.main()
