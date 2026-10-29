"""Package-wide constants shared by the nodes, media helpers and ASR layer."""

from __future__ import annotations

VERSION = "0.2.0"
PACKAGE_NAME = "comfyui-chinese-transcribe"

# Console prefix used by the node layer and the helpers.
LOG_PREFIX = "[Chinese Transcribe]"

# ComfyUI menu path: Audio -> Transcribe.
CATEGORY = "Audio/Transcribe"

SOURCE_TYPES = ("file", "url")
DEFAULT_SOURCE_TYPE = "file"

MODEL_CHOICES = (
    "iic/SenseVoiceSmall",
    "paraformer-zh",
    "FunAudioLLM/Fun-ASR-Nano-2512",
)
DEFAULT_MODEL = "iic/SenseVoiceSmall"

DEVICE_CHOICES = ("auto", "cuda", "cpu")
LANGUAGE_CHOICES = ("zh", "auto", "en", "yue", "ja", "ko")
HUB_CHOICES = ("auto", "ms", "hf")

VAD_BACKENDS = ("ffmpeg", "funasr")
DEFAULT_VAD_BACKEND = "ffmpeg"

TRANSCRIPT_FORMATS = ("srt", "vtt", "txt", "json")
ENCODINGS = ("utf-8-sig", "utf-8", "gbk")

# Namespaced ComfyUI socket types. Type matching is plain string equality, so
# a generic name such as "SEGMENTS" could accept an incompatible output from a
# different custom-node pack.
TYPE_MEDIA_SOURCE = "CT_MEDIA_SOURCE"
TYPE_MEDIA_INFO = "CT_MEDIA_INFO"
TYPE_SPEECH_SEGMENTS = "CT_SPEECH_SEGMENTS"
TYPE_SEGMENTS = "CT_SEGMENTS"

# Default sub-folder under ComfyUI's output directory.
DEFAULT_OUTPUT_SUBDIR = "transcribe"

# Environment overrides, mainly for headless installs and the tests.
ENV_OUTPUT_DIR = "COMFY_TRANSCRIBE_OUTPUT_DIR"
ENV_INPUT_DIR = "COMFY_TRANSCRIBE_INPUT_DIR"
ENV_FFMPEG_BINARY = "FFMPEG_BINARY"
ENV_FFPROBE_BINARY = "FFPROBE_BINARY"

DEFAULT_DOWNLOAD_MAX_MB = 2048
DEFAULT_DOWNLOAD_TIMEOUT = 120
DEFAULT_SAMPLE_RATE = "16000"

# FunASR returns sentence_info start/end values in milliseconds.
FUNASR_TIME_UNIT_MS = True

USER_AGENT = f"{PACKAGE_NAME}/{VERSION}"

__all__ = [
    "CATEGORY",
    "DEFAULT_DOWNLOAD_MAX_MB",
    "DEFAULT_DOWNLOAD_TIMEOUT",
    "DEFAULT_MODEL",
    "DEFAULT_OUTPUT_SUBDIR",
    "DEFAULT_SAMPLE_RATE",
    "DEFAULT_SOURCE_TYPE",
    "DEFAULT_VAD_BACKEND",
    "DEVICE_CHOICES",
    "ENCODINGS",
    "ENV_FFMPEG_BINARY",
    "ENV_FFPROBE_BINARY",
    "ENV_INPUT_DIR",
    "ENV_OUTPUT_DIR",
    "FUNASR_TIME_UNIT_MS",
    "HUB_CHOICES",
    "LANGUAGE_CHOICES",
    "LOG_PREFIX",
    "MODEL_CHOICES",
    "PACKAGE_NAME",
    "SOURCE_TYPES",
    "TRANSCRIPT_FORMATS",
    "TYPE_MEDIA_INFO",
    "TYPE_MEDIA_SOURCE",
    "TYPE_SEGMENTS",
    "TYPE_SPEECH_SEGMENTS",
    "USER_AGENT",
    "VAD_BACKENDS",
    "VERSION",
]
