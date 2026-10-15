#!/usr/bin/env python3
"""Convert sources/JobTitles.csv to design/data/Bronze/BaseBuilding/JobTitles.json (CopperGame idea 0054,
SIL-1482/SIL-1581): the job titles each Physical Skill can give ("Legendary Guard"). The owner's list; a
hand-maintained input until the designers add a Title column to the upgrade rows of the Buildings sheet.

Columns: Skill, Option 1, Option 2, Option 3. Option 1 is the base station's title; the later options follow
the station's upgrades. Out: one row per skill, {"Skill": PhysicalSkill Tag, "Titles": [BB.Title.* Tags]}.
Every title needs a Title Tag (BB.Title.<Name>) in sources/BaseBuildingTags.json.
"""

from tag_registry import REGISTRY
from pipeline_common import DATA_DIR, source_file, load_csv_rows, write_json

CSV_NAME = "JobTitles.csv"
DEST = DATA_DIR / "BaseBuilding" / "JobTitles.json"
OPTIONS = ("Option 1", "Option 2", "Option 3")


def convert() -> int:
    rows = []
    for row in load_csv_rows(source_file(CSV_NAME)):
        skill = (row.get("Skill") or "").strip()
        if not skill:
            continue
        tag = REGISTRY.resolve("Stat", skill, f"{CSV_NAME}:{skill}")
        if tag is not None and not tag.startswith("PhysicalSkill."):
            raise SystemExit(f"IMPORT FAILED: {CSV_NAME}: {skill} is not a Physical Skill")
        titles = [REGISTRY.resolve("Title", row.get(o), f"{CSV_NAME}:{skill}:{o}") for o in OPTIONS]
        if None in titles[:1]:
            continue  # unresolved names are reported with the other Tag problems
        rows.append({"Skill": tag, "Titles": [t for t in titles if t]})
    write_json(DEST, rows)
    return len(rows)


if __name__ == "__main__":
    print(f"Converted {convert()} skills -> {DEST}")
