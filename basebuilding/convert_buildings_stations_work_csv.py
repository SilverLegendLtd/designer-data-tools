#!/usr/bin/env python3
"""Convert the exported "Buildings, Stations, Work - ... - New Buildings.csv" into the tables described
in Base-Building-Design-Document.md, sec 5:

    data/basebuilding/Buildings.json  -- rows where Type is Building or Station
    data/basebuilding/Upgrades.json   -- rows where Type is Upgrade
    (Work.json rows, Type Basic/Crafting/ResearchItem/Research, are returned
    to build_data.py, which merges them with convert_crafting_list_csv.py's
    rows before writing data/basebuilding/Work.json.)

The sheet carries known, team-owned hygiene issues (see the design doc's
Decision Ledger "Genuinely open items" line): a leading/trailing 'T1'/'T5'
artifact row, ~55 blank trailing rows, and several rows with a blank Type
that duplicate an Upgrade row already captured elsewhere. This converter
skips all three categories rather than fixing or erroring on them --
cleanup is the designer_data owner's job, not this script's.
"""

import sys

import convert_leisure_buildings_csv
from tag_registry import REGISTRY
from pipeline_common import DATA_DIR, export_csv, blank_to_none, load_csv_rows, parse_int, \
    parse_number_or_item, write_json

CSV_NAME = "Buildings, Stations, Work - Surviving the Grey Legend - New Buildings.csv"
BUILDINGS_DEST = DATA_DIR / "basebuilding" / "Buildings.json"
UPGRADES_DEST = DATA_DIR / "basebuilding" / "Upgrades.json"
WORK_TYPES = ("Basic", "Crafting", "ResearchItem", "Research")

_RESOURCE_COLUMNS = {
    "Metal Resource": "MetalResource",
    "Wires Resource": "WiresResource",
    "Plastic Resource": "PlasticResource",
    "Fuel resource": "FuelResource",
}


def _is_artifact_row(row: dict) -> bool:
    name = (row.get("BuildingName") or "").strip()
    if not name:
        return True  # one of the ~55 blank trailing rows
    if name in ("T1", "T5") and not (row.get("Type") or "").strip():
        return True  # sheet-edge marker row, not real data
    return False


def _building_or_upgrade_entry(row: dict) -> dict:
    entry = {
        "BuildingName": row["BuildingName"].strip(),
        "Type": row["Type"].strip(),
        "Description": blank_to_none(row.get("Description")),
        "BaseBuffs": blank_to_none(row.get("BaseBuffs")),
        "PassiveBuffs": blank_to_none(row.get("PassiveBuffs")),
        "AreaRequirements": blank_to_none(row.get("Area Requirements")),
        "ItemsNeededToBuild": blank_to_none(row.get("Items Needed to Build")),
        "UpgradesTo": blank_to_none(row.get("UpgradesTo")),
        "ResearchRequirement": blank_to_none(row.get("ResearchRequirement")),
        "ResourcesNeededToBuild": blank_to_none(row.get("Resources Needed to Build")),
        "ElectricityRequirements": parse_int(row.get("Electricity Requirements")),
    }
    for csv_col, json_key in _RESOURCE_COLUMNS.items():
        entry[json_key] = parse_int(row.get(csv_col))
    return entry


def _work_entry(row: dict) -> dict:
    return {
        "BuildingName": row["BuildingName"].strip(),
        "Type": row["Type"].strip(),
        "Work": blank_to_none(row.get("Work")),
        "Phase": blank_to_none(row.get("CheckType")),  # "start"/"finish"; None for a bare Research spend-row
        "PrimarySkill": REGISTRY.resolve("Stat", row.get("PrimarySkill"), f"{CSV_NAME}:{row['BuildingName']}:PrimarySkill"),
        "SecondarySkill": REGISTRY.resolve("Stat", row.get("SecondarySkill"), f"{CSV_NAME}:{row['BuildingName']}:SecondarySkill"),
        "Attribute": REGISTRY.resolve("Stat", row.get("Attribute"), f"{CSV_NAME}:{row['BuildingName']}:Attribute"),
        "Difficulty": parse_number_or_item(row.get("Difficulty")),
        "MoodType": blank_to_none(row.get("MoodType")),
        "Workload": parse_number_or_item(row.get("Workload")),
        "Requirements": blank_to_none(row.get("Requirements")),
        "Description": blank_to_none(row.get("Description")),
        "BaseBuffs": blank_to_none(row.get("BaseBuffs")),
        # "<quantity> <item>", e.g. Grow Food's "2 Potatoes" (CopperGame 0040 F18); the column is optional.
        "Outcome": blank_to_none(row.get("Outcome")),
    }


def convert():
    """Returns (building_count, upgrade_count, work_rows). work_rows is handed
    to build_data.py to merge with the Crafting List CSV's rows before
    writing Work.json."""
    buildings = []
    upgrades = []
    work_rows = []
    skipped_hollow = 0

    for row in load_csv_rows(export_csv(CSV_NAME)):
        if _is_artifact_row(row):
            continue
        row_type = (row.get("Type") or "").strip()
        if not row_type:
            skipped_hollow += 1  # a known hollow-upgrade-row duplicate, see module docstring
            continue
        if row_type in ("Building", "Station"):
            buildings.append(_building_or_upgrade_entry(row))
            REGISTRY.tag_building_row(buildings[-1], CSV_NAME)
        elif row_type == "Upgrade":
            upgrades.append(_building_or_upgrade_entry(row))
            REGISTRY.tag_building_row(upgrades[-1], CSV_NAME)
        elif row_type in WORK_TYPES:
            work_rows.append(_work_entry(row))
            REGISTRY.tag_work_row(work_rows[-1], CSV_NAME)
        else:
            sys.exit(f"ERROR: unrecognized Type {row_type!r} on row {row.get('BuildingName')!r} in {CSV_NAME}")

    leisure_buildings, _ = convert_leisure_buildings_csv.convert()
    for leisure in leisure_buildings:
        buildings.append(leisure)
        REGISTRY.tag_building_row(leisure, convert_leisure_buildings_csv.CSV_NAME)
    write_json(BUILDINGS_DEST, buildings)
    write_json(UPGRADES_DEST, upgrades)
    if skipped_hollow:
        print(f"  ({skipped_hollow} blank-Type hollow rows skipped -- team-owned hygiene issue, see Decision Ledger)")
    return len(buildings), len(upgrades), work_rows


if __name__ == "__main__":
    b, u, w = convert()
    print(f"Converted {b} Buildings/Stations -> {BUILDINGS_DEST}")
    print(f"Converted {u} Upgrades -> {UPGRADES_DEST}")
    print(f"Found {len(w)} Work rows (written by build_data.py after merging with the Crafting List)")
