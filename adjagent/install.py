"""`python3 -m adjagent install ROOT`: every definition rendered into ROOT's agents/ and commands/,
and the shipped packages copied beside them. Overwrites without ceremony: the consumer's git is the
record of what an install changed."""

import shutil
from pathlib import Path

from adjagent.context import Render
from adjagent.errors import InputError
from adjagent.render import GENERATED_NOTICE, render_all, write_renders

REPO_ROOT = Path(__file__).resolve().parent.parent
# (source directory in this repository, destination below ROOT). The destination is a consumer
# contract — runner snippets and definition bodies name it — so it is stated, never derived.
SHIPPED_PACKAGES = (("kb_tools", "agents/kb_tools"), ("liaison_tools", "agents/liaison_tools"))
# Never shipped, matched at any depth: test suites and caches, safety copies, and this repository's
# own project documents. README.md is absent on purpose: a package that grows one ships it.
EXCLUDED_DIRS = frozenset({"tests", "__pycache__", ".pytest_cache"})
EXCLUDED_NAMES = frozenset(
    {".DS_Store", "SPEC.md", "ARCHITECTURE.md", "CONVENTIONS.md", "THESIS.md", "ROADMAP.md", "AGENTS.md", "CLAUDE.md"}
)
EXCLUDED_SUFFIX = ".bak"
# Copied files whose type takes a `#` comment carry the one-line installed banner; every other file
# — the .tmpl.md templates, the .lua filter — is copied byte-verbatim.
STAMPED_SUFFIXES = frozenset({".py", ".sh", ".toml", ".mk", ".just"})
SURFACES = ("agents", "commands")
_GENERATED = b"# !GENERATED! from "


def _shipped(relative: Path) -> bool:
    return not (
        EXCLUDED_DIRS.intersection(relative.parts[:-1])
        or relative.name in EXCLUDED_NAMES
        or relative.suffix == EXCLUDED_SUFFIX
    )


def package_copies(root: Path) -> list[tuple[Path, Path]]:
    """(source file, target under `root`) for every file the shipped packages deliver."""
    return [
        (source, root / destination / source.relative_to(REPO_ROOT / package))
        for package, destination in SHIPPED_PACKAGES
        for source in sorted((REPO_ROOT / package).rglob("*"))
        if source.is_file() and _shipped(source.relative_to(REPO_ROOT / package))
    ]


def stamped(data: bytes, *, origin: str) -> bytes:
    """`data` with the one-line installed banner on top, or below its shebang line."""
    banner = f"# !INSTALLED! from {origin} — {GENERATED_NOTICE}\n".encode("utf-8")
    if not data.startswith(b"#!"):
        return banner + data
    shebang, _, rest = data.partition(b"\n")
    return shebang + b"\n" + banner + rest


def _refuse_root(root: Path) -> None:
    if not root.is_dir():
        raise InputError(f"install root '{root}' is not an existing directory")
    resolved = root.resolve()
    if resolved == REPO_ROOT or any(resolved.is_relative_to(REPO_ROOT / package) for package, _ in SHIPPED_PACKAGES):
        raise InputError(
            f"install root '{root}' is this repository or inside a package source it copies from — "
            "install into the project that consumes it"
        )


def _is_ours(path: Path) -> bool:
    """A file whose frontmatter opens with a `!GENERATED!` banner: line 2 in 1.0, line 3 pre-1.0."""
    head = path.read_bytes().split(b"\n", 3)[:3]
    return head[0] == b"---" and any(line.startswith(_GENERATED) for line in head[1:])


def prune(root: Path, *, keep: set[Path]) -> list[Path]:
    """Remove every regular file under ROOT's surfaces, outside the package destinations, that is not
    in `keep`, would ship, and is ours; then each directory that leaves empty, up to its surface."""
    destinations = [root / destination for _, destination in SHIPPED_PACKAGES]
    stale = [
        path
        for surface in SURFACES
        for path in sorted((root / surface).rglob("*"))
        if path not in keep
        and path.is_file()
        and not path.is_symlink()
        and not any(path.is_relative_to(destination) for destination in destinations)
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


def install(root: Path, ctx: Render, *, verbose: bool) -> None:
    """Render, replace each package destination whole with a stamped copy, write the renders over what
    is there, then prune. A refusal of the root or of the render writes nothing."""
    _refuse_root(root)
    renders = render_all(ctx)
    copies = package_copies(root)
    for _, destination in SHIPPED_PACKAGES:
        shutil.rmtree(root / destination, ignore_errors=True)
    for source, target in copies:
        data = source.read_bytes()
        if source.suffix in STAMPED_SUFFIXES:
            data = stamped(data, origin=source.relative_to(REPO_ROOT).as_posix())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        shutil.copymode(source, target)
    written = write_renders(root, renders)
    pruned = prune(root, keep={*written, *(target for _, target in copies)})
    print(f"installed: {len(written)} definitions, {len(copies)} package files → {root}")
    for path in pruned:
        print(f"pruned {path}")
    if verbose:
        for path in [*(target for _, target in copies), *written]:
            print(f"wrote {path}")
