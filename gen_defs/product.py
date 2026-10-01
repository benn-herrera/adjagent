"""gen_defs — what the install product holds: shipped-package table, exclusion vocabulary, destinations, copy set, root guard."""

import shutil
from pathlib import Path

from .errors import InputError
from .paths import REPO_ROOT, rel

# The only files under agents/ and commands/ an install does NOT deliver.
# Everything else is copied verbatim — there is no inclusion list, so a new
# definition or tool file ships without an enrollment step. Directory names
# match at any depth; the suffix catches the generator's own safety copies.
INSTALL_EXCLUDED_DIRS = frozenset({"tests", "__pycache__", ".pytest_cache"})
INSTALL_EXCLUDED_NAMES = frozenset({".DS_Store"})
INSTALL_EXCLUDED_SUFFIX = ".bak"

# Project documentation: the closed vocabulary of filenames that document a
# project TO ITS OWN DEVELOPERS. A consuming project installs the code, not the
# project the code came from — a shipped package's SPEC and ARCHITECTURE state
# its contract for someone changing it here, its CONVENTIONS carries house rules
# for working inside this repository (kb_tools' names the tooling repo's own
# justfile targets), and ROADMAP, AGENTS and CLAUDE are development apparatus by
# definition. Adding a package, or a docs/ directory below one, needs no edit
# here: the names are matched wherever they sit.
#
# Two groups and a tail, which is the order the set reads in rather than
# alphabetical: the contract-doc precedence chain, then the development
# apparatus, then the maintainer-facing prose a package writes under a name of
# its own. Only that tail grows per-document — a name outside the chain cannot
# be derived from it — so a package doc that needs to stay here earns a line,
# and one that does not is shipping.
#
# Matched by NAME at any depth, never by placement or suffix. `README.md` is
# deliberately absent: it is the one name in that vocabulary a package writes
# for its consumer rather than its maintainer, so a package that grows one is
# shipping it on purpose. `.tmpl` files are payload rather than documentation —
# kb_tools/installed/CONVENTIONS.md.tmpl is written into a consuming project's
# own KB by a build — and match nothing here.
INSTALL_EXCLUDED_DOCS = frozenset(
    {
        "SPEC.md",
        "ARCHITECTURE.md",
        "CONVENTIONS.md",
        "ROADMAP.md",
        "AGENTS.md",
        "CLAUDE.md",
        "THESIS.md",
    }
)

# The shipped code packages: (source directory in this repository, destination
# relative to the install ROOT). Both paths are POSIX-relative strings.
#
# The destination is a CONSUMER CONTRACT and is frozen. Runner snippets already
# installed in consuming projects name `.claude/agents/kb_tools/…`, and every
# definition body writes its paths against `.claude/agents/…` (SPEC.md,
# Deployed Surfaces), so a consuming project cannot be asked to notice that
# this repository rearranged itself. Stating the pairing as data is what lets
# the source side move while the destination side does not — the two are one
# fact only for as long as the destination is derived from directory
# placement.
#
# Rows are read by package_destinations (which every other reader goes
# through — the copy set, the wholesale destination removal, and the prune's
# step-around) and by assert_install_root, which must guard a package source
# wherever it sits. Relocating a package is therefore an edit to this table
# and to nothing else.
SHIPPED_PACKAGES = (
    ("kb_tools", "agents/kb_tools"),
    ("liaison_tools", "agents/liaison_tools"),
)


def excluded_from_install(relpath: Path) -> bool:
    """Is this surface-relative path on the install exclusion list?"""
    return (
        bool(INSTALL_EXCLUDED_DIRS.intersection(relpath.parts[:-1]))
        or relpath.name in INSTALL_EXCLUDED_NAMES
        or relpath.name in INSTALL_EXCLUDED_DOCS
        or relpath.suffix == INSTALL_EXCLUDED_SUFFIX
    )


def assert_install_root(root: Path, *, source_root: Path = REPO_ROOT) -> None:
    """Refuse an install ROOT that would write the product into this
    repository's own tree.

    Two refusals, each with its own proposition, and neither is a data-loss
    guard: no ROOT rewrites a package source, and no destination the install
    removes wholesale (replace_package_destinations) can reach one, because a
    destination is always ROOT/agents/<package> and nothing puts that over a
    source sitting at this repository's top level. What both prevent is the
    product materializing inside its own source.

    **ROOT is this repository's root.** `agents/` and `commands/` are names in
    the install product, not directories this repository keeps (SPEC.md,
    Deployed Surfaces), so the render lands as an untracked copy of every
    definition beside the templates that produced it, matched by no `.gitignore`
    entry. The producers are the invocations that resolve ROOT to the repository
    exactly: `just install . --subdir=`, and `just render <slug>` given a slug
    that climbs out of `rendered/`.

    **ROOT is inside a package source.** `just install kb_tools` alone does it,
    ROOT being `kb_tools/.claude`. The first run merely writes the product into
    the source tree; the damage lands on the NEXT one, when those files are
    inside the tree package_pairs walks, so the copy set names sources that the
    destination removal then deletes underneath it and the install aborts
    partway through the copy on a file it had just enumerated. Containment is
    the right test here and equality is not: every directory under a package
    source is as fatal as the source itself. The sources are read from
    SHIPPED_PACKAGES rather than assumed to sit under a deployed surface — a
    package source outside every surface is still a source this install reads.

    The first test is equality and NOT containment, because the sanctioned
    deployment layout is a clone at `<project>/.claude/adjagent/` used as the
    install source: `just install <project>` then resolves ROOT to
    `<project>/.claude`, which contains every package source by construction. A
    containment test there refuses the one workflow this repository exists to
    serve. Equality separates them because the intended layout never makes ROOT
    the repository — it makes ROOT a directory the repository sits under.

    The cost of that narrowing, taken deliberately: a ROOT above the repository
    (`just install .. --subdir=`) is now allowed, and it is allowed because it
    is indistinguishable from the sanctioned layout. It lands an untracked
    render outside this repository rather than inside it, which is a mess in
    somebody else's directory and not a commit risk here.

    Both paths are resolved before comparison, so a symlink or a `..` segment
    cannot route around either test.
    """
    target = root.resolve()
    repo = source_root.resolve()
    if target == repo:
        raise InputError(
            f"install ROOT '{rel(root)}' is this repository's own root — the install would "
            f"write the whole product into the source tree, as an untracked agents/ and "
            f"commands/ beside the templates that render them. Install into the project that "
            f"consumes it: `just install <project>`"
        )
    for source, _ in SHIPPED_PACKAGES:
        source_dir = (source_root / source).resolve()
        if target.is_relative_to(source_dir):
            raise InputError(
                f"install ROOT '{rel(root)}' is inside this repository's own {source}/ package "
                f"source ({rel(source_dir)}) — the install would write the product into the tree "
                f"it copies from, and the next run's copy set would name files its own "
                f"destination removal deletes underneath it. Install into the project that "
                f"consumes it: `just install <project>`"
            )


def package_destinations(smap: dict[str, tuple[Path, Path]]) -> list[tuple[str, Path, Path]]:
    """(source directory in this repository, ROOT-relative destination key,
    absolute destination under ROOT) for every SHIPPED_PACKAGES row whose
    owning surface is in `smap`.

    Where a package LANDS is read off its row and never off where its source
    sits (SHIPPED_PACKAGES), and this is the single place that reading happens:
    package_pairs copies into these directories, replace_package_destinations
    empties them first, and the stale-output prune steps around them. A row
    whose surface `smap` does not cover is dropped, so
    a narrowed run delivers — and reasons about — no package on the surface it
    is not covering.
    """
    found = []
    for source_rel, dest_rel in SHIPPED_PACKAGES:
        destination = Path(dest_rel)
        surface, *below = destination.parts
        if surface in smap:
            found.append((source_rel, destination, smap[surface][1].joinpath(*below)))
    return found


def package_pairs(smap: dict[str, tuple[Path, Path]], *, source_root: Path = REPO_ROOT) -> list[tuple[str, Path, Path]]:
    """(ROOT-relative key, source, target) for every file an install COPIES,
    sorted by key: the shipped code packages under `source_root`, walked from
    each row's source and landed at each row's frozen destination, minus the
    exclusion list. That is the whole copy set — the definitions are rendered
    rather than copied, and nothing else in this repository is delivered by
    copy, which is what the name says.

    The key is the file's destination, not its source. That is what keeps an
    install's accounting — the per-surface counts, the report, a consuming
    project's tree — invariant under a change to where a package's source
    sits, which is the whole point of SHIPPED_PACKAGES.

    A package row is delivered only when the surface owning its destination is
    in `smap`, so `--surfaces commands` installs no agent-side package.
    """
    found: list[tuple[str, Path, Path]] = []
    for source_rel, key_root, destination in package_destinations(smap):
        walk_root = source_root / source_rel
        if not walk_root.is_dir():
            continue
        for source in sorted(walk_root.rglob("*")):
            if not source.is_file():
                continue
            relpath = source.relative_to(walk_root)
            if excluded_from_install(relpath):
                continue
            found.append(((key_root / relpath).as_posix(), source, destination / relpath))
    return sorted(found, key=lambda pair: pair[0])


def replace_package_destinations(smap: dict[str, tuple[Path, Path]]) -> list[str]:
    """Remove every shipped package's destination directory entire, returning
    the ROOT-relative key of each one that was there to remove.

    A shipped package's destination belongs to this repository whole. Its
    contents are ours, nothing in it is a consuming project's to maintain, and
    so the unit that gets replaced is the DIRECTORY and not the file. That is
    what retires a file whose source here has since been deleted — the copy
    that follows writes what the package holds now and has no way to notice
    what it used to hold — and it is why no row of the per-target write-safety
    table reaches inside one (SPEC.md, Write Safety). The banner prune does not
    reach inside one either: two rules at two granularities, and this is the
    coarse one.

    Exactly the destinations package_destinations derives from the
    SHIPPED_PACKAGES rows and nothing else: not a parent, not a sibling,
    nothing matched by a pattern.

    Every destination goes BEFORE any file is written, rather than each one
    going immediately ahead of its own copy. The two are independent — removal
    reads nothing the copy produces, and the copy reads its sources from this
    repository rather than from ROOT, which assert_install_root has already
    established cannot be the same place — so the order is free, and taking it
    this way makes it unrepresentable for a later removal to delete files an
    earlier copy has just written. That is what a table row whose destination
    nested inside another's would otherwise do, silently. A copy that raises
    partway therefore leaves a package short of files rather than holding stale
    ones; the install has failed either way, and the remedy for both states is
    the same re-install.
    """
    removed = []
    for _, key, destination in package_destinations(smap):
        if destination.is_dir():
            shutil.rmtree(destination)
            removed.append(key.as_posix())
    return removed
