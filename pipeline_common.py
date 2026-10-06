"""Shared paths and JSON/CSV helpers for the design-data pipeline (import_data.py).

Inputs:
  EXPORTS_DIR   CSVs exported from Google Sheets by apps_script/ExportSheets.gs into the
                Drive folder `Design/exports`, mirrored to this machine by Drive for desktop.
                File names are "<Spreadsheet title> - <Tab>.csv". Override with the
                DESIGN_EXPORTS_DIR environment variable (tests point it at a fixture folder).
  SOURCES_DIR   hand-maintained inputs that have no sheet yet (design/data/sources/).
  ATTRIBUTE_JSON  the canonical stat Tag registry (design/data/Attribute.json, designed with
                the Unreal lead).
Output:
  DATA_DIR      design/data/ -- the one source of truth every consumer copies from
                (consumers.json). Never edited by hand.
"""

import csv
import json
import os
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
GAME_DESIGN_ROOT = TOOLS_DIR.parent
DATA_DIR = Path(os.environ.get("DESIGN_DATA_DIR", GAME_DESIGN_ROOT / "design" / "data"))
SOURCES_DIR = DATA_DIR / "sources"
DOCS_OUT_DIR = DATA_DIR / "docs"
EXPORTS_DIR = Path(os.environ.get(
    "DESIGN_EXPORTS_DIR", r"G:\Shared drives\Games\Surviving the Grey Legend\Design\exports"))


def export_csv(name: str) -> Path:
    """A CSV exported from a sheet tab (see export_manifest.json)."""
    return EXPORTS_DIR / name


def source_file(name: str) -> Path:
    """A hand-maintained input with no sheet yet (design/data/sources/)."""
    return SOURCES_DIR / name


REGISTRIES_DIR = SOURCES_DIR / "registries"


def registry_entries() -> list[dict]:
    """Every non-stat Tag: sources/registries/<Kind>.json (Attribute.json shape: Name, Tag, DevComment,
    optional Aliases) replaces that Kind's rows in sources/BaseBuildingTags.json, kind by kind."""
    entries = json.loads((SOURCES_DIR / "BaseBuildingTags.json").read_text(encoding="utf-8"))
    files = sorted(REGISTRIES_DIR.glob("*.json")) if REGISTRIES_DIR.exists() else []
    replaced = {f.stem for f in files}
    entries = [e for e in entries if e["Kind"] not in replaced]
    for f in files:
        entries += [dict(e, Kind=f.stem, Registry=f.name) for e in json.loads(f.read_text(encoding="utf-8"))]
    return entries


def load_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"IMPORT FAILED: missing input {path} -- run the sheet export "
                         f"(script.google.com > project Export for games > exportAll > Run; see DATA_PIPELINE.md) or check DESIGN_EXPORTS_DIR")
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2))


def blank_to_none(value):
    value = (value or "").strip()
    return value if value else None


def parse_int(value, default: int = 0) -> int:
    value = (value or "").strip()
    if not value:
        return default
    return int(float(value))


def parse_int_or_none(value):
    value = (value or "").strip()
    if not value:
        return None
    return int(float(value))


def parse_number_or_item(value):
    """Parses a Difficulty/Workload cell that's either a number or the literal
    'item' placeholder (meaning: this row's real difficulty is authored
    per-item in Items.json, not here)."""
    value = (value or "").strip()
    if not value:
        return None
    if value.lower() == "item":
        return "item"
    as_float = float(value)
    return int(as_float) if as_float.is_integer() else as_float


# ---- Stat Tags (design/data/Attribute.json is the canonical registry) ---------
# Resolving sheet text to Tags lives in basebuilding/tag_registry.py; this only loads the stat rows.

ATTRIBUTE_JSON = DATA_DIR / "Attribute.json"
STAT_TAGS_DEST = DATA_DIR / "basebuilding" / "StatTags.json"


class StatTagRows:
    def __init__(self):
        self.entries = json.loads(ATTRIBUTE_JSON.read_text(encoding="utf-8"))
        self.by_tag = {e["Tag"]: e["Tag"] for e in self.entries}


STAT_TAGS = StatTagRows()


def write_stat_tags() -> int:
    """basebuilding/StatTags.json: Name, Tag, Category, Key, Min/Max for each
    Attribute.json row."""
    rows = []
    for e in STAT_TAGS.entries:
        category, key = e["Tag"].split(".", 1)
        rows.append({"Name": e["Name"], "Tag": e["Tag"], "Category": category, "Key": key,
                     "MinValue": e.get("MinValue"), "MaxValue": e.get("MaxValue")})
    write_json(STAT_TAGS_DEST, rows)
    return len(rows)
