#!/usr/bin/env python3
"""Pre-scale the build copy of the game images to the Vita's physical resolution.

Ren'Py lays the game out on a 1694x960 virtual screen and the Vita shows it at
960x544, so every image is drawn at 544/960 of its pixel size. Decoding,
uploading and sampling full-size WebP files wastes load time and texture
memory. Each image is resized by that factor with Lanczos (Pillow resamples
RGBA premultiplied), re-encoded as lossy WebP, and its original size is written
to game/vita_image_sizes.txt; vita_ui.rpy scales every image back to that size,
so BGI layout math and saves keep seeing the original pixel dimensions.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image

from project_paths import PROJECT_ROOT, display_path


DEFAULT_GAME = PROJECT_ROOT / "build/game"
DEFAULT_MANIFEST = PROJECT_ROOT / "build/GAME_MANIFEST.json"
DEFAULT_REPORT = PROJECT_ROOT / "build/IMAGE_SCALE_REPORT.json"
SIZES_NAME = "vita_image_sizes.txt"
VIRTUAL_HEIGHT = 960
PHYSICAL_HEIGHT = 544
QUALITY = 90
ALPHA_QUALITY = 100
METHOD = 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    return parser.parse_args()


def scaled(length: int) -> int:
    return max(1, (length * PHYSICAL_HEIGHT + VIRTUAL_HEIGHT // 2) // VIRTUAL_HEIGHT)


def scale_image(path_name: str) -> dict[str, object]:
    path = Path(path_name)
    original = path.read_bytes()
    with Image.open(io.BytesIO(original)) as image:
        if getattr(image, "n_frames", 1) != 1:
            raise ValueError("animated image is not supported: %s" % path)
        image.load()
        width, height = image.size
        target = (scaled(width), scaled(height))
        output = original
        if target != image.size:
            mode = "RGBA" if "A" in image.getbands() else "RGB"
            resized = image.convert(mode).resize(target, Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            resized.save(
                buffer,
                "WEBP",
                quality=QUALITY,
                alpha_quality=ALPHA_QUALITY,
                method=METHOD,
            )
            output = buffer.getvalue()
            temporary = path.with_name(".%s.tmp" % path.name)
            temporary.write_bytes(output)
            os.replace(temporary, path)
    return {
        "name": path.name,
        "original_size": [width, height],
        "size": list(target),
        "original_bytes": len(original),
        "bytes": len(output),
        "sha256": hashlib.sha256(output).hexdigest(),
    }


def update_manifest(path: Path, results: dict[str, dict[str, object]], table: Path) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    updated = set()
    for entry in manifest["files"]:
        destination = Path(entry["destination"])
        if destination.parent != Path("game/images"):
            continue
        result = results.get(destination.name)
        if result is None:
            raise ValueError("manifested image was not scaled: %s" % destination)
        entry["size"] = result["bytes"]
        entry["sha256"] = result["sha256"]
        updated.add(destination.name)
    missing = set(results) - updated
    if missing:
        raise ValueError("scaled images missing from game manifest: %s" % ", ".join(sorted(missing)))
    table_bytes = table.read_bytes()
    manifest["files"].append(
        {
            "source": "generated:%s" % SIZES_NAME,
            "destination": "game/%s" % SIZES_NAME,
            "size": len(table_bytes),
            "sha256": hashlib.sha256(table_bytes).hexdigest(),
        }
    )
    manifest["file_count"] = len(manifest["files"])
    manifest["total_bytes"] = sum(entry["size"] for entry in manifest["files"])
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    game = args.game.resolve()
    images = game / "images"
    table = game / SIZES_NAME
    if table.exists():
        raise FileExistsError("images were already scaled: %s" % display_path(table))
    paths = sorted(path for path in images.iterdir() if path.is_file())
    unexpected = [path.name for path in paths if path.suffix != ".webp"]
    unexpected += [path.name for path in images.iterdir() if path.is_dir()]
    if unexpected:
        raise ValueError("unexpected image payload entries: %s" % ", ".join(sorted(unexpected)))
    keys: dict[str, str] = {}
    for path in paths:
        key = path.stem.lower()
        if "\t" in key or "\n" in key:
            raise ValueError("image name cannot be stored in the size table: %r" % path.name)
        if key in keys:
            raise ValueError("image names collide case-insensitively: %s, %s" % (keys[key], path.name))
        keys[key] = path.name

    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        results = {
            result["name"]: result
            for result in pool.map(scale_image, [str(path) for path in paths], chunksize=32)
        }

    rows = sorted(
        (Path(name).stem.lower(), result["original_size"]) for name, result in results.items()
    )
    table.write_text(
        "".join("%s\t%d\t%d\n" % (key, width, height) for key, (width, height) in rows),
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(args.manifest, results, table)

    original_bytes = sum(result["original_bytes"] for result in results.values())
    scaled_bytes = sum(result["bytes"] for result in results.values())
    unchanged = sum(result["original_size"] == result["size"] for result in results.values())
    report = {
        "format": 1,
        "scale": "%d/%d" % (PHYSICAL_HEIGHT, VIRTUAL_HEIGHT),
        "quality": QUALITY,
        "alpha_quality": ALPHA_QUALITY,
        "method": METHOD,
        "images": len(results),
        "unchanged_images": unchanged,
        "original_bytes": original_bytes,
        "bytes": scaled_bytes,
        "size_table": SIZES_NAME,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "images: %d scaled, %d unchanged, %d -> %d bytes"
        % (len(results) - unchanged, unchanged, original_bytes, scaled_bytes)
    )
    print("size table: %s" % display_path(table))
    print("report: %s" % display_path(args.report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
