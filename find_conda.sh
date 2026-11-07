#!/bin/bash
# Find conda (Anaconda / Miniconda / Miniforge) and check for the Exam Maker environment.
#
# Run it:     ./find_conda.sh       prints a report and exits with:
#                                     0 = environment ready
#                                     1 = conda found, environment missing (run the Setup .command)
#                                     2 = conda not found
#                                     3 = environment present but out of date (package list changed)
# Source it:  source find_conda.sh  sets these for the other scripts, without printing:
#               CONDA_EXE, CONDA_BASE, EXAM_ENV_NAME, EXAM_ENV_PREFIX, EXAM_ENV_FILE, EXAM_ENV_STATUS
#               (status is one of: ready, missing, outdated, no_conda)

EXAM_ENV_NAME="${EXAM_ENV_NAME:-exam_maker}"
_EM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAM_ENV_FILE="$_EM_DIR/app/environment.yml"
EXAM_REQS_FILE="$_EM_DIR/app/requirements.txt"
EXAM_ENV_STAMP_NAME=".exam_maker_env_stamp"   # stored inside the environment after a successful setup

# Fingerprint of the package lists; the environment is "outdated" when it doesn't match the stamp.
exam_env_fingerprint() {
  cat "$EXAM_ENV_FILE" "$EXAM_REQS_FILE" 2>/dev/null | md5 -q 2>/dev/null || cat "$EXAM_ENV_FILE" "$EXAM_REQS_FILE" | md5sum | cut -d' ' -f1
}

_find_conda_exe() {
  local c
  for c in \
    "$CONDA_EXE" \
    "$(command -v conda 2>/dev/null)" \
    "$HOME/anaconda3/bin/conda" \
    "$HOME/miniconda3/bin/conda" \
    "$HOME/miniforge3/bin/conda" \
    "$HOME/mambaforge/bin/conda" \
    "$HOME/opt/anaconda3/bin/conda" \
    "$HOME/opt/miniconda3/bin/conda" \
    "/opt/anaconda3/bin/conda" \
    "/opt/miniconda3/bin/conda" \
    "/opt/miniforge3/bin/conda" \
    "/opt/homebrew/Caskroom/miniconda/base/bin/conda" \
    "/opt/homebrew/Caskroom/miniforge/base/bin/conda" \
    "/opt/homebrew/anaconda3/bin/conda" \
    "/usr/local/Caskroom/miniconda/base/bin/conda" \
    "/usr/local/anaconda3/bin/conda" \
    "/usr/local/miniconda3/bin/conda"; do
    if [ -n "$c" ] && [ -x "$c" ] && [ -f "$c" ]; then
      echo "$c"
      return 0
    fi
  done
  return 1
}

CONDA_EXE="$(_find_conda_exe)"
CONDA_BASE=""
EXAM_ENV_PREFIX=""
if [ -z "$CONDA_EXE" ]; then
  EXAM_ENV_STATUS="no_conda"
else
  CONDA_BASE="$("$CONDA_EXE" info --base 2>/dev/null)"
  # `conda env list` lines look like:  name   [*]   /path/to/env   (first column is the name)
  EXAM_ENV_PREFIX="$("$CONDA_EXE" env list 2>/dev/null | awk -v n="$EXAM_ENV_NAME" '$1 == n {print $NF; exit}')"
  if [ -z "$EXAM_ENV_PREFIX" ] || [ ! -x "$EXAM_ENV_PREFIX/bin/python" ]; then
    EXAM_ENV_STATUS="missing"
  elif [ "$(cat "$EXAM_ENV_PREFIX/$EXAM_ENV_STAMP_NAME" 2>/dev/null)" != "$(exam_env_fingerprint)" ]; then
    EXAM_ENV_STATUS="outdated"
  else
    EXAM_ENV_STATUS="ready"
  fi
fi
export CONDA_EXE CONDA_BASE EXAM_ENV_NAME EXAM_ENV_PREFIX EXAM_ENV_FILE EXAM_ENV_STATUS

# Run directly (not sourced): print a report and exit with the status code.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  echo "Exam Maker environment check"
  echo "  conda:        ${CONDA_EXE:-not found}"
  [ -n "$CONDA_BASE" ] && echo "  conda base:   $CONDA_BASE"
  echo "  environment:  $EXAM_ENV_NAME${EXAM_ENV_PREFIX:+  ($EXAM_ENV_PREFIX)}"
  case "$EXAM_ENV_STATUS" in
    ready)    echo "  status:       READY - the environment exists and matches app/environment.yml"; exit 0 ;;
    missing)  echo "  status:       MISSING - double-click 'Setup Exam Maker Environment.command' to create it"; exit 1 ;;
    no_conda) echo "  status:       CONDA NOT FOUND - install Anaconda or Miniconda (https://docs.conda.io/en/latest/miniconda.html)"; exit 2 ;;
    outdated) echo "  status:       OUT OF DATE - the package list changed; run 'Setup Exam Maker Environment.command' to update"; exit 3 ;;
  esac
fi
