#!/usr/bin/env python3
"""Generate checksums for the installable VPK and external media archives."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from project_paths import PROJECT_ROOT


DIST = PROJECT_ROOT / "build/dist"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate checksums and metadata for the built release payload."
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parse_args()
    vpk = DIST / "Subahibi.vpk"
    validation = json.loads((DIST / "VPK_VALIDATION.json").read_text(encoding="utf-8"))
    media = json.loads((DIST / "MEDIA_ARCHIVES.json").read_text(encoding="utf-8"))
    if validation.get("status") != "PASS":
        raise ValueError("VPK validation did not pass")
    files = [vpk] + [DIST / item["name"] for item in media["archives"]]
    checksums = [(sha256(path), path.name) for path in files]
    if checksums[0][0] != validation.get("sha256"):
        raise ValueError("VPK validation hash mismatch")
    (DIST / "SHA256SUMS").write_text(
        "".join("%s  %s\n" % item for item in checksums), encoding="utf-8"
    )
    manifest = {
        "format": 1,
        "title_id": "SHBI00001",
        "vpk": {"name": vpk.name, "size": vpk.stat().st_size, "sha256": checksums[0][0]},
        "media_archives": media["archives"],
    }
    (DIST / "RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print("release files: %d" % len(files))
    for digest, name in checksums:
        print("%s  %s" % (digest, name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
