"""Tests for sheet_rules.py: cell validation (names vs Tags, strict mode, unknown values) and the
name->Tag converter, including that a fully converted sheet imports to the same Tags.

    python -m unittest discover -s tools/tests -v
"""

import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import sheet_rules  # noqa: E402

DATA = TOOLS.parent / "design" / "data"
FIXTURE_EXPORTS = Path(__file__).resolve().parent / "fixtures" / "exports"
NEW_BUILDINGS = f"{sheet_rules.BSW} - New Buildings"
RESEARCH = f"{sheet_rules.BSW} - Research List"


def registries() -> sheet_rules.Registries:
    kinds = {"Stat": [{"Tag": e["Tag"], "Name": e["Name"]}
                      for e in json.loads((DATA / "Attribute.json").read_text(encoding="utf-8"))]}
    for e in json.loads((DATA / "sources" / "BaseBuildingTags.json").read_text(encoding="utf-8")):
        kinds.setdefault(e["Kind"], []).append({"Tag": e["Tag"], "Name": e["Name"], "Aliases": e.get("Aliases", [])})
    with (FIXTURE_EXPORTS / "Background Data - Background.csv").open(encoding="utf-8-sig", newline="") as f:
        kinds["Background"] = [{"Tag": r["Tag"], "Name": r["Name"]} for r in csv.DictReader(f)]
    return sheet_rules.Registries(kinds)


def read(sheet):
    with (FIXTURE_EXPORTS / f"{sheet}.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


class ValidateTest(unittest.TestCase):
    """Rows on the real New Buildings header; the five given cells go to BuildingName, Type, Work,
    PrimarySkill (column E) and BaseBuffs (column M), everything else blank."""
    reg = registries()
    header = read(NEW_BUILDINGS)[0]

    def check(self, cells, strict=False):
        row = [""] * len(self.header)
        for title, value in zip(["BuildingName", "Type", "Work", "PrimarySkill", "BaseBuffs"], cells):
            row[self.header.index(title)] = value
        return sheet_rules.validate_rows(NEW_BUILDINGS, self.header, [row], self.reg, strict)

    def test_tag_cell_is_silent(self):
        self.assertEqual(self.check(["Medical Station", "Basic", "Treat Wounds", "PhysicalSkill.Medical",
                                     "BB.Buff.WellBeing"]), [])

    def test_display_name_is_a_warning_with_the_tag(self):
        problems = self.check(["Medical Station", "Basic", "Treat Wounds", "Medical", "Well-Being"])
        self.assertEqual([(p["cell"], p["level"]) for p in problems], [("E2", "warning"), ("M2", "warning")])
        self.assertIn("PhysicalSkill.Medical", problems[0]["message"])

    def test_strict_makes_names_errors(self):
        problems = self.check(["Medical Station", "Basic", "Treat Wounds", "Medical", ""], strict=True)
        self.assertEqual([(p["cell"], p["level"]) for p in problems], [("E2", "error")])

    def test_unknown_value_is_an_error(self):
        problems = self.check(["Medical Station", "Basic", "Treat Wounds", "PhysicalSkill.Medicine", ""])
        self.assertEqual([(p["cell"], p["level"], p["value"]) for p in problems],
                         [("E2", "error", "PhysicalSkill.Medicine")])

    def test_work_only_column_ignored_on_building_rows(self):
        self.assertEqual(self.check(["Medical Station", "Station", "", "Nonsense", ""]), [])

    def test_real_exports_have_no_errors(self):
        for sheet in sheet_rules.SHEETS:
            header, rows = read(sheet)
            errors = [p for p in sheet_rules.validate_rows(sheet, header, rows, self.reg, False)
                      if p["level"] == "error"]
            self.assertEqual(errors, [], sheet)


class ConvertTest(unittest.TestCase):
    reg = registries()

    def test_cell_formats(self):
        rule = sheet_rules.SHEETS[NEW_BUILDINGS]["columns"]["Resources Needed to Build"]
        self.assertEqual(sheet_rules._convert_cell("Metal 15, Wires 10", rule, self.reg),
                         "Inventory.Resource.Metal 15, Inventory.Resource.Wires 10")
        special = sheet_rules.SHEETS[RESEARCH]["columns"]["SpecialCost"]
        self.assertEqual(sheet_rules._convert_cell("Firearms, Medical 15", special, self.reg),
                         "PhysicalSkill.Firearms, PhysicalSkill.Medical 15")

    def test_converted_sheets_have_no_name_warnings_and_import_to_the_same_tags(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            converted = tmp / "exports"
            shutil.copytree(FIXTURE_EXPORTS, converted)
            for sheet in sheet_rules.SHEETS:
                header, rows = read(sheet)
                sheet_rules.convert_rows(sheet, header, rows, self.reg)
                problems = sheet_rules.validate_rows(sheet, header, rows, self.reg, strict=True)
                self.assertEqual([p for p in problems if p["message"].startswith("display name")], [], sheet)
                with (converted / f"{sheet}.csv").open("w", encoding="utf-8", newline="") as f:
                    csv.writer(f).writerows([header] + rows)
            outputs = {}
            for name, exports in (("names", FIXTURE_EXPORTS), ("tags", converted)):
                out = tmp / name
                out.mkdir()
                shutil.copy(DATA / "Attribute.json", out)
                shutil.copytree(DATA / "sources", out / "sources")
                env = {**os.environ, "DESIGN_EXPORTS_DIR": str(exports), "DESIGN_DATA_DIR": str(out)}
                result = subprocess.run([sys.executable, str(TOOLS / "import_data.py"), "--build"], env=env,
                                        capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                outputs[name] = out
            for table in ("Buildings", "Upgrades", "Work", "ResearchTree", "LeisureActivities"):
                before, after = (json.loads((outputs[n] / "basebuilding" / f"{table}.json").read_text(encoding="utf-8"))
                                 for n in ("names", "tags"))
                tag_cols = lambda rows: [{k: v for k, v in r.items() if k.endswith(("Tag", "Tags"))} for r in rows]  # noqa: E731
                self.assertEqual(tag_cols(before), tag_cols(after), table)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


@unittest.skipUnless(shutil.which("node"), "Node.js not installed")
class AppsScriptParityTest(unittest.TestCase):
    """apps_script/ExportSheets.gs (run under Node) gives the same counts as sheet_rules.py."""

    def test_same_errors_warnings_and_conversions(self):
        reg = registries()
        tmp = Path(tempfile.mkdtemp())
        try:
            shutil.copytree(FIXTURE_EXPORTS, tmp, dirs_exist_ok=True)
            kinds = reg.kinds
            (tmp / "validation_rules.json").write_text(
                json.dumps({"strict": False, "kinds": kinds, "sheets": sheet_rules.SHEETS}), encoding="utf-8")
            result = subprocess.run(["node", str(Path(__file__).parent / "gs_parity.js"),
                                     str(TOOLS / "apps_script" / "ExportSheets.gs"), str(tmp)],
                                    capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            js = json.loads(result.stdout)
            for sheet in sheet_rules.SHEETS:
                header, rows = read(sheet)
                problems = sheet_rules.validate_rows(sheet, header, rows, reg, False)
                changes = sheet_rules.convert_rows(sheet, header, [r[:] for r in rows], reg)
                expected = {"errors": sum(p["level"] == "error" for p in problems),
                            "warnings": sum(p["level"] == "warning" for p in problems), "conversions": len(changes)}
                self.assertEqual(js[sheet], expected, sheet)
            self.assertGreater(js[NEW_BUILDINGS]["conversions"], 400)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
