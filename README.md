# Subahibi PS Vita

PS Vita port of *Wonderful Everyday Down the Rabbit-Hole* using the prebuilt
RenPy-Vita 7 runtime. The port includes editable English compatibility sources,
Vita UI, controller mappings and LiveArea files.

The original 4:3 presentation is centered at 725×544. The OLED pillarboxes
remain black and provide touch shortcuts without stretching the game image.

## Install

The release consists of one installable VPK and three Ren'Py media archives:

```text
Subahibi.vpk
Subahibi-images.rpa
Subahibi-audio-01.rpa
Subahibi-audio-02.rpa
```

Copy the three RPA files to the persistent data directory:

```text
ux0:data/Subahibi/
```

Then copy the approximately 44 MB VPK to `ux0:data/` and install it with
VitaShell. Keep the archives in
that directory; VPK updates replace `ux0:app/SHBI00001/`, while the media in
`ux0:data/Subahibi/` survives. Full instructions and checksum verification are
in [docs/INSTALLING.md](docs/INSTALLING.md).

## Build

Docker is the only build dependency. The clone contains all 132 editable
Ren'Py source modules, and Git LFS supplies the two media archives:

```text
port/game/*.rpy
port/game-audio.zip
port/game-images.zip
```

Then run:

```sh
git lfs pull
./docker/build.sh
./docker/run.sh build
```

To replace the media with another complete prepared set, regenerate its two
archives first:

```sh
./docker/run.sh bundle "/path/to/audio" "/path/to/optimized-images"
./docker/run.sh build
```

Outputs are written to `build/dist/`. See
[docs/BUILDING.md](docs/BUILDING.md) for the exact input layout and pipeline.

## Controls

| Input | Action |
|---|---|
| Cross / D-pad Down | Advance or confirm |
| Circle | Hide interface during dialogue; return in menus |
| Triangle | History |
| Square | Auto mode |
| L | Rollback |
| R | Toggle skip |
| Select | Quick Save |
| L + Select | Quick Load |
| Start | Game menu |
| D-pad / Sticks | Menu navigation |
| L / R in Save and Load | Previous / next page |
| Touch | Sidebar actions |
| Cross / Circle / Start during the opening logos | Skip the logos |

Close the application from LiveArea. The native RenPy-Vita Quit path is hidden
because the upstream runtime crashes while shutting down.

## Startup time

The instrumented phases of a real Vita launch on 22 August 2026 took
approximately 19–20 seconds before GLES renderer initialization. Most of this
work is repeated for every new process, so later launches are not expected to
be instant.

The largest measured phases were 4.76 seconds to load the core scripts, 3.67
seconds to initialize Ren'Py's generic error handling, 2.64 seconds for the
Python/Ren'Py bootstrap and early initialization, and 2.08 seconds for loader
initialization. Translation, screen preparation, garbage collection and the
remaining phases account for the rest.

The port disables Ren'Py's automatic startup registration of all 33,435 audio
files and 4,908 images. Audio already uses explicit paths, while images are
resolved from the RPA index when first shown. This reduced `Running init code`
from 9.13 seconds to 0.86 seconds without changing the media archives.

The Vita runtime copy also defers indexing the two external audio RPA files.
A background thread indexes them during the opening warning screen, or the
first audio lookup does if it comes first, for example when the opening is
skipped. This reduced `Loader init` from approximately 6.03 seconds to 2.08
seconds.

The build also gives each story chapter its own bytecode cache, so launch
unpickles only the startup scripts and a chapter loads its cache when entered.
It ships a 16 KB subset of `simhei.ttf` instead of the 9.8 MB font, drops
unused `renpy/common` modules and scales images to the 960×544 display. The
archives and precompiled `eboot.bin` remain unchanged; only the copied `core`,
`loader` and `script` modules inside the generated VPK are patched.

On hardware these changes brought the instrumented phases from 19.44 to 15.1–15.8
seconds over two launches. `Loading error handling` fell from 3.69 to 0.58
seconds, `Loading script` from 4.73 to 3.73–3.78 seconds and `Loader init` from
2.12 to 2.00–2.07 seconds; `Early init` varies between launches (0.43 to 1.10
seconds). The shipped screen cache is valid for the Vita runtime, so the first
launch after an installation no longer rewrites it: its screen phases took
0.38 seconds instead of 1.51.

The opening logos and warnings then take about 27 seconds of scripted pauses
and dissolves (31 seconds measured on the Vita, including image loads) unless
skipped with Cross, Circle or Start. The same background thread that indexes
the audio archives also loads the main menu background during the warning
screen, so the first menu frame does not decode it while the menu music is
being looked up. On hardware this brought the first menu frame from 1.26 to
0.35 seconds and the menu music lookup from 2.78 seconds to 56 milliseconds.

## Repository layout

| Path | Purpose |
|---|---|
| `port/game/` | Complete editable English game/Vita sources, fonts and GUI assets |
| `port/game-audio.zip` | Complete Ogg input tree |
| `port/game-images.zip` | Complete optimized WebP input tree |
| `assets/vita-livearea/` | LiveArea sources and generated assets |
| `docker/` | Reproducible Linux build environment |
| `tools/` | Build, packaging and validation implementation |
| `build/dist/` | Generated VPK, RPA data archives and checksums |

Title ID: `SHBI00001`.
