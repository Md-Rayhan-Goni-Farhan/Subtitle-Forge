# SubtitleForge

**Local AI subtitle generator. No internet, no API key, no cloud. Runs entirely on your CPU.**

Drop any video file onto the EXE and get a properly timed `.srt` subtitle file in seconds — the same folder as your video, same filename. Open it in VLC, Plex, or any media player.

---

## Download

**[→ Download SubtitleForge_release.zip from Releases](../../releases/latest)**

Extract the ZIP. Drag a video onto `SubtitleForge.exe`. That's it.

---

## Demo

**Input** — a raw MP4 file with no subtitles:

```
interview_clip.mp4
```

**Output** — `interview_clip.srt` generated automatically:

```srt
1
00:00:01,240 --> 00:00:04,180
The interesting thing about machine learning
is how little data you actually need.

2
00:00:04,620 --> 00:00:07,900
Most people assume you need millions of examples,
but that's not always true.

3
00:00:08,350 --> 00:00:11,410
With transfer learning, a few hundred
labelled samples can be enough.

4
00:00:12,100 --> 00:00:15,760
The real challenge is the quality
of your labels, not the quantity.
```

Load the SRT in VLC: `Subtitle → Add Subtitle File` — the text appears in sync with the speech, properly line-broken, naturally timed.

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

---

## License

MIT
