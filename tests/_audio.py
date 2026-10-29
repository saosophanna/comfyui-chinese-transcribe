"""Synthetic WAV helpers for the offline tests."""

from __future__ import annotations

import math
import struct
import wave


def write_wav(path, parts, sample_rate: int = 16000) -> str:
    """Write a 16-bit mono PCM WAV.

    ``parts`` is a sequence of ``(seconds, amplitude, frequency)`` tuples.
    Amplitude is 0..1; frequency 0 produces silence.
    """
    frames = bytearray()
    for seconds, amplitude, frequency in parts:
        count = int(round(float(seconds) * sample_rate))
        for index in range(count):
            if frequency:
                value = float(amplitude) * 32767.0 * math.sin(
                    2.0 * math.pi * float(frequency) * index / sample_rate
                )
            else:
                value = 0.0
            frames += struct.pack("<h", int(max(-32768, min(32767, value))))

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(frames))
    return str(path)
