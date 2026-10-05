#!/usr/bin/env python3
"""Convert the exported "... - Leisure Buildings.csv" (the Leisure building sheet, D52).

    Buildings: rows of Type "Leisure Building" -> returned to
               convert_buildings_stations_work_csv, which merges them into
               data/basebuilding/Buildings.json (a Leisure building fills a whole
               slot of its size, like a generator).
    Activities: rows of Type "Activity" -> data/basebuilding/LeisureActivities.json
               (data only for now: nothing reads them until the psychology
               connection, D62). BuildingName "Base" = not tied to a building.

Rows with a blank Type (the sheet's hollow "Base" row) are skipped.
"""

import sys

from tag_registry import REGISTRY
from pipeline_common import DATA_DIR, export_csv, source_file, blank_to_none, load_csv_rows, parse_int, write_json

CSV_NAME = "Buildings, Stations, Work - Surviving the Grey Legend - Leisure Buildings.csv"
ACTIVITIES_DEST = DATA_DIR / "basebuilding" / "LeisureActivities.json"
MOVEMENT_CSV_NAME = "Leisure Activity Movement.csv"
# The walking patterns the game can play (behaviour/leisure_movement.gd implements each one).
PATTERNS = ("stay", "loiter", "roam", "circuit", "visit", "corner", "shuffle")
DEFAULT_PATTERN = "stay"
BUILDING_TYPE = "Leisure Building"
NO_BUILDING = "Base"

_RESOURCE_COLUMNS = {
    "Metal Resource": ("MetalResource", "Metal"),
    "Wires Resource": ("WiresResource", "Wires"),
    "Plastic Resource": ("PlasticResource", "Plastic"),
    "Fuel resource": ("FuelResource", "Fuel"),
}


def _building_entry(row: dict) -> dict:
    entry = {
        "BuildingName": row["BuildingName"].strip(),
        "Type": BUILDING_TYPE,
        "Description": blank_to_none(row.get("Description")),
        "BaseBuffs": blank_to_none(row.get("BaseBuffs")),
        "PassiveBuffs": None,
        "AreaRequirements": blank_to_none(row.get("Area Requirements")),
        "ItemsNeededToBuild": None,
        "UpgradesTo": None,
        "ResearchRequirement": blank_to_none(row.get("ResearchRequirement")),
        "ElectricityRequirements": parse_int(row.get("Electricity Requirements")),
        "Capacity": parse_int(row.get("Capacity")),
        "Domain": blank_to_none(row.get("Domain")),
    }
    entry["DomainTag"] = REGISTRY.resolve("Stat", entry["Domain"], f'{CSV_NAME}:{entry["BuildingName"]}:Domain')
    parts = []
    for column, (key, label) in _RESOURCE_COLUMNS.items():
        entry[key] = parse_int(row.get(column))
        if entry[key] > 0:
            parts.append(f"{label} {entry[key]}")
    entry["ResourcesNeededToBuild"] = ", ".join(parts) if parts else None
    return entry


def _movement_table() -> dict:
    """(BuildingName, Activity) -> its placeholder walking pattern row; a pattern the game does not know fails the build."""
    table = {}
    for row in load_csv_rows(source_file(MOVEMENT_CSV_NAME)):
        key = ((row.get("BuildingName") or "").strip(), (row.get("Activity") or "").strip())
        pattern = (row.get("Pattern") or "").strip()
        if pattern not in PATTERNS:
            sys.exit(f"ERROR: unknown walking pattern {pattern!r} for {key} in {MOVEMENT_CSV_NAME}; known: {', '.join(PATTERNS)}")
        table[key] = {"Movement": pattern, "StepTicks": parse_int(row.get("StepTicks"), 4), "Reach": parse_int(row.get("Reach"), 1)}
    return table


def convert():
    """Returns the Leisure building entries (not yet tagged); writes LeisureActivities.json."""
    buildings = []
    activities = []
    movement = _movement_table()
    used = set()
    for row in load_csv_rows(export_csv(CSV_NAME)):
        name = (row.get("BuildingName") or "").strip()
        row_type = (row.get("Type") or "").strip()
        if not name or not row_type:
            continue
        where = f"{CSV_NAME}:{name}"
        if row_type == BUILDING_TYPE:
            buildings.append(_building_entry(row))
        elif row_type == "Activity":
            building_tag = None
            if name != NO_BUILDING:
                building_tag = REGISTRY.resolve("Building", name, where + ":BuildingName")
            activity = {
                "BuildingName": name,
                "Activity": row["Activity"].strip(),
                "Temperament": blank_to_none(row.get("Temperament")),
                "CoreNeed": blank_to_none(row.get("CoreNeed")),
                "Description": blank_to_none(row.get("Description")),
                "Participation": blank_to_none(row.get("Participation")),
                "BuildingTag": building_tag,
            }
            key = (name, activity["Activity"])
            walk = movement.get(key)
            if walk is None:
                print(f"  (no walking pattern for {name} / {activity['Activity']} in {MOVEMENT_CSV_NAME}: it stays put)")
                walk = {"Movement": DEFAULT_PATTERN, "StepTicks": 4, "Reach": 1}
            used.add(key)
            activity.update(walk)
            activity["Tag"] = REGISTRY.resolve("Leisure", f'{name} / {activity["Activity"]}', where + ":Activity")
            activities.append(activity)
        else:
            sys.exit(f"ERROR: unrecognized Type {row_type!r} on row {name!r} in {CSV_NAME}")
    for key in sorted(set(movement) - used):
        sys.exit(f"ERROR: {MOVEMENT_CSV_NAME} has a pattern for {key}, which is not an activity of {CSV_NAME}")
    write_json(ACTIVITIES_DEST, activities)
    return buildings, len(activities)
