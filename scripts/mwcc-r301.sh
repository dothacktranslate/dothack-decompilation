#!/usr/bin/env bash
set -euo pipefail

ROOT="$(
    cd "$(dirname "${BASH_SOURCE[0]}")/.." &&
    pwd
)"

WIBO="$ROOT/tools/wibo"
MWCC="${MWCC_R301:-$ROOT/tools/mwcc/r301/mwccps2.exe}"

if [ ! -x "$WIBO" ]; then
    echo "ERROR: Wibo not found:" >&2
    echo "  $WIBO" >&2
    exit 1
fi

if [ ! -f "$MWCC" ]; then
    echo "ERROR: CodeWarrior PS2 R3.01 compiler not found:" >&2
    echo "  $MWCC" >&2
    echo >&2
    echo "Install the local compiler under tools/mwcc/r301/" >&2
    echo "or set MWCC_R301 to its mwccps2.exe path." >&2
    exit 1
fi

cd "$(dirname "$MWCC")"

exec \
    "$WIBO" \
    "./$(basename "$MWCC")" \
    "$@"
