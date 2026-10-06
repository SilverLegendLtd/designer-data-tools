#!/usr/bin/env python3
"""Convert the Crafting List CSV into Work.json rows (Type "Crafting"), the
same start/finish shape as the Basic/Crafting/ResearchItem rows in
Buildings_Stations_Work.csv -- see convert_buildings_stations_work_csv.py and
Base-Building-Design-Document.md sec 5. Names here are distinct CraftNames
from that sheet's own Crafting rows (e.g. "High Damage Ammunition" here vs.
"Craft Ammunition" there, both under Expert Guard Station) -- these are
additional Work.json entries, not row-level merges with matching keys.
build_data.py appends this converter's rows to the other converter's before
writing data/basebuilding/Work.json.
"""

from tag_registry import REGISTRY
from pipeline_common import export_csv, blank_to_none, load_csv_rows, parse_int, parse_number_or_item

CSV_NAME = "Buildings, Stations, Work - Surviving the Grey Legend - Crafting List.csv"

_RESOURCE_COLUMNS = {
    "Metal Resource": "MetalResource",
    "Wires Resource": "WiresResource",
    "Plastic Resource": "PlasticResource",
    "Fuel resource": "FuelResource",
}


def convert() -> list[dict]:
    work_rows = []
    for row in load_csv_rows(export_csv(CSV_NAME)):
        if not (row.get("Station") or "").strip():
            continue
        entry = {
            "BuildingName": row["Station"].strip(),
            "Type": "Crafting",
            "Work": blank_to_none(row.get("CraftName")),
            "Phase": blank_to_none(row.get("WorkType")),
            "PrimarySkill": REGISTRY.resolve("Stat", row.get("PrimarySkill"), f"{CSV_NAME}:{row['CraftName']}:PrimarySkill"),
            "SecondarySkill": REGISTRY.resolve("Stat", row.get("SecondarySkill"), f"{CSV_NAME}:{row['CraftName']}:SecondarySkill"),
            "Attribute": REGISTRY.resolve("Stat", row.get("Attribute"), f"{CSV_NAME}:{row['CraftName']}:Attribute"),
            "Difficulty": parse_number_or_item(row.get("Difficulty")),
            "MoodType": blank_to_none(row.get("MoodType")),
            "Workload": parse_number_or_item(row.get("Workload")),
            "ResourcesNeededToBuild": blank_to_none(row.get("Resources Needed to Build")),
            "Outcome": blank_to_none(row.get("Outcome")),
            "Description": blank_to_none(row.get("Description")),
            "BaseBuffs": blank_to_none(row.get("BaseBuffs")),
        }
        for csv_col, json_key in _RESOURCE_COLUMNS.items():
            entry[json_key] = parse_int(row.get(csv_col))
        if entry["ResourcesNeededToBuild"] is None:
            # Only the number columns filled (e.g. Expand Base): the cost text is built from them.
            parts = [f"{csv_col.split()[0]} {entry[key]}" for csv_col, key in _RESOURCE_COLUMNS.items() if entry[key] > 0]
            entry["ResourcesNeededToBuild"] = ", ".join(parts) if parts else None
        REGISTRY.tag_work_row(entry, CSV_NAME)
        work_rows.append(entry)
    return work_rows


if __name__ == "__main__":
    rows = convert()
    print(f"Found {len(rows)} Crafting List work rows (written by build_data.py)")
