"""`python3 -m adjagent install TARGET`, once `adjagent.install_target` has resolved the harness
directory and the project root from TARGET. The set is written into ROOT, the harness's `plugin_dir`
below the harness directory — the harness directory itself where that is empty: every definition
rendered into ROOT's agents/, commands/ and skills/, the shipped packages copied to their stated
destinations — the docdicer tools inside the docdicer skill's directory, rebuilding their venv
afterwards where one stood — each file the installing harness ships copied into ROOT as it stands, the
harness's guardrail hook registered in a file of its own under ROOT where one install-time run of it
succeeds, and — when the install includes kb — the kb-tools package inside the kbase skill's own
directory, with the `kbase` MCP entry and the consumer's runner include line; a standalone plugin
installed below its project root also gets its agents file in its harness directory. What an earlier
layout left under the harness directory outside ROOT is removed as the prune and the retired package
destinations reach it, and an entry an earlier install registered in a project settings file is
removed by the install that writes its replacement. Overwrites without ceremony only what carries this repository's banner, refusing
over any other file at a path it writes: the consumer's git is the record of what an install
changed."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable
from functools import partial
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from adjagent.agents_file import (
    AgentsFileWrite,
    FollowedAgentsFile,
    checked_agents_file,
    checked_followed_agents_file,
    refuse_uncommitted,
    write_agents_file,
    write_followed_agents_file,
)
from adjagent.context import Render, harnesses
from adjagent.errors import InputError
from adjagent.harness import EntryClaim, GuardrailHook, Harness, McpSite, Replacement, RetiredEntry
from adjagent.install_target import user_dir_harnesses
from adjagent.preflight import VENV_DIR, run_preflighted
from adjagent.render import (
    GENERATED_MARK,
    GENERATED_NOTICE,
    appended_paragraph,
    render_all,
    write_renders,
    write_text_verbatim,
)


def checkout_root(package_root: Path) -> Path | None:
    """`package_root`'s parent when it holds a `.git` entry — a directory in a clone, a file in a
    worktree — else None. A package installed outside a checkout of this repository, a wheel in
    site-packages, is not in one even where another project's repository encloses it."""
    parent = package_root.parent
    return parent if (parent / ".git").exists() else None


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = checkout_root(PACKAGE_ROOT)


def uncommitted_sources() -> tuple[str, ...]:
    """Every `git status --porcelain` line under this package's directory, untracked included: the
    agents file is a function of the package, so an uncommitted change is an unpublished one. Outside
    a checkout there is no commit state, so nothing is uncommitted and git is not run."""
    if REPO_ROOT is None:
        return ()
    command = ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--", PACKAGE_ROOT.name]
    try:
        out = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise InputError(f"cannot read the commit state of {PACKAGE_ROOT}: {exc}") from exc
    return tuple(line for line in out.splitlines() if line)


def run_tool_install(script: Path) -> str | None:
    """Run a shipped tool's `script --install`, its output passing through: None when it exits 0, else
    one line saying how it failed — its exit status, or why it could not be started."""
    try:
        result = subprocess.run([str(script), "--install"], check=False)
    except OSError as exc:
        return f"could not be run: {exc}"
    return None if result.returncode == 0 else f"exited {result.returncode}"


# The docdicer tools package, inside the docdicer skill's own directory: its launcher script, and the
# virtual environment that script builds beside itself — not install output, so the install replaces it
# with the package and afterwards has the script rebuild it where it existed.
DOCDICER_TOOLS_PACKAGE = "skills/docdicer/tools"
DOCDICER_TOOLS_SCRIPT = f"{DOCDICER_TOOLS_PACKAGE}/docdicer"
DOCDICER_TOOLS_VENV = f"{DOCDICER_TOOLS_PACKAGE}/{VENV_DIR}"
# (source directory in this package, destination below ROOT) for the packages every project install
# ships; a user-level install ships none. A destination is a consumer contract — a skill names its own
# tools relative to its directory, and an installed runner line names its destination — so it is
# stated, never derived. `package_copies`, the `!INSTALLED!` stamping, the destination replacement
# and `_refuse_root`'s source list all read this table.
SHIPPED_PACKAGES: tuple[tuple[str, str], ...] = (("docdicer-tools", DOCDICER_TOOLS_PACKAGE),)
# The harness resources: files a harness ships that land in ROOT as they stand, copied and never
# rendered. The directory below this one in the source is the harness's own
# name, and the destination is ROOT itself — both stated, neither derived from a directory listing.
HARNESS_RESOURCES_SOURCE = "harnesses/resources"
# The interpreter the install-time probe runs a guardrail hook script under, found on PATH, and how long
# that run may take before it counts as failed.
GUARDRAIL_INTERPRETER = "perl"
GUARDRAIL_PROBE_SECONDS = 5.0
KBASE_SKILL_DIR = "skills/kbase"
# The kbase skill's router: carrying this repository's banner, it is what marks ROOT as a kb install.
KBASE_ROUTER = f"{KBASE_SKILL_DIR}/SKILL.md"
# The kb toolchain's package: this package's `kb-tools/`, delivered inside the kbase skill's own
# directory, shipped there only when the install includes kb.
KB_TOOLS_PACKAGE = f"{KBASE_SKILL_DIR}/kb-tools"
KB_TOOLS_SOURCE = "kb-tools"
RUNNER_SNIPPETS = "runner-snippets"
KB_TOOLS_SNIPPETS = f"{KB_TOOLS_PACKAGE}/{RUNNER_SNIPPETS}"
# The snippet each runner's include line pulls in — a justfile imports `kb.just`, a Makefile includes
# `kb.mk` — and the suffix that makes a line a line for that runner.
KB_SNIPPET_NAMES = {"just": "kb.just", "make": "kb.mk"}
# The command every harness's `kbase` MCP entry names: the bare name, resolved from PATH, where the
# user's own kbase install puts it.
KBASE_NAME = "kbase"
# The pre-1.0 underscore kb helper tree: the one legacy tree whose removal a run that excluded kb
# reports with advice, so it is named for that message.
LEGACY_KB_TOOLS = "agents/kb_tools"
# Every tree an earlier version left under a harness directory that this one removes, whatever it
# installs: the pre-1.0 kb helper tree, the v0.11.x kb-tools destination, the hyphenated
# `agents/kb-tools` an unreleased build wrote, and the liaison_tools package's old home under a
# definition surface.
LEGACY_TREES = (LEGACY_KB_TOOLS, "adj-tools/kb-tools", "agents/kb-tools", "agents/liaison_tools")
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
# Never shipped, matched at any depth: test suites, caches and virtual environments, safety copies,
# and this repository's own project documents. README.md is absent on purpose: a package that grows
# one ships it.
EXCLUDED_DIRS = frozenset({"tests", "__pycache__", ".pytest_cache", VENV_DIR})
EXCLUDED_NAMES = frozenset(
    {".DS_Store", "SPEC.md", "ARCHITECTURE.md", "CONVENTIONS.md", "THESIS.md", "ROADMAP.md", "AGENTS.md", "CLAUDE.md"}
)
EXCLUDED_SUFFIX = ".bak"
# Copied package files of a script or build-file type carry the one-line installed banner: by suffix,
# or by name for an extensionless script. Every other file — a `.gitignore` among them — is copied
# byte-verbatim.
STAMPED_SUFFIXES = frozenset({".py", ".sh", ".mk", ".just"})
STAMPED_NAMES = frozenset({"docdicer"})
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


def _packages(*, kb_included: bool) -> list[tuple[str, str]]:
    """(source directory, destination below ROOT) for every package this install ships: the always-
    shipped table, and — when kb is included — `kb-tools/` at its destination."""
    return [*SHIPPED_PACKAGES, *([(KB_TOOLS_SOURCE, KB_TOOLS_PACKAGE)] if kb_included else [])]


def package_copies(root: Path, *, kb_included: bool) -> list[tuple[Path, Path]]:
    """(source file, target under `root`) for every file the shipped packages deliver, each landing
    under its package's destination."""
    return [
        (source, root / destination / source.relative_to(PACKAGE_ROOT / package))
        for package, destination in _packages(kb_included=kb_included)
        for source in sorted((PACKAGE_ROOT / package).rglob("*"))
        if source.is_file() and _shipped(source.relative_to(PACKAGE_ROOT / package))
    ]


def harness_resource_copies(root: Path, *, harness: str) -> list[tuple[Path, Path]]:
    """(source file, target under `root`) for every file `harness` ships: `resources/<harness>/` in this
    package, delivered into ROOT, so `resources/opencode/plugins/x.ts` lands at `<ROOT>/plugins/x.ts`.

    These files are the harness's own, not this repository's generated product: each is copied
    byte-verbatim with its mode preserved and nothing else — no `!INSTALLED!` banner, no stamping. Each
    must carry its own `!INSTALLED! … adjagent` header in its first ten lines: that header is how a
    later install knows the target is one it wrote, and a target without it refuses the install. A
    harness shipping no resources directory copies nothing, which is not an error.

    The copy is one-way and is not a mirror: a resource file this repository drops is not removed from
    a consumer, because `prune` owns the three rendered surfaces and nothing outside them. What lands
    here stays until the consuming project removes it."""
    source = PACKAGE_ROOT / HARNESS_RESOURCES_SOURCE / harness
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
    """Refuse a root that exists and is not a directory, that is this repository, or that sits inside a
    source it copies from — a shipped package's, the kb toolchain's, or a harness's resource tree —
    installing there writes the product into the tree a later install reads from."""
    if os.path.lexists(root) and not root.is_dir():
        raise InputError(f"install root '{root}' is not a directory")
    resolved = root.resolve()
    sources = [
        *(PACKAGE_ROOT / package for package, _ in _packages(kb_included=True)),
        PACKAGE_ROOT / HARNESS_RESOURCES_SOURCE,
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


def _components(target: Path, *, base: Path) -> list[Path]:
    """Each path strictly between `base` and `target`, outermost first."""
    return [base / parent for parent in reversed(tuple(target.relative_to(base).parents)[:-1])]


def _blocked_component(target: Path, *, base: Path) -> Path | None:
    """The outermost path strictly between `base` and `target` that exists but is not a directory, links
    followed — a write below it would fail, a dangling link included — or None. `base` and everything
    above it are not examined."""
    return next((c for c in _components(target, base=base) if os.path.lexists(c) and not c.is_dir()), None)


def _foreign_on_path(target: Path, *, root: Path, ours: Callable[[Path], bool]) -> Path | None:
    """The path that keeps the install from writing `target` as a file it owns, or None: a component
    `_blocked_component` names below `root`, else `target` itself unless, links followed, it does not
    exist or is a regular file that `ours` accepts."""
    blocked = _blocked_component(target, base=root)
    if blocked is not None:
        return blocked
    if target.exists() and (not target.is_file() or not ours(target)):
        return target
    return None


def _dangling_on_path(target: Path, *, base: Path) -> Path | None:
    """The outermost link from below `base` to `target` that nothing can be written through, or None: a
    dangling link on the way, or `target` itself dangling where the directory its named path sits in
    does not exist. `base` and everything above it are not examined."""
    dangling = next((c for c in _components(target, base=base) if c.is_symlink() and not c.exists()), None)
    if dangling is not None:
        return dangling
    if target.is_symlink() and not target.exists() and not target.resolve().parent.is_dir():
        return target
    return None


def _refuse_foreign_targets(
    root: Path,
    *,
    real_root: Path,
    render_targets: Iterable[Path],
    resource_targets: Iterable[Path],
    harness_targets: Iterable[tuple[Path, str]],
    package_destinations: Iterable[Path],
) -> None:
    """Refuse an install that would overwrite a file it did not write, or write below a path under
    `root` that is not a directory. A target passes as `_foreign_on_path` reads it, judged by the claim
    its class makes of it: a render by its generated banner, a resource by its installed header, a
    harness-rendered file — `(path, marker)` — by the marker that file states about itself. A package
    destination, replaced whole, makes no claim. Each target's and destination's counterpart under
    `real_root`, the directory `root` is or is a scratch copy of, is also read for a link
    `_dangling_on_path` names: a copy holds nothing where a link dangles, so only the real path shows it.
    Every failing path is named once in the one refusal, so the operator clears them in one pass."""
    claims = [
        *((target, _is_ours) for target in render_targets),
        *((target, _is_our_resource) for target in resource_targets),
        *((target, partial(_is_our_harness_file, marker=marker)) for target, marker in harness_targets),
    ]
    failing = [
        *(
            _dangling_on_path(real_root / target.relative_to(root), base=real_root)
            or _foreign_on_path(target, root=root, ours=ours)
            for target, ours in claims
        ),
        *(_dangling_on_path(real_root / target.relative_to(root), base=real_root) for target in package_destinations),
    ]
    foreign = list(dict.fromkeys(path for path in failing if path is not None))
    if foreign:
        named = ", ".join(f"'{target}'" for target in foreign)
        raise InputError(
            f"install would overwrite files it did not write, or write below a non-directory: "
            f"{named} — move or remove each, then re-install"
        )


def prune(harness_dir: Path, *, keep: set[Path]) -> list[Path]:
    """Remove every regular file under the harness directory's surfaces that is not in `keep`, would
    ship, and is ours; then each directory that leaves empty, walking upward from the file to the first
    directory that still holds anything, the surface included and the harness directory never.

    A ROOT below the harness directory lies inside its skills surface, so this one walk reaches both
    ROOT's stale renders and what a layout writing straight into the harness directory left there.

    Package destinations sit inside the skills surface — `skills/kbase/kb-tools/` and
    `skills/docdicer/tools/` — and no destination is carved out by name. None needs to be: a copied
    package file carries the `!INSTALLED!` banner or none, never the generated one `_is_ours` reads, so
    it is untouched here rather than pruned, and a `.venv` below a destination is outside the would-ship
    vocabulary, so its files never enter the stale list. Every file under a surface is thus either ours
    or untouched. The would-ship vocabulary is name-based and covers `kb-` names and `kbase`, so a kb
    definition this run did not write — an install without kb — is stale and removed, while one the run
    wrote is in `keep`.

    A harness-rendered file such as the plugin manifest, and the harness's own settings file where it
    lives at ROOT, carry no generated banner, so wherever they sit they are neither pruned nor read as a
    stale render. The manifest is rendered on every install that emits it, and the settings file is
    only ever spliced, so neither has a stale form to remove.

    A link is what it names: the walk enters a linked directory, and an entry is judged by the file it
    names, so one naming a file in `keep` is kept. A stale entry that is a link has the link removed, and
    so does an emptied directory reached through one."""
    kept = {path.resolve() for path in keep}
    stale = [
        path
        for surface in SURFACES
        for path in _files_below(harness_dir / surface)
        if path.resolve() not in kept and path.is_file() and _shipped(path.relative_to(harness_dir)) and _is_ours(path)
    ]
    for path in stale:
        path.unlink()
    for path in stale:
        parent = path.parent
        while parent != harness_dir and parent.is_dir() and not any(parent.iterdir()):
            _remove_entry(parent, remove=Path.rmdir)
            parent = parent.parent
    return stale


def _files_below(top: Path) -> list[Path]:
    """Every non-directory below `top`, sorted, links followed: a directory whose resolved path the walk
    has already entered is not entered again, so a link cycle ends."""
    found: list[Path] = []
    entered: set[str] = set()
    for directory, subdirs, names in os.walk(top, followlinks=True):
        resolved = os.path.realpath(directory)
        if resolved in entered:
            subdirs.clear()
            continue
        entered.add(resolved)
        subdirs.sort()
        found.extend(Path(directory, name) for name in names)
    return sorted(found)


def _remove_entry(path: Path, *, remove: Callable[[Path], None]) -> None:
    """Remove `path` with `remove`, or, where it is a link, dangling or not, the link alone."""
    if path.is_symlink():
        path.unlink()
    else:
        remove(path)


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


def _without_span(text: str, *, start: int, end: int, items: list[tuple[int, int]], index: int) -> str:
    """`text` without item `index` of the container spanning `start` to `end`, whose items span `items`:
    the item and the separator joining it to a neighbour removed, every other byte kept, and a container
    it leaves empty closed up in place."""
    if len(items) == 1:
        return f"{text[: start + 1]}{text[end - 1 :]}"
    if index + 1 < len(items):
        return f"{text[: items[index][0]]}{text[items[index + 1][0] :]}"
    return f"{text[: items[index - 1][1]]}{text[items[index][1] :]}"


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


def _without_item(text: str, *, container: tuple[str, ...], item: str | int) -> str | None:
    """`text` — plain JSON the caller has parsed — without one item of the container at `container`'s
    path: the object member named `item`, or the array element at index `item`, as `_without_span`
    removes it. None when the removal cannot be made with certainty: a level naming a key on the path
    twice, a text this scanner cannot delimit, or a path not holding the item."""
    try:
        layout = _layout(text)
        _, _, member = _descend(text, root=layout.root, container=container)
        if member is None:
            raise _Unsafe(f"no '{container[-1]}'")
        opener = _at(text, member.value_start)
        if isinstance(item, str) and opener == "{":
            obj = _object(text, member.value_start)
            found = _member(obj.members, item)
            if found is None:
                raise _Unsafe(f"no '{item}'")
            items = [(each.key_start, each.value_end) for each in obj.members]
            return _without_span(text, start=obj.start, end=obj.end, items=items, index=obj.members.index(found))
        if isinstance(item, int) and opener == "[":
            arr = _array(text, member.value_start)
            if item >= len(arr.elements):
                raise _Unsafe(f"no element {item}")
            return _without_span(text, start=arr.start, end=arr.end, items=list(arr.elements), index=item)
        raise _Unsafe(f"'{container[-1]}' does not hold the item")
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
    stands in the way; None where `target`, links followed, is a regular file or does not exist. A
    non-directory on its path below `base`, or anything but a regular file at it, cannot hold it."""
    blocked = _blocked_component(target, base=base)
    if blocked is not None:
        return f"{blocked} is not a directory"
    if target.exists() and not target.is_file():
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


def _report_left_alone(message: str) -> None:
    """Print `message`, naming something the install left alone or skipped, on stderr: the write log
    is stdout, which the preflight discards, and this report is owed on every run."""
    print(message, file=sys.stderr)


def mcp_merge(base: Path, *, harness: Harness, command: str) -> None:
    """Register the `kbase` server in `harness`'s MCP settings file under `base`: the first discovered
    alternative, else the canonical path — created when no file the contract names exists. `base` is
    the project root for a harness whose settings file is the project's own, and ROOT for one whose
    file is the plugin's. The entry names `command` as given and lands at the contract's container
    path. A link at the file is read and written through, and a dangling one has the file it names
    created.

    An existing file is edited, never reserialized: the entry's own slot is spliced into the text as it
    stands, so every other byte — other entries, key order, indentation, line endings, number and
    string spelling — comes back exactly as it was found. A file that is not plain JSON (JSONC comments
    a rewrite would destroy), one naming a key the entry must pass through twice, one the splice
    cannot delimit, and a path `_settings_obstacle` names are each reported and left untouched, with
    the entry printed for the operator to merge by hand."""
    entry, container = harness.mcp.entry(command=command)
    target = _mcp_settings_file(base, harness=harness)
    by_hand = f"merge this entry by hand: {json.dumps(entry)}"
    obstacle = _settings_obstacle(target, base=base)
    if obstacle is not None:
        _report_left_alone(f"{target} not written: {obstacle} — left untouched; {by_hand}")
        return
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(_nested(container, entry), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {target} with the kbase MCP entry")
        return
    plain = _plain_json_object(target)
    if plain is None:
        _report_left_alone(f"{target} carries JSONC comments — left untouched; {by_hand}")
        return
    text, _ = plain
    spliced = _splice(text, container=container, entry=entry)
    if spliced is None:
        _report_left_alone(f"{target} could not be edited safely — left untouched; {by_hand}")
        return
    write_text_verbatim(target, spliced)
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


class _Claimed(NamedTuple):
    """An item of a settings file holding an entry an earlier install wrote: its key or index, its value,
    and how much of it is that entry."""

    item: str | int
    value: object
    claim: EntryClaim


def _retired_claims(data: dict, *, entry: RetiredEntry) -> list[_Claimed]:
    """Each item of a parsed settings file holding `entry`, as `entry.claim` reads it: the member
    `entry.member` of the object at `entry.container`, else each element of the array there. Empty where
    none does, or where the path holds no such container."""
    node: object = data
    for key in entry.container:
        node = node.get(key) if isinstance(node, dict) else None
    items: list[tuple[str | int, object]]
    if entry.member:
        items = [(entry.member, node[entry.member])] if isinstance(node, dict) and entry.member in node else []
    else:
        items = list(enumerate(node)) if isinstance(node, list) else []
    claims = [_Claimed(item, value, entry.claim(value)) for item, value in items]
    return [claimed for claimed in claims if claimed.claim is not EntryClaim.NONE]


def _retired_items(project: Path, *, entry: RetiredEntry) -> tuple[Path, str, list[_Claimed]] | None:
    """The project's settings file `entry.settings`, its text, and each item in it holding `entry`, where
    the removal can edit that file: a regular file `_settings_obstacle` names nothing of, in UTF-8 plain
    JSON whose path to `entry`'s container holds the types that container needs. None otherwise — the
    removal never refuses."""
    target = project / entry.settings
    if not _settings_to_read(target, base=project):
        return None
    try:
        plain = _plain_json_object(target)
        if plain is None:
            return None
        text, data = plain
        _refuse_wrong_types(data, target=target, container=entry.container, leaf=dict if entry.member else list)
    except InputError:
        return None
    return target, text, _retired_claims(data, entry=entry)


def _names_text(path: Path, text: str) -> bool:
    """Whether the file `path` reaches, a symlink followed, holds `text`, read as UTF-8 with any byte that
    is not replaced. A path that cannot be read does not."""
    try:
        return text in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def _retired_slot(entry: RetiredEntry) -> str:
    """Where `entry` sits in its settings file, as a report names it."""
    if entry.member:
        return f"'{'.'.join((*entry.container, entry.member))}' member"
    return f"'{'.'.join(entry.container)}' element"


def _remove_retired_entry(project: Path, *, entry: RetiredEntry) -> None:
    """Remove from the project's settings file `entry.settings` the entry an earlier install registered
    there, the caller having written its replacement.

    The file is the project's own and is edited, never reserialized: the one item `entry.claim` reads as
    holding the entry alone is cut out as `_without_item` cuts it, and every other byte — the project's
    own entries included — comes back as it was found. A link is read and written through. An absent
    file — a dangling link names none — or one holding no such item, is left with nothing said. More
    than one such item, or one holding the entry beside a command of the project's own, is reported with
    each printed and the file left untouched: removing it whole would delete the project's command. So
    is one the removal cannot make with certainty. A file `_retired_items` cannot read is left
    untouched, and reported only where the text found there holds `entry.trace`. Nothing here refuses the
    install."""
    target = project / entry.settings
    if not target.exists():
        return
    slot = _retired_slot(entry)
    unread = f"it names an earlier install's {slot}: remove that by hand"
    retired = _retired_items(project, entry=entry)
    if retired is None:
        # Searched as text: only a file naming the entry may strand it.
        if _names_text(target, entry.trace):
            why = _settings_obstacle(target, base=project) or f"{target} is not a JSON object the removal can edit"
            _report_left_alone(f"{target} not edited: {why} — left untouched; {unread}")
        return
    _, text, found = retired
    if not found:
        return
    by_hand = f"remove this entry by hand: {'; '.join(json.dumps(claimed.value) for claimed in found)}"
    if len(found) > 1 or found[0].claim is EntryClaim.SHARED:
        items = ", ".join(str(claimed.item) for claimed in found)
        _report_left_alone(
            f"{target} holds an earlier install's {slot} in {items}, not one item holding it alone — "
            f"left untouched; {by_hand}"
        )
        return
    removed = _without_item(text, container=entry.container, item=found[0].item)
    if removed is None:
        _report_left_alone(f"{target} could not be edited safely — left untouched; {by_hand}")
        return
    write_text_verbatim(target, removed)
    print(f"removed an earlier install's {slot} from {target}")


def _earlier_guardrail(
    root: Path, *, harness_dir: Path, project: Path, guardrail: GuardrailHook, retired: Iterable[RetiredEntry]
) -> list[Path]:
    """What an earlier install left registering the guardrail: its script under ROOT, and under the
    harness directory where a layout writing straight into it put one, where each carries the installed
    header; its registration under ROOT where that carries its marker; and each project settings file
    holding an entry of `retired` its recogniser accepts. A settings file the removal would not edit is
    not named."""
    scripts = dict.fromkeys((root / guardrail.script, harness_dir / guardrail.script))
    left = [script for script in scripts if _is_our_resource(script)]
    registration = root / guardrail.registration.path
    if _is_our_harness_file(registration, marker=guardrail.registration.marker):
        left.append(registration)
    for entry in retired:
        items = _retired_items(project, entry=entry)
        if items is not None and items[2]:
            left.append(items[0])
    return left


def _remove_retired_script(harness_dir: Path, *, script: str) -> None:
    """Remove the guardrail script a layout writing straight into the harness directory left at `script`
    below it, where the file it names carries the installed header — a link has the link alone removed —
    then its directory where that leaves it empty, the link alone where that directory is reached
    through one."""
    path = harness_dir / script
    if _blocked_component(path, base=harness_dir) is not None or not path.is_file():
        return
    if not _is_our_resource(path):
        return
    path.unlink()
    print(f"removed retired guardrail script {path}")
    if path.parent != harness_dir and not any(path.parent.iterdir()):
        _remove_entry(path.parent, remove=Path.rmdir)


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


def _check_runner(project: Path, *, real_project: Path) -> None:
    """Read `project`'s runner file before an install's first write: an unreadable or undecodable file is
    refused there, not raised out of the write phase with packages and renders already landed. Where
    there is none, a `Makefile` link at `real_project` that the created one could not be written through
    is refused: the copy a dry run installs into holds nothing where a link dangles."""
    found = _runner_file(project)
    if found is not None:
        _utf8_text(found[1])
        return
    dangling = _dangling_on_path(real_project / "Makefile", base=real_project)
    if dangling is not None:
        raise InputError(
            f"install would create the KB include line's Makefile through '{dangling}', which names nothing"
        )


def kb_include_line(*, runner: str, harness_relpath: str) -> str:
    """The canonical KB include line for `runner`: the non-fatal `import?` form for a justfile (just
    >= 1.33), or the `-include` form for a Makefile, each naming the installed snippets under the ROOT
    `harness_relpath` names relative to the project root."""
    snippets = f"{harness_relpath}/{KB_TOOLS_SNIPPETS}/{KB_SNIPPET_NAMES[runner]}"
    return {"just": f"import? '{snippets}'", "make": f"-include {snippets}"}[runner]


def _harness_dirs() -> dict[str, str]:
    """harness name → its project-harness-dir, for every harness this installation knows."""
    return {name: harness.project_harness_dir for name, harness in harnesses().items()}


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


def _lexical(path: Path) -> Path:
    """`path` made absolute and normalised without following symlinks."""
    return Path(os.path.normpath(path.absolute()))


def _harness_relpath(root: Path, lexical_project: Path) -> str:
    """ROOT's path relative to the project root, both judged as spelled, links not followed — the
    `<harness-relpath>` every consumer-facing line under the project spells. A ROOT outside the project
    root is refused."""
    lexical = _lexical(root)
    if not lexical.is_relative_to(lexical_project):
        raise InputError(
            f"install root '{root}' is not inside project root '{lexical_project}' — "
            "the harness directory must sit under the project it installs into"
        )
    return lexical.relative_to(lexical_project).as_posix()


def install_kb_include_line(project: Path, *, harness_relpath: str, real_project: Path | None = None) -> None:
    """Write the canonical KB include line into `project`'s runner file: the justfile or Makefile
    probed there, else a `Makefile` created carrying it.

    One line only. A line naming this run's harness directory is recognized by the shape of the snippets
    path it names, whatever tree sits between its first segment — the harness directory, matched against
    the first segment of `harness_relpath` — and `runner-snippets/`, and its whole path token is
    rewritten in place to the canonical one — so an assignment's left-hand side and a trailing comment
    survive — with no second line appended. A line naming another harness directory is reported and
    left alone, and so is a file holding more
    than one such line, which the operator merges by hand. Only the runner file this run selected is
    examined: a second runner file's stale line is left to the operator and is non-fatal. Nothing is
    written when `project` is this repository — its own runner is the generator's, not a consumer's.
    `real_project`, defaulting to `project`, is the project that is, where `project` is a scratch copy
    of it."""
    if (project if real_project is None else real_project) == REPO_ROOT:
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
        _report_left_alone(
            f"no include line written: {path} names the kb snippets on lines {indexes}; merge them into one"
        )
        return
    if named:
        match = named[0]
        lines = text.splitlines(keepends=True)
        prior = lines[match.index]
        # The line is this install's when it spells the same first segment — the harness directory — as
        # ROOT's path does; the whole path token, ROOT's own path below that segment included, is then
        # this install's to replace.
        if prior[match.start : match.end].split("/", 1)[0] != harness_relpath.split("/", 1)[0]:
            _report_left_alone(
                f"no include line written: {path} line {match.index + 1} already includes the kb "
                f"snippets for harness '{match.name}'"
            )
            return
        canonical = f"{harness_relpath}/{KB_TOOLS_SNIPPETS}/{KB_SNIPPET_NAMES[runner]}"
        rewritten = f"{prior[: match.start]}{canonical}{prior[match.end :]}"
        if rewritten == prior:
            _report_left_alone(
                f"no include line written: {path} line {match.index + 1} already names the installed "
                f"kb snippets for harness '{match.name}'"
            )
            return
        lines[match.index] = rewritten
        write_text_verbatim(path, "".join(lines))
        print(f"rewrote the KB include line in {path}")
        return
    line = kb_include_line(runner=runner, harness_relpath=harness_relpath)
    write_text_verbatim(path, appended_paragraph(text, line))
    print(f"installed: appended the KB include line to {path}")


def _installs_agents_file(
    harness_dir: Path, harness: Harness, *, lexical_project: Path, user_level: bool, global_agents_file: bool
) -> bool:
    """Whether an install into `harness_dir` writes an agents file there: a standalone plugin installed
    below its project root, judged as both are spelled, or a user-level install given
    `global_agents_file`."""
    plugin_below_project = harness.is_standalone_plugin and _lexical(harness_dir) != lexical_project
    return plugin_below_project or (user_level and global_agents_file)


def _keeps_the_block_current(harness: Harness, *, user_level: bool) -> bool:
    """Whether an install keeps the agents-file block current in the one place it lives: every project
    install of a harness that is not a standalone plugin, whose agents file is its plugin's."""
    return not user_level and not harness.is_standalone_plugin


def _guardrail_in_play(harness: Harness, *, user_level: bool) -> GuardrailHook | None:
    """The guardrail hook an install delivers, before the probe decides whether it registers: the
    harness's own on a project install, none on a user-level one."""
    return None if user_level else harness.guardrail


def _mcp_settings_base(harness: Harness, *, project: Path, root: Path) -> Path:
    """The base the MCP settings file lives at and resolves its paths against: ROOT for a harness that
    keeps its file there, the project root for every other."""
    return project if harness.mcp.site is McpSite.PROJECT else root


def _may_write_mcp_settings(harness: Harness, *, user_level: bool) -> bool:
    """Whether an install with the kb set writes the kbase MCP entry: every project install, and a
    user-level one where the harness keeps its settings file at ROOT."""
    return not user_level or harness.mcp.site is McpSite.HARNESS


def _may_write_include_line(harness: Harness, *, user_level: bool) -> bool:
    """Whether an install with the kb set writes the KB include line in the project's runner file: a
    project install, unless the harness is a standalone plugin. A standalone plugin is not a repo
    project, so it has no consumer runner file and none is created."""
    return not user_level and not harness.is_standalone_plugin


def _retirable_entries(harness: Harness, *, user_level: bool) -> tuple[RetiredEntry, ...]:
    """The entries earlier installs registered that a project install may remove; none at user level."""
    return () if user_level else harness.retired_entries


def _standing_docdicer_venvs(root: Path, *, harness_dir: Path, user_level: bool) -> list[Path]:
    """The docdicer tools' `.venv` directories a project install finds standing, removes with their
    package destination, and then has rebuilt at ROOT's: one at ROOT's destination, and one at the
    harness directory's where ROOT lies below it. None for a user-level install, which ships no
    package."""
    if user_level:
        return []
    venvs = dict.fromkeys((root / DOCDICER_TOOLS_VENV, harness_dir / DOCDICER_TOOLS_VENV))
    return [venv for venv in venvs if venv.is_dir()]


def _clear_package_destination(destination: Path) -> None:
    """Leave nothing at `destination` for the package copy to sit beside: a directory is removed whole,
    and any other file there unlinked, the destination being the repository's whole. A link stays and
    is copied through — the directory it names emptied, or made where it dangles, its own directory
    standing, as the refusals before the first write ensure."""
    if destination.is_symlink():
        if destination.is_dir():
            for entry in destination.iterdir():
                _remove_entry(entry, remove=shutil.rmtree if entry.is_dir() else Path.unlink)
        else:
            destination.resolve().mkdir()
    elif destination.is_dir():
        shutil.rmtree(destination)
    elif destination.exists():
        destination.unlink()


def _report_shadowing(root: Path, *, harness: Harness, user_level: bool) -> None:
    """Report a plugin the harness loads in place of another of the same name, for a harness that writes
    its set below its harness directory: a user-level install always shadows every project's; a project
    install is shadowed where the user-level ROOT holds every file the harness renders of its own, each
    carrying the marker that makes it ours."""
    if not harness.plugin_dir:
        return
    if user_level:
        _report_left_alone(
            f"{root} is user-level: the harness loads it in place of every project's plugin of the same name"
        )
        return
    user_root = harness.user_dir / harness.plugin_dir
    if all(_is_our_harness_file(user_root / file.path, marker=file.marker) for file in harness.rendered_files):
        _report_left_alone(
            f"{root} is shadowed by {user_root}, a user-level plugin of the same name: the harness loads that "
            "one, and this project's plugin — its tuning, version and MCP server — does not load"
        )


def install(
    harness_dir: Path,
    ctx: Render,
    *,
    verbose: bool,
    with_kb: bool = False,
    project_root: Path | None = None,
    uncommitted: Callable[[], tuple[str, ...]],
    tool_install: Callable[[Path], str | None],
    global_agents_file: bool = False,
    real_harness_dir: Path | None = None,
    real_project: Path | None = None,
    global_dir: Path | None = None,
) -> None:
    """Install the set `ctx` renders into ROOT, `harness_dir / ctx.harness.plugin_dir`. Every check runs
    first, so a refusal writes nothing; then the writes; then the removals.

    `verbose` prints each file written. `with_kb` asks for the kb set; an earlier kb install, or a
    standalone-plugin harness, includes it unasked. `project_root` is the project the harness directory
    belongs to, defaulting to `harness_dir`. `uncommitted` names the uncommitted changes to the sources,
    called only where a write must refuse on them. `tool_install` rebuilds the docdicer tools' `.venv`
    from the installed script the path names, returning None or one line saying how it failed.
    `global_agents_file` has a user-level install write the agents file too; a project install ignores
    it. `real_harness_dir` and `real_project` are the harness directory and project root the install is
    for, where `harness_dir` and `project_root` are a scratch copy of them, each defaulting to the path
    written. `global_dir` is the harness's user harness directory, or a scratch copy of it, defaulting
    to the directory itself."""
    root = harness_dir / ctx.harness.plugin_dir
    _refuse_root(harness_dir)
    _refuse_root(root)
    project = harness_dir.resolve() if project_root is None else Path(project_root).resolve()
    lexical_project = _lexical(harness_dir if project_root is None else Path(project_root))
    mcp_base = _mcp_settings_base(ctx.harness, project=project, root=root)
    user_level = ctx.harness.name in user_dir_harnesses(harness_dir if real_harness_dir is None else real_harness_dir)
    # A user-level harness directory need not sit under its project root — a user directory may be a
    # symlink out of home — and nothing a user-level install writes spells its path from there.
    harness_relpath = "" if user_level else _harness_relpath(root, lexical_project)
    kb_included = (
        with_kb
        or ctx.harness.is_standalone_plugin
        or any(_is_ours(base / KBASE_ROUTER) for base in (root, harness_dir))
    )
    # Every check runs before the first write: the root refusals and harness relpath above, then the
    # render, the guardrail probe that decides whether its script is a resource target, each render,
    # harness-file and resource target the install would overwrite and the paths below the harness
    # directory it would write through, an install including kb's runner file and MCP settings file,
    # and the agents file's. ROOT itself is created only after all of them.
    renders = render_all(ctx, include=lambda defn: kb_included or not excluded(defn.name))
    destinations = [] if user_level else _packages(kb_included=kb_included)
    package_files = [] if user_level else package_copies(root, kb_included=kb_included)
    resource_files = [] if user_level else harness_resource_copies(root, harness=ctx.harness.name)
    guardrail = _guardrail_in_play(ctx.harness, user_level=user_level)
    writes_mcp = kb_included and _may_write_mcp_settings(ctx.harness, user_level=user_level)
    writes_include_line = kb_included and _may_write_include_line(ctx.harness, user_level=user_level)
    retired_destinations = (
        []
        if user_level or not ctx.harness.plugin_dir
        else [harness_dir / dest for _, dest in _packages(kb_included=True)]
    )
    guardrail_skipped: str | None = None
    harness_files = list(ctx.harness.rendered_files)
    if guardrail is not None:
        script = PACKAGE_ROOT / HARNESS_RESOURCES_SOURCE / ctx.harness.name / guardrail.script
        guardrail_skipped = _guardrail_probe(script, project=project, temp_dir=ctx.harness.project_temp_dir)
        if guardrail_skipped is not None:
            resource_files = [(source, target) for source, target in resource_files if source != script]
        else:
            harness_files.append(guardrail.registration)
            renders = (*renders, (PurePosixPath(guardrail.registration.path), guardrail.registration.text()))
    registers_guardrail = guardrail is not None and guardrail_skipped is None
    # An entry an earlier install registered goes only on an install that writes what replaces it.
    replaced = {Replacement.GUARDRAIL: registers_guardrail, Replacement.MCP: writes_mcp}
    retiring = [
        entry for entry in _retirable_entries(ctx.harness, user_level=user_level) if replaced[entry.replacement]
    ]
    # The harness's own rendered files are a class of their own at the refusal: their ownership is the
    # marker each states, not a banner a JSON file has no way to carry.
    harness_markers = {PurePosixPath(file.path): file.marker for file in harness_files}
    _refuse_foreign_targets(
        harness_dir,
        real_root=harness_dir if real_harness_dir is None else real_harness_dir,
        render_targets=[root.joinpath(*relative.parts) for relative, _ in renders if relative not in harness_markers],
        resource_targets=[target for _, target in resource_files],
        harness_targets=[
            (root.joinpath(*relative.parts), harness_markers[relative])
            for relative, _ in renders
            if relative in harness_markers
        ],
        package_destinations=[root / destination for _, destination in destinations],
    )
    # Everything this install copies, in one list: `keep` and the report below count a harness's own
    # files with the packages', so neither reads as a stale render.
    copies = [*package_files, *resource_files]
    if writes_include_line:
        _check_runner(project, real_project=project if real_project is None else real_project)
    if writes_mcp:
        _, mcp_container = ctx.harness.mcp.entry(command=KBASE_NAME)
        mcp_target = _mcp_settings_file(mcp_base, harness=ctx.harness)
        _check_settings(mcp_target, base=mcp_base, container=mcp_container, leaf=object)
        # Read at the real path: the copy a dry run installs into holds nothing where a link dangles.
        real_root = (harness_dir if real_harness_dir is None else real_harness_dir) / ctx.harness.plugin_dir
        real_project_root = project if real_project is None else real_project
        real_mcp_base = _mcp_settings_base(ctx.harness, project=real_project_root, root=real_root)
        dangling = _dangling_on_path(_mcp_settings_file(real_mcp_base, harness=ctx.harness), base=real_mcp_base)
        if dangling is not None:
            raise InputError(f"install would write the kbase MCP entry through '{dangling}', which names nothing")
    agents_file: AgentsFileWrite | None = None
    if _installs_agents_file(
        harness_dir,
        ctx.harness,
        lexical_project=lexical_project,
        user_level=user_level,
        global_agents_file=global_agents_file,
    ):
        if user_level:
            refuse_uncommitted(uncommitted())
        agents_file = checked_agents_file(harness_dir, ctx.harness, real_directory=real_harness_dir)
    followed: FollowedAgentsFile | None = None
    if _keeps_the_block_current(ctx.harness, user_level=user_level):
        followed = checked_followed_agents_file(
            project,
            ctx.harness,
            global_dir=ctx.harness.user_dir if global_dir is None else global_dir,
            uncommitted=uncommitted,
            real_project=real_project,
        )
    # Read before the destination is replaced, which removes the venv with the rest of the package.
    rebuild_docdicer_venv = bool(_standing_docdicer_venvs(root, harness_dir=harness_dir, user_level=user_level))

    root.mkdir(parents=True, exist_ok=True)
    for _, destination in destinations:
        _clear_package_destination(root / destination)
    for source, target in package_files:
        data = source.read_bytes()
        if source.suffix in STAMPED_SUFFIXES or source.name in STAMPED_NAMES:
            data = stamped(data, origin=source.relative_to(PACKAGE_ROOT.parent).as_posix())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        shutil.copymode(source, target)
    for source, target in resource_files:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        shutil.copymode(source, target)
    written = write_renders(root, renders)
    if agents_file is not None:
        write_agents_file(agents_file)
    if followed is not None:
        write_followed_agents_file(followed)

    # Removed before the prune, so a skill directory the prune then empties goes with its last file.
    for retired in retired_destinations:
        if retired.is_symlink() or retired.is_dir():
            _remove_entry(retired, remove=shutil.rmtree)
            print(f"removed retired package destination {retired}")
    for relative in LEGACY_TREES:
        legacy = harness_dir / relative
        if legacy.is_symlink() or legacy.is_dir():
            _remove_entry(legacy, remove=shutil.rmtree)
            print(f"removed legacy tree {legacy}")
            if relative == LEGACY_KB_TOOLS and not kb_included:
                print(LEGACY_KB_TOOLS_MESSAGE)
    pruned = prune(harness_dir, keep={*written, *(target for _, target in copies)})
    print(f"installed: {len(written)} rendered files, {len(copies)} copied files → {root}")
    for path in pruned:
        print(f"pruned {path}")
    if verbose:
        for path in [*(target for _, target in copies), *written]:
            print(f"wrote {path}")
    if writes_mcp:
        mcp_merge(mcp_base, harness=ctx.harness, command=KBASE_NAME)
    if writes_include_line:
        install_kb_include_line(project, harness_relpath=harness_relpath, real_project=real_project)
    for entry in retiring:
        _remove_retired_entry(project, entry=entry)
    if guardrail is not None and registers_guardrail and harness_dir != root:
        _remove_retired_script(harness_dir, script=guardrail.script)
    elif guardrail is not None and not registers_guardrail:
        # Neither prune nor the one-way copy removes what an earlier install delivered, so it is named.
        earlier = _earlier_guardrail(
            root,
            harness_dir=harness_dir,
            project=project,
            guardrail=guardrail,
            retired=[entry for entry in ctx.harness.retired_entries if entry.replacement is Replacement.GUARDRAIL],
        )
        left = f"; left in place from an earlier install: {', '.join(str(path) for path in earlier)}" if earlier else ""
        _report_left_alone(f"guardrail hook skipped, neither installed nor registered: {guardrail_skipped}{left}")
    if rebuild_docdicer_venv:
        script = root / DOCDICER_TOOLS_SCRIPT
        failure = tool_install(script)
        if failure is not None:
            print(f"'{script} --install' failed, the install otherwise complete: {failure}")
    _report_shadowing(root, harness=ctx.harness, user_level=user_level)
    if ctx.harness.reload_rule:
        print(ctx.harness.reload_rule)


def _install_managed_paths(
    harness_dir: Path,
    harness: Harness,
    *,
    project: Path,
    lexical_project: Path,
    user_level: bool,
    global_agents_file: bool,
) -> list[tuple[Path, list[str]]]:
    """(base, paths relative to it) for everything an install into `harness_dir` may read or write: the
    project root as spelled, the harness directory, ROOT and the harness's user harness directory, in
    that order, ROOT keeping its position below the harness directory. Named from what the install
    writes by, never a listing of a directory, which in a user harness directory holds the operator's
    own trees. Each decision the install takes on what only its run knows — the kb set, the guardrail
    probe — is taken here as though it went the way that writes more."""
    root = harness_dir / harness.plugin_dir
    destinations = [destination for _, destination in _packages(kb_included=True)]
    under_harness_dir = [*SURFACES, *LEGACY_TREES, *destinations]
    under_root = [
        *SURFACES,
        *destinations,
        *(target.relative_to(root).as_posix() for _, target in harness_resource_copies(root, harness=harness.name)),
        *(file.path for file in harness.rendered_files),
    ]
    guardrail = _guardrail_in_play(harness, user_level=user_level)
    if guardrail is not None:
        under_harness_dir.append(guardrail.script)
        under_root.append(guardrail.registration.path)
    under_project: list[str] = []
    if _may_write_mcp_settings(harness, user_level=user_level):
        mcp_paths = [harness.mcp.canonical, *harness.mcp.alternatives]
        if _mcp_settings_base(harness, project=lexical_project, root=root) == root:
            under_root += mcp_paths
        else:
            under_project += mcp_paths
    if _may_write_include_line(harness, user_level=user_level):
        under_project += [*_JUSTFILE_NAMES, *_MAKEFILE_NAMES]
    under_project += [entry.settings for entry in _retirable_entries(harness, user_level=user_level)]
    if _installs_agents_file(
        harness_dir,
        harness,
        lexical_project=lexical_project,
        user_level=user_level,
        global_agents_file=global_agents_file,
    ):
        write = checked_agents_file(harness_dir, harness)
        under_harness_dir += [path.relative_to(harness_dir).as_posix() for path in write.paths]
    global_dir = harness.user_dir
    under_global_dir: list[str] = []
    if _keeps_the_block_current(harness, user_level=user_level):
        followed = checked_followed_agents_file(project, harness, global_dir=global_dir, uncommitted=lambda: ())
        for path in followed.paths:
            if path.is_relative_to(project):
                under_project.append(path.relative_to(project).as_posix())
            else:
                under_global_dir.append(path.relative_to(global_dir).as_posix())
    return [
        (lexical_project, under_project),
        (harness_dir, under_harness_dir),
        (root, under_root),
        (global_dir, under_global_dir),
    ]


def preflighted_install(
    harness_dir: Path,
    ctx: Render,
    *,
    verbose: bool,
    with_kb: bool = False,
    project_root: Path | None = None,
    uncommitted: Callable[[], tuple[str, ...]],
    tool_install: Callable[[Path], str | None],
    global_agents_file: bool = False,
    dry_run: bool = False,
) -> None:
    """`install` behind the preflight: run first into a scratch copy of the paths it manages, with the
    real harness directory and project root as its identity. Where that changed nothing, the harness
    directory is reported up to date and nothing in the target is touched — no file, no package
    destination, no `.venv`, no `tool_install` run. With `dry_run`, what would be created, changed and
    removed is printed relative to the project root, followed by the docdicer `.venv` rebuild the
    install would also make, and nothing is written. Otherwise the install runs exactly as `install`
    does. The copy holds no `.venv`, so only that real install can reach `tool_install`. Every printed
    path and refusal names the real target."""
    root = harness_dir / ctx.harness.plugin_dir
    _refuse_root(harness_dir)
    _refuse_root(root)
    project = harness_dir.resolve() if project_root is None else Path(project_root).resolve()
    lexical_project = _lexical(harness_dir if project_root is None else Path(project_root))
    user_level = ctx.harness.name in user_dir_harnesses(harness_dir)
    managed = _install_managed_paths(
        harness_dir,
        ctx.harness,
        project=project,
        lexical_project=lexical_project,
        user_level=user_level,
        global_agents_file=global_agents_file,
    )
    dry_run_notes: list[str] = []
    venvs = _standing_docdicer_venvs(root, harness_dir=harness_dir, user_level=user_level)
    if venvs:
        relpath = PurePosixPath(_harness_relpath(root, lexical_project))
        replaced = " and ".join(_harness_relpath(venv, lexical_project) for venv in venvs)
        dry_run_notes.append(
            f"the install would also replace {replaced} and run "
            f"'{relpath / DOCDICER_TOOLS_SCRIPT} --install', which needs the network"
        )
    run_preflighted(
        managed,
        install=lambda bases: install(
            bases[1],
            ctx,
            verbose=verbose,
            with_kb=with_kb,
            project_root=bases[0],
            uncommitted=uncommitted,
            tool_install=tool_install,
            global_agents_file=global_agents_file,
            real_harness_dir=harness_dir,
            real_project=project,
            global_dir=bases[3],
        ),
        dry_run=dry_run,
        target=harness_dir,
        report_root=lexical_project,
        dry_run_notes=dry_run_notes,
    )
