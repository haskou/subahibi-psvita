#!/usr/bin/env python3
"""Reduce no-op and rollback-invisible BGI statements in the build copy."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from project_paths import PROJECT_ROOT


DEFAULT_GAME = PROJECT_ROOT / "build/game"
DEFAULT_REPORT = PROJECT_ROOT / "build/BGI_OPTIMIZATION_REPORT.json"
DEFAULT_MANIFEST = PROJECT_ROOT / "build/GAME_MANIFEST.json"
CORE_SOURCES = {"bgi_core.rpy", "bgi_func.rpy"}
NOOP_RE = re.compile(r"^(?P<indent>[ \t]+)\$ bgi_line\(.*\)\s*$")
SAFE_RE = re.compile(
    r"^(?P<indent>[ \t]+)\$ (?P<expression>bgi_(?:"
    r"push_dword|push_offset|push_base_offset|push_string|"
    r"load|move|move_arg|load_base|store_base|"
    r"reg_exception_handler|unreg_exception_handler|"
    r"add|sub|mul|div|sar|eq|neq|leq|geq|lt|gt|"
    r"bool_and|bool_or|bool_zero"
    r")\(.*\))\s*$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Optimize generated BGI-style Ren'Py sources in the build tree."
    )
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update_manifest(path: Path, game: Path, optimized_names: set[str]) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    updated = set()
    for entry in manifest["files"]:
        destination = Path(entry["destination"])
        if destination.parent != Path("game") or destination.name not in optimized_names:
            continue
        optimized = game / destination.name
        entry["size"] = optimized.stat().st_size
        entry["sha256"] = sha256(optimized)
        updated.add(destination.name)
    missing = optimized_names - updated
    if missing:
        raise ValueError("optimized scripts missing from game manifest: %s" % ", ".join(sorted(missing)))
    manifest["total_bytes"] = sum(entry["size"] for entry in manifest["files"])
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def flush_group(output: list[str], group: list[tuple[str, str]]) -> tuple[int, int]:
    if not group:
        return 0, 0
    if len(group) == 1:
        indent, expression = group[0]
        output.append("%s$ %s\n" % (indent, expression))
        return 0, 0
    indent = group[0][0]
    output.append("%spython:\n" % indent)
    for _indent, expression in group:
        output.append("%s    %s\n" % (indent, expression))
    return 1, len(group)


def optimize(path: Path) -> dict[str, int] | None:
    source = path.read_text(encoding="utf-8")
    if "bgi_line(" not in source:
        return None

    output: list[str] = []
    group: list[tuple[str, str]] = []
    removed_noops = 0
    groups = 0
    grouped_statements = 0

    for line in source.splitlines(keepends=True):
        if NOOP_RE.match(line):
            removed_noops += 1
            continue

        match = SAFE_RE.match(line)
        if match:
            indent = match.group("indent")
            if group and group[0][0] != indent:
                added_groups, added_statements = flush_group(output, group)
                groups += added_groups
                grouped_statements += added_statements
                group = []
            group.append((indent, match.group("expression")))
            continue

        added_groups, added_statements = flush_group(output, group)
        groups += added_groups
        grouped_statements += added_statements
        group = []
        output.append(line)

    added_groups, added_statements = flush_group(output, group)
    groups += added_groups
    grouped_statements += added_statements

    optimized = "".join(output)
    path.write_text(optimized, encoding="utf-8")
    return {
        "removed_noop_statements": removed_noops,
        "python_groups": groups,
        "grouped_statements": grouped_statements,
        "source_bytes": len(source.encode("utf-8")),
        "optimized_bytes": len(optimized.encode("utf-8")),
    }


def main() -> int:
    args = parse_args()
    game = args.game.resolve()
    if not game.is_dir():
        raise FileNotFoundError("game build directory not found: %s" % game)

    files = {}
    for path in sorted(game.glob("*.rpy")):
        if path.name in CORE_SOURCES:
            continue
        result = optimize(path)
        if result is not None:
            files[path.name] = result

    totals = {
        key: sum(item[key] for item in files.values())
        for key in (
            "removed_noop_statements",
            "python_groups",
            "grouped_statements",
            "source_bytes",
            "optimized_bytes",
        )
    }
    update_manifest(args.manifest, game, set(files))
    report = {"format": 1, "mode": "build-copy-only", "files": files, "totals": totals}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("optimized BGI sources: %d" % len(files))
    print("removed no-op statements: %d" % totals["removed_noop_statements"])
    print(
        "grouped safe statements: %d into %d Python blocks"
        % (totals["grouped_statements"], totals["python_groups"])
    )
    print("report: %s" % args.report)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, UnicodeDecodeError, ValueError) as error:
        print("error: %s" % error, file=sys.stderr)
        raise SystemExit(2)
