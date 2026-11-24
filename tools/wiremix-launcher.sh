#!/bin/sh
# Some SSH sessions omit XDG_RUNTIME_DIR. Use the existing per-user PipeWire socket.
if [ -z "${PIPEWIRE_RUNTIME_DIR:-}" ] && [ -z "${XDG_RUNTIME_DIR:-}" ]; then
    PIPEWIRE_RUNTIME_DIR="/run/user/$(id -u)"
    export PIPEWIRE_RUNTIME_DIR
fi
exec "$HOME/.local/bin/.wiremix-bin" "$@"
