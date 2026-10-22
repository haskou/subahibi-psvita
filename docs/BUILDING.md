# Building

## Requirements

- Docker with Linux/amd64 container support.
- `port/game/`: all 132 editable English Ren'Py source modules, fonts and GUI resources.
- Git LFS data fetched for the clone:
  - `port/game-audio.zip`: 33,435 Ogg Vorbis files;
  - `port/game-images.zip`: 4,908 WebP files at the game's logical resolution.

No compiled game scripts are tracked. The builder downloads
checksum-pinned RenPy-Vita 1.0
and Ren'Py 7.4.9 dependencies while building the Docker image. The base image
is pinned by digest and the Python build tools by version and hash
(`requirements-tools.txt`). It uses the official precompiled `eboot.bin`; no
native runtime is compiled.

## Create the local media bundle

Skip this section when `port/game-audio.zip` and `port/game-images.zip` are
already present.

```sh
./docker/build.sh
./docker/run.sh bundle "/path/to/complete/audio" "/path/to/optimized/images"
```

The command rejects incomplete input trees and writes two separate archives,
both below 2 GiB. Ogg and WebP are already compressed, so members are stored
uncompressed with a fixed timestamp: identical inputs give byte-identical
archives. Generated extraction remains under ignored `local/`. On later builds,
extraction is skipped while the source tree, both archive sizes and
modification times, and the file counts still match.

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
3. copies the complete English source and media tree to `build/game/`;
4. removes no-op BGI statements, groups safe compatibility calls and inlines
   the frequent `1a5`, `1a1`, `14b` and `141` helper calls that take literal
   arguments;
5. converts story chapters to Ren'Py modules loaded only when entered;
6. generates the Vita dialogue-box raster from its editable source asset and
   re-encodes the main-menu art as a 725×544 lossy WebP, the size it is shown at;
7. subsets `simhei.ttf` to the glyphs used by the scripts and UI;
8. scales every WebP by 544/960 to the Vita display and records the original
   sizes in `vita_image_sizes.txt`; the game shows each image at its original
   logical size, so positions and anchors are unchanged;
9. stages the Vita runtime with the game tree, except images and audio;
10. compiles every core source, story module and startup cache with Ren'Py
    7.4.9, with one bytecode cache per story module
    (`game/cache/bytecode-<module>.rpyb`), then drops the unused `renpy/common`
    modules (achievements, gallery, in-app purchases, layered images, music
    room, themes, updater) and regenerates `game/cache/screens.rpyb` from the
    final payload as Ren'Py 7.4.9.0, the version of the Vita runtime (it has no
    `renpy.vc_version`), so the device accepts the screen cache instead of
    re-analysing every screen on first launch;
11. patches the runtime's `lib/python27.zip` in one pass
    (`tools/patch_vita_runtime.py`): a no-op NVIDIA probe in the Vita `core`;
    deferred external audio RPA indexing, which the game may also start from
    its own thread, and no startup scan of `cache/` and `saves/` in `loader`;
    and per-module bytecode caches in `script` (modules without one, such as
    Ren'Py's `_errorhandling`, keep using the startup cache);
12. packs images and audio from `build/game/` into three RPA-3.0 archives;
13. packages the staging tree with VitaSDK;
14. validates the VPK, RPA coverage, image size table, hashes, title metadata
    and staging parity.

Save compatibility depends on the global Ren'Py node serials. Every script
rewrite keeps the number of nodes per file from build to build, the pruned
common modules are compiled before they are dropped, and no `.rpy` file may be
added or removed without breaking existing saves. Saves of the PC release and
of the earlier Vita builds that stamped wall-clock node versions name other
layouts: step 5 embeds their translation to the shipped nodes (through the
optimizer's statement map for the optimized chapters), checked against the
shipped files at build time and against the loaded node counts at load time.

Run static tooling checks with:

```sh
./docker/run.sh check
```
