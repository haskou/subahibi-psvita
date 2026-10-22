#!/usr/bin/env python3
"""Pack game media into sub-2-GiB Ren'Py archives distributed beside the VPK."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
import zlib
from pathlib import Path

from project_paths import PROJECT_ROOT


DEFAULT_GAME = PROJECT_ROOT / "build/game"
DEFAULT_OUTPUT = PROJECT_ROOT / "build/dist"
DEFAULT_MAX_BYTES = 950 * 1024 * 1024
KEY = 0x42424242
PADDING = b"Made with Ren'Py."
HEADER_FORMAT = b"RPA-3.0 %016x %08x\n"
HEADER_SIZE = len(HEADER_FORMAT % (0, KEY))
CHUNK_SIZE = 8 * 1024 * 1024


def groups(paths: list[Path], maximum: int) -> list[list[Path]]:
    result: list[list[Path]] = []
    current: list[Path] = []
    size = 0
    for path in paths:
        file_size = path.stat().st_size + len(PADDING)
        if current and size + file_size > maximum:
            result.append(current)
            current, size = [], 0
        current.append(path)
        size += file_size
    if current:
        result.append(current)
    return result


def write_rpa(path: Path, game: Path, files: list[Path]) -> dict:
    """Write the archive in one pass, hashing the bytes as they are written."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    sizes = [source.stat().st_size for source in files]
    index_offset = HEADER_SIZE + sum(len(PADDING) + size for size in sizes)
    index = {}
    digest = hashlib.sha256()
    with temporary.open("wb") as output:
        def write(data: bytes) -> None:
            output.write(data)
            digest.update(data)

        write(HEADER_FORMAT % (index_offset, KEY))
        for source, length in zip(files, sizes):
            write(PADDING)
            offset = output.tell()
            with source.open("rb") as stream:
                for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
                    write(chunk)
            if output.tell() - offset != length:
                raise ValueError("media file changed while archiving: %s" % source)
            name = source.relative_to(game).as_posix()
            index[name.encode("utf-8")] = [(offset ^ KEY, length ^ KEY, b"")]
        write(zlib.compress(pickle.dumps(index, protocol=2), 9))
        size = output.tell()
    os.replace(temporary, path)
    if size >= 2**31:
        raise ValueError("media archive exceeds the Vita 2-GiB safety limit: %s" % path)
    return {
        "name": path.name,
        "size": size,
        "sha256": digest.hexdigest(),
        "file_count": len(files),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args()
    images = sorted((args.game / "images").rglob("*.webp"))
    audio = sorted((args.game / "audio").rglob("*.ogg"))
    if len(images) != 4908 or len(audio) != 33435:
        raise ValueError("expected 4,908 images and 33,435 audio files")
    args.output.mkdir(parents=True, exist_ok=True)
    for stale in args.output.glob("Subahibi-*.rpa"):
        stale.unlink()

    planned = [("Subahibi-images.rpa", images)]
    audio_groups = groups(audio, args.max_bytes)
    planned.extend(
        ("Subahibi-audio-%02d.rpa" % number, files)
        for number, files in enumerate(audio_groups, 1)
    )
    archives = []
    for name, files in planned:
        print("writing %s (%d files)" % (name, len(files)), flush=True)
        archives.append(write_rpa(args.output / name, args.game, files))

    report = {
        "format": 1,
        "archive_format": "RPA-3.0",
        "images": len(images),
        "audio": len(audio),
        "archives": archives,
    }
    (args.output / "MEDIA_ARCHIVES.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print("media archives: %d" % len(archives))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
