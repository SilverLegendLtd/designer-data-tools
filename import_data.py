#!/usr/bin/env python3
"""The design-data pipeline: Google Sheets -> Drive exports -> design/data -> every consumer.

    python tools/import_data.py             # build design/data from the exports, then copy to consumers
    python tools/import_data.py --build     # build design/data only
    python tools/import_data.py --copy      # copy design/data to the enabled consumers only
    python tools/import_data.py --check     # fail (exit 1) if any enabled consumer's copy differs
    python tools/import_data.py --publish-manifest   # put export_manifest.json in the Drive exports folder

Inputs (see pipeline_common.py): sheet CSVs in the Drive exports folder (written by
apps_script/ExportSheets.gs from export_manifest.json), hand-maintained files in
design/data/sources/, and design/data/Attribute.json. The build validates every Tag and
every row schema and stops on the first problem, writing nothing to consumers.
Consumers and their target folders are listed in consumers.json.
"""

import argparse
import filecmp
import json
import shutil
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(TOOLS_DIR / "basebuilding"))

from pipeline_common import DATA_DIR, EXPORTS_DIR, GAME_DESIGN_ROOT, export_csv, write_json  # noqa: E402

CONSUMERS_JSON = TOOLS_DIR / "consumers.json"
EXPORT_MANIFEST = TOOLS_DIR / "export_manifest.json"
BACKGROUND_TABS = {"Background": "Background", "Childhood": "Background_Childhood",
                   "YoungAdult": "Background_YoungAdult", "Adult": "Background_Adult"}


def _fail_if(what: str, problems: list) -> None:
    if problems:
        print(f"IMPORT FAILED: {what}:")
        for line in dict.fromkeys(problems[:60]):
            print("  " + line)
        sys.exit(1)


def build_basebuilding() -> None:
    import convert_base_layout_csv
    import convert_buildings_stations_work_csv
    import convert_crafting_list_csv
    import convert_research_list_csv
    import convert_starting_resources_csv
    import schemas
    from pipeline_common import write_stat_tags
    from tag_registry import REGISTRY

    tagged_tables = ["Buildings", "Upgrades", "Work", "ResearchTree", "StartingResources", "BaseLayout",
                     "LeisureActivities"]
    out = DATA_DIR / "basebuilding"
    _fail_if("the Tag registry is inconsistent", REGISTRY.integrity_errors())
    building_count, upgrade_count, work_rows = convert_buildings_stations_work_csv.convert()
    crafting_work_rows = convert_crafting_list_csv.convert()
    write_json(out / "Work.json", work_rows + crafting_work_rows)
    research_count = convert_research_list_csv.convert()
    starting_count = convert_starting_resources_csv.convert()
    layout_count = convert_base_layout_csv.convert()
    stat_count = write_stat_tags()

    tables = {name: json.loads((out / f"{name}.json").read_text(encoding="utf-8")) for name in tagged_tables}
    REGISTRY.resolve_references(tables)
    _fail_if("Tag problems (every sheet value must have an equivalent in Attribute.json / "
             "sources/BaseBuildingTags.json)", REGISTRY.report())
    _fail_if("rows that break their schema", schemas.validate(tables))
    schemas.write_schemas()
    for name, rows in tables.items():
        write_json(out / f"{name}.json", rows)
    REGISTRY.write_outputs()
    print(f"basebuilding: {building_count} buildings, {upgrade_count} upgrades, "
          f"{len(work_rows) + len(crafting_work_rows)} work rows, {research_count} research, "
          f"{starting_count} starting resources, {layout_count} layout rows, {stat_count} stat Tags")


def build_character() -> None:
    from backgroundCSVtoJSON import convert_csv_to_json

    out = DATA_DIR / "character"
    out.mkdir(parents=True, exist_ok=True)
    for tab, table in BACKGROUND_TABS.items():
        dest = out / f"{table}.json"
        convert_csv_to_json(str(export_csv(f"Background Data - {tab}.csv")), str(dest))
        if not dest.exists():
            sys.exit(f"IMPORT FAILED: Background Data - {tab}.csv did not convert")
        write_json(dest, json.loads(dest.read_text(encoding="utf-8")))  # normalise: UTF-8, LF


def publish_manifest(create: bool = False) -> None:
    """Keep the Drive copy of export_manifest.json (read by the Apps Script) equal to ours."""
    if create:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if EXPORTS_DIR.exists():
        shutil.copyfile(EXPORT_MANIFEST, EXPORTS_DIR / "export_manifest.json")
        print(f"export_manifest.json -> {EXPORTS_DIR}")


def report_export_age() -> None:
    log = EXPORTS_DIR / "export_log.json"
    if log.exists():
        entry = json.loads(log.read_text(encoding="utf-8"))
        print(f"sheet export: {entry.get('exportedAt')} by {entry.get('by')}, {len(entry.get('files', []))} tabs")
        for problem in entry.get("problems", []):
            print(f"  export problem: {problem}")
    else:
        print(f"sheet export: no export_log.json in {EXPORTS_DIR} (CSVs copied by hand?)")


def _copies(enabled_only: bool = True):
    """Yields (consumer, source file, destination file) for every consumers.json entry."""
    consumers = json.loads(CONSUMERS_JSON.read_text(encoding="utf-8"))["consumers"]
    for name, spec in consumers.items():
        if enabled_only and not spec["enabled"]:
            continue
        root = (GAME_DESIGN_ROOT / spec["root"]).resolve()
        for entry in spec["files"]:
            sources = sorted(DATA_DIR.glob(entry["from"]))
            if not sources:
                sys.exit(f"IMPORT FAILED: consumers.json {name}: nothing matches design/data/{entry['from']}")
            for src in sources:
                dest = root / entry["to"]
                yield name, src, (dest / src.name) if entry["to"].endswith("/") else dest


def copy_to_consumers() -> None:
    counts = {}
    for name, src, dest in _copies():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        counts[name] = counts.get(name, 0) + 1
    for name, n in counts.items():
        print(f"copied {n} files -> {name}")


def check_consumers() -> int:
    drift = [f"{name}: {dest} differs from design/data/{src.relative_to(DATA_DIR).as_posix()}"
             for name, src, dest in _copies()
             if not dest.exists() or not filecmp.cmp(src, dest, shallow=False)]
    print("\n".join(drift) if drift else "all consumer copies match design/data")
    return 1 if drift else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--build", action="store_true", help="build design/data only")
    mode.add_argument("--copy", action="store_true", help="copy design/data to the enabled consumers only")
    mode.add_argument("--check", action="store_true", help="exit 1 if a consumer copy differs")
    mode.add_argument("--publish-manifest", action="store_true", help="copy export_manifest.json to Drive")
    args = parser.parse_args()

    if args.check:
        sys.exit(check_consumers())
    if args.publish_manifest:
        publish_manifest(create=True)
        return
    if not args.copy:
        report_export_age()
        build_basebuilding()
        build_character()
        publish_manifest()
    if not args.build:
        copy_to_consumers()


if __name__ == "__main__":
    main()
