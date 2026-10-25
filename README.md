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
VitaShell. Keep the archives in that directory; VPK updates replace
`ux0:app/SHBI00001/`, while the media in `ux0:data/Subahibi/` survives. Keep at
least 2.3 GB free on `ux0:`. Full instructions and checksum verification are in
[docs/INSTALLING.md](docs/INSTALLING.md).

## Build

Docker is the only build dependency. The clone contains all 132 editable
Ren'Py source modules, and Git LFS supplies the two media archives. The Docker
base image and the Python tools are pinned by digest/hash, and identical inputs
produce byte-identical media archives:

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

## Saves

Saves made with the PC release and with earlier Vita builds load and continue.
The build embeds the translation of their script layout to the shipped one and
checks it when a save is loaded. Loading also restores the BGI sprite and
variable state, which the original game never saved. Save and Load screens
page with L / R.

## Startup time

On a real Vita, the instrumented startup phases before GLES renderer
initialization take 15.1–15.8 seconds. Most of this work is repeated for every
new process, so later launches are not instant, and a black screen during
initialization is expected.

| Phase | Time |
|---|---|
| Loading error handling | 0.58 s |
| Loading script | 3.73–3.78 s |
| Loader init | 2.00–2.07 s |
| Early init | 0.43–1.10 s |
| Screen phases, first launch after install | 0.38 s |
| First main menu frame | 0.35 s |
| Main menu music lookup | 0.056 s |

What keeps it down:

- Ren'Py's automatic startup registration of all 33,435 audio files and 4,908
  images is disabled. Audio uses explicit paths and images are resolved from
  the RPA index when first shown.
- The Vita runtime copy defers indexing the two external audio RPA files. A
  background thread indexes them during the opening warning screen, or the first
  audio lookup does if it comes first, for example when the opening is skipped.
  The same thread loads the main menu background, so the first menu frame does
  not decode it while the menu music is looked up.
- Each story chapter has its own bytecode cache, loaded when the chapter is
  entered; launch unpickles only the startup scripts.
- The shipped screen cache is valid for the Vita runtime, so the first launch
  after an installation does not rewrite it.
- A 16 KB subset of `simhei.ttf` replaces the 9.8 MB font, unused
  `renpy/common` modules are dropped and images are scaled to the 960×544
  display, which keeps the VPK at about 44 MB.

The precompiled `eboot.bin` is unchanged; only the copied `core`, `loader` and
`script` modules inside the generated VPK are patched.

The opening logos and warnings take about 27 seconds of scripted pauses and
dissolves (31 seconds measured on the Vita, including image loads) unless
skipped with Cross, Circle or Start.

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
