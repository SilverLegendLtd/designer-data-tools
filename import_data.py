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

import csv  # noqa: E402

import sheet_rules  # noqa: E402
from pipeline_common import ATTRIBUTE_JSON, DATA_DIR, EXPORTS_DIR, GAME_DESIGN_ROOT, export_csv, registry_entries, write_json  # noqa: E402

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


def registries() -> dict:
    """Every Tag list the sheets may reference, by kind (also published for the Apps Script)."""
    kinds = {"Stat": [{"Tag": e["Tag"], "Name": e["Name"]} for e in
                      json.loads(ATTRIBUTE_JSON.read_text(encoding="utf-8"))]}
    for e in registry_entries():
        kinds.setdefault(e["Kind"], []).append({"Tag": e["Tag"], "Name": e["Name"], "Aliases": e.get("Aliases", [])})
    background = export_csv("Background Data - Background.csv")
    if background.exists():
        with background.open(encoding="utf-8-sig", newline="") as f:
            kinds["Background"] = [{"Tag": r["Tag"], "Name": r["Name"]} for r in csv.DictReader(f) if r.get("Tag")]
    return kinds


def strict_tags() -> bool:
    return bool(json.loads(EXPORT_MANIFEST.read_text(encoding="utf-8")).get("strict_tags"))


def validate_exports() -> None:
    """Cell-level check of every exported tab against sheet_rules (same rules as the Apps Script)."""
    reg, strict = sheet_rules.Registries(registries()), strict_tags()
    manifest = json.loads(EXPORT_MANIFEST.read_text(encoding="utf-8"))
    problems = []
    for entry in manifest["exports"]:
        sheet = f'{entry["spreadsheet"]} - {entry["tab"]}'
        path = export_csv(sheet + ".csv")
        if not path.exists():
            continue  # the converter reports the missing file
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        if rows:
            problems += sheet_rules.validate_rows(sheet, rows[0], rows[1:], reg, strict)
    errors = [p for p in problems if p["level"] == "error"]
    names = [p for p in problems if p["level"] == "warning" and p["message"].startswith("display name")]
    if names:
        print(f"sheet validation: {len(names)} display names where a Tag belongs "
              f"(warnings until strict_tags is true in export_manifest.json)")
    for p in problems:
        if p["level"] == "warning" and p not in names:
            print(f'  warning: {p["sheet"]} {p["cell"]}: {p["message"]}')
    _fail_if("sheet validation", [f'{p["sheet"]} {p["cell"]}: {p["message"]}' for p in errors])


def build_basebuilding() -> None:
    import convert_base_layout_csv
    import convert_buildings_stations_work_csv
    import convert_crafting_list_csv
    import convert_food_items_csv
    import convert_goals_csv
    import convert_base_building_effects_csv
    import convert_night_events_csv
    import convert_research_list_csv
    import convert_starting_resources_csv
    import schemas
    from pipeline_common import write_stat_tags
    from tag_registry import REGISTRY

    tagged_tables = ["Buildings", "Upgrades", "Work", "ResearchTree", "StartingResources", "BaseLayout",
                     "LeisureActivities", "Items", "BaseBuildingEffects", "NightEvents", "Goals"]
    out = DATA_DIR / "basebuilding"
    _fail_if("the Tag registry is inconsistent", REGISTRY.integrity_errors())
    building_count, upgrade_count, work_rows = convert_buildings_stations_work_csv.convert()
    crafting_work_rows = convert_crafting_list_csv.convert()
    write_json(out / "Work.json", work_rows + crafting_work_rows)
    research_count = convert_research_list_csv.convert()
    starting_count = convert_starting_resources_csv.convert()
    layout_count = convert_base_layout_csv.convert()
    item_count = convert_food_items_csv.convert()
    effect_count = convert_base_building_effects_csv.convert()
    event_count = convert_night_events_csv.convert()
    goal_count = convert_goals_csv.convert()
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
          f"{starting_count} starting resources, {layout_count} layout rows, {item_count} food items, {effect_count} effects, {event_count} night events, {goal_count} goals, {stat_count} stat Tags")


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
    _fail_if("Background data that does not hold together", check_backgrounds(out))


def check_backgrounds(out) -> list:
    """The Background tabs, after converting: every row has its own Tag (Background.* /
    LifePath.<phase>.*), at least one stat modifier, real stat Tags as modifier keys, and life paths
    unlock only Backgrounds that exist. (2026-10-06: a blank A1 on the Adult tab exported every Tag
    under the key " ", and a Childhood row lost all its stats; neither stopped the import.)"""
    sys.path.insert(0, str(TOOLS_DIR / "basebuilding"))
    from tag_registry import REGISTRY

    problems = []
    tables = {table: json.loads((out / f"{table}.json").read_text(encoding="utf-8")) for table in BACKGROUND_TABS.values()}
    backgrounds = {row.get("Tag") for row in tables.get("Background", [])}
    for table, rows in tables.items():
        sheet = "Background Data - " + next(tab for tab, t in BACKGROUND_TABS.items() if t == table)
        phase = table.split("_", 1)[1] if "_" in table else None
        prefix = f"LifePath.{phase}." if phase else "Background."
        seen = set()
        for index, row in enumerate(rows, start=2):
            name = row.get("Name") or f"row {index}"
            tag = row.get("Tag")
            if not tag:
                problems.append(f'{sheet}: {name} has no Tag (is cell A1 exactly "Tag"? the columns are {list(row)[:3]})')
                continue
            if not str(tag).startswith(prefix):
                problems.append(f"{sheet}: {name}'s Tag {tag} does not start with {prefix}")
            if tag in seen:
                problems.append(f"{sheet}: the Tag {tag} is used twice")
            seen.add(tag)
            modifiers = {}
            for key, value in row.items():
                if key.endswith("Modifiers") and isinstance(value, dict):
                    modifiers.update(value)
            if not modifiers:
                problems.append(f"{sheet}: {name} has no stat modifiers at all (lost in the sheet?)")
            for stat in modifiers:
                if REGISTRY._kind_of(stat) != "Stat":
                    problems.append(f"{sheet}: {name}: {stat} is not a stat Tag in Attribute.json")
            if phase:
                for unlocked in row.get("UnlockedBackgrounds", []):
                    if unlocked not in backgrounds:
                        problems.append(f"{sheet}: {name} unlocks {unlocked}, which is not a Background")
    return problems


def publish_manifest(create: bool = False) -> None:
    """Keep the Drive copy of export_manifest.json (read by the Apps Script) equal to ours."""
    if create:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if EXPORTS_DIR.exists():
        shutil.copyfile(EXPORT_MANIFEST, EXPORTS_DIR / "export_manifest.json")
        rules = {"strict": strict_tags(), "kinds": registries(), "sheets": sheet_rules.SHEETS}
        write_json(EXPORTS_DIR / "validation_rules.json", rules)
        print(f"export_manifest.json + validation_rules.json -> {EXPORTS_DIR}")


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
        validate_exports()
        build_basebuilding()
        build_character()
    if not args.build:
        if not args.copy:
            publish_manifest()
        copy_to_consumers()


if __name__ == "__main__":
    main()
