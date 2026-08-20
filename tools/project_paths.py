"""Shared paths supplied by the reproducible Docker build environment."""

from __future__ import annotations

import os
import platform
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = Path(
    os.environ.get("SUBAHIBI_VENDOR_DIR", PROJECT_ROOT / "vendor")
).resolve()
RENPY_SDK = VENDOR_ROOT / "renpy-7.4.9-sdk"
RENPY_VITA_ARCHIVE = (
    VENDOR_ROOT
    / "renpy-vita-dist"
    / "Ren.Py.PSVita.Distribution.Tool.zip"
)
VITASDK_ROOT = Path(os.environ.get("VITASDK", "/usr/local/vitasdk")).resolve()
VITA_MKSFOEX = VITASDK_ROOT / "bin/vita-mksfoex"
VITA_PACK_VPK = VITASDK_ROOT / "bin/vita-pack-vpk"
WEBP_LIBRARY = Path(
    os.environ.get(
        "SUBAHIBI_WEBP_LIBRARY",
        "/usr/lib/x86_64-linux-gnu/libwebp.so",
    )
)


def renpy_sdk_python(sdk: Path = RENPY_SDK) -> Path:
    machine = platform.machine().lower()
    if platform.system() != "Linux" or machine not in {"x86_64", "amd64"}:
        raise ValueError(
            "Ren'Py precompilation must run in the linux/amd64 builder container"
        )
    result = sdk / "lib/linux-x86_64/python"
    if not result.is_file():
        raise FileNotFoundError("Ren'Py SDK Python is missing: %s" % result)
    return result


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)
