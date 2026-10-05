"""Tests for import_data.py: builds design/data from frozen sheet exports (fixtures/exports)
into a temp folder and checks real values, then checks the consumer drift detector.

    python -m unittest discover -s tools/tests -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
DATA = TOOLS.parent / "design" / "data"
FIXTURE_EXPORTS = Path(__file__).resolve().parent / "fixtures" / "exports"


def run(*args, env):
    return subprocess.run([sys.executable, str(TOOLS / "import_data.py"), *args],
                          env=env, capture_output=True, text=True, encoding="utf-8")


class ImportDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.out = cls.tmp / "data"
        cls.out.mkdir()
        shutil.copy(DATA / "Attribute.json", cls.out)
        shutil.copytree(DATA / "sources", cls.out / "sources")
        cls.env = {**os.environ, "DESIGN_EXPORTS_DIR": str(FIXTURE_EXPORTS), "DESIGN_DATA_DIR": str(cls.out)}
        cls.result = run("--build", env=cls.env)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def table(self, rel):
        return json.loads((self.out / rel).read_text(encoding="utf-8"))

    def test_build_succeeds(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout + self.result.stderr)
        self.assertIn("81 work rows", self.result.stdout)

    def test_work_row_has_resolved_tags(self):
        rows = [r for r in self.table("basebuilding/Work.json")
                if r["Tag"] == "BB.Job.MedicalStation.TreatWounds" and r["Phase"] == "start"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["PrimarySkill"], "PhysicalSkill.Medical")
        self.assertEqual(rows[0]["Difficulty"], 2)
        self.assertEqual(rows[0]["StationTag"], "BB.Station.MedicalStation")
        self.assertEqual(rows[0]["RequirementsTag"], "BB.Requirement.Patient")

    def test_generators_keep_sheet_electricity(self):
        by_tag = {b["Tag"]: b["ElectricityRequirements"] for b in self.table("basebuilding/Buildings.json")}
        self.assertEqual(by_tag["BB.Building.SmallPowerGenerator"], -2)
        self.assertEqual(by_tag["BB.Building.LargePowerGenerator"], -15)

    def test_research_and_stats_counts(self):
        self.assertEqual(len(self.table("basebuilding/ResearchTree.json")), 59)
        self.assertEqual(len(self.table("basebuilding/StatTags.json")), 42)

    def test_background_nested_columns(self):
        adult = {r["Tag"]: r for r in self.table("character/Background_Adult.json")}
        guard = adult["LifePath.Adult.CaravanGuard"]
        self.assertEqual(guard["AttributeModifiers"]["PhysicalSkill.Firearms"], 45.0)
        self.assertEqual(guard["UnlockedBackgrounds"], ["Background.SyndicateOperative",
                                                        "Background.ProfessionalMilitary"])

    def test_unknown_sheet_value_fails_the_build(self):
        bad = self.tmp / "bad_exports"
        shutil.copytree(FIXTURE_EXPORTS, bad)
        csv = bad / "Buildings, Stations, Work - Surviving the Grey Legend - New Buildings.csv"
        text = csv.read_text(encoding="utf-8-sig").replace("Well-Being", "Wellness Typo", 1)
        csv.write_text(text, encoding="utf-8")
        out = self.tmp / "bad_data"
        shutil.copytree(self.out, out, dirs_exist_ok=True)
        result = run("--build", env={**self.env, "DESIGN_EXPORTS_DIR": str(bad), "DESIGN_DATA_DIR": str(out)})
        self.assertEqual(result.returncode, 1)
        self.assertIn("Wellness Typo", result.stdout)


if __name__ == "__main__":
    unittest.main()
