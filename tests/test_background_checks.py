"""check_backgrounds (import_data.py): the Background tabs must hold together after converting.
Each case breaks a copy of design/data/character the way a sheet once broke (2026-10-06)."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import import_data  # noqa: E402

SOURCE = import_data.DATA_DIR / "character"


class BackgroundChecksTest(unittest.TestCase):
    def broken(self, table: str, change) -> list:
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        for path in SOURCE.glob("Background*.json"):
            shutil.copy(path, folder / path.name)
        if table:
            target = folder / f"{table}.json"
            rows = json.loads(target.read_text(encoding="utf-8"))
            change(rows)
            target.write_text(json.dumps(rows), encoding="utf-8")
        return import_data.check_backgrounds(folder)

    def test_the_real_data_holds_together(self):
        self.assertEqual(self.broken("", None), [])

    def test_a_blank_tag_header_fails(self):
        def blank(rows):
            for row in rows:
                row[" "] = row.pop("Tag")
        problems = self.broken("Background_Adult", blank)
        self.assertEqual(len(problems), 5)
        self.assertIn('has no Tag (is cell A1 exactly "Tag"?', problems[0])

    def test_a_row_without_stats_fails(self):
        def empty(rows):
            rows[4]["AttributeModifiers"] = {}
        problems = self.broken("Background_Childhood", empty)
        self.assertEqual(problems, [f"Background Data - Childhood: {json.loads((SOURCE / 'Background_Childhood.json').read_text(encoding='utf-8'))[4]['Name']} has no stat modifiers at all (lost in the sheet?)"])

    def test_an_unknown_unlock_and_a_wrong_stat_fail(self):
        def bad(rows):
            rows[0]["UnlockedBackgrounds"] = ["Background.Nobody"]
            rows[0]["AttributeModifiers"]["MentalSkill.NotAStat"] = 5.0
        problems = self.broken("Background_YoungAdult", bad)
        self.assertEqual(len(problems), 2)
        self.assertTrue(any("Background.Nobody, which is not a Background" in p for p in problems))
        self.assertTrue(any("MentalSkill.NotAStat is not a stat Tag" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
