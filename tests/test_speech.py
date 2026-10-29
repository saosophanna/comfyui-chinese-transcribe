"""Silence parsing, region refinement and the FFmpeg VAD backend."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _audio import write_wav
from _loader import load_module

audio = load_module("audio")
ffmpeg_utils = load_module("ffmpeg_utils")
speech = load_module("speech")

SILENCEDETECT = (
    "[silencedetect @ 0x1] silence_start: 0\n"
    "[silencedetect @ 0x1] silence_end: 1.0 | silence_duration: 1.0\n"
    "[silencedetect @ 0x1] silence_start: 2.5\n"
)


def ffmpeg_available() -> bool:
    try:
        ffmpeg_utils.find_ffmpeg()
        return True
    except Exception:
        return False


class SilenceParsingTests(unittest.TestCase):
    def test_pairs_start_and_end_events(self):
        self.assertEqual(
            speech.parse_silencedetect(SILENCEDETECT, 3.0),
            [(0.0, 1.0), (2.5, 3.0)],
        )

    def test_speech_is_the_complement(self):
        self.assertEqual(
            speech.speech_from_silences(3.0, [(0.0, 1.0), (2.5, 3.0)]),
            [(1.0, 2.5)],
        )
        self.assertEqual(speech.speech_from_silences(3.0, []), [(0.0, 3.0)])

    def test_ignores_noise(self):
        self.assertEqual(speech.parse_silencedetect("not ffmpeg output", 1.0), [])


class RefineTests(unittest.TestCase):
    def test_pads_and_merges(self):
        refined = speech.refine_segments(
            [(1.0, 2.0), (2.1, 3.0)],
            min_speech_ms=250,
            pad_ms=200,
            max_segment_seconds=30,
            duration=4.0,
        )
        self.assertEqual(refined, [(0.8, 3.2)])

    def test_drops_short_bursts(self):
        self.assertEqual(
            speech.refine_segments(
                [(1.0, 1.1)], min_speech_ms=250, pad_ms=0,
                max_segment_seconds=30, duration=5.0,
            ),
            [],
        )

    def test_caps_long_regions(self):
        self.assertEqual(
            speech.cap_segments([(0.0, 10.0)], 4.0),
            [(0.0, 4.0), (4.0, 8.0), (8.0, 10.0)],
        )

    def test_normalizes_dicts_and_merges_overlaps(self):
        value = {"segments": [[0, 1], [0.5, 2], {"start": 3, "end": 4}]}
        self.assertEqual(
            speech.normalize_speech_segments(value),
            [(0.0, 2.0), (3.0, 4.0)],
        )

    def test_adjacent_regions_stay_separate(self):
        self.assertEqual(
            speech.normalize_speech_segments({"segments": [[0, 1], [1, 2]]}),
            [(0.0, 1.0), (1.0, 2.0)],
        )

    def test_rejects_non_vad_values(self):
        with self.assertRaises(ValueError):
            speech.normalize_speech_segments(42)


@unittest.skipUnless(ffmpeg_available(), "ffmpeg is not available")
class FfmpegVadTests(unittest.TestCase):
    def test_detects_a_tone_between_silences(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "tone.wav"
            write_wav(wav, [(1.0, 0.0, 0), (1.0, 0.5, 440), (1.0, 0.0, 0)])
            self.assertAlmostEqual(audio.audio_duration(wav), 3.0, places=2)

            segments = speech.ffmpeg_vad(
                wav,
                threshold_db=-30.0,
                min_silence_ms=300,
                min_speech_ms=200,
                pad_ms=100,
                max_segment_seconds=30.0,
            )

        self.assertEqual(len(segments), 1)
        start, end = segments[0]
        self.assertGreater(start, 0.7)
        self.assertLess(start, 1.2)
        self.assertGreater(end, 1.8)
        self.assertLess(end, 2.3)


if __name__ == "__main__":
    unittest.main()
