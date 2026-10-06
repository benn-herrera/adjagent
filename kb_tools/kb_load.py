"""The KB's format version first; its files as the current format reads them; the one save that migrates.

`open_kb` reads `kb-format` from `kb-root/entry-point.md` before anything else and refuses a KB
newer than this toolchain reads. A KB stamped at the current major and minor version is read from
disk; an older one is read converted (`kb_migrate.chain`), each file in the form found, a renamed
file from its old spelling where that still stands. `land_migration` writes the conversion: every
covered file but the entry point, then the obsolete paths removed, then the stamped entry point
last — so an interrupted landing leaves the KB reading as its old version, and the next one
completes it.

Files are decoded UTF-8 with no newline translation, so a CRLF document keeps its bytes. This module
is also the one composer of index and build-record paths.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from kb_tools import kb_migrate, kb_schema, kb_util, kb_yaml
from kb_tools.kb_migrate import MigrationError
from kb_tools.kb_survey.manifest import write_text_atomic

#: The refusal classes: the stamp, and the KB root (no entry point).
CHECK_FORMAT = "kb-format"
CHECK_KB_ROOT = "kb-root"
#: The remedy for a KB newer than this toolchain.
UPDATE_REMEDY = "update kb_tools"

#: The build records beside `kb-root/`, by stem.
NODE_PASS_STEM = "kb-build-node-pass"
CLASSIFICATION_STEM = "kb-build-classification"
UNMARKED_STEM = "kb-build-unmarked"
RECORD_STEMS: tuple[str, ...] = (NODE_PASS_STEM, CLASSIFICATION_STEM, UNMARKED_STEM)

_YAML_SUFFIX = ".yaml"


class FormatRefusal(Exception):
    """The KB cannot be read by this toolchain: `check` names the class, `remedy` what fixes it."""

    def __init__(self, check: str, path: Path, detail: str, remedy: str = "") -> None:
        super().__init__(f"{check}: {path}: {detail}" + (f" — {remedy}" if remedy else ""))
        self.check = check
        self.path = path
        self.detail = detail
        self.remedy = remedy


@dataclass(frozen=True)
class KbFormat:
    """The version the KB is stamped at, and whether it is read from disk as the current format."""

    version: str
    current: bool


@dataclass(frozen=True)
class Landing:
    """What a landing wrote, in write order (the entry point last), and what it removed."""

    written: tuple[Path, ...]
    removed: tuple[Path, ...]


def index_path(kb_root: Path, name: str) -> Path:
    """The index stream `name` (`claims`, `depends-on`, …) in the current format."""
    return kb_root / kb_util.INDEX_DIRNAME / f"{name}{_YAML_SUFFIX}"


def record_path(repo_root: Path, stem: str) -> Path:
    """The build record `stem` (one of `RECORD_STEMS`) in the current format, beside `kb-root/`."""
    return repo_root / f"{stem}{_YAML_SUFFIX}"


def open_kb(kb_root: Path) -> KbFormat:
    """The KB's format version, read from the entry point before any other file.

    No entry point is a refusal naming `kb-root`, as is any file of the KB this module reads that is
    not UTF-8; a stamp that is not a `major.minor.patch` string, and a newer major or minor version,
    are refusals naming `kb-format`. An entry point whose
    frontmatter carries no stamp, or that opens with none, is `0.9.0` unless its comment block
    declares otherwise.
    """
    entry = kb_root / kb_schema.ENTRY_POINT_FILENAME
    try:
        text = _read_text(entry)
    except FileNotFoundError:
        raise FormatRefusal(CHECK_KB_ROOT, entry, f"{kb_root} has no {kb_schema.ENTRY_POINT_FILENAME}") from None
    version = _stamp(entry, text)
    try:
        have = kb_migrate.parse_version(version)
    except MigrationError:
        detail = (
            f"{kb_schema.ENTRY_POINT_FILENAME}'s {kb_schema.FORMAT_KEY} is {version!r}, "
            "not a major.minor.patch version"
        )
        raise FormatRefusal(CHECK_FORMAT, entry, detail) from None
    reads = kb_migrate.parse_version(kb_schema.FORMAT_VERSION)
    if have[:2] > reads[:2]:
        detail = f"the KB's metadata format is {version} and this kb_tools reads and writes {kb_schema.FORMAT_VERSION}"
        raise FormatRefusal(CHECK_FORMAT, entry, detail, UPDATE_REMEDY)
    return KbFormat(version=version, current=have[:2] == reads[:2])


def require_current(kb_root: Path) -> None:
    """`open_kb`, and an older KB refused as well, naming the refresh that migrates it.

    The gate of a command that writes into the KB, or that runs only over a KB refresh has
    already brought to the current format.
    """
    kb_format = open_kb(kb_root)
    if not kb_format.current:
        detail = f"the KB's metadata format is {kb_format.version} and this kb_tools writes {kb_schema.FORMAT_VERSION}"
        remedy = f"run `{kb_util.refresh_cmd(kb_root.parent)}`, which migrates the KB to {kb_schema.FORMAT_VERSION}"
        raise FormatRefusal(CHECK_FORMAT, kb_root / kb_schema.ENTRY_POINT_FILENAME, detail, remedy)


def read_document(kb_root: Path, rel: str, *, kb_format: KbFormat | None = None) -> str:
    """The document at `rel` (kb-root-relative, slash-separated) as the current format reads it.

    `kb_format` is `open_kb(kb_root)`'s answer where the caller already holds it; read here otherwise.
    """
    if kb_format is None:
        kb_format = open_kb(kb_root)
    text = _read_text(kb_root / rel)
    if kb_format.current:
        return text
    key = _repo_key(kb_root, kb_root / rel)
    return _converted(kb_format, {key: text}).files[key]


def read_index(
    kb_root: Path, name: str, *, kb_format: KbFormat | None = None
) -> tuple[list[dict], list[kb_yaml.IndexLineError]]:
    """The index stream `name`'s records, and a problem for each line that is not one.

    On an older KB the stream's superseded spelling is read converted where it stands, else the
    current one; it is converted line by line, so a line that does not convert is a problem at its
    own line number, as a bad line of the current form is. A missing file raises FileNotFoundError.
    `kb_format` is as `read_document` takes it.
    """
    if kb_format is None:
        kb_format = open_kb(kb_root)
    path = index_path(kb_root, name)
    superseded = _superseded(kb_root.parent, path)
    if kb_format.current or superseded is None or not superseded.is_file():
        return kb_yaml.parse_index(_read_text(path))
    old_key, new_key = _repo_key(kb_root, superseded), _repo_key(kb_root, path)
    records: list[dict] = []
    problems: list[kb_yaml.IndexLineError] = []
    for number, line in enumerate(_read_text(superseded).split("\n"), start=1):
        if not line.strip():
            continue
        try:
            converted = _converted(kb_format, {old_key: line}).files[new_key]
        except MigrationError as error:
            problems.append(kb_yaml.IndexLineError(number, f"does not convert to {kb_schema.FORMAT_VERSION}: {error}"))
            continue
        records += kb_yaml.parse_index(converted)[0]
    return records, problems


def read_record(repo_root: Path, stem: str) -> object:
    """The build record `stem`'s values.

    On an older KB the record's superseded spelling is read converted where it stands, else the
    current one. A record standing in neither spelling raises FileNotFoundError before the stamp
    is read, so a repository whose KB does not exist yet holds no record rather than refusing.
    """
    path = record_path(repo_root, stem)
    superseded = _superseded(repo_root, path)
    if not path.is_file() and (superseded is None or not superseded.is_file()):
        raise FileNotFoundError(f"no build record {path.name} stands at {repo_root}")
    kb_root = kb_util.kb_root(repo_root)
    kb_format = open_kb(kb_root)
    return kb_yaml.parse(_read_current_form(kb_root, kb_format, path, superseded))


def land_migration(kb_root: Path) -> Landing:
    """Write an older KB in the current format, the stamped entry point last.

    A KB at exactly the current version is left alone; one at the current major and minor with
    another patch has its stamp rewritten. Otherwise every covered file is converted; each whose
    text differs from disk is written, the entry point excepted; each obsolete path still standing
    that the converted KB does not hold is removed; then the entry point is written. A failure
    before that last write leaves the entry point unstamped, so the KB still reads as its old
    version and the next landing completes it.
    """
    kb_format = open_kb(kb_root)
    entry = kb_root / kb_schema.ENTRY_POINT_FILENAME
    if kb_format.current:
        if kb_format.version == kb_schema.FORMAT_VERSION:
            return Landing(written=(), removed=())
        write_text_atomic(kb_migrate.stamp(_read_text(entry)), entry)
        return Landing(written=(entry,), removed=())
    repo_root = kb_root.parent
    on_disk = _covered_files(kb_root)
    converted = _converted(kb_format, on_disk)
    entry_key = _repo_key(kb_root, entry)
    written: list[Path] = []
    for key in sorted(converted.files):
        if key != entry_key and on_disk.get(key) != converted.files[key]:
            path = repo_root / key
            write_text_atomic(converted.files[key], path)
            written.append(path)
    removed: list[Path] = []
    for key in converted.obsolete:
        path = repo_root / key
        if key not in converted.files and path.is_file():
            path.unlink()
            removed.append(path)
    if on_disk.get(entry_key) != converted.files[entry_key]:
        write_text_atomic(converted.files[entry_key], entry)
        written.append(entry)
    return Landing(written=tuple(written), removed=tuple(removed))


def _stamp(entry: Path, text: str) -> str:
    span = kb_yaml.find_frontmatter(text)
    if span is None:
        return kb_migrate.superseded_stamp(text) or kb_schema.UNSTAMPED_FORMAT_VERSION
    try:
        fields = kb_yaml.parse(text[span.body_start : span.body_end])
    except kb_yaml.KbYamlError as error:
        raise FormatRefusal(CHECK_FORMAT, entry, f"frontmatter {error}") from None
    if not isinstance(fields, dict):
        raise FormatRefusal(CHECK_FORMAT, entry, "frontmatter is not a mapping")
    if kb_schema.FORMAT_KEY not in fields:
        return kb_schema.UNSTAMPED_FORMAT_VERSION
    stamp = fields[kb_schema.FORMAT_KEY]
    if not isinstance(stamp, str) or not stamp:
        raise FormatRefusal(
            CHECK_FORMAT, entry, f"{kb_schema.FORMAT_KEY} in {kb_schema.ENTRY_POINT_FILENAME} is not a version"
        )
    return stamp


def _converted(kb_format: KbFormat, files: dict[str, str]) -> kb_migrate.Converted:
    major, minor, _ = kb_migrate.parse_version(kb_format.version)
    return kb_migrate.chain(f"{major}.{minor}.0", kb_schema.FORMAT_VERSION, files)


def _superseded(repo_root: Path, path: Path) -> Path | None:
    """Where the file now at `path` stood under the superseded format; None where it kept its spelling."""
    rel = kb_migrate.superseded_path(path.relative_to(repo_root).as_posix())
    return None if rel is None else repo_root / rel


def _read_current_form(kb_root: Path, kb_format: KbFormat, path: Path, superseded: Path | None) -> str:
    """`path`'s text in the current form: from its superseded spelling, converted, where that stands."""
    if kb_format.current or superseded is None or not superseded.is_file():
        return _read_text(path)
    old_key, new_key = _repo_key(kb_root, superseded), _repo_key(kb_root, path)
    return _converted(kb_format, {old_key: _read_text(superseded)}).files[new_key]


def _covered_files(kb_root: Path) -> dict[str, str]:
    """Every file a format covers, by repository-relative slash path.

    Each regular `.md` under `kb_root`, the index in either spelling, and the build records beside
    `kb_root` in either spelling.
    """
    repo_root = kb_root.parent
    index_dir = kb_root / kb_util.INDEX_DIRNAME
    paths: list[Path] = []
    for directory, _, names in os.walk(kb_root):
        for name in names:
            path = Path(directory, name)
            current = path.with_suffix(_YAML_SUFFIX)
            in_index = path.parent == index_dir and path in (current, _superseded(repo_root, current))
            if (path.suffix == ".md" or in_index) and path.is_file() and not path.is_symlink():
                paths.append(path)
    records = [record_path(repo_root, stem) for stem in RECORD_STEMS]
    records += [repo_root / rel for rel in kb_migrate.SUPERSEDED_RECORD_PATHS]
    paths += [path for path in records if path.is_file()]
    return {_repo_key(kb_root, path): _read_text(path) for path in paths}


def _repo_key(kb_root: Path, path: Path) -> str:
    return path.relative_to(kb_root.parent).as_posix()


def _read_text(path: Path) -> str:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return handle.read()
    except UnicodeDecodeError as error:
        raise FormatRefusal(CHECK_KB_ROOT, path, f"not UTF-8 ({error.reason} at byte {error.start})") from None
