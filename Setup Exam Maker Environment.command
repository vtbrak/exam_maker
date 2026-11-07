#!/bin/bash
# Create (or update) the "exam_maker" conda environment from app/environment.yml.
# Double-click to run. "Exam Maker.command" also calls this automatically when needed (with --no-pause).
# Options:  --no-pause  don't wait for Return at the end
#           --rebuild   delete the environment and build it fresh (removes leftover packages an update can't)
cd "$(dirname "$0")" || exit 1

NO_PAUSE=0; REBUILD=0
for arg in "$@"; do
  case "$arg" in
    --no-pause) NO_PAUSE=1 ;;
    --rebuild)  REBUILD=1 ;;
  esac
done
pause() { [ "$NO_PAUSE" = 1 ] || read -r -p "Press Return to close." _; }

source ./find_conda.sh

if [ "$REBUILD" = 1 ] && [ "$EXAM_ENV_STATUS" != "no_conda" ] && [ "$EXAM_ENV_STATUS" != "missing" ]; then
  echo "Removing the '$EXAM_ENV_NAME' environment so it can be rebuilt from scratch…"
  "$CONDA_EXE" env remove -y -n "$EXAM_ENV_NAME" || { echo "Couldn't remove the environment."; pause; exit 1; }
  EXAM_ENV_STATUS="missing"
fi

case "$EXAM_ENV_STATUS" in
  no_conda)
    echo "Anaconda or Miniconda was not found on this Mac."
    echo "Install Miniconda from https://docs.conda.io/en/latest/miniconda.html, then run this again."
    pause; exit 2 ;;
  missing)
    echo "Creating the '$EXAM_ENV_NAME' conda environment (first time only; a few minutes)…"
    "$CONDA_EXE" env create -n "$EXAM_ENV_NAME" -f "$EXAM_ENV_FILE" ;;
  ready|outdated)
    echo "Updating the '$EXAM_ENV_NAME' conda environment to match app/environment.yml…"
    "$CONDA_EXE" env update -n "$EXAM_ENV_NAME" -f "$EXAM_ENV_FILE" --prune ;;
esac
STATUS=$?

if [ $STATUS -ne 0 ]; then
  echo
  echo "Setup failed (see the messages above). Check your internet connection and try again."
  pause; exit 1
fi

# Re-check to pick up the environment's location, then record that it matches the current package list.
source ./find_conda.sh
if [ -z "$EXAM_ENV_PREFIX" ] || ! "$EXAM_ENV_PREFIX/bin/python" -c "import tkinter, customtkinter, reportlab, docx, openpyxl, pymupdf, PIL" 2>/dev/null; then
  echo "The environment was created but a package is missing. Run this setup again."
  pause; exit 1
fi
exam_env_fingerprint > "$EXAM_ENV_PREFIX/$EXAM_ENV_STAMP_NAME"

echo
echo "Done. The '$EXAM_ENV_NAME' environment is ready at $EXAM_ENV_PREFIX"
pause
exit 0
