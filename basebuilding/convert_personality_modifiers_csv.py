#!/usr/bin/env python3
"""Convert the sheet tab Personality Modifiers ("Motivations, Personality, Stamina, Strokes")
into basebuilding/PersonalityModifiers.json (CopperGame D140, idea 0057: the GDD's per-letter
personality effects and Stressor table).

One row per modifier: Trait (an MBTI letter I/E/S/N/T/F/J/P or a temperament SJ/SP/NT/NF),
Target (a Motivation Tag or a Stamina key from Stamina.json, which this build wrote already),
Modifier (from the fixed list), Amount. The Notes column is for designers only and is not exported.
"""

import json

from pipeline_common import DATA_DIR, export_csv, load_csv_rows, write_json

CSV_NAME = "Motivations, Personality, Stamina, Strokes - Personality Modifiers.csv"
DEST = DATA_DIR / "BaseBuilding" / "PersonalityModifiers.json"
_TRAITS = ("I", "E", "S", "N", "T", "F", "J", "P", "SJ", "SP", "NT", "NF")
_MODIFIERS = ("Hunger", "Uncaring", "DistressThreshold", "HighLimit", "LowLimit",
              "StrokeSensitivity", "AccumulatorSize", "Multiplier")


def convert() -> int:
    stamina_keys = {r["Key"] for r in json.loads((DATA_DIR / "BaseBuilding" / "Stamina.json").read_text(encoding="utf-8"))}
    motivation_tags = {r["Tag"] for r in json.loads((DATA_DIR / "BaseBuilding" / "Motivations.json").read_text(encoding="utf-8"))}
    rows = []
    for row in load_csv_rows(export_csv(CSV_NAME)):
        trait = (row.get("Trait") or "").strip()
        if not trait:
            continue
        if trait not in _TRAITS:
            raise SystemExit(f"IMPORT FAILED: Trait must be an MBTI letter or SJ/SP/NT/NF, found \"{trait}\"")
        target = (row.get("Target") or "").strip()
        if target not in motivation_tags and target not in stamina_keys:
            raise SystemExit(f"IMPORT FAILED: {trait} {row.get('Modifier')}: Target \"{target}\" is neither a Motivation Tag nor a Stamina key")
        modifier = (row.get("Modifier") or "").strip()
        if modifier not in _MODIFIERS:
            raise SystemExit(f'IMPORT FAILED: {trait} {target}: Modifier must be one of {", ".join(_MODIFIERS)}, found "{modifier}"')
        amount = float((row.get("Amount") or "").strip())
        rows.append({"Trait": trait, "Target": target, "Modifier": modifier, "Amount": amount})
    if not rows:
        raise SystemExit(f"IMPORT FAILED: {CSV_NAME}: no modifier rows")
    write_json(DEST, rows)
    return len(rows)


if __name__ == "__main__":
    print(f"Converted {convert()} personality modifiers -> {DEST}")
