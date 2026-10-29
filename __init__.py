"""ComfyUI custom nodes: Chinese video/audio transcription (FFmpeg + FunASR)."""

from .config import VERSION as __version__
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "__version__"]
