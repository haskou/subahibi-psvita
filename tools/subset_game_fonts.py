#!/usr/bin/env python3
"""Subset the build copy of the game fonts to the characters the game can show.

The text font is a CJK face whose Latin coverage is a tiny fraction of its
glyphs. Every displayable string comes from the game scripts or Ren'Py's
common scripts, so the subset keeps those characters plus Latin-1 and general
punctuation as a margin, and fails unless every requested character the
original font covered still maps to an identical glyph advance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

from project_paths import PROJECT_ROOT, RENPY_SDK


DEFAULT_GAME = PROJECT_ROOT / "build/game"
DEFAULT_MANIFEST = PROJECT_ROOT / "build/GAME_MANIFEST.json"
DEFAULT_REPORT = PROJECT_ROOT / "build/FONT_SUBSET_REPORT.json"
DEFAULT_COMMON = RENPY_SDK / "renpy/common"
FONTS = ("simhei.ttf",)
SCRIPT_SUFFIXES = {".rpy", ".rpym"}
MARGIN = set(range(0x20, 0x7F)) | set(range(0xA0, 0x100)) | set(range(0x2000, 0x2070))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--common", type=Path, default=DEFAULT_COMMON)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def script_codepoints(roots: list[tuple[Path, bool]]) -> set[int]:
    codepoints: set[int] = set()
    for root, recursive in roots:
        paths = root.rglob("*") if recursive else root.glob("*")
        scripts = [path for path in paths if path.suffix in SCRIPT_SUFFIXES and path.is_file()]
        if not scripts:
            raise FileNotFoundError("no Ren'Py scripts found in %s" % root)
        for path in scripts:
            codepoints.update(ord(character) for character in path.read_text(encoding="utf-8"))
    return {codepoint for codepoint in codepoints if codepoint >= 0x20}


def subset_font(path: Path, codepoints: set[int]) -> dict[str, object]:
    original = TTFont(path, recalcTimestamp=False)
    original_cmap = original.getBestCmap()
    covered = codepoints & set(original_cmap)

    options = subset.Options()
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.name_legacy = True
    options.legacy_kern = True
    options.notdef_outline = True
    options.drop_tables += ["meta"]
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=covered)
    font = TTFont(path, recalcTimestamp=False)
    subsetter.subset(font)

    cmap = font.getBestCmap()
    lost = sorted(codepoint for codepoint in covered if codepoint not in cmap)
    if lost:
        raise ValueError("%s subset lost U+%04X" % (path.name, lost[0]))
    original_metrics = original["hmtx"].metrics
    metrics = font["hmtx"].metrics
    changed = [
        codepoint
        for codepoint in covered
        if metrics[cmap[codepoint]] != original_metrics[original_cmap[codepoint]]
    ]
    if changed:
        raise ValueError("%s subset changed metrics of U+%04X" % (path.name, min(changed)))

    temporary = path.with_name(".%s.tmp-%d" % (path.name, os.getpid()))
    try:
        font.save(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "original_glyphs": len(original.getGlyphOrder()),
        "subset_glyphs": len(font.getGlyphOrder()),
        "codepoints": len(covered),
        "bytes": path.stat().st_size,
    }


def update_manifest(path: Path, game: Path, names: set[str]) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    updated = set()
    for entry in manifest["files"]:
        destination = Path(entry["destination"])
        if destination.parent != Path("game") or destination.name not in names:
            continue
        font = game / destination.name
        entry["size"] = font.stat().st_size
        entry["sha256"] = hashlib.sha256(font.read_bytes()).hexdigest()
        updated.add(destination.name)
    missing = names - updated
    if missing:
        raise ValueError("subset fonts missing from game manifest: %s" % ", ".join(sorted(missing)))
    manifest["total_bytes"] = sum(entry["size"] for entry in manifest["files"])
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    game = args.game.resolve()
    shown = script_codepoints([(game, False), (args.common, True)])
    requested = shown | MARGIN
    fonts = {}
    for name in FONTS:
        path = game / name
        original_bytes = path.stat().st_size
        result = subset_font(path, requested)
        result["original_bytes"] = original_bytes
        cmap = TTFont(path).getBestCmap()
        result["missing_script_characters"] = [
            "U+%04X" % codepoint for codepoint in sorted(shown - set(cmap))
        ]
        fonts[name] = result
        print(
            "%s: %d -> %d bytes, %d glyphs, %d script characters without a glyph"
            % (
                name,
                original_bytes,
                result["bytes"],
                result["subset_glyphs"],
                len(result["missing_script_characters"]),
            )
        )
    update_manifest(args.manifest, game, set(FONTS))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps({"format": 1, "fonts": fonts}, indent=2) + "\n", encoding="utf-8"
    )
    print("report: %s" % args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
