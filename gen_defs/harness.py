"""
Harness files: templates/harness/<name>.toml, one per supported harness.

    [harness.<key>]                 fills @!hrn.<key>!@ (`agents_file` module
    text = "..."                    docstring), exactly one string `text`

    [harness.agent-frontmatter]     how each agent frontmatter field renders
    [harness.tools]                 for this harness, and its tool vocabulary
                                    (`frontmatter` module docstring)

    [harness.model]                 optional, each key in it optional
    pattern = '...'                 `pattern` and `shape` come as a pair
    shape = "..."
    inherit-text = ""

The three structural tables sit under [harness] but are not values: they are
removed before the `hrn.` map is built, so @!hrn.tools!@ is an unknown harness
key like any other.

[harness.model] holds what the harness accepts as a `model:` value, and
nothing about which model a tier gets — the family's tier map and the
optional alias map decide that (`model_tuning` module docstring).
`pattern` is the check every tier's rendered text must fullmatch; `shape` is
the same rule in words with an example, the only form a refusal shows the
user, and is required wherever `pattern` is (and the reverse);
`inherit-text` is what a tier token renders when that text is `inherit`, which
may be empty text, eliding the `model:` line.
"""

import re
import tomllib
from pathlib import Path
from typing import NamedTuple

from .errors import InputError
from .frontmatter import FRONTMATTER_TABLE_KEY, TOOLS_TABLE_KEY, FrontmatterRules, load_frontmatter_rules
from .markers import IDENTIFIER, DynamicMap
from .paths import HARNESS_DIR, rel

HARNESS_TABLE = "harness"
HARNESS_SUFFIX = ".toml"
MODEL_TABLE_KEY = "model"
MODEL_PATTERN = "pattern"
MODEL_SHAPE = "shape"
MODEL_INHERIT_TEXT = "inherit-text"
# The [harness.<key>] tables that are structure rather than `hrn.` values.
STRUCTURAL_HARNESS_KEYS = (FRONTMATTER_TABLE_KEY, TOOLS_TABLE_KEY, MODEL_TABLE_KEY)


class HarnessModel(NamedTuple):
    """A harness's [harness.model] table; each field None where the harness
    declares nothing."""

    pattern: re.Pattern[str] | None
    shape: str | None
    inherit_text: str | None


class Harness(NamedTuple):
    """A loaded harness file: the `hrn.` values, its model shape, and its
    frontmatter rules."""

    values: DynamicMap
    model: HarnessModel
    frontmatter: FrontmatterRules


def load_harness(name: str, harness_dir: Path = HARNESS_DIR) -> Harness:
    """Load templates/harness/<name>.toml. An unknown name lists the harnesses
    there are."""
    path = harness_dir / f"{name}{HARNESS_SUFFIX}"
    if re.fullmatch(IDENTIFIER, name) is None or not path.is_file():
        available = ", ".join(sorted(p.stem for p in harness_dir.glob(f"*{HARNESS_SUFFIX}"))) or "(none)"
        raise InputError(f"unknown harness '{name}' — available: {available}")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise InputError(f"{rel(path)}: invalid TOML — {exc}") from exc
    stray = set(data) - {HARNESS_TABLE}
    if stray:
        raise InputError(f"{rel(path)}: unknown top-level table(s) {sorted(stray)} — only [{HARNESS_TABLE}.<key>]")
    table = dict(data.get(HARNESS_TABLE, {}))
    frontmatter = load_frontmatter_rules(
        table.pop(FRONTMATTER_TABLE_KEY, {}), table.pop(TOOLS_TABLE_KEY, {}), source=rel(path)
    )
    model = _load_model(table.pop(MODEL_TABLE_KEY, {}), where=f"{rel(path)}: [{HARNESS_TABLE}.{MODEL_TABLE_KEY}]")
    values: DynamicMap = {}
    for key, entry in table.items():
        where = f"{rel(path)}: [{HARNESS_TABLE}.{key}]"
        if re.fullmatch(IDENTIFIER, key) is None:
            raise InputError(f"{where}: '{key}' is not a harness key — it must match {IDENTIFIER}")
        if not isinstance(entry, dict) or set(entry) != {"text"} or not isinstance(entry["text"], str):
            raise InputError(
                f"{where}: must hold exactly one string 'text' "
                f"(every [{HARNESS_TABLE}.<key>] but {', '.join(STRUCTURAL_HARNESS_KEYS)})"
            )
        values[key] = entry["text"]
    return Harness(values, model, frontmatter)


def _load_model(table: object, *, where: str) -> HarnessModel:
    if not isinstance(table, dict):
        raise InputError(f"{where}: must be a table")
    unknown = sorted(set(table) - {MODEL_PATTERN, MODEL_SHAPE, MODEL_INHERIT_TEXT})
    if unknown:
        raise InputError(
            f"{where}: unknown key(s) {unknown} — it holds {MODEL_PATTERN}, {MODEL_SHAPE}, {MODEL_INHERIT_TEXT}"
        )
    for present, missing in ((MODEL_PATTERN, MODEL_SHAPE), (MODEL_SHAPE, MODEL_PATTERN)):
        if present in table and missing not in table:
            raise InputError(f"{where}: {present} is declared without {missing} — it needs both")
    shape = table.get(MODEL_SHAPE)
    if shape is not None and (not isinstance(shape, str) or not shape.strip()):
        raise InputError(f"{where}: {MODEL_SHAPE} must be a non-empty string")
    pattern = None
    if MODEL_PATTERN in table:
        if not isinstance(table[MODEL_PATTERN], str):
            raise InputError(f"{where}: {MODEL_PATTERN} must be a string")
        try:
            pattern = re.compile(table[MODEL_PATTERN])
        except re.error as exc:
            raise InputError(f"{where}: {MODEL_PATTERN} is not a valid regular expression — {exc}") from exc
    inherit_text = table.get(MODEL_INHERIT_TEXT)
    if inherit_text is not None and not isinstance(inherit_text, str):
        raise InputError(f"{where}: {MODEL_INHERIT_TEXT} must be a string")
    return HarnessModel(pattern, shape, inherit_text)
