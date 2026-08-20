#!/bin/sh
set -eu

export HOME=/tmp/subahibi-home
mkdir -p "$HOME"

cd /workspace

command=${1:-build}
if [ "$#" -gt 0 ]; then
    shift
fi

case "$command" in
    build)
        exec python3 tools/build_port.py "$@"
        ;;
    bundle)
        exec python3 tools/create_game_media_bundle.py "$@"
        ;;
    livearea)
        exec python3 tools/prepare_livearea_assets.py "$@"
        ;;
    check)
        python3 -m compileall -q tools
        for tool in tools/*.py; do
            python3 "$tool" --help >/dev/null
        done
        exec python3 tools/check_vendor.py
        ;;
    shell)
        exec /bin/bash "$@"
        ;;
    *)
        printf 'Unknown command: %s\n' "$command" >&2
        printf 'Available commands: build, bundle, livearea, check, shell\n' >&2
        exit 2
        ;;
esac
