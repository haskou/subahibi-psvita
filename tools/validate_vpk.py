#!/usr/bin/env python3
"""Perform a static, byte-for-byte validation of the generated Vita VPK."""

from __future__ import annotations

import argparse
import hashlib
import json
import pickletools
import struct
import sys
import zipfile
import zlib
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import BinaryIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VPK = PROJECT_ROOT / "build/dist/Subahibi.vpk"
DEFAULT_STAGING = PROJECT_ROOT / "build/staging"
DEFAULT_JSON = PROJECT_ROOT / "build/dist/VPK_VALIDATION.json"
DEFAULT_PRECOMPILE_REPORT = PROJECT_ROOT / "build/PRECOMPILE_REPORT.json"
DEFAULT_GAME_MANIFEST = PROJECT_ROOT / "build/GAME_MANIFEST.json"
EXPECTED_TITLE_ID = "SHBI00001"
EXPECTED_TITLE = "Subahibi"
EXPECTED_LIVEAREA_STYLE = "psmobile"
MAX_LIVEAREA_IMAGE_SIZE = 420 * 1024
REQUIRED_MODULES = {
    "module/libGLESv2.suprx",
    "module/libIMGEGL.suprx",
    "module/libgpu_es4_ext.suprx",
    "module/libpvrPSP2_WSEGL.suprx",
}
REQUIRED_FILES = {
    "eboot.bin",
    "sce_sys/param.sfo",
    "sce_sys/icon0.png",
    "sce_sys/livearea/contents/template.xml",
    "lib/python27.zip",
    "renpy.py",
    "game/script.rpyc",
    "game/vita_ui.rpyc",
    "game/vita_renderer.rpyc",
    "game/vita_lazy_modules.rpyc",
    "game/cache/bytecode.rpyb",
    "game/cache/pyanalysis.rpyb",
    "game/cache/screens.rpyb",
} | REQUIRED_MODULES
FORBIDDEN_RUNTIME_TRANSLATION_FILES = {
    "game/vita_translation.rpy",
    "game/vita_translation.rpyc",
    "game/vita_translation.json",
}
FORBIDDEN_VITA_PRESPLASH_FILES = {
    "game/presplash.png",
    "game/presplash.jpg",
    "game/presplash.webp",
    "game/presplash_foreground.png",
    "game/presplash_background.png",
}
RPYC_MAGIC = b"RENPY RPC2"


def sha256_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return sha256_stream(stream)


def parse_sfo(data: bytes) -> dict[str, object]:
    if len(data) < 20:
        raise ValueError("param.sfo is truncated")
    magic, version, key_offset, data_offset, entry_count = struct.unpack_from("<4sIIII", data, 0)
    if magic != b"\x00PSF":
        raise ValueError("param.sfo has invalid magic")
    if 20 + entry_count * 16 > len(data):
        raise ValueError("param.sfo index is truncated")

    values: dict[str, object] = {}
    for index in range(entry_count):
        offset = 20 + index * 16
        key_rel, value_format, value_length, value_max_length, value_rel = struct.unpack_from(
            "<HHIII", data, offset
        )
        key_start = key_offset + key_rel
        key_end = data.find(b"\x00", key_start)
        if key_end < key_start:
            raise ValueError("param.sfo key is not terminated")
        value_start = data_offset + value_rel
        value_end = value_start + value_length
        if value_end > len(data) or value_length > value_max_length:
            raise ValueError("param.sfo value is outside the file")
        key = data[key_start:key_end].decode("utf-8")
        raw = data[value_start:value_end]
        if value_format == 0x0404:
            if len(raw) != 4:
                raise ValueError("invalid DWORD length for %s" % key)
            values[key] = struct.unpack("<I", raw)[0]
        elif value_format == 0x0204:
            values[key] = raw.rstrip(b"\x00").decode("utf-8")
        else:
            values[key] = raw.hex()
    values["_version"] = version
    return values


def png_metadata(data: bytes) -> tuple[int, int, int, int]:
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n") or data[12:16] != b"IHDR":
        raise ValueError("invalid PNG")
    width, height = struct.unpack(">II", data[16:24])
    return width, height, data[24], data[25]


def rpyc_strings(data: bytes, slot: int = 1) -> list[str]:
    if not data.startswith(RPYC_MAGIC):
        raise ValueError("invalid RPYC magic")
    offset = len(RPYC_MAGIC)
    while True:
        current, start, length = struct.unpack_from("<III", data, offset)
        offset += 12
        if current == 0:
            raise ValueError("RPYC slot %d is missing" % slot)
        if current != slot:
            continue
        payload = zlib.decompress(data[start : start + length])
        return [
            argument.decode("utf-8", "replace") if isinstance(argument, bytes) else argument
            for opcode, argument, _position in pickletools.genops(payload)
            if opcode.name
            in {"BINUNICODE", "SHORT_BINUNICODE", "UNICODE", "BINSTRING", "SHORT_BINSTRING", "STRING"}
        ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vpk", type=Path, default=DEFAULT_VPK)
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--precompile-report", type=Path, default=DEFAULT_PRECOMPILE_REPORT)
    parser.add_argument("--game-manifest", type=Path, default=DEFAULT_GAME_MANIFEST)
    args = parser.parse_args()
    vpk = args.vpk.resolve()
    staging = args.staging.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not vpk.is_file():
        print("FAIL: VPK not found: %s" % vpk)
        return 1
    if not staging.is_dir():
        print("FAIL: staging not found: %s" % staging)
        return 1
    if vpk.stat().st_size >= 2**31:
        errors.append("VPK exceeds the 2-GiB VitaShell safety limit")

    staging_files = {
        path.relative_to(staging).as_posix(): path
        for path in staging.rglob("*")
        if path.is_file()
    }
    game_files = [path for name, path in staging_files.items() if name.startswith("game/")]
    game_bytes = sum(path.stat().st_size for path in game_files)
    loose_media = [
        name for name in staging_files
        if name.startswith(("game/audio/", "game/images/"))
    ]
    if loose_media:
        errors.append("media must be distributed as external RPA archives")
    media_report_path = vpk.parent / "MEDIA_ARCHIVES.json"
    if not media_report_path.is_file():
        errors.append("media archive report is missing")
    else:
        media_report = json.loads(media_report_path.read_text(encoding="utf-8"))
        if media_report.get("images") != 4908 or media_report.get("audio") != 33435:
            errors.append("media archive coverage is incomplete")
        for item in media_report.get("archives", []):
            archive_path = vpk.parent / item["name"]
            if not archive_path.is_file():
                errors.append("media archive is missing: %s" % item["name"])
            elif archive_path.stat().st_size != item["size"] or sha256_file(archive_path) != item["sha256"]:
                errors.append("media archive does not match report: %s" % item["name"])

    if not args.game_manifest.is_file():
        errors.append("game manifest is missing: %s" % args.game_manifest)
        expected_source_less_rpyc = None
    else:
        game_manifest = json.loads(args.game_manifest.read_text(encoding="utf-8"))
        if game_manifest.get("profile") != "full-media":
            errors.append("game manifest is not a full-media payload")
        expected_source_less_rpyc = sum(
            entry["destination"].endswith((".rpyc", ".rpymc"))
            for entry in game_manifest.get("files", [])
        )

    if not args.precompile_report.is_file():
        errors.append("precompile report is missing: %s" % args.precompile_report)
    else:
        precompile = json.loads(args.precompile_report.read_text(encoding="utf-8"))
        if precompile.get("mode") != "host-precompiled-renpy-7.4.9":
            errors.append("unexpected precompile mode")
        if (
            expected_source_less_rpyc is not None
            and precompile.get("source_less_game_rpyc_preserved")
            != expected_source_less_rpyc
        ):
            errors.append(
                "precompile source-less RPYC count mismatch: expected %d, got %r"
                % (
                    expected_source_less_rpyc,
                    precompile.get("source_less_game_rpyc_preserved"),
                )
            )
        for relative in precompile.get("generated_common_compiled", []):
            if "renpy/common/" + relative not in staging_files:
                errors.append("precompiled common is missing: %s" % relative)
        for relative in precompile.get("generated_game_compiled", []):
            if "game/" + relative not in staging_files:
                errors.append("precompiled game file is missing: %s" % relative)
        for relative in precompile.get("removed_compiled_sources", []):
            if relative in staging_files:
                errors.append("compiled source was not stripped: %s" % relative)
        for name, metadata in precompile.get("cache", {}).items():
            cache_file = staging_files.get("game/cache/" + name)
            if cache_file is None:
                errors.append("precompiled cache is missing: %s" % name)
            elif sha256_file(cache_file) != metadata.get("sha256"):
                errors.append("precompiled cache hash mismatch: %s" % name)

    with zipfile.ZipFile(vpk) as archive:
        corrupt = archive.testzip()
        if corrupt:
            errors.append("ZIP CRC failure: %s" % corrupt)
        members = [info for info in archive.infolist() if not info.is_dir()]
        names = [info.filename for info in members]
        duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
        if duplicates:
            errors.append("duplicate ZIP paths: %s" % ", ".join(duplicates))
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                errors.append("unsafe ZIP path: %s" % name)

        archive_names = set(names)
        missing_required = sorted(REQUIRED_FILES - archive_names)
        if missing_required:
            errors.append("required files missing: %s" % ", ".join(missing_required))
        forbidden_translation = sorted(FORBIDDEN_RUNTIME_TRANSLATION_FILES & archive_names)
        if forbidden_translation:
            errors.append(
                "runtime translation files present: %s" % ", ".join(forbidden_translation)
            )
        forbidden_presplash = sorted(FORBIDDEN_VITA_PRESPLASH_FILES & archive_names)
        if forbidden_presplash:
            errors.append(
                "Vita presplash may prevent GLES surface recreation: %s"
                % ", ".join(forbidden_presplash)
            )
        source_language_ui = sorted(
            name for name in archive_names if name.startswith("game/tl/")
        )
        if source_language_ui:
            errors.append(
                "source-language UI translation files present: %s"
                % ", ".join(source_language_ui)
            )
        if not any(name.startswith("game/") for name in names):
            errors.append("game/ payload is absent")
        lazy_modules = sorted(
            name for name in archive_names
            if name.startswith("game/") and name.endswith(".rpymc")
        )
        if len(lazy_modules) != 124:
            errors.append(
                "lazy story module count mismatch: expected 124, got %d"
                % len(lazy_modules)
            )
        if "game/2_0716.rpyc" in archive_names:
            errors.append("2_0716 is monolithic RPYC instead of a lazy RPYMC module")

        try:
            launcher = archive.read("renpy.py").decode("utf-8")
            if 'os.environ["RENPY_SEARCHPATH"] = "ux0:/data/Subahibi"' not in launcher:
                errors.append("persistent media search path is missing from renpy.py")
            if 'os.environ["RENPY_PERFORMANCE_TEST"] = "0"' not in launcher:
                errors.append("redundant Vita GL performance test is not disabled")
        except (KeyError, UnicodeDecodeError) as error:
            errors.append("cannot inspect Ren'Py launcher: %s" % error)

        try:
            overlay_strings = rpyc_strings(archive.read("game/vita_ui.rpyc"))
            overlay_tokens = set(overlay_strings)
            overlay_text = "\n".join(overlay_strings)
            for token in (
                '"Start"',
                "Start()",
                '"Load"',
                'ShowMenu("load")',
                '"About"',
                'ShowMenu("about")',
                '"Subahibi"',
                '"pad_b_press"',
                '"pad_y_press"',
                '"pad_x_press"',
                '"pad_rightshoulder_press"',
                '"pad_leftshoulder_press"',
                '"pad_leftshoulder_release"',
                '"pad_back_press"',
                '"SELECT\\nQ. Save"',
                '"L+SELECT\\nQ. Load"',
                '"START\\nMenu"',
                '"vita_overlay"',
                "vita_sidebar",
                "confirm",
                '"confirm_yes"',
                '"confirm_no"',
                '"pad_a_press"',
                "If(vita_confirm_yes, yes_action, no_action)",
                'Function(renpy.set_focus, "confirm", "confirm_no")',
            ):
                if token not in overlay_tokens:
                    errors.append("Vita UI token is missing: %s" % token)
            for marker in (
                "style.slot_time_text.size = 32",
                "config.thumbnail_width = 256",
                "config.thumbnail_height = 144",
                "config.predict_screens = False",
                "config.predict_file_pages = False",
                "config.audio_directory = None",
                "config.images_directory = None",
                "config.missing_show = vita_lazy_missing_show",
                "renpy.display.image.ImageReference.find_target = vita_lazy_find_image_reference",
                'style.navigation_button.hover_background = Solid("#e9e5f2cc")',
                'style.navigation_button.selected_idle_background = Solid("#dbeaf7dd")',
                'style.navigation_button_text.hover_color = "#5548a5"',
                'style.navigation_button_text.selected_idle_color = "#1d5597"',
                'style.vita_navigation_panel.background = Solid("#f7f9fbb8")',
                "config.reload_menu = False",
                "style.history_text.size = 40",
                "config.intra_transition = None",
                "def vita_map_pad_event(event_name):",
                'if event_name == "pad_dpdown_press":',
                'config.keymap["dismiss_unfocused"] = list(config.keymap["dismiss"])',
                'mapped += ("dismiss_unfocused",)',
                'return mapped + ("dismiss", "dismiss_unfocused")',
                "config.map_pad_event = vita_map_pad_event",
                "config.screen_width = 1694",
                "config.screen_height = 960",
                "config.layer_clipping[layer_name] = (207, 0, 1280, 960)",
                'config.top_layers.append("vita_overlay")',
                "style.vita_side_button.xsize = 190",
                "style.vita_side_button.keyboard_focus = False",
                "style.vita_confirm_prompt_text.size = 44",
                'style.vita_confirm_button.selected_idle_background = Solid("#1468a8ff")',
                'style.vita_confirm_button.selected_hover_background = Solid("#4e56a8ff")',
            ):
                if marker not in overlay_text:
                    errors.append("Vita UI marker is missing: %s" % marker)
            for forbidden in (
                '"Extra"',
                '"Help"',
                '"Quit"',
                '"Back"',
                '"Q.Save"',
                '"Q.Load"',
                '"Prefs"',
                '"Cross: Advance / Confirm\\n',
            ):
                if forbidden in overlay_tokens:
                    errors.append("forbidden Vita navigation entry remains: %s" % forbidden)
        except (KeyError, ValueError, struct.error, zlib.error) as error:
            errors.append("cannot inspect compiled Vita UI: %s" % error)

        try:
            file_screen_text = "\n".join(
                rpyc_strings(archive.read("game/screens.rpyc"))
            )
            for marker in (
                "load_mode",
                "FileLoad(slot) if load_mode else FileSave(slot)",
                "first_used_slot",
            ):
                if marker not in file_screen_text:
                    errors.append("compiled file-screen marker is missing: %s" % marker)

            lazy_loader_text = "\n".join(
                rpyc_strings(archive.read("game/vita_lazy_modules.rpyc"))
            )
            for marker in (
                "subahibi_bgi_modules",
                '"game/%s.rpym" % module_name',
                "if not module_names:",
            ):
                if marker not in lazy_loader_text:
                    errors.append("compiled lazy-load marker is missing: %s" % marker)
        except (KeyError, ValueError, struct.error, zlib.error) as error:
            errors.append("cannot inspect compiled save/load support: %s" % error)

        staging_names = set(staging_files)
        if archive_names != staging_names:
            missing = sorted(staging_names - archive_names)
            extra = sorted(archive_names - staging_names)
            if missing:
                errors.append("staging files absent from VPK: %s" % ", ".join(missing))
            if extra:
                errors.append("unexpected VPK files: %s" % ", ".join(extra))

        for info in members:
            source = staging_files.get(info.filename)
            if source is None:
                continue
            if info.file_size != source.stat().st_size:
                errors.append("size mismatch: %s" % info.filename)
                continue
            with archive.open(info) as stream:
                if sha256_stream(stream) != sha256_file(source):
                    errors.append("content mismatch: %s" % info.filename)

        try:
            sfo = parse_sfo(archive.read("sce_sys/param.sfo"))
        except (KeyError, UnicodeDecodeError, ValueError) as error:
            errors.append("cannot parse param.sfo: %s" % error)
            sfo = {}
        if sfo.get("TITLE_ID") != EXPECTED_TITLE_ID:
            errors.append("TITLE_ID mismatch: %r" % sfo.get("TITLE_ID"))
        if sfo.get("TITLE") != EXPECTED_TITLE:
            errors.append("TITLE mismatch: %r" % sfo.get("TITLE"))
        if sfo.get("APP_VER") != "01.03":
            errors.append("APP_VER mismatch: %r" % sfo.get("APP_VER"))
        if sfo.get("ATTRIBUTE2") != 12:
            errors.append("ATTRIBUTE2 mismatch: %r" % sfo.get("ATTRIBUTE2"))

        livearea_dimensions = {}
        for name, expected in {
            "sce_sys/icon0.png": (128, 128),
            "sce_sys/livearea/contents/bg.png": (840, 500),
            "sce_sys/livearea/contents/startup.png": (280, 158),
        }.items():
            try:
                png_data = archive.read(name)
                width, height, bit_depth, color_type = png_metadata(png_data)
                actual = (width, height)
                livearea_dimensions[name] = [width, height]
                if actual != expected:
                    errors.append("LiveArea dimensions for %s: %r" % (name, actual))
                if (bit_depth, color_type) != (8, 3):
                    errors.append(
                        "LiveArea PNG must be 8-bit indexed for %s; got depth %d, color type %d"
                        % (name, bit_depth, color_type)
                    )
                if len(png_data) > MAX_LIVEAREA_IMAGE_SIZE:
                    errors.append(
                        "LiveArea PNG exceeds 420 KiB for %s: %d bytes"
                        % (name, len(png_data))
                    )
            except (KeyError, ValueError) as error:
                errors.append("invalid LiveArea PNG %s: %s" % (name, error))

        try:
            template = ET.fromstring(archive.read("sce_sys/livearea/contents/template.xml"))
            if template.tag != "livearea":
                errors.append("LiveArea template root is not <livearea>")
            if template.get("style") != EXPECTED_LIVEAREA_STYLE:
                errors.append("LiveArea style mismatch: %r" % template.get("style"))
            if template.findtext("livearea-background/image") != "bg.png":
                errors.append("LiveArea background image mapping is invalid")
            if template.findtext("gate/startup-image") != "startup.png":
                errors.append("LiveArea startup image mapping is invalid")
        except (ET.ParseError, KeyError) as error:
            errors.append("invalid LiveArea template: %s" % error)

        uncompressed_size = sum(info.file_size for info in members)
        staging_size = sum(path.stat().st_size for path in staging_files.values())
        if uncompressed_size != staging_size:
            errors.append("uncompressed VPK size does not equal staging size")

    suffix_counts = Counter(Path(name).suffix.casefold() or "[no extension]" for name in staging_files)
    result = {
        "status": "FAIL" if errors else "PASS",
        "vpk": str(vpk.relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(vpk),
        "size": vpk.stat().st_size,
        "file_count": len(staging_files),
        "game_file_count": len(game_files),
        "game_size": game_bytes,
        "uncompressed_size": sum(path.stat().st_size for path in staging_files.values()),
        "title_id": sfo.get("TITLE_ID"),
        "title": sfo.get("TITLE"),
        "sfo": sfo,
        "livearea_dimensions": livearea_dimensions,
        "suffix_counts": dict(sorted(suffix_counts.items())),
        "warnings": warnings,
        "errors": errors,
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if errors:
        for error in errors:
            print("FAIL: %s" % error)
        return 1
    print("PASS: valid VPK with %d files and TITLE_ID %s" % (len(staging_files), sfo["TITLE_ID"]))
    print("SHA-256: %s" % result["sha256"])
    print("size: %d bytes" % result["size"])
    print("uncompressed: %d bytes" % result["uncompressed_size"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
