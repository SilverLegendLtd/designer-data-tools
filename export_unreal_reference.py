#!/usr/bin/env python3
"""Read-only export of the Unreal project's text files (C++ source, config, data tables, docs)
from Perforce into game-design/reference/unreal/<stream>/, without touching the p4 workspace.

    python tools/export_unreal_reference.py            # needs a valid `p4 login`

Uses `p4 print` (bulk, one call per folder and extension), so nothing is synced or checked out.
reference/ is git-ignored: this is company source and must not go into the personal game-design repo.
Findings drawn from it live in UNREAL_REFERENCE.md (tracked).
"""

import io
import marshal
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reference" / "unreal"
# (depot folder, extensions). //grey/dev has the newest Data/; dev_jyri the newest code (Game/ removed).
SPECS = [
    ("//grey/dev_jyri/GreyGame/Source/", ["h", "cpp", "cs"]),
    ("//grey/dev_jyri/GreyGame/Plugins/GameFeatures/", ["h", "cpp", "cs", "uplugin", "ini", "json"]),
    ("//grey/dev_jyri/GreyGame/Config/", ["ini"]),
    ("//grey/dev_jyri/GreyGame/Docs/", ["md"]),
    ("//grey/dev_jyri/GreyGame/Tools/", ["py", "ps1"]),
    ("//grey/dev_jyri/GreyGame/", ["uproject"]),
    ("//grey/dev/GreyGame/Data/", ["json"]),
]


def long_path(path: Path) -> str:
    """Windows paths in deep plugin folders exceed MAX_PATH without the \\\\?\\ prefix."""
    text = str(path.resolve())
    return "\\\\?\\" + text if os.name == "nt" and not text.startswith("\\\\?\\") else text


def export() -> int:
    written = 0
    for folder, exts in SPECS:
        for ext in exts:
            pattern = folder + ("*." if folder.endswith("GreyGame/") else "....") + ext
            result = subprocess.run(["p4", "-G", "print", pattern], capture_output=True)
            stream = io.BytesIO(result.stdout)
            records = []
            while True:
                try:
                    records.append(marshal.load(stream))
                except EOFError:
                    break
            current, chunks, deleted = None, [], False
            for record in records + [{b"depotFile": None}]:
                if b"depotFile" in record:
                    if current and chunks and not deleted:
                        dest = OUT / current.replace("//grey/", "")
                        os.makedirs(long_path(dest.parent), exist_ok=True)
                        with open(long_path(dest), "wb") as f:
                            f.write(b"".join(chunks))
                        written += 1
                    if record[b"depotFile"] is None:
                        break
                    current = record[b"depotFile"].decode()
                    chunks, deleted = [], b"delete" in record.get(b"action", b"")
                elif record.get(b"code") in (b"text", b"binary"):
                    chunks.append(record.get(b"data", b""))
                elif record.get(b"code") == b"error" and b"no such file" not in record.get(b"data", b""):
                    sys.exit("p4 error: " + record.get(b"data", b"").decode(errors="replace").strip()
                             + "\n(run `p4 login` first)")
    return written


if __name__ == "__main__":
    count = export()
    print(f"{count} files -> {OUT}")
