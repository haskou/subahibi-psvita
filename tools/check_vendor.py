#!/usr/bin/env python3
"""Validate the host dependencies expected by the Vita build tools."""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

from project_paths import (
    PROJECT_ROOT,
    RENPY_SDK,
    RENPY_VITA_ARCHIVE,
    VITA_MKSFOEX,
    VITA_PACK_VPK,
    renpy_sdk_python,
)

EXPECTED_FILES = {
    RENPY_VITA_ARCHIVE:
        "74614f39b167a983f7c224c85b832d1a3f2f388c5983ff1cb1620f7e2ea6cbc7",
    RENPY_SDK / "renpy/display/core.py":
        "a08779b104eade2c44601108a80e52c73b8ed32765a10d80a240de6712cfabac",
}


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the host dependencies required by the Vita build."
    )
    parser.parse_args()

    errors: list[str] = []
    for path, expected in EXPECTED_FILES.items():
        if not path.is_file():
            errors.append("missing file: %s" % display_path(path))
            continue
        actual = sha256(path)
        if actual != expected:
            errors.append(
                "SHA-256 mismatch for %s: expected %s, got %s"
                % (display_path(path), expected, actual)
            )
    try:
        python2 = renpy_sdk_python()
    except (FileNotFoundError, ValueError) as error:
        errors.append(str(error))
        python2 = RENPY_SDK / "lib/linux-x86_64/python"
    for path in (python2, VITA_MKSFOEX, VITA_PACK_VPK):
        if not path.is_file():
            errors.append("missing executable: %s" % display_path(path))
        elif not path.stat().st_mode & 0o111:
            errors.append("not executable: %s" % display_path(path))

    runtime = RENPY_VITA_ARCHIVE
    if runtime.is_file():
        try:
            with zipfile.ZipFile(runtime) as archive:
                required = (
                    "Ren'Py PSVita Distribution Tool/Assets/eboot.bin",
                    "Ren'Py PSVita Distribution Tool/Assets/lib/python27.zip",
                    "Ren'Py PSVita Distribution Tool/Assets/renpy.py",
                )
                missing = [name for name in required if name not in archive.namelist()]
                if missing:
                    errors.append("runtime archive is missing: %s" % ", ".join(missing))
        except zipfile.BadZipFile:
            errors.append("runtime archive is not a valid ZIP")

    if errors:
        print("FAIL")
        for error in errors:
            print("- %s" % error)
        return 1
    print("PASS")
    print("RenPy-Vita runtime, Ren'Py 7.4.9 SDK, and VitaSDK host tools are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
