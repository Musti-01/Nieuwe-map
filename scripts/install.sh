#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install --cache-dir "${PIP_CACHE_DIR:-/workspace/.pip-cache}" --require-hashes -r requirements.lock
