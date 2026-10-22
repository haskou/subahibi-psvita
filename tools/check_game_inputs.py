#!/usr/bin/env python3
"""Validate the complete port and prepared local media tree."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from project_paths import PROJECT_ROOT


GAME = PROJECT_ROOT / "local/prepared-game"
PORT = PROJECT_ROOT / "port/game"
REQUIRED_FILES = {
    "script.rpy", "options.rpy", "gui.rpy", "screens.rpy",
    "bgi_core.rpy", "bgi_func.rpy", "makerlogo.rpy", "main.rpy",
    "vita_ui.rpy", "vita_renderer.rpy",
    "simhei.ttf", "gui/main_menu.png",
}
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def main() -> int:
    argparse.ArgumentParser(description="Validate the port build inputs.").parse_args()
    errors: list[str] = []
    for relative in sorted(REQUIRED_FILES):
        if not (GAME / relative).is_file():
            errors.append("missing prepared game file: %s" % relative)
    checks = {
        "Ren'Py source files": (len(list(GAME.glob("*.rpy"))), 132),
        "prepared WebP images": (len(list((GAME / "images").rglob("*.webp"))), 4908),
        "prepared Ogg audio files": (len(list((GAME / "audio").rglob("*.ogg"))), 33435),
    }
    for label, (actual, expected) in checks.items():
        if actual != expected:
            errors.append("%s: expected %d, found %d" % (label, expected, actual))
    compiled = sorted(path.name for path in PORT.glob("*.rpyc"))
    if compiled:
        errors.append("compiled RPYC files present in port/game: %s" % ", ".join(compiled))
    cjk_sources = []
    for source in sorted(PORT.glob("*.rpy")):
        if CJK_RE.search(source.read_text(encoding="utf-8")):
            cjk_sources.append(source.name)
    if cjk_sources:
        errors.append("non-English CJK text remains in: %s" % ", ".join(cjk_sources))
    if errors:
        print("FAIL")
        for error in errors:
            print("- %s" % error)
        return 1
    print("PASS")
    print("The port and local media bundle are complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
