#!/usr/bin/env python3
"""Convert Starting_Resources.csv into data/basebuilding/StartingResources.json:
the Base Inventory's New Game stock, one row per resource (Metal, Wires,
Plastic, Fuel, Food). See Base-Building-Design-Document.md sec 2.2 gap #1
and D64 for why the amounts are what they are. The Notes column is for
designers only and is not exported.
"""

from tag_registry import REGISTRY
from pipeline_common import DATA_DIR, source_file, load_csv_rows, parse_int, write_json

CSV_NAME = "Starting_Resources.csv"
JSON_DEST = DATA_DIR / "basebuilding" / "StartingResources.json"


def convert() -> int:
    rows = []
    for row in load_csv_rows(source_file(CSV_NAME)):
        resource = (row.get("Resource") or "").strip()
        if not resource:
            continue
        entry = {"Resource": resource, "Amount": parse_int(row.get("Amount"))}
        REGISTRY.tag_resource_row(entry, CSV_NAME)
        rows.append(entry)

    write_json(JSON_DEST, rows)
    return len(rows)


if __name__ == "__main__":
    print(f"Converted {convert()} starting resources -> {JSON_DEST}")
