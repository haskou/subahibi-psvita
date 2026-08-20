#!/usr/bin/env python3
"""Assemble the ignored game tree from tracked sources and media archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path, PurePosixPath

from project_paths import PROJECT_ROOT


DEFAULT_SOURCES = PROJECT_ROOT / "port/game"
DEFAULT_AUDIO = PROJECT_ROOT / "port/game-audio.zip"
DEFAULT_IMAGES = PROJECT_ROOT / "port/game-images.zip"
DEFAULT_OUTPUT = PROJECT_ROOT / "local/prepared-game"
MARKER = ".prepared-game.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def inventory(game: Path) -> dict[str, int]:
    return {
        "rpy": len(list(game.glob("*.rpy"))),
        "audio": len(list((game / "audio").rglob("*.ogg"))),
        "images": len(list((game / "images").rglob("*.webp"))),
    }


def safe_extract(bundle: zipfile.ZipFile, destination: Path) -> None:
    corrupt = bundle.testzip()
    if corrupt:
        raise ValueError("corrupt archive entry: %s" % corrupt)
    for info in bundle.infolist():
        relative = PurePosixPath(info.filename)
        if info.is_dir():
            continue
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise ValueError("unsafe archive path: %s" % info.filename)
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with bundle.open(info) as source, target.open("wb") as output:
            shutil.copyfileobj(source, output, 8 * 1024 * 1024)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--audio", type=Path, default=DEFAULT_AUDIO)
    parser.add_argument("--images", type=Path, default=DEFAULT_IMAGES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    archives = (args.audio, args.images)
    missing = [str(path) for path in archives if not path.is_file()]
    if not args.sources.is_dir():
        missing.append(str(args.sources))
    if missing:
        raise FileNotFoundError("missing game archive(s): %s" % ", ".join(missing))
    hashes = {path.name: sha256(path) for path in archives}
    hashes["port/game"] = tree_sha256(args.sources)
    expected = {"rpy": 132, "audio": 33435, "images": 4908}
    marker = args.output / MARKER
    if marker.is_file():
        state = json.loads(marker.read_text(encoding="utf-8"))
        if state.get("archives") == hashes and inventory(args.output) == expected:
            print("game data already prepared")
            return 0

    temporary = args.output.with_name(".%s.tmp-%d" % (args.output.name, os.getpid()))
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    try:
        shutil.copytree(args.sources, temporary, dirs_exist_ok=True)
        for archive in archives:
            with zipfile.ZipFile(archive) as bundle:
                safe_extract(bundle, temporary)
        actual = inventory(temporary)
        if actual != expected:
            raise ValueError("incomplete prepared game: expected %r, found %r" % (expected, actual))
        (temporary / MARKER).write_text(
            json.dumps({"format": 1, "archives": hashes}, indent=2) + "\n",
            encoding="utf-8",
        )
        if args.output.exists():
            shutil.rmtree(args.output)
        os.replace(temporary, args.output)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    print("prepared 132 Ren'Py sources, 4,908 images and 33,435 audio files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
