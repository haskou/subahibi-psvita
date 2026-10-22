#!/usr/bin/env python3
"""Write checksums for the installable VPK and external media archives.

validate_vpk.py already hashed every release file; reuse those digests instead
of reading the 2-GiB payload again.
"""

from __future__ import annotations

import argparse
import json

from project_paths import PROJECT_ROOT


DIST = PROJECT_ROOT / "build/dist"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate checksums and metadata for the built release payload."
    )
    return parser.parse_args()


def main() -> int:
    parse_args()
    vpk = DIST / "Subahibi.vpk"
    validation = json.loads((DIST / "VPK_VALIDATION.json").read_text(encoding="utf-8"))
    media = json.loads((DIST / "MEDIA_ARCHIVES.json").read_text(encoding="utf-8"))
    if validation.get("status") != "PASS":
        raise ValueError("VPK validation did not pass")
    releases = [{"name": vpk.name, "size": validation["size"], "sha256": validation["sha256"]}]
    releases.extend(media["archives"])
    for item in releases:
        if (DIST / item["name"]).stat().st_size != item["size"]:
            raise ValueError("release file changed after validation: %s" % item["name"])
    checksums = [(item["sha256"], item["name"]) for item in releases]
    (DIST / "SHA256SUMS").write_text(
        "".join("%s  %s\n" % item for item in checksums), encoding="utf-8"
    )
    manifest = {
        "format": 1,
        "title_id": "SHBI00001",
        "vpk": releases[0],
        "media_archives": media["archives"],
    }
    (DIST / "RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print("release files: %d" % len(releases))
    for digest, name in checksums:
        print("%s  %s" % (digest, name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
