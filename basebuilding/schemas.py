"""Declared schema (columns + types) for every generated base-building table.
import_data.py validates every row against it and writes
design/data/basebuilding/schemas/<Table>.schema.json, the DataTable shape the Unreal
port reads (foundation plan F2).

Types: string, int, number_or_item (a number, or the literal "item"),
tag:<Kind> (a registry Tag of that Kind; Kind "Stat" = Attribute.json),
tag_list:<Kind> (list of them), tag_map:<Kind> (Tag -> int quantity), bool, string_list, number, stat_deltas.
A trailing `?` allows null. Display-name columns are kept next to their Tag
columns until the runtime switches to Tags (foundation plan F3).
"""

import re

from pipeline_common import DATA_DIR, write_json
from tag_registry import REGISTRY

SCHEMA_DIR = DATA_DIR / "basebuilding" / "schemas"
_TAG = re.compile(r"^[A-Za-z][A-Za-z0-9]*(\.[A-Za-z0-9]+)+$")

_ELECTRICITY = "negative = supplies electricity (owner, C5)"
_ITEM = "\"item\" = the studied item's own levels set it (design doc 4.5); the placeholder stands until Items.json carries them (owner, C14)"

_BUILDING = {
    "Tag": "tag:Building", "BuildingName": "string", "Type": "string", "Description": "string?",
    "BaseBuffs": "string?", "BaseBuffsTags": "tag_list:Buff",
    "PassiveBuffs": "string?", "PassiveBuffsTags": "tag_list:Passive",
    "AreaRequirements": "string?", "AreaRequirementsTag": "tag:Area?",
    "ItemsNeededToBuild": "string?", "ItemsNeededToBuildTags": "tag_map:Item",
    "UpgradesTo": "string?", "UpgradesToTags": "tag_list:Building",
    "ResearchRequirement": "string?", "ResearchRequirementTags": "tag_list:Research",
    "ResourcesNeededToBuild": "string?", "ResourcesNeededToBuildTags": "tag_map:Resource",
    "ElectricityRequirements": "int", "MetalResource": "int", "WiresResource": "int",
    "PlasticResource": "int", "FuelResource": "int",
    "Capacity": "int?", "Domain": "string?", "DomainTag": "tag:Stat?",
}

SCHEMAS = {
    "BaseBuildingEffects": {
        "conventions": {"Tag": "GameplayEffect.BaseBuilding.<Name> (CopperLegend's effect format, category BaseBuilding)",
                        "DurationHours": "game hours, linear decay (D44); null = until removed (e.g. Starving ends with a meal)",
                        "WorkTierModifier": "changes a work check's outcome tier (-1 = one tier worse)"},
        "columns": {"Tag": "tag:Effect", "Name": "string", "EffectType": "string",
                    "CheckSkill": "string?", "CheckSkillTag": "tag:Stat?", "SecondaryCheckSkill": "string?", "SecondaryCheckSkillTag": "tag:Stat?",
                    "CheckAttribute": "string?", "CheckAttributeTag": "tag:Stat?", "DurationCheckSkill": "string?", "DurationCheckSkillTag": "tag:Stat?",
                    "DurationCheckSecondarySkill": "string?", "DurationCheckSecondarySkillTag": "tag:Stat?",
                    "DurationCheckAttribute": "string?", "DurationCheckAttributeTag": "tag:Stat?",
                    "Effects": "stat_deltas", "Arousal": "number?", "Valence": "number?", "WorkTierModifier": "int?",
                    "CannotWork": "bool", "DurationHours": "int?", "AppliedBy": "string?", "Notes": "string?"},
    },
    "Items": {
        "conventions": {"Tag": "Inventory.Item.<Name>", "CategoryTag": "Inventory.Category.*; Food items are what cooking consumes (CopperGame 0040)",
                        "Nutrition": "how many meals the item is worth when cooked, before the cook's outcome tier"},
        "columns": {"Tag": "tag:Item", "Name": "string", "Category": "string", "CategoryTag": "tag:ItemCategory",
                    "Nutrition": "int", "Sources": "string_list", "NeedsResearch": "bool", "Notes": "string?"},
    },
    "LeisureActivities": {
        "conventions": {"Tag": "BB.Leisure.<Building>.<Activity>; BuildingTag is null for the universal Wandering (BuildingName \"Base\")"},
        "columns": {"Tag": "tag:Leisure", "BuildingName": "string", "Activity": "string", "Temperament": "string?",
                    "CoreNeed": "string?", "Description": "string?", "Participation": "string?", "BuildingTag": "tag:Building?",
                    "Movement": "string", "StepTicks": "int", "Reach": "int"},
    },
    "Buildings": {"conventions": {"ElectricityRequirements": _ELECTRICITY,
                                  "Tag": "BB.Building.* or BB.Station.*"}, "columns": _BUILDING},
    "Upgrades": {"conventions": {"ElectricityRequirements": _ELECTRICITY, "Tag": "BB.Upgrade.*"},
                 "columns": dict(_BUILDING, Tag="tag:Upgrade")},
    "Work": {
        "conventions": {
            "Difficulty": _ITEM, "Workload": "same \"item\" convention as Difficulty",
            "Tag": "BB.Job.<Station>.<Work>: the start and finish rows of one job share it (PhaseTag tells them apart)",
            "PrimarySkill": "stat Tag from Attribute.json",
        },
        "columns": {
            "Tag": "tag:Job", "StationTag": "tag:Station?", "BuildingName": "string", "Type": "string",
            "WorkTypeTag": "tag:WorkType", "Work": "string?", "Phase": "string?", "PhaseTag": "tag:Phase?",
            "PrimarySkill": "tag:Stat?", "SecondarySkill": "tag:Stat?", "Attribute": "tag:Stat?",
            "Difficulty": "number_or_item?", "MoodType": "string?", "MoodTypeTag": "tag:Mood?",
            "Workload": "number_or_item?", "Requirements": "string?", "RequirementsTag": "tag:Requirement?",
            "Description": "string?", "BaseBuffs": "string?", "BaseBuffsTags": "tag_list:Buff",
            "ResourcesNeededToBuild": "string?", "ResourcesNeededToBuildTags": "tag_map:Resource",
            "Outcome": "string?", "OutcomeTag": "tag:Item?", "OutcomeQuantity": "int?",
            "MetalResource": "int?", "WiresResource": "int?", "PlasticResource": "int?", "FuelResource": "int?",
        },
    },
    "ResearchTree": {
        "conventions": {"SkillTags": "the Physical Skills this node belongs to",
                        "SpecialCostTags": "skill Tag -> points; \"Firearms, Medical 15\" = 15 in each listed pool"},
        "columns": {
            "Tag": "tag:Research", "Name": "string", "SkillTags": "tag_list:Stat", "Tier": "int", "BasicCost": "int",
            "SpecialCost": "string?", "SpecialCostTags": "tag_map:Stat",
            "RequirementA": "string?", "RequirementATag": "tag?", "RequirementB": "string?", "RequirementBTag": "tag?",
            "Description": "string?", "BaseBuffs": "string?", "BaseBuffsTags": "tag_list:Buff",
        },
    },
    "StartingResources": {"conventions": {}, "columns": {"Tag": "tag:Resource", "Resource": "string", "Amount": "int"}},
    "BaseLayout": {
        "conventions": {"X/Y/Width/Height": "2D world pixels from the base's top-left (D65)"},
        "columns": {"Id": "string", "Kind": "string", "KindTag": "tag:LayoutKind", "Size": "string?",
                    "SizeTag": "tag:LayoutSize?", "X": "int", "Y": "int", "Width": "int", "Height": "int",
                    "EntranceX": "int?", "EntranceY": "int?"},
    },
}


def _is_tag(kind: str, value) -> bool:
    if not (isinstance(value, str) and _TAG.match(value)):
        return False
    if kind == "":
        return value in REGISTRY.names  # any registry Tag
    if kind in ("Building", "Station"):
        # a building-ish Tag column may hold a Building, Station or Upgrade Tag
        return any(value in (e["Tag"] for e in REGISTRY.entries if e["Kind"] == k) for k in (kind, "Station", "Upgrade", "Building"))
    return REGISTRY._kind_of(value) == kind


def _ok(type_name: str, value) -> bool:
    if type_name.endswith("?"):
        if value is None:
            return True
        type_name = type_name[:-1]
    base, _, kind = type_name.partition(":")
    if base == "string":
        return isinstance(value, str)
    if base == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if base == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if base == "stat_deltas":
        return isinstance(value, list) and all(isinstance(v, dict) and _is_tag("Stat", v.get("StatTag")) and isinstance(v.get("Value"), (int, float)) for v in value)
    if base == "bool":
        return isinstance(value, bool)
    if base == "string_list":
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    if base == "number_or_item":
        return value == "item" or (isinstance(value, (int, float)) and not isinstance(value, bool))
    if base == "tag":
        return _is_tag(kind, value)
    if base == "tag_list":
        return isinstance(value, list) and all(_is_tag(kind, v) for v in value)
    if base == "tag_map":
        return isinstance(value, dict) and all(_is_tag(kind, k) and isinstance(v, int) for k, v in value.items())
    return False


def validate(tables: dict) -> list:
    """Every row of every table against its schema; unknown or missing columns count."""
    errors = []
    for name, rows in tables.items():
        columns = SCHEMAS[name]["columns"]
        for index, row in enumerate(rows):
            label = f"{name}[{index}] {row.get('Tag') or row.get('Id') or ''}".strip()
            for extra in sorted(set(row) - set(columns)):
                errors.append(f"{label}: column {extra} is not in the schema")
            for column, type_name in columns.items():
                if column not in row:
                    if not type_name.endswith("?"):
                        errors.append(f"{label}: column {column} is missing")
                elif not _ok(type_name, row[column]):
                    errors.append(f"{label}: {column} = {row[column]!r} is not {type_name}")
    return errors


def write_schemas() -> None:
    for name, schema in SCHEMAS.items():
        write_json(SCHEMA_DIR / f"{name}.schema.json", {"table": name, **schema})
