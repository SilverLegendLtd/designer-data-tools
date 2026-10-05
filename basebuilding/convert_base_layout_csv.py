#!/usr/bin/env python3
"""Convert Base_Layout.csv into data/basebuilding/BaseLayout.json: the base's
floor plan -- the 9 building slots (6 Small + 2 Medium + 1 Large, D6) as 2D
rects with an entrance point each, plus the open Yard between them and the
Gate out of the base. See Base-Building-Design-Document.md sec 2.1 and D65.
Coordinates are 2D world pixels from the base's top-left corner. The Notes
column is for designers only and is not exported.
"""

from tag_registry import REGISTRY
from pipeline_common import DATA_DIR, source_file, blank_to_none, load_csv_rows, parse_int, parse_int_or_none, write_json

CSV_NAME = "Base_Layout.csv"
JSON_DEST = DATA_DIR / "basebuilding" / "BaseLayout.json"


def convert() -> int:
    rows = []
    for row in load_csv_rows(source_file(CSV_NAME)):
        area_id = (row.get("Id") or "").strip()
        if not area_id:
            continue
        entry = {
            "Id": area_id,
            "Kind": (row.get("Kind") or "").strip(),
            "Size": blank_to_none(row.get("Size")),
            "X": parse_int(row.get("X")),
            "Y": parse_int(row.get("Y")),
            "Width": parse_int(row.get("Width")),
            "Height": parse_int(row.get("Height")),
            "EntranceX": parse_int_or_none(row.get("EntranceX")),
            "EntranceY": parse_int_or_none(row.get("EntranceY")),
        }
        REGISTRY.tag_layout_row(entry, CSV_NAME)
        rows.append(entry)

    write_json(JSON_DEST, rows)
    return len(rows)


if __name__ == "__main__":
    print(f"Converted {convert()} base layout areas -> {JSON_DEST}")
