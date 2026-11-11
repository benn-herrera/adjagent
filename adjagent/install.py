"""`python3 -m adjagent install PLUGIN TARGET`, once `adjagent.install_target` has resolved the harness
directory and the project root from TARGET. The plugin is written into ROOT, the harness's `plugin_dir`
below the harness directory — the harness directory itself where that is empty: every definition the
plugin ships rendered into ROOT's agents/, commands/ and skills/, each shipped package whose owning
definition rendered copied to its stated destination — the docdicer tools inside the docdicer skill's
directory, replacing any venv their launcher built there, the development scripts inside the
development skill's, the kb-tools package inside the kbase skill's, with the `kbase` MCP entry — and,
for each copied package carrying runner snippets, its include line in the consumer's runner file; each
file the installing harness ships copied into ROOT as it stands,
the harness's guardrail hook registered in a file of its own under ROOT where one install-time run of
it succeeds; a harness-directory plugin installed below its project root also gets its agents file in its
harness directory. Overwrites without ceremony only what carries this repository's banner, refusing
over any other file at a path it writes: the consumer's git is the record of what an install changed."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Iterable
from functools import partial
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from adjagent import install_base
from adjagent.agents_file import (
    AgentsFileWrite,
    FollowedAgentsFile,
    checked_agents_file,
    checked_followed_agents_file,
    write_agents_file,
    write_followed_agents_file,
)
from adjagent.context import Render
from adjagent.errors import InputError
from adjagent.harness import KBASE_OWNER, GuardrailHook, Harness, HarnessFile
from adjagent.install_base import KB_TOOLS_DIR, PACKAGE_ROOT, report_left_alone
from adjagent.install_target import user_dir_harnesses
from adjagent.preflight import VENV_DIR, run_preflighted
from adjagent.render import (
    GENERATED_MARK,
    GENERATED_NOTICE,
    harness_file_text,
    render_all,
    shipped_harness_files,
    write_renders,
)
from adjagent.runner_file import JUSTFILE_NAMES, MAKEFILE_NAMES, SnippetSet, check_runner, install_include_lines


def uncommitted_sources() -> tuple[str, ...]:
    """Every `git status --porcelain` line under this package's directory, untracked included: the
    agents file is a function of the package, so an uncommitted change is an unpublished one. Outside
    a checkout there is no commit state, so nothing is uncommitted and git is not run."""
    if install_base.REPO_ROOT is None:
        return ()
    command = ["git", "-C", str(install_base.REPO_ROOT), "status", "--porcelain", "--", PACKAGE_ROOT.name]
    try:
        out = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise InputError(f"cannot read the commit state of {PACKAGE_ROOT}: {exc}") from exc
    return tuple(line for line in out.splitlines() if line)


# The docdicer tools package, inside the docdicer skill's own directory: its launcher script, and the
# virtual environment that script builds beside itself on its next run — not install output, so the
# install replaces it with the package.
DOCDICER_TOOLS_PACKAGE = "skills/docdicer/tools"
# The development scripts package, inside the development skill's own directory: the cold-read runner.
DEVELOPMENT_SCRIPTS_PACKAGE = "skills/development/scripts"


class ShippedPackage(NamedTuple):
    """A package an install copies: its source directory in this package, its destination below ROOT,
    the definition it ships with, and the runner snippets it carries, their directory below the
    destination, whose include line a project install writes into the project's runner file."""

    source: str
    destination: str
    owner: str
    snippets: SnippetSet | None = None

    def installed_snippets(self) -> SnippetSet | None:
        """`snippets` with its directory below ROOT, as an include line names it."""
        if self.snippets is None:
            return None
        return self.snippets._replace(directory=f"{self.destination}/{self.snippets.directory}")


# Every package a project install may ship, each where its owner renders; a user-level install ships
# none. A destination is a consumer contract — a skill names its own tools relative to its directory,
# and an installed runner line names its snippets directory — so each is stated, never derived.
# `package_copies`, the `!INSTALLED!` stamping, the destination replacement and the runner include
# lines all read this table; the include lines land in its order.
SHIPPED_PACKAGES: tuple[ShippedPackage, ...] = (
    ShippedPackage(
        "docdicer-tools",
        DOCDICER_TOOLS_PACKAGE,
        "docdicer",
        SnippetSet("docdicer", "runner-snippets", {"just": "docdicer.just", "make": "docdicer.mk"}),
    ),
    ShippedPackage("development-tools", DEVELOPMENT_SCRIPTS_PACKAGE, "development"),
    ShippedPackage(
        "kb-tools",
        KB_TOOLS_DIR,
        KBASE_OWNER,
        SnippetSet("kb", "runner-snippets", {"just": "kb.just", "make": "kb.mk"}),
    ),
)
# The harness resources: files a harness ships that land in ROOT as they stand, copied and never
# rendered. The directory below this one in the source is the harness's own
# name, and the destination is ROOT itself — both stated, neither derived from a directory listing.
HARNESS_RESOURCES_SOURCE = "harnesses/resources"
# The interpreter the install-time probe runs a guardrail hook script under, found on PATH, and how long
# that run may take before it counts as failed.
GUARDRAIL_INTERPRETER = "perl"
GUARDRAIL_PROBE_SECONDS = 5.0
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
# path a payload names: `adjagent/definitions/<module>.py`. A file opening with one of these is one
# this repository wrote; the bare mark followed by anything else is somebody else's file.
_GENERATED = f"# {GENERATED_MARK}".encode("utf-8")
_COMMENT_GENERATED = f"<!-- {GENERATED_MARK}".encode("utf-8")
_PAYLOAD_PATH = b"adjagent/"
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


def package_copies(root: Path, packages: Iterable[ShippedPackage]) -> list[tuple[Path, Path]]:
    """(source file, target under `root`) for every file `packages` deliver, each landing under its
    package's destination."""
    return [
        (source, root / package.destination / source.relative_to(PACKAGE_ROOT / package.source))
        for package in packages
        for source in sorted((PACKAGE_ROOT / package.source).rglob("*"))
        if source.is_file() and _shipped(source.relative_to(PACKAGE_ROOT / package.source))
    ]


def harness_resource_copies(root: Path, *, harness: str) -> list[tuple[Path, Path]]:
    """(source file, target under `root`) for every file `harness` ships: `resources/<harness>/` in this
    package, delivered into ROOT, so `resources/claude/hooks/guardrail.pl` lands at
    `<ROOT>/hooks/guardrail.pl`.

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


def _bannered(line: bytes, prefix: bytes) -> bool:
    """Whether `line` opens with `prefix` and then a payload naming a module path this repository
    writes — not merely the mark, which any hand-written comment can carry."""
    return line.startswith(prefix) and line[len(prefix) :].startswith(_PAYLOAD_PATH)


def _is_ours(path: Path) -> bool:
    """A generated file, by the carrier it opens with: an HTML comment on line 1 — how a skill's supporting
    file holds its banner, having no frontmatter — or a frontmatter block whose banner sits on line 2.
    A file that cannot be read is not ours."""
    try:
        with path.open("rb") as handle:
            head = [handle.readline() for _ in range(2)]
    except OSError:
        return False
    return _bannered(head[0], _COMMENT_GENERATED) or (head[0].rstrip() == b"---" and _bannered(head[1], _GENERATED))


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


def _refuse_foreign_targets(
    *,
    render_targets: Iterable[Path],
    resource_targets: Iterable[Path],
    harness_targets: Iterable[tuple[Path, str]],
) -> None:
    """Refuse an install that would overwrite a file it did not write. A target that exists passes only
    where the claim its class makes of it holds: a render by its generated banner, a resource by its
    installed header, a harness-rendered file — `(path, marker)` — by the marker that file states about
    itself. Every failing path is named in the one refusal, so the operator clears them in one pass."""
    claims = [
        *((target, _is_ours) for target in render_targets),
        *((target, _is_our_resource) for target in resource_targets),
        *((target, partial(_is_our_harness_file, marker=marker)) for target, marker in harness_targets),
    ]
    foreign = [target for target, ours in claims if target.exists() and not ours(target)]
    if foreign:
        named = ", ".join(f"'{target}'" for target in foreign)
        raise InputError(
            f"install would overwrite files it did not write: {named} — move or remove each, then re-install"
        )


def prune(root: Path, *, keep: set[Path]) -> list[Path]:
    """Remove every regular file under ROOT's surfaces that is not in `keep`, would
    ship, and is ours; then each directory that leaves empty, walking upward from the file to the first
    directory that still holds anything, the surface included and ROOT never.

    Package destinations sit inside the skills surface — `skills/kbase/kb-tools/`,
    `skills/docdicer/tools/` and `skills/development/scripts/` — and no destination is carved out by
    name. None needs to be: a copied package file carries the `!INSTALLED!` banner or none, never the
    generated one `_is_ours` reads, so it is untouched here rather than pruned, and a `.venv` below a
    destination is outside the would-ship vocabulary, so its files never enter the stale list. Every file under a surface is thus either ours
    or untouched. A definition of ours this run did not write — one its plugin does not ship — is stale
    and removed, while one the run wrote is in `keep`. Nothing outside ROOT's surfaces is walked, so
    another plugin's ROOT beside this one is never read.

    A harness-rendered file such as the plugin manifest or `.mcp.json` carries no generated banner, so
    wherever it sits it is neither pruned nor read as a stale render. Each is rendered on every install
    of a plugin that ships its owner, and ROOT is that plugin's alone, so none has a stale form to
    remove."""
    stale = [
        path
        for surface in SURFACES
        for path in _files_below(root / surface)
        if path not in keep and path.is_file() and _shipped(path.relative_to(root)) and _is_ours(path)
    ]
    for path in stale:
        path.unlink()
    for path in stale:
        parent = path.parent
        # An earlier stale file's walk may already have removed this one's directory.
        while parent != root and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    return stale


def _files_below(top: Path) -> list[Path]:
    """Every non-directory `os.walk` lists below `top`, sorted."""
    return sorted(Path(directory, name) for directory, _, names in os.walk(top) for name in names)


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


def _earlier_guardrail(root: Path, *, guardrail: GuardrailHook) -> list[Path]:
    """What an earlier install left registering the guardrail: its script under ROOT where it carries
    the installed header, and its registration under ROOT where that carries its marker."""
    script = root / guardrail.script
    left = [script] if _is_our_resource(script) else []
    registration = root / guardrail.registration.path
    if _is_our_harness_file(registration, marker=guardrail.registration.marker):
        left.append(registration)
    return left


def _lexical(path: Path) -> Path:
    """`path` made absolute and normalised."""
    return Path(os.path.normpath(path.absolute()))


def _harness_relpath(root: Path, project: Path) -> str:
    """ROOT's path relative to the project root, both as spelled — the `<harness-relpath>` every
    consumer-facing line under the project spells."""
    return _lexical(root).relative_to(project).as_posix()


def _installs_agents_file(harness_dir: Path, harness: Harness, *, project: Path) -> bool:
    """Whether an install into `harness_dir` writes an agents file there: a harness-directory plugin installed
    below its project root, judged as both are spelled."""
    return harness.is_harness_dir_plugin and _lexical(harness_dir) != project


def _is_project_install_of_a_nested_plugin(harness: Harness, *, user_level: bool) -> bool:
    """Whether an install is a project install of a nested plugin. Such an install keeps the agents-file
    block current in the one place it lives and, for each shipped package carrying runner snippets,
    writes its include line in the project's runner file. A harness-directory plugin's agents file is its
    own, and it is no repo project, so it has no consumer runner file and none is created."""
    return not user_level and not harness.is_harness_dir_plugin


def _guardrail_in_play(harness: Harness, *, user_level: bool) -> GuardrailHook | None:
    """The guardrail hook an install delivers, before the probe decides whether it registers: the
    harness's own on a project install, none on a user-level one."""
    return None if user_level else harness.guardrail


def _resource_copies(root: Path, *, harness: Harness, user_level: bool) -> list[tuple[Path, Path]]:
    """The harness resources an install copies: every one on a project install, and only the entry that
    registers the plugin on a user-level one, which delivers no guardrail."""
    copies = harness_resource_copies(root, harness=harness.name)
    if not user_level:
        return copies
    if not harness.entry_resource:
        return []
    return [(source, target) for source, target in copies if target == root / harness.entry_resource]


def _clear_package_destination(destination: Path) -> None:
    """Leave an empty directory at `destination`, or nothing, for the package copy: a directory is
    emptied and stays; anything else there is unlinked."""
    if destination.is_dir():
        for entry in destination.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
    else:
        destination.unlink(missing_ok=True)


def _report_shadowing(root: Path, *, harness: Harness, files: Iterable[HarnessFile], user_level: bool) -> None:
    """Report a plugin the harness loads in place of another of the same name, for a harness whose
    user-level plugin does so: a user-level install always shadows every project's; a project install
    is shadowed where the user-level ROOT holds every one of `files`, the harness's own files this
    install renders, each carrying the marker that makes it ours."""
    if not harness.user_plugin_shadows:
        return
    if user_level:
        report_left_alone(
            f"{root} is user-level: the harness loads it in place of every project's plugin of the same name"
        )
        return
    user_root = harness.user_dir / harness.plugin_dir
    if all(_is_our_harness_file(user_root / file.path, marker=file.marker) for file in files):
        report_left_alone(
            f"{root} is shadowed by {user_root}, a user-level plugin of the same name: the harness loads that "
            "one, and this project's plugin — its tuning, version and MCP server — does not load"
        )


def install(
    harness_dir: Path,
    ctx: Render,
    *,
    verbose: bool,
    project_root: Path | None = None,
    uncommitted: Callable[[], tuple[str, ...]],
    real_harness_dir: Path | None = None,
    real_project: Path | None = None,
    global_dir: Path | None = None,
) -> None:
    """Install the plugin `ctx` renders into ROOT, `harness_dir / ctx.bound_harness.plugin_dir`. Every
    check runs first, so a refusal writes nothing; then the writes; then the removals.

    `verbose` prints each file written. `project_root` is the project the harness directory belongs to,
    defaulting to `harness_dir`. `uncommitted` names the uncommitted changes to the sources, called only
    where a write must refuse on them. `real_harness_dir` and `real_project` are the harness directory
    and project root the install is for, where `harness_dir` and `project_root` are a scratch copy of
    them, each defaulting to the path written. `global_dir` is the harness's user harness directory, or a
    scratch copy of it, defaulting to the directory itself."""
    root = harness_dir / ctx.bound_harness.plugin_dir
    project = _lexical(harness_dir if project_root is None else Path(project_root))
    user_level = ctx.harness.name in user_dir_harnesses(harness_dir if real_harness_dir is None else real_harness_dir)
    harness_relpath = _harness_relpath(root, project)
    # Every check runs before the first write: the render, the guardrail probe that decides whether its
    # script is a resource target, each render, harness-file and resource target the install would
    # overwrite, the runner file where a shipped package carries runner snippets, and the agents file's.
    # ROOT itself is created only after all of them.
    renders = render_all(ctx)
    packages = [] if user_level else [package for package in SHIPPED_PACKAGES if ctx.ships(package.owner)]
    package_files = package_copies(root, packages)
    resource_files = _resource_copies(root, harness=ctx.harness, user_level=user_level)
    guardrail = _guardrail_in_play(ctx.bound_harness, user_level=user_level)
    snippet_sets = [snippets for package in packages if (snippets := package.installed_snippets()) is not None]
    writes_include_lines = bool(snippet_sets) and _is_project_install_of_a_nested_plugin(
        ctx.harness, user_level=user_level
    )
    guardrail_skipped: str | None = None
    own_files = shipped_harness_files(ctx)
    harness_files = list(own_files)
    if guardrail is not None:
        script = PACKAGE_ROOT / HARNESS_RESOURCES_SOURCE / ctx.harness.name / guardrail.script
        guardrail_skipped = _guardrail_probe(script, project=project, temp_dir=ctx.harness.project_temp_dir)
        if guardrail_skipped is not None:
            resource_files = [(source, target) for source, target in resource_files if source != script]
        else:
            harness_files.append(guardrail.registration)
            registration = harness_file_text(guardrail.registration, ctx)
            renders = (*renders, (PurePosixPath(guardrail.registration.path), registration))
    registers_guardrail = guardrail is not None and guardrail_skipped is None
    # The harness's own rendered files are a class of their own at the refusal: their ownership is the
    # marker each states, not a banner a JSON file has no way to carry.
    harness_markers = {PurePosixPath(file.path): file.marker for file in harness_files}
    _refuse_foreign_targets(
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
    if writes_include_lines:
        check_runner(project)
    agents_file: AgentsFileWrite | None = None
    if _installs_agents_file(harness_dir, ctx.harness, project=project):
        agents_file = checked_agents_file(harness_dir, ctx.harness, ctx.plugin, real_directory=real_harness_dir)
    followed: FollowedAgentsFile | None = None
    if _is_project_install_of_a_nested_plugin(ctx.harness, user_level=user_level):
        followed = checked_followed_agents_file(
            project,
            ctx.harness,
            ctx.plugin,
            global_dir=ctx.harness.user_dir if global_dir is None else global_dir,
            uncommitted=uncommitted,
            real_project=real_project,
        )

    root.mkdir(parents=True, exist_ok=True)
    for package in packages:
        _clear_package_destination(root / package.destination)
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

    pruned = prune(root, keep={*written, *(target for _, target in copies)})
    print(f"installed: {len(written)} rendered files, {len(copies)} copied files → {root}")
    for path in pruned:
        print(f"pruned {path}")
    if verbose:
        for path in [*(target for _, target in copies), *written]:
            print(f"wrote {path}")
    if writes_include_lines:
        install_include_lines(project, snippet_sets, harness_relpath=harness_relpath, real_project=real_project)
    if guardrail is not None and not registers_guardrail:
        # Neither prune nor the one-way copy removes what an earlier install delivered, so it is named.
        earlier = _earlier_guardrail(root, guardrail=guardrail)
        left = f"; left in place from an earlier install: {', '.join(str(path) for path in earlier)}" if earlier else ""
        report_left_alone(f"guardrail hook skipped, neither installed nor registered: {guardrail_skipped}{left}")
    _report_shadowing(root, harness=ctx.bound_harness, files=own_files, user_level=user_level)
    if ctx.harness.reload_rule:
        print(ctx.harness.reload_rule)


def _install_managed_paths(
    harness_dir: Path,
    ctx: Render,
    *,
    project: Path,
    user_level: bool,
) -> list[tuple[Path, list[str]]]:
    """(base, paths relative to it) for everything an install of `ctx` into `harness_dir` may read or
    write: the project root as spelled, the harness directory, ROOT and the harness's user harness
    directory, in that order, ROOT keeping its position below the harness directory. Named from what
    the install writes by, never a listing of a directory, which in a user harness directory holds the
    operator's own trees. Each decision the install takes on what only its run knows — the guardrail
    probe — is taken here as though it went the way that writes more, and every package destination
    and harness-rendered file is named whichever definitions the plugin ships."""
    harness, bound = ctx.harness, ctx.bound_harness
    root = harness_dir / bound.plugin_dir
    under_harness_dir: list[str] = []
    under_root = [
        *SURFACES,
        *(package.destination for package in SHIPPED_PACKAGES),
        *(
            target.relative_to(root).as_posix()
            for _, target in _resource_copies(root, harness=harness, user_level=user_level)
        ),
        *(file.path for file in bound.harness_files),
    ]
    guardrail = _guardrail_in_play(bound, user_level=user_level)
    if guardrail is not None:
        under_root.append(guardrail.registration.path)
    under_project: list[str] = []
    if _is_project_install_of_a_nested_plugin(harness, user_level=user_level):
        under_project += [*JUSTFILE_NAMES, *MAKEFILE_NAMES]
    if _installs_agents_file(harness_dir, harness, project=project):
        write = checked_agents_file(harness_dir, harness, ctx.plugin)
        under_harness_dir += [path.relative_to(harness_dir).as_posix() for path in write.paths]
    global_dir = harness.user_dir
    under_global_dir: list[str] = []
    if _is_project_install_of_a_nested_plugin(harness, user_level=user_level):
        followed = checked_followed_agents_file(
            project, harness, ctx.plugin, global_dir=global_dir, uncommitted=lambda: ()
        )
        for path in followed.paths:
            if path.is_relative_to(project):
                under_project.append(path.relative_to(project).as_posix())
            else:
                under_global_dir.append(path.relative_to(global_dir).as_posix())
    return [
        (project, under_project),
        (harness_dir, under_harness_dir),
        (root, under_root),
        (global_dir, under_global_dir),
    ]


def preflighted_install(
    harness_dir: Path,
    ctx: Render,
    *,
    verbose: bool,
    project_root: Path | None = None,
    uncommitted: Callable[[], tuple[str, ...]],
    dry_run: bool = False,
) -> None:
    """`install` behind the preflight: run first into a scratch copy of the paths it manages, with the
    real harness directory and project root as its identity. Where that changed nothing, the harness
    directory is reported up to date and nothing in the target is touched — no file, no package
    destination, no `.venv`. With `dry_run`, what would be created, changed and removed is printed
    relative to the project root, and nothing is written. Otherwise the install runs exactly as
    `install` does. Every printed path and refusal names the real target."""
    project = _lexical(harness_dir if project_root is None else Path(project_root))
    user_level = ctx.harness.name in user_dir_harnesses(harness_dir)
    managed = _install_managed_paths(
        harness_dir,
        ctx,
        project=project,
        user_level=user_level,
    )
    run_preflighted(
        managed,
        install=lambda bases: install(
            bases[1],
            ctx,
            verbose=verbose,
            project_root=bases[0],
            uncommitted=uncommitted,
            real_harness_dir=harness_dir,
            real_project=project,
            global_dir=bases[3],
        ),
        dry_run=dry_run,
        target=harness_dir,
        report_root=project,
    )
