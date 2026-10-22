#!/usr/bin/env python3
"""Generate Vita-specific GUI raster assets without modifying local sources."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import io
import json
import os
import struct
import sys
import zlib
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GAME = PROJECT_ROOT / "build/game"
TEXTBOX = GAME / "gui/textbox.png"
MAIN_MENU_SOURCE = GAME / "gui/main_menu.png"
MAIN_MENU = GAME / "gui/main_menu.webp"
REPORT = PROJECT_ROOT / "build/VITA_UI_ASSETS.json"
TARGET_HEIGHT = 320
# The Vita draws the 1280x960 game rectangle at 725x544 (vita_ui.rpy), which
# shows the main-menu art at that size; vita_ui.rpy scales it back to 1280x960.
# The art ships as lossy WebP (scale_vita_images.py settings): the Vita runtime
# measured 835 ms to decode it as a 725x544 PNG against 57-82 ms for WebP
# images of the same size.
MAIN_MENU_SOURCE_SIZE = (1280, 960)
MAIN_MENU_SIZE = (725, 544)
MAIN_MENU_QUALITY = 90
MAIN_MENU_ALPHA_QUALITY = 100
MAIN_MENU_METHOD = 4
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    left_distance = abs(estimate - left)
    above_distance = abs(estimate - above)
    corner_distance = abs(estimate - upper_left)
    if left_distance <= above_distance and left_distance <= corner_distance:
        return left
    if above_distance <= corner_distance:
        return above
    return upper_left


def decode_rgba(path: Path) -> tuple[int, int, list[bytes]]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG: %s" % path)
    position = len(PNG_SIGNATURE)
    idat = []
    width = height = 0
    while position < len(data):
        length = struct.unpack_from(">I", data, position)[0]
        kind = data[position + 4 : position + 8]
        payload = data[position + 8 : position + 8 + length]
        position += 12 + length
        if kind == b"IHDR":
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if (depth, color, compression, filtering, interlace) != (8, 6, 0, 0, 0):
                raise ValueError("textbox PNG must be non-interlaced 8-bit RGBA")
        elif kind == b"IDAT":
            idat.append(payload)
        elif kind == b"IEND":
            break
    if not width or not height or not idat:
        raise ValueError("incomplete PNG: %s" % path)

    packed = zlib.decompress(b"".join(idat))
    stride = width * 4
    rows = []
    previous = bytearray(stride)
    offset = 0
    for _y in range(height):
        filter_type = packed[offset]
        offset += 1
        current = bytearray(packed[offset : offset + stride])
        offset += stride
        if filter_type > 4:
            raise ValueError("unsupported PNG filter: %d" % filter_type)
        for index in range(stride):
            left = current[index - 4] if index >= 4 else 0
            above = previous[index]
            upper_left = previous[index - 4] if index >= 4 else 0
            if filter_type == 1:
                current[index] = (current[index] + left) & 0xFF
            elif filter_type == 2:
                current[index] = (current[index] + above) & 0xFF
            elif filter_type == 3:
                current[index] = (current[index] + ((left + above) // 2)) & 0xFF
            elif filter_type == 4:
                current[index] = (current[index] + paeth(left, above, upper_left)) & 0xFF
        rows.append(bytes(current))
        previous = current
    return width, height, rows


def resize_rows(rows: list[bytes], target_height: int) -> list[bytes]:
    if target_height < 2 or len(rows) < 2:
        raise ValueError("textbox resize requires at least two rows")
    result = []
    source_last = len(rows) - 1
    target_last = target_height - 1
    for target_y in range(target_height):
        numerator = target_y * source_last
        low = numerator // target_last
        remainder = numerator % target_last
        if remainder == 0 or low == source_last:
            result.append(rows[low])
            continue
        high = low + 1
        low_weight = target_last - remainder
        result.append(
            bytes(
                (a * low_weight + b * remainder + target_last // 2) // target_last
                for a, b in zip(rows[low], rows[high])
            )
        )
    return result


def remove_lateral_fade(rows: list[bytes], width: int) -> list[bytes]:
    """Extend each row's center pixel across its full width."""
    center_offset = (width // 2) * 4
    return [row[center_offset : center_offset + 4] * width for row in rows]


def chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = binascii.crc32(kind)
    checksum = binascii.crc32(payload, checksum) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def encode_rgba(path: Path, width: int, rows: list[bytes]) -> None:
    packed = b"".join(b"\x00" + row for row in rows)
    header = struct.pack(">IIBBBBB", width, len(rows), 8, 6, 0, 0, 0)
    output = (
        PNG_SIGNATURE
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(packed, 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(output)


def update_manifest(assets: dict[Path, Path]) -> None:
    """Point each source asset's manifest entry at its generated output."""
    path = PROJECT_ROOT / "build/GAME_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entries = {entry["destination"]: entry for entry in manifest["files"]}
    for source, output in assets.items():
        destination = "game/%s" % source.relative_to(GAME).as_posix()
        entry = entries.get(destination)
        if entry is None:
            raise ValueError("%s is missing from game manifest" % destination)
        entry["destination"] = "game/%s" % output.relative_to(GAME).as_posix()
        entry["size"] = output.stat().st_size
        entry["sha256"] = sha256(output)
    manifest["total_bytes"] = sum(entry["size"] for entry in manifest["files"])
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def prepare_textbox() -> dict[str, object]:
    source_hash = sha256(TEXTBOX)
    width, source_height, rows = decode_rgba(TEXTBOX)
    if width != 1280 or source_height != 185:
        raise ValueError(
            "unexpected source textbox dimensions: %dx%d" % (width, source_height)
        )
    # The source raster combines a useful vertical fade with lateral fades that
    # make dialogue hard to read near the edges. Preserve the center column's
    # original colour and alpha profile, then extend it horizontally so the
    # enlarged Vita textbox remains translucent but has no lateral gradients.
    resized_rows = resize_rows(rows, TARGET_HEIGHT)
    if len(resized_rows) != TARGET_HEIGHT:
        raise ValueError("textbox resize produced an invalid row count")
    output_rows = remove_lateral_fade(resized_rows, width)
    encode_rgba(TEXTBOX, width, output_rows)
    output_width, output_height, output_rows = decode_rgba(TEXTBOX)
    if (output_width, output_height) != (1280, TARGET_HEIGHT):
        raise ValueError("generated textbox dimensions are invalid")
    if any(row != row[:4] * output_width for row in output_rows):
        raise ValueError("generated textbox still contains a lateral gradient")
    alpha_values = [row[3] for row in output_rows]
    if min(alpha_values) != 0 or max(alpha_values) != 204:
        raise ValueError("generated textbox did not preserve the source alpha range")
    return {
        "source_dimensions": [width, source_height],
        "output_dimensions": [output_width, output_height],
        "lateral_fade_removed": True,
        "alpha_range": [min(alpha_values), max(alpha_values)],
        "fully_opaque": False,
        "source_sha256": source_hash,
        "output_sha256": sha256(TEXTBOX),
    }


def prepare_main_menu() -> dict[str, object]:
    source_hash = sha256(MAIN_MENU_SOURCE)
    with Image.open(MAIN_MENU_SOURCE) as image:
        image.load()
        if image.size != MAIN_MENU_SOURCE_SIZE:
            raise ValueError("unexpected source main-menu dimensions: %dx%d" % image.size)
        mode = "RGBA" if "A" in image.getbands() else "RGB"
        resized = image.convert(mode).resize(MAIN_MENU_SIZE, Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    resized.save(
        buffer,
        "WEBP",
        quality=MAIN_MENU_QUALITY,
        alpha_quality=MAIN_MENU_ALPHA_QUALITY,
        method=MAIN_MENU_METHOD,
    )
    MAIN_MENU.write_bytes(buffer.getvalue())
    os.remove(MAIN_MENU_SOURCE)
    return {
        "source_dimensions": list(MAIN_MENU_SOURCE_SIZE),
        "output_dimensions": list(MAIN_MENU_SIZE),
        "source_sha256": source_hash,
        "output_sha256": sha256(MAIN_MENU),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the Vita-specific dialogue-box and main-menu raster assets."
    )
    parser.parse_args()

    textbox = prepare_textbox()
    main_menu = prepare_main_menu()
    update_manifest({TEXTBOX: TEXTBOX, MAIN_MENU_SOURCE: MAIN_MENU})
    report = {
        "format": 2,
        "mode": "generated-vita-copy",
        "assets": {"gui/textbox.png": textbox, "gui/main_menu.webp": main_menu},
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for name, asset in report["assets"].items():
        source_width, source_height = asset["source_dimensions"]
        output_width, output_height = asset["output_dimensions"]
        print("%s: %dx%d -> %dx%d" % (name, source_width, source_height, output_width, output_height))
    print("report: %s" % REPORT)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, RuntimeError, ValueError, zlib.error) as error:
        print("error: %s" % error, file=sys.stderr)
        raise SystemExit(2)
