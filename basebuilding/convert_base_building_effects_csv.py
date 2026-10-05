#!/usr/bin/env python3
"""Convert the exported "Gameplay Effects for Dialogue System - Base Building Effects.csv" to
design/data/basebuilding/BaseBuildingEffects.json (CopperGame idea 0041).

The tab follows CopperLegend's gameplay effect columns (Name, Tag, EffectType, the check and
duration-check stats, Effects, Arousal, Valence) plus base building's own: WorkTierModifier,
CannotWork, DurationHours, AppliedBy, Notes. Every Tag must be an Effect Tag
(GameplayEffect.BaseBuilding.*) in sources/BaseBuildingTags.json; every stat name resolves
through Attribute.json. `Effects` is a list of "<stat> <value>" parts (e.g. "Focus -1; Logic -1").

Until the tab is exported the CSV is missing: the build says so and writes an empty table.
"""

import sys

from tag_registry import REGISTRY
from pipeline_common import DATA_DIR, export_csv, blank_to_none, load_csv_rows, parse_int_or_none, write_json

CSV_NAME = "Gameplay Effects for Dialogue System - Base Building Effects.csv"
DEST = DATA_DIR / "basebuilding" / "BaseBuildingEffects.json"
STAT_COLUMNS = ("CheckSkill", "SecondaryCheckSkill", "CheckAttribute",
                "DurationCheckSkill", "DurationCheckSecondarySkill", "DurationCheckAttribute")


def _number(value, where: str):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        sys.exit(f"ERROR: {where}: {value!r} is not a number")


def _stat_deltas(value, where: str) -> list:
    deltas = []
    for part in (value or "").replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        name, _, amount = part.rpartition(" ")
        tag = REGISTRY.resolve("Stat", name, where + ":Effects")
        deltas.append({"Stat": name, "StatTag": tag, "Value": _number(amount, where + ":Effects")})
    return deltas


def convert() -> int:
    path = export_csv(CSV_NAME)
    effects = []
    if not path.exists():
        print(f"  (no {CSV_NAME} exported yet: BaseBuildingEffects.json is empty)")
    else:
        for row in load_csv_rows(path):
            name = (row.get("Name") or "").strip()
            if not name:
                continue
            where = f"{CSV_NAME}:{name}"
            tag = REGISTRY.resolve("Effect", (row.get("Tag") or "").strip() or name, where + ":Tag")
            effect = {
                "Tag": tag,
                "Name": name,
                "EffectType": (row.get("EffectType") or "").strip(),
            }
            for column in STAT_COLUMNS:
                effect[column] = blank_to_none(row.get(column))
                effect[column + "Tag"] = REGISTRY.resolve("Stat", effect[column], f"{where}:{column}")
            effect.update({
                "Effects": _stat_deltas(row.get("Effects"), where),
                "Arousal": _number(row.get("Arousal"), where + ":Arousal"),
                "Valence": _number(row.get("Valence"), where + ":Valence"),
                "WorkTierModifier": parse_int_or_none(row.get("WorkTierModifier")),
                "CannotWork": (row.get("CannotWork") or "").strip().lower() in ("yes", "y", "true"),
                "DurationHours": parse_int_or_none(row.get("DurationHours")),
                "AppliedBy": blank_to_none(row.get("AppliedBy")),
                "Notes": blank_to_none(row.get("Notes")),
            })
            effects.append(effect)
    write_json(DEST, effects)
    return len(effects)
