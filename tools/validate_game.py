#!/usr/bin/env python3
"""Validate the generated source payload without launching Ren'Py."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME = PROJECT_ROOT / "build/game"
REQUIRED_FILES = {
    "script.rpy", "options.rpy", "gui.rpy", "screens.rpy",
    "bgi_core.rpy", "bgi_func.rpy", "makerlogo.rpym", "main.rpym",
    "1-1_0710_dream.rpym", "vita_ui.rpy", "vita_renderer.rpy",
    "vita_lazy_modules.rpy",
    "SourceHanSansLite.ttf", "simhei.ttf", "gui/main_menu.png",
    "images/logo1.webp", "images/SGScSlct990000.webp",
    "audio/bgm003.ogg", "audio/bgm019.ogg",
}
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_magic(path: Path) -> bool:
    header = path.read_bytes()[:16]
    suffix = path.suffix.casefold()
    if suffix == ".webp":
        return header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    if suffix == ".ogg":
        return header.startswith(b"OggS")
    if suffix == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".ttf", ".otf"}:
        return header.startswith((b"\x00\x01\x00\x00", b"OTTO", b"ttcf"))
    return True


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("invalid PNG: %s" % path)
    return struct.unpack(">II", data[16:24])


def require_text(path: Path, values: tuple[str, ...], errors: list[str]) -> None:
    source = path.read_text(encoding="utf-8")
    for value in values:
        if value not in source:
            errors.append("missing source setting %r in %s" % (value, path.name))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    args = parser.parse_args()
    game = args.game.resolve()
    manifest_path = game.parent / "GAME_MANIFEST.json"
    errors: list[str] = []

    if not game.is_dir():
        errors.append("game directory is missing: %s" % game)
    if not manifest_path.is_file():
        errors.append("manifest is missing: %s" % manifest_path)
    if errors:
        for error in errors:
            print("FAIL: %s" % error)
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual_files = {
        path.relative_to(game).as_posix(): path
        for path in game.rglob("*") if path.is_file()
    }
    expected_files = {
        Path(entry["destination"]).relative_to("game").as_posix(): entry
        for entry in manifest["files"]
    }

    missing_required = sorted(REQUIRED_FILES - set(actual_files))
    if missing_required:
        errors.append("required files missing: %s" % ", ".join(missing_required))
    source_count = sum(relative.endswith((".rpy", ".rpym")) for relative in actual_files)
    if source_count != 133:
        errors.append("expected 133 Ren'Py/module sources, found %d" % source_count)
    compiled = sorted(
        relative for relative in actual_files
        if relative.endswith((".rpyc", ".rpymc"))
    )
    if compiled:
        errors.append("compiled scripts present before precompile: %s" % ", ".join(compiled))

    cjk_sources = []
    for relative, path in sorted(actual_files.items()):
        if relative.endswith((".rpy", ".rpym")) and CJK_RE.search(
            path.read_text(encoding="utf-8")
        ):
            cjk_sources.append(relative)
    if cjk_sources:
        errors.append("non-English CJK text remains in: %s" % ", ".join(cjk_sources))

    require_text(
        game / "vita_ui.rpy",
        (
            "config.screen_width = 1694", "config.screen_height = 960",
            "gui.textbox_height = 320", "style.say_dialogue.size = 40",
            "style.history_text.size = 40", '"pad_b_press"',
            'event_name == "pad_dpdown_press"',
            "config.audio_directory = None",
            "config.images_directory = None",
            "config.missing_show = vita_lazy_missing_show",
            "renpy.display.image.ImageReference.find_target = vita_lazy_find_image_reference",
        ),
        errors,
    )
    require_text(
        game / "options.rpy",
        (
            'define config.name = _("Subahibi")',
            'define config.version = "1.0.3"',
            "define config.developer = False", "define config.console = False",
        ),
        errors,
    )
    require_text(
        game / "screens.rpy",
        (
            'use file_slots(_("Load"), load_mode=True)',
            "action (FileLoad(slot) if load_mode else FileSave(slot))",
            "default_focus (load_mode and slot == first_used_slot)",
        ),
        errors,
    )
    require_text(
        game / "vita_lazy_modules.rpy",
        (
            'data["subahibi_bgi_modules"] = modules',
            '"subahibi_bgi_modules"',
            '"game/%s.rpym" % module_name',
            "if not module_names:",
        ),
        errors,
    )
    if "ImageDissolve(bgi_imdis" in (game / "bgi_func.rpy").read_text(encoding="utf-8"):
        errors.append("expensive BGI ImageDissolve remains in source")

    textbox = actual_files.get("gui/textbox.png")
    ui_assets_path = game.parent / "VITA_UI_ASSETS.json"
    if not ui_assets_path.is_file():
        errors.append("Vita UI-assets report is missing")
    elif textbox is None:
        errors.append("Vita textbox asset is missing")
    else:
        ui_assets = json.loads(ui_assets_path.read_text(encoding="utf-8"))
        if png_dimensions(textbox) != (1280, 320):
            errors.append("Vita textbox dimensions are not 1280x320")
        if sha256(textbox) != ui_assets.get("output_sha256"):
            errors.append("Vita textbox does not match UI-assets report")

    if set(actual_files) != set(expected_files):
        missing = sorted(set(expected_files) - set(actual_files))
        extra = sorted(set(actual_files) - set(expected_files))
        if missing:
            errors.append("manifest files missing: %s" % ", ".join(missing))
        if extra:
            errors.append("unmanifested files present: %s" % ", ".join(extra))

    for relative, path in sorted(actual_files.items()):
        if any(part.startswith("x-") for part in Path(relative).parts):
            errors.append("unrestored x- path: %s" % relative)
        if relative.startswith(("cache/", "tl/")):
            errors.append("generated/runtime directory copied: %s" % relative)
        if not valid_magic(path):
            errors.append("unexpected file signature: %s" % relative)
        entry = expected_files.get(relative)
        if entry:
            if path.stat().st_size != entry["size"]:
                errors.append("size mismatch: %s" % relative)
            elif sha256(path) != entry["sha256"]:
                errors.append("SHA-256 mismatch: %s" % relative)

    if len(actual_files) != manifest["file_count"]:
        errors.append("file_count mismatch")
    if sum(path.stat().st_size for path in actual_files.values()) != manifest["total_bytes"]:
        errors.append("total_bytes mismatch")

    if errors:
        for error in errors:
            print("FAIL: %s" % error)
        return 1
    print("PASS: %d files, %d bytes" % (manifest["file_count"], manifest["total_bytes"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
