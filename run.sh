#!/usr/bin/env bash
# Convenience launcher — activates the venv automatically.
# Usage: ./run.sh <youtube_url> [options]
# Example: ./run.sh "https://youtu.be/dQw4w9WgXcQ" --model small --format srt

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/venv"

if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
  PYTHON="$VIRTUAL_ENV/bin/python"
elif [ -x "$VENV/bin/python" ]; then
  PYTHON="$VENV/bin/python"
else
  echo "Error: venv not found at $VENV"
  echo "Activate a virtual environment or create one at $VENV; see README.md"
  exit 1
fi

exec "$PYTHON" "$SCRIPT_DIR/transcribe.py" "$@"
