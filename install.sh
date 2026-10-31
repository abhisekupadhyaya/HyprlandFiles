#!/bin/sh
# Run from a reviewed checkout; do not pipe this file into a shell.
set -eu
PROJECT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Python 3 is required (included with Ubuntu Server).'
    exit 1
fi
exec python3 "$PROJECT_DIR/tools/installer.py" "$@"
