#!/usr/bin/env bash
# Convenience launcher — activates the venv automatically.
# Usage: ./run.sh <youtube_url> [options]
# Example: ./run.sh "https://youtu.be/dQw4w9WgXcQ" --model small --format srt

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/venv"

if [ ! -f "$VENV/bin/python" ]; then
  echo "Error: venv not found at $VENV"
  echo "Run setup first: see README.md"
  exit 1
fi

exec "$VENV/bin/python" "$SCRIPT_DIR/transcribe.py" "$@"
