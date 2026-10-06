#!/usr/bin/env python3
"""Convert the exported "Events List - Night Events - Night Events.csv" to
design/data/basebuilding/NightEvents.json (CopperGame ideas 0037 / 0039).

One row per event: EventName, Beat, Conditions, Subject, Severity, DeadlineSource,
Weight, CooldownDays, Once, Title, Text, Choice<n>Label / Cost / Outcomes,
FirstSlice, Notes. Every EventName must have an Event Tag (BB.Event.<EventName>)
in sources/BaseBuildingTags.json.

Parsed where the grammar is known, kept as text where it is not (the event
engine reads what it can run; FirstSlice = Yes rows are the ones it fires):
  Conditions  "; "-list. "<base stat> <band>" (e.g. "Well-Being Low") -> StatTag + BandTag;
              anything else stays {"Raw": ...}.
  Cost        "<base stat> <n>" -> {stat Tag: n}.
  Outcomes    "; "-list. "Effect <effect> on <target>" -> Effect; "<base stat> +n" -> Stat;
              "<resource> +/-n" -> Resource; anything else -> {"Raw": ...}.
Only FirstSlice = Yes rows must resolve every effect name; a later row may name an effect the list
does not have yet (e.g. "Injured"): it stays text until the designers add it.
"""

import re

from tag_registry import REGISTRY
from pipeline_common import DATA_DIR, export_csv, blank_to_none, load_csv_rows, parse_int, write_json

CSV_NAME = "Events List - Night Events - Night Events.csv"
DEST = DATA_DIR / "basebuilding" / "NightEvents.json"
CHOICES = 3
_BANDS = ("Low", "Weak", "Normal", "High")
_AMOUNT = re.compile(r"^(.+?)\s+([+-]?\d+)$")
_EFFECT = re.compile(r"^Effect\s+(.+?)\s+on\s+(.+?)(?:\s*\((.*)\))?$")


def _parts(value) -> list:
    return [p.strip() for p in (value or "").split(";") if p.strip()]


def _condition(text: str, where: str) -> dict:
    name, _, band = text.rpartition(" ")
    if band in _BANDS and name:
        return {"Raw": text, "StatTag": REGISTRY.resolve("Buff", name, where),
                "BandTag": REGISTRY.resolve("Band", band, where)}
    return {"Raw": text}


def _cost(value, where: str) -> dict:
    cost = {}
    for part in _parts(value):
        match = _AMOUNT.match(part)
        if not match:
            REGISTRY.errors.append(f'{where}: cost "{part}" is not "<base stat> <n>"')
            continue
        tag = REGISTRY.resolve("Buff", match.group(1), where)
        if tag:
            cost[tag] = abs(int(match.group(2)))
    return cost


def _outcome(text: str, where: str, strict: bool) -> dict:
    effect = _EFFECT.match(text)
    if effect:
        known = REGISTRY.lookup.get("Effect", {}).get(re.sub(r"[^a-z0-9]", "", effect.group(1).lower()))
        if not known and not strict:
            return {"Raw": text}
        return {"Raw": text, "Kind": "Effect", "Tag": REGISTRY.resolve("Effect", effect.group(1), where), "Target": effect.group(2)}
    amount = _AMOUNT.match(text)
    if amount:
        name, value = amount.group(1), int(amount.group(2))
        if REGISTRY.lookup.get("Buff", {}).get(re.sub(r"[^a-z0-9]", "", name.lower())):
            return {"Raw": text, "Kind": "Stat", "Tag": REGISTRY.resolve("Buff", name, where), "Amount": value}
        if REGISTRY.lookup.get("Resource", {}).get(re.sub(r"[^a-z0-9]", "", name.lower())):
            return {"Raw": text, "Kind": "Resource", "Tag": REGISTRY.resolve("Resource", name, where), "Amount": value}
    return {"Raw": text}


def convert() -> int:
    path = export_csv(CSV_NAME)
    events = []
    if not path.exists():
        print(f"  (no {CSV_NAME} exported yet: NightEvents.json is empty)")
    else:
        for row in load_csv_rows(path):
            name = (row.get("EventName") or "").strip()
            if not name:
                continue
            where = f"{CSV_NAME}:{name}"
            strict = (row.get("FirstSlice") or "").strip().lower() == "yes"
            choices = []
            for n in range(1, CHOICES + 1):
                label = blank_to_none(row.get(f"Choice{n}Label"))
                if label is None:
                    continue
                choices.append({
                    "Label": label,
                    "Cost": _cost(row.get(f"Choice{n}Cost"), f"{where}:Choice{n}Cost"),
                    "Outcomes": [_outcome(p, f"{where}:Choice{n}Outcomes", strict) for p in _parts(row.get(f"Choice{n}Outcomes"))],
                })
            events.append({
                "Tag": REGISTRY.resolve("Event", name, where + ":EventName"),
                "EventName": name,
                "Beat": (row.get("Beat") or "").strip(),
                "Conditions": [_condition(p, where + ":Conditions") for p in _parts(row.get("Conditions"))],
                "Subject": blank_to_none(row.get("Subject")),
                "Severity": blank_to_none(row.get("Severity")),
                "DeadlineSource": blank_to_none(row.get("DeadlineSource")),
                "Weight": parse_int(row.get("Weight")),
                "CooldownDays": parse_int(row.get("CooldownDays")),
                "Once": (row.get("Once") or "").strip().lower() in ("yes", "y", "true"),
                "Title": blank_to_none(row.get("Title")),
                "Text": blank_to_none(row.get("Text")),
                "Choices": choices,
                "FirstSlice": (row.get("FirstSlice") or "").strip(),
            })
    write_json(DEST, events)
    return len(events)
