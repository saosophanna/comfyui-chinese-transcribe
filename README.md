# Chinese video/audio transcription — ComfyUI nodes

Takes a **direct media URL**, a **platform page URL** (Douyin, TikTok, YouTube,
Bilibili, ... via yt-dlp), a **local video**, or a **local audio file** and
produces Chinese text with timestamps plus optional **TXT / JSON / SRT / VTT**
subtitles. FFmpeg handles media, [FunASR](https://github.com/modelscope/FunASR)
handles speech recognition. Transcription runs locally; the network is used only
for the optional URL download and the first FunASR model download.

Ten nodes are registered under **Audio → Transcribe**:

| Node | Purpose |
|---|---|
| `Media Input (URL / File)` | Declare one source: a URL or a local path. |
| `Resolve Media` | Conditional router: downloads URLs (audio-checked), validates local files. |
| `Download Media (Direct URL)` | Standalone direct-URL download (audio-checked). |
| `Download Media (yt-dlp)` | Platform page or media URL via yt-dlp (audio or muxed video). |
| `Load Media (Probe)` | Validates a file and reports duration/streams/codecs. |
| `FFmpeg Extract Audio` | Video/audio → PCM WAV (mono, 16 kHz by default). |
| `VAD (Detect Speech)` | Finds speech regions; optional chunk WAVs. |
| `FunASR Transcribe (Chinese)` | Speech → text + timed segments. |
| `Format Transcript (TXT/JSON/SRT/VTT)` | Formats and writes a subtitle/text file. |
| `Save Transcript` | Saves arbitrary text to the output folder. |

## Pipeline

```
Media Input ──media_source──> Resolve Media ──media_path──> Load Media
   (url)                        (downloads)                       │
   (file)                       (validates)                       ▼
                                                    FFmpeg Extract Audio
                                                               │
                                                       audio_path
                                                               ▼
                                                    VAD (optional) ──┐
                                                               │      │
                                                               ▼      │
                                                    FunASR Transcribe ◄┘
                                                       (speech_segments)
                                                               │
                                                  transcript + segments
                                                               ▼
                                                    Format Transcript ──> SRT/VTT/TXT/JSON
                                                               │
                                                               ▼
                                                    Save Transcript / preview
```

`Resolve Media` is the conditional router the graph needs: a URL is downloaded,
a local path is validated, and both return one `media_path` string. `Load Media`
is the convergence/probe point. `Download Media` is an alternative entry point
for URL-only graphs:

```
Download Media ──media_path──> Load Media ──> FFmpeg Extract Audio ──> ...
```

For platform pages, replace the downloader with yt-dlp:

```
Download Media (yt-dlp) ──media_path──> Load Media ──> FFmpeg Extract Audio ──> ...
```

VAD is optional. Without it, FunASR uses its own built-in `fsmn-vad`. Connect it
when you want VAD chunking, split files, or **segment-level timing from models
that do not return timestamps** (SenseVoice and Fun-ASR-Nano).

## Example workflows

Ready-to-import graphs live in [`example_workflows/`](example_workflows/):

| File | Pipeline |
|---|---|
| [`ChineseTranscribe_Starter.json`](example_workflows/ChineseTranscribe_Starter.json) | Local file or direct URL → `paraformer-zh` → SRT with sentence timestamps. |
| [`ChineseTranscribe_VAD_SenseVoice.json`](example_workflows/ChineseTranscribe_VAD_SenseVoice.json) | VAD → `SenseVoiceSmall` → SRT with one cue per speech region (long/noisy recordings). |
| [`ChineseTranscribe_Platform_URL.json`](example_workflows/ChineseTranscribe_Platform_URL.json) | yt-dlp page URL → `paraformer-zh` → SRT (Douyin/TikTok/YouTube/Bilibili). |

Drag a JSON onto the ComfyUI canvas (or **Workflow → Open**), set the media
input, and Queue. The local/URL and VAD workflows use `video.mp4` as a
placeholder; the platform workflow uses an empty page URL. Each graph includes
a **How to use** note. See
[`example_workflows/README.md`](example_workflows/README.md) for details.

## Install

In `ComfyUI/custom_nodes`:

```bash
git clone https://github.com/saosophanna/comfyui-chinese-transcribe.git
cd comfyui-chinese-transcribe
python install.py
```

That is the whole setup. Restart ComfyUI and the nodes appear under
**Audio → Transcribe**.

`install.py`:

- re-executes itself with ComfyUI's bundled Python when it finds
  `python_embeded`, `.venv*` (including RunPod's `.venv-cu128`) or `venv*`
  next to `custom_nodes`;
- installs `requirements.txt` with pip;
- reports whether `ffmpeg` and `ffprobe` are available;
- warns if pip changed the installed torch version.

It is safe to run repeatedly. If `python` is not on `PATH` on Windows, use
`py install.py`. If you use ComfyUI Manager, installing this repository runs
`install.py` automatically.

Manual alternative, using the same Python environment that launches ComfyUI:

```bash
python -m pip install -r requirements.txt
```

`install.py --check` prints the environment and installed versions without
changing anything.

### Requirement 1: FFmpeg

`ffmpeg` and `ffprobe` must be available. Check in a terminal:

```bash
ffmpeg -version
ffprobe -version
```

Windows (PowerShell):

```powershell
winget install Gyan.FFmpeg
```

After installing, restart ComfyUI so the new `PATH` is visible. If the
executables are not on `PATH`, set `FFMPEG_BINARY` and `FFPROBE_BINARY` to their
full paths:

```powershell
setx FFMPEG_BINARY "C:\ffmpeg\bin\ffmpeg.exe"
setx FFPROBE_BINARY "C:\ffmpeg\bin\ffprobe.exe"
```

If `ffprobe` is missing, media inspection falls back to PyAV, which ComfyUI
bundles. Audio extraction and VAD still need `ffmpeg`.

### Requirement 2: FunASR and yt-dlp

`install.py` installs FunASR and yt-dlp. To do it manually:

```bash
python -m pip install -U "funasr>=1.3.0" yt-dlp
```

Use the interpreter that launches ComfyUI (for example
`ComfyUI\python_embeded\python.exe -m pip install...`). The nodes lazily import
FunASR, so ComfyUI still starts and shows them when it is missing; execution
then raises a message with the exact interpreter path.

The first transcription downloads model weights (to the ModelScope/Hugging Face
cache). This can take several minutes and a few GB of disk. Fun-ASR-Nano is the
largest; SenseVoiceSmall is the smallest.

> **PyTorch note:** FunASR uses the `torch`/`torchaudio` already installed in
> ComfyUI. If pip proposes replacing your CUDA-enabled torch with a CPU build,
> stop: keep ComfyUI's GPU build and install FunASR against it (for example
> with a pip constraints file, or `--no-deps` plus FunASR's non-torch
> dependencies). Do not let a custom node silently downgrade torch.

### Optional environment variables

| Variable | Effect |
|---|---|
| `FFMPEG_BINARY` | Path to the ffmpeg executable. |
| `FFPROBE_BINARY` | Path to the ffprobe executable. |
| `COMFY_TRANSCRIBE_OUTPUT_DIR` | Overrides ComfyUI's output folder (headless/testing). |
| `COMFY_TRANSCRIBE_INPUT_DIR` | Overrides ComfyUI's input folder (headless/testing). |

## Models

| Model | Languages | Timestamps | Use when |
|---|---|---|---|
| `iic/SenseVoiceSmall` (default) | Mandarin, Cantonese, English, Japanese, Korean; `auto` detects | **No** | Fast baseline transcript. Connect VAD for SRT cues. |
| `paraformer-zh` | Mandarin | **Yes**, sentence-level (`sentence_timestamp=True`) with `ct-punc` punctuation | Chinese subtitles with timing. |
| `FunAudioLLM/Fun-ASR-Nano-2512` | Multilingual incl. Chinese dialects (31 languages per its release notes) | No documented timestamps | Newer/context-aware multilingual recognition; needs a recent FunASR. |

The usage above is verified against the FunASR and SenseVoice documentation
(2026-10-29). See [DEVELOPMENT.md](DEVELOPMENT.md) for the exact calls and
caveats.

Models stay cached in memory (and on the GPU when selected) until ComfyUI
restarts. If VRAM is tight, set `device` to `cpu` or unload other models first.

**Subtitles:** use `paraformer-zh` for sentence-level Chinese timing. SenseVoice
and Fun-ASR-Nano return a single whole-file cue unless `speech_segments` is
connected; with VAD connected you get **one cue per speech region**, which is
usable for SRT but coarser than paraformer's sentence splitting.

`language` and `use_itn` are SenseVoice options. `hotword` is `paraformer-zh`
only. The node logs when an option is ignored.

## Inputs

### Media Input (URL / File)

| Input | Type | Default | Notes |
|---|---|---|---|
| `source_type` | combo | `file` | `file` or `url`. |
| `url` | STRING | empty | Direct `http(s)` media URL; used only for `url`. |
| `path` | STRING | empty | Local path; relative names are looked up in `ComfyUI/input`. |

Outputs: `media_source` (`CT_MEDIA_SOURCE`), `source_type` (STRING).

A local file is validated when this node runs, so a typo fails early.

### Resolve Media

| Input | Type | Default | Notes |
|---|---|---|---|
| `media_source` | CT_MEDIA_SOURCE | — | Connect Media Input. |
| `output_dir` | STRING | `transcribe/downloads` | Under ComfyUI's output folder. |
| `max_download_mb` | INT | `2048` | Abort larger downloads. |
| `timeout_seconds` | INT | `120` | Per-read network timeout. |
| `filename` (optional) | STRING | empty | Override the download filename. |

Outputs: `media_path` (STRING), `source_kind` (`url` / `file`).

URLs are downloaded; local files bypass the download entirely. HTML responses,
empty responses, oversized files and non-media content types are rejected. The
saved file is then probed for an audio stream, so a video-only DASH/CDN track
fails here with "is a video-only track" instead of later at extraction.

### Download Media (Direct URL)

| Input | Type | Default | Notes |
|---|---|---|---|
| `url` | STRING | empty | Direct media URL. |
| `output_dir` | STRING | `transcribe/downloads` | Output folder. |
| `max_download_mb` | INT | `2048` | Size limit. |
| `timeout_seconds` | INT | `120` | Read timeout. |
| `filename` (optional) | STRING | empty | Override the filename. |

Outputs: `media_path` (STRING), `bytes` (INT). The file is written atomically
(`.part` then rename) and probed for an audio stream before the node returns.

### Download Media (yt-dlp)

| Input | Type | Default | Notes |
|---|---|---|---|
| `url` | STRING | empty | Platform **page** URL (Douyin/TikTok/YouTube/Bilibili) or a direct media URL. |
| `mode` | combo | `audio` | `audio` = best audio → WAV; `video` = best video + audio → MP4. |
| `output_dir` | STRING | `transcribe/downloads` | Output folder. |
| `filename` | STRING | empty | Optional output stem; empty uses the video title and id. |
| `cookies_file` (optional) | STRING | empty | Netscape `cookies.txt` for login/region-locked pages; relative to `ComfyUI/input`. |

Outputs: `media_path` (STRING), `title` (STRING), `duration` (FLOAT).

This uses [yt-dlp](https://github.com/yt-dlp/yt-dlp). Pass the page URL, not a
video-only CDN link; yt-dlp resolves the separate video/audio tracks. `audio`
mode is smaller and is the best choice for transcription. If a site extractor
stops working, update it in ComfyUI's Python:
`python -m pip install -U yt-dlp`.

Cookies are sensitive: the file can contain account credentials. Keep it in
`ComfyUI/input` and do not share workflows or logs that reference it.

### Load Media (Probe)

| Input | Type | Default | Notes |
|---|---|---|---|
| `media_path` | STRING | empty | File from Resolve Media, either Download Media node, or a local path. |

Outputs: `media_path` (STRING), `media_info` (`CT_MEDIA_INFO`), `summary`
(STRING, e.g. `clip.mp4 | 01:23 | 45.2 MB | h264 1920x1080 + aac 48000 Hz 2 ch`).

Uses `ffprobe -show_format -show_streams`; falls back to PyAV if ffprobe is
missing. Warns when the file has no audio stream; URL downloads are already
rejected by the download nodes before they reach this point.

### FFmpeg Extract Audio

| Input | Type | Default | Notes |
|---|---|---|---|
| `media_path` | STRING | empty | Video or audio input. |
| `sample_rate` | combo | `16000` | 8000 / 16000 / 22050 / 44100 / 48000. |
| `mono` | BOOLEAN | `true` | Down-mix to one channel. |
| `output_dir` | STRING | `transcribe/audio` | Output folder. |
| `filename` (optional) | STRING | empty | Default: `<source>_<rate>_mono.wav`. |

Outputs: `audio_path` (STRING), `duration` (FLOAT seconds), `sample_rate` (INT).

The command is equivalent to:

```bash
ffmpeg -hide_banner -nostdin -y -i input.mp4 \
  -map 0:a:0 -vn -ac 1 -ar 16000 -c:a pcm_s16le audio.wav
```

It never modifies the source and refuses to overwrite the source file. The
default output is exactly what FunASR expects.

### VAD (Detect Speech)

| Input | Type | Default | Notes |
|---|---|---|---|
| `audio_path` | STRING | empty | Usually Extract Audio's output. |
| `backend` | combo | `ffmpeg` | `ffmpeg` = `silencedetect`; `funasr` = `fsmn-vad`. |
| `threshold_db` | FLOAT | `-35` | ffmpeg: quieter than this is silence. |
| `min_silence_ms` | INT | `400` | ffmpeg: shortest pause that ends a region. |
| `min_speech_ms` | INT | `250` | ffmpeg: shorter bursts are dropped. |
| `pad_ms` | INT | `200` | Keep context around each region. |
| `max_segment_seconds` | FLOAT | `30` | Split longer regions. |
| `device` | combo | `auto` | funasr backend only. |
| `write_chunks` (optional) | BOOLEAN | `false` | Write each region to a WAV. |
| `output_dir` (optional) | STRING | `transcribe/chunks` | Chunk folder. |

Outputs: `speech_segments` (`CT_SPEECH_SEGMENTS`), `segment_count` (INT),
`speech_seconds` (FLOAT). The dict includes `segments` as `[[start, end], ...]`
seconds, `duration`, `backend`, and `chunks` when written.

### FunASR Transcribe (Chinese)

| Input | Type | Default | Notes |
|---|---|---|---|
| `audio_path` | STRING | empty | WAV from Extract Audio. |
| `model` | combo | `iic/SenseVoiceSmall` | See the model table. |
| `device` | combo | `auto` | `cuda` errors clearly when CUDA is unavailable. |
| `language` | combo | `zh` | SenseVoice: `zh/auto/en/yue/ja/ko`. |
| `use_itn` | BOOLEAN | `true` | SenseVoice inverse text normalisation. |
| `batch_size_s` | INT | `300` | Audio batch size in seconds. |
| `max_segment_seconds` | FLOAT | `30` | Cap when `speech_segments` is connected. |
| `speech_segments` (optional) | CT_SPEECH_SEGMENTS | — | VAD output; transcribes each region. |
| `hotword` (optional) | STRING | empty | paraformer-zh only, e.g. `魔搭 20`. |
| `hub` (optional) | combo | `auto` | `auto` / `ms` (ModelScope) / `hf`. |
| `keep_chunks` (optional) | BOOLEAN | `false` | Keep temporary chunk WAVs. |

Outputs: `transcript` (STRING), `segments` (`CT_SEGMENTS`), `segment_count` (INT).

`CT_SEGMENTS` contains:

```json
{
  "text": "你好，世界。",
  "segments": [
    {"start": 0.12, "end": 1.84, "text": "你好，世界。"}
  ],
  "duration": 12.5,
  "language": "zh",
  "model": "paraformer-zh",
  "device": "cuda:0",
  "timing": "sentence",
  "has_timestamps": true,
  "chunks": []
}
```

`timing` is `sentence` (model-provided timing), `vad` (one cue per VAD region)
or `whole` (single cue). Models are cached per model/device/hub, so consecutive
queues do not reload weights.

### Format Transcript (TXT/JSON/SRT/VTT)

| Input | Type | Default | Notes |
|---|---|---|---|
| `transcript` | STRING | empty | Connect FunASR's transcript output. |
| `segments` | CT_SEGMENTS | — | Connect FunASR's segments output. |
| `format` | combo | `srt` | `srt`, `vtt`, `txt`, `json`. |
| `filename` | STRING | `transcript` | Extension is added/replaced. |
| `output_dir` | STRING | `transcribe` | Output folder. |
| `max_line_chars` | INT | `42` | SRT/VTT line width in columns; CJK/full-width characters count as 2. |
| `encoding` | combo | `utf-8-sig` | `utf-8-sig` / `utf-8` / `gbk`. |

Outputs: `formatted_text` (STRING, previewable), `output_path` (STRING). The
node is an output node, so it runs even when only its file is wanted.

SRT/VTT need timed segments. With `timing: whole`, use `paraformer-zh` or
connect VAD; the node raises an actionable error instead of writing a broken
subtitle file.

JSON output:

```json
{
  "text": "你好，世界。",
  "language": "zh",
  "model": "paraformer-zh",
  "duration": 12.5,
  "segments": [{"start": 0.12, "end": 1.84, "text": "你好，世界。"}]
}
```

### Save Transcript

| Input | Type | Default | Notes |
|---|---|---|---|
| `text` | STRING | empty | Multiline text. |
| `filename` | STRING | `transcript` | Without extension. |
| `extension` | combo | `txt` | `txt`, `srt`, `vtt`, `json`, `md`. |
| `output_dir` | STRING | `transcribe` | Output folder. |
| `encoding` | combo | `utf-8-sig` | Text encoding. |

Output: `saved_path` (STRING).

## Where files go

Everything is under ComfyUI's output folder by default:

```
ComfyUI/output/transcribe/
├── downloads/     # URL downloads
├── audio/         # extracted 16 kHz mono WAV
├── chunks/        # VAD chunks / kept ASR chunks
└── *.srt|vtt|txt|json
```

Relative `output_dir` values must stay inside the output folder; a path that
escapes it raises. Absolute paths are honoured because these nodes run on your
own machine. `filename` is sanitized (path separators, Windows-illegal
characters, reserved names).

### Remote ComfyUI / RunPod

The starter workflow's `video.mp4` is a placeholder and will fail until the
file exists. Either:

- upload the media to `<ComfyUI>/input` (on RunPod-Slim this is usually
  `/workspace/runpod-slim/ComfyUI/input`) and set **Media Input → path** to its
  filename or full path;
- set **Media Input → source_type** to `url` and paste a direct media URL; or
- use **Download Media (yt-dlp)** with the platform **page** URL (for Douyin,
  TikTok, YouTube, Bilibili, ...).

`python3 install.py` (run from the custom node folder with the Python that
launches ComfyUI) installs the Python dependencies on the pod. FFmpeg must also
be present.

## Recipes

**1. Chinese subtitles with sentence timing**

```
Media Input (file) → Resolve Media → Load Media → Extract Audio
  → FunASR Transcribe (paraformer-zh) → Format Transcript (srt)
```

**2. Fast transcript, no timestamps**

```
... → FunASR Transcribe (iic/SenseVoiceSmall) → Format Transcript (txt)
```

**3. Subtitles from SenseVoice or Fun-ASR-Nano**

```
... → Extract Audio → VAD (ffmpeg, max 30 s)
  → FunASR Transcribe (speech_segments connected) → Format Transcript (srt)
```

**4. Long recordings**

Raise `max_segment_seconds` on VAD to 30–60 s and keep it connected to FunASR.
Each region is cut to a temporary WAV, transcribed, and its timestamps are
offset back to the original timeline. Check `keep_chunks` to inspect the cuts.

**5. Platform page (Douyin/TikTok/YouTube/Bilibili)**

```
Download Media (yt-dlp, mode=audio) → Load Media → Extract Audio
  → FunASR Transcribe (paraformer-zh) → Format Transcript (srt)
```

Use the **page URL**, not the video-only CDN link. If the page needs a login or
is region-locked, provide a `cookies.txt`.

**6. Direct URL**

```
Media Input (source_type=url) → Resolve Media → Load Media → ...
```

or paste the URL into `Download Media (Direct URL)` and keep using Load Media.
Only direct media URLs work here; use the yt-dlp node for platform pages.

## Direct URLs vs platform pages

`Download Media (Direct URL)` and `Resolve Media` accept **direct media URLs**
only. A YouTube/Bilibili/Twitter page returns HTML and is rejected with a clear
message.

Use **`Download Media (yt-dlp)`** for platform pages. It resolves the page,
selects the separate video/audio streams and either extracts the audio to WAV
or merges them to MP4. Pass the page URL (`douyin.com/video/...`,
`v.douyin.com/...`, `youtube.com/watch?...`, `bilibili.com/video/...`).

Some platforms also serve **video-only** CDN links: the file downloads fine but
has no audio stream. `Resolve Media` and `Download Media (Direct URL)` probe the
saved file and reject it with "is a video-only track"; local files still get a
`Load Media` warning, and `FFmpeg Extract Audio` fails if one reaches it. That
URL is one DASH track, not the whole video. The yt-dlp node with the page URL is
the fix; a direct CDN link cannot recover the missing audio.

## Errors

| Message | Cause / fix |
|---|---|
| `ffmpeg was not found` | Install FFmpeg, add it to `PATH`, or set `FFMPEG_BINARY`; restart ComfyUI. |
| `FunASR is not available...` | Install FunASR in the exact interpreter shown in the message. |
| `Media file not found: ... Looked in:` | Put the file in `ComfyUI/input`, use an absolute path, or switch `source_type` to `url` with a direct media URL. |
| `The URL returned 'text/html', not media` | It is a web page, not a media file. Use a direct URL or yt-dlp. |
| `Download failed: HTTP 403/404` | The URL is private, expired or blocked; try a fresh direct link. |
| `Download is X MB, above the N MB limit` | Raise `max_download_mb` or download outside ComfyUI. |
| `SRT output needs timed segments` | Use `paraformer-zh` or connect VAD. |
| `device is set to 'cuda', but ... no usable CUDA device` | Select `cpu` or install a CUDA torch build. |
| `The connected VAD found no usable speech segments` | Lower `threshold_db` / `min_speech_ms` or disconnect `speech_segments`. |
| `output_dir must stay inside ComfyUI's output directory` | Use a relative folder or an absolute path. |
| `Cannot save the transcript as gbk` | The text contains characters outside GBK; use UTF-8. |
| `The output WAV would overwrite the input media` | Pick another filename/output folder. |
| `is a video-only track` / `has no audio stream` | The input is a video-only DASH/CDN track with no audio. The URL download nodes reject it immediately; for local files `FFmpeg Extract Audio` reports it. Use the yt-dlp node with the **page** URL. |
| `yt-dlp is not installed` | Run `python install.py`, or `python -m pip install -U yt-dlp` in ComfyUI's Python. |
| `yt-dlp failed ... Sign in` | The page needs cookies. Export `cookies.txt` and set `cookies_file`. |
| `yt-dlp failed ... video-only` | You passed a direct CDN link. Use the platform page URL. |
| `contains no audio or video streams` | The file is not media (web page/archive/unsupported container). |

Console lines are prefixed with `[Chinese Transcribe]` (model load time, device,
chunk counts, output paths).

## Limitations

- No speaker diarization, translation, or word-level karaoke timing yet.
- No upload widget; put files in `ComfyUI/input` or use a download node.
- Cues come from the model's sentence/character timing; long sentences are
  wrapped for display, not re-timed.
- The model returns text in the spoken language; `paraformer-zh` is Mandarin.
- Cached downloads: change a download widget or delete the file to force a
  fresh download.
- yt-dlp site extractors change often; update it (`pip install -U yt-dlp`) if a
  platform stops working. Login/region-locked pages may need a cookies file.
- Live streams are not supported well; use a finished video/page URL.
- Fun-ASR-Nano is newer and less battle-tested here; if its model id is
  rejected, update FunASR (`pip install -U funasr`).

## Development

The package has an offline test suite (no network, no FunASR model downloads).
FFmpeg-based tests are skipped automatically when `ffmpeg` is missing:

```bash
python -m unittest discover -s tests -v
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for the architecture, verified API
contracts, custom-type shapes and the roadmap.

## References

- [FunASR — models and AutoModel usage](https://github.com/modelscope/FunASR)
- [FunASR — model selection guide](https://modelscope.github.io/FunASR/model-selection.html)
- [SenseVoiceSmall — usage and languages](https://github.com/FunAudioLLM/SenseVoice)
- [FFmpeg — silencedetect filter](https://ffmpeg.org/ffmpeg-filters.html#silencedetect)
- [ComfyUI — custom node backend docs](https://docs.comfy.org/custom-nodes/backend/overview)
