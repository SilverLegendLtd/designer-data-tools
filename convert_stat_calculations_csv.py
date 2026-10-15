#!/usr/bin/env python3
"""Convert the three tabs of "Mental & Physical Attributes & Skills - Surviving The Grey Legend"
into design/data/Bronze/character/:

  Stat Calculations -> StatCalculations.json  the Mental Attributes and Skills as MBTI formulas:
      value = clamp(round((EI*cEI + SN*cSN + TF*cTF + JP*cJP) / Divisor + Offset), Min, Max)
      axes -100..100, positive = E, S, T, J. `Weights` holds the four coefficients.
      A row may also weight other stats (column `Stats`, "Tag=coefficient; Tag=coefficient"): the
      sum then adds coefficient * the character's stat (`StatWeights` in the JSON). The Meter rows
      (Stamina) use this: Timing "Maximum" = the most the meter can hold, not its current value.
  Physical Bonuses  -> PhysicalBonuses.json   the MBTI bonuses, given once at birth (D126 in CopperGame).
      SN / JP / TF hold "+" (axis > 0), "-" (axis < 0) or null (any); an axis at exactly 0 matches
      neither. `Bonus` is the tier's value from the constants. A Tag's bonus is the sum of the
      matching rows, added to its base value, clamped once at the end.
  Stat Constants    -> StatConstants.json     tiers, base values, clamp range, axis range.

The build stops (IMPORT FAILED) when a Tag is not in Attribute.json, a coefficient is not a number,
the readable Formula column disagrees with the coefficients, a bonus names an unknown tier, or a
required constant is missing.
"""

import ast
import json
import operator

from pipeline_common import DATA_DIR, STAT_TAGS, blank_to_none, export_csv, load_csv_rows, write_json

SHEET = "Mental & Physical Attributes & Skills - Surviving The Grey Legend"
OUT = DATA_DIR / "Character"
AXES = ("EI", "SN", "TF", "JP")
REQUIRED_CONSTANTS = ["BonusTier.Large", "BonusTier.Medium", "BonusTier.Small", "PhysicalAttribute.BaseValue",
                      "PhysicalSkill.BaseValue", "Stat.Min", "Stat.Max", "Mbti.AxisMin", "Mbti.AxisMax"]
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
# Axis and stat values the Formula text and the coefficients are compared at.
_SAMPLES = [dict(zip(AXES, v)) for v in
            [(0, 0, 0, 0), (100, -100, 37, -61), (-80, 20, -100, 100), (13, 77, -42, -5), (-100, -100, 100, 55)]]
STAT_SAMPLE_VALUES = (10, 55, 0, 100, 31)  # one per sample; a stat's value is this times its position


def _number(text, label, problems):
    try:
        value = float((text or "").strip())
    except ValueError:
        problems.append(f"{label}: '{text}' is not a number")
        return 0
    return int(value) if value.is_integer() else value


def _evaluate(formula: str, axes: dict) -> float:
    """Arithmetic only: + - * / on numbers and the axis / stat names (no eval)."""
    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return -walk(node.operand) if isinstance(node.op, ast.USub) else walk(node.operand)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name) and node.id in axes:
            return axes[node.id]
        raise ValueError(f"unsupported in formula: {ast.dump(node)[:40]}")
    return walk(ast.parse(formula, mode="eval"))


def _stat_weights(text: str, where: str, problems: list) -> dict:
    """'PhysicalAttribute.Endurance=0.5; MentalAttribute.Focus=1' -> {Tag: coefficient}."""
    weights = {}
    for part in [p.strip() for p in (text or "").split(";") if p.strip()]:
        tag, _, coefficient = part.partition("=")
        tag = tag.strip()
        if tag not in STAT_TAGS.by_tag:
            problems.append(f"{where}: Stats names '{tag}', not a Tag in Attribute.json")
        weights[tag] = _number(coefficient, f"{where} Stats {tag}", problems)
    return weights


def _rows(tab: str):
    return load_csv_rows(export_csv(f"{SHEET} - {tab}.csv"))


def convert_constants(problems: list) -> dict:
    rows = []
    for row in _rows("Stat Constants"):
        key = (row.get("Key") or "").strip()
        if not key:
            continue
        raw = (row.get("Value") or "").strip()
        try:
            value = float(raw)
            value = int(value) if value.is_integer() else value
        except ValueError:
            value = raw
        rows.append({"Key": key, "Value": value, "Notes": blank_to_none(row.get("Notes"))})
    have = {r["Key"] for r in rows}
    for key in REQUIRED_CONSTANTS:
        if key not in have:
            problems.append(f"Stat Constants: required row {key} is missing")
    write_json(OUT / "StatConstants.json", rows)
    return {r["Key"]: r["Value"] for r in rows}


def convert_calculations(problems: list) -> int:
    out, seen = [], set()
    for line, row in enumerate(_rows("Stat Calculations"), start=2):
        tag = (row.get("Tag") or "").strip()
        if not tag:
            continue
        where = f"Stat Calculations row {line} ({tag})"
        if tag not in STAT_TAGS.by_tag:
            problems.append(f"{where}: not a Tag in Attribute.json")
        if tag in seen:
            problems.append(f"{where}: the Tag appears twice")
        seen.add(tag)
        weights = {axis: _number(row.get(axis), f"{where} {axis}", problems) for axis in AXES}
        divisor = _number(row.get("Divisor"), f"{where} Divisor", problems)
        offset = _number(row.get("Offset"), f"{where} Offset", problems)
        # A blank Min or Max means no limit on that side (Health may go over 100, D131).
        low = _number(row.get("Min"), f"{where} Min", problems) if (row.get("Min") or "").strip() else None
        high = _number(row.get("Max"), f"{where} Max", problems) if (row.get("Max") or "").strip() else None
        stat_weights = _stat_weights(row.get("Stats"), where, problems)
        formula = (row.get("Formula") or "").strip()
        if not divisor:
            problems.append(f"{where}: Divisor is 0")
        elif formula:
            try:
                for number, sample in enumerate(_SAMPLES):
                    # Stats are named in the Formula by the last part of their Tag ("Endurance").
                    stat_values = {tag.rsplit(".", 1)[-1]: STAT_SAMPLE_VALUES[(number + position) % 5]
                                   for position, tag in enumerate(stat_weights)}
                    from_weights = (sum(weights[a] * sample[a] for a in AXES)
                                    + sum(c * stat_values[t.rsplit(".", 1)[-1]] for t, c in stat_weights.items())) / divisor + offset
                    if abs(_evaluate(formula, {**sample, **stat_values}) - from_weights) > 1e-6:
                        problems.append(f"{where}: the Formula text '{formula}' does not match the EI/SN/TF/JP "
                                        f"coefficients, Divisor and Offset")
                        break
            except (ValueError, SyntaxError, ZeroDivisionError) as error:
                problems.append(f"{where}: cannot read the Formula text '{formula}' ({error})")
        out.append({"Tag": tag, "Name": blank_to_none(row.get("Name")), "Kind": blank_to_none(row.get("Kind")),
                    "Letters": blank_to_none(row.get("Letters")), "Weights": weights, "StatWeights": stat_weights,
                    "Divisor": divisor,
                    "Offset": offset, "Min": low, "Max": high, "Timing": blank_to_none(row.get("Timing")),
                    "Formula": formula or None, "Notes": blank_to_none(row.get("Notes"))})
    write_json(OUT / "StatCalculations.json", out)
    return len(out)


def convert_bonuses(constants: dict, problems: list) -> int:
    out = []
    for line, row in enumerate(_rows("Physical Bonuses"), start=2):
        tag = (row.get("Tag") or "").strip()
        if not tag:
            continue
        where = f"Physical Bonuses row {line} ({tag})"
        if tag not in STAT_TAGS.by_tag:
            problems.append(f"{where}: not a Tag in Attribute.json")
        tier = (row.get("Tier") or "").strip()
        bonus = constants.get(f"BonusTier.{tier}")
        if not isinstance(bonus, (int, float)):
            problems.append(f"{where}: Tier '{tier}' has no BonusTier.{tier} row in Stat Constants")
        entry = {"Tag": tag, "Tier": tier, "Bonus": bonus}
        for axis in ("SN", "JP", "TF"):
            sign = (row.get(axis) or "").strip()
            if sign not in ("", "+", "-"):
                problems.append(f"{where}: {axis} must be +, - or empty, not '{sign}'")
            entry[axis] = sign or None
        if not any(entry[a] for a in ("SN", "JP", "TF")):
            problems.append(f"{where}: no condition at all (SN, JP and TF are all empty)")
        entry.update({"Types": blank_to_none(row.get("Types")), "Timing": blank_to_none(row.get("Timing")),
                      "Notes": blank_to_none(row.get("Notes"))})
        out.append(entry)
    write_json(OUT / "PhysicalBonuses.json", out)
    return len(out)


def convert() -> tuple:
    """-> (calculation rows, bonus rows, problems)."""
    problems = []
    constants = convert_constants(problems)
    calculations = convert_calculations(problems)
    bonuses = convert_bonuses(constants, problems)
    return calculations, bonuses, problems


if __name__ == "__main__":
    calculations, bonuses, problems = convert()
    print(json.dumps({"calculations": calculations, "bonuses": bonuses, "problems": problems}, indent=2))
