# Building

## Requirements

- Docker with Linux/amd64 container support.
- `port/game/`: all 132 editable English Ren'Py source modules, fonts and GUI resources.
- Git LFS data fetched for the clone:
  - `port/game-audio.zip`: 33,435 Ogg Vorbis files;
  - `port/game-images.zip`: 4,908 Vita-sized WebP files.

No compiled game scripts are tracked. The builder downloads
checksum-pinned RenPy-Vita 1.0
and Ren'Py 7.4.9 dependencies while building the Docker image. It uses the
official precompiled `eboot.bin`; no native runtime is compiled.

## Create the local media bundle

Skip this section when `port/game-audio.zip` and `port/game-images.zip` are
already present.

```sh
./docker/build.sh
./docker/run.sh bundle "/path/to/complete/audio" "/path/to/optimized/images"
```

The command rejects incomplete input trees and writes two separate archives,
both below 2 GiB. Generated extraction remains under ignored `local/`. On later
builds, extraction is skipped while the source tree, both archive hashes and
file counts still match.

## Build the release

```sh
./docker/build.sh
./docker/run.sh build
```

The resulting release files are:

```text
build/dist/Subahibi.vpk
build/dist/Subahibi-images.rpa
build/dist/Subahibi-audio-01.rpa
build/dist/Subahibi-audio-02.rpa
build/dist/SHA256SUMS
build/dist/RELEASE_MANIFEST.json
build/dist/VPK_VALIDATION.json
```

The VPK intentionally contains the runtime, scripts, UI and caches but not the
38,343 media files. VitaShell uses a signed 32-bit file-size path in relevant
archive operations, and the former 2.32 GB monolithic VPK failed immediately
with `0xFFFFFFFF`. Media is therefore written as three RPA-3.0 archives, each
smaller than 1 GiB, and stored persistently in `ux0:data/Subahibi/` beside the
approximately 50 MB VPK installation payload.

## Pipeline

The build:

1. validates the pinned runtime and tracked editable port inputs;
2. assembles the ignored game tree from `port/game/` and both media archives;
3. copies the complete English source and media tree;
4. removes no-op BGI statements and groups safe compatibility calls;
5. converts story chapters to Ren'Py modules loaded only when entered;
6. generates the Vita dialogue-box raster from its editable source asset;
7. compiles every core source, story module and startup cache with Ren'Py 7.4.9;
8. patches the copied Python loader to defer external audio RPA indexing;
9. packs images and audio into three RPA-3.0 archives;
10. packages the remaining staging tree with VitaSDK;
11. validates the VPK, RPA coverage, hashes, title metadata and staging parity.

Run static tooling checks with:

```sh
./docker/run.sh check
```
