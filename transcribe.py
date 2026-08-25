#!/usr/bin/env python3
"""
yt-transcriber — Transcribe any YouTube video using yt-dlp + OpenAI Whisper.
Works regardless of whether the video has captions enabled or not.

Usage:
    python transcribe.py <youtube_url> [options]

Examples:
    python transcribe.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    python transcribe.py "https://youtu.be/dQw4w9WgXcQ" --model medium --format srt
    python transcribe.py "https://youtu.be/dQw4w9WgXcQ" --output ~/Desktop/my_transcript
"""

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

# ── Colour helpers (no external deps) ────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
RED    = "\033[31m"
DIM    = "\033[2m"

def info(msg):    print(f"{CYAN}  ›{RESET} {msg}")
def success(msg): print(f"{GREEN}  ✓{RESET} {BOLD}{msg}{RESET}")
def warn(msg):    print(f"{YELLOW}  ⚠{RESET}  {msg}")
def error(msg):   print(f"{RED}  ✗{RESET}  {msg}", file=sys.stderr)
def step(msg):    print(f"\n{BOLD}{CYAN}──{RESET} {BOLD}{msg}{RESET}")

# ── Audio download via yt-dlp ─────────────────────────────────────────────────

def download_audio(url: str, out_dir: str) -> tuple[str, dict]:
    """
    Download best-quality audio from a YouTube URL.
    Returns (audio_filepath, video_metadata).
    """
    try:
        import yt_dlp
    except ImportError:
        error("yt-dlp is not installed. Run: pip install yt-dlp")
        sys.exit(1)

    audio_path_holder = {}

    class QuietLogger:
        def debug(self, msg):
            # show download progress lines only
            if msg.startswith("[download]"):
                print(f"  {DIM}{msg}{RESET}", end="\r")
        def warning(self, msg):
            if "deprecated" not in msg.lower():
                warn(msg)
        def error(self, msg):
            error(msg)

    def progress_hook(d):
        if d["status"] == "downloading":
            pct     = d.get("_percent_str", "?%").strip()
            speed   = d.get("_speed_str", "").strip()
            eta     = d.get("_eta_str", "").strip()
            total   = d.get("_total_bytes_str", d.get("_total_bytes_estimate_str", "")).strip()
            line    = f"  {DIM}Downloading audio: {pct} of {total}  {speed}  ETA {eta}{RESET}   "
            print(line, end="\r")
        elif d["status"] == "finished":
            print(" " * 80, end="\r")  # clear the progress line
            audio_path_holder["path"] = d["filename"]

    template = os.path.join(out_dir, "%(id)s.%(ext)s")

    ydl_opts = {
        "format":           "bestaudio/best",
        "outtmpl":          template,
        "postprocessors":   [{
            "key":            "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "logger":           QuietLogger(),
        "progress_hooks":   [progress_hook],
        "no_warnings":      False,
        "noplaylist":       True,
        "no_update":        True,
        "quiet":            True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        meta = ydl.extract_info(url, download=True)

    # yt-dlp changes extension after postprocessing → find the mp3
    video_id = meta.get("id", "audio")
    mp3_path = os.path.join(out_dir, f"{video_id}.mp3")

    if not os.path.exists(mp3_path):
        # fallback: find any audio file in out_dir matching the id
        candidates = list(Path(out_dir).glob(f"{video_id}.*"))
        if not candidates:
            raise FileNotFoundError(f"Could not find downloaded audio for video id '{video_id}'")
        mp3_path = str(candidates[0])

    return mp3_path, meta


# ── Transcription via Whisper ─────────────────────────────────────────────────

def transcribe_audio(audio_path: str, model_name: str, language: str | None) -> dict:
    """
    Run Whisper on the audio file.
    Returns the full result dict (text, segments, language).
    """
    try:
        import whisper
    except ImportError:
        error("openai-whisper is not installed. Run: pip install openai-whisper")
        sys.exit(1)

    info(f"Loading Whisper model '{model_name}' …  (first run downloads the model weights)")
    model = whisper.load_model(model_name)

    info("Transcribing audio …  (this may take a while on CPU)")
    t0 = time.time()

    kwargs = {"verbose": False}
    if language:
        kwargs["language"] = language

    result = model.transcribe(audio_path, **kwargs)

    elapsed = time.time() - t0
    info(f"Transcription finished in {elapsed:.1f}s  |  detected language: {result.get('language', 'unknown')}")

    return result


# ── Output formatters ─────────────────────────────────────────────────────────

def format_txt(result: dict) -> str:
    """Plain text — paragraph per 5 sentences."""
    segments = result.get("segments", [])
    if not segments:
        return result.get("text", "").strip()

    lines = []
    buf   = []
    for i, seg in enumerate(segments):
        buf.append(seg["text"].strip())
        # new paragraph roughly every 5 segments
        if (i + 1) % 5 == 0:
            lines.append(" ".join(buf))
            buf = []
    if buf:
        lines.append(" ".join(buf))

    return "\n\n".join(lines)


def format_srt(result: dict) -> str:
    """SRT subtitle format."""
    segments = result.get("segments", [])
    blocks   = []
    for i, seg in enumerate(segments, 1):
        start = _srt_time(seg["start"])
        end   = _srt_time(seg["end"])
        text  = seg["text"].strip()
        blocks.append(f"{i}\n{start} --> {end}\n{text}")
    return "\n\n".join(blocks)


def format_vtt(result: dict) -> str:
    """WebVTT subtitle format."""
    segments = result.get("segments", [])
    blocks   = ["WEBVTT\n"]
    for seg in segments:
        start = _vtt_time(seg["start"])
        end   = _vtt_time(seg["end"])
        text  = seg["text"].strip()
        blocks.append(f"{start} --> {end}\n{text}")
    return "\n\n".join(blocks)


def format_tsv(result: dict) -> str:
    """Tab-separated: start(s) \\t end(s) \\t text"""
    rows = ["start\tend\ttext"]
    for seg in result.get("segments", []):
        rows.append(f"{seg['start']:.3f}\t{seg['end']:.3f}\t{seg['text'].strip()}")
    return "\n".join(rows)


def _srt_time(seconds: float) -> str:
    ms  = int((seconds % 1) * 1000)
    s   = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _vtt_time(seconds: float) -> str:
    ms  = int((seconds % 1) * 1000)
    s   = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


FORMATTERS = {
    "txt": (format_txt, ".txt"),
    "srt": (format_srt, ".srt"),
    "vtt": (format_vtt, ".vtt"),
    "tsv": (format_tsv, ".tsv"),
}

# ── Safe filename ─────────────────────────────────────────────────────────────

def safe_filename(title: str, max_len: int = 80) -> str:
    keep = set(" abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_()")
    name = "".join(c if c in keep else "_" for c in title).strip("_").strip()
    return name[:max_len] or "transcript"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Transcribe any YouTube video using Whisper ASR.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Whisper models (speed vs accuracy trade-off):
  tiny    — fastest, least accurate (~32MB)
  base    — good for quick tests (~74MB)
  small   — balanced  (~244MB)  ← recommended default
  medium  — more accurate, slower (~769MB)
  large   — most accurate, slowest (~1.5GB)

Output formats:
  txt — plain text paragraphs
  srt — SubRip subtitles (timestamps)
  vtt — WebVTT subtitles
  tsv — tab-separated with start/end times
        """,
    )

    parser.add_argument("url",
        help="YouTube video URL")
    parser.add_argument("--model", "-m",
        default="small",
        choices=["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"],
        help="Whisper model to use (default: small)")
    parser.add_argument("--format", "-f",
        default="txt",
        choices=list(FORMATTERS.keys()),
        dest="fmt",
        help="Output format: txt, srt, vtt, tsv (default: txt)")
    parser.add_argument("--output", "-o",
        default=None,
        help="Output file path (without extension). Defaults to Desktop/<video_title>")
    parser.add_argument("--language", "-l",
        default=None,
        help="Force a language code, e.g. 'en', 'fr', 'de'. Auto-detects if omitted.")
    parser.add_argument("--keep-audio",
        action="store_true",
        help="Keep the downloaded audio file after transcription")

    args = parser.parse_args()

    # ── Banner
    print(f"\n{BOLD}  YT Transcriber — powered by yt-dlp + OpenAI Whisper{RESET}")
    print(f"  {DIM}URL   : {args.url}{RESET}")
    print(f"  {DIM}Model : {args.model}  |  Format : {args.fmt}{RESET}\n")

    # ── Step 1: download audio
    step("Step 1 / 2 — Downloading audio")
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            audio_path, meta = download_audio(args.url, tmp_dir)
        except Exception as exc:
            error(f"Download failed: {exc}")
            sys.exit(1)

        title    = meta.get("title", "transcript")
        duration = meta.get("duration", 0)
        channel  = meta.get("uploader") or meta.get("channel") or ""

        success(f"Audio downloaded  ({duration // 60}m {duration % 60}s)")
        info(f"Title  : {title}")
        if channel:
            info(f"Channel: {channel}")

        # ── Step 2: transcribe
        step("Step 2 / 2 — Transcribing with Whisper")
        try:
            result = transcribe_audio(audio_path, args.model, args.language)
        except Exception as exc:
            error(f"Transcription failed: {exc}")
            sys.exit(1)

        # ── Format output
        formatter, ext = FORMATTERS[args.fmt]
        content = formatter(result)

        # ── Determine output path
        if args.output:
            out_path = Path(args.output).expanduser().with_suffix(ext)
        else:
            desktop  = Path.home() / "Desktop"
            out_path = desktop / (safe_filename(title) + ext)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")

        # ── Keep audio?
        if args.keep_audio:
            import shutil
            audio_dest = out_path.with_suffix(Path(audio_path).suffix)
            shutil.copy2(audio_path, audio_dest)
            info(f"Audio saved to : {audio_dest}")

    # ── Done
    print()
    success(f"Transcript saved → {out_path}")
    word_count = len(content.split())
    info(f"Words: ~{word_count:,}")
    print()


if __name__ == "__main__":
    main()
