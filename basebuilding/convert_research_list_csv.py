#!/usr/bin/env python3
"""Convert the Research List CSV into data/basebuilding/ResearchTree.json.

Per Base-Building-Design-Document.md sec 5, this table is "node name,
skill/tier, costs, prerequisites, unlocks" -- not a Work item (sec 4.3:
spending Research Points against the tree is "a player-driven spend action,
not itself a skill-checked work item"). The source CSV nonetheless carries a
vestigial skill-check "finish" companion row for several early nodes
(WorkType=finish, no Tier/BasicCost/RequirementA of its own -- a copy-paste
leftover from the Buildings_Stations_Work.csv template). Those rows are
dropped here rather than merged in, since they don't carry any real
tree-node data; nodes past the first few never got a finish row authored at
all, which is itself evidence the field doesn't belong to this table's shape.
"""

from tag_registry import REGISTRY
from pipeline_common import DATA_DIR, export_csv, blank_to_none, load_csv_rows, parse_int_or_none, write_json

CSV_NAME = "Buildings, Stations, Work - Surviving the Grey Legend - Research List.csv"
JSON_DEST = DATA_DIR / "basebuilding" / "ResearchTree.json"


def convert() -> int:
    nodes = []
    for row in load_csv_rows(export_csv(CSV_NAME)):
        if (row.get("WorkType") or "").strip().lower() == "finish":
            continue  # vestigial companion row, see module docstring
        name = (row.get("Name") or "").strip()
        if not name:
            continue
        node = {
            "Name": name,
            "SkillTags": REGISTRY.resolve_list("Stat", row.get("Skill"), f"{CSV_NAME}:{name}:Skill"),
            "Tier": parse_int_or_none(row.get("Tier")),
            "BasicCost": parse_int_or_none(row.get("BasicCost")),
            "SpecialCost": blank_to_none(row.get("SpecialCost")),
            "RequirementA": blank_to_none(row.get("RequirementA")),
            "RequirementB": blank_to_none(row.get("RequirementB")),
            "Description": blank_to_none(row.get("Description")),
            "BaseBuffs": blank_to_none(row.get("BaseBuffs")),
        }
        REGISTRY.tag_research_row(node, CSV_NAME)
        nodes.append(node)

    write_json(JSON_DEST, nodes)
    return len(nodes)


if __name__ == "__main__":
    print(f"Converted {convert()} Research Tree nodes -> {JSON_DEST}")
