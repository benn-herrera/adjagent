"""`python3 -m adjagent install ROOT`: every definition rendered into ROOT's agents/, commands/ and
skills/, the shipped packages copied beside them under adj-tools/, and — when the install includes kb
— the kb-tools package beside the consumer's `kbase` MCP entry and its runner include line.
Overwrites without ceremony: the consumer's git is the record of what an install changed."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple, cast

from adjagent.context import Render
from adjagent.errors import InputError
from adjagent.harness import Harness
from adjagent.loading import load
from adjagent.render import GENERATED_MARK, GENERATED_NOTICE, render_all, write_renders

REPO_ROOT = Path(__file__).resolve().parent.parent
# (source directory in this repository, destination below ROOT) for the packages every install ships.
# A destination is a consumer contract — definition bodies and the installed runner line name it —
# so it is stated, never derived.
SHIPPED_PACKAGES = (("liaison_tools", "adj-tools/liaison_tools"),)
# The kb toolchain's package: the runner snippets from this repository beside a `kbase` executable,
# shipped to one destination only when the install includes kb.
KB_TOOLS_PACKAGE = "adj-tools/kb-tools"
KB_TOOLS_SOURCE = "kb-tools"
RUNNER_SNIPPETS = "runner-snippets"
KB_TOOLS_SNIPPETS = f"{KB_TOOLS_PACKAGE}/{RUNNER_SNIPPETS}"
KBASE_BASENAME = "kbase.exe" if os.name == "nt" else "kbase"
# The installed executable's Git LFS pattern, matched at any depth so either harness directory and
# the Windows name are covered.
_LFS_PATTERN = "**/adj-tools/kb-tools/kbase*"
_LFS_ADVICE = f"""  If this project tracks its installed agent tree, put it under Git LFS before committing:

      git lfs track '{_LFS_PATTERN}'

  If it was committed already, rewrite that history once with:

      git lfs migrate import --include='{_LFS_PATTERN}'

  A project that leaves the installed tree untracked needs nothing."""
_LFS_UNTRACKED = f"  NOTE: the `kbase` executable is a binary of several MB and is not under Git LFS.\n\n{_LFS_ADVICE}"
# Said of whichever `kbase` the installed tree holds, not of one this run wrote: the sticky install
# refreshes the snippets and leaves the executable an earlier run put there.
_LFS_UNKNOWN = (
    f"  NOTE: the installed `kbase` executable is a binary of several MB, and git cannot tell whether "
    f"it is under Git LFS.\n\n{_LFS_ADVICE}"
)
# The pre-1.0 underscore destination: the one legacy tree whose removal a run that excluded kb reports
# with advice, so it is named for that message as well as being the first LEGACY_KB_DIRS entry.
LEGACY_KB_TOOLS = "agents/kb_tools"
# The hyphenated destination the kb-tools package moved out of.
LEGACY_KB_TOOLS_PACKAGE = "agents/kb-tools"
# Every tree the kb toolchain has been installed into: the pre-1.0 underscore helper tree, then the
# hyphenated destination it moved to. Each is removed on every install whatever this one installs, and
# each is a snippets path an installed include line may name.
LEGACY_KB_DIRS = (LEGACY_KB_TOOLS, LEGACY_KB_TOOLS_PACKAGE)
# Every tree an earlier version installed that this one removes, whatever it installs: the kb trees,
# and the liaison_tools package's old home under a definition surface.
LEGACY_TREES = (*LEGACY_KB_DIRS, "agents/liaison_tools")
LEGACY_KB_TOOLS_MESSAGE = "legacy kb_tools removed. if you are using kb functionality install using `install-with-kb`"
# The snippets paths an installed runner include line may name: the current destination, then that
# path below each legacy tree.
_SNIPPET_PATHS = (KB_TOOLS_SNIPPETS, *(f"{directory}/{RUNNER_SNIPPETS}" for directory in LEGACY_KB_DIRS))
# The `kb-` definition names and `kbase` — the skill, whose name is also its directory. This repository
# produces them only for an install that includes the kb toolchain, so a run without kb neither writes
# them nor keeps the ones it finds.
NOT_BY_DEFAULT = re.compile(r"^(kb-|kbase$)")
# Runner files probed at the project root, in priority order: any justfile variant selects `just`,
# else any make variant selects `make`.
_JUSTFILE_NAMES = ("justfile", "Justfile", ".justfile")
_MAKEFILE_NAMES = ("Makefile", "makefile", "GNUmakefile")
# Never shipped, matched at any depth: test suites and caches, safety copies, and this repository's
# own project documents. README.md is absent on purpose: a package that grows one ships it.
EXCLUDED_DIRS = frozenset({"tests", "__pycache__", ".pytest_cache"})
EXCLUDED_NAMES = frozenset(
    {".DS_Store", "SPEC.md", "ARCHITECTURE.md", "CONVENTIONS.md", "THESIS.md", "ROADMAP.md", "AGENTS.md", "CLAUDE.md"}
)
EXCLUDED_SUFFIX = ".bak"
# Copied files whose type takes a `#` comment carry the one-line installed banner; every other file
# is copied byte-verbatim.
STAMPED_SUFFIXES = frozenset({".py", ".sh", ".toml", ".mk", ".just"})
SURFACES = ("agents", "commands", "skills")
# The generated-banner prefixes, built from the mark `render` writes above the payload, and the module
# paths a payload may name: the current `adjagent/definitions/<module>.py`, and the pre-1.0
# `templates/...` template a definition was rendered from. A file opening with one of these is one
# this repository wrote; the bare mark followed by anything else is somebody else's file.
_GENERATED = f"# {GENERATED_MARK}".encode("utf-8")
_COMMENT_GENERATED = f"<!-- {GENERATED_MARK}".encode("utf-8")
_PAYLOAD_PATHS = (b"adjagent/", b"templates/")


def _shipped(relative: Path) -> bool:
    """A file the shipped vocabulary covers, matched at any depth: not a test suite or cache, not a
    safety copy, not one of this repository's own project documents."""
    return not (
        EXCLUDED_DIRS.intersection(relative.parts[:-1])
        or relative.name in EXCLUDED_NAMES
        or relative.suffix == EXCLUDED_SUFFIX
    )


def excluded(name: str) -> bool:
    """A definition name `NOT_BY_DEFAULT` covers: a `kb-` definition or the `kbase` skill. This
    repository produces such a name only for an install that includes the kb toolchain."""
    return NOT_BY_DEFAULT.match(name) is not None


def package_copies(root: Path, *, kb_included: bool) -> list[tuple[Path, Path]]:
    """(source file, target under `root`) for every file the shipped packages deliver: the always-
    shipped table, and — when kb is included — the kb-tools runner snippets, which land under that
    package's destination. The `kbase` executable is not here: the install writes it from the source
    `--kbase-dist` names, or leaves the one already installed alone."""
    always = [
        (source, root / destination / source.relative_to(REPO_ROOT / package))
        for package, destination in SHIPPED_PACKAGES
        for source in sorted((REPO_ROOT / package).rglob("*"))
        if source.is_file() and _shipped(source.relative_to(REPO_ROOT / package))
    ]
    if not kb_included:
        return always
    snippets = REPO_ROOT / KB_TOOLS_SOURCE / RUNNER_SNIPPETS
    return always + [
        (source, root / KB_TOOLS_PACKAGE / RUNNER_SNIPPETS / source.relative_to(snippets))
        for source in sorted(snippets.rglob("*"))
        if source.is_file() and _shipped(source.relative_to(snippets))
    ]


def stamped(data: bytes, *, origin: str) -> bytes:
    """`data` with the one-line installed banner on top, or below its shebang line."""
    banner = f"# !INSTALLED! from {origin} — {GENERATED_NOTICE}\n".encode("utf-8")
    if not data.startswith(b"#!"):
        return banner + data
    shebang, _, rest = data.partition(b"\n")
    return shebang + b"\n" + banner + rest


def _refuse_root(root: Path) -> None:
    """Refuse a root that is not a directory, that is this repository, or that sits inside a shipped
    package's source — installing there writes the product into the tree a later install reads from."""
    if not root.is_dir():
        raise InputError(f"install root '{root}' is not an existing directory")
    resolved = root.resolve()
    sources = [REPO_ROOT / package for package, _ in SHIPPED_PACKAGES] + [REPO_ROOT / KB_TOOLS_SOURCE]
    if resolved == REPO_ROOT or any(resolved.is_relative_to(source) for source in sources):
        raise InputError(
            f"install root '{root}' is this repository or inside a package source it copies from — "
            "install into the project that consumes it"
        )


def _bannered(line: bytes, prefix: bytes) -> bool:
    """Whether `line` opens with `prefix` and then a payload naming a module path this repository
    writes — not merely the mark, which any hand-written comment can carry."""
    return line.startswith(prefix) and line[len(prefix) :].startswith(_PAYLOAD_PATHS)


def _is_ours(path: Path) -> bool:
    """A generated file, by the carrier it opens with: an HTML comment on line 1 — how a skill's supporting
    file holds its banner, having no frontmatter — or a frontmatter block whose banner sits on line 2 in
    1.0, line 3 pre-1.0. A file that cannot be read is not ours."""
    try:
        with path.open("rb") as handle:
            head = [handle.readline() for _ in range(3)]
    except OSError:
        return False
    return _bannered(head[0], _COMMENT_GENERATED) or (
        head[0].rstrip() == b"---" and any(_bannered(line, _GENERATED) for line in head[1:])
    )


def prune(root: Path, *, keep: set[Path]) -> list[Path]:
    """Remove every regular file under ROOT's surfaces that is not in `keep`, would ship, and is ours;
    then each directory that leaves empty, up to its surface.

    No shipped package lands inside a surface — the destinations sit beside them, under `adj-tools/` —
    so every file under a surface is either ours or untouched, and no destination is carved out. The
    would-ship vocabulary is name-based and covers `kb-` names and `kbase`, so a kb definition this
    run did not write — an install without kb — is stale and removed, while one the run wrote is in
    `keep`."""
    stale = [
        path
        for surface in SURFACES
        for path in sorted((root / surface).rglob("*"))
        if path not in keep
        and path.is_file()
        and not path.is_symlink()
        and _shipped(path.relative_to(root))
        and _is_ours(path)
    ]
    for path in stale:
        path.unlink()
    for path in stale:
        parent = path.parent
        while parent.parent != root and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    return stale


def _runs(path: Path) -> bool:
    """Whether `path` is a regular file this user can execute."""
    return path.is_file() and os.access(path, os.X_OK)


def _executable_in(directory: Path) -> Path | None:
    """The `kbase` executable under `directory`, under either platform's name, when it can run."""
    return next(
        (directory / name for name in ("kbase", "kbase.exe") if _runs(directory / name)),
        None,
    )


def _kbase_source(root: Path, kbase_dist: Path | None) -> tuple[Path, bool]:
    """(the `kbase` executable to install, whether it is a file to copy to the destination) for an
    install that includes kb. A `--kbase-dist` must name an existing executable carrying the installed
    basename, and is copied to the kb-tools destination; with no flag, the executable already installed
    there is the source and is left where it stands, while a file there that cannot run is no source and
    the legacy lookup follows. An executable an earlier version installed under a legacy tree, under
    either platform's name, is copied the same way, so the first install after the destination moved
    carries it across. None existing is refused."""
    installed = root / KB_TOOLS_PACKAGE / KBASE_BASENAME
    if kbase_dist is not None:
        if kbase_dist.name != KBASE_BASENAME or not _runs(kbase_dist):
            raise InputError(
                f"--kbase-dist '{kbase_dist}' is not an executable named '{KBASE_BASENAME}' — the MCP "
                "entry registers that name, so a source under any other one installs nothing runnable"
            )
        return kbase_dist, True
    if _runs(installed):
        return installed, False
    for relative in LEGACY_KB_DIRS:
        legacy = _executable_in(root / relative)
        if legacy is not None:
            return legacy, True
    state = "exists but is not an executable file" if installed.exists() else "does not exist"
    raise InputError(
        f"kb is included but no kbase executable is available: '{installed}' {state}, no "
        "legacy tree holds one, and no --kbase-dist was passed — pass --kbase-dist=<path>, or "
        "install kb first"
    )


def _kbase_copy(root: Path, source: Path) -> tuple[Path, bytes]:
    """(the executable to copy, its bytes) for a source this run installs at the kb-tools destination.
    The bytes are read here, before the first write, because a source inside a destination this run
    replaces whole would be deleted before it could be read; such a source is refused instead."""
    replaced = [root / destination for _, destination in SHIPPED_PACKAGES] + [root / KB_TOOLS_PACKAGE]
    resolved = source.resolve()
    for destination in replaced:
        if resolved.is_relative_to(destination.resolve()):
            raise InputError(
                f"the kbase source '{source}' is inside '{destination}', which this install replaces — "
                "pass a source outside the install root"
            )
    try:
        return source, source.read_bytes()
    except OSError as exc:
        raise InputError(f"the kbase source '{source}' cannot be read: {exc}") from exc


def _refuse_non_object(data: dict, *, container: tuple[str, ...]) -> None:
    """Refuse a key on `container`'s path that holds something other than an object: it cannot nest the
    entry."""
    for key in container[:-1]:
        child = data.get(key)
        if child is None:
            return
        if not isinstance(child, dict):
            raise InputError(f"MCP settings nests a non-object under '{key}' — cannot register the kbase server")
        data = child


def _mcp_entry_at(data: dict, *, container: tuple[str, ...], entry: dict) -> dict:
    """`data` with `entry` at `container`'s path, every unrelated key kept. A key on that path holding
    something other than an object cannot nest the entry and is refused."""
    _refuse_non_object(data, container=container)
    nested = data
    for key in container[:-1]:
        nested = nested.setdefault(key, {})
    nested[container[-1]] = entry
    return data


# The splice `mcp_merge` edits an existing settings file with. A file the consumer already has is
# theirs, so the entry is placed in the text itself rather than by reserializing a parse of it: key
# order, indentation, line endings and every other value come back byte for byte. The scanner below
# reads just enough structure to delimit that one slot, and refuses rather than guesses.


class _Unsafe(Exception):
    """A placement the splice will not guess at: a level naming the key it must touch twice, or a text
    it cannot delimit."""


class _Member(NamedTuple):
    """One member of a JSON object: its key, where the key's token starts, and its value's span."""

    key: str
    key_start: int
    value_start: int
    value_end: int


class _Object(NamedTuple):
    """A JSON object: where its braces sit and the members between them."""

    start: int
    end: int
    members: tuple[_Member, ...]


def _at(text: str, index: int) -> str:
    """The character at `index`; running off the end is a text the splice will not delimit."""
    if index >= len(text):
        raise _Unsafe("text ends inside a value")
    return text[index]


def _skip_ws(text: str, index: int) -> int:
    """The first index at or after `index` holding a non-whitespace character."""
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    return index


def _string_end(text: str, index: int) -> int:
    """The index just past the string opening at `index`: escapes stepped over whole, so a quote or
    brace inside the string is never read as structure."""
    index += 1
    while True:
        char = _at(text, index)
        if char == "\\":
            index += 2
        elif char == '"':
            return index + 1
        else:
            index += 1


def _value_end(text: str, index: int) -> int:
    """The index just past the JSON value opening at `index`."""
    char = _at(text, index)
    if char == '"':
        return _string_end(text, index)
    if char == "{":
        return _object(text, index).end
    if char == "[":
        index = _skip_ws(text, index + 1)
        while _at(text, index) != "]":
            index = _skip_ws(text, _value_end(text, index))
            if _at(text, index) == ",":
                index = _skip_ws(text, index + 1)
            elif _at(text, index) != "]":
                raise _Unsafe("an array element with no separator")
        return index + 1
    while index < len(text) and text[index] not in ",}] \t\r\n":
        index += 1
    return index


def _object(text: str, index: int) -> _Object:
    """The object whose opening brace is at `index`: its members and the span it covers. A key appearing
    twice is read as it stands; `_member` is what refuses it, at the level the splice chooses on."""
    members: list[_Member] = []
    cursor = _skip_ws(text, index + 1)
    while _at(text, cursor) != "}":
        key_end = _string_end(text, cursor)
        value_start = _skip_ws(text, key_end)
        if _at(text, value_start) != ":":
            raise _Unsafe("a member with no colon")
        value_start = _skip_ws(text, value_start + 1)
        value_end = _value_end(text, value_start)
        members.append(_Member(json.loads(text[cursor:key_end]), cursor, value_start, value_end))
        cursor = _skip_ws(text, value_end)
        if _at(text, cursor) == ",":
            cursor = _skip_ws(text, cursor + 1)
        elif _at(text, cursor) != "}":
            raise _Unsafe("a member with no separator")
    return _Object(index, cursor + 1, tuple(members))


def _member(members: tuple[_Member, ...], key: str) -> _Member | None:
    """The member named `key`, or None when the object has none. A level naming it twice does not say
    which one is meant, so it is refused."""
    found = [member for member in members if member.key == key]
    if len(found) > 1:
        raise _Unsafe(f"'{key}' twice on one level")
    return found[0] if found else None


def _line_indent(text: str, index: int) -> str | None:
    """The whitespace from the start of `index`'s line up to `index` — the indent a key or brace takes
    there; None when anything other than whitespace precedes it on that line."""
    prefix = text[text.rfind("\n", 0, index) + 1 : index]
    return prefix if not prefix.strip(" \t") else None


def _indent_unit(text: str, root: _Object) -> str | None:
    """The step from an object's closing-brace indent to its members' indent, read from the file's first
    object that states one; None when it writes none (a file on one line, or flat)."""
    obj = root
    while True:
        close = _line_indent(text, obj.end - 1)
        if obj.members and close is not None:
            member = _line_indent(text, obj.members[0].key_start)
            if member is not None and member.startswith(close):
                return member[len(close) :] or None
        nested = next((member for member in obj.members if _at(text, member.value_start) == "{"), None)
        if nested is None:
            return None
        obj = _object(text, nested.value_start)


def _member_indent(text: str, obj: _Object, unit: str | None) -> str | None:
    """The indent a member added to `obj` takes: its last sibling's, else one `unit` in from the
    object's closing brace; None where the file writes no such line."""
    if obj.members:
        return _line_indent(text, obj.members[-1].key_start)
    close = _line_indent(text, obj.end - 1)
    return None if close is None or unit is None else close + unit


def _value_text(value: object, *, indent: str | None, unit: str | None, newline: str) -> str:
    """`value` as JSON: inline when `indent` or `unit` is None, else a level per line, the first line
    where the caller puts it and every line after it at `indent` plus the depth it already carries."""
    if indent is None or unit is None:
        return json.dumps(value, separators=(",", ":"))
    lines = json.dumps(value, indent=unit).split("\n")
    return newline.join([lines[0], *(indent + line for line in lines[1:])])


def _with_member(text: str, *, obj: _Object, key: str, value: object, unit: str | None, newline: str) -> str:
    """`text` with `key` and `value` a member of `obj` — after its last member, or alone in an empty
    object — on a line at its siblings' indent, or inline where the file writes no such line."""
    indent = _member_indent(text, obj, unit)
    member = f"{json.dumps(key)}: {_value_text(value, indent=indent, unit=unit, newline=newline)}"
    if obj.members:
        at = obj.members[-1].value_end
        if indent is None:
            return f"{text[:at]},{member}{text[at:]}"
        return f"{text[:at]},{newline}{indent}{member}{text[at:]}"
    close = _line_indent(text, obj.end - 1)
    interior = obj.start + 1
    if indent is None or close is None:
        return f"{text[:interior]}{member}{text[obj.end - 1 :]}"
    return f"{text[:interior]}{newline}{indent}{member}{newline}{close}{text[obj.end - 1 :]}"


def _splice(text: str, *, container: tuple[str, ...], entry: dict) -> str | None:
    """`text` — plain JSON the caller has parsed — with `entry` at `container`'s path, every byte
    outside that slot kept. None when the placement cannot be made with certainty: a level naming the
    key the splice must pass through twice, or a text this scanner cannot delimit."""
    try:
        start = _skip_ws(text, 0)
        if _at(text, start) != "{":
            raise _Unsafe("a document whose root is not an object")
        root = _object(text, start)
        unit = _indent_unit(text, root)
        newline = "\r\n" if "\r\n" in text else "\n"
        obj = root
        for depth, key in enumerate(container[:-1]):
            member = _member(obj.members, key)
            if member is None:
                # The container is absent from here down: the whole chain goes in as one member.
                value: object = {container[-1]: entry}
                for name in reversed(container[depth + 1 : -1]):
                    value = {name: value}
                return _with_member(text, obj=obj, key=key, value=value, unit=unit, newline=newline)
            if _at(text, member.value_start) != "{":
                raise _Unsafe(f"'{key}' is not an object")
            obj = _object(text, member.value_start)
        member = _member(obj.members, container[-1])
        if member is None:
            return _with_member(text, obj=obj, key=container[-1], value=entry, unit=unit, newline=newline)
        indent = _line_indent(text, member.key_start)
        value_text = _value_text(entry, indent=indent, unit=unit, newline=newline)
        return f"{text[: member.value_start]}{value_text}{text[member.value_end :]}"
    except _Unsafe:
        return None


def mcp_merge(project: Path, *, harness: Harness, command: str, kb_root: str) -> None:
    """Register the `kbase` server in `harness`'s project settings file under `project` — also the
    project root the entry is built against, so a command inside it is named relative to it: the first
    discovered alternative, else the canonical path — created when no file the contract names exists.
    The entry lands at the contract's container path.

    An existing file is edited, never reserialized: the entry's own slot is spliced into the text as it
    stands, so every other byte — other entries, key order, indentation, line endings, number and
    string spelling — comes back exactly as it was found. A file that is not plain JSON (JSONC comments
    a rewrite would destroy), one naming a key the entry must pass through twice, and one the splice
    cannot delimit are each reported and left untouched, with the entry printed for the operator to
    merge by hand."""
    entry, container = harness.mcp.entry(command=command, kb_root=kb_root, project_root=project)
    canonical = project / harness.mcp.canonical
    candidates = [project / alternative for alternative in harness.mcp.alternatives] + [canonical]
    target = next((path for path in candidates if path.is_file()), canonical)
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        fresh = json.dumps(_mcp_entry_at({}, container=container, entry=entry), indent=2) + "\n"
        target.write_text(fresh, encoding="utf-8")
        print(f"wrote {target} with the kbase MCP entry")
        return
    # newline="" on both sides: the file's own line endings are the consumer's, and a CRLF file
    # translated on the way in or out would be rewritten without the merge touching it.
    text = _utf8_text(target)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    # A text json.loads rejects is a JSONC comment carrier, or otherwise not a plain object; a splice
    # would destroy what it cannot read, so both are left to the operator.
    if not isinstance(data, dict):
        print(f"{target} carries JSONC comments — left untouched; merge this entry by hand: {json.dumps(entry)}")
        return
    _refuse_non_object(data, container=container)
    spliced = _splice(text, container=container, entry=entry)
    if spliced is None:
        print(f"{target} could not be edited safely — left untouched; merge this entry by hand: {json.dumps(entry)}")
        return
    target.write_text(spliced, encoding="utf-8", newline="")
    print(f"registered the kbase MCP entry in {target}")


def _runner_file(project: Path) -> tuple[str, Path] | None:
    """(runner, file) probed at the project root: any justfile variant selects `just`, else any make
    variant selects `make`."""
    for runner, names in (("just", _JUSTFILE_NAMES), ("make", _MAKEFILE_NAMES)):
        for name in names:
            if (project / name).is_file():
                return runner, project / name
    return None


def _utf8_text(path: Path) -> str:
    """`path`'s text, read with no newline translation so a rewrite keeps each line's own ending. A
    file that cannot be read or decoded is refused, naming it."""
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return handle.read()
    except (OSError, UnicodeError) as exc:
        raise InputError(f"'{path}' is not readable UTF-8 text: {exc}") from exc


def _check_runner(project: Path) -> None:
    """Read `project`'s runner file before an install's first write: an unreadable or undecodable file is
    refused there, not raised out of the write phase with packages and renders already landed."""
    found = _runner_file(project)
    if found is not None:
        _utf8_text(found[1])


def kb_include_line(*, runner: str, harness_relpath: str) -> str:
    """The canonical KB include line for `runner`: the non-fatal `import?` form for a justfile (just
    >= 1.33), or the `-include` form for a Makefile, each naming the installed snippets under the
    harness directory `harness_relpath` names relative to the project root."""
    snippets = f"{harness_relpath}/{KB_TOOLS_SNIPPETS}"
    return {"just": f"import? '{snippets}/kb.just'", "make": f"-include {snippets}/kb.mk"}[runner]


def _harness_dirs() -> dict[str, str]:
    """harness name → its project-harness-dir, for every harness this installation knows."""
    harnesses = cast(dict[str, Harness], load("adjagent.harnesses", "HARNESS"))
    return {name: harness.project_harness_dir for name, harness in harnesses.items()}


class _NamedLine(NamedTuple):
    """An existing runner include line `_named_harnesses` recognized: the harness it names — or the raw
    directory prefix when no harness claims it — its index in the file, the snippets path it spells and
    where in the line that path starts."""

    name: str
    index: int
    path: str
    start: int


def _snippet_path(line: str) -> tuple[str, int] | None:
    """The installed snippets path `line` names first and its offset in the line, or None when it names
    none."""
    found = [(line.find(path), path) for path in _SNIPPET_PATHS if path in line]
    if not found:
        return None
    start, path = min(found)
    return path, start


def _named_harnesses(text: str) -> list[_NamedLine]:
    """A `_NamedLine` for every non-comment line pointing at any harness's installed kb-tools snippets,
    under any path an install has used; empty when no line points at one. A commented-out line is prose
    about an install, not one."""
    dirs = _harness_dirs()
    found: list[_NamedLine] = []
    for index, line in enumerate(text.splitlines()):
        if line.lstrip().startswith("#"):
            continue
        match = _snippet_path(line)
        if match is None:
            continue
        path, start = match
        prefix = line[:start].rsplit(maxsplit=1)[-1].strip("/'\"")
        name = next((name for name, directory in dirs.items() if directory == prefix), prefix)
        found.append(_NamedLine(name, index, path, start))
    return found


def _harness_relpath(root: Path, project: Path) -> str:
    """ROOT's path relative to the project root — the `<harness-relpath>` every consumer-facing line
    under the project spells. A ROOT outside the project root is refused."""
    resolved = root.resolve()
    if not resolved.is_relative_to(project):
        raise InputError(
            f"install root '{root}' is not inside project root '{project}' — "
            "the harness directory must sit under the project it installs into"
        )
    return resolved.relative_to(project).as_posix()


def install_kb_include_line(project: Path, *, harness_relpath: str) -> None:
    """Write the canonical KB include line into `project`'s runner file: the justfile or Makefile
    probed there, else a `Makefile` created carrying it.

    One line only. A line naming this run's harness under any snippets path an install has used is
    rewritten in place — only that path token, so an assignment's left-hand side and a trailing comment
    survive — and no second line is appended. A line naming another harness is reported and left alone,
    and so is a file holding more than one such line, which the operator merges by hand. Only the runner
    file this run selected is examined: a second runner file's legacy line is left to the operator and
    is non-fatal. Nothing is written when `project` is this repository — its own runner is the
    generator's, not a consumer's."""
    if project == REPO_ROOT:
        return
    found = _runner_file(project)
    if found is None:
        path = project / "Makefile"
        path.write_text(
            "# Makefile — created by the adjagent installer.\n"
            f"# The line below pulls in the KB maintenance targets from the installed tree under "
            f"{harness_relpath}; add project targets below it.\n\n"
            f"{kb_include_line(runner='make', harness_relpath=harness_relpath)}\n",
            encoding="utf-8",
        )
        print(f"created {path} with the KB include line")
        return
    runner, path = found
    text = _utf8_text(path)
    named = _named_harnesses(text)
    if len(named) > 1:
        indexes = ", ".join(str(match.index + 1) for match in named)
        print(f"no include line written: {path} names the kb snippets on lines {indexes}; merge them into one")
        return
    if named:
        match = named[0]
        if _harness_dirs().get(match.name, match.name) != harness_relpath:
            print(
                f"no include line written: {path} line {match.index + 1} already includes the kb "
                f"snippets for harness '{match.name}'"
            )
            return
        lines = text.splitlines(keepends=True)
        prior = lines[match.index]
        rewritten = f"{prior[: match.start]}{KB_TOOLS_SNIPPETS}{prior[match.start + len(match.path) :]}"
        if rewritten == prior:
            print(
                f"no include line written: {path} line {match.index + 1} already names the installed "
                f"kb snippets for harness '{match.name}'"
            )
            return
        lines[match.index] = rewritten
        path.write_text("".join(lines), encoding="utf-8", newline="")
        print(f"rewrote the KB include line in {path}")
        return
    line = kb_include_line(runner=runner, harness_relpath=harness_relpath)
    if not text:
        appended = f"{line}\n"
    elif text.endswith("\n\n"):
        appended = f"{text}{line}\n"
    elif text.endswith("\n"):
        appended = f"{text}\n{line}\n"
    else:
        appended = f"{text}\n\n{line}\n"
    path.write_text(appended, encoding="utf-8", newline="")
    print(f"installed: appended the KB include line to {path}")


def _git(directory: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    """`git -C directory <args>` captured as text, or None when git is absent or cannot run. An
    install must not fail on a repository's state."""
    try:
        return subprocess.run(
            ["git", "-C", str(directory), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _lfs_advisory(binary: Path) -> str | None:
    """The Git LFS note for the installed `kbase`: None when it is already LFS-tracked, the untracked
    note when git says it is not, the generic note when git cannot answer."""
    inside = _git(binary.parent, "rev-parse", "--is-inside-work-tree")
    if inside is None or inside.returncode != 0:
        return _LFS_UNKNOWN
    attr = _git(binary.parent, "check-attr", "filter", "--", binary.name)
    if attr is not None and attr.returncode == 0 and attr.stdout.rstrip().endswith("filter: lfs"):
        return None
    return _LFS_UNTRACKED


def install(
    root: Path,
    ctx: Render,
    *,
    verbose: bool,
    with_kb: bool = False,
    kbase_dist: Path | None = None,
    project_root: Path | None = None,
) -> None:
    """Render, replace each package destination whole with a stamped copy, write the renders over what
    is there, then prune. An install that includes kb — `with_kb` names it, or an installed `kbase`
    binary stands at the current `adj-tools/kb-tools` destination or the `agents/kb-tools` one an
    earlier version used (the sticky rule, per ROOT and not per project) — also writes the kb-tools
    package, the harness's `kbase` MCP entry and the consumer's runner include line; every install
    removes each tree an earlier version installed. A refusal of the root, of the render, or of the
    kbase source writes nothing."""
    _refuse_root(root)
    project = root.resolve() if project_root is None else Path(project_root).resolve()
    harness_relpath = _harness_relpath(root, project)
    # A per-ROOT diagnostic on the file's presence alone: a tree whose tracked executable has not
    # been pulled from LFS must not turn a plain install into one that rewrites the consumer's runner
    # and MCP configuration, so no mode and no tree shape is read. What the install copies from is a
    # different question — there the MCP entry would register a command that cannot start, so
    # `_kbase_source` is stricter, and its refusal is the place that reports it.
    kb_included = with_kb or any(
        (root / destination / KBASE_BASENAME).is_file() for destination in (KB_TOOLS_PACKAGE, LEGACY_KB_TOOLS_PACKAGE)
    )
    # Every check runs before the first write: the root refusal and harness relpath above, then the
    # render, the kbase source an install including kb copies from, and that install's runner file.
    renders = render_all(ctx, include=lambda defn: kb_included or not excluded(defn.name))
    copies = package_copies(root, kb_included=kb_included)
    kbase = _kbase_source(root, kbase_dist) if kb_included else None
    kbase_copy = _kbase_copy(root, kbase[0]) if kbase is not None and kbase[1] else None
    if kb_included:
        _check_runner(project)

    for _, destination in SHIPPED_PACKAGES:
        shutil.rmtree(root / destination, ignore_errors=True)
    dist_target: Path | None = None
    if kbase_copy is not None:
        # The executable to copy — `--kbase-dist`'s, or the legacy tree's — replaces the destination
        # whole, beside the snippets.
        executable, data = kbase_copy
        destination = root / KB_TOOLS_PACKAGE
        shutil.rmtree(destination, ignore_errors=True)
        dist_target = destination / KBASE_BASENAME
        dist_target.parent.mkdir(parents=True, exist_ok=True)
        dist_target.write_bytes(data)
        shutil.copymode(executable, dist_target)
    elif kbase is not None:
        # The sticky install refreshes the snippets and leaves the installed executable alone.
        shutil.rmtree(root / KB_TOOLS_PACKAGE / RUNNER_SNIPPETS, ignore_errors=True)
    if kbase is not None:
        binary = dist_target if dist_target is not None else root / KB_TOOLS_PACKAGE / KBASE_BASENAME
        advisory = _lfs_advisory(binary)
        if advisory is not None:
            print(advisory, file=sys.stderr)
    for source, target in copies:
        data = source.read_bytes()
        if source.suffix in STAMPED_SUFFIXES:
            data = stamped(data, origin=source.relative_to(REPO_ROOT).as_posix())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        shutil.copymode(source, target)
    written = write_renders(root, renders)

    for relative in LEGACY_TREES:
        legacy = root / relative
        if legacy.is_dir():
            shutil.rmtree(legacy)
            print(f"removed legacy tree {legacy}")
            if relative == LEGACY_KB_TOOLS and not kb_included:
                print(LEGACY_KB_TOOLS_MESSAGE)
    pruned = prune(root, keep={*written, *(target for _, target in copies)})
    print(
        f"installed: {len(written)} rendered files, "
        f"{len(copies) + int(dist_target is not None)} package files → {root}"
    )
    for path in pruned:
        print(f"pruned {path}")
    if verbose:
        for path in [*(target for _, target in copies), *([dist_target] if dist_target is not None else []), *written]:
            print(f"wrote {path}")
    if kb_included:
        mcp_merge(
            project,
            harness=ctx.harness,
            command=str(root.resolve() / KB_TOOLS_PACKAGE / KBASE_BASENAME),
            kb_root=str(project),
        )
        install_kb_include_line(project, harness_relpath=harness_relpath)
