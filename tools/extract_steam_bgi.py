#!/usr/bin/env python3
"""Inventory and extract supported BGI/Ethornell data from a Steam install.

The source installation is opened read-only. All generated files are written
below the explicitly supplied output directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import struct
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath


ARC_MAGIC = b"BURIKO ARC20"
ARC_HEADER_SIZE = 16
ARC_ENTRY_SIZE = 128
ARC_NAME_SIZE = 96
COMPILED_MAGIC = b"BurikoCompiledScriptVer1.00"
DSC_MAGIC = b"DSC FORMAT 1.00"
CBG_MAGIC = b"CompressedBG___\x00"


@dataclass(frozen=True)
class ArcEntry:
    archive: str
    name: str
    relative_offset: int
    absolute_offset: int
    size: int
    kind: str
    magic_hex: str
    width: int | None
    height: int | None
    bits_per_pixel: int | None
    format_version: int | None


@dataclass(frozen=True)
class TextEntry:
    index: int
    text_offset: int
    kind: str
    comment: str
    code_offsets: list[int]
    text: str


@dataclass(frozen=True)
class TextReference:
    code_offset: int
    text_offset: int
    kind: str
    comment: str
    speaker: str
    text: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory ARC20 archives and extract English text from BGI scripts."
    )
    parser.add_argument("source", type=Path, help="Steam game installation directory")
    parser.add_argument("output", type=Path, help="Generated local working directory")
    parser.add_argument(
        "--extract-matching-images",
        type=Path,
        metavar="IMAGE_TREE",
        help="Extract raw ARC entries whose stem exists in IMAGE_TREE",
    )
    parser.add_argument(
        "--compare-image-tree",
        type=Path,
        metavar="IMAGE_TREE",
        help="Record filename coverage against an image tree without extracting it",
    )
    parser.add_argument(
        "--extract-all-scripts",
        action="store_true",
        help="Extract raw compiled scripts from Script/CVTD and export their text tables",
    )
    parser.add_argument(
        "--extract-all-images",
        action="store_true",
        help="Extract every CBG image payload below images/raw-cbg",
    )
    parser.add_argument(
        "--extract-all-audio",
        action="store_true",
        help="Extract every BW-wrapped Vorbis stream below audio/ogg",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode_arc_name(raw: bytes) -> str:
    raw = raw.split(b"\x00", 1)[0]
    if not raw:
        raise ValueError("ARC entry has an empty name")
    for encoding in ("shift_jis", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("shift_jis", "replace")


def safe_relative_path(name: str) -> Path:
    normalized = name.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("unsafe ARC entry path: %r" % name)
    return Path(*pure.parts)


def classify_header(header: bytes) -> str:
    if header.startswith(COMPILED_MAGIC):
        return "compiled-script"
    if header.startswith(DSC_MAGIC):
        return "dsc-script"
    if header.startswith(CBG_MAGIC):
        return "cbg-image"
    if header.startswith(b"BM"):
        return "bmp-image"
    if header.startswith(b"OggS"):
        return "ogg-audio"
    if len(header) >= 8 and header[4:8] == b"bw  ":
        return "bw-audio"
    if header.startswith(b"BSE 1.0"):
        return "bse"
    return "unknown"


def cbg_metadata(header: bytes) -> tuple[int | None, int | None, int | None, int | None]:
    if len(header) < 48 or not header.startswith(CBG_MAGIC):
        return None, None, None, None
    width, height = struct.unpack_from("<HH", header, 0x10)
    bits_per_pixel = struct.unpack_from("<I", header, 0x14)[0]
    version = struct.unpack_from("<H", header, 0x2E)[0]
    return width, height, bits_per_pixel, version


def read_arc_entries(path: Path, source: Path) -> list[ArcEntry]:
    file_size = path.stat().st_size
    entries: list[ArcEntry] = []
    with path.open("rb") as stream:
        header = stream.read(ARC_HEADER_SIZE)
        if len(header) != ARC_HEADER_SIZE or header[:12] != ARC_MAGIC:
            raise ValueError("not a BURIKO ARC20 archive: %s" % path)
        count = struct.unpack_from("<I", header, 12)[0]
        table_size = count * ARC_ENTRY_SIZE
        if ARC_HEADER_SIZE + table_size > file_size:
            raise ValueError("truncated ARC entry table: %s" % path)
        table = stream.read(table_size)
        payload_base = ARC_HEADER_SIZE + table_size
        for index in range(count):
            record = table[index * ARC_ENTRY_SIZE : (index + 1) * ARC_ENTRY_SIZE]
            name = decode_arc_name(record[:ARC_NAME_SIZE])
            relative_offset, size = struct.unpack_from("<II", record, 96)
            absolute_offset = payload_base + relative_offset
            if absolute_offset + size > file_size:
                raise ValueError(
                    "%s entry %d (%s) exceeds archive bounds" % (path, index, name)
                )
            stream.seek(absolute_offset)
            magic = stream.read(min(64, size))
            width, height, bits_per_pixel, format_version = cbg_metadata(magic)
            entries.append(
                ArcEntry(
                    archive=str(path.relative_to(source)),
                    name=name,
                    relative_offset=relative_offset,
                    absolute_offset=absolute_offset,
                    size=size,
                    kind=classify_header(magic),
                    magic_hex=magic[:16].hex(),
                    width=width,
                    height=height,
                    bits_per_pixel=bits_per_pixel,
                    format_version=format_version,
                )
            )
    return entries


def inventory_archives(source: Path) -> tuple[list[ArcEntry], list[dict[str, object]]]:
    entries: list[ArcEntry] = []
    skipped: list[dict[str, object]] = []
    for archive in sorted(source.glob("*.arc")):
        with archive.open("rb") as stream:
            header = stream.read(ARC_HEADER_SIZE)
        if header[:12] != ARC_MAGIC:
            reason = "zero-filled-placeholder" if header == bytes(len(header)) else "unsupported-magic"
            skipped.append(
                {
                    "archive": str(archive.relative_to(source)),
                    "size": archive.stat().st_size,
                    "reason": reason,
                    "magic_hex": header.hex(),
                }
            )
            continue
        entries.extend(read_arc_entries(archive, source))
    return entries, skipped


def copy_arc_entry(source: Path, entry: ArcEntry, destination: Path) -> Path:
    relative = safe_relative_path(entry.name)
    target = destination / Path(entry.archive).stem / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    archive = source / entry.archive
    with archive.open("rb") as input_stream, target.open("wb") as output_stream:
        input_stream.seek(entry.absolute_offset)
        remaining = entry.size
        while remaining:
            chunk = input_stream.read(min(1024 * 1024, remaining))
            if not chunk:
                raise EOFError("unexpected end of archive while extracting %s" % entry.name)
            output_stream.write(chunk)
            remaining -= len(chunk)
    return target


def extract_bw_ogg(source: Path, entry: ArcEntry, destination: Path) -> Path:
    relative = safe_relative_path(entry.name).with_suffix(".ogg")
    target = destination / Path(entry.archive).stem / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    archive = source / entry.archive
    with archive.open("rb") as input_stream:
        input_stream.seek(entry.absolute_offset)
        header = input_stream.read(64)
        if len(header) != 64 or header[4:8] != b"bw  ":
            raise ValueError("invalid BW audio header: %s/%s" % (entry.archive, entry.name))
        payload_size = struct.unpack_from("<I", header, 8)[0]
        if payload_size != entry.size - 64:
            raise ValueError("BW payload length mismatch: %s/%s" % (entry.archive, entry.name))
        first = input_stream.read(4)
        if first != b"OggS":
            raise ValueError("BW payload is not Ogg Vorbis: %s/%s" % (entry.archive, entry.name))
        with target.open("wb") as output_stream:
            output_stream.write(first)
            remaining = payload_size - 4
            while remaining:
                chunk = input_stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise EOFError("unexpected end of BW audio payload")
                output_stream.write(chunk)
                remaining -= len(chunk)
    return target


def find_text_boundary(compiled: bytes) -> int:
    marker = b"\x1b\x00\x00\x00"
    position = compiled.rfind(marker)
    return len(compiled) if position < 0 else position + len(marker)


def parse_text_slots(text_pool: bytes) -> dict[int, bytes]:
    slots: dict[int, bytes] = {}
    position = 0
    while position < len(text_pool):
        end = text_pool.find(b"\x00", position)
        if end < 0:
            end = len(text_pool)
        slots[position] = text_pool[position:end]
        if end == len(text_pool):
            break
        position = end + 1
    return slots


def read_u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        return -1
    return struct.unpack_from("<I", data, offset)[0]


def decode_script_text(raw: bytes) -> str:
    for encoding in ("utf-8", "cp1252", "shift_jis"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "replace")


def classify_reference(code: bytes, position: int, slots: dict[int, bytes]) -> tuple[str, str]:
    opcode = read_u32(code, position - 4)
    if opcode == 0x7F:
        return "file", "FILE"
    if opcode != 0x03:
        return "other", "OTHER"

    def function_at(delta: int, expected: int) -> bool:
        return read_u32(code, position + delta) == expected

    if function_at(0x0C, 0x140):
        return "name", "NAME"
    if function_at(0x04, 0x140):
        # In version 1.00 calls, the dialogue pointer is eight bytes after the
        # corresponding speaker-name pointer.
        name_pointer = read_u32(code, position - 0x08)
        speaker = ""
        if name_pointer >= len(code):
            speaker_raw = slots.get(name_pointer - len(code))
            if speaker_raw is not None:
                speaker = decode_script_text(speaker_raw)
        return "text", "TEXT" + ((" [%s]" % speaker) if speaker else "")
    if function_at(0x04, 0x14B):
        return "ruby-kanji", "TEXT RUBY KANJI"
    if function_at(0x0C, 0x14B):
        return "ruby-furigana", "TEXT RUBY FURIGANA"
    if function_at(0x0C, 0x143):
        return "backlog", "TEXT BACKLOG"
    return "other", "OTHER"


def extract_text_entries(compiled: bytes) -> list[TextEntry]:
    if not compiled.startswith(COMPILED_MAGIC):
        raise ValueError("not an uncompressed BurikoCompiledScriptVer1.00 file")
    if len(compiled) < 0x20:
        raise ValueError("compiled script is truncated")
    header_size = 0x1C + read_u32(compiled, 0x1C)
    boundary = find_text_boundary(compiled)
    if not 0 <= header_size <= boundary <= len(compiled):
        raise ValueError("invalid compiled script section boundaries")
    code = compiled[header_size:boundary]
    slots = parse_text_slots(compiled[boundary:])
    references: dict[int, dict[str, object]] = {}
    ranks = {
        "other": 0,
        "file": 1,
        "ruby-furigana": 2,
        "ruby-kanji": 3,
        "backlog": 4,
        "name": 5,
        "text": 6,
    }
    for position in range(4, len(code) - 3, 4):
        value = read_u32(code, position)
        if value < len(code):
            continue
        text_offset = value - len(code)
        if text_offset not in slots:
            continue
        kind, comment = classify_reference(code, position, slots)
        current = references.setdefault(
            text_offset, {"kind": kind, "comment": comment, "code_offsets": []}
        )
        if ranks[kind] > ranks[str(current["kind"])]:
            current["kind"] = kind
            current["comment"] = comment
        current["code_offsets"].append(position)

    result: list[TextEntry] = []
    for index, offset in enumerate(sorted(references), start=1):
        info = references[offset]
        result.append(
            TextEntry(
                index=index,
                text_offset=offset,
                kind=str(info["kind"]),
                comment=str(info["comment"]),
                code_offsets=list(info["code_offsets"]),
                text=decode_script_text(slots[offset]),
            )
        )
    return result


def extract_text_references(compiled: bytes) -> list[TextReference]:
    if not compiled.startswith(COMPILED_MAGIC):
        raise ValueError("not an uncompressed BurikoCompiledScriptVer1.00 file")
    header_size = 0x1C + read_u32(compiled, 0x1C)
    boundary = find_text_boundary(compiled)
    code = compiled[header_size:boundary]
    slots = parse_text_slots(compiled[boundary:])
    references = []
    for position in range(4, len(code) - 3, 4):
        value = read_u32(code, position)
        if value < len(code):
            continue
        text_offset = value - len(code)
        raw = slots.get(text_offset)
        if raw is None:
            continue
        kind, comment = classify_reference(code, position, slots)
        speaker = ""
        if kind == "text":
            name_pointer = read_u32(code, position - 0x08)
            if name_pointer >= len(code):
                speaker_raw = slots.get(name_pointer - len(code))
                if speaker_raw is not None:
                    speaker = decode_script_text(speaker_raw)
        references.append(
            TextReference(
                code_offset=position,
                text_offset=text_offset,
                kind=kind,
                comment=comment,
                speaker=speaker,
                text=decode_script_text(raw),
            )
        )
    return references


def write_text_exports(
    script: Path, raw_root: Path, text_root: Path
) -> tuple[dict[str, object], list[TextEntry], list[TextReference]]:
    relative = script.name
    raw_target = raw_root / relative
    raw_target.parent.mkdir(parents=True, exist_ok=True)
    # Do not copy ACLs or extended metadata from removable/network volumes.
    # Some filesystems reject copystat even after the data copy succeeds.
    shutil.copyfile(script, raw_target)
    raw_target.chmod(0o644)
    data = raw_target.read_bytes()
    entries = extract_text_entries(data)
    references = extract_text_references(data)
    json_target = text_root / (relative + ".json")
    tsv_target = text_root / (relative + ".tsv")
    json_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(
        json.dumps([asdict(entry) for entry in entries], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with tsv_target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, dialect="excel-tab", lineterminator="\n")
        writer.writerow(("index", "text_offset", "kind", "comment", "code_offsets", "text"))
        for entry in entries:
            writer.writerow(
                (
                    entry.index,
                    "0x%08x" % entry.text_offset,
                    entry.kind,
                    entry.comment,
                    ",".join("0x%08x" % value for value in entry.code_offsets),
                    entry.text.replace("\r", "\\r").replace("\n", "\\n"),
                )
            )
    events_json = text_root / (relative + ".events.json")
    events_tsv = text_root / (relative + ".events.tsv")
    events_json.write_text(
        json.dumps([asdict(reference) for reference in references], ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    with events_tsv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, dialect="excel-tab", lineterminator="\n")
        writer.writerow(("code_offset", "text_offset", "kind", "speaker", "text"))
        for reference in references:
            writer.writerow(
                (
                    "0x%08x" % reference.code_offset,
                    "0x%08x" % reference.text_offset,
                    reference.kind,
                    reference.speaker,
                    reference.text.replace("\r", "\\r").replace("\n", "\\n"),
                )
            )
    return (
        {
            "script": relative,
            "size": len(data),
            "sha256": sha256(raw_target),
            "entries": len(entries),
            "kinds": dict(sorted(Counter(entry.kind for entry in entries).items())),
        },
        entries,
        references,
    )


def write_dialogue_catalog(
    output: Path, scripts: list[tuple[str, list[TextReference]]]
) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, dialect="excel-tab", lineterminator="\n")
        writer.writerow(("script", "code_offset", "text_offset", "kind", "speaker", "text"))
        for script_name, references in scripts:
            for reference in references:
                if reference.kind not in {"name", "text"}:
                    continue
                writer.writerow(
                    (
                        script_name,
                        "0x%08x" % reference.code_offset,
                        "0x%08x" % reference.text_offset,
                        reference.kind,
                        reference.speaker,
                        reference.text.replace("\r", "\\r").replace("\n", "\\n"),
                    )
                )
                count += 1
    return count


def image_stems(root: Path) -> set[str]:
    suffixes = {".webp", ".png", ".jpg", ".jpeg", ".bmp"}
    stems: set[str] = set()
    for path in root.rglob("*"):
        if path.suffix.casefold() not in suffixes:
            continue
        stem = path.stem
        if stem.startswith("x-"):
            stem = stem[2:]
        stems.add(stem.casefold())
    return stems


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_dir():
        raise FileNotFoundError("Steam installation not found: %s" % source)
    if output == source or source in output.parents:
        raise ValueError("output must not be inside the Steam installation")
    output.mkdir(parents=True, exist_ok=True)

    arc_entries, skipped_archives = inventory_archives(source)
    inventory = {
        "source": str(source),
        "source_mode": "read-only",
        "archives": len(list(source.glob("*.arc"))),
        "entries": len(arc_entries),
        "total_entry_bytes": sum(entry.size for entry in arc_entries),
        "kinds": dict(sorted(Counter(entry.kind for entry in arc_entries).items())),
        "skipped_archives": skipped_archives,
        "arc_entries": [asdict(entry) for entry in arc_entries],
    }
    if args.compare_image_tree:
        reference_stems = image_stems(args.compare_image_tree.resolve())
        steam_stems = {
            Path(entry.name).stem.casefold()
            for entry in arc_entries
            if entry.kind == "cbg-image"
        }
        inventory["image_name_comparison"] = {
            "reference_tree": str(args.compare_image_tree.resolve()),
            "reference_unique_stems": len(reference_stems),
            "steam_unique_stems": len(steam_stems),
            "matching_stems": len(reference_stems & steam_stems),
            "reference_only": sorted(reference_stems - steam_stems),
            "steam_only": sorted(steam_stems - reference_stems),
        }

    script_summaries: list[dict[str, object]] = []
    script_text: list[tuple[str, list[TextReference]]] = []
    if args.extract_all_scripts:
        script_dir = source / "Script/CVTD"
        for script in sorted(path for path in script_dir.iterdir() if path.is_file()):
            summary, entries, references = write_text_exports(
                script, output / "scripts/raw", output / "scripts/text"
            )
            script_summaries.append(summary)
            script_text.append((script.name, references))
        inventory["dialogue_catalog_entries"] = write_dialogue_catalog(
            output / "scripts/dialogue.tsv", script_text
        )
        inventory["loose_compiled_scripts"] = script_summaries

    extracted_images: list[dict[str, object]] = []
    if args.extract_matching_images or args.extract_all_images:
        wanted = (
            image_stems(args.extract_matching_images.resolve())
            if args.extract_matching_images
            else set()
        )
        for entry in arc_entries:
            if entry.kind != "cbg-image":
                continue
            if not args.extract_all_images and Path(entry.name).stem.casefold() not in wanted:
                continue
            target = copy_arc_entry(source, entry, output / "images/raw-cbg")
            extracted_images.append(
                {
                    "archive": entry.archive,
                    "name": entry.name,
                    "output": str(target.relative_to(output)),
                    "size": target.stat().st_size,
                    "sha256": sha256(target),
                }
            )
        inventory["matching_images"] = extracted_images

    extracted_audio: list[dict[str, object]] = []
    if args.extract_all_audio:
        for entry in arc_entries:
            if entry.kind != "bw-audio":
                continue
            target = extract_bw_ogg(source, entry, output / "audio/ogg")
            extracted_audio.append(
                {
                    "archive": entry.archive,
                    "name": entry.name,
                    "output": str(target.relative_to(output)),
                    "size": target.stat().st_size,
                    "sha256": sha256(target),
                }
            )
        inventory["extracted_audio"] = extracted_audio

    (output / "inventory.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Archives: %d" % inventory["archives"])
    print("ARC entries: %d" % inventory["entries"])
    print("Kinds: %s" % json.dumps(inventory["kinds"], sort_keys=True))
    print("Scripts exported: %d" % len(script_summaries))
    print("Matching CBG images extracted: %d" % len(extracted_images))
    print("Ogg audio streams extracted: %d" % len(extracted_audio))
    print("Inventory: %s" % (output / "inventory.json"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, EOFError) as error:
        print("error: %s" % error, file=sys.stderr)
        raise SystemExit(1)
