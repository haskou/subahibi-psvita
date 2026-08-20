#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

exec docker build \
    --platform linux/amd64 \
    --tag subahibi-vita-builder \
    --file "$project_dir/docker/Dockerfile" \
    "$project_dir"
