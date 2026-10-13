"""Tests for convert_stat_calculations_csv.py (the "Mental & Physical Attributes & Skills" tabs):
the converter against the frozen fixture exports, and that it refuses broken rows.

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
DATA = TOOLS.parent / "design" / "data"
FIXTURE_EXPORTS = Path(__file__).resolve().parent / "fixtures" / "exports"
SHEET = "Mental & Physical Attributes & Skills - Surviving The Grey Legend"


def convert(exports: Path, out: Path):
    env = {**os.environ, "DESIGN_EXPORTS_DIR": str(exports), "DESIGN_DATA_DIR": str(out)}
    return subprocess.run([sys.executable, str(TOOLS / "convert_stat_calculations_csv.py")],
                          env=env, capture_output=True, text=True, encoding="utf-8")


class StatCalculationsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "data"
        self.out.mkdir()
        shutil.copy(DATA / "Attribute.json", self.out)
        self.exports = self.tmp / "exports"
        shutil.copytree(FIXTURE_EXPORTS, self.exports)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def table(self, name):
        return json.loads((self.out / "character" / name).read_text(encoding="utf-8"))

    def edit(self, tab, change):
        path = self.exports / f"{SHEET} - {tab}.csv"
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        change(rows)
        with path.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(rows)

    def test_converts_every_row_with_real_values(self):
        result = convert(self.exports, self.out)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        by_tag = {r["Tag"]: r for r in self.table("StatCalculations.json")}
        self.assertEqual(len(by_tag), 23)
        self.assertEqual(by_tag["MentalAttribute.Focus"]["Weights"], {"EI": -1, "SN": 0, "TF": 0, "JP": 0})
        self.assertEqual((by_tag["MentalAttribute.Focus"]["Divisor"], by_tag["MentalAttribute.Focus"]["Offset"]), (2, 50))
        self.assertEqual(by_tag["MentalSkill.ResearchAptitude"]["Weights"], {"EI": -1, "SN": 1, "TF": 1, "JP": 0})
        self.assertEqual(by_tag["MentalSkill.ResearchAptitude"]["Divisor"], 6)

    def test_bonuses_take_their_value_from_the_tier_constants(self):
        convert(self.exports, self.out)
        rows = self.table("PhysicalBonuses.json")
        self.assertEqual(len(rows), 9)
        endurance = {(r["Tier"], r["SN"], r["JP"]): r["Bonus"] for r in rows if r["Tag"] == "PhysicalAttribute.Endurance"}
        self.assertEqual(endurance, {("Large", "-", None): 15, ("Small", "+", "+"): 5})
        agility = [r for r in rows if r["Tag"] == "PhysicalAttribute.Agility"]
        self.assertEqual([(r["Bonus"], r["SN"], r["TF"]) for r in agility], [(10, "-", "-")])

    def test_unknown_tag_stops_the_build(self):
        self.edit("Stat Calculations", lambda rows: rows[1].__setitem__(0, "MentalAttribute.Nonsense"))
        result = convert(self.exports, self.out)
        self.assertIn("(MentalAttribute.Nonsense): not a Tag in Attribute.json", result.stdout + result.stderr)

    def test_formula_text_must_match_the_coefficients(self):
        header = None

        def change(rows):
            nonlocal header
            header = rows[0]
            rows[1][header.index("Formula")] = "(-EI + 100) / 2"  # SocialEnergy's real formula is (EI + 100) / 2

        self.edit("Stat Calculations", change)
        self.assertIn("does not match", convert(self.exports, self.out).stdout)

    def test_unknown_tier_and_bad_sign_are_reported(self):
        def change(rows):
            header = rows[0]
            rows[1][header.index("Tier")] = "Huge"
            rows[2][header.index("SN")] = "x"

        self.edit("Physical Bonuses", change)
        output = convert(self.exports, self.out).stdout
        self.assertIn("Tier 'Huge' has no BonusTier.Huge", output)
        self.assertIn("SN must be +, - or empty, not 'x'", output)


if __name__ == "__main__":
    unittest.main()
