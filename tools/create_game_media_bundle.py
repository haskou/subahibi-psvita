#!/usr/bin/env python3
"""Create separate sub-2-GiB audio and image ZIP archives."""

from __future__ import annotations

import argparse
import os
import zipfile
from pathlib import Path

from project_paths import PROJECT_ROOT


def write_archive(output: Path, root: Path, prefix: str, files: list[Path]) -> None:
    temporary = output.with_suffix(output.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(
        temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9,
        allowZip64=True,
    ) as bundle:
        for path in files:
            bundle.write(path, prefix + "/" + path.relative_to(root).as_posix())
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
