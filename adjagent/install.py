"""`python3 -m adjagent install ROOT`: every definition rendered into ROOT's agents/, commands/ and
skills/, the shipped packages copied beside them under adj-tools/, each file the installing harness
ships copied into ROOT as it stands, the harness's guardrail hook registered in the project's settings
file where one install-time run of it succeeds, and — when the install includes kb — the kb-tools
package inside the kbase skill's own directory, with the consumer's `kbase` MCP entry and its runner
include line.
Overwrites without ceremony only what carries this repository's banner, refusing over any other file at
a path it writes: the consumer's git is the record of what an install changed."""

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Iterable
from functools import partial
from pathlib import Path, PurePosixPath
from typing import NamedTuple, cast

from adjagent.context import Render
from adjagent.errors import InputError
from adjagent.harness import GuardrailHook, Harness, HookClaim, McpSite
from adjagent.loading import load
from adjagent.render import GENERATED_MARK, GENERATED_NOTICE, render_all, write_renders

REPO_ROOT = Path(__file__).resolve().parent.parent
# (source directory in this repository, destination below ROOT) for the packages every install ships.
# A destination is a consumer contract — definition bodies and the installed runner line name it —
# so it is stated, never derived.
#
# Empty for now: no package ships, the one row this held having retired. The machinery around it
# stays, because a package is expected to return — `package_copies`, the `!INSTALLED!` stamping, the
# destination replacement and `_refuse_root`'s source list all read this tuple, so one row
# here restores the whole path, and nothing else needs an edit.
SHIPPED_PACKAGES: tuple[tuple[str, str], ...] = ()
# The harness resources: files a harness ships that land in its project harness directory as they
# stand, copied and never rendered. The directory below this one in the source is the harness's own
# name, and the destination is ROOT itself — both stated, neither derived from a directory listing.
HARNESS_RESOURCES_SOURCE = "adjagent/harnesses/resources"
# The interpreter the install-time probe runs a guardrail hook script under, found on PATH, and how long
# that run may take before it counts as failed.
GUARDRAIL_INTERPRETER = "perl"
GUARDRAIL_PROBE_SECONDS = 5.0
# The kb toolchain's package: this repository's `kb-tools/` — the runner snippets and the signature
# spot check — beside a `kbase` executable and its detached signature, delivered inside the kbase
# skill's own directory, shipped there only when the install includes kb.
KB_TOOLS_PACKAGE = "skills/kbase/kb-tools"
KB_TOOLS_SOURCE = "kb-tools"
RUNNER_SNIPPETS = "runner-snippets"
KB_TOOLS_SNIPPETS = f"{KB_TOOLS_PACKAGE}/{RUNNER_SNIPPETS}"
# The snippet each runner's include line pulls in — a justfile imports `kb.just`, a Makefile includes
# `kb.mk` — and the suffix that makes a line a line for that runner.
KB_SNIPPET_NAMES = {"just": "kb.just", "make": "kb.mk"}
KBASE_BASENAME = "kbase.exe" if os.name == "nt" else "kbase"
# The detached signature the release installer leaves beside the executable, named for it, and the name
# it is installed under; `kb-tools/verify-kbase-signature.sh` checks the one `.asc` beside it.
SIGNATURE_SUFFIX = ".asc"
KBASE_SIGNATURE = f"{KBASE_BASENAME}{SIGNATURE_SUFFIX}"
# The pre-1.0 underscore destination: the one legacy tree whose removal a run that excluded kb reports
# with advice, so it is named for that message as well as being the first LEGACY_KB_DIRS entry.
LEGACY_KB_TOOLS = "agents/kb_tools"
# The hyphenated destination the kb-tools package moved out of.
LEGACY_KB_TOOLS_PACKAGE = "agents/kb-tools"
# Every tree the kb toolchain has been installed into: the pre-1.0 underscore helper tree, then the
# hyphenated destination it moved to. Each is removed on every install whatever this one installs.
LEGACY_KB_DIRS = (LEGACY_KB_TOOLS, LEGACY_KB_TOOLS_PACKAGE)
# Every tree an earlier version installed that this one removes, whatever it installs: the kb trees,
# and the liaison_tools package's old home under a definition surface.
LEGACY_TREES = (*LEGACY_KB_DIRS, "agents/liaison_tools")
LEGACY_KB_TOOLS_MESSAGE = "legacy kb_tools removed. if you are using kb functionality install using `install-with-kb`"
# A runner include line is recognized by the shape of the path it names, never by a list of spellings:
# any path ending `<directory>/runner-snippets/<that runner's snippet>`, so a tree no release here
# wrote — the pre-1.0 `agents/kb_tools/`, or the consumer's own hand — is still a line this install
# owns rather than one it appends a second copy beside. The path's first segment is the harness
# directory the line is a line for.
_SNIPPET_PATTERNS = {
    runner: re.compile(rf"(?P<path>[^\s/'\"]+(?:/[^\s/'\"]+)*/{RUNNER_SNIPPETS}/{re.escape(snippet)})")
    for runner, snippet in KB_SNIPPET_NAMES.items()
}
# The definition names a base install excludes, matched by shape rather than against a list of names:
# anything opening `kb-`, then `kbase` — the skill, and the one name it excludes today. No `kb-`
# definition ships, so the prefix is there for the next one: a `kb-` definition stays out of a base
# install without an edit here.
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
# The mark a copied file's banner opens with: the one `stamped` writes, and the one a harness resource
# carries as its own text beside the repository's name on one of its first lines, in whatever comment
# syntax its format takes, so no format's syntax is parsed.
_INSTALLED_MARK = "!INSTALLED!"
_RESOURCE_BANNER = re.compile(re.escape(_INSTALLED_MARK).encode("utf-8") + rb" .* adjagent")
_RESOURCE_BANNER_LINES = 10


def _shipped(relative: Path) -> bool:
    """A file the shipped vocabulary covers, matched at any depth: not a test suite or cache, not a
    safety copy, not one of this repository's own project documents."""
    return not (
        EXCLUDED_DIRS.intersection(relative.parts[:-1])
        or relative.name in EXCLUDED_NAMES
        or relative.suffix == EXCLUDED_SUFFIX
    )


def excluded(name: str) -> bool:
    """A definition name `NOT_BY_DEFAULT` covers, matched by shape: anything opening `kb-`, and
    `kbase` — the one name it excludes today. No `kb-` definition ships, so the prefix is what keeps
    the next one out of a base install."""
    return NOT_BY_DEFAULT.match(name) is not None


def package_copies(root: Path, *, kb_included: bool) -> list[tuple[Path, Path]]:
    """(source file, target under `root`) for every file the shipped packages deliver: the always-
    shipped table, and — when kb is included — every file of `kb-tools/`, the runner snippets and the
    signature spot check, which land under that package's destination. The `kbase` executable and its
    signature are not here: the install writes them from the source `--kbase-dist` names, or leaves the
    ones already installed alone."""
    packages = [*SHIPPED_PACKAGES, *([(KB_TOOLS_SOURCE, KB_TOOLS_PACKAGE)] if kb_included else [])]
    return [
        (source, root / destination / source.relative_to(REPO_ROOT / package))
        for package, destination in packages
        for source in sorted((REPO_ROOT / package).rglob("*"))
        if source.is_file() and _shipped(source.relative_to(REPO_ROOT / package))
    ]


def harness_resource_copies(root: Path, *, harness: str) -> list[tuple[Path, Path]]:
    """(source file, target under `root`) for every file `harness` ships: `resources/<harness>/` in this
    repository, delivered into ROOT — the harness directory — so `resources/opencode/plugins/x.ts` lands
    at `<ROOT>/plugins/x.ts`.

    These files are the harness's own, not this repository's generated product: each is copied
    byte-verbatim with its mode preserved and nothing else — no `!INSTALLED!` banner, no stamping. Each
    must carry its own `!INSTALLED! … adjagent` header in its first ten lines: that header is how a
    later install knows the target is one it wrote, and a target without it refuses the install. A
    harness shipping no resources directory copies nothing, which is not an error.

    The copy is one-way and is not a mirror: a resource file this repository drops is not removed from
    a consumer, because `prune` owns the three rendered surfaces and nothing outside them. What lands
    here stays until the consuming project removes it."""
    source = REPO_ROOT / HARNESS_RESOURCES_SOURCE / harness
    if not source.is_dir():
        return []
    return [
        (path, root / path.relative_to(source))
        for path in sorted(source.rglob("*"))
        if path.is_file() and _shipped(path.relative_to(source))
    ]


def stamped(data: bytes, *, origin: str) -> bytes:
    """`data` with the one-line installed banner on top, or below its shebang line."""
    banner = f"# {_INSTALLED_MARK} from {origin} — {GENERATED_NOTICE}\n".encode("utf-8")
    if not data.startswith(b"#!"):
        return banner + data
    shebang, _, rest = data.partition(b"\n")
    return shebang + b"\n" + banner + rest


def _refuse_root(root: Path) -> None:
    """Refuse a root that is not a directory, that is this repository, or that sits inside a source it
    copies from — a shipped package's, the kb toolchain's, or a harness's resource tree — installing
    there writes the product into the tree a later install reads from."""
    if not root.is_dir():
        raise InputError(f"install root '{root}' is not an existing directory")
    resolved = root.resolve()
    sources = [
        *(REPO_ROOT / package for package, _ in SHIPPED_PACKAGES),
        REPO_ROOT / KB_TOOLS_SOURCE,
        REPO_ROOT / HARNESS_RESOURCES_SOURCE,
    ]
    if resolved == REPO_ROOT or any(resolved.is_relative_to(source) for source in sources):
        raise InputError(
            f"install root '{root}' is this repository or inside a source it copies from — "
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


def _is_our_resource(path: Path) -> bool:
    """A harness resource this repository ships, by the `!INSTALLED! … adjagent` header on one of its
    first ten lines. A file that cannot be read is not ours."""
    try:
        with path.open("rb") as handle:
            head = [handle.readline() for _ in range(_RESOURCE_BANNER_LINES)]
    except OSError:
        return False
    return any(_RESOURCE_BANNER.search(line) for line in head)


def _is_our_harness_file(path: Path, *, marker: str) -> bool:
    """A harness-rendered file this repository wrote: the marker the file states about itself appears in
    it. A file that cannot be read or decoded is not ours."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return marker in text


def _blocked_component(target: Path, *, base: Path) -> Path | None:
    """The outermost path strictly between `base` and `target` that exists as a symlink or as anything
    but a directory — a write below it would land elsewhere or fail — or None. `base` and everything
    above it are not examined."""
    for parent in reversed(target.relative_to(base).parents[:-1]):
        component = base / parent
        if os.path.lexists(component) and (component.is_symlink() or not component.is_dir()):
            return component
    return None


def _foreign_on_path(target: Path, *, root: Path, ours: Callable[[Path], bool]) -> Path | None:
    """The path that keeps the install from writing `target` as a file it owns, or None: a component
    `_blocked_component` names below `root`, else `target` itself unless it is absent — a dangling
    symlink counts as something — or a regular file, not a symlink, that `ours` accepts."""
    blocked = _blocked_component(target, base=root)
    if blocked is not None:
        return blocked
    if os.path.lexists(target) and (target.is_symlink() or not target.is_file() or not ours(target)):
        return target
    return None


def _refuse_foreign_targets(
    root: Path,
    *,
    render_targets: Iterable[Path],
    resource_targets: Iterable[Path],
    harness_targets: Iterable[tuple[Path, str]],
) -> None:
    """Refuse an install that would overwrite a file it did not write, or write below a path under
    `root` that is a symlink or not a directory. A target passes as `_foreign_on_path` reads it, judged
    by the claim its class makes of it: a render by its generated banner, a resource by its installed
    header, a harness-rendered file — `(path, marker)` — by the marker that file states about itself.
    Every failing path is named once in the one refusal, so the operator clears them in one pass."""
    claims = [
        *((target, _is_ours) for target in render_targets),
        *((target, _is_our_resource) for target in resource_targets),
        *((target, partial(_is_our_harness_file, marker=marker)) for target, marker in harness_targets),
    ]
    failing = (_foreign_on_path(target, root=root, ours=ours) for target, ours in claims)
    foreign = list(dict.fromkeys(path for path in failing if path is not None))
    if foreign:
        named = ", ".join(f"'{target}'" for target in foreign)
        raise InputError(
            f"install would overwrite files it did not write, or write below a symlink or a non-directory: "
            f"{named} — move or remove each, then re-install"
        )


def prune(root: Path, *, keep: set[Path]) -> list[Path]:
    """Remove every regular file under ROOT's surfaces that is not in `keep`, would ship, and is ours;
    then each directory that leaves empty, up to its surface.

    The kb-tools package is the one destination inside a surface — `skills/kbase/kb-tools/` — and no
    destination is carved out by name. It needs none: a copied package file opens with the
    `!INSTALLED!` banner rather than the generated one `_is_ours` reads, so it is untouched here rather
    than pruned, and the `kbase` executable and its signature beside it carry no banner of ours at all.
    Every file under a surface is thus either ours or untouched. The would-ship vocabulary is
    name-based and covers `kb-` names and `kbase`, so a kb definition this run did not write — an
    install without kb — is stale and removed, while one the run wrote is in `keep`.

    A file at ROOT's top level is outside every surface, and so outside this walk: a harness-rendered
    file such as the plugin manifest, and the harness's own settings file where it lives at ROOT, are
    neither pruned nor read as a stale render. The manifest is rendered on every install that emits it,
    and the settings file is only ever spliced, so neither has a stale form to remove."""
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


class _KbaseCopy(NamedTuple):
    """The executable a run installs at the kb-tools destination, read before the first write: its
    source and bytes, the detached signature expected beside it, and that signature's bytes — None
    where no file stands there."""

    source: Path
    data: bytes
    signature: Path
    signature_data: bytes | None


def _kbase_copy(root: Path, source: Path) -> _KbaseCopy:
    """The executable at `source` and its `<source>.asc` signature, for a run that installs them at the
    kb-tools destination. The bytes are read here, before the first write, because a file inside a
    destination this run replaces whole would be deleted before it could be read; such a file is
    refused instead. A missing signature is no refusal: the executable installs without one."""
    signature = source.with_name(f"{source.name}{SIGNATURE_SUFFIX}")
    replaced = [root / destination for _, destination in SHIPPED_PACKAGES] + [root / KB_TOOLS_PACKAGE]
    for path in (source, signature):
        resolved = path.resolve()
        for destination in replaced:
            if resolved.is_relative_to(destination.resolve()):
                raise InputError(
                    f"the kbase source '{path}' is inside '{destination}', which this install replaces — "
                    "pass a source outside the install root"
                )
    try:
        data = source.read_bytes()
        signature_data = signature.read_bytes() if signature.is_file() else None
    except OSError as exc:
        raise InputError(f"the kbase source '{exc.filename}' cannot be read: {exc}") from exc
    return _KbaseCopy(source, data, signature, signature_data)


_JSON_TYPE_NAMES = {dict: "an object", list: "an array"}


def _refuse_wrong_types(data: dict, *, target: Path, container: tuple[str, ...], leaf: type) -> None:
    """Refuse `target`, parsed as `data`, where a key on `container`'s path holds the wrong type, `null`
    included: each key above the last must hold an object, and the last one a `leaf`. A key that is
    absent is created by the merge and passes."""
    node = data
    for depth, key in enumerate(container):
        if key not in node:
            return
        expected = leaf if depth == len(container) - 1 else dict
        if not isinstance(node[key], expected):
            raise InputError(
                f"'{target}' holds a '{'.'.join(container[: depth + 1])}' that is not "
                f"{_JSON_TYPE_NAMES[expected]} — cannot register the entry there"
            )
        node = node[key]


def _nested(keys: tuple[str, ...], leaf: object) -> object:
    """`leaf` nested under `keys`, the first outermost."""
    for name in reversed(keys):
        leaf = {name: leaf}
    return leaf


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


class _Array(NamedTuple):
    """A JSON array: where its brackets sit and each element's (start, end) span."""

    start: int
    end: int
    elements: tuple[tuple[int, int], ...]


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
        return _array(text, index).end
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


def _array(text: str, index: int) -> _Array:
    """The array whose opening bracket is at `index`: each element's span and the span it covers."""
    elements: list[tuple[int, int]] = []
    cursor = _skip_ws(text, index + 1)
    while _at(text, cursor) != "]":
        end = _value_end(text, cursor)
        elements.append((cursor, end))
        cursor = _skip_ws(text, end)
        if _at(text, cursor) == ",":
            cursor = _skip_ws(text, cursor + 1)
        elif _at(text, cursor) != "]":
            raise _Unsafe("an array element with no separator")
    return _Array(index, cursor + 1, tuple(elements))


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


def _child_indent(text: str, *, last_start: int | None, end: int, unit: str | None) -> str | None:
    """The indent an item added to a container takes: its last sibling's, starting at `last_start`, else
    one `unit` in from the container's closing character just before `end`; None where the file writes
    no such line."""
    if last_start is not None:
        return _line_indent(text, last_start)
    close = _line_indent(text, end - 1)
    return None if close is None or unit is None else close + unit


def _with_item(
    text: str, *, start: int, end: int, last_end: int | None, item: str, indent: str | None, newline: str
) -> str:
    """`text` with `item` added to the container spanning `start` to `end` — after its last item, which
    ends at `last_end`, or alone in an empty container — on a line at `indent`, or inline where that is
    None."""
    if last_end is not None:
        if indent is None:
            return f"{text[:last_end]},{item}{text[last_end:]}"
        return f"{text[:last_end]},{newline}{indent}{item}{text[last_end:]}"
    close = _line_indent(text, end - 1)
    if indent is None or close is None:
        return f"{text[: start + 1]}{item}{text[end - 1 :]}"
    return f"{text[: start + 1]}{newline}{indent}{item}{newline}{close}{text[end - 1 :]}"


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
    last_start, last_end = (obj.members[-1].key_start, obj.members[-1].value_end) if obj.members else (None, None)
    indent = _child_indent(text, last_start=last_start, end=obj.end, unit=unit)
    member = f"{json.dumps(key)}: {_value_text(value, indent=indent, unit=unit, newline=newline)}"
    return _with_item(
        text, start=obj.start, end=obj.end, last_end=last_end, item=member, indent=indent, newline=newline
    )


def _with_element(text: str, *, arr: _Array, value: object, unit: str | None, newline: str) -> str:
    """`text` with `value` appended to `arr` — after its last element, or alone in an empty array — on a
    line at its siblings' indent, or inline where the file writes no such line."""
    last_start, last_end = arr.elements[-1] if arr.elements else (None, None)
    indent = _child_indent(text, last_start=last_start, end=arr.end, unit=unit)
    item = _value_text(value, indent=indent, unit=unit, newline=newline)
    return _with_item(text, start=arr.start, end=arr.end, last_end=last_end, item=item, indent=indent, newline=newline)


class _Layout(NamedTuple):
    """A plain-JSON document's root object, the indent step it writes (None for none), and its line
    ending."""

    root: _Object
    unit: str | None
    newline: str


def _layout(text: str) -> _Layout:
    """The root object of `text` and the formatting an added value copies."""
    start = _skip_ws(text, 0)
    if _at(text, start) != "{":
        raise _Unsafe("a document whose root is not an object")
    root = _object(text, start)
    return _Layout(root, _indent_unit(text, root), "\r\n" if "\r\n" in text else "\n")


def _descend(text: str, *, root: _Object, container: tuple[str, ...]) -> tuple[_Object, int, _Member | None]:
    """Walk `container`'s path from `root`: (the deepest object reached, the depth of the key looked up
    in it, that key's member or None where it is absent). A key the walk passes through must hold an
    object."""
    obj = root
    for depth, key in enumerate(container[:-1]):
        member = _member(obj.members, key)
        if member is None:
            return obj, depth, None
        if _at(text, member.value_start) != "{":
            raise _Unsafe(f"'{key}' is not an object")
        obj = _object(text, member.value_start)
    return obj, len(container) - 1, _member(obj.members, container[-1])


def _with_chain(text: str, *, layout: _Layout, obj: _Object, keys: tuple[str, ...], leaf: object) -> str:
    """`text` with the chain `keys` — absent from `obj` down — added to `obj` as one member, `leaf` at
    its end."""
    value = _nested(keys[1:], leaf)
    return _with_member(text, obj=obj, key=keys[0], value=value, unit=layout.unit, newline=layout.newline)


def _splice(text: str, *, container: tuple[str, ...], entry: dict) -> str | None:
    """`text` — plain JSON the caller has parsed — with `entry` at `container`'s path, every byte
    outside that slot kept. None when the placement cannot be made with certainty: a level naming the
    key the splice must pass through twice, or a text this scanner cannot delimit."""
    try:
        layout = _layout(text)
        obj, depth, member = _descend(text, root=layout.root, container=container)
        if member is None:
            return _with_chain(text, layout=layout, obj=obj, keys=container[depth:], leaf=entry)
        indent = _line_indent(text, member.key_start)
        value_text = _value_text(entry, indent=indent, unit=layout.unit, newline=layout.newline)
        return f"{text[: member.value_start]}{value_text}{text[member.value_end :]}"
    except _Unsafe:
        return None


def _splice_element(text: str, *, container: tuple[str, ...], entry: dict, replace: int | None) -> str | None:
    """`text` — plain JSON the caller has parsed — with `entry` an element of the array at `container`'s
    path: replacing the element at index `replace`, else appended, every byte outside that slot kept. An
    absent array, or a chain of objects down to it, is created holding `entry` alone. None when the
    placement cannot be made with certainty, as for `_splice`, or where the path holds no array."""
    try:
        layout = _layout(text)
        obj, depth, member = _descend(text, root=layout.root, container=container)
        if member is None:
            return _with_chain(text, layout=layout, obj=obj, keys=container[depth:], leaf=[entry])
        if _at(text, member.value_start) != "[":
            raise _Unsafe(f"'{container[-1]}' is not an array")
        arr = _array(text, member.value_start)
        if replace is None:
            return _with_element(text, arr=arr, value=entry, unit=layout.unit, newline=layout.newline)
        start, end = arr.elements[replace]
        indent = _line_indent(text, start)
        value_text = _value_text(entry, indent=indent, unit=layout.unit, newline=layout.newline)
        return f"{text[:start]}{value_text}{text[end:]}"
    except _Unsafe:
        return None


def _mcp_settings_file(base: Path, *, harness: Harness) -> Path:
    """The settings file `harness` registers its MCP entry in under `base`: the first discovered
    alternative, else the canonical path, whether or not it exists yet."""
    canonical = base / harness.mcp.canonical
    candidates = [base / alternative for alternative in harness.mcp.alternatives] + [canonical]
    return next((path for path in candidates if os.path.lexists(path)), canonical)


def _settings_obstacle(target: Path, *, base: Path) -> str | None:
    """Why the settings file at `target` cannot be created or edited in place, naming the path that
    stands in the way; None where `target` is a regular file or absent. A symlink at it or on its path
    below `base`, dangling or not, is never written through — what it reaches is not this project's
    alone — and a non-directory on that path, or anything but a regular file at it, cannot hold it."""
    blocked = _blocked_component(target, base=base)
    if blocked is not None:
        return f"{blocked} is {'a symlink' if blocked.is_symlink() else 'not a directory'}"
    if target.is_symlink():
        return f"{target} is a symlink"
    if os.path.lexists(target) and not target.is_file():
        return f"{target} is not a regular file"
    return None


def _settings_to_read(target: Path, *, base: Path) -> bool:
    """Whether a merge would read `target`: it exists, and `_settings_obstacle` names nothing."""
    return _settings_obstacle(target, base=base) is None and target.is_file()


def _check_settings(target: Path, *, base: Path, container: tuple[str, ...], leaf: type) -> None:
    """Read a settings file a merge will edit before an install's first write: an unreadable or
    undecodable one, or a plain-JSON one holding the wrong type on `container`'s path, is refused there,
    not raised out of the write phase with renders already landed. One the merge will only report — a
    JSONC file, or one `_settings_obstacle` names — passes."""
    if not _settings_to_read(target, base=base):
        return
    plain = _plain_json_object(target)
    if plain is not None:
        _refuse_wrong_types(plain[1], target=target, container=container, leaf=leaf)


def _plain_json_object(target: Path) -> tuple[str, dict] | None:
    """`target`'s text and its parse when it is a plain JSON object a splice can edit, else None. A file
    that cannot be read or decoded is refused."""
    # Read untranslated: a splice writes this text back, and a CRLF file translated here would be
    # rewritten without the merge touching it.
    text = _utf8_text(target)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    # A text json.loads rejects is a JSONC comment carrier, or otherwise not a plain object; a splice
    # would destroy what it cannot read, so both are left to the operator.
    return (text, data) if isinstance(data, dict) else None


def mcp_merge(base: Path, *, harness: Harness, command: str) -> None:
    """Register the `kbase` server in `harness`'s MCP settings file under `base`: the first discovered
    alternative, else the canonical path — created when no file the contract names exists. `base` is
    also the directory the entry is built against, so a command inside it is named relative to it and
    the file names no machine-specific path. It is the project root for a harness whose settings file
    is the project's own, and ROOT for one whose file is the plugin's. The entry lands at the
    contract's container path.

    An existing file is edited, never reserialized: the entry's own slot is spliced into the text as it
    stands, so every other byte — other entries, key order, indentation, line endings, number and
    string spelling — comes back exactly as it was found. A file that is not plain JSON (JSONC comments
    a rewrite would destroy), one naming a key the entry must pass through twice, one the splice
    cannot delimit, and a path `_settings_obstacle` names are each reported and left untouched, with
    the entry printed for the operator to merge by hand."""
    entry, container = harness.mcp.entry(command=command, base=base)
    target = _mcp_settings_file(base, harness=harness)
    by_hand = f"merge this entry by hand: {json.dumps(entry)}"
    obstacle = _settings_obstacle(target, base=base)
    if obstacle is not None:
        print(f"{target} not written: {obstacle} — left untouched; {by_hand}")
        return
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(_nested(container, entry), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {target} with the kbase MCP entry")
        return
    plain = _plain_json_object(target)
    if plain is None:
        print(f"{target} carries JSONC comments — left untouched; {by_hand}")
        return
    text, _ = plain
    spliced = _splice(text, container=container, entry=entry)
    if spliced is None:
        print(f"{target} could not be edited safely — left untouched; {by_hand}")
        return
    target.write_text(spliced, encoding="utf-8", newline="")
    print(f"registered the kbase MCP entry in {target}")


def _guardrail_probe(script: Path, *, project: Path, temp_dir: str) -> str | None:
    """None when `script`, run once under `GUARDRAIL_INTERPRETER` on a command it allows — a redirect
    into `temp_dir` — exits 0 within `GUARDRAIL_PROBE_SECONDS`; otherwise why it did not: the exit status
    and the first stderr line, the timeout, or the `OSError` raised starting the interpreter. The argv
    runs with no shell, so a missing
    interpreter raises rather than exiting 127, and `CLAUDE_PROJECT_DIR` is removed so the hook reads
    the root from the input, as it does when that variable is unset."""
    payload = {"tool_name": "Bash", "tool_input": {"command": f"echo x > {temp_dir}/probe"}, "cwd": str(project)}
    env = {name: value for name, value in os.environ.items() if name != "CLAUDE_PROJECT_DIR"}
    argv = [GUARDRAIL_INTERPRETER, str(script)]
    try:
        result = subprocess.run(
            argv,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
            timeout=GUARDRAIL_PROBE_SECONDS,
        )
    except OSError as exc:
        return f"'{GUARDRAIL_INTERPRETER}' could not be run: {exc}"
    except subprocess.TimeoutExpired:
        return f"'{' '.join(argv)}' did not exit within {GUARDRAIL_PROBE_SECONDS:g} seconds"
    if result.returncode == 0:
        return None
    first = next(iter(result.stderr.splitlines()), "")
    return f"'{' '.join(argv)}' exited {result.returncode}: {first}"


def _guardrail_claims(data: dict, *, guardrail: GuardrailHook) -> list[tuple[int, HookClaim]]:
    """(index, claim) for each element of the array at `guardrail.container` in a parsed settings file
    that holds the guardrail hook, as `guardrail.claim` reads it; empty where none does, or where the
    path holds no array."""
    node: object = data
    for key in guardrail.container:
        node = node.get(key) if isinstance(node, dict) else None
    if not isinstance(node, list):
        return []
    claims = [(index, guardrail.claim(element)) for index, element in enumerate(node)]
    return [(index, claim) for index, claim in claims if claim is not HookClaim.NONE]


def guardrail_merge(project: Path, *, guardrail: GuardrailHook, entry: dict[str, object]) -> None:
    """Register `entry` in `guardrail.settings` under `project`, created holding it alone when absent.

    An existing file is the project's own and is edited, never reserialized: the entry is spliced into
    the array at `guardrail.container`, created when absent, and every other byte — the project's own
    hooks included — comes back as it was found. Ours is the one element holding only the guardrail
    hook, replaced whole; with none, the entry is appended. More than one such element, or one holding
    the hook beside another command, is reported and the file left untouched: replacing it whole would
    delete the project's hook. So is a file that is not a plain JSON object (JSONC comments), one the
    splice cannot place with certainty, and a path `_settings_obstacle` names, each with the entry
    printed to merge by hand."""
    target = project / guardrail.settings
    by_hand = f"merge this entry by hand: {json.dumps(entry)}"
    obstacle = _settings_obstacle(target, base=project)
    if obstacle is not None:
        print(f"{target} not written: {obstacle} — left untouched; {by_hand}")
        return
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(_nested(guardrail.container, [entry]), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {target} with the guardrail hook entry")
        return
    plain = _plain_json_object(target)
    if plain is None:
        print(f"{target} is not a plain JSON object — left untouched; {by_hand}")
        return
    text, data = plain
    found = _guardrail_claims(data, guardrail=guardrail)
    if len(found) > 1 or (found and found[0][1] is HookClaim.SHARED):
        indexes = ", ".join(str(index) for index, _ in found)
        print(
            f"{target} names the guardrail hook in {'.'.join(guardrail.container)} entries {indexes}, not one "
            f"entry holding it alone — left untouched; {by_hand}"
        )
        return
    replace = found[0][0] if found else None
    spliced = _splice_element(text, container=guardrail.container, entry=entry, replace=replace)
    if spliced is None:
        print(f"{target} could not be edited safely — left untouched; {by_hand}")
        return
    if spliced == text:
        print(f"{target} already registers the guardrail hook")
        return
    target.write_text(spliced, encoding="utf-8", newline="")
    print(f"registered the guardrail hook in {target}")


def _earlier_guardrail(script: Path, *, project: Path, guardrail: GuardrailHook) -> list[Path]:
    """The guardrail script and settings file an earlier install left registered: the script where it
    carries the installed header, and the settings file where it holds an element `guardrail.claim`
    accepts. A settings file the merge would not edit, or one that cannot be read or parsed, is not
    named."""
    left = [script] if _is_our_resource(script) else []
    settings = project / guardrail.settings
    if not _settings_to_read(settings, base=project):
        return left
    try:
        plain = _plain_json_object(settings)
    except InputError:
        return left
    if plain is not None and _guardrail_claims(plain[1], guardrail=guardrail):
        left.append(settings)
    return left


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
    snippets = f"{harness_relpath}/{KB_TOOLS_SNIPPETS}/{KB_SNIPPET_NAMES[runner]}"
    return {"just": f"import? '{snippets}'", "make": f"-include {snippets}"}[runner]


def _harness_dirs() -> dict[str, str]:
    """harness name → its project-harness-dir, for every harness this installation knows."""
    harnesses = cast(dict[str, Harness], load("adjagent.harnesses", "HARNESS"))
    return {name: harness.project_harness_dir for name, harness in harnesses.items()}


class _NamedLine(NamedTuple):
    """An existing runner include line `_named_harnesses` recognized: the harness it names — or the raw
    first path segment when no harness claims it — its index in the file, and the span of the snippets
    path it spells."""

    name: str
    index: int
    start: int
    end: int


def _named_harnesses(text: str, *, runner: str) -> list[_NamedLine]:
    """A `_NamedLine` for every non-comment line naming `runner`'s installed kb-tools snippets, under
    whatever tree the path spells; empty when no line names one. A commented-out line is prose about an
    install, not one."""
    dirs = _harness_dirs()
    pattern = _SNIPPET_PATTERNS[runner]
    found: list[_NamedLine] = []
    for index, line in enumerate(text.splitlines()):
        if line.lstrip().startswith("#"):
            continue
        match = pattern.search(line)
        if match is None:
            continue
        start, end = match.span("path")
        segment = line[start:end].split("/", 1)[0]
        name = next((name for name, directory in dirs.items() if directory == segment), segment)
        found.append(_NamedLine(name, index, start, end))
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

    One line only. A line naming this run's harness is recognized by the shape of the snippets path it
    names, whatever tree sits in front of `runner-snippets/`, and rewritten in place — only that path
    token, so an assignment's left-hand side and a trailing comment survive — with no second line
    appended. A line naming another harness is reported and left alone, and so is a file holding more
    than one such line, which the operator merges by hand. Only the runner file this run selected is
    examined: a second runner file's stale line is left to the operator and is non-fatal. Nothing is
    written when `project` is this repository — its own runner is the generator's, not a consumer's."""
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
    named = _named_harnesses(text, runner=runner)
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
        # The harness directory the line spells is kept as it is written; the tree below it belongs to
        # this install, so it is replaced whole.
        segment = prior[match.start : match.end].split("/", 1)[0]
        canonical = f"{segment}/{KB_TOOLS_SNIPPETS}/{KB_SNIPPET_NAMES[runner]}"
        rewritten = f"{prior[: match.start]}{canonical}{prior[match.end :]}"
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


def install(
    root: Path,
    ctx: Render,
    *,
    verbose: bool,
    with_kb: bool = False,
    kbase_dist: Path | None = None,
    project_root: Path | None = None,
) -> None:
    """Render every included definition and every file the harness renders of its own into ROOT,
    replace each package destination whole with a stamped copy, copy the harness's own resource files
    into ROOT as they stand, write the renders over what is there, then prune. An install that includes
    kb — `with_kb` names it, the harness is one whose files sit at its own root, which is a plugin and
    always takes the kb set, or an installed `kbase` binary stands at the current
    `skills/kbase/kb-tools` destination or the `agents/kb-tools` one an earlier version used (the
    sticky rule, per ROOT and not per project) — also writes the kb-tools package, the harness's
    `kbase` MCP entry and, for a harness whose files sit in a project subdirectory, the consumer's
    runner include line, none being written or created for a harness installed at its own root, which
    is a plugin rather than a repo project; the entry goes in the harness's own MCP
    settings file, which sits at the project root or, under a harness whose file is the plugin's, at
    ROOT, its command named relative to that directory. Every install removes each tree an earlier
    version installed. A harness with a guardrail hook has its script run once on this machine first:
    when that run succeeds the script ships with the other resources and every install registers it in
    the project's settings file; when it fails, neither happens, the install goes on, and the report
    names why and what an earlier install left in place. A file at a render, harness-file or resource
    target that does not carry what that class of file states as its origin — this repository's
    generated banner or installed header, or the marker a harness-rendered file states about itself —
    or a symlink or non-directory between ROOT and such a target, refuses the install; package
    destinations are replaced whole unchecked. A refusal of the root, of the render, of a target it
    would overwrite, of the kbase source, of the runner file, of the MCP settings file, of the harness
    directory the guardrail entry cannot name or of the guardrail settings file writes nothing; a
    settings path that is a symlink or not a regular file is reported and left alone."""
    _refuse_root(root)
    project = root.resolve() if project_root is None else Path(project_root).resolve()
    # The settings file's own base: a harness that keeps its file at ROOT resolves its paths and names
    # its command relative to ROOT, every other to the project root.
    mcp_base = project if ctx.harness.mcp.site is McpSite.PROJECT else root
    harness_relpath = _harness_relpath(root, project)
    # A per-ROOT diagnostic on the file's presence alone: a tree whose executable is absent must not
    # turn a plain install into one that rewrites the consumer's runner and MCP configuration, so no
    # mode and no tree shape is read — of a harness installed under a project. A harness whose files
    # sit at ROOT is a plugin whose product is the kb set, so there the set is always included and only
    # the source is left to find. What the install copies from is a different question — there the
    # MCP entry would register a command that cannot start, so `_kbase_source` is stricter, and its
    # refusal is the place that reports it.
    kb_included = (
        with_kb
        or ctx.harness.user_harness_dir == "."
        or any(
            (root / destination / KBASE_BASENAME).is_file()
            for destination in (KB_TOOLS_PACKAGE, LEGACY_KB_TOOLS_PACKAGE)
        )
    )
    # Every check runs before the first write: the root refusal and harness relpath above, then the
    # render, the guardrail probe that decides whether its script is a resource target, each render,
    # harness-file and resource target the install would overwrite and the paths below ROOT it would
    # write through, the kbase source an install including kb copies from, that install's runner file
    # and MCP settings file, and — when the probe passed — the guardrail entry built for this harness
    # directory and the guardrail settings file.
    renders = render_all(ctx, include=lambda defn: kb_included or not excluded(defn.name))
    package_files = package_copies(root, kb_included=kb_included)
    resource_files = harness_resource_copies(root, harness=ctx.harness.name)
    guardrail = ctx.harness.guardrail
    guardrail_skipped: str | None = None
    if guardrail is not None:
        script = REPO_ROOT / HARNESS_RESOURCES_SOURCE / ctx.harness.name / guardrail.script
        guardrail_skipped = _guardrail_probe(script, project=project, temp_dir=ctx.harness.project_temp_dir)
        if guardrail_skipped is not None:
            resource_files = [(source, target) for source, target in resource_files if source != script]
    # The harness's own rendered files are a class of their own at the refusal: their ownership is the
    # marker each states, not a banner a JSON manifest has no way to carry.
    harness_markers = {PurePosixPath(file.path): file.marker for file in ctx.harness.rendered_files}
    _refuse_foreign_targets(
        root,
        render_targets=[root.joinpath(*relative.parts) for relative, _ in renders if relative not in harness_markers],
        resource_targets=[target for _, target in resource_files],
        harness_targets=[
            (root.joinpath(*relative.parts), harness_markers[relative])
            for relative, _ in renders
            if relative in harness_markers
        ],
    )
    # Everything this install copies, in one list: `keep` and the report below count a harness's own
    # files with the packages', so neither reads as a stale render.
    copies = [*package_files, *resource_files]
    kbase = _kbase_source(root, kbase_dist) if kb_included else None
    kbase_copy = _kbase_copy(root, kbase[0]) if kbase is not None and kbase[1] else None
    kbase_command = str(root.resolve() / KB_TOOLS_PACKAGE / KBASE_BASENAME)
    if kb_included:
        _check_runner(project)
        _, mcp_container = ctx.harness.mcp.entry(command=kbase_command, base=mcp_base)
        mcp_target = _mcp_settings_file(mcp_base, harness=ctx.harness)
        _check_settings(mcp_target, base=mcp_base, container=mcp_container, leaf=object)
    guardrail_entry: dict[str, object] | None = None
    if guardrail is not None and guardrail_skipped is None:
        guardrail_entry = guardrail.entry(harness_relpath)
        _check_settings(project / guardrail.settings, base=project, container=guardrail.container, leaf=list)

    for _, destination in SHIPPED_PACKAGES:
        shutil.rmtree(root / destination, ignore_errors=True)
    kbase_written: list[Path] = []
    if kbase_copy is not None:
        # The executable to copy — `--kbase-dist`'s, or the legacy tree's — replaces the destination
        # whole, beside the snippets, with its signature where one stands beside the source.
        destination = root / KB_TOOLS_PACKAGE
        shutil.rmtree(destination, ignore_errors=True)
        destination.mkdir(parents=True)
        dist_target = destination / KBASE_BASENAME
        dist_target.write_bytes(kbase_copy.data)
        shutil.copymode(kbase_copy.source, dist_target)
        kbase_written.append(dist_target)
        if kbase_copy.signature_data is not None:
            signature_target = destination / KBASE_SIGNATURE
            signature_target.write_bytes(kbase_copy.signature_data)
            kbase_written.append(signature_target)
    elif kbase is not None:
        # The sticky install refreshes the snippets and leaves the installed executable and its
        # signature alone.
        shutil.rmtree(root / KB_TOOLS_PACKAGE / RUNNER_SNIPPETS, ignore_errors=True)
    for source, target in package_files:
        data = source.read_bytes()
        if source.suffix in STAMPED_SUFFIXES:
            data = stamped(data, origin=source.relative_to(REPO_ROOT).as_posix())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        shutil.copymode(source, target)
    for source, target in resource_files:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
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
        f"{len(copies) + len(kbase_written)} copied files → {root}"
    )
    if kbase_copy is not None and kbase_copy.signature_data is None:
        print(f"no kbase signature at {kbase_copy.signature} — installed the executable without one")
    for path in pruned:
        print(f"pruned {path}")
    if verbose:
        for path in [*(target for _, target in copies), *kbase_written, *written]:
            print(f"wrote {path}")
    if kb_included:
        mcp_merge(mcp_base, harness=ctx.harness, command=kbase_command)
        # A harness whose files sit at its own root is a plugin, not a repo project, so it has no
        # consumer runner file to include the snippets in and none is created.
        if ctx.harness.user_harness_dir != ".":
            install_kb_include_line(project, harness_relpath=harness_relpath)
    if guardrail is None:
        return
    if guardrail_entry is not None:
        guardrail_merge(project, guardrail=guardrail, entry=guardrail_entry)
        return
    # Neither prune nor the one-way copy removes what an earlier install delivered, so it is named.
    earlier = _earlier_guardrail(root / guardrail.script, project=project, guardrail=guardrail)
    left = f"; left in place from an earlier install: {', '.join(str(path) for path in earlier)}" if earlier else ""
    print(f"guardrail hook skipped, neither installed nor registered: {guardrail_skipped}{left}")
