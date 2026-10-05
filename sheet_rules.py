"""Which sheet columns hold which kind of Tag, and the sheet-level validator.

One declaration, two users:
  - import_data.py validates the exported CSVs with validate_csv() and prints problems by cell (A1).
  - `import_data.py --publish-manifest` writes these rules plus every registry to
    Design/exports/validation_rules.json, which apps_script/ExportSheets.gs reads to validate the
    sheets themselves each morning (same logic, ported to Apps Script; keep the two in step).

Column roles:
  ref       a reference to registry entries: the cell should hold Tag(s). Converted by the
            Apps Script name->Tag converter, and a display name is a warning (an error when strict).
  identity  the row's own display name; its Tag comes from the registry. Never converted
            (it is what the game shows); only checked to exist.
Formats: single, list ("A, B"), quantities ("A 15, B 10"; names before a number share it),
outcome ("20 Item"). A column may be scoped with `when` (only rows whose Type is in the list,
mirroring the converters) and may list `except` values that are not registry entries.
Sheet options: `skip_blank` (rows with that column blank are not data), `header_kinds` (headers
like "AttributeModifiers/<Tag>" whose Tag part must be a registry Tag) and `header_level`.
"""

import re

BSW = "Buildings, Stations, Work - Surviving the Grey Legend"
HOLDERS = ["Station", "Upgrade", "Building"]


BUILDING_ROWS = ["Building", "Station", "Upgrade"]
WORK_ROWS = ["Basic", "Crafting", "ResearchItem", "Research"]


def _ref(kinds, fmt="single", when=None):
    rule = {"role": "ref", "kinds": kinds if isinstance(kinds, list) else [kinds], "format": fmt}
    return dict(rule, when=when) if when else rule


def _identity(kinds, when=None, except_=None):
    rule = {"role": "identity", "kinds": kinds if isinstance(kinds, list) else [kinds], "format": "single"}
    if when:
        rule["when"] = when
    if except_:
        rule["except"] = except_
    return rule


def _scoped(columns: dict, when: list) -> dict:
    return {title: dict(rule, when=when) for title, rule in columns.items()}


_CHECK = {"PrimarySkill": _ref("Stat"), "SecondarySkill": _ref("Stat"), "Attribute": _ref("Stat"),
          "MoodType": _ref("Mood")}
# header_level "warning": the Background Data Adult tab still has a MentalSkill.InitiatingConversations
# column, which is not a stat (owner 2026-10-05: designers remove it). Make it "error" once it is gone.
_BACKGROUND_HEADERS = {"header_kinds": {"AttributeModifiers/": "Stat"}, "header_level": "warning"}
_BACKGROUND = {"columns": {"UnlockedBackgrounds/0": _ref("Background"), "UnlockedBackgrounds/1": _ref("Background")},
               **_BACKGROUND_HEADERS}

SHEETS = {
    f"{BSW} - New Buildings": {"skip_blank": "Type", "columns": {
        "BuildingName": _identity(HOLDERS),
        **_scoped({**_CHECK, "Requirements": _ref("Requirement")}, WORK_ROWS),
        "BaseBuffs": _ref("Buff", "list"),
        **_scoped({"PassiveBuffs": _ref("Passive", "list"), "Area Requirements": _ref("Area"),
                   "Items Needed to Build": _ref("Item", "quantities"), "UpgradesTo": _ref(HOLDERS, "list"),
                   "ResearchRequirement": _ref("Research", "list"),
                   "Resources Needed to Build": _ref("Resource", "quantities")}, BUILDING_ROWS)}},
    f"{BSW} - Crafting List": {"skip_blank": "Station", "columns": {
        "Station": _ref(["Station", "Upgrade"]), **_CHECK,
        "Resources Needed to Build": _ref("Resource", "quantities"), "Outcome": _ref("Item", "outcome"),
        "BaseBuffs": _ref("Buff", "list")}},
    f"{BSW} - Research List": {"columns": {
        "Name": _identity("Research"), "Skill": _ref("Stat", "list"), **_CHECK,
        "SpecialCost": _ref("Stat", "quantities"), "RequirementA": _ref(["Research"] + HOLDERS, "list"),
        "RequirementB": _ref(["Research"] + HOLDERS, "list"), "BaseBuffs": _ref("Buff", "list")}},
    f"{BSW} - Leisure Buildings": {"skip_blank": "Type", "columns": {
        "BuildingName": _identity("Building", except_=["Base"]),
        **_scoped({"BaseBuffs": _ref("Buff", "list"), "Area Requirements": _ref("Area"),
                   "ResearchRequirement": _ref("Research", "list")}, ["Leisure Building"])}},
    "Background Data - Background": {"columns": {}, **_BACKGROUND_HEADERS},
    "Background Data - Childhood": _BACKGROUND,
    "Background Data - YoungAdult": _BACKGROUND,
    "Background Data - Adult": _BACKGROUND,
}

_QUANTITY = re.compile(r"^(.*?)\s+(\d+)$")
_OUTCOME = re.compile(r"^(\d+)\s+(.+)$")


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def a1(col: int, row: int) -> str:
    """0-based column, 1-based row -> 'B7'."""
    letters = ""
    col += 1
    while col:
        col, rem = divmod(col - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{row}"


class Registries:
    """kind -> entries [{Tag, Name, Aliases}] with lookups by Tag and by normalised name."""

    def __init__(self, kinds: dict):
        self.kinds = kinds
        self.by_tag = {k: {e["Tag"]: e for e in rows} for k, rows in kinds.items()}
        self.by_name = {}
        for k, rows in kinds.items():
            table = self.by_name.setdefault(k, {})
            for e in rows:
                for name in [e["Name"]] + e.get("Aliases", []):
                    table.setdefault(norm(name), e["Tag"])

    def match(self, kinds: list, value: str):
        """-> ("tag", Tag) | ("name", Tag) | (None, None)."""
        for k in kinds:
            if value in self.by_tag.get(k, {}):
                return "tag", value
        for k in kinds:
            tag = self.by_name.get(k, {}).get(norm(value))
            if tag:
                return "name", tag
        return None, None


def _parts(value: str, fmt: str):
    """Yields the names inside one cell, by format; returns problems for malformed cells."""
    if fmt == "single":
        return [value], []
    items = [p.strip() for p in value.split(",") if p.strip()]
    if fmt == "list":
        return items, []
    if fmt == "outcome":
        m = _OUTCOME.match(value)
        return ([m.group(2)], []) if m else ([], [f'"{value}" is not "<quantity> <item>"'])
    names, pending, problems = [], [], []
    for item in items:  # quantities
        m = _QUANTITY.match(item)
        if not m:
            pending.append(item)
            continue
        names += pending + [m.group(1)]
        pending = []
    if pending:
        problems.append(f'"{value}": no quantity after {", ".join(pending)}')
    return names, problems


def validate_rows(sheet: str, header: list, rows: list, reg: Registries, strict: bool) -> list:
    """rows = list of lists (data rows, header excluded). Returns problems:
    {"sheet", "cell", "value", "level": "error"|"warning", "message"}."""
    rules = SHEETS.get(sheet)
    if rules is None:
        return []
    problems = []

    def add(level, col, row, value, message):
        problems.append({"sheet": sheet, "cell": a1(col, row), "value": value, "level": level, "message": message})

    for col, title in enumerate(header):
        for prefix, kind in rules.get("header_kinds", {}).items():
            if title.startswith(prefix):
                tag = title[len(prefix):]
                if reg.match([kind], tag)[0] != "tag":
                    add(rules.get("header_level", "error"), col, 1, title, f"header: {tag} is not a {kind} Tag")
    skip = header.index(rules["skip_blank"]) if rules.get("skip_blank") in header else None
    type_col = header.index("Type") if "Type" in header else None
    for title, rule in rules["columns"].items():
        if title not in header:
            add("error", 0, 1, title, f'column "{title}" is missing')
            continue
        col = header.index(title)
        for r, row in enumerate(rows, start=2):
            cell = lambda c: (row[c] if c is not None and c < len(row) else "").strip()  # noqa: E731
            value = cell(col)
            if skip is not None and not cell(skip):
                continue
            if "when" in rule and cell(type_col) not in rule["when"]:
                continue
            if not value or value in rule.get("except", []) or (rule["kinds"] == ["Stat"] and value.lower() == "none"):
                continue
            names, bad = _parts(value, rule["format"])
            for message in bad:
                add("error", col, r, value, message)
            for name in names:
                how, tag = reg.match(rule["kinds"], name)
                kinds = "/".join(rule["kinds"])
                if how is None:
                    add("error", col, r, name, f'"{name}" is not a known {kinds}')
                elif how == "name" and rule["role"] == "ref":
                    add("error" if strict else "warning", col, r, name, f'display name: use the Tag {tag}')
    return problems


def _convert_cell(value: str, rule: dict, reg: Registries) -> str:
    """Rewrites the display names in one cell to Tags, keeping its format. Unknown names stay."""
    def tag_of(name):
        how, tag = reg.match(rule["kinds"], name.strip())
        return tag if how else name.strip()

    fmt = rule["format"]
    if fmt == "single":
        return tag_of(value)
    if fmt == "outcome":
        m = _OUTCOME.match(value)
        return f"{m.group(1)} {tag_of(m.group(2))}" if m else value
    items = [p.strip() for p in value.split(",") if p.strip()]
    if fmt == "list":
        return ", ".join(tag_of(p) for p in items)
    out = []  # quantities
    for item in items:
        m = _QUANTITY.match(item)
        out.append(f"{tag_of(m.group(1))} {m.group(2)}" if m else tag_of(item))
    return ", ".join(out)


def convert_rows(sheet: str, header: list, rows: list, reg: Registries) -> list:
    """The name->Tag converter (reference for the Apps Script's convertNamesToTags): rewrites every
    `ref` cell in place and returns the changes [{"cell", "old", "new"}]. Identity columns are kept."""
    rules = SHEETS.get(sheet)
    if rules is None:
        return []
    changes = []
    skip = header.index(rules["skip_blank"]) if rules.get("skip_blank") in header else None
    type_col = header.index("Type") if "Type" in header else None
    for title, rule in rules["columns"].items():
        if rule["role"] != "ref" or title not in header:
            continue
        col = header.index(title)
        for r, row in enumerate(rows, start=2):
            cell = lambda c: (row[c] if c is not None and c < len(row) else "").strip()  # noqa: E731
            value = cell(col)
            if not value or (skip is not None and not cell(skip)):
                continue
            if "when" in rule and cell(type_col) not in rule["when"]:
                continue
            if rule["kinds"] == ["Stat"] and value.lower() == "none":
                continue
            new = _convert_cell(value, rule, reg)
            if new != value:
                row[col] = new
                changes.append({"cell": a1(col, r), "old": value, "new": new})
    return changes
