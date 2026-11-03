#!/usr/bin/env bash
# Start RoleEdge on http://localhost:8100 (PORT=8200 bash run.sh for another port).
# The first run makes a Python environment in .venv and installs the app (a few minutes).
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8100}"

PY=""
for candidate in python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
    PY="$candidate"; break
  fi
done
if [ -z "$PY" ]; then
  echo "RoleEdge needs Python 3.11 or newer: python.org, or on a Mac: brew install python@3.12"; exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Note: ffmpeg isn't installed, so videos, reel links and voice recordings won't work"
  echo "      (Mac: brew install ffmpeg, Linux: sudo apt install ffmpeg). Typed messages and web pages still do."
fi

if [ ! -x .venv/bin/roleedge ]; then
  echo "First run: installing RoleEdge into .venv ..."
  "$PY" -m venv .venv
  .venv/bin/python -m pip install --quiet --upgrade pip
  .venv/bin/python -m pip install --quiet -e .
fi

[ -f .env ] || cp .env.example .env
if ! grep -Eq '^META_API_KEY="?[^"[:space:]]+' .env; then
  echo "Add your Meta Model API key to the .env file in this folder (META_API_KEY=\"...\"), then run this again."; exit 1
fi
echo "Checking the Meta key ..."
.venv/bin/roleedge check || { echo "The Meta key didn't work (see above)."; exit 1; }

echo
echo "RoleEdge is starting. Open http://localhost:$PORT"
echo "  caregiver: http://localhost:$PORT/studio      Linda's phone: http://localhost:$PORT/phone/chen"
echo "  Japanese family's phone: http://localhost:$PORT/phone/sato      tuning lab: http://localhost:$PORT/lab"
echo "Stop it with Ctrl+C."
exec .venv/bin/roleedge serve --port "$PORT"
