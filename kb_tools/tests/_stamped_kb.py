"""A KB a test builds inline, in the current metadata format.

Every inline KB goes through here, so it is stamped the way a refreshed KB is:
``entry-point.md`` carries ``kb-format`` as its frontmatter's last key, and an
index stream is written where ``kb_load`` reads it, in the form it reads. An
unstamped KB belongs in a test only as a migration's input: a copy of the
format's goldens, or the document tree ``graph-init`` seeds.
"""

from collections.abc import Iterable, Mapping
from pathlib import Path

from kb_tools import kb_index_lib, kb_load, kb_migrate

_ENTRY_POINT = "entry-point.md"

# The entry point an inline KB gets when its files name none.
_DEFAULT_ENTRY_POINT = "# Knowledge Base\n"


def stamped(document: str) -> str:
    """``document`` as a stamped entry point: its frontmatter (or a new one) with ``kb-format`` last."""
    return kb_migrate.stamp(document)


def write_stamped_kb(kb_root: Path, files: Mapping[str, str] | None = None) -> Path:
    """``files`` (kb-root-relative) under ``kb_root``, the entry point stamped; a default one where none is given."""
    documents = {_ENTRY_POINT: _DEFAULT_ENTRY_POINT, **(files or {})}
    documents[_ENTRY_POINT] = stamped(documents[_ENTRY_POINT])
    for relative, text in documents.items():
        target = kb_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return kb_root


def write_index(kb_root: Path, name: str, records: Iterable[Mapping]) -> Path:
    """The index stream ``name`` holding ``records``, at the path ``kb_load`` reads it from."""
    path = kb_load.index_path(kb_root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(kb_index_lib.serialize_records([dict(record) for record in records]), encoding="utf-8")
    return path
