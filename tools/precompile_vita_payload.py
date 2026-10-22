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
import zipfile
from pathlib import Path

from project_paths import PROJECT_ROOT, RENPY_SDK, display_path, renpy_sdk_python


DEFAULT_STAGING = PROJECT_ROOT / "build/staging"
DEFAULT_SDK = RENPY_SDK
DEFAULT_REPORT = PROJECT_ROOT / "build/PRECOMPILE_REPORT.json"
DEFAULT_MODULE_REPORT = PROJECT_ROOT / "build/BGI_MODULE_REPORT.json"
CACHE_FILES = ("bytecode.rpyb", "pyanalysis.rpyb", "screens.rpyb")
MODULE_CACHE_PATTERN = "bytecode-%s.rpyb"
COMPILED_SUFFIXES = {".rpyc", ".rpymc"}
SCRIPT_NODE_EPOCH = 1700000000
# Compiled with the rest of renpy/common so that the global statement serials,
# and therefore existing saves, stay identical, then left out of the payload so
# the Vita does not load and initialize them on every launch. Nothing that
# remains references them: the keymap needs only 00console/00director, and
# 00compat touches MusicRoom only for script versions <= 6.15.7 (game: 7.4.4).
PRUNED_COMMON_MODULES = (
    "00achievement.rpyc",
    "00gallery.rpyc",
    "00iap.rpyc",
    "00layeredimage.rpyc",
    "00musicroom.rpyc",
    "00themes.rpyc",
    "00updater.rpyc",
)


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


def write_runtime_screen_cache(sdk: Path, base: Path, staging: Path, temporary: Path) -> None:
    """Regenerate screens.rpyb under the script digest the Vita computes.

    Ren'Py discards screens.rpyb unless it starts with renpy.game.script.digest,
    an MD5 seeded with renpy.version_only and fed the digests of the files it
    loads. The compile pass loads the BGI module preloader and pruned common
    modules, and the Vita runtime has no renpy.vc_version module, so it runs as
    7.4.9.0 instead of the SDK's 7.4.9.<vc_version>. Re-analysing every screen
    and rewriting the cache then costs the first launch on the device.
    """
    with zipfile.ZipFile(staging / "lib/python27.zip") as runtime_library:
        if any(name.startswith("renpy/vc_version.") for name in runtime_library.namelist()):
            raise ValueError("Vita runtime ships renpy.vc_version; its version is no longer 7.4.9.0")

    runtime_base = temporary / "runtime-base"
    runtime_project = temporary / "runtime-project"
    runtime_base.mkdir()
    shutil.copy2(base / "renpy.py", runtime_base / "renpy.py")
    base_renpy = base / "renpy"

    def ignore_runtime(directory: str, names: list[str]) -> set[str]:
        if Path(directory) == base_renpy:
            return {name for name in names if name == "common" or name.startswith("vc_version.")}
        return set()

    shutil.copytree(base_renpy, runtime_base / "renpy", ignore=ignore_runtime)
    shutil.copytree(staging / "renpy/common", runtime_base / "renpy/common")
    os.symlink(str(sdk / "lib"), str(runtime_base / "lib"), target_is_directory=True)
    os.symlink(str(sdk / "module"), str(runtime_base / "module"), target_is_directory=True)
    shutil.copytree(staging / "game", runtime_project / "game")
    screen_cache = runtime_project / "game/cache/screens.rpyb"
    screen_cache.unlink()

    completed = subprocess.run(
        [str(renpy_sdk_python(sdk)), str(runtime_base / "renpy.py"), str(runtime_project), "quit"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    if completed.returncode:
        raise RuntimeError(
            "Ren'Py screen cache pass failed (%d):\n%s" % (completed.returncode, completed.stdout)
        )
    runtime_log = (runtime_project / "log.txt").read_text(encoding="utf-8")
    if "Ren'Py 7.4.9.0u\n" not in runtime_log:
        raise ValueError("screen cache pass did not run as the Vita's Ren'Py 7.4.9.0u")
    if not screen_cache.is_file():
        raise ValueError("screen cache pass did not write %s" % screen_cache)
    shutil.copy2(screen_cache, staging / "game/cache/screens.rpyb")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--sdk", type=Path, default=DEFAULT_SDK)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--module-report", type=Path, default=DEFAULT_MODULE_REPORT)
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
        script_loader = base / "renpy/script.py"
        script_source = script_loader.read_text(encoding="utf-8")
        clock_assignment = "        version = int(time.time())"
        stable_assignment = "        version = int(os.environ.get('SOURCE_DATE_EPOCH', time.time()))"
        if script_source.count(clock_assignment) != 1:
            raise ValueError("cannot locate Ren'Py script-node clock assignment")
        script_loader.write_text(
            script_source.replace(clock_assignment, stable_assignment),
            encoding="utf-8",
        )
        shutil.copytree(staging / "renpy/common", base / "renpy/common")
        os.symlink(str(sdk / "lib"), str(base / "lib"), target_is_directory=True)
        os.symlink(str(sdk / "module"), str(base / "module"), target_is_directory=True)
        shutil.copytree(staging, project)

        module_names = []
        module_preloader = project / "game/000_precompile_bgi_modules.rpy"
        if args.module_report.is_file():
            module_report = json.loads(args.module_report.read_text(encoding="utf-8"))
            module_names = sorted(set(module_report.get("module_by_label", {}).values()))
            if module_names:
                # Keep this a single init block: every compiled node takes a
                # serial from Ren'Py's global counter, and save compatibility
                # depends on the serials of the files compiled after it.
                # Module bytecode is moved out of the startup cache into one
                # cache per module, read by the patched Vita load_module().
                # Expressions queued before each load are compiled first so
                # they stay in the startup cache, as the runtime expects.
                module_preloader.write_text(
                    "init -2000 python:\n"
                    "    def _subahibi_precompile_modules(names):\n"
                    "        import os\n"
                    "        import zlib\n"
                    "        from renpy.compat.pickle import dumps\n"
                    "        script = renpy.game.script\n"
                    "        directory = os.path.join(config.gamedir, 'cache')\n"
                    "        if not os.path.isdir(directory):\n"
                    "            os.makedirs(directory)\n"
                    "        for name in names:\n"
                    "            script.update_bytecode()\n"
                    "            before = set(script.bytecode_newcache)\n"
                    "            renpy.load_module(name)\n"
                    "            entries = { }\n"
                    "            for key in set(script.bytecode_newcache) - before:\n"
                    "                entries[key] = script.bytecode_newcache.pop(key)\n"
                    "            data = (renpy.script.BYTECODE_VERSION, entries)\n"
                    "            path = os.path.join(directory, %r %% name)\n"
                    "            with open(path, 'wb') as f:\n"
                    "                f.write(zlib.compress(dumps(data, 2), 3))\n"
                    "    _subahibi_precompile_modules(%r)\n"
                    % (MODULE_CACHE_PATTERN, module_names),
                    encoding="utf-8",
                )

        command = [
            str(renpy_sdk_python(sdk)),
            str(base / "renpy.py"),
            str(project),
            "compile",
            "--keep-orphan-rpyc",
        ]
        compile_environment = os.environ.copy()
        compile_environment["SOURCE_DATE_EPOCH"] = str(SCRIPT_NODE_EPOCH)
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=compile_environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        if completed.returncode:
            raise RuntimeError(
                "Ren'Py precompilation failed (%d):\n%s"
                % (completed.returncode, completed.stdout)
            )

        if module_names:
            module_preloader.unlink()
            compiled_preloader = module_preloader.with_suffix(".rpyc")
            if compiled_preloader.exists():
                compiled_preloader.unlink()

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

        unknown_pruned = sorted(set(PRUNED_COMMON_MODULES) - set(generated_common))
        if unknown_pruned:
            raise ValueError(
                "prunable common modules were not compiled: %s" % ", ".join(unknown_pruned)
            )

        cache = project / "game/cache"
        expected_cache = list(CACHE_FILES) + [
            MODULE_CACHE_PATTERN % name for name in module_names
        ]
        missing_cache = [name for name in expected_cache if not (cache / name).is_file()]
        if missing_cache:
            raise ValueError("precompile cache is incomplete: %s" % ", ".join(missing_cache))

        for name, source in generated_common.items():
            if name in PRUNED_COMMON_MODULES:
                continue
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

        write_runtime_screen_cache(sdk, base, staging, temporary)

    staged_cache = staging / "game/cache"
    cache_report = {
        path.name: {"size": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(staged_cache.iterdir())
        if path.is_file()
    }
    report = {
        "format": 1,
        "mode": "host-precompiled-renpy-7.4.9",
        "script_node_epoch": SCRIPT_NODE_EPOCH,
        "staging": str(staging.relative_to(PROJECT_ROOT)),
        "sdk": display_path(sdk),
        "source_less_game_rpyc_preserved": len(orphan_game),
        "generated_game_compiled": sorted(generated_game),
        "generated_common_compiled_count": len(generated_common),
        "generated_common_compiled": sorted(generated_common),
        "pruned_common_modules": list(PRUNED_COMMON_MODULES),
        "removed_compiled_sources": sorted(removed_sources),
        "cache": cache_report,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("preserved source-less game RPYC/RPYMC: %d" % len(orphan_game))
    print("generated game RPYC/RPYMC: %d" % len(generated_game))
    print("generated common RPYC/RPYMC: %d" % len(generated_common))
    print("pruned common modules: %d" % len(PRUNED_COMMON_MODULES))
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
