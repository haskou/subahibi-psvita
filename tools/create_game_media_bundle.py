#!/usr/bin/env python3
"""Create separate sub-2-GiB audio and image ZIP archives.

Ogg and WebP are already compressed, so members are stored; a fixed timestamp
and mode make the archives byte-identical for identical inputs.
"""

from __future__ import annotations

import argparse
import os
import shutil
import zipfile
from pathlib import Path

from project_paths import PROJECT_ROOT


FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)


def write_archive(output: Path, root: Path, prefix: str, files: list[Path]) -> None:
    temporary = output.with_suffix(output.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as bundle:
        for path in files:
            info = zipfile.ZipInfo(prefix + "/" + path.relative_to(root).as_posix(), FIXED_DATE_TIME)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            info.file_size = path.stat().st_size
            with path.open("rb") as source, bundle.open(info, "w") as destination:
                shutil.copyfileobj(source, destination, 1024 * 1024)
    os.replace(temporary, output)
    if output.stat().st_size >= 2**31:
        raise ValueError("archive exceeds the 2-GiB limit: %s" % output)
    print("%s: %d files, %d bytes" % (output, len(files), output.stat().st_size))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("images", type=Path)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "port")
    args = parser.parse_args()
    audio = sorted(args.audio.rglob("*.ogg"))
    images = sorted(args.images.rglob("*.webp"))
    if len(audio) != 33435 or len(images) != 4908:
        raise ValueError(
            "expected 33,435 Ogg and 4,908 WebP files; found %d and %d"
            % (len(audio), len(images))
        )
    args.output.mkdir(parents=True, exist_ok=True)
    write_archive(args.output / "game-audio.zip", args.audio, "audio", audio)
    write_archive(args.output / "game-images.zip", args.images, "images", images)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
