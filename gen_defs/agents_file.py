"""
The harness agents file — one template, rendered per harness, and installed by
block replacement.

templates/harness/AGENTS.tmpl.md is the operator agents file every supported
harness reads (Claude Code's CLAUDE.md, opencode's AGENTS.md). It is not a
surface: discovery never reaches templates/harness/, `install` never renders
it, and it carries no banner. One harness file per harness supplies the values
that differ between them:

    templates/harness/<name>.toml
        [harness.<key>]
        text = "..."

Each entry fills @!hrn.<key>!@, a strict value namespace: a key the loaded
file does not define is an error, never an empty string. The same file also
fills the agent and command surfaces' @!hrn.<key>!@ markers, loaded by
`generate`/`install --harness NAME` (default model_tuning.DEFAULT_HARNESS).

The template's fence names its outputs by metakey rather than by name, because
the output path is itself rendered:

    +++
    [[outputs._resolve]]
    text = "@!dyn.agents-file-install-dir-arg!@/@!hrn.agents-file!@"
    +++

Every `_resolve` entry's `text` renders to one output path, and the body below
the fence renders once per output. A resolved path must sit directly in DIR,
the directory the file is installed into, and one named the harness's
[harness.agents-file] is that harness's native file — the destination only in
Global scope (Install, below). `_resolve` is underscore-led so it
can never be read as an output name; a surface template carrying it is refused
by split_outputs.

The render binds five invocation parameters of its own, beside the five tier
tokens (pinned by DEFAULT_PIN_MAP; the agents file takes no tuning flags):

    @!dyn.agents-file-install-dir-arg!@   DIR, as given
    @!dyn.gen-short-sha!@                 this repository's short HEAD sha,
                                          suffixed **dirty** while templates/
                                          carries staged, unstaged or
                                          untracked changes
    @!dyn.agents-file-scope-name!@        `Global` when DIR is the harness's
                                          [harness.user-harness-dir];
                                          otherwise `Project` when DIR/.git
                                          exists (a file or a directory);
                                          otherwise DIR's own name
    @!dyn.existing-user-content-before-rendered-minus-h1!@
    @!dyn.existing-user-content-after-rendered!@
                                          the user's own text above and below
                                          the block — see Install, below

The revision is probed by the CLI and passed in, so the render's output never
depends on the state of the repository a test runs in.

Install
-------

    python3 -m gen_defs install-agents-file HARNESS DIR

The directives live in AGENTS.md. In Global scope the destination is the
harness's native file, DIR/<agents-file>, and nothing else is touched.
Anywhere else a native-file output is relocated to DIR/AGENTS.md, and a native
file named otherwise (claude's CLAUDE.md) becomes the one-line redirect
`@AGENTS.md`: created when absent, left alone when it already redirects there,
and refused, with nothing written, when it holds anything else — its content is
the operator's to move into AGENTS.md by hand. The redirect is planned with
every other output and written after them.

The installed file has four parts, in order, each placed by the template: the
H1; the user's before-content; the block, from the begin marker line through
the end marker line; the user's after-content. An install replaces the block
wholesale and owns nothing outside it.

A marker line is recognised by its ends alone, with surrounding whitespace
stripped: a begin line starts `<!-- vvv-adjagent` and ends `adjagent-vvv -->`,
an end line starts `<!-- ^^^-adjagent` and ends `adjagent-^^^ -->`. What sits
between — the `version[<sha>]` revision included — is information only and
never compared, so a block written by any earlier revision is still found. A
file is valid with no marker lines at all, or with exactly one begin line
followed by exactly one end line; any other count or order is malformed and
refused, and nothing is written.

The existing file is split:

    existing file     before-content                     after-content
    valid pair        above the begin line, minus the    below the end line
                      first line starting `# `
    no markers        the whole file, minus the first    empty
                      line starting `# `
    no file           empty                              empty

and each span is trimmed: leading and trailing empty or whitespace-only lines
are dropped, the final line's terminator with them, and the interior is kept
byte for byte. Trimming is what makes a second install byte-identical to the
first.

User content is never rendered. The two user-content parameters are bound as
verbatim values (`markers` module docstring), as are DIR and the scope name:
spliced in as themselves, never rescanned, never residual-checked, and never
read across by a scan. The render must hold exactly one marker pair, the
before-content value exactly once above the begin line and the after-content
value exactly once below the end line, counted by the verbatim spans the
expansion records — so an empty span still counts. A template that does not is
refused. The `_resolve` paths render without the user-content parameters.

Every output is planned — read, split, rendered — before any is written, and a
refusal anywhere writes nothing. Refused: a dirty templates revision; an
output path, or the `backup.<name>` beside it, that is a symlink or exists as
anything but a regular file; an existing file that is not UTF-8 or is
malformed. Each output is then written by case: identical text writes nothing
and reports `unchanged`; a missing file is written; any other write first
copies the prior file's bytes to `backup.<name>` beside it, the one rolling
backup, overwritten by the next write that changes the file. A file that had
no markers is reported as kept whole above the block, its duplicated rules now
the user's to delete.

A destination whose only non-blank content is one line `@<path>` (surrounding
whitespace ignored) is a redirect: the install goes into <path>, resolved from
the redirect's own directory, by the same rules, and the redirect file itself
is never written; any other file, two imports or an import beside text, is an
ordinary one. One hop only — a target that is itself a redirect, or that
resolves outside DIR once symlinks are resolved, or whose directory does not
exist, is refused with nothing written. A missing target is a fresh install,
the target and its backup take the destination's symlink refusals, it is
planned with every other output, and its report names the redirect followed.

Dev render
----------

    python3 -m gen_defs dev render-agents-file HARNESS OUT

renders with both user-content spans empty, the install directory bound to
OUT's parent, and writes the text to the file OUT, whose parent must already
exist. An OUT already holding different text is refused and nothing is
written: this verb never overwrites, identical text is left alone, and a dirty
templates revision still renders. Its sanctioned caller is the private
`render-agents-file` just recipe, whose name and arguments are the stable
interface; this verb behind it may change.
"""

import itertools
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from .chunks import load_chunks
from .discovery import read_fence
from .errors import InputError
from .markers import (
    DYNAMIC_NAMESPACE,
    IDENTIFIER,
    DynamicMap,
    Expansion,
    Routes,
    Verbatim,
    assert_no_residual_markers,
    expand,
)
from .model_tuning import DEFAULT_PIN_MAP, tier_binding
from .paths import AGENTS_FILE_TEMPLATE, HARNESS_DIR, REPO_ROOT, rel
from .rendering import routing_table

HARNESS_TABLE = "harness"
HARNESS_SUFFIX = ".toml"
RESOLVE_METAKEY = "_resolve"
DIRTY_SUFFIX = "**dirty**"
INSTALL_DIR_PARAMETER = "agents-file-install-dir-arg"
SHORT_SHA_PARAMETER = "gen-short-sha"
SCOPE_NAME_PARAMETER = "agents-file-scope-name"
BEFORE_CONTENT_PARAMETER = "existing-user-content-before-rendered-minus-h1"
AFTER_CONTENT_PARAMETER = "existing-user-content-after-rendered"
# The harness key naming the file a harness reads its agents file from.
AGENTS_FILE_KEY = "agents-file"
# The harness key naming the harness's user-global directory.
USER_HARNESS_DIR_KEY = "user-harness-dir"
GLOBAL_SCOPE_NAME = "Global"
PROJECT_SCOPE_NAME = "Project"
BACKUP_PREFIX = "backup."
# (prefix, suffix) of a marker line, whitespace-stripped.
BEGIN_MARKER = ("<!-- vvv-adjagent", "adjagent-vvv -->")
END_MARKER = ("<!-- ^^^-adjagent", "adjagent-^^^ -->")
H1_PREFIX = "# "
# A redirect file's one non-blank line: an import of the file to install into.
REDIRECT_PREFIX = "@"
# Where the directives live outside Global scope, whatever the harness reads.
STANDARD_AGENTS_FILE = "AGENTS.md"
NATIVE_REDIRECT = f"{REDIRECT_PREFIX}{STANDARD_AGENTS_FILE}\n"


@dataclass(frozen=True)
class TemplatesRevision:
    """The repository revision a render comes from: the short HEAD sha, and
    the paths under templates/ that differ from it."""

    sha: str
    dirty: tuple[str, ...]

    @property
    def value(self) -> str:
        return f"{self.sha}{DIRTY_SUFFIX}" if self.dirty else self.sha


def load_harness(name: str, harness_dir: Path = HARNESS_DIR) -> DynamicMap:
    """Load templates/harness/<name>.toml as key -> value.

    Schema: [harness.<key>] tables only, each key an identifier, each table
    holding exactly one string `text`. An unknown name lists the harnesses
    there are.
    """
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
    values: DynamicMap = {}
    for key, entry in data.get(HARNESS_TABLE, {}).items():
        where = f"{rel(path)}: [{HARNESS_TABLE}.{key}]"
        if re.fullmatch(IDENTIFIER, key) is None:
            raise InputError(f"{where}: '{key}' is not a harness key — it must match {IDENTIFIER}")
        if not isinstance(entry, dict) or set(entry) != {"text"} or not isinstance(entry["text"], str):
            raise InputError(f"{where}: must hold exactly one string 'text'")
        values[key] = entry["text"]
    return values


def _required_harness_value(values: DynamicMap, key: str, *, harness: str) -> str:
    if key not in values:
        raise InputError(f"harness '{harness}' defines no [{HARNESS_TABLE}.{key}]")
    return values[key]


def agents_file_name(harness: str, harness_dir: Path = HARNESS_DIR) -> str:
    """The file name a harness reads its agents file from (CLAUDE.md, AGENTS.md)."""
    return _required_harness_value(load_harness(harness, harness_dir), AGENTS_FILE_KEY, harness=harness)


def _is_user_harness_dir(user_harness_dir: str, directory: Path) -> bool:
    return Path(user_harness_dir).expanduser().resolve() == directory.resolve()


def agents_file_scope_name(user_harness_dir: str, directory: Path) -> str:
    """What the agents file in `directory` is scoped to: `Global` for the
    harness's user-global directory, `Project` for a git checkout (a `.git`
    file is a worktree or a submodule), otherwise the directory's own name."""
    if _is_user_harness_dir(user_harness_dir, directory):
        return GLOBAL_SCOPE_NAME
    if (directory / ".git").exists():
        return PROJECT_SCOPE_NAME
    return directory.resolve().name


def _git(repo: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise InputError(f"cannot read the templates revision of {repo}: git {' '.join(args)} failed — {exc}") from exc


def probe_templates_revision(repo: Path = REPO_ROOT) -> TemplatesRevision:
    """The short HEAD sha of `repo`, and every path `git status` reports under
    its templates/ — untracked included, since an untracked template changes
    the render as much as a modified one."""
    sha = _git(repo, "rev-parse", "--short=7", "HEAD").strip()
    dirty = tuple(line for line in _git(repo, "status", "--porcelain", "--", "templates").splitlines() if line)
    return TemplatesRevision(sha=sha, dirty=dirty)


def _is_marker_line(line: str, marker: tuple[str, str]) -> bool:
    stripped = line.strip()
    return stripped.startswith(marker[0]) and stripped.endswith(marker[1])


def split_agents_file(text: str, *, where: str) -> tuple[str, str] | None:
    """The text above the begin marker line and below the end marker line, or
    None for a text with no marker lines. Any other shape than none or one
    begin line followed by one end line is refused, naming `where`."""
    lines = text.split("\n")
    begins = [i for i, line in enumerate(lines) if _is_marker_line(line, BEGIN_MARKER)]
    ends = [i for i, line in enumerate(lines) if _is_marker_line(line, END_MARKER)]
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1 or begins[0] > ends[0]:
        order = " (end before begin)" if len(begins) == len(ends) == 1 else ""
        raise InputError(
            f"{where}: malformed adjagent markers — {len(begins)} begin line(s) and {len(ends)} end line(s){order}; "
            "a file holds none, or one begin line followed by one end line. Nothing written"
        )
    return "\n".join(lines[: begins[0]]), "\n".join(lines[ends[0] + 1 :])


def _without_first_h1(text: str) -> str:
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith(H1_PREFIX):
            del lines[i]
            break
    return "\n".join(lines)


def trim_user_content(text: str) -> str:
    """`text` without its leading and trailing empty or whitespace-only lines,
    or the final line's terminator; the interior is kept exactly."""
    lines = text.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).removesuffix("\r")


def user_content_spans(existing: str | None, *, where: str) -> tuple[str, str]:
    """The trimmed (before, after) user content an install keeps from the
    existing file — empty for no file."""
    if existing is None:
        return "", ""
    parts = split_agents_file(existing, where=where)
    if parts is None:
        return trim_user_content(_without_first_h1(existing)), ""
    above, below = parts
    return trim_user_content(_without_first_h1(above)), trim_user_content(below)


class _Bindings(NamedTuple):
    """What one harness's agents-file render binds: the chunk table, the
    invocation parameters, and the harness file's values."""

    chunks: dict[str, dict]
    dynamic: DynamicMap
    harness: DynamicMap


def _agents_file_bindings(harness: str, directory: Path, revision: TemplatesRevision, harness_dir: Path) -> _Bindings:
    """The bindings for one harness, with the agents-file install directory
    bound to `directory`, which must exist."""
    if not directory.is_dir():
        raise InputError(f"'{directory}' is not an existing directory — the agents file renders into one")
    values = load_harness(harness, harness_dir)
    user_harness_dir = _required_harness_value(values, USER_HARNESS_DIR_KEY, harness=harness)
    chunks = load_chunks()
    dynamic: DynamicMap = {
        **tier_binding(chunks, pin_map=DEFAULT_PIN_MAP).real,
        INSTALL_DIR_PARAMETER: Verbatim(str(directory)),
        SHORT_SHA_PARAMETER: revision.value,
        SCOPE_NAME_PARAMETER: Verbatim(agents_file_scope_name(user_harness_dir, directory)),
    }
    return _Bindings(chunks, dynamic, values)


def _routes(bindings: _Bindings, user_content: DynamicMap) -> Routes:
    """The agents-file render's routes: no family fills `fam`, and
    `user_content` joins the invocation parameters."""
    return routing_table(bindings.chunks, {**bindings.dynamic, **user_content}, {}, bindings.harness)


def _assert_agents_file_structure(expansion: Expansion, *, template: Path) -> None:
    """The render holds one marker pair, the before-content value once above
    it and the after-content value once below it."""
    where = rel(template)
    text = expansion.text
    if split_agents_file(text, where=where) is None:
        raise InputError(f"{where}: the agents file renders no adjagent marker lines — it needs one begin/end pair")
    lines = text.split("\n")
    starts = list(itertools.accumulate((len(line) + 1 for line in lines), initial=0))
    begin = next(i for i, line in enumerate(lines) if _is_marker_line(line, BEGIN_MARKER))
    end = next(i for i, line in enumerate(lines) if _is_marker_line(line, END_MARKER))
    for parameter, placed, side in (
        (BEFORE_CONTENT_PARAMETER, lambda offset: offset < starts[begin], "above the begin"),
        (AFTER_CONTENT_PARAMETER, lambda offset: offset >= starts[end + 1], "below the end"),
    ):
        marker = f"@!{DYNAMIC_NAMESPACE}.{parameter}!@"
        offsets = [span.offset for span in expansion.verbatim if span.marker == marker]
        if len(offsets) != 1 or not placed(offsets[0]):
            raise InputError(f"{where}: {marker} must render exactly once, {side} marker line")


def _agents_file_body(bindings: _Bindings, *, template: Path, harness: str, before: str = "", after: str = "") -> str:
    _, body = read_fence(template)
    user_content: DynamicMap = {BEFORE_CONTENT_PARAMETER: Verbatim(before), AFTER_CONTENT_PARAMETER: Verbatim(after)}
    expansion = expand(body, _routes(bindings, user_content), args={})
    assert_no_residual_markers(expansion, path=template, name=f"{harness} agents file")
    _assert_agents_file_structure(expansion, template=template)
    return expansion.text


def render_agents_file_text(
    harness: str,
    directory: Path,
    revision: TemplatesRevision,
    *,
    template: Path = AGENTS_FILE_TEMPLATE,
    harness_dir: Path = HARNESS_DIR,
) -> str:
    """The agents file for one harness, as it reads when installed in
    `directory` with no user content. The fence's `_resolve` entries are not
    consulted: the caller names where the text goes."""
    bindings = _agents_file_bindings(harness, directory, revision, harness_dir)
    return _agents_file_body(bindings, template=template, harness=harness)


def _resolved_output_paths(bindings: _Bindings, *, template: Path, directory: Path) -> list[Path]:
    fence, _ = read_fence(template)
    routes = _routes(bindings, {})
    paths = []
    for entry in _resolve_entries(fence, template):
        resolved = expand(entry, routes, args={})
        assert_no_residual_markers(resolved, path=template, name=RESOLVE_METAKEY)
        path = Path(resolved.text)
        if path.parent != directory:
            raise InputError(f"{rel(template)}: '{entry}' resolves to {path}, which is not directly inside {directory}")
        paths.append(path)
    return paths


def _resolve_entries(fence: dict | None, template: Path) -> list[str]:
    """The `text` of every [[outputs._resolve]] entry, refusing any other shape."""
    outputs = (fence or {}).get("outputs")
    if not isinstance(outputs, dict) or set(outputs) != {RESOLVE_METAKEY}:
        raise InputError(f"{rel(template)}: the fence must declare [[outputs.{RESOLVE_METAKEY}]] and no other output")
    entries = outputs[RESOLVE_METAKEY]
    if not isinstance(entries, list) or not entries:
        raise InputError(f"{rel(template)}: outputs.{RESOLVE_METAKEY} must be a non-empty list of tables")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"text"} or not isinstance(entry["text"], str):
            raise InputError(f"{rel(template)}: each outputs.{RESOLVE_METAKEY} entry holds exactly one string 'text'")
    return [entry["text"] for entry in entries]


def _backup_path(path: Path) -> Path:
    return path.with_name(BACKUP_PREFIX + path.name)


def _refuse_unless_regular_or_absent(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise InputError(f"{path} is a symlink or not a regular file — refusing to write through it; nothing written")


def _read_existing(path: Path) -> str | None:
    """The file's text exactly as stored — line endings untranslated — or None
    when there is no file."""
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            return stream.read()
    except UnicodeDecodeError as exc:
        raise InputError(f"{path} is not UTF-8 text — nothing written") from exc


class AgentsFilePlan(NamedTuple):
    """One planned output: the file written, its current text (None when
    absent), the text it receives, and the redirect file followed to reach it
    (None when the destination was written directly)."""

    path: Path
    existing: str | None
    text: str
    redirect: Path | None


def _redirect_reference(text: str) -> str | None:
    """The <path> of a text whose only non-blank line is `@<path>`, else None."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) != 1 or not lines[0].startswith(REDIRECT_PREFIX):
        return None
    return lines[0].removeprefix(REDIRECT_PREFIX) or None


def _redirect_target(redirect: Path, reference: str, *, directory: Path) -> Path:
    """Where a redirect points, refused unless it is one hop to a regular or
    absent file inside `directory`."""
    target = redirect.parent / reference
    refusal = f"{redirect} redirects to {target}"
    if not target.resolve().is_relative_to(directory.resolve()):
        raise InputError(f"{refusal}, which resolves outside {directory} — merge by hand; nothing written")
    if not target.parent.is_dir():
        raise InputError(f"{refusal}, whose directory does not exist — nothing written")
    _refuse_unless_regular_or_absent(target)
    existing = _read_existing(target)
    if existing is not None and _redirect_reference(existing) is not None:
        raise InputError(
            f"{refusal}, which is itself a redirect — the chain is more than one hop; merge by hand. Nothing written"
        )
    return target


def _follow_redirect(destination: Path, *, directory: Path) -> tuple[Path, str | None, Path | None]:
    """The file an install into `destination` writes, its current text, and
    the redirect followed one hop to reach it (None when there is none)."""
    _refuse_unless_regular_or_absent(destination)
    existing = _read_existing(destination)
    reference = None if existing is None else _redirect_reference(existing)
    if reference is None:
        return destination, existing, None
    path = _redirect_target(destination, reference, directory=directory)
    return path, _read_existing(path), destination


def _native_redirect_plan(native: Path) -> AgentsFilePlan:
    """The native file outside Global scope, as the redirect to the AGENTS.md
    beside it: written when absent, kept as it is when it already redirects
    there, refused when it holds anything else."""
    _refuse_unless_regular_or_absent(native)
    existing = _read_existing(native)
    if existing is None:
        return AgentsFilePlan(native, None, NATIVE_REDIRECT, None)
    reference = _redirect_reference(existing)
    if reference is not None and native.parent / reference == native.with_name(STANDARD_AGENTS_FILE):
        return AgentsFilePlan(native, existing, existing, None)
    raise InputError(
        f"{native} holds its own content, but outside the harness's user-global directory the agents file "
        f"installs into {STANDARD_AGENTS_FILE} and {native.name} holds only the redirect "
        f"'{NATIVE_REDIRECT.strip()}' — move its content into {native.with_name(STANDARD_AGENTS_FILE)} and "
        f"replace it with '{NATIVE_REDIRECT.strip()}' by hand. Nothing written"
    )


def render_agents_file(
    harness: str,
    directory: Path,
    revision: TemplatesRevision,
    *,
    template: Path = AGENTS_FILE_TEMPLATE,
    harness_dir: Path = HARNESS_DIR,
) -> list[AgentsFilePlan]:
    """Plan the install of one harness's agents file into `directory`, one
    plan per `_resolve` entry, each destination directly inside `directory`
    and followed one hop when it is a redirect, the existing file's user
    content carried into the new text. Outside Global scope a native-file
    output goes to AGENTS.md instead, and its native file is planned last as
    the redirect to it. Reads, and writes nothing."""
    bindings = _agents_file_bindings(harness, directory, revision, harness_dir)
    native_name = _required_harness_value(bindings.harness, AGENTS_FILE_KEY, harness=harness)
    relocate = native_name != STANDARD_AGENTS_FILE and not _is_user_harness_dir(
        bindings.harness[USER_HARNESS_DIR_KEY], directory
    )
    plans, redirects = [], []
    for destination in _resolved_output_paths(bindings, template=template, directory=directory):
        if relocate and destination.name == native_name:
            redirects.append(_native_redirect_plan(destination))
            destination = destination.with_name(STANDARD_AGENTS_FILE)
        path, existing, redirect = _follow_redirect(destination, directory=directory)
        _refuse_unless_regular_or_absent(_backup_path(path))
        before, after = user_content_spans(existing, where=str(path))
        text = _agents_file_body(bindings, template=template, harness=harness, before=before, after=after)
        plans.append(AgentsFilePlan(path, existing, text, redirect))
    plans += redirects
    written = [plan.path for plan in plans]
    if len(set(written)) != len(written):
        raise InputError(
            f"the install into {directory} would write one file twice ({', '.join(map(str, written))}) — "
            "a redirect points back at a file this install writes; untangle it by hand. Nothing written"
        )
    return plans


def install_agents_file(
    harness: str,
    directory: Path,
    revision: TemplatesRevision,
    *,
    template: Path = AGENTS_FILE_TEMPLATE,
    harness_dir: Path = HARNESS_DIR,
) -> None:
    """Install one harness's agents file into `directory` by block replacement,
    refusing a dirty revision, and planning every output before writing any."""
    if revision.dirty:
        raise InputError(
            f"templates/ has uncommitted changes ({', '.join(revision.dirty)}) — commit them before installing; "
            "nothing written"
        )
    plans = render_agents_file(harness, directory, revision, template=template, harness_dir=harness_dir)
    for path, existing, text, redirect in plans:
        via = ""
        if redirect is not None:
            via = f" (redirect {redirect.name} → {path.name if path.parent == redirect.parent else path})"
        if existing == text:
            print(f"unchanged {path}{via}")
            continue
        if existing is None:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path}{via} — no prior file, no backup")
            continue
        backup = _backup_path(path)
        shutil.copyfile(path, backup)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path}{via} — prior content backed up to {backup}")
        if split_agents_file(existing, where=str(path)) is None:
            print(
                f"{path} had no adjagent markers: all of its prior content is kept above the block as your own, "
                "and any rules it duplicates from the block are now yours to delete"
            )


def write_agents_file_renders(renders: list[tuple[Path, str]]) -> None:
    """Write each render, refusing — before writing any — if one would replace
    a file holding different text. A file already holding the render is left
    alone."""
    differing = []
    for path, text in renders:
        if not path.exists():
            continue
        try:
            same = path.read_text(encoding="utf-8") == text
        except UnicodeDecodeError:
            same = False
        if not same:
            differing.append(path)
    if differing:
        raise InputError(
            "refusing to overwrite existing file(s) with different content: "
            + ", ".join(str(path) for path in differing)
            + " — nothing written"
        )
    for path, text in renders:
        if path.exists():
            print(f"unchanged {path}")
        else:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path}")
