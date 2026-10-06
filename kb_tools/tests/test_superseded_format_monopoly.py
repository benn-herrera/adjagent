"""Only `kb_migrate` knows the 0.9.0 format, as a mechanical assertion rather than a convention.

Every other module reads a KB in the current format, from disk or converted by `kb_migrate`, so none
spells the superseded forms: the comment-block opener `kb-frontmatter`, a `.jsonl` index name, or a
`.json` build-record name. The sweep reads each module's whole source, comments and docstrings
included — a prose mention of a superseded form is a second statement of it, and is what a reader
takes for current.
"""

from pathlib import Path

import kb_tools
from kb_tools import kb_index_lib, kb_load

_SWEPT_ROOT = Path(kb_tools.__file__).resolve().parent
_REPO_ROOT = _SWEPT_ROOT.parent
_UNSWEPT_PARTS = frozenset({"_vendor", "tests"})
_OWNER = "kb_tools/kb_migrate.py"

#: Every spelling of a superseded form, the index and record names built from the current inventories,
#: and the bare suffixes as a literal or a docstring spells them — `cadence.jsonl` and the like are
#: longer names, which never open a quote or a backtick on the dot.
_SUPERSEDED_SPELLINGS = (
    "kb-frontmatter",
    *(f"{name}.jsonl" for name in kb_index_lib.INDEX_FILES),
    *(f"{stem}.json" for stem in kb_load.RECORD_STEMS),
    *(f"{quote}{suffix}{quote}" for quote in "\"'`" for suffix in (".jsonl", ".json")),
)


def _package_modules() -> dict[str, str]:
    return {
        path.relative_to(_REPO_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(_SWEPT_ROOT.rglob("*.py"))
        if not _UNSWEPT_PARTS & set(path.relative_to(_SWEPT_ROOT).parts)
    }


def test_no_module_but_kb_migrate_spells_a_superseded_form() -> None:
    spelled = {
        (module, spelling)
        for module, source in _package_modules().items()
        if module != _OWNER
        for spelling in _SUPERSEDED_SPELLINGS
        if spelling in source
    }

    assert spelled == set()


def test_the_sweep_reads_the_owner_it_exempts() -> None:
    """Without this the sweep would pass over a package it had stopped reading."""
    source = _package_modules()[_OWNER]

    assert "kb-frontmatter" in source
