#!/usr/bin/env python3
"""Convert the sheet tab Level-up ("Mental & Physical Attributes & Skills - Surviving The Grey Legend")
into basebuilding/LevelCurve.json: the Character XP each level costs
(CopperGame D132, idea 0047, SIL-1482). One row per level: Level and XpFromPrevious (the XP the step
from the previous level costs; level 1 costs 0). The last row is the level cap. Optional columns: Title
(a name for the level, e.g. "Proficient") and Perk (any entry other than blank/no/0 = this level gives a
perk, D133). The Notes column is for designers only and is not exported.
"""

from pipeline_common import DATA_DIR, export_csv, blank_to_none, load_csv_rows, parse_int, write_json

CSV_NAME = "Mental & Physical Attributes & Skills - Surviving The Grey Legend - Level-up.csv"
JSON_DEST = DATA_DIR / "BaseBuilding" / "LevelCurve.json"


def convert() -> int:
    rows = []
    for row in load_csv_rows(export_csv(CSV_NAME)):
        if not (row.get("Level") or "").strip():
            continue
        perk = (row.get("Perk") or "").strip().lower()
        rows.append({"Level": parse_int(row.get("Level")), "XpFromPrevious": parse_int(row.get("XpFromPrevious")),
                     "Title": blank_to_none(row.get("Title")), "GivesPerk": perk not in ("", "no", "n", "0", "false")})
    levels = [r["Level"] for r in rows]
    if levels != list(range(1, len(rows) + 1)) or rows[0]["XpFromPrevious"] != 0 \
            or any(r["XpFromPrevious"] <= 0 for r in rows[1:]):
        raise SystemExit(f"IMPORT FAILED: {CSV_NAME} must list levels 1..n in order, level 1 at 0 XP and every later level above 0")
    write_json(JSON_DEST, rows)
    return len(rows)


if __name__ == "__main__":
    print(f"Converted {convert()} levels -> {JSON_DEST}")
