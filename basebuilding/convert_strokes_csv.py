#!/usr/bin/env python3
"""Convert the sheet tab Strokes ("Motivations, Personality, Stamina, Strokes") into
basebuilding/Strokes.json (CopperGame D136-D138, SIL-1610, idea 0056).

One row per stroke source: Source (a BB.StrokeSource.* Tag), Motivation (a Motivation Tag; blank
only when Scope is CurrentMotivation, the stroke lands on the Need of the stat that fell/rose,
D136), Amount, DailyCap (blank = no cap), Scope (Self / Crew / CurrentMotivation), Trait
(optional: an MBTI letter or SJ/SP/NT/NF temperament, D140; blank = all characters).
The Notes column is for designers only and is not exported.
"""

from pipeline_common import DATA_DIR, export_csv, blank_to_none, load_csv_rows, parse_int_or_none, write_json

CSV_NAME = "Motivations, Personality, Stamina, Strokes - Strokes.csv"
DEST = DATA_DIR / "BaseBuilding" / "Strokes.json"
_SCOPES = ("Self", "Crew", "CurrentMotivation")
_TRAITS = ("I", "E", "S", "N", "T", "F", "J", "P", "SJ", "SP", "NT", "NF")


def convert() -> int:
    rows = []
    for row in load_csv_rows(export_csv(CSV_NAME)):
        source = (row.get("Source") or "").strip()
        if not source:
            continue
        motivation = blank_to_none(row.get("Motivation"))
        scope = (row.get("Scope") or "").strip()
        if scope not in _SCOPES:
            raise SystemExit(f"IMPORT FAILED: {source}: Scope must be one of {'/'.join(_SCOPES)}, found \"{scope}\"")
        if not motivation and scope != "CurrentMotivation":
            raise SystemExit(f"IMPORT FAILED: {source}: Motivation is blank but Scope is not CurrentMotivation")
        if motivation and scope == "CurrentMotivation":
            raise SystemExit(f"IMPORT FAILED: {source}: Scope CurrentMotivation takes its motivation from the event, leave Motivation blank")
        trait = blank_to_none(row.get("Trait"))
        if trait is not None and trait not in _TRAITS:
            raise SystemExit(f"IMPORT FAILED: {source}: Trait must be an MBTI letter or SJ/SP/NT/NF, found \"{trait}\"")
        amount = int(float((row.get("Amount") or "").strip()))
        if amount == 0:
            raise SystemExit(f"IMPORT FAILED: {source}: Amount must not be 0")
        daily_cap = parse_int_or_none(row.get("DailyCap"))
        if daily_cap is not None and daily_cap <= 0:
            raise SystemExit(f"IMPORT FAILED: {source}: DailyCap must be above 0")
        rows.append({"Source": source, "Motivation": motivation, "Amount": amount,
                     "DailyCap": daily_cap, "Scope": scope, "Trait": trait})
    if not rows:
        raise SystemExit(f"IMPORT FAILED: {CSV_NAME}: no stroke rows")
    write_json(DEST, rows)
    return len(rows)


if __name__ == "__main__":
    print(f"Converted {convert()} strokes -> {DEST}")
