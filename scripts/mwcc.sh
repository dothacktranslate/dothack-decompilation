#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

WIBO="$ROOT/tools/wibo"
MWCC="$ROOT/tools/mwcc/mwccps2.exe"

if [ ! -x "$WIBO" ]; then
    echo "ERROR: wibo was not found or is not executable:"
    echo "  $WIBO"
    exit 1
fi

if [ ! -f "$MWCC" ]; then
    echo "ERROR: Metrowerks compiler was not found:"
    echo "  $MWCC"
    echo
    echo "Place the private compiler at:"
    echo "  tools/mwcc/mwccps2.exe"
    exit 1
fi

exec "$WIBO" "$MWCC" "$@"
