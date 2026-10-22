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

from scale_vita_images import SIZES_NAME, scaled

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME = PROJECT_ROOT / "build/game"
REQUIRED_FILES = {
    "script.rpy", "options.rpy", "gui.rpy", "screens.rpy",
    "bgi_core.rpy", "bgi_func.rpy", "makerlogo.rpym", "main.rpym",
    "1-1_0710_dream.rpym", "vita_ui.rpy", "vita_renderer.rpy",
    "vita_lazy_modules.rpy", SIZES_NAME,
    "simhei.ttf", "gui/main_menu.webp",
    "images/logo1.webp", "images/SGScSlct990000.webp",
    "audio/bgm003.ogg", "audio/bgm019.ogg",
}
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def read_file(path: Path, digest_content: bool) -> tuple[bytes, str | None]:
    """Return the file header and, if requested, its SHA-256 in one pass."""
    with path.open("rb") as stream:
        header = stream.read(32)
        if not digest_content:
            return header, None
        digest = hashlib.sha256(header)
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return header, digest.hexdigest()


def valid_magic(header: bytes, suffix: str) -> bool:
    suffix = suffix.casefold()
    if suffix == ".webp":
        return header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    if suffix == ".ogg":
        return header.startswith(b"OggS")
    if suffix == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".ttf", ".otf"}:
        return header.startswith((b"\x00\x01\x00\x00", b"OTTO", b"ttcf"))
    return True


def png_dimensions(header: bytes, path: Path) -> tuple[int, int]:
    if len(header) < 24 or not header.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("invalid PNG: %s" % path)
    return struct.unpack(">II", header[16:24])


def webp_dimensions(header: bytes) -> tuple[int, int] | None:
    kind = header[12:16]
    if kind == b"VP8 " and len(header) >= 30:
        width, height = struct.unpack_from("<HH", header, 26)
        return width & 0x3FFF, height & 0x3FFF
    if kind == b"VP8L" and len(header) >= 25:
        bits = int.from_bytes(header[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if kind == b"VP8X" and len(header) >= 30:
        return (
            int.from_bytes(header[24:27], "little") + 1,
            int.from_bytes(header[27:30], "little") + 1,
        )
    return None


def read_image_sizes(path: Path | None, errors: list[str]) -> dict[str, tuple[int, int]]:
    if path is None:
        return {}
    sizes = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fields = line.split("\t")
        if len(fields) != 3 or not fields[1].isdigit() or not fields[2].isdigit():
            errors.append("malformed %s line %d" % (SIZES_NAME, number))
            continue
        sizes[fields[0]] = (int(fields[1]), int(fields[2]))
    return sizes


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
            "renpy.display.im.Image(filename), size=vita_image_size(image_name)",
            'VITA_SELECTED_FILL = "#8fd3f4"',
            'VITA_SELECTED_HOVER_TEXT = "#002c5c"',
            "default persistent.vita_side_buttons = True",
            'textbutton "Show Side Buttons" action ToggleField(persistent, "vita_side_buttons")',
            "if quick_menu and persistent.vita_side_buttons:",
            "config.change_language_callbacks.append(vita_menu_styles)",
            'restyle("game_menu_viewport", keyboard_focus=False)',
            "renpy.display.behavior.Bar.event = vita_bar_event_direct",
            '"_call_splashscreen_1" in renpy.get_return_stack()',
            "config.label_callback = vita_label_callback",
        ),
        errors,
    )
    require_text(
        game / "options.rpy",
        (
            'define config.name = _("Subahibi")',
            'define config.version = "1.0.0"',
            "define config.developer = False", "define config.console = False",
        ),
        errors,
    )
    require_text(
        game / "screens.rpy",
        (
            'use file_slots(_("Load"), load_mode=True)',
            "action (FileLoad(slot) if load_mode else FileSave(slot))",
            'key "pad_b_press" action Return()',
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

    ui_assets_path = game.parent / "VITA_UI_ASSETS.json"
    if not ui_assets_path.is_file():
        errors.append("Vita UI-assets report is missing")
    else:
        ui_assets = json.loads(ui_assets_path.read_text(encoding="utf-8")).get("assets", {})
        for relative, dimensions, measure in (
            ("gui/textbox.png", (1280, 320), lambda header, path: png_dimensions(header, path)),
            ("gui/main_menu.webp", (725, 544), lambda header, path: webp_dimensions(header)),
        ):
            asset = actual_files.get(relative)
            if asset is None:
                errors.append("Vita UI asset is missing: %s" % relative)
                continue
            header, digest = read_file(asset, True)
            if measure(header, asset) != dimensions:
                errors.append("Vita UI asset is not %dx%d: %s" % (dimensions + (relative,)))
            if digest != ui_assets.get(relative, {}).get("output_sha256"):
                errors.append("Vita UI asset does not match UI-assets report: %s" % relative)

    if set(actual_files) != set(expected_files):
        missing = sorted(set(expected_files) - set(actual_files))
        extra = sorted(set(actual_files) - set(expected_files))
        if missing:
            errors.append("manifest files missing: %s" % ", ".join(missing))
        if extra:
            errors.append("unmanifested files present: %s" % ", ".join(extra))

    image_sizes = read_image_sizes(actual_files.get(SIZES_NAME), errors)
    for relative, path in sorted(actual_files.items()):
        if any(part.startswith("x-") for part in Path(relative).parts):
            errors.append("unrestored x- path: %s" % relative)
        if relative.startswith(("cache/", "tl/")):
            errors.append("generated/runtime directory copied: %s" % relative)
        entry = expected_files.get(relative)
        size_matches = entry is not None and path.stat().st_size == entry["size"]
        header, digest = read_file(path, size_matches)
        if not valid_magic(header, path.suffix):
            errors.append("unexpected file signature: %s" % relative)
        if entry:
            if not size_matches:
                errors.append("size mismatch: %s" % relative)
            elif digest != entry["sha256"]:
                errors.append("SHA-256 mismatch: %s" % relative)
        if relative.startswith("images/"):
            original = image_sizes.pop(Path(relative).stem.lower(), None)
            if original is None:
                errors.append("image is missing from %s: %s" % (SIZES_NAME, relative))
            elif webp_dimensions(header) != (scaled(original[0]), scaled(original[1])):
                errors.append("image is not scaled to the Vita display: %s" % relative)
    if image_sizes:
        errors.append(
            "%s lists missing images: %s" % (SIZES_NAME, ", ".join(sorted(image_sizes)))
        )

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
