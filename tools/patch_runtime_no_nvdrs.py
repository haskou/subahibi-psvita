#!/usr/bin/env python3
"""Patch a copied Vita staging tree to skip Ren'Py's desktop NVDRS probe.

The prebuilt RenPy-Vita runtime does not provide Python's native ``_ctypes``
module. Ren'Py 7.4.9 nevertheless calls ``Interface.setup_nvdrs`` on every
platform and catches the expected ImportError. The Vita does not need this
NVIDIA desktop-driver workaround.

This tool leaves eboot.bin and the game untouched. It recompiles only
``renpy/display/core.pyo`` with the already-local Ren'Py 7.4.9 Python 2.7 host
runtime, then replaces that member in the generated staging ``python27.zip``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

from project_paths import PROJECT_ROOT, RENPY_SDK, renpy_sdk_python


DEFAULT_STAGING = PROJECT_ROOT / "build/staging"
CORE_SOURCE = RENPY_SDK / "renpy/display/core.py"
ZIP_MEMBER = "renpy/display/core.pyo"

ORIGINAL_BLOCK = """        try:
            self.setup_nvdrs()
        except:
            pass
"""

PATCHED_BLOCK = """        # NVDRS is an optional NVIDIA desktop-driver workaround. The Vita
        # runtime has no _ctypes module, so do not probe for the desktop DLL.
        pass
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    return parser.parse_args()


def rewrite_zip(archive: Path, replacement: Path) -> None:
    temporary = archive.with_suffix(".zip.tmp")
    found = False
    with zipfile.ZipFile(archive, "r") as source, zipfile.ZipFile(temporary, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == ZIP_MEMBER:
                data = replacement.read_bytes()
                found = True
            target.writestr(info, data)
    if not found:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("python27.zip does not contain %s" % ZIP_MEMBER)
    os.replace(temporary, archive)


def main() -> int:
    args = parse_args()
    staging = args.staging.resolve()

    python2 = renpy_sdk_python()
    for required in (staging / "eboot.bin", staging / "lib/python27.zip", CORE_SOURCE, python2):
        if not required.is_file():
            raise FileNotFoundError(required)

    output_zip = staging / "lib/python27.zip"
    original_zip_hash = sha256(output_zip)
    original_eboot_hash = sha256(staging / "eboot.bin")

    source_text = CORE_SOURCE.read_text(encoding="utf-8")
    occurrences = source_text.count(ORIGINAL_BLOCK)
    if occurrences != 1:
        raise RuntimeError("expected one NVDRS call block, found %d" % occurrences)
    patched_text = source_text.replace(ORIGINAL_BLOCK, PATCHED_BLOCK)

    with tempfile.TemporaryDirectory(prefix="renpy-vita-no-nvdrs-") as temporary_dir:
        temporary_path = Path(temporary_dir)
        patched_source = temporary_path / "core.py"
        patched_source.write_text(patched_text, encoding="utf-8")
        python_environment = os.environ.copy()
        python_environment["PYTHONHOME"] = str(RENPY_SDK)
        python_environment["LD_LIBRARY_PATH"] = str(RENPY_SDK / "lib/linux-x86_64")
        subprocess.run(
            [
                str(python2), "-O", "-c",
                "import py_compile, sys; py_compile.compile(sys.argv[1], doraise=True)",
                str(patched_source),
            ],
            check=True,
            env=python_environment,
        )
        compiled = temporary_path / "core.pyo"
        if not compiled.is_file():
            raise RuntimeError("Python 2.7 did not produce core.pyo")
        rewrite_zip(output_zip, compiled)

    if sha256(staging / "eboot.bin") != original_eboot_hash:
        raise RuntimeError("eboot.bin changed unexpectedly")

    print("staging: %s" % staging)
    print("patched member: %s" % ZIP_MEMBER)
    print("source python27.zip SHA-256: %s" % original_zip_hash)
    print("patched python27.zip SHA-256: %s" % sha256(output_zip))
    print("eboot.bin unchanged: yes")
    manifest_path = staging.parent / "VITA_STAGING_MANIFEST.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["runtime_patch"] = {
            "member": ZIP_MEMBER,
            "purpose": "skip unsupported desktop NVDRS probe",
            "original_python27_sha256": original_zip_hash,
            "patched_python27_sha256": sha256(output_zip),
            "eboot_unchanged": True,
        }
        files = [path for path in staging.rglob("*") if path.is_file()]
        manifest["file_count"] = len(files)
        manifest["total_bytes"] = sum(path.stat().st_size for path in files)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
