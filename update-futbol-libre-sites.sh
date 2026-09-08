#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"
source "$(pwd)/config.sh"

exec "$PYTHON_VENV" src/search_sites.py
