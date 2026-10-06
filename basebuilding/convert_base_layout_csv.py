#!/usr/bin/env python3
"""Convert the "Base Expansion" tab of Buildings, Stations, Work into
data/basebuilding/BaseLayout.json: what the base is made of -- its building
slots (Small / Medium / Large, D6), the Yard, the Gate, the Dormitory and its
bunks, the Mess and its seats, the leisure and wander points -- and which
Expand Base choice opens a part (`Unlock`: "Bunks 1", "Slot 2" ...; empty =
there from the start). Owner, 2026-10-06: positions are not design data; each
game places the parts itself by Id (CopperGame: its own placement file; Unreal:
level actors tagged with the Id). The Notes column is for designers only.
"""

import re

from tag_registry import REGISTRY
from pipeline_common import DATA_DIR, export_csv, blank_to_none, load_csv_rows, parse_int_or_none, write_json

CSV_NAME = "Buildings, Stations, Work - Surviving the Grey Legend - Base Expansion.csv"
JSON_DEST = DATA_DIR / "basebuilding" / "BaseLayout.json"
_UNLOCK = re.compile(r"^(Bunks|Slot) (\d+)$")


def convert() -> int:
    rows = []
    for row in load_csv_rows(export_csv(CSV_NAME)):
        area_id = (row.get("Id") or "").strip()
        if not area_id:
            continue
        unlock = blank_to_none(row.get("Unlock"))
        if unlock is not None and not _UNLOCK.match(unlock):
            REGISTRY.errors.append(f'{CSV_NAME}:{area_id}:Unlock "{unlock}" is not "Bunks <n>" or "Slot <n>"')
        entry = {
            "Id": area_id,
            "Kind": (row.get("Kind") or "").strip(),
            "Size": blank_to_none(row.get("Size")),
            "Row": blank_to_none(row.get("Row")),
            "Order": parse_int_or_none(row.get("Order")),
            "Capacity": parse_int_or_none(row.get("Capacity")),
            "Unlock": unlock,
        }
        REGISTRY.tag_layout_row(entry, CSV_NAME)
        rows.append(entry)

    write_json(JSON_DEST, rows)
    return len(rows)


if __name__ == "__main__":
    print(f"Converted {convert()} base layout parts -> {JSON_DEST}")
