# YT Transcriber

Transcribe **any** YouTube video to text using [yt-dlp](https://github.com/yt-dlp/yt-dlp) + [OpenAI Whisper](https://github.com/openai/whisper).  
Works even when the video has captions/transcripts **disabled** — it downloads the audio and runs speech recognition locally.

---

## Quick start

```bash
cd ~/Desktop/yt-transcriber
./run.sh "https://www.youtube.com/watch?v=VIDEO_ID"
```

The transcript is saved to `~/Desktop/<video_title>.txt` by default.

---

## Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--model` | `-m` | `small` | Whisper model size |
| `--format` | `-f` | `txt` | Output format: `txt`, `srt`, `vtt`, `tsv` |
| `--output` | `-o` | Desktop/<title> | Custom output path (no extension) |
| `--language` | `-l` | auto-detect | Force language, e.g. `en`, `fr`, `de` |
| `--keep-audio` | | off | Keep the downloaded MP3 alongside the transcript |

---

## Models — speed vs accuracy

| Model | Size | Speed (CPU) | Notes |
|-------|------|-------------|-------|
| `tiny` | 32 MB | Very fast | Low accuracy |
| `base` | 74 MB | Fast | OK for testing |
| `small` | 244 MB | Moderate | **Recommended** |
| `medium` | 769 MB | Slow | High accuracy |
| `large` | 1.5 GB | Very slow | Best accuracy |

First run downloads the model weights automatically to `~/.cache/whisper/`.

---

## Examples

```bash
# Plain text transcript (default)
./run.sh "https://youtu.be/VIDEO_ID"

# SRT subtitles with timestamps
./run.sh "https://youtu.be/VIDEO_ID" --format srt

# Use a larger model for better accuracy
./run.sh "https://youtu.be/VIDEO_ID" --model medium

# Force English, save to a custom path
./run.sh "https://youtu.be/VIDEO_ID" --language en --output ~/Documents/my_transcript

# Keep the downloaded audio too
./run.sh "https://youtu.be/VIDEO_ID" --keep-audio
```

---

## Output formats

- **txt** — readable paragraphs, one per ~5 segments  
- **srt** — SubRip subtitles with timestamps (for video players)  
- **vtt** — WebVTT subtitles (for web/browsers)  
- **tsv** — tab-separated with precise start/end times in seconds
