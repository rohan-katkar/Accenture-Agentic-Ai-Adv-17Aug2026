#!/usr/bin/env bash
# One-command setup: Linux / macOS / Codespaces terminal / WSL2.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
$PY -m venv .venv
./.venv/bin/pip install --upgrade pip -q
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python common/data_gen.py
./.venv/bin/python -m pytest tests/ -q
echo "Setup complete - 17/17 acceptance tests must show above."
