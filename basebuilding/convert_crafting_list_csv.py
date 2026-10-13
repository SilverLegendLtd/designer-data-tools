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

from tag_registry import REGISTRY, split_list, _norm
from pipeline_common import export_csv, blank_to_none, load_csv_rows, parse_int, parse_number_or_item

CSV_NAME = "Buildings, Stations, Work - Surviving the Grey Legend - Crafting List.csv"

_RESOURCE_COLUMNS = {
    "Metal Resource": "MetalResource",
    "Wires Resource": "WiresResource",
    "Plastic Resource": "PlasticResource",
    "Fuel resource": "FuelResource",
}


def _unlocked_by(value, where: str) -> list:
    """UnlockedBy: blank = known from the start; else Upgrade / Research / Item names (or Tags) that teach the recipe (D118)."""
    tags = []
    for name in split_list(value):
        found = name if name in REGISTRY.names else next(
            (REGISTRY.lookup.get(kind, {}).get(_norm(name)) for kind in ("Upgrade", "Research", "Item")
             if REGISTRY.lookup.get(kind, {}).get(_norm(name))), None)
        if found:
            tags.append(found)
        else:
            REGISTRY.resolve("Upgrade", name, where)  # records the unresolved name for the build report
    return tags


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
        # Recipe columns (D118, on the start row): the generic Job that lists the recipe at this Station,
        # what it makes, and what teaches it.
        where = f"{CSV_NAME}:{row['CraftName']}"
        job = blank_to_none(row.get("Job"))
        entry["Job"] = job
        entry["JobTag"] = REGISTRY.resolve("Job", REGISTRY.job_name({"BuildingName": entry["BuildingName"], "Work": job}), where + ":Job") if job else None
        entry["Output"] = blank_to_none(row.get("Output"))
        entry["OutputTag"], entry["OutputQuantity"] = REGISTRY.outcome(row.get("Output"), where + ":Output")
        entry["UnlockedBy"] = blank_to_none(row.get("UnlockedBy"))
        entry["UnlockedByTags"] = _unlocked_by(row.get("UnlockedBy"), where + ":UnlockedBy")
        work_rows.append(entry)
    return work_rows


if __name__ == "__main__":
    rows = convert()
    print(f"Found {len(rows)} Crafting List work rows (written by build_data.py)")
