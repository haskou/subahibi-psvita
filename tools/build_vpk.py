#!/usr/bin/env python3
"""Create the Subahibi Vita VPK from the prebuilt staging tree."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from project_paths import PROJECT_ROOT, VITA_MKSFOEX, VITA_PACK_VPK


DEFAULT_STAGING = PROJECT_ROOT / "build/staging"
DEFAULT_OUTPUT = PROJECT_ROOT / "build/dist/Subahibi.vpk"
DEFAULT_MKSFOEX = VITA_MKSFOEX
DEFAULT_PACK_VPK = VITA_PACK_VPK
TITLE_ID = "SHBI00001"
TITLE = "Subahibi"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--vita-mksfoex", type=Path, default=DEFAULT_MKSFOEX)
    parser.add_argument("--vita-pack-vpk", type=Path, default=DEFAULT_PACK_VPK)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def host_command(tool: Path, *arguments: str) -> list[str]:
    return [str(tool), *arguments]


def add_arguments(staging: Path) -> list[str]:
    arguments: list[str] = []
    for item in sorted(staging.iterdir()):
        if item.name == "eboot.bin":
            continue
        if item.name == "sce_sys":
            for child in sorted(item.iterdir()):
                if child.name == "param.sfo":
                    continue
                arguments.extend(("-a", "%s=%s" % (child, Path("sce_sys") / child.name)))
            continue
        arguments.extend(("-a", "%s=%s" % (item, item.name)))
    return arguments


def main() -> int:
    args = parse_args()
    staging = args.staging.resolve()
    output = args.output.resolve()
    mksfoex = args.vita_mksfoex.resolve()
    pack_vpk = args.vita_pack_vpk.resolve()
    for tool in (mksfoex, pack_vpk):
        if not tool.is_file() or not os.access(tool, os.X_OK):
            raise FileNotFoundError("VitaSDK host tool is missing or not executable: %s" % tool)
    if not staging.is_dir():
        raise FileNotFoundError("Vita staging directory not found: %s" % staging)

    required = (
        staging / "eboot.bin",
        staging / "lib/python27.zip",
        staging / "renpy.py",
        staging / "game/script.rpyc",
        staging / "sce_sys/icon0.png",
        staging / "sce_sys/livearea/contents/template.xml",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("staging is incomplete: %s" % ", ".join(missing))

    param_sfo = staging / "sce_sys/param.sfo"
    subprocess.run(
        host_command(
            mksfoex,
            "-d", "ATTRIBUTE2=12",
            "-d", "PARENTAL_LEVEL=1",
            "-s", "APP_VER=01.10",
            "-s", "TITLE_ID=%s" % TITLE_ID,
            TITLE,
            str(param_sfo),
        ),
        check=True,
    )

    staging_manifest = staging.parent / "VITA_STAGING_MANIFEST.json"
    if staging_manifest.is_file():
        manifest = json.loads(staging_manifest.read_text(encoding="utf-8"))
        staging_files = [path for path in staging.rglob("*") if path.is_file()]
        manifest.update(
            {
                "file_count": len(staging_files),
                "total_bytes": sum(path.stat().st_size for path in staging_files),
                "title_id": TITLE_ID,
                "title": TITLE,
                "param_sfo": str(param_sfo.relative_to(PROJECT_ROOT)),
            }
        )
        staging_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        if not args.force:
            raise FileExistsError("output exists; pass --force to replace it: %s" % output)
        output.unlink()

    command = host_command(
        pack_vpk,
        "-s", str(param_sfo),
        "-b", str(staging / "eboot.bin"),
        *add_arguments(staging),
        str(output),
    )
    subprocess.run(command, check=True)
    print("TITLE_ID: %s" % TITLE_ID)
    print("title: %s" % TITLE)
    print("param.sfo: %s" % param_sfo)
    print("VPK: %s" % output)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (FileExistsError, FileNotFoundError, subprocess.CalledProcessError) as error:
        print("error: %s" % error, file=sys.stderr)
        sys.exit(2)
