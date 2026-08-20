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

Install the approximately 93 MB VPK with VitaShell, then copy the three RPA files to:

```text
ux0:app/SHBI00001/game/
```

Do not launch the game until all three archives are present. Full instructions
and checksum verification are in [docs/INSTALLING.md](docs/INSTALLING.md).

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
| Circle | Hide interface |
| Triangle | History |
| Square | Auto mode |
| L | Rollback |
| R | Toggle skip |
| Select | Quick Save |
| L + Select | Quick Load |
| Start | Game menu |
| D-pad / Sticks | Menu navigation |
| Touch | Sidebar actions |

Close the application from LiveArea. The native RenPy-Vita Quit path is hidden
because the upstream runtime crashes while shutting down.

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
