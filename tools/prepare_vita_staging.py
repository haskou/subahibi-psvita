#!/usr/bin/env python3
"""Combine the official Ren'Py Vita runtime with the generated game payload."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath

from project_paths import PROJECT_ROOT, RENPY_VITA_ARCHIVE, display_path


DEFAULT_ARCHIVE = RENPY_VITA_ARCHIVE
DEFAULT_GAME = PROJECT_ROOT / "build/game"
DEFAULT_OUTPUT = PROJECT_ROOT / "build/staging"
DEFAULT_LIVEAREA = PROJECT_ROOT / "assets/vita-livearea/sce_sys"
ASSET_PREFIX = "Ren'Py PSVita Distribution Tool/Assets/"
EXPECTED_ARCHIVE_SHA256 = "74614f39b167a983f7c224c85b832d1a3f2f388c5983ff1cb1620f7e2ea6cbc7"
# Media ship as external RPA archives packed straight from the game payload.
MEDIA_DIRECTORIES = frozenset({"images", "audio"})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_asset_path(name: str) -> Path | None:
    if not name.startswith(ASSET_PREFIX):
        return None
    relative = PurePosixPath(name[len(ASSET_PREFIX) :])
    if not relative.parts:
        return None
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("unsafe path in runtime archive: %s" % name)
    return Path(*relative.parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--livearea", type=Path, default=DEFAULT_LIVEAREA)
    parser.add_argument(
        "--fallback-save-directory",
        help="Use this Vita save directory when the game omits config.save_directory.",
    )
    parser.add_argument("--clean", action="store_true")
    parser.add_argument(
        "--expected-sha256",
        default=EXPECTED_ARCHIVE_SHA256,
        help="Expected SHA-256 for the official v1.0 archive.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive = args.archive.resolve()
    game = args.game.resolve()
    output = args.output.resolve()
    livearea = args.livearea.resolve()
    if not archive.is_file():
        raise FileNotFoundError("official distribution archive not found: %s" % archive)
    if not game.is_dir():
        raise FileNotFoundError("generated game directory not found: %s" % game)
    if not livearea.is_dir():
        raise FileNotFoundError("LiveArea directory not found: %s" % livearea)
    archive_sha256 = sha256(archive)
    if archive_sha256.casefold() != args.expected_sha256.casefold():
        raise ValueError(
            "runtime archive SHA-256 mismatch: expected %s, got %s"
            % (args.expected_sha256, archive_sha256)
        )
    if output == game or game in output.parents:
        raise ValueError("staging output must not be inside the game source")

    manifest_path = output.parent / "VITA_STAGING_MANIFEST.json"
    if output.exists():
        if not args.clean:
            raise FileExistsError("output exists; pass --clean to replace it: %s" % output)
        shutil.rmtree(output)
    if manifest_path.exists() and args.clean:
        manifest_path.unlink()

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / (".%s.tmp-%d" % (output.name, os.getpid()))
    if temporary.exists():
        raise FileExistsError("temporary output already exists: %s" % temporary)

    runtime_files = []
    try:
        temporary.mkdir()
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                relative = safe_asset_path(info.filename)
                if relative is None or info.is_dir():
                    continue
                target = temporary / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(info) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
                runtime_files.append(relative.as_posix())
        game_root = os.fspath(game)
        shutil.copytree(
            game,
            temporary / "game",
            ignore=lambda directory, names: MEDIA_DIRECTORIES if directory == game_root else (),
        )
        shutil.copytree(livearea, temporary / "sce_sys")
        renpy_launcher = temporary / "renpy.py"
        launcher_source = renpy_launcher.read_text(encoding="utf-8")
        vita_renderer = '        os.environ["RENPY_RENDERER"] = "gles"\n'
        vita_searchpath = (
            vita_renderer
            + '        os.environ["RENPY_SEARCHPATH"] = "ux0:/data/Subahibi"\n'
            + '        os.environ["RENPY_PERFORMANCE_TEST"] = "0"\n'
        )
        if launcher_source.count(vita_renderer) != 1:
            raise ValueError("cannot locate Vita launcher environment setup in renpy.py")
        renpy_launcher.write_text(
            launcher_source.replace(vita_renderer, vita_searchpath), encoding="utf-8"
        )
        if args.fallback_save_directory:
            source = renpy_launcher.read_text(encoding="utf-8")
            old = 'return "ux0:/Ren\'Py Data/" + save_directory'
            new = (
                'return "ux0:/Ren\'Py Data/" + '
                '(save_directory or %r)' % args.fallback_save_directory
            )
            if source.count(old) != 1:
                raise ValueError("cannot locate Vita save-directory expression in renpy.py")
            renpy_launcher.write_text(source.replace(old, new), encoding="utf-8")
        os.replace(temporary, output)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    required = (
        "eboot.bin",
        "lib/python27.zip",
        "module/libGLESv2.suprx",
        "renpy.py",
        "renpy/common/00start.rpy",
        "game/script.rpy",
        "game/vita_ui.rpy",
        "game/vita_renderer.rpy",
        "sce_sys/icon0.png",
        "sce_sys/livearea/contents/bg.png",
        "sce_sys/livearea/contents/startup.png",
        "sce_sys/livearea/contents/template.xml",
    )
    missing = [name for name in required if not (output / name).is_file()]
    if missing:
        raise ValueError("incomplete Vita staging; missing: %s" % ", ".join(missing))

    all_files = [path for path in output.rglob("*") if path.is_file()]
    manifest = {
        "format": 1,
        "runtime_source": display_path(archive),
        "runtime_sha256": archive_sha256,
        "runtime_file_count": len(runtime_files),
        "game_source": str(game.relative_to(PROJECT_ROOT)),
        "livearea_source": str(livearea.relative_to(PROJECT_ROOT)),
        "output": str(output.relative_to(PROJECT_ROOT)),
        "file_count": len(all_files),
        "total_bytes": sum(path.stat().st_size for path in all_files),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("runtime files: %d" % len(runtime_files))
    print("staging files: %d" % manifest["file_count"])
    print("staging bytes: %d" % manifest["total_bytes"])
    print("output: %s" % output)
    print("manifest: %s" % manifest_path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (FileExistsError, FileNotFoundError, ValueError, zipfile.BadZipFile) as error:
        print("error: %s" % error, file=sys.stderr)
        sys.exit(2)
