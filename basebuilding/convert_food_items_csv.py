#!/usr/bin/env python3
"""Convert the exported food item list ("Items, Food - List - Food Items.csv") to
design/data/basebuilding/Items.json (eating, CopperGame idea 0040).

Columns: Name, Category, Nutrition, Source, NeedsResearch, Notes. Every Name must have an
Item Tag (Inventory.Item.*) and every Category an ItemCategory Tag (Inventory.Category.*) in
sources/BaseBuildingTags.json. Source is a comma list (Farmed, Looted, Starting), kept as text
until the game reads it.

Until the sheet is exported, the CSV is missing: the build says so and writes an empty table,
so the rest of the import still runs.
"""

from tag_registry import REGISTRY
from pipeline_common import DATA_DIR, export_csv, blank_to_none, load_csv_rows, parse_int, write_json

CSV_NAME = "Items, Food - List - Food Items.csv"
DEST = DATA_DIR / "basebuilding" / "Items.json"


def convert() -> int:
    path = export_csv(CSV_NAME)
    items = []
    if not path.exists():
        print(f"  (no {CSV_NAME} exported yet: Items.json is empty)")
    else:
        for row in load_csv_rows(path):
            name = (row.get("Name") or "").strip()
            if not name:
                continue
            where = f"{CSV_NAME}:{name}"
            category = (row.get("Category") or "").strip()
            items.append({
                "Tag": REGISTRY.resolve("Item", name, where + ":Name"),
                "Name": name,
                "Category": category,
                "CategoryTag": REGISTRY.resolve("ItemCategory", category, where + ":Category"),
                "Nutrition": parse_int(row.get("Nutrition")),
                "Sources": [s.strip() for s in (row.get("Source") or "").split(",") if s.strip()],
                "NeedsResearch": (row.get("NeedsResearch") or "").strip().lower() in ("yes", "y", "true"),
                "Notes": blank_to_none(row.get("Notes")),
            })
    write_json(DEST, items)
    return len(items)
