#!/usr/bin/env python3
"""Generate Vita LiveArea PNG files from the tracked source artwork."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import struct
import zlib
from pathlib import Path

import numpy as np
import pillow_avif  # noqa: F401 - registers AVIF support with Pillow.
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ICON = PROJECT_ROOT / "assets/vita-livearea/icon0.jpg"
DEFAULT_BACKGROUND = PROJECT_ROOT / "assets/vita-livearea/background.avif"
DEFAULT_OUTPUT = PROJECT_ROOT / "assets/vita-livearea/sce_sys"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def save_rgb_png(image: Image.Image, output: Path) -> None:
    image.convert("RGB").save(output, format="PNG", compress_level=6)


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def paeth(left: int, above: int, upper_left: int) -> int:
    prediction = left + above - upper_left
    left_distance = abs(prediction - left)
    above_distance = abs(prediction - above)
    diagonal_distance = abs(prediction - upper_left)
    if left_distance <= above_distance and left_distance <= diagonal_distance:
        return left
    if above_distance <= diagonal_distance:
        return above
    return upper_left


def read_rgb_png(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("not a PNG: %s" % path)
    position = 8
    compressed = bytearray()
    width = height = 0
    while position < len(data):
        length = struct.unpack_from(">I", data, position)[0]
        kind = data[position + 4 : position + 8]
        payload = data[position + 8 : position + 8 + length]
        position += 12 + length
        if kind == b"IHDR":
            width, height, depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if (depth, color_type, compression, filtering, interlace) != (8, 2, 0, 0, 0):
                raise ValueError("expected non-interlaced 8-bit RGB PNG: %s" % path)
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
    raw = zlib.decompress(bytes(compressed))
    stride = width * 3
    expected = height * (stride + 1)
    if len(raw) != expected:
        raise ValueError("unexpected PNG scanline length: %s" % path)
    output = bytearray(height * stride)
    previous = bytearray(stride)
    source = 0
    for row_index in range(height):
        filter_type = raw[source]
        source += 1
        row = bytearray(raw[source : source + stride])
        source += stride
        for index in range(stride):
            left = row[index - 3] if index >= 3 else 0
            above = previous[index]
            upper_left = previous[index - 3] if index >= 3 else 0
            if filter_type == 1:
                row[index] = (row[index] + left) & 0xFF
            elif filter_type == 2:
                row[index] = (row[index] + above) & 0xFF
            elif filter_type == 3:
                row[index] = (row[index] + ((left + above) // 2)) & 0xFF
            elif filter_type == 4:
                row[index] = (row[index] + paeth(left, above, upper_left)) & 0xFF
            elif filter_type != 0:
                raise ValueError("unsupported PNG filter: %d" % filter_type)
        start = row_index * stride
        output[start : start + stride] = row
        previous = row
    return width, height, bytes(output)


def adaptive_palette(rgb: bytes, maximum_colors: int = 256) -> np.ndarray:
    pixels = np.frombuffer(rgb, dtype=np.uint8).reshape(-1, 3)
    colors, counts = np.unique(pixels, axis=0, return_counts=True)
    boxes = [np.arange(len(colors), dtype=np.int32)]
    while len(boxes) < maximum_colors:
        candidate = -1
        candidate_score = -1
        candidate_axis = 0
        for index, members in enumerate(boxes):
            if len(members) < 2:
                continue
            ranges = np.ptp(colors[members], axis=0).astype(np.int32)
            axis = int(np.argmax(ranges))
            score = int(ranges[axis]) * int(counts[members].sum())
            if score > candidate_score:
                candidate = index
                candidate_score = score
                candidate_axis = axis
        if candidate < 0:
            break
        members = boxes.pop(candidate)
        members = members[np.argsort(colors[members, candidate_axis], kind="stable")]
        weights = counts[members]
        split = int(np.searchsorted(np.cumsum(weights), weights.sum() // 2)) + 1
        split = min(max(split, 1), len(members) - 1)
        boxes.extend((members[:split], members[split:]))

    palette = np.empty((len(boxes), 3), dtype=np.float32)
    for index, members in enumerate(boxes):
        palette[index] = np.average(colors[members], axis=0, weights=counts[members])

    # A few deterministic weighted k-means passes substantially improve edges
    # and gradients over a fixed RGB cube while retaining an indexed PNG.
    assignments = np.zeros(len(colors), dtype=np.uint8)
    for _iteration in range(5):
        for start in range(0, len(colors), 4096):
            end = min(len(colors), start + 4096)
            delta = colors[start:end, None, :].astype(np.float32) - palette[None, :, :]
            distance = np.sum(delta * delta, axis=2)
            assignments[start:end] = np.argmin(distance, axis=1).astype(np.uint8)
        updated = palette.copy()
        for index in range(len(palette)):
            members = assignments == index
            if np.any(members):
                updated[index] = np.average(colors[members], axis=0, weights=counts[members])
        if np.array_equal(np.rint(updated), np.rint(palette)):
            palette = updated
            break
        palette = updated
    return np.clip(np.rint(palette), 0, 255).astype(np.uint8)


def nearest_palette_indices(
    rgb: bytes, palette: np.ndarray, width: int, height: int
) -> bytes:
    pixels = np.frombuffer(rgb, dtype=np.uint8).reshape(height, width, 3).astype(np.float32)
    bayer = np.array(
        (
            (0, 48, 12, 60, 3, 51, 15, 63),
            (32, 16, 44, 28, 35, 19, 47, 31),
            (8, 56, 4, 52, 11, 59, 7, 55),
            (40, 24, 36, 20, 43, 27, 39, 23),
            (2, 50, 14, 62, 1, 49, 13, 61),
            (34, 18, 46, 30, 33, 17, 45, 29),
            (10, 58, 6, 54, 9, 57, 5, 53),
            (42, 26, 38, 22, 41, 25, 37, 21),
        ),
        dtype=np.float32,
    )
    threshold = (np.tile(bayer, ((height + 7) // 8, (width + 7) // 8))[:height, :width] - 31.5)
    pixels = np.clip(pixels + threshold[:, :, None] * (8.0 / 64.0), 0, 255).reshape(-1, 3)
    indices = np.empty(len(pixels), dtype=np.uint8)
    for start in range(0, len(pixels), 16384):
        end = min(len(pixels), start + 16384)
        delta = pixels[start:end, None, :].astype(np.float32) - palette[None, :, :]
        distance = np.sum(delta * delta, axis=2)
        indices[start:end] = np.argmin(distance, axis=1).astype(np.uint8)
    return indices.tobytes()


def index_png_in_place(path: Path) -> int:
    width, height, rgb = read_rgb_png(path)
    palette = adaptive_palette(rgb)
    indices = nearest_palette_indices(rgb, palette, width, height)
    scanlines = b"".join(
        b"\x00" + indices[row * width : (row + 1) * width]
        for row in range(height)
    )
    png = b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0)),
            png_chunk(b"PLTE", palette.tobytes()),
            png_chunk(b"IDAT", zlib.compress(scanlines, 9)),
            png_chunk(b"IEND", b""),
        )
    )
    path.write_bytes(png)
    return len(palette)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--icon", type=Path, default=DEFAULT_ICON)
    parser.add_argument("--background", type=Path, default=DEFAULT_BACKGROUND)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    icon = args.icon.resolve()
    background = args.background.resolve()
    output = args.output.resolve()
    for source in (icon, background):
        if not source.is_file():
            raise FileNotFoundError("LiveArea source image not found: %s" % source)

    contents = output / "livearea/contents"
    contents.mkdir(parents=True, exist_ok=True)
    icon_output = output / "icon0.png"
    background_output = contents / "bg.png"
    startup_output = contents / "startup.png"

    with Image.open(background) as source_background:
        source_background = source_background.convert("RGB")
        crop_width = 1467
        crop_height = 873
        left = (source_background.width - crop_width) // 2
        top = (source_background.height - crop_height) // 2
        cropped = source_background.crop(
            (left, top, left + crop_width, top + crop_height)
        )
        resized = cropped.resize((840, 500), Image.Resampling.LANCZOS)
        save_rgb_png(resized, background_output)

    with Image.open(icon) as source_icon:
        resized_icon = source_icon.convert("RGB").resize(
            (128, 128), Image.Resampling.LANCZOS
        )
        save_rgb_png(resized_icon, icon_output)
    # The psmobile gate begins at (580, 199) in the 960x544 LiveArea. The
    # background begins at (60, 44), so this is the exact 280x158 background
    # region beneath the gate. Keeping the gate visually continuous leaves the
    # character unobstructed and puts the Start button below the title artwork.
    with Image.open(background_output) as generated_background:
        startup = generated_background.crop((520, 155, 800, 313))
        save_rgb_png(startup, startup_output)
    palette_sizes = {
        generated: index_png_in_place(generated)
        for generated in (icon_output, background_output, startup_output)
    }

    outputs = {
        "sce_sys/icon0.png": icon_output,
        "sce_sys/livearea/contents/bg.png": background_output,
        "sce_sys/livearea/contents/startup.png": startup_output,
    }
    manifest = {
        "format": 1,
        "sources": {
            "icon": {
                "path": display_path(icon),
                "sha256": sha256(icon),
            },
            "background": {
                "path": display_path(background),
                "sha256": sha256(background),
            },
        },
        "outputs": {
            name: {
                "size": path.stat().st_size,
                "sha256": sha256(path),
                "png_bit_depth": 8,
                "png_color_type": 3,
                "palette_colors": palette_sizes[path],
            }
            for name, path in outputs.items()
        },
    }
    manifest_path = output.parent / "LIVEAREA_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("LiveArea assets generated in: %s" % output)
    print("Manifest: %s" % manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
