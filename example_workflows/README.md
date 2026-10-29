# Example workflows

Ready-to-import ComfyUI graphs for this custom node package.

| File | Pipeline | Use |
|---|---|---|
| [`ChineseTranscribe_Starter.json`](ChineseTranscribe_Starter.json) | Media Input → Resolve Media → Load Media → FFmpeg Extract Audio → FunASR (`paraformer-zh`) → Format Transcript (SRT) | Best Chinese subtitles: sentence timestamps and punctuation. Works with a local file or a direct URL. |
| [`ChineseTranscribe_VAD_SenseVoice.json`](ChineseTranscribe_VAD_SenseVoice.json) | … → VAD (`ffmpeg`) → FunASR (`iic/SenseVoiceSmall`, `speech_segments` connected) → Format Transcript (SRT) | Long or noisy recordings, and segment-level SRT cues from a model that returns no timestamps. |
| [`ChineseTranscribe_Platform_URL.json`](ChineseTranscribe_Platform_URL.json) | Download Media (yt-dlp, audio) → Load Media → FFmpeg Extract Audio → FunASR (`paraformer-zh`) → Format Transcript (SRT) | Douyin/TikTok/YouTube/Bilibili **page URLs**. yt-dlp resolves the separate video/audio streams. |

## Import

1. Install the custom node package first — see [../README.md](../README.md).
2. Restart ComfyUI.
3. Drag a JSON file onto the canvas, or use **Workflow → Open**.
4. Put your media in `ComfyUI/input` and set **Media Input → path** to its
   filename (the placeholder is `video.mp4`), or enter an absolute path.
   For a direct URL, set **Media Input → source_type** to `url` and paste the
   URL.
   For `ChineseTranscribe_Platform_URL.json`, paste the platform **page URL**
   into **Download Media (yt-dlp) → url** instead.
5. Queue. The transcript/subtitle path is printed in the ComfyUI console and
   returned by **Format Transcript**.

## Notes

- The first transcription downloads FunASR model weights.
- FFmpeg must be installed and on `PATH`.
- Change **Format Transcript → format** to `txt`, `json` or `vtt`; the output
  extension follows automatically.
- Only direct media URLs work with Media Input / Download Media (Direct URL).
  For YouTube/Bilibili/Douyin/TikTok **pages**, use the platform workflow and
  its yt-dlp node.
- Video-only CDN links (common on Douyin/TikTok) have no audio. Use the page
  URL; yt-dlp fetches the separate audio track.
- Login/region-locked pages may need a Netscape `cookies.txt` in `ComfyUI/input`
  and the `cookies_file` widget.
- Both local/URL workflows contain a **How to use** note with the same
  essentials; the platform workflow has its own note.

The JSON files are validated by `tests/test_example_workflows.py`, which checks
the widget order, slot indexes, link types and node contracts against
`INPUT_TYPES`.
