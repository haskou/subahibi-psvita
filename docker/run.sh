#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
command=${1:-build}
if [ "$#" -gt 0 ]; then
    shift
fi

if [ "$command" = "bundle" ]; then
    if [ "$#" -lt 2 ]; then
        printf 'Usage: ./docker/run.sh bundle /path/to/audio /path/to/images\n' >&2
        exit 2
    fi
    audio_dir=$(CDPATH= cd -- "$1" && pwd)
    image_dir=$(CDPATH= cd -- "$2" && pwd)
    shift 2
    set -- "$command" /input-audio /input-images "$@"
    exec docker run --rm --platform linux/amd64 \
        --volume "$project_dir:/workspace" \
        --volume "$audio_dir:/input-audio:ro" \
        --volume "$image_dir:/input-images:ro" \
        --user "$(id -u):$(id -g)" \
        subahibi-vita-builder "$@"
fi

set -- "$command" "$@"
exec docker run --rm --platform linux/amd64 \
    --volume "$project_dir:/workspace" \
    --user "$(id -u):$(id -g)" \
    subahibi-vita-builder "$@"
