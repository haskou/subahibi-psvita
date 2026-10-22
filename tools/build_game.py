#!/usr/bin/env python3
"""Build the reproducible Ren'Py Vita payload from editable sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Iterable, Iterator, Sequence, Set


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "local/prepared-game"
DEFAULT_OUTPUT = PROJECT_ROOT / "build/game"

ENTRY_SCRIPTS = (
    "script.rpy",
    "options.rpy",
    "gui.rpy",
    "screens.rpy",
    "bgi_core.rpy",
    "bgi_func.rpy",
    "makerlogo.rpy",
    "main.rpy",
    "1-1_0710_dream.rpy",
)

SCRIPT_SUFFIXES = {".rpy", ".rpym"}
FONT_SUFFIXES = {".ttf", ".otf"}
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_@+~.-]*")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the current Vita payload from the canonical game tree."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--entry-script",
        action="append",
        dest="entry_scripts",
        help="Ren'Py source used for static media discovery; may be repeated.",
    )
    parser.add_argument(
        "--all-media",
        action="store_true",
        help="Copy every image and audio file instead of the statically discovered subset.",
    )
    parser.add_argument(
        "--minimal-scripts",
        action="store_true",
        help="Copy only the listed entry sources instead of every game source.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Replace an existing output directory.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def canonical_relative_path(source_root: Path, source_file: Path) -> Path:
    return source_file.relative_to(source_root)


def copy_and_hash(source: Path, target: Path) -> tuple[int, str]:
    """Copy like shutil.copy2, hashing the bytes in the same pass."""
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as reader, target.open("wb") as writer:
        for chunk in iter(lambda: reader.read(1024 * 1024), b""):
            writer.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    shutil.copystat(source, target)
    return size, digest.hexdigest()


def build_media_index(source_root: Path) -> DefaultDict[str, Set[Path]]:
    index: DefaultDict[str, Set[Path]] = defaultdict(set)
    for directory_name in ("images", "audio"):
        directory = source_root / directory_name
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            restored = canonical_relative_path(source_root, path)
            index[restored.name.casefold()].add(path)
            index[restored.stem.casefold()].add(path)
    return index


def discover_media(source_root: Path, entry_scripts: Sequence[str]) -> Set[Path]:
    index = build_media_index(source_root)
    selected: Set[Path] = set()
    for name in entry_scripts:
        script = source_root / name
        if not script.is_file():
            raise FileNotFoundError("entry script not found: %s" % script)
        for token in TOKEN_RE.findall(script.read_text(encoding="utf-8")):
            selected.update(index.get(token.casefold(), ()))
    return selected


def base_files(
    source_root: Path, minimal_scripts: bool, entry_scripts: Sequence[str]
) -> Set[Path]:
    selected: Set[Path] = set()
    entry_script_names = set(entry_scripts)
    for path in source_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(source_root)
        if relative.parts[0] in {"cache", "tl"}:
            continue
        if relative.parts[0] == "gui":
            selected.add(path)
        elif path.suffix.casefold() in SCRIPT_SUFFIXES | FONT_SUFFIXES:
            if (
                not minimal_scripts
                or path.suffix.casefold() in FONT_SUFFIXES
                or path.name in entry_script_names
            ):
                selected.add(path)
        elif relative.parent == Path(".") and path.name == "script_version.txt":
            selected.add(path)
    return selected


def all_media(source_root: Path) -> Set[Path]:
    selected: Set[Path] = set()
    for directory_name in ("images", "audio"):
        selected.update(path for path in (source_root / directory_name).rglob("*") if path.is_file())
    return selected


def validate_source_and_output(source_root: Path, output: Path) -> None:
    source_root = source_root.resolve()
    output = output.resolve()
    if not source_root.is_dir():
        raise FileNotFoundError("source game directory not found: %s" % source_root)
    if output == source_root or source_root in output.parents:
        raise ValueError("output must not be inside the evidence/source tree")


def copy_payload(source_root: Path, destination: Path, files: Iterable[Path]) -> list[dict]:
    manifest_entries = []
    for source in sorted(files):
        relative = canonical_relative_path(source_root, source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        size, digest = copy_and_hash(source, target)
        manifest_entries.append(
            {
                "source": str(source.relative_to(PROJECT_ROOT)),
                "destination": str(Path("game") / relative),
                "size": size,
                "sha256": digest,
            }
        )
    return manifest_entries


def main() -> int:
    args = parse_args()
    source_root = args.source.resolve()
    output = args.output.resolve()
    entry_scripts = tuple(args.entry_scripts or ENTRY_SCRIPTS)
    validate_source_and_output(source_root, output)

    files = base_files(source_root, args.minimal_scripts, entry_scripts)
    media = all_media(source_root) if args.all_media else discover_media(source_root, entry_scripts)
    files.update(media)
    total_size = sum(path.stat().st_size for path in files)

    if args.minimal_scripts:
        profile = "minimal-scripts"
    else:
        profile = "full-media" if args.all_media else "dependency-selected"
    print("profile: %s" % profile)
    print("files: %d" % len(files))
    print("bytes: %d" % total_size)
    print("media files: %d" % len(media))
    print("output: %s" % output)
    if args.dry_run:
        return 0

    manifest_path = output.parent / "GAME_MANIFEST.json"
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

    try:
        temporary.mkdir()
        entries = copy_payload(source_root, temporary, files)
        os.replace(temporary, output)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    manifest = {
        "format": 1,
        "profile": profile,
        "source": str(source_root.relative_to(PROJECT_ROOT)),
        "output": str(output.relative_to(PROJECT_ROOT)),
        "entry_scripts": list(entry_scripts),
        "file_count": len(entries),
        "total_bytes": sum(entry["size"] for entry in entries),
        "files": entries,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("manifest: %s" % manifest_path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (FileExistsError, FileNotFoundError, UnicodeDecodeError, ValueError) as error:
        print("error: %s" % error, file=sys.stderr)
        sys.exit(2)
