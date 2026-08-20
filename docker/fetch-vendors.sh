#!/bin/sh
set -eu

destination=${1:-/opt/subahibi/vendor}
runtime_dir="$destination/renpy-vita-dist"
sdk_archive="$destination/renpy-7.4.9-sdk.tar.bz2"

runtime_url="https://github.com/SonicMastr/renpy-vita/releases/download/v1.0/Ren.Py.PSVita.Distribution.Tool.zip"
runtime_sha256="74614f39b167a983f7c224c85b832d1a3f2f388c5983ff1cb1620f7e2ea6cbc7"
sdk_url="https://www.renpy.org/dl/7.4.9/renpy-7.4.9-sdk.tar.bz2"
sdk_sha256="081013caca105812d2cf7879ef2d89a8ec0da30cf926bf7cd23407507bd4e36d"

mkdir -p "$runtime_dir"

curl --fail --location --retry 3 \
    "$runtime_url" \
    --output "$runtime_dir/Ren.Py.PSVita.Distribution.Tool.zip"
printf '%s  %s\n' \
    "$runtime_sha256" \
    "$runtime_dir/Ren.Py.PSVita.Distribution.Tool.zip" \
    | sha256sum --check --status

curl --fail --location --retry 3 \
    "$sdk_url" \
    --output "$sdk_archive"
printf '%s  %s\n' "$sdk_sha256" "$sdk_archive" \
    | sha256sum --check --status

tar -xjf "$sdk_archive" -C "$destination"
rm "$sdk_archive"

test -f "$destination/renpy-7.4.9-sdk/renpy/display/core.py"
test -x "$destination/renpy-7.4.9-sdk/lib/linux-x86_64/python"
