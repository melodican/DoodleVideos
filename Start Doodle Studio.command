#!/bin/bash
# Double-click launcher for Doodle Studio (macOS).
# Spins up the venv + Flask dashboard and opens it in your browser.
# Close this Terminal window (or press Ctrl-C) to stop the server.

# Always run from the folder this script lives in.
cd "$(dirname "$0")" || { echo "Could not find the project folder."; read -r; exit 1; }

PORT="${PORT:-8000}"          # 8000 avoids the macOS AirPlay clash on 5000
URL="http://localhost:$PORT"

# First run (or a fresh checkout): create the venv and install dependencies.
if [ ! -x ".venv/bin/python" ]; then
  echo "First run — setting up the Python environment (this can take a minute)…"
  python3 -m venv .venv || { echo "Could not create the virtual environment."; read -r; exit 1; }
  ".venv/bin/python" -m pip install --quiet --upgrade pip
  ".venv/bin/python" -m pip install --quiet -r requirements.txt || {
    echo "Dependency install failed — see the messages above."; read -r; exit 1; }
fi

# Open the browser as soon as the server is actually listening.
(
  for _ in $(seq 1 60); do
    if curl -s -o /dev/null "$URL"; then open "$URL"; break; fi
    sleep 0.5
  done
) &

echo "🎬 Doodle Studio → $URL"
echo "   (leave this window open; close it or press Ctrl-C to stop)"
echo

# Hand control to Flask in the foreground so closing the window stops it.
exec ".venv/bin/python" -m dashboard.app
