#!/usr/bin/env python3
"""Build and statically validate the complete current Vita payload."""

from __future__ import annotations

import argparse
import subprocess
import sys

from project_paths import PROJECT_ROOT


def run(*arguments: str) -> None:
    command = [sys.executable, *arguments]
    print("+ %s" % " ".join(command), flush=True)
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> int:
    argparse.ArgumentParser(
        description="Build and statically validate the translated Vita VPK."
    ).parse_args()
    run("tools/check_vendor.py")
    run("tools/prepare_game_media.py")
    run("tools/check_game_inputs.py")
    run("tools/build_game.py", "--all-media", "--clean")
    run("tools/optimize_bgi_scripts.py")
    run("tools/build_lazy_bgi_modules.py")
    run("tools/prepare_vita_ui_assets.py")
    run("tools/subset_game_fonts.py")
    run("tools/scale_vita_images.py")
    run("tools/validate_game.py")
    run("tools/prepare_vita_staging.py", "--clean")
    run("tools/precompile_vita_payload.py")
    run("tools/patch_vita_runtime.py")
    run("tools/build_media_archives.py")
    run("tools/build_vpk.py", "--force")
    run("tools/validate_vpk.py")
    run("tools/prepare_release.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
