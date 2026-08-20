#!/usr/bin/env python3
"""Decode BGI/Ethornell CompressedBG version 2 images to PNG.

This decoder covers the 24-bit and 32-bit DCT-based CBG variant used by the
Steam release. It requires NumPy and writes PNG files using the standard
library, so no image conversion program is required.
"""

from __future__ import annotations

import argparse
import binascii
import struct
import sys
import zlib
from pathlib import Path

import numpy as np


MAGIC = b"CompressedBG___\x00"
HEADER_SIZE = 0x30
DCT_BASIS = np.array(
    [
        1.00000000, 1.38703990, 1.30656302, 1.17587554, 1.00000000, 0.78569496, 0.54119611, 0.27589938,
        1.38703990, 1.92387950, 1.81225491, 1.63098633, 1.38703990, 1.08979023, 0.75066054, 0.38268343,
        1.30656302, 1.81225491, 1.70710683, 1.53635550, 1.30656302, 1.02655995, 0.70710677, 0.36047992,
        1.17587554, 1.63098633, 1.53635550, 1.38268340, 1.17587554, 0.92387950, 0.63637930, 0.32442334,
        1.00000000, 1.38703990, 1.30656302, 1.17587554, 1.00000000, 0.78569496, 0.54119611, 0.27589938,
        0.78569496, 1.08979023, 1.02655995, 0.92387950, 0.78569496, 0.61731654, 0.42521504, 0.21677275,
        0.54119611, 0.75066054, 0.70710677, 0.63637930, 0.54119611, 0.42521504, 0.29289323, 0.14931567,
        0.27589938, 0.38268343, 0.36047992, 0.32442334, 0.27589938, 0.21677275, 0.14931567, 0.07612047,
    ],
    dtype=np.float32,
).reshape(8, 8)
BLOCK_FILL_ORDER = np.array(
    [
        0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
        12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
        35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
        58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63,
    ],
    dtype=np.int16,
)


class BitReader:
    def __init__(self, data: bytes, position: int = 0) -> None:
        self.data = data
        self.position = position
        self.cache = 0
        self.cache_bits = 0

    def read_bit(self) -> int:
        if self.cache_bits == 0:
            if self.position >= len(self.data):
                raise EOFError("unexpected end of CBG bitstream")
            self.cache = self.data[self.position]
            self.position += 1
            self.cache_bits = 8
        self.cache_bits -= 1
        return (self.cache >> self.cache_bits) & 1

    def read_bits(self, count: int) -> int:
        value = 0
        for _ in range(count):
            value = (value << 1) | self.read_bit()
        return value

    def align_byte(self) -> None:
        if self.cache_bits:
            self.read_bits(self.cache_bits)


class HuffmanTree:
    def __init__(self, weights: list[int], version2: bool = False) -> None:
        self.nodes: list[dict[str, int | bool]] = [
            {"valid": weight != 0, "parent": False, "weight": weight, "left": -1, "right": -1}
            for weight in weights
        ]
        root_weight = sum(weights)
        if root_weight == 0:
            raise ValueError("CBG Huffman table has no symbols")
        while True:
            children: list[int] = []
            combined = 0
            for child_number in range(2):
                candidate = -1
                minimum = 0xFFFFFFFF
                index = 0
                if version2:
                    while index < len(self.nodes):
                        if bool(self.nodes[index]["valid"]):
                            candidate = index
                            minimum = int(self.nodes[index]["weight"])
                            index += 1
                            break
                        index += 1
                if candidate < 0:
                    index = 0
                # Version 2 preserves the first valid node on equal weights.
                if version2:
                    index = max(index, child_number + 1)
                while index < len(self.nodes):
                    if bool(self.nodes[index]["valid"]) and int(self.nodes[index]["weight"]) < minimum:
                        candidate = index
                        minimum = int(self.nodes[index]["weight"])
                    index += 1
                self.nodes[candidate]["valid"] = False
                children.append(candidate)
                combined += int(self.nodes[candidate]["weight"])
            self.nodes.append(
                {
                    "valid": True,
                    "parent": True,
                    "weight": combined,
                    "left": children[0],
                    "right": children[1],
                }
            )
            if combined >= root_weight:
                break

    def decode(self, reader: BitReader) -> int:
        index = len(self.nodes) - 1
        while bool(self.nodes[index]["parent"]):
            index = int(self.nodes[index]["right"] if reader.read_bit() else self.nodes[index]["left"])
            if index < 0:
                raise ValueError("invalid CBG Huffman branch")
        return index


def read_varint(data: bytes, position: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if position >= len(data) or shift >= 32:
            raise EOFError("invalid CBG variable-length integer")
        byte = data[position]
        position += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, position
        shift += 7


def read_weight_table(data: bytes, position: int, count: int) -> tuple[list[int], int]:
    weights: list[int] = []
    for _ in range(count):
        value, position = read_varint(data, position)
        weights.append(value)
    return weights, position


def next_key_byte(key: int) -> tuple[int, int]:
    low_product = 20021 * (key & 0xFFFF)
    high = (key >> 16) * 20021 + key * 346
    high = (high + (low_product >> 16)) & 0xFFFF
    key = ((high << 16) + (low_product & 0xFFFF) + 1) & 0xFFFFFFFF
    return key, high & 0xFF


def decrypt(data: bytes, key: int, checksum_sum: int, checksum_xor: int) -> bytes:
    output = bytearray(data)
    actual_sum = 0
    actual_xor = 0
    for index in range(len(output)):
        key, value = next_key_byte(key)
        output[index] = (output[index] - value) & 0xFF
        actual_sum = (actual_sum + output[index]) & 0xFF
        actual_xor ^= output[index]
    if actual_sum != checksum_sum or actual_xor != checksum_xor:
        raise ValueError("CBG encrypted-table checksum mismatch")
    return bytes(output)


def jpeg_signed(value: int, bit_count: int) -> int:
    if bit_count and value >> (bit_count - 1) == 0:
        return ((-1 << bit_count) | value) + 1
    return value


def float_to_sample(values: np.ndarray) -> np.ndarray:
    integers = values.astype(np.int32)
    result = 128 + (integers >> 3)
    return np.where(result <= 0, 0, np.where(result <= 255, result, np.where(result < 384, 255, 0))).astype(np.float32)


def inverse_dct_blocks(coefficients: np.ndarray, scale: np.ndarray) -> np.ndarray:
    """Run the format's scaled 8x8 inverse DCT over a batch of blocks."""
    data = coefficients.astype(np.float32) * scale[None, :, :]
    tmp = np.empty_like(data)
    for column in range(8):
        v1, v2, v3, v4, v5, v6, v7, v8 = (data[:, row, column] for row in range(8))
        v10 = v1 + v5
        v11 = v1 - v5
        v12 = v3 + v7
        v13 = (v3 - v7) * 1.414213562 - v12
        a1 = v10 + v12
        a7 = v10 - v12
        a3 = v11 + v13
        a5 = v11 - v13
        v14 = v2 + v8
        v15 = v2 - v8
        v16 = v6 + v4
        v17 = v6 - v4
        a8 = v14 + v16
        b11 = (v14 - v16) * 1.414213562
        v9 = (v17 + v15) * 1.847759065
        b10 = 1.082392200 * v15 - v9
        b13 = -2.613125930 * v17 + v9
        a6 = b13 - a8
        a4 = b11 - a6
        a2 = b10 + a4
        tmp[:, :, column] = np.stack(
            (a1 + a8, a3 + a6, a5 + a4, a7 - a2, a7 + a2, a5 - a4, a3 - a6, a1 - a8),
            axis=1,
        )

    result = np.empty_like(tmp)
    for row in range(8):
        v1, v2, v3, v4, v5, v6, v7, v8 = (tmp[:, row, column] for column in range(8))
        v10 = v1 + v5
        v11 = v1 - v5
        v12 = v3 + v7
        v13 = (v3 - v7) * 1.414213562 - v12
        a1 = v10 + v12
        a7 = v10 - v12
        a3 = v11 + v13
        a5 = v11 - v13
        v14 = v2 + v8
        v15 = v2 - v8
        v16 = v6 + v4
        v17 = v6 - v4
        a8 = v14 + v16
        b11 = (v14 - v16) * 1.414213562
        v9 = (v17 + v15) * 1.847759065
        b10 = v9 - v15 * 1.082392200
        b13 = v9 - v17 * 2.613125930
        a6 = b13 - a8
        a4 = b11 - a6
        a2 = b10 - a4
        result[:, row, :] = np.stack(
            (a1 + a8, a3 + a6, a5 + a4, a7 + a2, a7 - a2, a5 - a4, a3 - a6, a1 - a8),
            axis=1,
        )
    return float_to_sample(result)


def decode_rgb_stripe(
    block_data: bytes,
    width: int,
    bits_per_pixel: int,
    tree_dc: HuffmanTree,
    tree_ac: HuffmanTree,
    dct: np.ndarray,
) -> np.ndarray:
    coefficient_count, position = read_varint(block_data, 0)
    plane_count = 1 if bits_per_pixel == 8 else 3
    expected = width * 8 * plane_count
    if coefficient_count != expected:
        raise ValueError("unexpected CBG stripe coefficient count %d (expected %d)" % (coefficient_count, expected))
    coefficients = np.zeros(coefficient_count, dtype=np.int16)
    reader = BitReader(block_data, position)
    accumulator = 0
    for base in range(0, coefficient_count, 64):
        count = tree_dc.decode(reader)
        if count:
            accumulator += jpeg_signed(reader.read_bits(count), count)
        coefficients[base] = accumulator
    reader.align_byte()
    for base in range(0, coefficient_count, 64):
        index = 1
        while index < 64:
            code = tree_ac.decode(reader)
            if code == 0:
                break
            if code == 0x0F:
                index += 16
                continue
            index += code & 0x0F
            if index >= 64:
                break
            bit_count = code >> 4
            value = jpeg_signed(reader.read_bits(bit_count), bit_count)
            coefficients[base + int(BLOCK_FILL_ORDER[index])] = value
            index += 1

    blocks_x = width // 8
    planes = coefficients.reshape(plane_count, blocks_x, 8, 8)
    if plane_count == 1:
        gray = inverse_dct_blocks(planes[0], dct[0])
        samples = np.clip(gray.transpose(1, 0, 2).reshape(8, width) + 128.0, 0, 255).astype(
            np.uint8
        )
        result = np.full((8, width, 4), 255, dtype=np.uint8)
        result[:, :, :3] = samples[:, :, None]
        return result
    channels = np.empty((3, blocks_x, 8, 8), dtype=np.float32)
    channels[0] = inverse_dct_blocks(planes[0], dct[0])
    channels[1] = inverse_dct_blocks(planes[1], dct[1])
    channels[2] = inverse_dct_blocks(planes[2], dct[1])
    y = channels[0]
    cb = channels[1]
    cr = channels[2]
    r = np.clip(y + 1.402 * cr - 178.956, 0, 255)
    g = np.clip(y - 0.34414 * cb - 0.71414 * cr + 135.95984, 0, 255)
    b = np.clip(y + 1.772 * cb - 226.316, 0, 255)
    rgba_blocks = np.stack((r, g, b, np.full_like(r, 255)), axis=-1).astype(np.uint8)
    return rgba_blocks.transpose(1, 0, 2, 3).reshape(8, width, 4)


def decode_alpha(data: bytes, width: int, rgba: np.ndarray) -> None:
    if len(data) < 4 or struct.unpack_from("<I", data)[0] != 1:
        return
    position = 4
    pixel = 0
    control = 2
    flat = rgba.reshape(-1, 4)
    while pixel < len(flat) and position < len(data):
        control >>= 1
        if control == 1:
            control = data[position] | 0x100
            position += 1
        if control & 1:
            if position + 2 > len(data):
                break
            value = struct.unpack_from("<H", data, position)[0]
            position += 2
            x_offset = value & 0x3F
            if x_offset > 0x1F:
                x_offset -= 0x40
            y_offset = (value >> 6) & 7
            if y_offset:
                y_offset -= 8
            count = ((value >> 9) & 0x7F) + 3
            reference = pixel + x_offset + y_offset * width
            if reference < 0 or reference >= pixel:
                break
            for _ in range(count):
                if pixel >= len(flat):
                    break
                flat[pixel, 3] = flat[reference, 3]
                pixel += 1
                reference += 1
        else:
            if position >= len(data):
                break
            flat[pixel, 3] = data[position]
            position += 1
            pixel += 1


def decode_v1(
    data: bytes,
    width: int,
    height: int,
    bits_per_pixel: int,
    intermediate_length: int,
    encrypted_length: int,
    decrypted: bytes,
) -> np.ndarray:
    position = 0
    weights, position = read_weight_table(decrypted, position, 0x100)
    tree = HuffmanTree(weights, version2=False)
    reader = BitReader(data, HEADER_SIZE + encrypted_length)
    packed = bytearray(intermediate_length)
    for index in range(intermediate_length):
        packed[index] = tree.decode(reader)

    pixel_size = bits_per_pixel // 8
    output_size = width * height * pixel_size
    output = bytearray(output_size)
    source_position = 0
    destination = 0
    zero_run = False
    while destination < output_size:
        count, source_position = read_varint(packed, source_position)
        if destination + count > output_size:
            raise ValueError("CBG v1 RLE run exceeds output size")
        if not zero_run:
            end = source_position + count
            if end > len(packed):
                raise EOFError("truncated CBG v1 RLE literal run")
            output[destination : destination + count] = packed[source_position:end]
            source_position = end
        destination += count
        zero_run = not zero_run

    stride = width * pixel_size
    for y in range(height):
        line = y * stride
        for x in range(width):
            pixel = line + x * pixel_size
            for component in range(pixel_size):
                average = 0
                if x:
                    average += output[pixel + component - pixel_size]
                if y:
                    average += output[pixel + component - stride]
                if x and y:
                    average //= 2
                if average:
                    output[pixel + component] = (output[pixel + component] + average) & 0xFF

    raw = np.frombuffer(output, dtype=np.uint8).reshape(height, width, pixel_size)
    rgba = np.full((height, width, 4), 255, dtype=np.uint8)
    if bits_per_pixel == 8:
        rgba[:, :, :3] = raw
    elif bits_per_pixel == 24:
        rgba[:, :, 0] = raw[:, :, 2]
        rgba[:, :, 1] = raw[:, :, 1]
        rgba[:, :, 2] = raw[:, :, 0]
    elif bits_per_pixel == 32:
        rgba[:, :, 0] = raw[:, :, 2]
        rgba[:, :, 1] = raw[:, :, 1]
        rgba[:, :, 2] = raw[:, :, 0]
        rgba[:, :, 3] = raw[:, :, 3]
    else:
        raise ValueError("unsupported CBG v1 depth: %d" % bits_per_pixel)
    return rgba


def decode_cbg(path: Path) -> np.ndarray:
    data = path.read_bytes()
    if len(data) < HEADER_SIZE or not data.startswith(MAGIC):
        raise ValueError("not a CompressedBG image: %s" % path)
    width, height = struct.unpack_from("<HH", data, 0x10)
    bits_per_pixel = struct.unpack_from("<I", data, 0x14)[0]
    intermediate_length = struct.unpack_from("<I", data, 0x20)[0]
    key = struct.unpack_from("<I", data, 0x24)[0]
    encrypted_length = struct.unpack_from("<I", data, 0x28)[0]
    checksum_sum, checksum_xor = data[0x2C], data[0x2D]
    version = struct.unpack_from("<H", data, 0x2E)[0]
    if version not in {1, 2} or bits_per_pixel not in {8, 24, 32}:
        raise ValueError("unsupported CompressedBG version or pixel depth")
    if HEADER_SIZE + encrypted_length > len(data) or (version == 2 and encrypted_length < 0x80):
        raise ValueError("invalid CBG encrypted table length")
    decrypted = decrypt(
        data[HEADER_SIZE : HEADER_SIZE + encrypted_length], key, checksum_sum, checksum_xor
    )
    if version == 1:
        return decode_v1(
            data,
            width,
            height,
            bits_per_pixel,
            intermediate_length,
            encrypted_length,
            decrypted,
        )
    dct = np.frombuffer(decrypted[:0x80], dtype=np.uint8).astype(np.float32)
    dct = dct.reshape(2, 8, 8) * DCT_BASIS[None, :, :]
    stream = data[HEADER_SIZE + encrypted_length :]
    position = 0
    weights_dc, position = read_weight_table(stream, position, 0x10)
    weights_ac, position = read_weight_table(stream, position, 0xB0)
    tree_dc = HuffmanTree(weights_dc, version2=True)
    tree_ac = HuffmanTree(weights_ac, version2=True)
    padded_width = (width + 7) & ~7
    padded_height = (height + 7) & ~7
    y_blocks = padded_height // 8
    input_base = position + (y_blocks + 1) * 4
    if input_base > len(stream):
        raise ValueError("truncated CBG stripe offset table")
    offsets = [struct.unpack_from("<i", stream, position + index * 4)[0] - input_base for index in range(y_blocks + 1)]
    position += (y_blocks + 1) * 4
    blocks = stream[position:]
    pad_skip = ((padded_width >> 3) + 7) >> 3
    rgba = np.full((padded_height, padded_width, 4), 255, dtype=np.uint8)
    for stripe in range(y_blocks):
        start = offsets[stripe] + pad_skip
        end = offsets[stripe + 1] if stripe + 1 < y_blocks else len(blocks)
        if start < 0 or start >= len(blocks) or end <= start:
            continue
        rgba[stripe * 8 : stripe * 8 + 8] = decode_rgb_stripe(
            blocks[start:end], padded_width, bits_per_pixel, tree_dc, tree_ac, dct
        )
    if bits_per_pixel == 32 and 0 <= offsets[y_blocks] < len(blocks):
        decode_alpha(blocks[offsets[y_blocks] :], padded_width, rgba)
    return rgba[:height, :width].copy()


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)


def write_png(path: Path, rgba: np.ndarray, compression: int = 9) -> None:
    height, width, channels = rgba.shape
    if channels != 4 or rgba.dtype != np.uint8:
        raise ValueError("PNG writer expects uint8 RGBA data")
    scanlines = b"".join(b"\x00" + rgba[row].tobytes() for row in range(height))
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(scanlines, compression))
        + png_chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Decode BGI CompressedBG v2 images to PNG")
    parser.add_argument("source", type=Path, help="CBG file or directory")
    parser.add_argument("output", type=Path, help="PNG file or output directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    inputs = [source] if source.is_file() else sorted(path for path in source.rglob("*") if path.is_file())
    if not inputs:
        raise FileNotFoundError("no CBG files found: %s" % source)
    for input_path in inputs:
        if source.is_file():
            target = output if output.suffix.casefold() == ".png" else output / (input_path.name + ".png")
        else:
            target = output / input_path.relative_to(source).with_suffix(input_path.suffix + ".png")
        rgba = decode_cbg(input_path)
        write_png(target, rgba)
        print("%s -> %s (%dx%d)" % (input_path, target, rgba.shape[1], rgba.shape[0]))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, EOFError) as error:
        print("error: %s" % error, file=sys.stderr)
        raise SystemExit(1)
