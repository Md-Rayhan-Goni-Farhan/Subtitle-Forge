# SubtitleForge

**Local AI subtitle generator. Just choose your video and watch the magic unfold**

Open the exe app, choose your video, hit generate and get a properly timed `.srt` subtitle file in seconds — the same folder as your video, same filename. Open it in VLC, Plex, or any media player and Enjoy!

---

## Download

**[→ Download SubtitleForge_release.zip from Releases](../../releases/latest)**

Extract the ZIP. Click on the exe, browse your video and select it and hit generate.

---

## How It Works

1. **Audio extraction** — ffmpeg strips the audio track from the video file into a 16kHz mono WAV
2. **Transcription** — OpenAI Whisper (`small` model) runs locally on CPU with word-level timestamps enabled
3. **Subtitle segmentation** — a custom segmentation pass groups words into blocks using natural speech pause detection, character-count limits, and duration caps — not sentence-dumping
4. **SRT output** — blocks are written to standard SRT format with millisecond-accurate timestamps

No data ever leaves your machine.

---

## Subtitle Formatting Rules

The output follows broadcast subtitle conventions:

| Parameter | Value |
|-----------|-------|
| Max characters per line | 42 |
| Max lines per block | 2 |
| Minimum display duration | 0.8 seconds |
| Maximum display duration | 7.0 seconds |
| Pause gap that splits a block | 0.3 seconds |

---

## Supported Formats

**Video input:** MP4, MKV, AVI, MOV, WMV, FLV, WebM — anything ffmpeg can open (essentially everything)

**Languages:** Whisper `small` supports 99 languages including English, Arabic, Spanish, French, German, Japanese, Chinese, Hindi, Bengali, Portuguese, Russian, and more. Language is auto-detected.

**Model accuracy:** The `small` model (244M parameters) achieves word error rates competitive with human transcription on clean audio. Accuracy degrades with heavy background noise, strong accents, or very low audio quality.

---

## System Requirements

- Windows 10 or 11 (64-bit)
- ~2GB free disk space (model weights are bundled)
- ~4GB RAM minimum
- No GPU required — runs entirely on CPU
- No Python, no internet connection, no installation

---

## Building From Source

If you want to build the EXE yourself:

```bash
git clone https://github.com/yourusername/SubtitleForge
cd SubtitleForge
setup_dev.bat
```

`setup_dev.bat` installs all Python dependencies, downloads the Whisper model weights, builds the EXE with PyInstaller, and packages the release ZIP automatically.

---

## Architecture Notes

The bundled EXE is built with PyInstaller in one-directory mode. The model weights (`small.pt`, ~460MB) are stored in a `whisper_models/` subfolder alongside the EXE. The `ffmpeg.exe` static binary is also bundled — no system-level installation required for any component.

The transcription pipeline uses Whisper's word-level timestamp mode (`word_timestamps=True`) rather than segment-level timestamps. This gives per-word timing information that the segmentation pass uses to construct subtitle blocks that align precisely with speech, rather than grouping by Whisper's internal segment boundaries which are often too long for subtitle display.

