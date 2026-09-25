import sys
import os
import subprocess
import tempfile
import textwrap
import threading
import re
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk

MODEL_SIZE = "small"
MAX_CHARS_PER_LINE = 42
MAX_LINES_PER_BLOCK = 2
MIN_DURATION = 0.8
MAX_DURATION = 7.0
GAP_THRESHOLD = 0.3
SUPPORTED_EXTENSIONS = (
    ".mp4", ".mkv", ".avi", ".mov", ".wmv",
    ".flv", ".webm", ".m4v", ".mpg", ".mpeg"
)


def find_ffmpeg():
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        bundled = os.path.join(exe_dir, "ffmpeg.exe")
        if os.path.isfile(bundled):
            return bundled
    import shutil
    path = shutil.which("ffmpeg")
    if path:
        return path
    raise FileNotFoundError(
        "ffmpeg not found. On Windows place ffmpeg.exe next to the EXE. "
        "On Linux/Mac install ffmpeg via your package manager."
    )


def get_device():
    import torch
    if torch.cuda.is_available():
        return "cuda"
    try:
        if torch.version.hip and torch.cuda.is_available():
            return "cuda"  # ROCm exposes itself as cuda in PyTorch
    except Exception:
        pass
    return "cpu"


def extract_audio(video_path, ffmpeg_path, log):
    log("Extracting audio from video...")
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_name = tmp.name
    tmp.close()
    cmd = [
        ffmpeg_path, "-y",
        "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        tmp_name
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr.decode(errors='replace')}")
    log("Audio extracted successfully.")
    return tmp_name


def seconds_to_srt_time(s):
    s = max(0.0, s)
    hours = int(s // 3600)
    minutes = int((s % 3600) // 60)
    secs = int(s % 60)
    millis = int(round((s - int(s)) * 1000))
    if millis >= 1000:
        millis = 999
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def wrap_text(text):
    text = text.strip()
    if len(text) <= MAX_CHARS_PER_LINE:
        return text
    lines = textwrap.wrap(text, width=MAX_CHARS_PER_LINE)
    if len(lines) > MAX_LINES_PER_BLOCK:
        lines = lines[:MAX_LINES_PER_BLOCK]
    return "\n".join(lines)


def build_subtitle_blocks(segments):
    words = []
    for seg in segments:
        for w in seg.get("words", []):
            word_text = w.get("word", "").strip()
            if word_text:
                words.append({
                    "word": word_text,
                    "start": float(w["start"]),
                    "end": float(w["end"]),
                })

    if not words:
        return []

    blocks = []
    group_words = []
    group_start = 0.0

    for w in words:
        if not group_words:
            group_start = w["start"]

        accumulated = " ".join(cw["word"] for cw in group_words) + " " + w["word"]
        char_count = len(accumulated.strip())
        duration = w["end"] - group_start
        gap = (w["start"] - group_words[-1]["end"]) if group_words else 0.0

        should_flush = (
            (char_count > MAX_CHARS_PER_LINE * MAX_LINES_PER_BLOCK) or
            (duration > MAX_DURATION) or
            (gap > GAP_THRESHOLD and bool(group_words))
        )

        if should_flush and group_words:
            end_time = group_words[-1]["end"]
            text = " ".join(cw["word"] for cw in group_words)
            text = re.sub(r"\s+", " ", text).strip()
            text = re.sub(r"^\W+", "", text)
            if text:
                actual_end = end_time if (end_time - group_start) >= MIN_DURATION else group_start + MIN_DURATION
                blocks.append({"start": group_start, "end": actual_end, "text": wrap_text(text)})
            group_words = []
            group_start = w["start"]

        group_words.append(w)

    if group_words:
        end_time = group_words[-1]["end"]
        text = " ".join(cw["word"] for cw in group_words)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"^\W+", "", text)
        if text:
            actual_end = end_time if (end_time - group_start) >= MIN_DURATION else group_start + MIN_DURATION
            blocks.append({"start": group_start, "end": actual_end, "text": wrap_text(text)})

    return blocks


def write_srt(blocks, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        for i, block in enumerate(blocks, start=1):
            f.write(f"{i}\n")
            f.write(f"{seconds_to_srt_time(block['start'])} --> {seconds_to_srt_time(block['end'])}\n")
            f.write(f"{block['text']}\n\n")


def generate_subtitles(video_path, log, on_progress):
    import whisper
    import io
    import sys as _sys

    # In a windowed EXE sys.stderr is None — give tqdm something safe to write to
    # so it doesn't crash, while we intercept it for the progress bar
    if _sys.stderr is None:
        _sys.stderr = io.StringIO()

    class StderrCapture(io.TextIOBase):
        def __init__(self, original):
            self._original = original
            self._buf = ""

        def write(self, s):
            if self._original is not None:
                try:
                    self._original.write(s)
                    self._original.flush()
                except Exception:
                    pass
            self._buf += s
            parts = re.split(r"[\r\n]", self._buf)
            self._buf = parts[-1]
            for part in parts[:-1]:
                self._parse(part)
            return len(s)

        def flush(self):
            if self._original is not None:
                try:
                    self._original.flush()
                except Exception:
                    pass

        def fileno(self):
            raise io.UnsupportedOperation("fileno")

        def _parse(self, line):
            m = re.search(
                r"(\d+)%\|.*?\|\s*(\d+)/(\d+)\s*\[(\S+)<(\S+),\s*([\d.]+\S*)\]",
                line
            )
            if m:
                pct = int(m.group(1))
                current = int(m.group(2))
                total = int(m.group(3))
                elapsed = m.group(4)
                eta = m.group(5)
                speed = m.group(6)
                # sanity check — if current > total, they got swapped
                if current > total:
                    current, total = total, current
                on_progress(current, total, pct, elapsed, eta, speed)

    log(f"Processing: {os.path.basename(video_path)}")
    ffmpeg = find_ffmpeg()
    log("ffmpeg found.")
    audio_path = extract_audio(video_path, ffmpeg, log)

    old_stderr = _sys.stderr
    _sys.stderr = StderrCapture(old_stderr)

    try:
        if getattr(sys, "frozen", False):
            model_dir = os.path.join(os.path.dirname(sys.executable), "whisper_models")
        else:
            model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper_models")

        device = get_device()
        log(f"Device: {device.upper()}")
        log(f"Loading Whisper '{MODEL_SIZE}' model...")
        model = whisper.load_model(MODEL_SIZE, download_root=model_dir, device=device)
        log("Model loaded. Transcribing...")

        result = model.transcribe(
            audio_path,
            word_timestamps=True,
            verbose=False,
            condition_on_previous_text=True,
            temperature=0.0,
            compression_ratio_threshold=2.4,
            no_speech_threshold=0.6,
        )

        log("Transcription complete. Building subtitle blocks...")
        blocks = build_subtitle_blocks(result["segments"])

        if not blocks:
            log("No speech detected in the audio. SRT not written.")
            return None

        video_dir = os.path.dirname(os.path.abspath(video_path))
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        srt_path = os.path.join(video_dir, base_name + ".srt")
        write_srt(blocks, srt_path)

        lang = result.get("language", "unknown")
        log(f"Done! {len(blocks)} subtitle blocks written.")
        log(f"Detected language: {lang}")
        log(f"Output: {srt_path}")
        return srt_path

    finally:
        _sys.stderr = old_stderr
        try:
            os.unlink(audio_path)
        except OSError:
            pass

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Local Subtitle Generator")
        self.resizable(False, False)
        self.configure(bg="#1a1a2e")
        self._set_icon()
        self._build_ui()
        self._center_window()
        self._first_progress = True

    def _set_icon(self):
        try:
            if getattr(sys, "frozen", False):
                icon_path = os.path.join(sys._MEIPASS, "icon.ico")
            else:
                icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
            if os.path.isfile(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

    def _center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def _build_ui(self):
        PAD = 20
        BG = "#1a1a2e"
        CARD = "#16213e"
        ACCENT = "#e94560"
        TEXT = "#eaeaea"
        MUTED = "#888"

        header = tk.Frame(self, bg=BG, padx=PAD, pady=PAD)
        header.pack(fill="x")
        tk.Label(header, text="Local Subtitle Generator",
                 font=("Segoe UI", 22, "bold"), fg=ACCENT, bg=BG).pack(anchor="w")

        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x", padx=PAD)

        card = tk.Frame(self, bg=CARD, padx=PAD, pady=PAD)
        card.pack(fill="x", padx=PAD, pady=(PAD, 0))
        tk.Label(card, text="Video File", font=("Segoe UI Semibold", 10),
                 fg=TEXT, bg=CARD).pack(anchor="w")

        file_row = tk.Frame(card, bg=CARD)
        file_row.pack(fill="x", pady=(6, 0))

        self._file_var = tk.StringVar(value="No file selected")
        self._file_label = tk.Label(
            file_row, textvariable=self._file_var,
            font=("Consolas", 9), fg=MUTED, bg="#0f3460",
            anchor="w", padx=8, pady=6, width=55, relief="flat"
        )
        self._file_label.pack(side="left", fill="x", expand=True)

        tk.Button(
            file_row, text="Browse…", font=("Segoe UI Semibold", 11),
            bg=ACCENT, fg="white", relief="flat",
            activebackground="#c73652", activeforeground="white",
            padx=14, pady=4, cursor="hand2",
            command=self._browse
        ).pack(side="left", padx=(8, 0))

        tk.Label(card, text="Supported: MP4, MKV, AVI, MOV, WMV, FLV, WebM and more",
                 font=("Segoe UI", 8), fg=MUTED, bg=CARD).pack(anchor="w", pady=(4, 0))

        btn_frame = tk.Frame(self, bg=BG, padx=PAD, pady=12)
        btn_frame.pack(fill="x")
        self._gen_btn = tk.Button(
            btn_frame, text="Generate Subtitles",
            font=("Segoe UI Semibold", 13),
            bg=ACCENT, fg="white", relief="flat",
            activebackground="#c73652", activeforeground="white",
            padx=24, pady=10, cursor="hand2",
            command=self._start, state="disabled"
        )
        self._gen_btn.pack(fill="x")

        prog_card = tk.Frame(self, bg=CARD, padx=PAD, pady=14)
        prog_card.pack(fill="x", padx=PAD)

        top_row = tk.Frame(prog_card, bg=CARD)
        top_row.pack(fill="x")

        self._pct_var = tk.StringVar(value="0%")
        tk.Label(top_row, textvariable=self._pct_var,
                 font=("Segoe UI Semibold", 18), fg=TEXT, bg=CARD).pack(side="left")

        self._eta_var = tk.StringVar(value="")
        tk.Label(top_row, textvariable=self._eta_var,
                 font=("Consolas", 9), fg=MUTED, bg=CARD).pack(side="right", anchor="s", pady=(0, 4))

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "SF.Horizontal.TProgressbar",
            troughcolor="#0f3460",
            background="#e94560",
            bordercolor=CARD,
            lightcolor="#e94560",
            darkcolor="#e94560",
            thickness=16,
        )
        self._progress = ttk.Progressbar(
            prog_card, style="SF.Horizontal.TProgressbar",
            mode="determinate", maximum=100, value=0
        )
        self._progress.pack(fill="x", pady=(8, 6))

        self._frames_var = tk.StringVar(value="")
        tk.Label(prog_card, textvariable=self._frames_var,
                 font=("Consolas", 8), fg=MUTED, bg=CARD).pack(anchor="w")

        log_frame = tk.Frame(self, bg=BG, padx=PAD)
        log_frame.pack(fill="x", pady=(PAD, 0))
        tk.Label(log_frame, text="Log", font=("Segoe UI Semibold", 10),
                 fg=TEXT, bg=BG).pack(anchor="w")

        self._log_box = scrolledtext.ScrolledText(
            self, height=12, width=72,
            font=("Consolas", 9), bg="#0a0a1a", fg="#00e676",
            insertbackground="white", relief="flat",
            state="disabled", padx=8, pady=8
        )
        self._log_box.pack(fill="both", padx=PAD, pady=(4, PAD))

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var,
                 font=("Segoe UI", 9), fg=MUTED, bg=BG,
                 anchor="w", padx=PAD).pack(fill="x", pady=(0, 6))

        self._video_path = None

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select a video file",
            filetypes=[
                ("Video files", " ".join(f"*{e}" for e in SUPPORTED_EXTENSIONS)),
                ("All files", "*.*"),
            ]
        )
        if path:
            self._video_path = path
            self._file_var.set(os.path.basename(path))
            self._file_label.configure(fg="#eaeaea")
            self._gen_btn.configure(state="normal")
            self._status_var.set("File selected. Ready to generate.")

    def _log(self, msg):
        def _append():
            self._log_box.configure(state="normal")
            self._log_box.insert("end", msg + "\n")
            self._log_box.see("end")
            self._log_box.configure(state="disabled")
        self.after(0, _append)

    def _set_status(self, msg):
        self.after(0, lambda: self._status_var.set(msg))

    def _on_progress(self, current, total, pct, elapsed, eta, speed):
        def _update():
            if self._first_progress:
                self._first_progress = False
                self._progress.stop()
                self._progress.configure(mode="determinate", value=0)
            self._progress.configure(value=pct)
            self._pct_var.set(f"{pct}%")
            self._eta_var.set(f"Elapsed: {elapsed}   ETA: {eta}   {speed}")
            self._frames_var.set(f"{current:,} / {total:,} frames")
        self.after(0, _update)

    def _set_busy(self, busy):
        def _do():
            if busy:
                self._gen_btn.configure(state="disabled", text="Working…")
                self._progress.configure(mode="indeterminate")
                self._progress.start(12)
            else:
                self._progress.stop()
                self._progress.configure(mode="determinate")
                self._gen_btn.configure(state="normal", text="Generate Subtitles")
        self.after(0, _do)

    def _start(self):
        if not self._video_path:
            return
        self._first_progress = True
        self._set_busy(True)
        self._set_status("Processing…")
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            result = generate_subtitles(self._video_path, self._log, self._on_progress)
            if result:
                self.after(0, lambda: self._progress.configure(value=100))
                self.after(0, lambda: self._pct_var.set("100%"))
                self._set_status(f"Done — {os.path.basename(result)}")
            else:
                self._set_status("No speech detected.")
        except Exception as e:
            import traceback
            self._log(f"\n[ERROR] {e}")
            self._log(traceback.format_exc())
            self._set_status("Error — see log for details.")
        finally:
            self._set_busy(False)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()