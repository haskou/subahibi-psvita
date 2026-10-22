#!/usr/bin/env python3
"""Patch the staged RenPy-Vita ``lib/python27.zip`` in a single rewrite.

The prebuilt Vita runtime ships ``.pyo`` bytecode only, and several of its
modules differ from the desktop Ren'Py 7.4.9 SDK sources (``core.pyo`` has
Vita renderer, screenshot and preload branches). Recompiling SDK sources
would silently discard those branches, so every patch is applied at the
code-object level and proven against the shipped bytecode first:

* ``renpy/display/core.pyo``: the Vita bytecode is kept; only
  ``Interface.setup_nvdrs`` is replaced by a no-op. The runtime has no
  ``_ctypes``, so the desktop NVIDIA driver probe can only fail.
* ``renpy/loader.pyo``: the SDK source with lazy, thread-safe audio archive
  mounting and a startup directory scan that skips ``cache/`` and ``saves/``.
  The SDK differs from the Vita bytecode only in ``check_autoreload``, so the
  Vita version of that function is transplanted back.
* ``renpy/script.pyo``: the SDK source (identical to the Vita bytecode) with
  per-module bytecode caches, so startup unpickles only the bytecode of the
  scripts loaded at init and each lazy story module loads its own cache.

For each SDK-based member the unpatched SDK source, after the same
transplants, must compile to code identical to the shipped bytecode
(ignoring file names and line tables). The ``.pyo`` header is kept from the
original member, so the output is reproducible. eboot.bin is untouched.
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

LAZY_AUDIO_INSERT = '''\
# SUBAHIBI-VITA PATCH: lazy audio archive mounting.
#
# index_archives() eagerly reads every archive index at startup. The audio
# archives hold ~33k entries that are not needed until the first sound
# plays, so prefixes whose name matches LAZY_ARCHIVE_MARKER are deferred
# into lazy_archives_pending and mounted on the first lookup miss instead.
# The game may also mount them ahead of time from its own thread, while the
# main and audio threads keep looking files up.

LAZY_ARCHIVE_MARKER = "audio"
lazy_archives_pending = [ ]
lazy_archives_lock = threading.Lock()

# Ren'Py pickles the globals of its modules at startup, to restore them on a
# restart. A lock cannot be pickled, so it is excluded from that backup,
# like renpy.audio.audio.lock.
renpy.name_blacklist.add("renpy.loader.lazy_archives_lock")


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
    Indexes all pending lazy archives, so audio files resolve exactly as
    they would if the archive had been indexed at startup.

    Each archive reaches lower_map and archives before it leaves
    lazy_archives_pending. A lookup that saw an empty pending list at its
    start therefore sees every archive. A lookup that saw pending archives
    calls this function on a miss, which waits for a mount in progress.
    """

    with lazy_archives_lock:
        while lazy_archives_pending:
            prefix = lazy_archives_pending[0]

            fn = transfn(prefix + ".rpa")
            f = open(fn, "rb")
            with f:
                index = RPAv3ArchiveHandler.read_index(f)

            # Mirror index_archives(): keep the lowercase lookup map usable
            # for names that only exist inside lazily mounted archives.
            for j in index:
                fn = unicode(j)
                lower_map[unicodedata.normalize('NFC', fn.lower())] = fn

            archives.append((prefix + ".rpa", index))
            lazy_archives_pending.pop(0)

        loadable_cache.clear()


'''

INDEX_ARCHIVES_HEAD = '''\
def index_archives():
    """
    Loads in the indexes for the archive files. Also updates the lower_map.
    """\
'''

# Read before the archive scan, see mount_lazy_archives().
LAZY_PENDING_SNAPSHOT = '''\
    lazy_pending = bool(lazy_archives_pending)

'''

LAZY_AUDIO_REPLACEMENTS = (
    (
        INDEX_ARCHIVES_HEAD,
        LAZY_AUDIO_INSERT + INDEX_ARCHIVES_HEAD,
    ),
    (
        '''\
    for prefix in renpy.config.archives:
        for ext in archive_extensions:
            fn = None
            f = None
''',
        '''\
    for prefix in renpy.config.archives:
        if LAZY_ARCHIVE_MARKER in prefix.lower():
            lazy_archives_pending.append(prefix)
            continue

        for ext in archive_extensions:
            fn = None
            f = None
''',
    ),
    (
        '''\
def load_from_archive(name):
    """
    Returns an open python file object of the given type from an archive file.
    """

''',
        '''\
def load_from_archive(name):
    """
    Returns an open python file object of the given type from an archive file.
    """

''' + LAZY_PENDING_SNAPSHOT,
    ),
    (
        '''\
        return rv

    return None


file_open_callbacks.append(load_from_archive)
''',
        '''\
        return rv

    if lazy_pending and lazy_name_may_match(name):
        mount_lazy_archives()
        return load_from_archive(name)

    return None


file_open_callbacks.append(load_from_archive)
''',
    ),
    (
        '''\
def loadable_core(name):
    """
    Returns True if the name is loadable with load, False if it is not.
    """

''',
        '''\
def loadable_core(name):
    """
    Returns True if the name is loadable with load, False if it is not.
    """

''' + LAZY_PENDING_SNAPSHOT,
    ),
    (
        '''\
    if name in remote_files:
        loadable_cache[name] = True
        return name

    loadable_cache[name] = False
    return False
''',
        '''\
    if name in remote_files:
        loadable_cache[name] = True
        return name

    if lazy_pending and lazy_name_may_match(name):
        mount_lazy_archives()
        return loadable_core(name)

    loadable_cache[name] = False
    return False
''',
    ),
)

SKIP_CACHE_SCAN_REPLACEMENTS = (
    (
        '''\
def walkdir(dir): # @ReservedAssignment
    rv = [ ]

    if not os.path.exists(dir) and not renpy.config.developer:
        return rv

    for i in os.listdir(dir):
        if i[0] == ".":
            continue

        try:
            i = renpy.exports.fsdecode(i)
        except:
            continue

        if os.path.isdir(dir + "/" + i):
            for fn in walkdir(dir + "/" + i):
''',
        '''\
# SUBAHIBI-VITA PATCH: scandirfiles() discards every cache/ and saves/
# entry, but walkdir() still lists them and stats each one. The game ships
# ~125 per-module bytecode caches in cache/, so the startup scan skips those
# directories at the top of each search path.
SCAN_SKIPPED_DIRS = ("cache", "saves")


def walkdir(dir, skip=()): # @ReservedAssignment
    rv = [ ]

    if not os.path.exists(dir) and not renpy.config.developer:
        return rv

    for i in os.listdir(dir):
        if i[0] == ".":
            continue

        try:
            i = renpy.exports.fsdecode(i)
        except:
            continue

        if os.path.isdir(dir + "/" + i):
            if i in skip:
                continue

            for fn in walkdir(dir + "/" + i):
''',
    ),
    (
        '''\
        i = os.path.join(renpy.config.basedir, i)
        for j in walkdir(i):
            add(i, j, files, seen)
''',
        '''\
        i = os.path.join(renpy.config.basedir, i)
        for j in walkdir(i, SCAN_SKIPPED_DIRS):
            add(i, j, files, seen)
''',
    ),
)

MODULE_BYTECODE_REPLACEMENTS = (
    (
        '''\
BYTECODE_FILE = "cache/bytecode.rpyb"
''',
        '''\
BYTECODE_FILE = "cache/bytecode.rpyb"

# SUBAHIBI-VITA PATCH: per-module bytecode caches, written at build time.
MODULE_BYTECODE_FILE = "cache/bytecode-%s.rpyb"
''',
    ),
    (
        '''\
        fn, dir = files[0] # @ReservedAssignment
        initcode = [ ]

        self.load_appropriate_file(".rpymc", ".rpym", dir, fn, initcode)
''',
        '''\
        fn, dir = files[0] # @ReservedAssignment
        initcode = [ ]

        # SUBAHIBI-VITA PATCH: the startup cache excludes the lazily loaded
        # story modules; compile each one against its own cache instead.
        # Ren'Py's own modules (_errorhandling, _shaders, tl/None/common)
        # have no module cache and stay in the startup cache.
        module_bytecode = None

        try:
            with renpy.loader.load(MODULE_BYTECODE_FILE % name) as f:
                version, cache = loads(zlib.decompress(f.read()))
                if version == BYTECODE_VERSION:
                    module_bytecode = cache
        except:
            pass

        if module_bytecode is None:
            self.load_appropriate_file(".rpymc", ".rpym", dir, fn, initcode)
        else:
            # Expressions queued since the last load belong to the startup
            # cache, so compile them before swapping it out.
            self.update_bytecode()

            oldcache = self.bytecode_oldcache
            newcache = self.bytecode_newcache
            self.bytecode_oldcache = module_bytecode
            self.bytecode_newcache = { }

            try:
                self.load_appropriate_file(".rpymc", ".rpym", dir, fn, initcode)
            finally:
                self.bytecode_oldcache = oldcache
                self.bytecode_newcache = newcache
''',
    ),
)

PATCHES = (
    {
        "member": "renpy/display/core.pyo",
        "purpose": "skip the desktop NVDRS probe; keep Vita core bytecode",
        "source": None,
        "replacements": (),
        "keep_original": (),
        "noop": ("Interface.setup_nvdrs",),
        # The desktop SDK core never references renpy.vita.
        "present": (b"vita",),
        "absent": (b"cdll",),
    },
    {
        "member": "renpy/loader.pyo",
        "purpose": "defer audio archive indexing; skip cache/ and saves/ in the startup scan",
        "source": "renpy/loader.py",
        "replacements": LAZY_AUDIO_REPLACEMENTS + SKIP_CACHE_SCAN_REPLACEMENTS,
        "keep_original": ("check_autoreload",),
        "noop": (),
        "present": (b"mount_lazy_archives", b"SCAN_SKIPPED_DIRS"),
        "absent": (),
    },
    {
        "member": "renpy/script.pyo",
        "purpose": "load lazy module bytecode from per-module caches",
        "source": "renpy/script.py",
        "replacements": MODULE_BYTECODE_REPLACEMENTS,
        "keep_original": (),
        "noop": (),
        "present": (b"cache/bytecode-%s.rpyb",),
        "absent": (),
    },
)

# Runs under the SDK's Python 2.7, whose marshal format matches the Vita.
PY2_HELPER = r'''
import json
import marshal
import sys
import types

CO_VARARGS = 0x04
CO_VARKEYWORDS = 0x08


def load_pyo(path):
    with open(path, "rb") as f:
        data = f.read()
    return data[:8], marshal.loads(data[8:])


def compile_source(path, filename):
    with open(path, "rU") as f:
        source = f.read()
    if not source.endswith("\n"):
        source += "\n"
    return compile(source, filename, "exec", 0, True)


def rebuild(code, consts=None, filename=None, firstlineno=None):
    return types.CodeType(
        code.co_argcount, code.co_nlocals, code.co_stacksize, code.co_flags,
        code.co_code,
        code.co_consts if consts is None else consts,
        code.co_names, code.co_varnames,
        code.co_filename if filename is None else filename,
        code.co_name,
        code.co_firstlineno if firstlineno is None else firstlineno,
        code.co_lnotab, code.co_freevars, code.co_cellvars)


def child_index(code, name):
    hits = [
        index for index, const in enumerate(code.co_consts)
        if isinstance(const, types.CodeType) and const.co_name == name
    ]
    if len(hits) != 1:
        sys.exit("expected one code object %r in %r, found %d" % (name, code.co_name, len(hits)))
    return hits[0]


def find(code, path):
    for name in path:
        code = code.co_consts[child_index(code, name)]
    return code


def replace(code, path, new):
    if not path:
        return new
    consts = list(code.co_consts)
    index = child_index(code, path[0])
    consts[index] = replace(consts[index], path[1:], new)
    return rebuild(code, consts=tuple(consts))


def noop_stub(original):
    if original.co_flags & (CO_VARARGS | CO_VARKEYWORDS):
        sys.exit("cannot stub variadic function %r" % original.co_name)
    arguments = ", ".join(original.co_varnames[:original.co_argcount])
    module = compile("def %s(%s):\n    pass\n" % (original.co_name, arguments),
                     original.co_filename, "exec", 0, True)
    stub = find(module, [original.co_name])
    return rebuild(stub, filename=original.co_filename, firstlineno=original.co_firstlineno)


def signature(code):
    return (
        code.co_name, code.co_argcount, code.co_nlocals, code.co_stacksize,
        code.co_flags, code.co_code, code.co_names, code.co_varnames,
        code.co_freevars, code.co_cellvars,
        tuple(
            signature(const) if isinstance(const, types.CodeType) else (type(const), const)
            for const in code.co_consts
        ),
    )


def transplant(code, original, job):
    for qualname in job["keep_original"]:
        path = qualname.split(".")
        code = replace(code, path, find(original, path))
    for qualname in job["noop"]:
        path = qualname.split(".")
        code = replace(code, path, noop_stub(find(original, path)))
    return code


for job in json.load(open(sys.argv[1])):
    header, original = load_pyo(job["original"])
    if job["source"] is None:
        patched = original
    else:
        unpatched = transplant(compile_source(job["source"], original.co_filename), original, job)
        if signature(unpatched) != signature(original):
            sys.exit("%s: SDK source does not match the Vita bytecode" % job["member"])
        patched = compile_source(job["patched"], original.co_filename)
    patched = transplant(patched, original, job)
    if signature(patched) == signature(original):
        sys.exit("%s: patch changed nothing" % job["member"])
    with open(job["output"], "wb") as f:
        f.write(header + marshal.dumps(patched))
'''


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def apply_replacements(text: str, replacements: tuple[tuple[str, str], ...]) -> str:
    for old, new in replacements:
        if text.count(old) != 1:
            raise RuntimeError("expected exactly one match for %r block" % old[:48])
        text = text.replace(old, new, 1)
    return text


def build_members(runtime_zip: Path, temporary: Path) -> dict[str, bytes]:
    jobs = []
    with zipfile.ZipFile(runtime_zip) as archive:
        for index, patch in enumerate(PATCHES):
            original = temporary / ("%d-original.pyo" % index)
            original.write_bytes(archive.read(patch["member"]))
            job = {
                "member": patch["member"],
                "original": str(original),
                "source": None,
                "patched": None,
                "keep_original": list(patch["keep_original"]),
                "noop": list(patch["noop"]),
                "output": str(temporary / ("%d-patched.pyo" % index)),
            }
            if patch["source"] is not None:
                source = RENPY_SDK / patch["source"]
                patched = temporary / ("%d-patched.py" % index)
                patched.write_text(
                    apply_replacements(
                        source.read_text(encoding="utf-8"), patch["replacements"]
                    ),
                    encoding="utf-8",
                )
                job["source"] = str(source)
                job["patched"] = str(patched)
            jobs.append(job)

    helper = temporary / "patch_pyo.py"
    helper.write_text(PY2_HELPER, encoding="utf-8")
    jobs_path = temporary / "jobs.json"
    jobs_path.write_text(json.dumps(jobs), encoding="utf-8")
    environment = os.environ.copy()
    environment["PYTHONHOME"] = str(RENPY_SDK)
    environment["LD_LIBRARY_PATH"] = str(RENPY_SDK / "lib/linux-x86_64")
    subprocess.run(
        [str(renpy_sdk_python()), "-O", str(helper), str(jobs_path)],
        check=True,
        env=environment,
    )

    members = {}
    for patch, job in zip(PATCHES, jobs):
        data = Path(job["output"]).read_bytes()
        for marker in patch["present"]:
            if marker not in data:
                raise RuntimeError("%s lacks %r" % (patch["member"], marker))
        for marker in patch["absent"]:
            if marker in data:
                raise RuntimeError("%s still contains %r" % (patch["member"], marker))
        members[patch["member"]] = data
    return members


def rewrite_zip(archive: Path, members: dict[str, bytes]) -> None:
    temporary = archive.with_suffix(".zip.tmp")
    replaced = set()
    with zipfile.ZipFile(archive, "r") as source, zipfile.ZipFile(temporary, "w") as target:
        for info in source.infolist():
            data = members.get(info.filename)
            if data is None:
                data = source.read(info.filename)
            else:
                replaced.add(info.filename)
            target.writestr(info, data)
    missing = sorted(set(members) - replaced)
    if missing:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("python27.zip does not contain %s" % ", ".join(missing))
    os.replace(temporary, archive)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    args = parser.parse_args()
    staging = args.staging.resolve()
    runtime_zip = staging / "lib/python27.zip"
    eboot = staging / "eboot.bin"
    for required in (eboot, runtime_zip):
        if not required.is_file():
            raise FileNotFoundError(required)

    original_zip_hash = sha256(runtime_zip)
    original_eboot_hash = sha256(eboot)
    with tempfile.TemporaryDirectory(prefix="renpy-vita-runtime-") as temporary_name:
        members = build_members(runtime_zip, Path(temporary_name))
    rewrite_zip(runtime_zip, members)
    if sha256(eboot) != original_eboot_hash:
        raise RuntimeError("eboot.bin changed unexpectedly")
    patched_zip_hash = sha256(runtime_zip)

    print("staging: %s" % staging)
    for patch in PATCHES:
        print("patched %s: %s" % (patch["member"], patch["purpose"]))
    print("source python27.zip SHA-256: %s" % original_zip_hash)
    print("patched python27.zip SHA-256: %s" % patched_zip_hash)
    print("eboot.bin unchanged: yes")

    manifest_path = staging.parent / "VITA_STAGING_MANIFEST.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["runtime_patches"] = {
            "original_python27_sha256": original_zip_hash,
            "patched_python27_sha256": patched_zip_hash,
            "eboot_unchanged": True,
            "members": [
                {
                    "member": patch["member"],
                    "purpose": patch["purpose"],
                    "sha256": hashlib.sha256(members[patch["member"]]).hexdigest(),
                }
                for patch in PATCHES
            ],
        }
        files = [path for path in staging.rglob("*") if path.is_file()]
        manifest["file_count"] = len(files)
        manifest["total_bytes"] = sum(path.stat().st_size for path in files)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
