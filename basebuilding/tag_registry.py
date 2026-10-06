"""The Tag registry: every Tag in the base-building data and its human-readable
names, and the one place the converters turn sheet text into Tags.

Two source files, same shape (`Name`, `Tag`, `DevComment`):
  design/data/Attribute.json             stat Tags (Unreal lead's registry; Kind "Stat")
  design/data/sources/BaseBuildingTags.json  everything else, each with a `Kind`
                                         and optional `Aliases` (other spellings the sheets use)

A sheet value resolves by `Name` or `Aliases`, ignoring case, spaces and
punctuation ("Well-Being" = "well being"). A value with no match fails the
build, listed once per name with where it was seen: add it to
BaseBuildingTags.json (or fix the sheet). Converters call tag_*_row() per row;
cross-references between tables are resolved afterwards by
resolve_references(). Also writes the generated registry
(design/data/basebuilding/TagRegistry.json) and design/data/docs/basebuilding/*.md.

    python tools/basebuilding/tag_registry.py     # registry integrity check only
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # tools/: pipeline_common

from pipeline_common import DATA_DIR, DOCS_OUT_DIR, STAT_TAGS, registry_entries, source_file, write_json

BB_TAGS_JSON = source_file("BaseBuildingTags.json")
REGISTRY_DEST = DATA_DIR / "basebuilding" / "TagRegistry.json"
REGISTRY_DOC = DOCS_OUT_DIR / "basebuilding" / "tag-registry.md"
UNREAL_DOC = DOCS_OUT_DIR / "basebuilding" / "tags-for-unreal-lead.md"

# Kind -> required Tag prefix. "Stat" Tags come from Attribute.json (any category).
KIND_PREFIX = {
    "Building": "BB.Building.", "Station": "BB.Station.", "Upgrade": "BB.Upgrade.", "Job": "BB.Job.",
    "Research": "BB.Research.", "Resource": "Inventory.Resource.", "Item": "Inventory.Item.",
    "Buff": "BB.Buff.", "Passive": "BB.Passive.", "Mood": "BB.Mood.", "Area": "BB.Area.",
    "Requirement": "BB.Requirement.", "Phase": "BB.Phase.", "WorkType": "BB.WorkType.",
    "LayoutKind": "BB.Layout.Kind.", "LayoutSize": "BB.Building.Size.",
    "ResearchPool": "BB.ResearchPool.", "Activity": "BB.Activity.", "ActivityPhase": "BB.ActivityPhase.",
    "Leisure": "BB.Leisure.", "Setting": "BB.Setting.", "SettingsTab": "BB.SettingsTab.", "Drain": "BB.Drain.", "Band": "BB.Band.", "ItemCategory": "Inventory.Category.", "Effect": "GameplayEffect.BaseBuilding.", "Meal": "BB.Meal.", "Event": "BB.Event.",
    "EventBeat": "BB.EventBeat.", "EventSubject": "BB.EventSubject.", "Severity": "BB.Severity.",
}
_TAG = re.compile(r"^[A-Za-z][A-Za-z0-9]*(\.[A-Za-z0-9]+)+$")
_QUANTITY = re.compile(r"^(.*?)\s+(\d+)$")
_OUTCOME = re.compile(r"^(\d+)\s+(.+)$")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def leaf(text: str) -> str:
    """'Human-Suitable Nanobots' -> 'HumanSuitableNanobots' (for adding new registry rows)."""
    return "".join(w[:1].upper() + w[1:] for w in re.findall(r"[A-Za-z0-9]+", text))


def split_list(value) -> list:
    return [p.strip() for p in (value or "").split(",") if p.strip()]


class TagRegistry:
    def __init__(self):
        self.entries = [dict(e, Kind="Stat") for e in STAT_TAGS.entries]
        self.entries += registry_entries()
        self.lookup = {}  # kind -> normalized name -> Tag
        self.names = {}   # Tag -> display name
        for e in self.entries:
            table = self.lookup.setdefault(e["Kind"], {})
            for name in [e["Name"]] + e.get("Aliases", []):
                table.setdefault(_norm(name), e["Tag"])
            self.names[e["Tag"]] = e["Name"]
        self.unresolved = {}  # (kind, value) -> set of places
        self.errors = []      # row-level problems (quantities, references)

    # ---- integrity -------------------------------------------------------
    def integrity_errors(self) -> list:
        errors, tags, per_kind = [], {}, {}
        for e in self.entries:
            tag, kind = e["Tag"], e["Kind"]
            if kind != "Stat" and kind not in KIND_PREFIX:
                errors.append(f'{tag}: unknown Kind "{kind}"')
            elif kind != "Stat" and "Registry" not in e and not tag.startswith(KIND_PREFIX[kind]):  # owner files set their own namespace
                errors.append(f"{tag}: a {kind} Tag must start with {KIND_PREFIX[kind]}")
            if not _TAG.match(tag):
                errors.append(f"{tag}: not a dotted Tag")
            if tag in tags:
                errors.append(f"{tag}: listed twice ({tags[tag]} and {e['Name']})")
            tags[tag] = e["Name"]
            for name in [e["Name"]] + e.get("Aliases", []):
                key = (kind, _norm(name))
                if key in per_kind and per_kind[key] != tag:
                    errors.append(f'{kind} name "{name}" maps to both {per_kind[key]} and {tag}')
                per_kind[key] = tag
        return errors

    # ---- resolving -------------------------------------------------------
    def resolve(self, kind: str, value, where: str):
        """One sheet value -> Tag. Blank (and "None" for stats) -> None. A value
        that matches nothing is recorded and resolves to None."""
        value = (value or "").strip()
        if not value or (kind == "Stat" and value.lower() == "none"):
            return None
        tag = self.lookup.get(kind, {}).get(_norm(value))
        if tag is None and value in self.names and self._kind_of(value) == kind:
            tag = value  # the sheet already holds the Tag
        if tag is None:
            self.unresolved.setdefault((kind, value), set()).add(where)
        return tag

    def _kind_of(self, tag: str):
        return next((e["Kind"] for e in self.entries if e["Tag"] == tag), None)

    def resolve_list(self, kind: str, value, where: str) -> list:
        return [t for t in (self.resolve(kind, p, where) for p in split_list(value)) if t]

    def quantities(self, kind: str, value, where: str) -> dict:
        """'Metal 15, Wires 10' -> {Tag: 15, Tag: 10}; 'Firearms, Medical 15' -> every
        listed name gets 15 (design doc 4.3). Names with no quantity are an error."""
        out, pending = {}, []
        for part in split_list(value):
            match = _QUANTITY.match(part)
            if not match:
                pending.append(part)
                continue
            for name in pending + [match.group(1)]:
                tag = self.resolve(kind, name, where)
                if tag:
                    out[tag] = int(match.group(2))
            pending = []
        if pending:
            self.errors.append(f'{where}: "{value}" has names without a quantity: {", ".join(pending)}')
        return out

    def outcome(self, value, where: str):
        """'20 High damage Ammunition' -> (Tag, 20)."""
        match = _OUTCOME.match((value or "").strip())
        if not match:
            if value:
                self.errors.append(f'{where}: Outcome "{value}" is not "<quantity> <item>"')
            return None, None
        return self.resolve("Item", match.group(2), where), int(match.group(1))

    def name_for(self, tag) -> str:
        return self.names.get(tag, str(tag))

    def report(self) -> list:
        lines = [f'unresolved {kind} "{value}" (in {", ".join(sorted(where))}): '
                 f"add it to BaseBuildingTags.json or fix the sheet"
                 for (kind, value), where in sorted(self.unresolved.items())]
        return lines + self.errors

    # ---- row tagging (called by the converters) --------------------------
    def tag_building_row(self, row: dict, source: str) -> None:
        kind = {"Station": "Station", "Upgrade": "Upgrade"}.get(row["Type"], "Building")
        where = f"{source}:{row['BuildingName']}"
        row["Tag"] = self.resolve(kind, row["BuildingName"], where)
        row["BaseBuffsTags"] = self.resolve_list("Buff", row.get("BaseBuffs"), where + ":BaseBuffs")
        row["PassiveBuffsTags"] = self.resolve_list("Passive", row.get("PassiveBuffs"), where + ":PassiveBuffs")
        row["AreaRequirementsTag"] = self.resolve("Area", row.get("AreaRequirements"), where + ":AreaRequirements")
        row["ItemsNeededToBuildTags"] = self.quantities("Item", row.get("ItemsNeededToBuild"), where + ":ItemsNeededToBuild")
        row["ResourcesNeededToBuildTags"] = self.quantities(
            "Resource", row.get("ResourcesNeededToBuild"), where + ":ResourcesNeededToBuild")

    def job_name(self, row: dict) -> str:
        """'Medical Station / Treat Wounds'; the station cell may hold the station's Tag."""
        station = self.names.get(row["BuildingName"], row["BuildingName"])
        return f'{station} / {row["Work"] or "(research spend)"}'

    def tag_work_row(self, row: dict, source: str) -> None:
        where = f"{source}:{self.job_name(row)}"
        row["Tag"] = self.resolve("Job", self.job_name(row), where)
        row["PhaseTag"] = self.resolve("Phase", row.get("Phase"), where + ":Phase")
        row["WorkTypeTag"] = self.resolve("WorkType", row["Type"], where + ":Type")
        row["MoodTypeTag"] = self.resolve("Mood", row.get("MoodType"), where + ":MoodType")
        row["RequirementsTag"] = self.resolve("Requirement", row.get("Requirements"), where + ":Requirements")
        row["BaseBuffsTags"] = self.resolve_list("Buff", row.get("BaseBuffs"), where + ":BaseBuffs")
        row["ResourcesNeededToBuildTags"] = self.quantities(
            "Resource", row.get("ResourcesNeededToBuild"), where + ":ResourcesNeededToBuild")
        row["OutcomeTag"], row["OutcomeQuantity"] = self.outcome(row.get("Outcome"), where + ":Outcome")

    def tag_research_row(self, row: dict, source: str) -> None:
        where = f"{source}:{row['Name']}"
        row["Tag"] = self.resolve("Research", row["Name"], where)
        row["SpecialCostTags"] = self.quantities("Stat", row.get("SpecialCost"), where + ":SpecialCost")
        row["BaseBuffsTags"] = self.resolve_list("Buff", row.get("BaseBuffs"), where + ":BaseBuffs")

    def tag_resource_row(self, row: dict, source: str) -> None:
        """A starting stock row: a Resource (Metal ...) or an Item (food items, CopperGame 0040 F19)."""
        name = row["Resource"]
        tag = self.lookup.get("Resource", {}).get(_norm(name)) or self.lookup.get("Item", {}).get(_norm(name))
        row["Tag"] = tag or self.resolve("Resource", name, f"{source}:{name}")

    def tag_layout_row(self, row: dict, source: str) -> None:
        where = f"{source}:{row['Id']}"
        row["KindTag"] = self.resolve("LayoutKind", row.get("Kind"), where + ":Kind")
        row["SizeTag"] = self.resolve("LayoutSize", row.get("Size"), where + ":Size")

    # ---- cross-references between tables ---------------------------------
    def resolve_references(self, tables: dict) -> None:
        """Fills the *Tags reference columns; a dangling reference is an error."""
        def ref(table, field, row_name, names, kinds):
            tags = []
            for name in (names if isinstance(names, list) else split_list(names)):
                tag = name if self._kind_of(name) in kinds else None  # the cell already holds the Tag
                tag = tag or next((t for k in kinds if (t := self.lookup[k].get(_norm(name)))), None)
                if tag is None:
                    self.errors.append(f'{table}.{field}: "{row_name}" refers to "{name}", which does not exist')
                else:
                    tags.append(tag)
            return tags

        holders = ["Station", "Upgrade", "Building"]
        for table in ("Buildings", "Upgrades"):
            for row in tables[table]:
                row["UpgradesToTags"] = ref(table, "UpgradesTo", row["BuildingName"], row.get("UpgradesTo"), holders)
                row["ResearchRequirementTags"] = ref(
                    table, "ResearchRequirement", row["BuildingName"], row.get("ResearchRequirement"), ["Research"])
        for row in tables["Work"]:
            stations = ref("Work", "BuildingName", self.job_name(row), [row["BuildingName"]], ["Station", "Upgrade"])
            row["StationTag"] = stations[0] if stations else None
        for row in tables["ResearchTree"]:
            for field in ("RequirementA", "RequirementB"):
                tags = ref("ResearchTree", field, row["Name"], row.get(field), ["Research"] + holders)
                row[field + "Tag"] = tags[0] if tags else None

    # ---- generated outputs -----------------------------------------------
    def write_outputs(self) -> None:
        REGISTRY_DOC.parent.mkdir(parents=True, exist_ok=True)
        write_json(REGISTRY_DEST, [
            {"Kind": e["Kind"], "Tag": e["Tag"], "Name": e["Name"], "Aliases": e.get("Aliases", []),
             "DevComment": e.get("DevComment", "")} for e in self.entries])
        lines = ["# Tag registry", "",
                 "Generated by `python tools/import_data.py` (game-design) from `design/data/Attribute.json` (stats) and "
                 "`design/data/sources/BaseBuildingTags.json`. Every Tag and the human-readable names the sheets may use "
                 "for it. Do not edit; edit the two source files.", ""]
        for kind in ["Stat"] + list(KIND_PREFIX):
            rows = [e for e in self.entries if e["Kind"] == kind]
            if not rows:
                continue
            lines += [f"## {kind} ({len(rows)})", "", "| Tag | Name | Also accepted |", "|---|---|---|"]
            lines += [f'| `{e["Tag"]}` | {e["Name"]} | {", ".join(e.get("Aliases", []))} |' for e in rows]
            lines.append("")
        REGISTRY_DOC.write_text("\n".join(lines), encoding="utf-8", newline="\n")

        lines = ["# Proposed Gameplay Tags for the Unreal lead", "",
                 "Generated from `design/data/sources/BaseBuildingTags.json` (game-design). The leaf names are our proposal: please review. "
                 "Stat Tags come from `Attribute.json` and are not listed. New namespaces to confirm: `BB.Upgrade.*`, "
                 "`BB.Buff.*`, `BB.Passive.*`, `BB.Mood.*`, `BB.Area.*`, `BB.Requirement.*`, `BB.Phase.*`, "
                 "`BB.WorkType.*`, `BB.Layout.Kind.*`, `Inventory.Resource.*`, `Inventory.Item.*`. "
                 "`BB.Building.Size.*` already exists (our `Large` is your `Big`).", ""]
        for kind in KIND_PREFIX:
            rows = [e for e in self.entries if e["Kind"] == kind]
            lines += [f"## {kind}", "", "```ini"]
            lines += [f'GameplayTagList=(Tag="{e["Tag"]}",DevComment="{e["Name"]}")' for e in rows]
            lines += ["```", ""]
        UNREAL_DOC.write_text("\n".join(lines), encoding="utf-8", newline="\n")


REGISTRY = TagRegistry()

if __name__ == "__main__":
    problems = REGISTRY.integrity_errors()
    print("\n".join(problems) if problems else f"registry OK: {len(REGISTRY.entries)} Tags")
    sys.exit(1 if problems else 0)
