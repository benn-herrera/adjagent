"""Format conversion: a KB's metadata files from an older format version to the current one.

Text in, text out: `chain` takes the files as repository-relative slash paths (`kb-root/...` and
the build records beside it) and returns the current form's files plus the paths the conversion
made obsolete. No file I/O; every superseded form's parser lives here and nowhere else.

One step today, `0.9.0 → 1.0.0`, a port of kbase's `internal/migrate/from_0_9_0.go`: the
comment-block frontmatter moves to YAML frontmatter at the top of the document, a leaf's node
declarations become `experiment-nodes` / `support-nodes` lists, the JSON build records and the JSONL
index become YAML, and the entry point is stamped. The 0.9.0 grammar is read with Python's
whitespace — `str.strip`, `str.splitlines`, `\\s` — because that is how kb_tools wrote and read it.
"""

import json
import posixpath
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from kb_tools import kb_schema, kb_yaml
from kb_tools.kb_yaml import FlowList, Number

# Each step's versions are its own, fixed when it was written, not the current version.
_V0_9_0 = "0.9.0"
_V1_0_0 = "1.0.0"

# The converter's view of a KB's layout, repository-relative; kbase's converter states the same.
_ENTRY_POINT_PATH = f"{kb_schema.KB_DIRNAME}/{kb_schema.ENTRY_POINT_FILENAME}"
_INDEX_DIR = f"{kb_schema.KB_DIRNAME}/{kb_schema.INDEX_DIRNAME}"

# The 0.9.0 format's build records, frozen with that format: equal to `kb_load.RECORD_STEMS` today
# by coincidence, not derivation, since the current record set may grow without changing what a
# 0.9.0 KB held.
_RECORD_STEMS_0_9_0 = ("kb-build-node-pass", "kb-build-classification", "kb-build-unmarked")

_CURRENT_SUFFIX = ".yaml"
_RECORD_SUFFIX_0_9_0 = ".json"
_INDEX_SUFFIX_0_9_0 = ".jsonl"

#: Every repository-relative path a build record stood at under a superseded format.
SUPERSEDED_RECORD_PATHS: tuple[str, ...] = tuple(f"{stem}{_RECORD_SUFFIX_0_9_0}" for stem in _RECORD_STEMS_0_9_0)

_VERSION_PART_RE = re.compile(r"0|[1-9][0-9]*")

_COMMENT_BLOCK_RE = re.compile(r"<!--\s*kb-frontmatter\s*\n(.*?)\n[ \t]*-->", re.DOTALL)
_COMMENT_BLOCK_OPEN_RE = re.compile(r"<!--\s*kb-frontmatter\s*\n")
_BLOCK_BULLET_RE = re.compile(r"\s*-\s+(.*)")
_PAIR_SCORE_RE = re.compile(kb_schema.NUMBER_TOKEN_RE)
_CLAIM_ID = kb_schema.id_body("clm")
_STRENGTHENS_PAIR_RE = re.compile(rf"\s*(?:-\s*)?({_CLAIM_ID})\s*:\s*({kb_schema.NUMBER_TOKEN_RE})\s*")
_PENDING = re.escape(kb_schema.PENDING_LITERAL)
_SUPPORTS_PAIR_RE = re.compile(rf"\s*(?:-\s*)?({_CLAIM_ID})\s*:\s*({kb_schema.NUMBER_TOKEN_RE}|{_PENDING})\s*")


class MigrationError(ValueError):
    """A file that does not convert, or a version the chain cannot reach; names which."""


@dataclass(frozen=True)
class Converted:
    """The files in the target form, a renamed file under its new path only, and the obsolete paths."""

    files: dict[str, str]
    obsolete: tuple[str, ...]


def parse_version(version: str) -> tuple[int, int, int]:
    """A strict `major.minor.patch` version, no leading zeros; MigrationError otherwise."""
    parts = version.split(".")
    if len(parts) != 3 or not all(_VERSION_PART_RE.fullmatch(part) for part in parts):
        raise MigrationError(f"{version!r} is not a major.minor.patch version")
    major, minor, patch = (int(part) for part in parts)
    return major, minor, patch


def superseded_path(current: str) -> str | None:
    """The repository-relative path the file now at `current` stood at under the superseded format.

    None where the file kept its spelling: a document, or a build record the 0.9.0 format did not hold.
    """
    stem, suffix = posixpath.splitext(current)
    if suffix != _CURRENT_SUFFIX:
        return None
    if posixpath.dirname(current) == _INDEX_DIR:
        return stem + _INDEX_SUFFIX_0_9_0
    record = stem + _RECORD_SUFFIX_0_9_0
    return record if record in SUPERSEDED_RECORD_PATHS else None


def chain(from_version: str, to_version: str, files: Mapping[str, str]) -> Converted:
    """`files` converted from `from_version` to `to_version` through each step in version order.

    The obsolete paths are the union of every step's, sorted. A version no step leads on from, and a
    `from_version` newer than `to_version`, are a MigrationError naming it.
    """
    target = parse_version(to_version)
    current = parse_version(from_version)
    if current > target:
        raise MigrationError(f"{from_version} is newer than {to_version}, and nothing downgrades")
    converted = dict(files)
    obsolete: set[str] = set()
    version = from_version
    while current < target:
        step = next((s for s in _STEPS if s.from_version == version and parse_version(s.to_version) <= target), None)
        if step is None:
            raise MigrationError(f"no converter leads from {version} toward {to_version}")
        try:
            converted, gone = step.convert(converted)
        except MigrationError as error:
            raise MigrationError(f"migrate {step.from_version} → {step.to_version}: {error}") from error
        obsolete.update(gone)
        version = step.to_version
        current = parse_version(version)
    return Converted(files=converted, obsolete=tuple(sorted(obsolete)))


def superseded_stamp(text: str) -> str | None:
    """The `kb-format` an entry point in the 0.9.0 form declares in its comment block, if any."""
    match = _comment_block(text)
    if match is None:
        return None
    for field in _generic_fields(match.group(1).splitlines()):
        if field.key != kb_schema.FORMAT_KEY:
            continue
        value = field.value
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str) and value:
            return value
    return None


def stamp(document: str) -> str:
    """`document` in YAML frontmatter with `kb-format` at the current version as its last key.

    A document already opening with YAML frontmatter has it re-encoded with the stamp moved last; one
    with a 0.9.0 comment block is converted; one with neither gains a block holding the stamp alone.
    """
    return _document_yaml_frontmatter(document, stamp_version=kb_schema.FORMAT_VERSION)


def holds_superseded_frontmatter(text: str) -> bool:
    """Whether `text` carries a 0.9.0 comment block, which no current-format reader takes as frontmatter."""
    return _comment_block(text) is not None


def _comment_block(text: str) -> "re.Match[str] | None":
    """The first comment block, what `_COMMENT_BLOCK_RE.search` returns, in one pass.

    The lazy body under DOTALL makes `search` scan to the end of the text from every opener with no
    closer after it: measured at 1 600 openers and no closer, 4.5 s. If the first opener has no
    closer after it no later one has either, closers only lying further on, so the leftmost match is
    the one anchored at the first opener or there is none.
    """
    opener = _COMMENT_BLOCK_OPEN_RE.search(text)
    if opener is None:
        return None
    return _COMMENT_BLOCK_RE.match(text, opener.start())


# ---------------------------------------------------------------------------------------------
# 0.9.0 → 1.0.0


def _convert_0_9_0(files: Mapping[str, str]) -> tuple[dict[str, str], list[str]]:
    out: dict[str, str] = {}
    obsolete: list[str] = []
    for path in sorted(files):
        text = files[path]
        try:
            if path in SUPERSEDED_RECORD_PATHS:
                out[path.removesuffix(_RECORD_SUFFIX_0_9_0) + _CURRENT_SUFFIX] = _record_yaml(text)
                obsolete.append(path)
            elif posixpath.dirname(path) == _INDEX_DIR and path.endswith(_INDEX_SUFFIX_0_9_0):
                out[path.removesuffix(_INDEX_SUFFIX_0_9_0) + _CURRENT_SUFFIX] = _index_stream(text)
                obsolete.append(path)
            elif path.endswith(".md"):
                stamp_version = _V1_0_0 if path == _ENTRY_POINT_PATH else None
                out[path] = _document_yaml_frontmatter(text, stamp_version=stamp_version)
            elif path not in out:
                # Sorted, an old spelling precedes its new one, so the converted old form wins.
                out[path] = text
        except MigrationError as error:
            raise MigrationError(f"{path}: {error}") from error
    return out, obsolete


def _record_yaml(text: str) -> str:
    """A JSON build record as a YAML document, keys in their order and numbers as written."""
    try:
        record = json.loads(text, parse_float=Number, parse_int=Number, parse_constant=kb_yaml.refuse_json_constant)
    except ValueError as error:
        raise MigrationError(f"not a JSON record: {error}") from error
    if not isinstance(record, dict):
        raise MigrationError("a build record is a JSON object")
    return kb_yaml.dump(record)


def _index_stream(text: str) -> str:
    """A JSONL index as a YAML stream: per record, `--- ` and the record as a one-line JSON object.

    Split on `\\n` alone: a JSON string may hold a raw U+2028, which `splitlines` would break on.
    """
    lines: list[str] = []
    for number, line in enumerate(text.split("\n"), start=1):
        line = line.strip()
        if not line:
            continue
        if not line.startswith("{"):
            raise MigrationError(f"line {number}: a record is a JSON object")
        try:
            record = json.loads(line, parse_constant=kb_yaml.refuse_json_constant)
        except ValueError as error:
            raise MigrationError(f"line {number}: {error}") from error
        lines.append(kb_yaml.index_line(record))
    return "".join(lines)


def _document_yaml_frontmatter(text: str, *, stamp_version: str | None) -> str:
    """`text` with its comment block's fields moved into YAML frontmatter at the top.

    The block and its line break are removed and every other byte kept. A document already opening
    with YAML frontmatter is in the next form: returned unchanged, or re-encoded with the stamp. A
    document with neither is returned unchanged unless it is to be stamped. `stamp_version`, where
    given, is set as `kb-format`, the last key.
    """
    span = kb_yaml.find_frontmatter(text)
    if span is not None:
        if stamp_version is None:
            return text
        try:
            fields = kb_yaml.parse(text[span.body_start : span.body_end])
        except kb_yaml.KbYamlError as error:
            raise MigrationError(f"frontmatter: {error}") from error
        if not isinstance(fields, dict):
            raise MigrationError("frontmatter is not a mapping")
        return "---\n" + kb_yaml.dump(_with_stamp(fields, stamp_version)) + text[span.close_start :]
    match = _comment_block(text)
    if match is None and stamp_version is None:
        return text
    fields = {}
    rest = text
    if match is not None:
        fields = _block_fields(match.group(1))
        end = match.end()
        if text.startswith("\r\n", end):
            end += 2
        elif text.startswith("\n", end):
            end += 1
        rest = text[: match.start()] + text[end:]
    if stamp_version is not None:
        fields = _with_stamp(fields, stamp_version)
    return kb_yaml.frontmatter(kb_yaml.dump(fields).removesuffix("\n").split("\n")) + "\n" + rest


def _with_stamp(fields: dict, version: str) -> dict:
    """`fields` with `kb-format` at `version` as the last key."""
    out = {key: value for key, value in fields.items() if key != kb_schema.FORMAT_KEY}
    out[kb_schema.FORMAT_KEY] = version
    return out


@dataclass(frozen=True)
class _PlacedField:
    """One key and value of the converted block, at the body line it stands for."""

    line: int
    key: str
    value: object


def _generic_fields(lines: list[str]) -> list[_PlacedField]:
    """Every field of a block body as the 0.9.0 field reader took it, each at its key's line.

    A list written inline stays a flow list; a bullet list becomes a block list, a `key: value`
    bullet a one-key mapping whose numeric value stays a number.
    """
    out: list[_PlacedField] = []
    at = 0
    while at < len(lines):
        line = lines[at].rstrip()
        if not line or ":" not in line:
            at += 1
            continue
        end = _block_field_end(lines, at)
        key, _, value = line.partition(":")
        out.append(_PlacedField(at, key.strip(), _block_value(value.strip(), lines[at + 1 : end])))
        at = end
    return out


def _block_field_end(lines: list[str], start: int) -> int:
    """One past the last line of the field opening at `start`."""
    value = lines[start].rstrip().partition(":")[2].strip()
    at = start + 1
    if value.startswith("[") and not value.endswith("]"):
        while at < len(lines) and not lines[at].strip().endswith("]"):
            at += 1
        return min(at + 1, len(lines))
    if not value:
        while at < len(lines) and _BLOCK_BULLET_RE.fullmatch(lines[at]):
            at += 1
    return at


def _block_value(value: str, tail: list[str]) -> object:
    if not tail:
        return _block_scalar(value)
    if value.startswith("["):
        return _block_scalar(" ".join([value, *(line.strip() for line in tail)]))
    items: list = []
    for line in tail:
        item = _BLOCK_BULLET_RE.fullmatch(line).group(1).strip()
        key, is_pair, score = item.partition(":")
        if not is_pair:
            items.append(item)
            continue
        score = score.strip()
        items.append({key.strip(): Number(score) if _PAIR_SCORE_RE.fullmatch(score) else score})
    return items


def _block_scalar(value: str) -> object:
    """A one-line value typed as kb_tools typed it.

    `[…]` a flow list, a double-quoted string with its quotes stripped once, `true` or `false` a
    boolean, anything else the string as written.
    """
    if value.startswith("[") and value.endswith("]"):
        return FlowList(item.strip() for item in value[1:-1].split(",") if item.strip())
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value in ("true", "false"):
        return value == "true"
    return value


@dataclass(frozen=True)
class _NodeScan:
    """One kind of node declaration as the 0.9.0 node scan read it.

    An opener key starts a node, and the member key and the pair-list key — leading dashes trimmed —
    attach to the kind's latest node whatever stands between; a pair line, bullet optional, joins the
    pair list while the list is open, and any other key line closes it.
    """

    opener: str
    member: str | None
    pairs_key: str
    list_key: str
    pair_re: re.Pattern[str]

    def scan(self, lines: list[str]) -> tuple[list[dict] | None, int, set[int]]:
        """The kind's declarations as one list, the line the first opens on, every line taken."""
        taken: set[int] = set()
        decls: list[dict] = []
        first = 0
        in_pairs = False
        for at, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            pair = self.pair_re.fullmatch(line)
            if in_pairs and pair and decls:
                score = pair.group(2)
                value = score if score == kb_schema.PENDING_LITERAL else Number(score)
                decls[-1][self.pairs_key].append({pair.group(1): value})
                taken.add(at)
                continue
            head, has_colon, tail = stripped.partition(":")
            if not has_colon:
                continue
            key, value = head.strip().lstrip("- ").strip(), tail.strip()
            if key == self.pairs_key:
                in_pairs = True
                if decls:
                    decls[-1].setdefault(self.pairs_key, [])
                    taken.add(at)
                continue
            in_pairs = False
            if key == self.opener:
                if not decls:
                    first = at
                decls.append({key: value})
                taken.add(at)
            elif key == self.member and decls:
                decls[-1][key] = value
                taken.add(at)
        if not decls:
            return None, 0, taken
        nodes = [{key: value for key, value in decl.items() if value != []} for decl in decls]
        return nodes, first, taken


_NODE_SCANS = (
    _NodeScan(
        opener="exp-id",
        member="status",
        pairs_key="strengthens",
        list_key=kb_schema.EXPERIMENT_NODES_KEY,
        pair_re=_STRENGTHENS_PAIR_RE,
    ),
    _NodeScan(
        opener="sup-id",
        member=None,
        pairs_key="supports",
        list_key=kb_schema.SUPPORT_NODES_KEY,
        pair_re=_SUPPORTS_PAIR_RE,
    ),
)


def _block_fields(body: str) -> dict:
    """A comment block's fields in block order.

    Each kind's node declarations, read as the 0.9.0 node scan read them, become one list standing
    where the kind's first declaration stood; every other field is read as the 0.9.0 field reader
    read it, less the lines a node scan took.
    """
    lines = body.splitlines()
    placed: list[_PlacedField] = []
    taken: set[int] = set()
    for node_scan in _NODE_SCANS:
        nodes, first, scan_taken = node_scan.scan(lines)
        taken |= scan_taken
        if nodes is not None:
            placed.append(_PlacedField(first, node_scan.list_key, nodes))
    placed.extend(field for field in _generic_fields(lines) if field.line not in taken)
    placed.sort(key=lambda field: field.line)
    fields: dict = {}
    for field in placed:
        if field.key in fields:
            raise MigrationError(f"frontmatter key {field.key!r} repeats; a YAML mapping holds each key once")
        fields[field.key] = field.value
    return fields


@dataclass(frozen=True)
class _Step:
    from_version: str
    to_version: str
    convert: Callable[[Mapping[str, str]], tuple[dict[str, str], list[str]]]


_STEPS = (_Step(_V0_9_0, _V1_0_0, _convert_0_9_0),)
