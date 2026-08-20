#!/usr/bin/env python3
"""Decode and resize Steam CBG images into the ignored Vita asset workspace."""

from __future__ import annotations

import argparse
import concurrent.futures
import ctypes
import hashlib
import json
import os
import struct
from pathlib import Path

import numpy as np

from decode_bgi_cbg import decode_cbg, write_png
from project_paths import PROJECT_ROOT, WEBP_LIBRARY


DEFAULT_RAW = PROJECT_ROOT / "local/steam/images/raw-cbg"
DEFAULT_REFERENCE = PROJECT_ROOT / "port/game/images"
DEFAULT_OUTPUT = PROJECT_ROOT / "local/assets/optimized"
DEFAULT_INVENTORY = PROJECT_ROOT / "local/steam/inventory.json"
DEFAULT_WEBP_LIBRARY = WEBP_LIBRARY


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def webp_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("not a WebP image: %s" % path)
    position = 12
    while position + 8 <= len(data):
        kind = data[position : position + 4]
        length = struct.unpack_from("<I", data, position + 4)[0]
        payload = data[position + 8 : position + 8 + length]
        if kind == b"VP8X" and len(payload) >= 10:
            width = 1 + int.from_bytes(payload[4:7], "little")
            height = 1 + int.from_bytes(payload[7:10], "little")
            return width, height
        if kind == b"VP8 " and len(payload) >= 10 and payload[3:6] == b"\x9d\x01\x2a":
            width, height = struct.unpack_from("<HH", payload, 6)
            return width & 0x3FFF, height & 0x3FFF
        if kind == b"VP8L" and len(payload) >= 5 and payload[0] == 0x2F:
            bits = int.from_bytes(payload[1:5], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        position += 8 + length + (length & 1)
    raise ValueError("WebP dimensions not found: %s" % path)


def webp_has_alpha(path: Path) -> bool:
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("not a WebP image: %s" % path)
    position = 12
    while position + 8 <= len(data):
        kind = data[position : position + 4]
        length = struct.unpack_from("<I", data, position + 4)[0]
        payload = data[position + 8 : position + 8 + length]
        if kind == b"ALPH":
            return True
        if kind == b"VP8X" and payload:
            return bool(payload[0] & 0x10)
        position += 8 + length + (length & 1)
    return False


def cbg_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(0x30)
    if len(header) < 0x30 or not header.startswith(b"CompressedBG___\x00"):
        raise ValueError("not a CompressedBG image: %s" % path)
    return struct.unpack_from("<HH", header, 0x10)


def reference_dimensions(root: Path) -> dict[str, tuple[int, int]]:
    result = {}
    for path in sorted(root.rglob("*.webp")):
        key = path.stem.casefold()
        dimensions = webp_dimensions(path)
        previous = result.get(key)
        if previous is None or dimensions[0] * dimensions[1] < previous[0] * previous[1]:
            result[key] = dimensions
    return result


def target_dimensions(
    width: int, height: int, reference: tuple[int, int] | None
) -> tuple[int, int, int, int, str]:
    aspect = width / float(height)
    panorama = aspect > 2.0 or aspect < 0.5
    if reference is not None:
        reference_width, reference_height = reference
        maximum = 4096 if panorama else 1280
        maximum_height = 4096 if panorama else 960
        canvas_scale = min(
            1.0,
            maximum / float(reference_width),
            maximum_height / float(reference_height),
        )
        canvas_width = max(1, round(reference_width * canvas_scale))
        canvas_height = max(1, round(reference_height * canvas_scale))
        reason = "compatibility-reference"
    elif panorama:
        canvas_width = canvas_height = 4096
        reason = "panorama-overscan"
    else:
        canvas_width, canvas_height = 1280, 960
        reason = "standard-frame"
    content_scale = min(
        1.0,
        canvas_width / float(width),
        canvas_height / float(height),
    )
    content_width = max(1, round(width * content_scale))
    content_height = max(1, round(height * content_scale))
    if reference is None:
        canvas_width = content_width
        canvas_height = content_height
    return content_width, content_height, canvas_width, canvas_height, reason


def resize_rgba(source: np.ndarray, width: int, height: int) -> np.ndarray:
    source_height, source_width, _channels = source.shape
    if (source_width, source_height) == (width, height):
        return source
    x = (np.arange(width, dtype=np.float32) + 0.5) * source_width / width - 0.5
    y = (np.arange(height, dtype=np.float32) + 0.5) * source_height / height - 0.5
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x_weight = (x - x0).reshape(1, width, 1)
    y_weight = y - y0
    x0 = np.clip(x0, 0, source_width - 1)
    x1 = np.clip(x0 + 1, 0, source_width - 1)
    y0 = np.clip(y0, 0, source_height - 1)
    y1 = np.clip(y0 + 1, 0, source_height - 1)
    output = np.empty((height, width, 4), dtype=np.uint8)
    for start in range(0, height, 32):
        end = min(height, start + 32)
        top = (
            source[y0[start:end]][:, x0].astype(np.float32) * (1.0 - x_weight)
            + source[y0[start:end]][:, x1].astype(np.float32) * x_weight
        )
        bottom = (
            source[y1[start:end]][:, x0].astype(np.float32) * (1.0 - x_weight)
            + source[y1[start:end]][:, x1].astype(np.float32) * x_weight
        )
        weight = y_weight[start:end].reshape(end - start, 1, 1)
        output[start:end] = np.clip(top * (1.0 - weight) + bottom * weight, 0, 255).astype(
            np.uint8
        )
    return output


def write_webp(path: Path, rgba: np.ndarray, library_path: str, quality: float) -> None:
    library = ctypes.CDLL(library_path)
    library.WebPEncodeRGBA.argtypes = (
        ctypes.POINTER(ctypes.c_uint8),
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_float,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)),
    )
    library.WebPEncodeRGBA.restype = ctypes.c_size_t
    library.WebPFree.argtypes = (ctypes.c_void_p,)
    contiguous = np.ascontiguousarray(rgba)
    encoded = ctypes.POINTER(ctypes.c_uint8)()
    height, width, _channels = contiguous.shape
    size = library.WebPEncodeRGBA(
        contiguous.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
        width,
        height,
        width * 4,
        quality,
        ctypes.byref(encoded),
    )
    if not size:
        raise RuntimeError("libwebp failed to encode %s" % path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(ctypes.string_at(encoded, size))
    finally:
        library.WebPFree(encoded)


def process(task: dict) -> dict:
    source = Path(task["source"])
    output = Path(task["output"])
    source_width, source_height = cbg_dimensions(source)
    content_width, content_height, output_width, output_height, reason = target_dimensions(
        source_width, source_height, tuple(task["reference"]) if task["reference"] else None
    )
    reused = False
    source_has_alpha = False
    if task["format"] == "webp" and output.is_file():
        try:
            if webp_dimensions(output) != (output_width, output_height):
                raise ValueError("cached WebP dimensions do not match policy")
            source_has_alpha = webp_has_alpha(output)
            reused = True
        except (OSError, ValueError):
            reused = False
    if not reused:
        try:
            rgba = decode_cbg(source)
        except Exception as error:
            raise ValueError("failed to decode %s: %s" % (source, error)) from error
        source_has_alpha = bool(np.any(rgba[:, :, 3] != 255))
        resized = resize_rgba(rgba, content_width, content_height)
        if (content_width, content_height) != (output_width, output_height):
            canvas = np.zeros((output_height, output_width, 4), dtype=np.uint8)
            x = (output_width - content_width) // 2
            y = (output_height - content_height) // 2
            canvas[y : y + content_height, x : x + content_width] = resized
            resized = canvas
        if task["format"] == "webp":
            write_webp(output, resized, task["webp_library"], task["quality"])
        else:
            write_png(output, resized, compression=6)
    return {
        "archive": task["archive"],
        "name": task["name"],
        "source": str(source),
        "source_sha256": sha256(source),
        "source_width": source_width,
        "source_height": source_height,
        "source_has_alpha": source_has_alpha,
        "output": str(output),
        "output_sha256": sha256(output),
        "output_size": output.stat().st_size,
        "output_width": output_width,
        "output_height": output_height,
        "content_width": content_width,
        "content_height": content_height,
        "resized": (source_width, source_height) != (content_width, content_height),
        "padded": (content_width, content_height) != (output_width, output_height),
        "reason": reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--format", choices=("webp", "png"), default="webp")
    parser.add_argument("--quality", type=float, default=90.0)
    parser.add_argument("--webp-library", type=Path, default=DEFAULT_WEBP_LIBRARY)
    args = parser.parse_args()

    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    if args.format == "webp" and not args.webp_library.is_file():
        raise FileNotFoundError(
            "libwebp not found; pass --webp-library or use --format png: %s"
            % args.webp_library
        )
    references = reference_dimensions(args.reference)
    tasks = []
    duplicate_entries = []
    seen_outputs = set()
    for entry in inventory["arc_entries"]:
        if entry["kind"] != "cbg-image":
            continue
        relative = Path(Path(entry["archive"]).stem) / entry["name"]
        source = args.raw / relative
        output = args.output / relative.parent / (relative.name + "." + args.format)
        if not source.is_file():
            raise FileNotFoundError(source)
        output_key = str(output)
        if output_key in seen_outputs:
            duplicate_entries.append(
                {
                    "archive": entry["archive"],
                    "name": entry["name"],
                    "source": str(source),
                    "output": output_key,
                    "note": "duplicate archive entry with the same extracted path",
                }
            )
            continue
        seen_outputs.add(output_key)
        tasks.append(
            {
                "archive": entry["archive"],
                "name": entry["name"],
                "source": str(source),
                "output": str(output),
                "reference": references.get(Path(entry["name"]).stem.casefold()),
                "format": args.format,
                "quality": args.quality,
                "webp_library": str(args.webp_library),
            }
        )
    if args.limit is not None:
        tasks = tasks[: args.limit]

    results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for index, result in enumerate(executor.map(process, tasks), start=1):
            results.append(result)
            if index % 100 == 0 or index == len(tasks):
                print("processed %d/%d" % (index, len(tasks)), flush=True)
    results.sort(key=lambda item: (item["archive"], item["name"]))
    manifest = {
        "format": 1,
        "policy": {
            "standard_maximum": [1280, 960],
            "panorama_ratio_threshold": 2.0,
            "absolute_texture_maximum": 4096,
            "upscaling": False,
            "output_format": args.format,
            "webp_quality": args.quality if args.format == "webp" else None,
            "reference_tree": str(args.reference),
        },
        "inventory_entry_count": len(results) + len(duplicate_entries),
        "file_count": len(results),
        "duplicate_entries": duplicate_entries,
        "resized_count": sum(item["resized"] for item in results),
        "padded_count": sum(item["padded"] for item in results),
        "source_bytes": sum(Path(item["source"]).stat().st_size for item in results),
        "output_bytes": sum(item["output_size"] for item in results),
        "files": results,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("manifest: %s" % (args.output / "MANIFEST.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
