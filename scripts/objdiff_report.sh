#!/usr/bin/env bash
set -euo pipefail

ROOT="$(
    cd "$(dirname "${BASH_SOURCE[0]}")/.." &&
    pwd
)"

cd "$ROOT"

source .venv/bin/activate

python3 scripts/configure_objdiff.py

mkdir -p build/objdiff

objdiff-cli report generate \
    -p "$ROOT" \
    -o "$ROOT/build/objdiff/report.json"
