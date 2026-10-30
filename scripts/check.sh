#!/bin/sh
set -eu
PROJECT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_DIR"
python3 scripts/audit_public.py
sh -n install.sh
sh -n scripts/check.sh
PYTHONPATH="$PROJECT_DIR/controller:$PROJECT_DIR/tools:$PROJECT_DIR/python${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m unittest discover -s tests -v
if command -v shellcheck >/dev/null 2>&1; then
    shellcheck install.sh scripts/check.sh bin/hf-polkit
fi
