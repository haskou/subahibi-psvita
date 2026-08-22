#!/usr/bin/env python3
"""Patch a copied Vita staging tree to index audio archives lazily.

Ren'Py's ``renpy/loader.py`` eagerly reads every archive index during
``index_archives()`` at startup. On PS Vita hardware this costs several
seconds, most of it unpickling the ~33k entries of the two audio archives,
which are not needed until the first sound plays.

This tool defers any archive whose name contains ``audio``: its prefix is
parked in a pending list instead of being indexed, and the first failed file
lookup mounts every pending archive, rebuilds the lowercase lookup map and
clears Ren'Py's loadable cache before retrying.

Like patch_runtime_no_nvdrs.py, this leaves eboot.bin and the game untouched.
It recompiles only ``renpy/loader.pyo`` with the already-local Ren'Py 7.4.9
Python 2.7 host runtime, then replaces that member in the generated staging
``python27.zip``.
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
LOADER_SOURCE = RENPY_SDK / "renpy/loader.py"
ZIP_MEMBER = "renpy/loader.pyo"

INSERT_LAZY_BLOCK = '''\
# SUBAHIBI-VITA PATCH: lazy audio archive mounting.
#
# index_archives() eagerly reads every archive index at startup. The audio
# archives hold ~33k entries that are not needed until the first sound
# plays, so prefixes whose name matches LAZY_ARCHIVE_MARKER are deferred
# into lazy_archives_pending and mounted on the first lookup miss instead.

LAZY_ARCHIVE_MARKER = "audio"
lazy_archives_pending = [ ]
lazy_archives_mounted = False


def lazy_name_may_match(name):
    """
    True if a missed lookup could plausibly live inside a deferred audio
    archive. Ren'Py probes for optional files that legitimately do not
    exist (error handling, translations), so mounting on any miss would
    defeat the optimization.
    """

    return LAZY_ARCHIVE_MARKER + "/" in name


def mount_lazy_archives():
    """
    Indexes all pending lazy archives. Called from the load paths when a
    likely-audio lookup misses, so audio files resolve exactly as they
    would if the archive had been indexed at startup.
    """

    global lazy_archives_mounted

    while lazy_archives_pending:
        prefix = lazy_archives_pending.pop(0)

        fn = transfn(prefix + ".rpa")
        f = open(fn, "rb")
        with f:
            index = RPAv3ArchiveHandler.read_index(f)
            archives.append((prefix + ".rpa", index))

            # Mirror index_archives(): keep the lowercase lookup map usable
            # for names that only exist inside lazily mounted archives.
            for j in index:
                fn = unicode(j)
                lower_map[unicodedata.normalize('NFC', fn.lower())] = fn

    lazy_archives_mounted = True
    loadable_cache.clear()


'''

INDEX_ARCHIVES_HEAD = '''\
def index_archives():
    """
    Loads in the indexes for the archive files. Also updates the lower_map.
    """\
'''

SKIP_LAZY_OLD = '''\
    for prefix in renpy.config.archives:
        for ext in archive_extensions:
            fn = None
            f = None
'''

SKIP_LAZY_NEW = '''\
    for prefix in renpy.config.archives:
        if LAZY_ARCHIVE_MARKER in prefix.lower():
            lazy_archives_pending.append(prefix)
            continue

        for ext in archive_extensions:
            fn = None
            f = None
'''

ARCHIVE_MISS_OLD = '''\
        return rv

    return None


file_open_callbacks.append(load_from_archive)
'''

ARCHIVE_MISS_NEW = '''\
        return rv

    if lazy_archives_pending and lazy_name_may_match(name):
        mount_lazy_archives()
        return load_from_archive(name)

    return None


file_open_callbacks.append(load_from_archive)
'''

LOADABLE_MISS_OLD = '''\
    if name in remote_files:
        loadable_cache[name] = True
        return name

    loadable_cache[name] = False
    return False
'''

LOADABLE_MISS_NEW = '''\
    if name in remote_files:
        loadable_cache[name] = True
        return name

    if lazy_archives_pending and lazy_name_may_match(name):
        mount_lazy_archives()
        return loadable_core(name)

    loadable_cache[name] = False
    return False
'''


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
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
    temporary.replace(archive)


def main() -> int:
    args = parse_args()
    staging = args.staging.resolve()

    python2 = renpy_sdk_python()
    for required in (staging / "eboot.bin", staging / "lib/python27.zip", LOADER_SOURCE, python2):
        if not required.is_file():
            raise FileNotFoundError(required)

    output_zip = staging / "lib/python27.zip"
    original_zip_hash = sha256(output_zip)
    original_eboot_hash = sha256(staging / "eboot.bin")

    source_text = LOADER_SOURCE.read_text(encoding="utf-8")
    patched_text = source_text.replace(
        INDEX_ARCHIVES_HEAD, INSERT_LAZY_BLOCK + INDEX_ARCHIVES_HEAD, 1
    )
    for old, new in (
        (SKIP_LAZY_OLD, SKIP_LAZY_NEW),
        (ARCHIVE_MISS_OLD, ARCHIVE_MISS_NEW),
        (LOADABLE_MISS_OLD, LOADABLE_MISS_NEW),
    ):
        if source_text.count(old) != 1:
            raise RuntimeError("expected exactly one match for %r block" % old[:48])
        patched_text = patched_text.replace(old, new, 1)

    with tempfile.TemporaryDirectory(prefix="renpy-vita-lazy-audio-") as temporary_dir:
        temporary_path = Path(temporary_dir)
        patched_source = temporary_path / "loader.py"
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
        compiled = temporary_path / "loader.pyo"
        if not compiled.is_file():
            raise RuntimeError("Python 2.7 did not produce loader.pyo")
        if b"mount_lazy_archives" not in compiled.read_bytes():
            raise RuntimeError("compiled loader.pyo lacks the lazy-mount symbols")
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
        patches = manifest.setdefault("runtime_patches", [])
        patches.append({
            "member": ZIP_MEMBER,
            "purpose": "defer audio archive indexing until first sound lookup",
            "original_python27_sha256": original_zip_hash,
            "patched_python27_sha256": sha256(output_zip),
            "eboot_unchanged": True,
        })
        files = [path for path in staging.rglob("*") if path.is_file()]
        manifest["file_count"] = len(files)
        manifest["total_bytes"] = sum(path.stat().st_size for path in files)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
