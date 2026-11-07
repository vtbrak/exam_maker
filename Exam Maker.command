#!/bin/bash
# Double-click to open Exam Maker.
# Runs in the "exam_maker" conda environment. If the environment is missing or its package list changed,
# it is created/updated first (Setup Exam Maker Environment.command), which takes a few minutes once.
cd "$(dirname "$0")" || exit 1

source ./find_conda.sh

case "$EXAM_ENV_STATUS" in
  no_conda)
    echo "Exam Maker runs in a conda environment, but Anaconda or Miniconda was not found on this Mac."
    echo "Install Miniconda from https://docs.conda.io/en/latest/miniconda.html, then double-click this file again."
    read -r -p "Press Return to close." _
    exit 1 ;;
  missing|outdated)
    ./"Setup Exam Maker Environment.command" --no-pause || {
      read -r -p "Environment setup failed (see above). Press Return to close." _
      exit 1; }
    source ./find_conda.sh ;;
esac

echo "Starting Exam Maker… (you can leave this window open; closing the app ends it)"
cd app || exit 1
"$EXAM_ENV_PREFIX/bin/python" -m exam_maker
STATUS=$?
if [ $STATUS -ne 0 ]; then
  read -r -p "Exam Maker stopped with an error (see above). Press Return to close." _
fi
