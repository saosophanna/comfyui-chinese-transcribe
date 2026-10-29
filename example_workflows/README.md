# Example workflows

Ready-to-import ComfyUI graphs for this custom node package.

| File | Pipeline | Use |
|---|---|---|
| [`ChineseTranscribe_Starter.json`](ChineseTranscribe_Starter.json) | Media Input → Resolve Media → Load Media → FFmpeg Extract Audio → FunASR (`paraformer-zh`) → Format Transcript (SRT) | Best Chinese subtitles: sentence timestamps and punctuation. Works with a local file or a direct URL. |
| [`ChineseTranscribe_VAD_SenseVoice.json`](ChineseTranscribe_VAD_SenseVoice.json) | … → VAD (`ffmpeg`) → FunASR (`iic/SenseVoiceSmall`, `speech_segments` connected) → Format Transcript (SRT) | Long or noisy recordings, and segment-level SRT cues from a model that returns no timestamps. |

## Import

1. Install the custom node package first — see [../README.md](../README.md).
2. Restart ComfyUI.
3. Drag a JSON file onto the canvas, or use **Workflow → Open**.
4. Put your media in `ComfyUI/input` and set **Media Input → path** to its
   filename (the placeholder is `video.mp4`), or enter an absolute path.
   For a direct URL, set **Media Input → source_type** to `url` and paste the
   URL.
5. Queue. The transcript/subtitle path is printed in the ComfyUI console and
   returned by **Format Transcript**.

## Notes

- The first transcription downloads FunASR model weights.
- FFmpeg must be installed and on `PATH`.
- Change **Format Transcript → format** to `txt`, `json` or `vtt`; the output
  extension follows automatically.
- Only direct media URLs work. YouTube/Bilibili pages are HTML and are
  rejected; download them with yt-dlp first.
- Both workflows contain a **How to use** note with the same essentials.

The JSON files are validated by `tests/test_example_workflows.py`, which checks
the widget order, slot indexes, link types and node contracts against
`INPUT_TYPES`.
