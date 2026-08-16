#!/usr/bin/env bash
# =====================================================================
# One-command bootstrap for macOS, Linux, WSL and Azure ML compute.
#   bash setup.sh              create a venv and install
#   bash setup.sh --conda      use conda instead (Azure ML compute default)
#   bash setup.sh --no-corpus  skip building the Day 2 vector collection
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")"

USE_CONDA=false
BUILD_CORPUS=true
for arg in "$@"; do
  case "$arg" in
    --conda)     USE_CONDA=true ;;
    --no-corpus) BUILD_CORPUS=false ;;
    *) echo "unknown option: $arg"; exit 2 ;;
  esac
done

echo "=== 1. Python environment ==="
if $USE_CONDA; then
  if ! command -v conda >/dev/null 2>&1; then
    echo "conda not found. Re-run without --conda to use a venv."; exit 1
  fi
  conda env create -f environment.yml -n agentic-batch1 2>/dev/null \
    || conda env update -f environment.yml -n agentic-batch1
  echo "Activate with:  conda activate agentic-batch1"
  PY="conda run -n agentic-batch1 python"
else
  PYBIN="${PYTHON:-python3}"
  VER=$($PYBIN -c 'import sys;print("%d.%d"%sys.version_info[:2])')
  case "$VER" in
    3.11|3.12) echo "Python $VER OK" ;;
    *) echo "Python $VER found. This package needs 3.11 or 3.12."; exit 1 ;;
  esac
  [ -d .venv ] || $PYBIN -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  echo "Activate later with:  source .venv/bin/activate"
  PY="python"
  $PY -m pip install --upgrade pip --quiet
  $PY -m pip install -r 00_Program/requirements.txt
fi

echo
echo "=== 2. Configuration ==="
if [ -f .env ]; then
  echo ".env already exists - left untouched."
else
  cp 00_Program/.env.example .env
  echo "Created .env from the template."
  echo "Edit it to add AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY,"
  echo "or set LAB_OFFLINE_MODE=true to run everything without Azure."
fi

echo
if $BUILD_CORPUS; then
  echo "=== 3. Day 2 remittance corpus ==="
  # Day 2 Lab 3 onward and the whole Capstone read this collection.
  $PY Day2_RAG/solutions/lab01_vector_ingestion.py >/dev/null 2>&1 \
    && echo "Vector collection built." \
    || echo "Skipped - run Day2_RAG/solutions/lab01_vector_ingestion.py manually."
  echo
fi

echo "=== 4. Verification ==="
$PY 00_Program/verify_environment.py || true

echo
echo "Next:  python Day1_Foundations/labs/lab01_environment_and_telemetry.py"
