#!/usr/bin/env python3
"""Precompile the exact staged Ren'Py payload with the matching 7.4.9 SDK.

This compiles Ren'Py source and builds caches only. It does not rebuild the
Vita executable or any native runtime module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from project_paths import PROJECT_ROOT, RENPY_SDK, display_path, renpy_sdk_python


DEFAULT_STAGING = PROJECT_ROOT / "build/staging"
DEFAULT_SDK = RENPY_SDK
DEFAULT_REPORT = PROJECT_ROOT / "build/PRECOMPILE_REPORT.json"
CACHE_FILES = ("bytecode.rpyb", "pyanalysis.rpyb", "screens.rpyb")
COMPILED_SUFFIXES = {".rpyc", ".rpymc"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compiled_files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and path.suffix in COMPILED_SUFFIXES
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--sdk", type=Path, default=DEFAULT_SDK)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    staging = args.staging.resolve()
    sdk = args.sdk.resolve()
    report_path = args.report.resolve()
    if not (staging / "game").is_dir() or not (staging / "renpy/common").is_dir():
        raise FileNotFoundError("incomplete Vita staging: %s" % staging)
    if not (sdk / "renpy.py").is_file() or not (sdk / "renpy").is_dir():
        raise FileNotFoundError("incomplete Ren'Py SDK: %s" % sdk)

    original_game = compiled_files(staging / "game")
    orphan_game = {
        name: path
        for name, path in original_game.items()
        if not path.with_suffix(path.suffix[:-1]).is_file()
    }
    orphan_hashes = {name: sha256(path) for name, path in orphan_game.items()}

    with tempfile.TemporaryDirectory(prefix="subahibi-precompile-") as temporary_name:
        temporary = Path(temporary_name)
        base = temporary / "base"
        project = temporary / "project"
        base.mkdir()
        shutil.copy2(sdk / "renpy.py", base / "renpy.py")

        sdk_renpy = sdk / "renpy"

        def ignore_common(directory: str, names: list[str]) -> set[str]:
            if Path(directory).resolve() == sdk_renpy.resolve() and "common" in names:
                return {"common"}
            return set()

        shutil.copytree(sdk_renpy, base / "renpy", ignore=ignore_common)
        shutil.copytree(staging / "renpy/common", base / "renpy/common")
        os.symlink(str(sdk / "lib"), str(base / "lib"), target_is_directory=True)
        os.symlink(str(sdk / "module"), str(base / "module"), target_is_directory=True)
        shutil.copytree(staging, project)

        command = [
            str(renpy_sdk_python(sdk)),
            str(base / "renpy.py"),
            str(project),
            "compile",
            "--keep-orphan-rpyc",
        ]
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        if completed.returncode:
            raise RuntimeError(
                "Ren'Py precompilation failed (%d):\n%s"
                % (completed.returncode, completed.stdout)
            )

        compiled_game = compiled_files(project / "game")
        changed_orphans = [
            name
            for name, digest in orphan_hashes.items()
            if name not in compiled_game or sha256(compiled_game[name]) != digest
        ]
        if changed_orphans:
            raise ValueError(
                "precompilation changed source-less game RPYC files: %s"
                % ", ".join(sorted(changed_orphans))
            )

        generated_game = {
            name: path
            for name, path in compiled_game.items()
            if name not in original_game or sha256(path) != sha256(original_game[name])
        }
        generated_common = compiled_files(base / "renpy/common")
        bad_source_digests = []
        for name, compiled in generated_common.items():
            source = compiled.with_suffix(compiled.suffix[:-1])
            if not source.is_file() or compiled.read_bytes()[-16:] != hashlib.md5(
                source.read_bytes()
            ).digest():
                bad_source_digests.append(name)
        if bad_source_digests:
            raise ValueError(
                "compiled common source digest mismatch: %s"
                % ", ".join(sorted(bad_source_digests))
            )

        cache = project / "game/cache"
        missing_cache = [name for name in CACHE_FILES if not (cache / name).is_file()]
        if missing_cache:
            raise ValueError("precompile cache is incomplete: %s" % ", ".join(missing_cache))

        for name, source in generated_common.items():
            destination = staging / "renpy/common" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        for name, source in generated_game.items():
            destination = staging / "game" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        destination_cache = staging / "game/cache"
        if destination_cache.exists():
            raise FileExistsError("staging cache already exists: %s" % destination_cache)
        shutil.copytree(cache, destination_cache)

        removed_sources = []
        for name in generated_common:
            compiled = staging / "renpy/common" / name
            source = compiled.with_suffix(compiled.suffix[:-1])
            if source.is_file():
                removed_sources.append(source.relative_to(staging).as_posix())
                source.unlink()
        for name in generated_game:
            compiled = staging / "game" / name
            source = compiled.with_suffix(compiled.suffix[:-1])
            if source.is_file():
                removed_sources.append(source.relative_to(staging).as_posix())
                source.unlink()

    cache_report = {
        name: {
            "size": (staging / "game/cache" / name).stat().st_size,
            "sha256": sha256(staging / "game/cache" / name),
        }
        for name in CACHE_FILES
    }
    report = {
        "format": 1,
        "mode": "host-precompiled-renpy-7.4.9",
        "staging": str(staging.relative_to(PROJECT_ROOT)),
        "sdk": display_path(sdk),
        "source_less_game_rpyc_preserved": len(orphan_game),
        "generated_game_compiled": sorted(generated_game),
        "generated_common_compiled_count": len(generated_common),
        "generated_common_compiled": sorted(generated_common),
        "removed_compiled_sources": sorted(removed_sources),
        "cache": cache_report,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("preserved source-less game RPYC/RPYMC: %d" % len(orphan_game))
    print("generated game RPYC/RPYMC: %d" % len(generated_game))
    print("generated common RPYC/RPYMC: %d" % len(generated_common))
    print("removed compiled source files: %d" % len(removed_sources))
    print("generated cache files: %d" % len(cache_report))
    print("report: %s" % report_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as error:
        print("error: %s" % error, file=sys.stderr)
        raise SystemExit(2)
