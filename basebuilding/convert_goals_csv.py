#!/usr/bin/env python3
"""Convert sources/Goals.csv to design/data/basebuilding/Goals.json (CopperGame idea 0045, FI-07):
the mini-wins and milestones. A hand-maintained input until the designers make a Goals sheet.

One row per goal: GoalName, Kind (MiniWin / Milestone), Requirement, OfferWhen, DreamText,
DoneText, Reward, Notes (designers only, not exported). Every GoalName needs a Goal Tag
(BB.Goal.<Name>) in sources/BaseBuildingTags.json.

Requirement and OfferWhen use a small grammar (an unknown one fails the build):
  Branch <Physical Skill>   every single-skill research node of that skill is unlocked
  AllStations               every Work Station in the Buildings sheet stands at least once
  Nights >= N               N nights survived
  NoMissedMeals Days N      nobody went without a meal for N days in a row
  AllStats >= <band>        every base stat is in that band or higher
  Expansions >= N           N base expansions made
Each becomes {"Raw", "Type", and SkillTag / Amount / BandTag as the type needs}.
A blank OfferWhen is null: a MiniWin is offered in a dream (CopperGame's rule, owner 2026-10-06).
"""

import re

from tag_registry import REGISTRY
from pipeline_common import DATA_DIR, source_file, blank_to_none, load_csv_rows, write_json

CSV_NAME = "Goals.csv"
DEST = DATA_DIR / "basebuilding" / "Goals.json"
_AT_LEAST = re.compile(r"^(Nights|Expansions)\s*>=\s*(\d+)$")
_MEALS = re.compile(r"^NoMissedMeals\s+Days\s+(\d+)$")
_ALL_STATS = re.compile(r"^AllStats\s*>=\s*(\w+)$")
_BRANCH = re.compile(r"^Branch\s+(.+)$")


def condition(text, where: str):
    text = (text or "").strip()
    if not text:
        return None
    if text == "AllStations":
        return {"Raw": text, "Type": "AllStations"}
    match = _AT_LEAST.match(text)
    if match:
        return {"Raw": text, "Type": match.group(1), "Amount": int(match.group(2))}
    match = _MEALS.match(text)
    if match:
        return {"Raw": text, "Type": "NoMissedMealsDays", "Amount": int(match.group(1))}
    match = _ALL_STATS.match(text)
    if match:
        return {"Raw": text, "Type": "AllStatsBand", "BandTag": REGISTRY.resolve("Band", match.group(1), where)}
    match = _BRANCH.match(text)
    if match:
        return {"Raw": text, "Type": "Branch", "SkillTag": REGISTRY.resolve("Stat", match.group(1), where)}
    REGISTRY.errors.append(f'{where}: "{text}" is not a goal condition (see convert_goals_csv.py)')
    return {"Raw": text}


def convert() -> int:
    path = source_file(CSV_NAME)
    goals = []
    for row in load_csv_rows(path) if path.exists() else []:
        name = (row.get("GoalName") or "").strip()
        if not name:
            continue
        where = f"{CSV_NAME}:{name}"
        kind = (row.get("Kind") or "").strip()
        goals.append({
            "Tag": REGISTRY.resolve("Goal", name, where + ":GoalName"),
            "GoalName": name,
            "Kind": kind,
            "KindTag": REGISTRY.resolve("GoalKind", kind, where + ":Kind"),
            "Requirement": condition(row.get("Requirement"), where + ":Requirement"),
            "OfferWhen": condition(row.get("OfferWhen"), where + ":OfferWhen"),
            "DreamText": blank_to_none(row.get("DreamText")),
            "DoneText": blank_to_none(row.get("DoneText")),
            "Reward": blank_to_none(row.get("Reward")),
        })
    write_json(DEST, goals)
    return len(goals)


if __name__ == "__main__":
    print(f"Converted {convert()} goals -> {DEST}")
