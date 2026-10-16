#!/usr/bin/env python3
"""Convert the sheet tabs Stamina and Stamina Drain ("Motivations, Personality, Stamina, Strokes")
into basebuilding/Stamina.json and basebuilding/StaminaDrain.json (CopperGame D136-D139, SIL-1604).

Stamina: one row per key (Key, Value). The share keys (TiredBelow, TiredClearsAt, ExhaustedBelow,
ExhaustedClearsAt, SleepWhileExhaustedShare) must be 0..1 and SleepWhileExhaustedShare must stay
below ExhaustedClearsAt (D137: a night that starts Exhausted must not clear Exhausted).
Stamina Drain: one row per Physical Skill (Skill, DrainPerTick > 0) for guard and station work.
The Notes column is for designers only and is not exported.
"""

from pipeline_common import DATA_DIR, export_csv, load_csv_rows, write_json

CSV_NAME = "Motivations, Personality, Stamina, Strokes - Stamina.csv"
CSV_NAME_DRAIN = "Motivations, Personality, Stamina, Strokes - Stamina Drain.csv"
DEST = DATA_DIR / "BaseBuilding" / "Stamina.json"
DEST_DRAIN = DATA_DIR / "BaseBuilding" / "StaminaDrain.json"

_SHARE_KEYS = {"Stamina.TiredBelow", "Stamina.TiredClearsAt", "Stamina.ExhaustedBelow",
               "Stamina.ExhaustedClearsAt", "Stamina.SleepWhileExhaustedShare"}


def convert() -> int:
    rows = []
    for row in load_csv_rows(export_csv(CSV_NAME)):
        key = (row.get("Key") or "").strip()
        if not key or not key.startswith("Stamina."):
            continue
        value = float((row.get("Value") or "").strip())
        if key in _SHARE_KEYS and not 0.0 <= value <= 1.0:
            raise SystemExit(f"IMPORT FAILED: {key} {value} is a share of the max and must be 0..1")
        rows.append({"Key": key, "Value": value})
    if not _SHARE_KEYS <= {r["Key"] for r in rows}:
        raise SystemExit(f"IMPORT FAILED: {CSV_NAME} is missing share keys: {sorted(_SHARE_KEYS - {r['Key'] for r in rows})}")
    if len({r["Key"] for r in rows}) != len(rows):
        raise SystemExit(f"IMPORT FAILED: {CSV_NAME} has a duplicate Key")
    by_key = {r["Key"]: r["Value"] for r in rows}
    if by_key["Stamina.SleepWhileExhaustedShare"] >= by_key["Stamina.ExhaustedClearsAt"]:
        raise SystemExit("IMPORT FAILED: Stamina.SleepWhileExhaustedShare must stay below Stamina.ExhaustedClearsAt (D137)")
    for low, high in (("Stamina.TiredBelow", "Stamina.TiredClearsAt"),
                      ("Stamina.ExhaustedBelow", "Stamina.ExhaustedClearsAt")):
        if by_key[low] >= by_key[high]:
            raise SystemExit(f"IMPORT FAILED: {low} must be below {high}")

    drain_rows = []
    for row in load_csv_rows(export_csv(CSV_NAME_DRAIN)):
        skill = (row.get("Skill") or "").strip()
        if not skill:
            continue
        per_tick = float((row.get("DrainPerTick") or "").strip())
        if per_tick <= 0:
            raise SystemExit(f"IMPORT FAILED: {CSV_NAME_DRAIN}: DrainPerTick for {skill} must be above 0")
        drain_rows.append({"Skill": skill, "DrainPerTick": per_tick})

    write_json(DEST, rows)
    write_json(DEST_DRAIN, drain_rows)
    return len(rows) + len(drain_rows)


if __name__ == "__main__":
    print(f"Converted -> {DEST} + {DEST_DRAIN}")
