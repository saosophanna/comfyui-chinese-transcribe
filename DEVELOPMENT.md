# Development notes

Developer-facing notes for `comfyui-chinese-transcribe`. User documentation
lives in [README.md](README.md).

## Architecture

| Path | Responsibility |
|---|---|
| `__init__.py` | ComfyUI entry point: registration mappings and `__version__`. |
| `config.py` | Version, category, model/format choices, environment variable names, defaults. |
| `nodes/inputs.py` | Shared `INPUT_TYPES` builders; the widget-order contract. |
| `nodes/common.py` | `[Chinese Transcribe]` logging, ComfyUI `ProgressBar`, text writing. |
| `nodes/media_input.py` | `Media Input`: source kind + URL/path → `CT_MEDIA_SOURCE`. |
| `nodes/resolve_media.py` | `Resolve Media`: download-or-validate conditional router. |
| `nodes/download_media.py` | `Download Media`: standalone direct-URL download. |
| `nodes/download_ytdlp.py` | `Download Media (yt-dlp)`: platform page downloader (audio/video). |
| `nodes/load_media.py` | `Load Media`: path validation + `CT_MEDIA_INFO` probe. |
| `nodes/extract_audio.py` | `FFmpeg Extract Audio`: video/audio → PCM WAV. |
| `nodes/vad.py` | `VAD`: speech regions with ffmpeg or FunASR. |
| `nodes/transcribe.py` | `FunASR Transcribe`: model/device/language widgets + chunk routing. |
| `nodes/format_transcript.py` | `Format Transcript`: TXT/JSON/SRT/VTT writing. |
| `nodes/save_transcript.py` | `Save Transcript`: arbitrary text saving. |
| `paths.py` | ComfyUI input/output roots, path resolution, filename safety. |
| `media.py` | URL validation, streaming download, filename inference, ffprobe/PyAV inspection, download audio guard. |
| `ytdlp_utils.py` | yt-dlp options, audio/video download, output-path resolution. |
| `ffmpeg_utils.py` | Binary discovery, subprocess wrapper, extraction command builder, ffprobe JSON. |
| `audio.py` | WAV info, duration, PCM slicing (wave module with ffmpeg fallback). |
| `speech.py` | `silencedetect` parsing, region refinement, fsmn-vad wrapper, VAD backends. |
| `funasr_utils.py` | Lazy FunASR import, actionable install error, device resolution. |
| `asr.py` | Model cache, per-model `generate()` calls, chunking, result parsing. |
| `transcript.py` | Character-timestamp grouping and subtitle/text formatting. |
| `requirements.txt` | `requests` + `funasr` + `yt-dlp`; FFmpeg is a system dependency. |
| `install.py` | One-command installer: re-execs with ComfyUI's Python, runs pip, checks FFmpeg. |
| `example_workflows/` | Starter graphs: paraformer SRT, VAD + SenseVoice SRT, yt-dlp platform URL. |
| `tests/` | Offline unittest suite (no network, no model downloads). |

### Runtime flow

1. `Media Input` validates the selected widget and returns
   `{"type": "file"|"url", "url": ..., "path": ..., "label": ...}`.
2. `Resolve Media` branches on `type`: URLs go through `media.download_media()`,
   local files through `paths.resolve_input_path()`. URL downloads are then
   checked with `media.require_audio_stream()`, which rejects a video-only track
   at the download node; local files are validated by `Load Media`. Both return
   one path string.
2b. `Download Media (yt-dlp)` is the platform-page alternative:
   `ytdlp_utils.download_with_ytdlp()` uses yt-dlp to download the best audio
   (converted to WAV) or best video+audio (merged to MP4), then the graph joins
   at `Load Media`.
3. `Load Media` probes with `ffprobe -show_format -show_streams` (PyAV fallback)
   and returns a JSON-friendly `CT_MEDIA_INFO` dict.
4. `FFmpeg Extract Audio` runs
   `ffmpeg -i <in> -map 0:a:0 -vn -ac 1 -ar 16000 -c:a pcm_s16le <out.wav>`.
5. `VAD` optionally returns `CT_SPEECH_SEGMENTS` (pairs in seconds). The ffmpeg
   backend parses `silencedetect` stderr; the funasr backend reads
   `AutoModel(model="fsmn-vad").generate(...)`.
6. `FunASR Transcribe` loads/caches a model and calls `generate()` once for the
   whole file, or once per VAD region. Chunk timestamps are offset back to the
   original timeline. The result is a `CT_SEGMENTS` dict.
7. `Format Transcript` formats and writes the file under ComfyUI's output
   directory; `Save Transcript` writes arbitrary text.

## Verified API contract (2026-10-29)

Sources:

- <https://github.com/modelscope/FunASR> — AutoModel examples, `paraformer-zh`
  with `vad_model="fsmn-vad"`, `punc_model="ct-punc"`, `device`, `hotword`.
- <https://github.com/FunAudioLLM/SenseVoice> — SenseVoiceSmall constructor and
  `generate()` arguments, `rich_transcription_postprocess`.
- <https://modelscope.github.io/FunASR/model-selection.html> — model selection,
  Fun-ASR-Nano usage.
- FunASR issues/docs on `sentence_timestamp=True` → `sentence_info` with
  `start`/`end` in **milliseconds** (e.g. issue #1383).
- <https://ffmpeg.org/ffmpeg-filters.html#silencedetect> — filter syntax and
  `silence_start` / `silence_end` log lines.

### Model calls

| Model | Constructor | `generate()` | Timing |
|---|---|---|---|
| `iic/SenseVoiceSmall` | `model=`, `vad_model="fsmn-vad"`, `vad_kwargs={"max_single_segment_time": 30000}`, `device` | `input`, `cache={}`, `language`, `use_itn`, `batch_size_s`, `merge_vad=True`, `merge_length_s=15` | **None**; post-process with `rich_transcription_postprocess`. |
| `paraformer-zh` | `model=`, `vad_model="fsmn-vad"`, `punc_model="ct-punc"`, `device` | `input`, `batch_size_s`, `sentence_timestamp=True`, optional `hotword` | `sentence_info[]` with `start`/`end` ms and `sentence`/`text`; char-level `timestamp` fallback. |
| `FunAudioLLM/Fun-ASR-Nano-2512` | `model=`, `vad_model="fsmn-vad"`, `vad_kwargs`, `trust_remote_code=True`, `device` | `input` (documented plain call) | **No documented timestamps**; chunk timing comes from VAD. |

`AutoModel(..., disable_update=True)` is passed for every model. The optional
`hub` widget forwards `hub="ms"` or `hub="hf"` when selected.

Fun-ASR-Nano's plain `generate(input=...)` call is documented. The
`trust_remote_code` + `vad_model` combination comes from its model card / HF
usage examples and has not been run live here; verify it first (roadmap item 1).

### Parsing rules

1. **SenseVoice tags** (`<|zh|><|NEUTRAL|>...`) are removed by
   `rich_transcription_postprocess`; when that import fails, a regex strips
   `<|...|>` tags.
2. **`sentence_info`** is preferred. Entry text comes from `sentence` or `text`;
   time may be `start`/`end`, `start_time`/`end_time`, or a per-character
   `timestamp` list; all values are milliseconds.
3. **Character timestamps** are grouped into cues by sentence-ending
   punctuation, `max_chars=60` and `max_seconds=12`. FunASR's punctuation model
   may add characters without timestamps, so alignment tries: all characters,
   non-whitespace characters, then non-punctuation characters. If none match,
   the result falls back to one whole-range cue.
4. **No timing** → one cue spanning the audio file (or the VAD chunk).

### Device strings

`auto` → `cuda:0` when `torch.cuda.is_available()`, else `cpu`. Explicit `cuda`
raises a clear error when unavailable. `cpu` is always honoured.

### FFmpeg / VAD

- Binary lookup order: `FFMPEG_BINARY` / `FFPROBE_BINARY`, `PATH`, then
  `imageio_ffmpeg` (ffmpeg only). `ffprobe` has no imageio fallback.
- Media probe: `ffprobe -v error -print_format json -show_format -show_streams`.
  PyAV is used only when `ffprobe` is absent, not when it fails.
- Extraction: input `-ss` before `-i`, `-map 0:a:0`, `-vn`, `-ac`, `-ar`,
  `-c:a pcm_s16le`; output `-t` for chunks.
- `silencedetect=noise=-35.0dB:d=0.400` on `-f null -`; speech is the
  complement of the reported silences over the probed duration.
- `fsmn-vad` result: `[{"value": [[start_ms, end_ms], ...]}]`; converted to
  seconds, padded, merged and capped.

### yt-dlp

- Audio mode: `format="bestaudio/b"` plus the `FFmpegExtractAudio`
  postprocessor with `preferredcodec="wav"`.
- Video mode: `format="bv*+ba/b"` plus `merge_output_format="mp4"`.
- Common options: `paths={"home": dest}`, `outtmpl`, `noplaylist`,
  `overwrites`, `windowsfilenames`, optional `cookiefile`.
- URL normalization: Douyin feed/modal URLs with a numeric `modal_id` query
  value are rewritten to `https://www.douyin.com/video/<id>`, the only form the
  Douyin extractor matches. Other URLs pass through unchanged.
- Output path resolution: `requested_downloads[].filepath`, then
  `prepare_filename()`, then the `.wav` sibling, then the newest media file
  with the same stem. This was smoke-tested against real yt-dlp using a local
  HTTP server in both audio and video modes.
- Site extractors change regularly; users should update yt-dlp when a platform
  breaks.

## Custom types

ComfyUI passes the Python values through links unchanged. The socket-type
strings are namespaced (`CT_` = Chinese Transcribe) because ComfyUI matches
types by plain string equality; a generic name such as `SEGMENTS` would accept
an incompatible output from another custom-node pack.

### `CT_MEDIA_SOURCE`

```python
{"type": "file"|"url", "url": str, "path": str, "label": str}
```

### `CT_MEDIA_INFO`

```python
{
  "path", "name", "size_bytes", "duration", "format", "format_long",
  "stream_count", "has_audio", "has_video",
  "audio_codec", "sample_rate", "channels",
  "video_codec", "width", "height"
}
```

All values are JSON-friendly.

### `CT_SPEECH_SEGMENTS`

```python
{
  "audio_path": str,
  "duration": float,
  "backend": "ffmpeg"|"funasr",
  "segments": [[start_s, end_s], ...],
  "speech_seconds": float,
  "params": {...},
  "chunks": [str, ...]
}
```

### `CT_SEGMENTS`

```python
{
  "text": str,
  "segments": [{"start": float, "end": float, "text": str}, ...],
  "duration": float,
  "language": str,
  "model": str,
  "device": str,
  "timing": "sentence"|"vad"|"whole",
  "has_timestamps": bool,
  "chunks": [str, ...]
}
```

## ComfyUI integration rules

1. **Widget order is positional.** `widgets_values` in workflow JSON follows
   `INPUT_TYPES` key order: required first, then optional. Append new widgets at
   the end; never insert before existing ones. `tests/test_nodes_contract.py`
   snapshots the order.
2. **Custom-type inputs are sockets**, not widgets: `CT_MEDIA_SOURCE`,
   `CT_MEDIA_INFO` (output only), `CT_SPEECH_SEGMENTS`, `CT_SEGMENTS`. They do not
   occupy `widgets_values` slots.
3. **File nodes use `IS_CHANGED`.** `Load Media`, `Extract Audio`, `VAD` and
   `FunASR Transcribe` return a cache key containing the input file's
   mtime/size plus every relevant widget. Without this, replacing a file at the
   same path would silently reuse the old transcript.
4. **Downloads are cached by their widgets.** Changing a URL/filename or
   deleting the downloaded file forces a new copy; `Download Media` does not
   poll the remote.
5. **Use output nodes deliberately.** `Format Transcript` and `Save Transcript`
   set `OUTPUT_NODE = True` because their purpose is to write a file even when
   nothing is linked downstream.
6. **Lazy imports are mandatory.** `funasr`, `requests`, `torch` and
   `imageio_ffmpeg` are imported inside functions. `nodes/__init__.py` must
   never import them, or one missing optional package hides every node.
7. **Sanitize shifted widgets.** Old workflows can deliver a boolean into a
   string widget. `sanitize.py` treats `True`/`"True"`/`"None"` as empty for
   text and clamps numbers.

### Adding an input safely

1. Add the builder to the node's `INPUT_TYPES` (or `nodes/inputs.py` if shared)
   **after** the existing widgets.
2. Thread it through the node method signature and, if needed, `asr.transcribe`
   / `speech.detect`.
3. Add it to the node's `IS_CHANGED` cache key.
4. Update `README.md`, `tests/test_nodes_contract.py` widget-order snapshots and
   the pipeline tests.
5. Bump `config.VERSION`.

## Transcription details

- **Whole-file mode** lets FunASR's built-in VAD handle long audio and
  `batch_size_s` control batching.
- **VAD mode** cuts each region with `audio.slice_audio()`: PCM WAV is sliced
  with the standard `wave` module (no re-encode), anything else goes through
  ffmpeg. Temporary files live in `tempfile.mkdtemp()` and are removed unless
  `keep_chunks` is on; kept chunks go to
  `output/transcribe/chunks/asr_<timestamp>_<id>/`.
- **Text joining:** Chinese/Cantonese/Japanese join without spaces; English,
  Korean and unknown languages join with spaces; `auto` looks for CJK
  characters.
- **Model cache:** keyed by `(model_id, resolved_device, hub)`. Weights stay in
  memory between queues; ComfyUI restarts clear it.
- **Model load** is logged with elapsed time. The first run also downloads
  weights before that timer starts.
- **`sentence_timestamp`:** passed only to paraformer models. If the installed
  FunASR raises `TypeError`, the call is retried without it and the node logs
  that timing will be coarse. This is the only intentionally broad fallback in
  the ASR path.

## Testing notes

- Environment used while developing: Windows 11, Python 3.13.2, FFmpeg 7.1
  (`gyan.dev` full build). FunASR was **not** installed, so the suite exercises
  parsing and orchestration, not real inference.
- Run the suite from the package folder:

  ```bash
  python -m unittest discover -s tests -v
  ```

- `tests/_loader.py` loads the package with `spec_from_file_location` on
  `__init__.py`, which is what ComfyUI's `load_custom_node` does. It stubs
  `requests` when missing and never imports FunASR. `test_asr_pipeline.py`
  injects a fake `funasr` module to check constructor/generate arguments and
  VAD chunk offsets without downloading weights.
- FFmpeg-dependent tests are skipped when `ffmpeg` is unavailable. The rest are
  pure and fast (~0.5 s for 119 tests).
- Coverage: filename safety and traversal, download streaming/HTML/size/HTTP
  errors, downloaded-file audio guards, yt-dlp URL normalization, duration/unit
  formatting, `silencedetect` parsing, region
  refinement/capping, character-timestamp alignment with punctuation offsets,
  CJK-aware subtitle wrapping, SRT/VTT/TXT/JSON formatting, FunASR result
  shapes (whole/sentence/char), fake-FunASR model/generate arguments and chunk
  offsets, yt-dlp options and download orchestration with a fake module,
  widget order, `IS_CHANGED` keys, installer check mode and versioned-venv
  detection, example workflow slot/widget/link validation, and an end-to-end
  file→extract→VAD→SRT run with real FFmpeg.
- Real yt-dlp path resolution was smoke-tested against a local HTTP server in
  both audio and video modes; no external platform was contacted.

## Roadmap

### High priority

1. **Live-verify every model.** Run SenseVoiceSmall, paraformer-zh and
   Fun-ASR-Nano on the same Chinese clip on CPU and CUDA. Record first-run
   download size, VRAM, load time and transcript quality; confirm
   `sentence_info` field names and milliseconds, and whether Fun-ASR-Nano
   accepts `trust_remote_code`/VAD in the installed FunASR version. Update the
   constructor kwargs if reality differs.
2. **Sentence alignment after punctuation.** FunASR issue #1383 reports
   `sentence_timestamp=True` can misalign sentence splits. Compare
   `sentence_info` against the character-timestamp grouping fallback and pick
   the better one per model; consider making the grouping limits widgets.
3. **Harden yt-dlp.** The platform node is implemented with audio/video modes
   and cookies. Verify Douyin/TikTok/YouTube/Bilibili extractors live, then add
   an explicit proxy input and playlist selection (currently `noplaylist` and
   the first entry). Keep the direct HTTP downloader unchanged.
4. **Download robustness.** Resume partial downloads, retry transient HTTP
   failures, expose a progress bar from `download_media`, and support a
   `Referer`/cookie header for CDNs that require it.
5. **Interrupt handling.** Check ComfyUI's interrupt flag between VAD chunks and
   between ASR regions so cancelling a long transcription stops promptly.

### Medium priority

6. **Native ComfyUI audio.** Accept the built-in `AUDIO` type from `LoadAudio`
   (waveform tensor + sample rate) in addition to file paths, and emit
   `AUDIO` where useful.
7. **Upload widget / video loader.** A frontend upload button or integration
   with a `LoadVideo` node would remove the manual copy into `ComfyUI/input`.
8. **Speaker diarization.** Use FunASR's `spk_model="cam++"` (or `sentence_info`
   speaker ids) and add speaker labels to SRT cues.
9. **Translation / bilingual subtitles.** Optional translate step producing
   bilingual SRT lines; keep it a separate node so the ASR path stays local.
10. **Richer timing.** Emit ASS with word-level karaoke timing from
    paraformer's character timestamps; expose cue length limits as widgets.
11. **Batch media.** Accept a list of files and iterate, with per-file outputs.

### Repo and quality

12. Add `pyproject.toml` with ComfyUI Registry metadata and a `CHANGELOG.md`.
13. Wire the suite into CI (syntax check, unit tests, widget-order snapshot,
    example-workflow validation).
14. Add PyAV-probe and live-download tests behind opt-in environment flags.
