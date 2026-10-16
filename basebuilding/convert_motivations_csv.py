#!/usr/bin/env python3
"""Convert the sheet tab Motivation ("Motivations, Personality, Stamina, Strokes") into
basebuilding/Motivations.json (CopperGame D135/D136, SIL-1604, idea 0056).

One row per motivation: Tag (Motivation.*), Name, Group (Need / Social), BaseStat (a base-stat
display name, resolved to BaseStatTag, a Buff Tag, D63/D94-D96; blank for Social motivations),
InSlice (Yes = the game runs it this slice), AccumulatorSize, Step, Baseline, LowLimit,
HighLimit, DistressThreshold. Baseline must sit between the limits, which must be ordered.
The Notes column is for designers only and is not exported.
"""

from tag_registry import REGISTRY
from pipeline_common import DATA_DIR, export_csv, blank_to_none, load_csv_rows, parse_int, write_json

CSV_NAME = "Motivations, Personality, Stamina, Strokes - Motivation.csv"
DEST = DATA_DIR / "BaseBuilding" / "Motivations.json"


def convert() -> int:
    rows = []
    for row in load_csv_rows(export_csv(CSV_NAME)):
        tag = (row.get("Tag") or "").strip()
        if not tag:
            continue
        group = (row.get("Group") or "").strip()
        if group not in ("Need", "Social"):
            raise SystemExit(f"IMPORT FAILED: {tag}: Group must be Need or Social, found \"{group}\"")
        base_stat = blank_to_none(row.get("BaseStat"))
        base_stat_tag = REGISTRY.resolve("Buff", base_stat, CSV_NAME) if base_stat else None
        if group == "Need" and not base_stat_tag:
            raise SystemExit(f"IMPORT FAILED: {tag}: a Need motivation must name a base stat (Buff) in BaseStat")
        in_slice = (row.get("InSlice") or "").strip().lower()
        if in_slice not in ("yes", "no"):
            raise SystemExit(f"IMPORT FAILED: {tag}: InSlice must be Yes or No, found \"{in_slice}\"")
        limits = [parse_int(row.get(k)) for k in ("LowLimit", "Baseline", "HighLimit")]
        if not limits[0] <= limits[1] <= limits[2]:
            raise SystemExit(f"IMPORT FAILED: {tag}: LowLimit {limits[0]} <= Baseline {limits[1]} <= HighLimit {limits[2]} must hold")
        rows.append({"Tag": tag, "Name": (row.get("Name") or "").strip(), "Group": group,
                     "BaseStat": base_stat, "BaseStatTag": base_stat_tag, "InSlice": in_slice == "yes",
                     "AccumulatorSize": parse_int(row.get("AccumulatorSize")),
                     "Step": parse_int(row.get("Step")), "Baseline": limits[1],
                     "LowLimit": limits[0], "HighLimit": limits[2],
                     "DistressThreshold": parse_int(row.get("DistressThreshold"))})
    if not any(r["InSlice"] for r in rows):
        raise SystemExit(f"IMPORT FAILED: {CSV_NAME}: no motivation has InSlice Yes")
    write_json(DEST, rows)
    return len(rows)


if __name__ == "__main__":
    print(f"Converted {convert()} motivations -> {DEST}")
