#!/usr/bin/env python3
"""Replace game images with same-name Vita-sized Steam images."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import shutil
from pathlib import Path

from prepare_steam_images import webp_dimensions


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME = PROJECT_ROOT / "build/game"
DEFAULT_STEAM_IMAGES = PROJECT_ROOT / "local/assets/optimized"
DEFAULT_REPORT = PROJECT_ROOT / "build/STEAM_IMAGE_REPLACEMENTS.json"
DEFAULT_UNMATCHED_REPORT = PROJECT_ROOT / "local/reports/UNMATCHED_STEAM_IMAGES.md"
DEFAULT_UNMATCHED_DIRECTORY = PROJECT_ROOT / "local/reports/images"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def update_manifest(game: Path, replacements: list[dict]) -> None:
    manifest_path = game.parent / "GAME_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = {entry["destination"]: entry for entry in manifest["files"]}
    for replacement in replacements:
        destination = "game/" + replacement["game_path"]
        output = game / replacement["game_path"]
        if destination not in entries:
            raise ValueError("image manifest entry is missing: %s" % destination)
        entries[destination].update(
            {
                "source": "Vita-sized image generated from local Steam data",
                "size": output.stat().st_size,
                "sha256": sha256(output),
            }
        )
    manifest["total_bytes"] = sum(entry["size"] for entry in manifest["files"])
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--steam-images", type=Path, default=DEFAULT_STEAM_IMAGES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--unmatched-report", type=Path, default=DEFAULT_UNMATCHED_REPORT
    )
    parser.add_argument(
        "--unmatched-directory", type=Path, default=DEFAULT_UNMATCHED_DIRECTORY
    )
    args = parser.parse_args()
    game = args.game.resolve()
    steam_images = args.steam_images.resolve()
    image_root = game / "images"
    if not image_root.is_dir() or not steam_images.is_dir():
        raise FileNotFoundError("game or prepared Steam image directory is missing")

    index: dict[str, list[Path]] = collections.defaultdict(list)
    for source in sorted(steam_images.rglob("*.webp")):
        index[source.stem.casefold()].append(source)

    replacements = []
    unmatched = []
    for destination in sorted(image_root.rglob("*.webp")):
        candidates = index[destination.stem.casefold()]
        relative = destination.relative_to(game).as_posix()
        if not candidates:
            unmatched.append(relative)
            continue
        # Later Steam archives override earlier archives. This matters for the
        # three ev3101 variants duplicated by the final Steam content patch.
        source = max(candidates, key=lambda path: path.parent.name.casefold())
        source_dimensions = webp_dimensions(source)
        destination_dimensions = webp_dimensions(destination)
        cross_source = source_dimensions[0] * destination_dimensions[1]
        cross_destination = destination_dimensions[0] * source_dimensions[1]
        aspect_error = abs(cross_source - cross_destination) / float(
            max(cross_source, cross_destination)
        )
        # Integer resizing can differ by one pixel on a constrained axis.
        same_aspect = aspect_error <= 0.001
        no_larger = (
            source_dimensions[0] <= destination_dimensions[0]
            and source_dimensions[1] <= destination_dimensions[1]
        )
        if source_dimensions != destination_dimensions and not (same_aspect and no_larger):
            raise ValueError(
                "Steam image dimensions differ for %s: %r != %r"
                % (relative, source_dimensions, destination_dimensions)
            )
        previous_sha256 = sha256(destination)
        source_sha256 = sha256(source)
        shutil.copyfile(source, destination)
        replacements.append(
            {
                "game_path": relative,
                "steam_source": str(source.relative_to(PROJECT_ROOT)),
                "previous_dimensions": list(destination_dimensions),
                "output_dimensions": list(source_dimensions),
                "previous_sha256": previous_sha256,
                "output_sha256": source_sha256,
                "changed": previous_sha256 != source_sha256,
            }
        )

    update_manifest(game, replacements)
    report = {
        "format": 1,
        "mode": "direct-file-replacement",
        "replacement_count": len(replacements),
        "changed_count": sum(item["changed"] for item in replacements),
        "unmatched": unmatched,
        "replacements": replacements,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.unmatched_report.parent.mkdir(parents=True, exist_ok=True)
    unmatched_directory = args.unmatched_directory.resolve()
    if unmatched_directory.exists():
        shutil.rmtree(unmatched_directory)
    unmatched_directory.mkdir(parents=True)
    for relative_name in unmatched:
        relative = Path(relative_name)
        source = game / relative
        destination = unmatched_directory / relative.relative_to("images")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    unmatched_lines = [
        "# Images without a Steam equivalent",
        "",
        "Generated by `tools/apply_steam_images.py` from the complete game payload.",
        "These files were retained from the game data because no same-name image",
        "was present in the extracted and optimized Steam image set.",
        "",
        "Exact source copies are stored next to this report. Every path below is",
        "relative to `local/reports/`.",
        "",
        "Total: **%d**" % len(unmatched),
        "",
    ]
    unmatched_lines.extend("- `%s`" % path for path in unmatched)
    args.unmatched_report.write_text(
        "\n".join(unmatched_lines) + "\n", encoding="utf-8"
    )
    print("Steam image replacements: %d" % report["replacement_count"])
    print("byte-different replacements: %d" % report["changed_count"])
    print("unmatched images: %d" % len(unmatched))
    for path in unmatched:
        print("unmatched: %s" % path)
    print("report: %s" % args.report)
    print("unmatched report: %s" % args.unmatched_report)
    print("unmatched source copies: %s" % unmatched_directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
