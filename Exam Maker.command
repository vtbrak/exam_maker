#!/bin/bash
# Double-click to open Exam Maker. The first run sets up Python packages (about a minute).
cd "$(dirname "$0")/app" || exit 1

VENV=".venv"
STAMP="$VENV/.requirements-installed"

find_python() {
  for c in /opt/miniconda3/bin/python3 "$HOME/miniconda3/bin/python3" "$HOME/anaconda3/bin/python3" \
           /opt/homebrew/bin/python3 /usr/local/bin/python3 \
           /Library/Frameworks/Python.framework/Versions/Current/bin/python3 "$(command -v python3)"; do
    if [ -x "$c" ] && "$c" -c 'import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      echo "$c"; return 0
    fi
  done
  return 1
}

if [ ! -x "$VENV/bin/python" ]; then
  PY="$(find_python)" || {
    echo "Exam Maker needs Python 3.10 or newer with Tk (tkinter)."
    echo "Install it from https://www.python.org/downloads/macos/ and double-click this file again."
    read -r -p "Press Return to close." _; exit 1; }
  echo "Setting up Exam Maker (first run only)…"
  "$PY" -m venv "$VENV" || { read -r -p "Setup failed. Press Return to close." _; exit 1; }
fi

if [ ! -f "$STAMP" ] || [ requirements.txt -nt "$STAMP" ]; then
  echo "Installing packages…"
  "$VENV/bin/python" -m pip install --quiet --upgrade pip &&
  "$VENV/bin/python" -m pip install --quiet -r requirements.txt &&
  touch "$STAMP" || { read -r -p "Package install failed (check your internet connection). Press Return to close." _; exit 1; }
fi

echo "Starting Exam Maker… (you can leave this window open; closing the app ends it)"
"$VENV/bin/python" -m exam_maker
STATUS=$?
if [ $STATUS -ne 0 ]; then
  read -r -p "Exam Maker stopped with an error (see above). Press Return to close." _
fi
