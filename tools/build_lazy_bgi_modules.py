#!/usr/bin/env python3
"""Turn optimized BGI scripts into on-demand Ren'Py modules."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import textwrap
from pathlib import Path

from optimize_bgi_scripts import optimize_source
from project_paths import PROJECT_ROOT


DEFAULT_GAME = PROJECT_ROOT / "build/game"
DEFAULT_MANIFEST = PROJECT_ROOT / "build/GAME_MANIFEST.json"
DEFAULT_OPTIMIZATION = PROJECT_ROOT / "build/BGI_OPTIMIZATION_REPORT.json"
DEFAULT_REPORT = PROJECT_ROOT / "build/BGI_MODULE_REPORT.json"
LAZY_SOURCE = "vita_lazy_modules.rpy"
LABEL_RE = re.compile(r"^label\s+([A-Za-z0-9_]+)\s*:", re.MULTILINE)

# Ren'Py names script nodes (filename, version, serial): the version is the
# time the file was compiled and the serial counts the statements compiled
# before the node. The build pins the version, so its own saves resolve
# directly. Earlier releases named the nodes of the files below; the statement
# index (serial - first serial) addresses the same statement of the shipped
# file. Each row is (save filename, version, shipped file, first serial,
# statements in the save's layout).
#
# The PC release compiled the unoptimized chapters: rows for optimized files
# translate through the optimizer's statement map.
PC_RELEASE_LAYOUTS = (
    ("game/1-1_0710_dream.rpy", 1618583803, "1-1_0710_dream.rpy", 0, 1730),
    ("game/main.rpy", 1618583894, "main.rpy", 799290, 183),
    ("game/bgi_func.rpy", 1618583891, "bgi_func.rpy", 774318, 804),
    ("game/script.rpy", 1618583488, "script.rpy", 740, 33),
)
# Vita builds that stamped wall-clock versions compiled the shipped statements
# but four fewer of them in the vita_*.rpy files, so their module serials are
# four lower.
WALL_CLOCK_LAYOUTS = (
    ("game/1-1_0710_dream.rpym", 1787262624, "1-1_0710_dream.rpy", 2461, 760),
    ("game/bgi_func.rpy", 1787262624, "bgi_func.rpy", 810, 804),
    ("game/script.rpy", 1787262624, "script.rpy", 2391, 33),
    ("game/main.rpym", 1787262652, "main.rpy", 316091, 94),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile generated BGI chapters as modules loaded on demand."
    )
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--optimization", type=Path, default=DEFAULT_OPTIMIZATION)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def legacy_layouts(game: Path, manifest: dict, renamed: dict[str, str]) -> dict:
    """Map (save filename, version) to (current filename, first serial,
    current statements, statement map or None)."""

    sources = {Path(entry["destination"]).name: entry["source"] for entry in manifest["files"]}
    layouts = {}
    for save_name, version, shipped, first, statements in WALL_CLOCK_LAYOUTS:
        current = "game/" + renamed.get(shipped, shipped)
        layouts[(save_name, version)] = (current, first, statements, None)
    for save_name, version, shipped, first, statements in PC_RELEASE_LAYOUTS:
        current = "game/" + renamed.get(shipped, shipped)
        if shipped not in renamed:
            layouts[(save_name, version)] = (current, first, statements, None)
            continue
        source = PROJECT_ROOT / sources[shipped]
        optimized, _result, statement_map = optimize_source(source.read_text(encoding="utf-8"))
        if optimized != (game / renamed[shipped]).read_text(encoding="utf-8"):
            raise ValueError("%s does not optimize to the shipped %s" % (source, shipped))
        if statement_map is None or len(statement_map) != statements:
            raise ValueError("%s no longer has the PC release's statements" % source)
        current_statements = max(index for index in statement_map if index is not None) + 1
        layouts[(save_name, version)] = (current, first, current_statements, statement_map)
    return layouts


def layouts_source(layouts: dict) -> str:
    lines = ["{"]
    for key, (current, first, statements, statement_map) in sorted(layouts.items()):
        if statement_map is None:
            map_source = "None"
        else:
            items = textwrap.fill(
                ", ".join(repr(index) for index in statement_map),
                width=88,
                initial_indent=" " * 12,
                subsequent_indent=" " * 12,
            )
            map_source = "[\n%s\n        ]" % items
        lines.append("        %r: (%r, %d, %d, %s)," % (key, current, first, statements, map_source))
    lines.append("    }")
    return "\n".join(lines)


def lazy_source(module_by_label: dict[str, str], layouts: dict) -> str:
    mapping = json.dumps(module_by_label, indent=8, sort_keys=True)
    return '''# Generated for the Vita build. The editable BGI sources remain unchanged.

init 1000 python:
    import os

    bgi_lazy_module_by_label = %s
    bgi_lazy_label_by_module = dict(
        (module_name, label)
        for label, module_name in bgi_lazy_module_by_label.items()
    )
    bgi_lazy_module_names = set(bgi_lazy_module_by_label.values())
    bgi_lazy_loaded_modules = set()
    bgi_lazy_active_module = None

    def bgi_lazy_load_module(module_name):
        global bgi_lazy_active_module
        if not module_name:
            return
        entry_label = bgi_lazy_label_by_module.get(module_name)
        if entry_label is None:
            raise Exception("unknown lazy BGI module: %%s" %% module_name)
        # The loaded-module set belongs to the rollbackable store and is also
        # restored by saves. The script namemap is the authority for what this
        # process has really loaded.
        if renpy.has_label(entry_label):
            bgi_lazy_loaded_modules.add(module_name)
            bgi_lazy_active_module = module_name
            return
        initcode = renpy.game.script.load_module(module_name)
        if initcode:
            raise Exception("story module unexpectedly contains init code: %%s" %% module_name)
        renpy.game.script.analyze()
        renpy.atl.compile_all()
        bgi_lazy_loaded_modules.add(module_name)
        bgi_lazy_active_module = module_name

    def bgi_lazy_load_label(label):
        module_name = bgi_lazy_module_by_label.get(label)
        if module_name is None:
            raise Exception("no lazy BGI module provides label %%s" %% label)
        bgi_lazy_load_module(module_name)

    def bgi_lazy_save_json(data):
        modules = sorted(
            module_name
            for module_name in bgi_lazy_loaded_modules
            if module_name in bgi_lazy_module_names
        )
        if modules:
            data["subahibi_bgi_modules"] = modules
        if bgi_lazy_active_module in bgi_lazy_module_names:
            data["subahibi_bgi_module"] = bgi_lazy_active_module

    if bgi_lazy_save_json not in config.save_json_callbacks:
        config.save_json_callbacks.append(bgi_lazy_save_json)

    def bgi_f_0f0():
        _window_hide(trans=0, auto=False)
        target = bgi_stack.pop().lower().replace('-', '_')
        label = 'l' + target
        bgi_lazy_load_label(label)
        renpy.call(label)

    _SubahibiFileLoad = FileLoad

    # Saves from earlier releases name script nodes of other layouts. Alias
    # the known ones right after a save is decoded and before
    # RollbackLog.unfreeze() validates its execution contexts; Ren'Py skips
    # rollback entries it still cannot resolve. Names of this build are never
    # aliased.
    _subahibi_original_loads = renpy.loadsave.loads

    # (save filename, version) -> (current filename, first serial, current
    # statements, statement map or None for the same statement index).
    bgi_lazy_legacy_layouts = %s

    def bgi_lazy_current_nodes():
        nodes_by_file = {}
        for name, node in renpy.game.script.namemap.items():
            if isinstance(name, tuple) and len(name) == 3 and node.name == name:
                nodes_by_file.setdefault(name[0], []).append(name)
        for names in nodes_by_file.values():
            names.sort(key=lambda name: name[2])
        return nodes_by_file

    def bgi_lazy_alias_saved_node(name, nodes_by_file):
        if not isinstance(name, tuple) or len(name) != 3:
            return
        layout = bgi_lazy_legacy_layouts.get((name[0], name[1]))
        if layout is None:
            return
        filename, first_serial, statements, statement_map = layout
        names = nodes_by_file.get(filename, ())
        if len(names) != statements:
            return
        index = name[2] - first_serial
        if statement_map is not None:
            if not 0 <= index < len(statement_map):
                return
            index = statement_map[index]
            if index is None:
                return
        if 0 <= index < statements:
            renpy.game.script.namemap[name] = renpy.game.script.namemap[names[index]]

    def bgi_lazy_install_save_aliases(saved_log):
        nodes_by_file = bgi_lazy_current_nodes()
        for rollback in saved_log.log:
            context = rollback.context
            bgi_lazy_alias_saved_node(context.current, nodes_by_file)
            bgi_lazy_alias_saved_node(context.come_from_name, nodes_by_file)
            for name in context.call_location_stack:
                bgi_lazy_alias_saved_node(name, nodes_by_file)
            for name in context.return_stack:
                bgi_lazy_alias_saved_node(name, nodes_by_file)

        bgi_lazy_alias_saved_node(saved_log.fixed_rollback_boundary, nodes_by_file)
        for name, data in saved_log.forward:
            bgi_lazy_alias_saved_node(name, nodes_by_file)

    def bgi_lazy_compatible_loads(data):
        roots, saved_log = _subahibi_original_loads(data)
        bgi_lazy_install_save_aliases(saved_log)
        return roots, saved_log

    renpy.loadsave.loads = bgi_lazy_compatible_loads

    def bgi_lazy_slot_name(action):
        if action.slot:
            return str(action.name)
        page = action.page if action.page is not None else persistent._file_page
        try:
            page = int(page) + persistent._file_folder * config.file_pages_per_folder
        except ValueError:
            pass
        if config.linear_saves_page_size is not None:
            try:
                return str((int(page) - 1) * config.linear_saves_page_size + int(action.name))
            except ValueError:
                pass
        return str(page) + "-" + str(action.name)

    def bgi_lazy_modules_from_legacy_save(action):
        try:
            data = renpy.loadsave.location.load(bgi_lazy_slot_name(action))
        except Exception:
            return []

        matches = []
        matched_modules = set()

        # Ren'Py stores the complete call and return stacks as script node
        # identifiers. Parent modules such as main.rpym can appear only as a
        # filename there and not as a label. They must be present before the
        # save is unfrozen or Ren'Py falls back through the startup context.
        for module_name in sorted(bgi_lazy_module_names):
            filenames = (
                "game/%%s.rpym" %% module_name,
                "game/%%s.rpy" %% module_name,
            )
            if any(filename.encode("ascii") in data for filename in filenames):
                matches.append(module_name)
                matched_modules.add(module_name)

        matched_labels = []
        labels = sorted(bgi_lazy_module_by_label, key=len, reverse=True)
        for label in labels:
            if any(longer.startswith(label + "_") for longer in matched_labels):
                continue
            encoded = label.encode("ascii")
            if encoded in data:
                module_name = bgi_lazy_module_by_label[label]
                if module_name not in matched_modules:
                    matches.append(module_name)
                    matched_modules.add(module_name)
                matched_labels.append(label)
        return matches

    class SubahibiFileLoad(_SubahibiFileLoad):
        def __call__(self):
            module_names = FileJson(
                self.name,
                "subahibi_bgi_modules",
                page=self.page,
                slot=self.slot,
            )
            if module_names:
                for module_name in module_names:
                    bgi_lazy_load_module(module_name)

            module_name = FileJson(
                self.name,
                "subahibi_bgi_module",
                page=self.page,
                slot=self.slot,
            )
            if module_name:
                bgi_lazy_load_module(module_name)

            # Saves made by builds that only recorded the active module can
            # still contain return addresses in parent BGI modules. Recover
            # every referenced module from those legacy saves before Ren'Py
            # restores the execution context.
            if not module_names:
                for legacy_module in bgi_lazy_modules_from_legacy_save(self):
                    bgi_lazy_load_module(legacy_module)
            return _SubahibiFileLoad.__call__(self)

    FileLoad = SubahibiFileLoad
''' % (mapping, layouts_source(layouts))


def main() -> int:
    args = parse_args()
    game = args.game.resolve()
    optimization = json.loads(args.optimization.read_text(encoding="utf-8"))
    optimized_names = sorted(optimization["files"])
    module_by_label: dict[str, str] = {}
    renamed: dict[str, str] = {}

    for name in optimized_names:
        source = game / name
        text = source.read_text(encoding="utf-8")
        match = LABEL_RE.search(text)
        if match is None:
            raise ValueError("BGI source has no entry label: %s" % name)
        label = match.group(1)
        module = source.stem
        if label in module_by_label:
            raise ValueError("duplicate BGI entry label: %s" % label)
        target = source.with_suffix(".rpym")
        source.rename(target)
        module_by_label[label] = module
        renamed[name] = target.name

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    layouts = legacy_layouts(game, manifest, renamed)
    generated = game / LAZY_SOURCE
    generated.write_text(lazy_source(module_by_label, layouts), encoding="utf-8")

    updated = set()
    for entry in manifest["files"]:
        destination = Path(entry["destination"])
        replacement = renamed.get(destination.name)
        if destination.parent != Path("game") or replacement is None:
            continue
        target = game / replacement
        entry["destination"] = str(Path("game") / replacement)
        entry["size"] = target.stat().st_size
        entry["sha256"] = sha256(target)
        updated.add(destination.name)
    missing = set(renamed) - updated
    if missing:
        raise ValueError("module sources missing from manifest: %s" % ", ".join(sorted(missing)))
    manifest["files"].append(
        {
            "source": "generated:%s" % LAZY_SOURCE,
            "destination": "game/%s" % LAZY_SOURCE,
            "size": generated.stat().st_size,
            "sha256": sha256(generated),
        }
    )
    manifest["file_count"] = len(manifest["files"])
    manifest["total_bytes"] = sum(entry["size"] for entry in manifest["files"])
    args.manifest.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    report = {
        "format": 1,
        "mode": "on-demand-rpym",
        "module_count": len(module_by_label),
        "module_by_label": module_by_label,
        "generated_loader": LAZY_SOURCE,
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("lazy BGI modules: %d" % len(module_by_label))
    print("generated loader: %s" % generated)
    print("report: %s" % args.report)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, UnicodeDecodeError, ValueError) as error:
        print("error: %s" % error, file=sys.stderr)
        raise SystemExit(2)
