"""ComfyUI node classes, one module per node."""

from .download_media import ChineseTranscribeDownloadMedia
from .download_ytdlp import ChineseTranscribeYtDlp
from .extract_audio import ChineseTranscribeExtractAudio
from .format_transcript import ChineseTranscribeFormatTranscript
from .load_media import ChineseTranscribeLoadMedia
from .media_input import ChineseTranscribeMediaInput
from .resolve_media import ChineseTranscribeResolveMedia
from .save_transcript import ChineseTranscribeSaveTranscript
from .transcribe import ChineseTranscribeFunASR
from .vad import ChineseTranscribeVAD

NODE_CLASS_MAPPINGS = {
    "ChineseTranscribeMediaInput": ChineseTranscribeMediaInput,
    "ChineseTranscribeResolveMedia": ChineseTranscribeResolveMedia,
    "ChineseTranscribeDownloadMedia": ChineseTranscribeDownloadMedia,
    "ChineseTranscribeYtDlp": ChineseTranscribeYtDlp,
    "ChineseTranscribeLoadMedia": ChineseTranscribeLoadMedia,
    "ChineseTranscribeExtractAudio": ChineseTranscribeExtractAudio,
    "ChineseTranscribeVAD": ChineseTranscribeVAD,
    "ChineseTranscribeFunASR": ChineseTranscribeFunASR,
    "ChineseTranscribeFormatTranscript": ChineseTranscribeFormatTranscript,
    "ChineseTranscribeSaveTranscript": ChineseTranscribeSaveTranscript,
}

NODE_DISPLAY_NAME_MAPPINGS = {
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

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "ChineseTranscribeDownloadMedia",
    "ChineseTranscribeYtDlp",
    "ChineseTranscribeExtractAudio",
    "ChineseTranscribeFormatTranscript",
    "ChineseTranscribeLoadMedia",
    "ChineseTranscribeMediaInput",
    "ChineseTranscribeResolveMedia",
    "ChineseTranscribeSaveTranscript",
    "ChineseTranscribeFunASR",
    "ChineseTranscribeVAD",
]
