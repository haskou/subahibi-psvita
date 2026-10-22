#!/usr/bin/env python3
"""Reduce no-op and rollback-invisible BGI statements in the build copy.

Saves name script nodes by a serial that counts every compiled statement, so
each rewrite here keeps the statement count of the optimized build stable from
build to build: a run of safe Python statements becomes one Python block, and
a folded ``call`` (a Call plus an implicit Pass node) becomes ``pass``
statements. ``optimize_source`` also returns the statement map that
``build_lazy_bgi_modules.py`` uses to resolve nodes named by saves of the
unoptimized PC release.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from collections import Counter
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
CALL_RE = re.compile(r"^(?P<indent>[ \t]+)call (?P<label>bgi_f_[0-9a-f]+)\s*$")
PUSH_FUNCTIONS = {"bgi_push_string", "bgi_push_dword"}

# Argument-only helper labels inlined at their call sites when every argument
# is a literal push in the pending Python group: label -> (arity, expression).
# ``{pN}`` is the N-th pushed argument; check_folded_labels() proves that the
# label body in bgi_func.rpy is exactly these pops plus this expression.
FOLDED_CALLS = {
    "bgi_f_1a5": (1, "voice('audio/' + {p1} + '.ogg')"),
    "bgi_f_1a1": (
        2,
        "renpy.music.play('audio/' + {p2} + '.ogg', channel=u'sound', "
        "relative_volume={p1}/128.0)",
    ),
    "bgi_f_14b": (2, "bgi_f14b_dict[{p2}] = {p1}"),
    "bgi_f_141": (0, "nvl_clear()"),
}


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


def check_folded_labels(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    for label, (arity, template) in FOLDED_CALLS.items():
        expected = ["$ p%d = bgi_stack.pop()" % index for index in range(arity, 0, -1)]
        expected.append(
            "$ " + template.format(**{"p%d" % index: "p%d" % index for index in range(1, arity + 1)})
        )
        expected.append("return")
        starts = [index for index, line in enumerate(lines) if line == "label %s:" % label]
        if len(starts) != 1:
            raise ValueError("%s: expected one label %s" % (path.name, label))
        body = []
        for line in lines[starts[0] + 1:]:
            if line.strip():
                body.append(line.strip())
            if line.strip() == "return":
                break
        if body != expected:
            raise ValueError("%s: label %s no longer matches its fold" % (path.name, label))


def literal_argument(expression: str) -> str | None:
    """Source of the literal argument of a BGI push, or None for other statements."""

    try:
        node = ast.parse(expression, mode="eval").body
    except SyntaxError:
        return None
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in PUSH_FUNCTIONS
        and len(node.args) == 1
        and not node.keywords
    ):
        return None
    try:
        value = ast.literal_eval(node.args[0])
    except ValueError:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    if isinstance(value, str) and not value.isascii():
        return None
    return ast.get_source_segment(expression, node.args[0])


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


def fold_call(group: list[tuple[str, str]], indent: str, label: str) -> int | None:
    """Inline a helper call into the group; returns the ``pass`` lines to emit."""

    arity, template = FOLDED_CALLS[label]
    if len(group) < arity:
        return None
    arguments = [literal_argument(expression) for _indent, expression in group[len(group) - arity:]]
    if None in arguments:
        return None
    # Before: the group's node (if any) + Call + Pass. After: one group node.
    passes = 2 if group else 1
    del group[len(group) - arity:]
    group.append((indent, template.format(**{
        "p%d" % (index + 1): argument for index, argument in enumerate(arguments)
    })))
    return passes


def source_statements(line: str) -> int | None:
    """Ren'Py statements compiled from one BGI script line, None if not a BGI line."""

    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("label "):
        return 0
    if stripped.startswith("call "):
        # A Call node plus the Pass node Ren'Py appends as its return site.
        return 2
    if stripped.startswith("$ ") or stripped in {"pass", "return"}:
        return 1
    return None


def optimize_source(source: str) -> tuple[str, dict[str, int], list[int | None] | None]:
    """Optimize one BGI script.

    Also returns the statement map: for each statement Ren'Py compiles from
    ``source``, in compile order and ending with the Return it appends to
    every file, the index of the optimized statement that continues the same
    execution, or None where the optimized script has no such position (after
    part of a Python group, or between a group and the call folded into it).
    The map is None when the source contains lines this module cannot count.
    """

    output: list[str] = []
    group: list[tuple[str, str]] = []
    statement_map: list[int | None] = []
    # Statements emitted so far, and the statement_map index that resumes
    # at the start of the pending group.
    emitted = 0
    group_head: int | None = None
    countable = True
    stats: Counter[str] = Counter()
    folded = {label: 0 for label in FOLDED_CALLS}

    def flush() -> None:
        nonlocal emitted, group_head
        if not group:
            return
        added_groups, added_statements = flush_group(output, group)
        stats["python_groups"] += added_groups
        stats["grouped_statements"] += added_statements
        if group_head is not None:
            statement_map[group_head] = emitted
        emitted += 1
        group.clear()
        group_head = None

    for line in source.splitlines(keepends=True):
        if NOOP_RE.match(line):
            stats["removed_noop_statements"] += 1
            statement_map.append(None if group else emitted)
            continue

        match = SAFE_RE.match(line)
        call = CALL_RE.match(line)
        indent = (match or call).group("indent") if match or call else None
        if (match or call) and group and group[0][0] != indent:
            flush()

        if match:
            if not group:
                group_head = len(statement_map)
            statement_map.append(None)
            group.append((indent, match.group("expression")))
            continue

        passes = None
        if call and call.group("label") in FOLDED_CALLS:
            passes = fold_call(group, indent, call.group("label"))

        if passes is None:
            flush()
            output.append(line)
            count = source_statements(line)
            if count is None:
                countable = False
                count = 0
            statement_map.extend(range(emitted, emitted + count))
            emitted += count
            continue

        folded[call.group("label")] += 1
        # The Call resumes at the group only when the folded expression is
        # all of it; its Pass resumes after the folded group, at the last pass.
        if passes == 1:
            group_head = len(statement_map)
        statement_map.append(None)
        flush()
        statement_map.append(emitted + passes - 1)
        output.extend("%spass\n" % indent for _index in range(passes))
        emitted += passes

    flush()
    statement_map.append(emitted)

    optimized = "".join(output)
    result = {
        "removed_noop_statements": stats["removed_noop_statements"],
        "python_groups": stats["python_groups"],
        "grouped_statements": stats["grouped_statements"],
        "folded_calls": sum(folded.values()),
        "source_bytes": len(source.encode("utf-8")),
        "optimized_bytes": len(optimized.encode("utf-8")),
    }
    result.update(("folded_" + label, count) for label, count in folded.items())
    return optimized, result, statement_map if countable else None


def optimize(path: Path) -> dict[str, int] | None:
    source = path.read_text(encoding="utf-8")
    if "bgi_line(" not in source:
        return None
    optimized, result, _statement_map = optimize_source(source)
    path.write_text(optimized, encoding="utf-8")
    return result


def main() -> int:
    args = parse_args()
    game = args.game.resolve()
    if not game.is_dir():
        raise FileNotFoundError("game build directory not found: %s" % game)

    check_folded_labels(game / "bgi_func.rpy")
    files = {}
    for path in sorted(game.glob("*.rpy")):
        if path.name in CORE_SOURCES:
            continue
        result = optimize(path)
        if result is not None:
            files[path.name] = result

    totals: Counter[str] = Counter()
    for item in files.values():
        totals.update(item)
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
    print(
        "folded helper calls: %d (%s)"
        % (
            totals["folded_calls"],
            ", ".join(
                "%s %d" % (label, totals["folded_" + label]) for label in FOLDED_CALLS
            ),
        )
    )
    print("report: %s" % args.report)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, UnicodeDecodeError, ValueError) as error:
        print("error: %s" % error, file=sys.stderr)
        raise SystemExit(2)
