#!/usr/bin/env python3
"""Convert the exported item lists to design/data/Bronze/basebuilding/Items.json (eating, CopperGame idea 0040;
combat items, D118). Both lists live in the spreadsheet "Buildings, Stations, Work - Surviving the Grey
Legend" (they moved there from the spreadsheet "Items, Food - List" on 2026-10-07):

  Items Food    "... - Items Food.csv"    Name, Category, Nutrition, Source, NeedsResearch, Notes
  Items Combat  "... - Items Combat.csv"  Name, Category, Source, NeedsResearch, Notes  (no Nutrition)

Every Name must have an Item Tag (Inventory.Item.*) and every Category an ItemCategory Tag
(Inventory.Category.*) in sources/BaseBuildingTags.json. Source is a comma list (Farmed, Looted, Starting,
Crafted), kept as text until the game reads it. A name's repeated spaces are collapsed ("High Damage
Ammunition"), the Tag lookup ignores them anyway. Nutrition is null for an item with no such column.

Until the new Items Food tab is exported, the old export (LEGACY_FOOD_CSV) is read if it is still there; with
neither, the build says so and writes the other list only, so the rest of the import still runs.
"""

from tag_registry import REGISTRY
from pipeline_common import DATA_DIR, export_csv, blank_to_none, load_csv_rows, parse_int_or_none, write_json

SHEET = "Buildings, Stations, Work - Surviving the Grey Legend"
FOOD_CSV = f"{SHEET} - Items Food.csv"
COMBAT_CSV = f"{SHEET} - Items Combat.csv"
LEGACY_FOOD_CSV = "Items, Food - List - Food Items.csv"
# Kept for the callers that name the first list.
CSV_NAME = FOOD_CSV
DEST = DATA_DIR / "BaseBuilding" / "Items.json"


def _read(csv_name: str) -> list[dict]:
    path = export_csv(csv_name)
    items = []
    for row in load_csv_rows(path):
        name = " ".join((row.get("Name") or "").split())
        if not name:
            continue
        where = f"{csv_name}:{name}"
        category = (row.get("Category") or "").strip()
        items.append({
            "Tag": REGISTRY.resolve("Item", name, where + ":Name"),
            "Name": name,
            "Category": category,
            "CategoryTag": REGISTRY.resolve("ItemCategory", category, where + ":Category"),
            "Nutrition": parse_int_or_none(row.get("Nutrition")),
            "Sources": [s.strip() for s in (row.get("Source") or "").split(",") if s.strip()],
            "NeedsResearch": (row.get("NeedsResearch") or "").strip().lower() in ("yes", "y", "true"),
            "Notes": blank_to_none(row.get("Notes")),
        })
    return items


def convert() -> int:
    items = []
    food = FOOD_CSV
    if not export_csv(food).exists() and export_csv(LEGACY_FOOD_CSV).exists():
        print(f"  ({FOOD_CSV} not exported yet: reading {LEGACY_FOOD_CSV})")
        food = LEGACY_FOOD_CSV
    for csv_name in (food, COMBAT_CSV):
        if export_csv(csv_name).exists():
            items.extend(_read(csv_name))
        else:
            print(f"  (no {csv_name} exported yet: its items are missing from Items.json)")
    write_json(DEST, items)
    return len(items)
