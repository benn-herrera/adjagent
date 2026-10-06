"""
Full-product install — `install ROOT`:

    python3 -m gen_defs install <project>/.claude [--family NAME]
        [--model-tier-map SPEC] [--model-pin-tier-alias-map SPEC]

An install delivers the whole deployed product in two halves. The shipped
packages (kb_tools/, liaison_tools/) are a REMOVE-AND-RECURSIVE-COPY
into the destinations the table below names, minus one explicit exclusion list
(INSTALL_EXCLUDED_*) — test suites and their fixtures, python/pytest caches,
*.bak safety copies, .DS_Store, and this repository's own project
documentation, which is code's provenance rather than part of it. There is no
inclusion list and no complement computation: a new tool file ships with no
enrollment step. The definitions are RENDERED into ROOT's two surfaces by the
ordinary generation pass — there is no checked-in render to copy, so the copy
half never had them to deliver, and the (family, tier-map, alias-map) triple an
install was given is just the triple that render runs under. `install` declares
neither `--surfaces` nor the selection globs, which would narrow the product to
a partial install.

Where a copied file LANDS is not, however, read off where its source sits. The
shipped code packages travel by an explicit source -> destination table
(SHIPPED_PACKAGES): each row pairs a source directory in this repository with
the ROOT-relative destination it must arrive at, and the copy walks the row's
source while keying every file to the row's destination. The destination is a
CONSUMER contract — runner snippets already installed in consuming projects
name .claude/agents/kb_tools/..., and every definition body writes its paths
against .claude/agents/... — so the source may be relocated within this
repository and the destination may not follow it. Stating the pairing as data
is what keeps those two facts independent; deriving the destination from
directory placement is what made them the same fact.

EVERY install renders, whatever triple it was given: a default-triple install
is one triple among the possible ones, not a special case with a copy behind
it, which is what makes a default install and a tuned one the same code path
and the same guarantee. The render pass receives the effective triple and the
tier resolver the invocation built, so an install can never deliver
definitions tuned differently from what its own banners claim. Every target
that pass meets is absent or provably untouched tool output (see the
banner's body hash, `banners` module docstring), so it leaves no numbered
backups behind. Only a NON-DEFAULT triple earns a clause on the summary line —
a default render is the non-event report-by-exception exists for.

The installed tree is an ARTIFACT, not a working copy: this repository is the
source of truth and a re-install always overwrites. Local edits to installed
files are never preserved — edit the templates or the definitions here and
re-install — but they are not destroyed either: a target that is not provably
this tool's own output is copied aside as a numbered .bak first, exactly as
generation does it. The overwrite always happens; the backup only keeps
divergent human work from being destroyed by it, and *.bak files under an
installed tree are deletable at will.

A shipped package's destination is the one place that does not hold, and the
difference is of unit rather than of degree. The directory is this
repository's entire — its contents are ours and none of it is a consuming
project's to maintain — so an install REMOVES IT WHOLE and writes the package
fresh rather than reconciling it file by file. That is what retires a file
whose source here has since been deleted, by construction instead of by
detection: the copy writes what the package holds now and has no way to notice
what it used to hold. Nothing inside one is set aside first, so a local edit
made there is gone at the next install rather than preserved beside itself.
Two rules at two granularities, and the boundary between them is the one the
SHIPPED_PACKAGES table already draws: per-file and banner-gated out on the
deployed surfaces, where a consuming project's own files legitimately sit;
wholesale inside a package destination, where they do not.

An install writes exactly as generation does (see the content-write paragraph,
`generation` module docstring): an extant definition under a deployed surface
is rewritten through its own inode, so a tree installed by one user updates
cleanly under another so long as the group can write. Ownership and mode are
whatever the first install left. A COPIED file is always a fresh one — its
destination went with the directory — and is chmodded only to carry the
source's executable bit.

Every COPIED file is stamped with an !INSTALLED! banner carrying the same
!BODY-SHA256! line the generated banner carries, in whatever comment syntax
its filetype admits:

    *.md with frontmatter    comment lines inside the frontmatter block —
                             dropped by every frontmatter reader, the body
                             extraction the liaisons run included
    *.md without, commands/  a minimal frontmatter block holding only the
                             banner, as render_template already does for a
                             frontmatter-less command template: a command's
                             first BODY line is the description Claude Code
                             lists it by, and nothing may displace it
    *.md without, agents/    an HTML comment block above the content — a
                             shipped package's own documentation must not gain
                             frontmatter, which would present it as a
                             definition
    .py .sh .toml .mk .just  `#` comment lines at the top, below a shebang
    *.tmpl.md                a template (kb_tools/installed/, or a prompt
                             under kb_tools/kb_driver/prompt-templates/):
                             every byte is payload for what is composed from
                             it, so a banner would ship inside that — copied
                             verbatim, like the row below
    any other suffix         no comment syntax to carry a banner: the file is
                             copied verbatim, and --verbose names it (which
                             files those are follows from their name alone,
                             so a clean install does not report it)

Third-party source vendored into a shipped package under a `_vendor/`
directory is exempt whatever its suffix: the banner would assert adjagent
provenance over code we did not write, and tell its reader to edit a source
repository that is not the file's. It is copied verbatim and --verbose names
it as unstamped. A STAMPING carve-out only — vendored code ships like any
other package file, and the exclusion list above is untouched.

A generated definition is exempt: it arrives carrying its own !GENERATED!
banner, which already forbids in-place edits and names the real edit path.
The two banners are one marking scheme — provenance plus a body hash — and
the hash buys the same thing on re-install that it buys on regeneration: a
target whose body still hashes to its own banner is provably ours and is
overwritten silently, while a mismatched or unbannered target is backed up
first. Re-installing an untouched tree is therefore byte-stable: no content
changes and no backups.
"""

import contextlib
import io
import stat
from collections.abc import Callable
from pathlib import Path

from .banners import banner_claim, stamp_installed
from .discovery import COMMAND_SURFACE
from .errors import InputError
from .generation import generate
from .model_tuning import OverlaySource, TierBinding, Tuning, display_maps
from .paths import REPO_ROOT, TEMPLATE_SUFFIX, rel
from .product import assert_install_root, package_pairs, replace_package_destinations
from .pruning import prune_stale
from .rendering import all_renders

# Filetypes whose comment syntax can carry the banner as `#` lines. A suffix
# absent here and not .md admits no comment we can rely on (JSON is the case
# in point), so its file is copied verbatim and the install reports it.
HASH_COMMENT_SUFFIXES = frozenset({".py", ".sh", ".toml", ".mk", ".just"})
MARKDOWN_SUFFIX = ".md"
# Third-party source vendored into a shipped package lives under a directory of
# this name. Its files ship — this is a STAMPING carve-out, never an exclusion —
# but they are copied verbatim: the banner would claim adjagent provenance over
# code we did not write and send its reader to the wrong source repository.
VENDOR_DIR = "_vendor"
# The only mode bits an install ever sets, and only on a file it just created:
# an executable source (the liaison shell tools) must land runnable. An update
# writes in place and inherits whatever mode the target already carries.
EXEC_BITS = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


def bannerable(source: Path) -> bool:
    """Does this file's type admit a comment the !INSTALLED! banner can live
    in? (Whether it *needs* one is install_content's question.)

    A template (`*.tmpl.md`) does not, whatever its final suffix: every byte of
    it is payload for a file another tool writes from it, so a banner stamped
    in would ship inside that file."""
    if source.name.endswith(TEMPLATE_SUFFIX):
        return False
    return source.suffix == MARKDOWN_SUFFIX or source.suffix in HASH_COMMENT_SUFFIXES


def vendored(key: Path) -> bool:
    """Is this install key inside a shipped package's `_vendor/` tree?

    Decided on the DESTINATION key, as every other piece of install accounting
    is (package_pairs), and never on the source path: a source root that itself
    sits somewhere under a `_vendor/` directory would otherwise carve out the
    whole product. Directory names match at any depth; a file named `_vendor`
    is not one."""
    return VENDOR_DIR in key.parts[:-1]


def install_content(source: Path, *, surface: str) -> str | None:
    """The text to install for a copied file — its source, banner stamped in —
    or None when the file travels verbatim: a generated definition (its own
    !GENERATED! banner already forbids in-place edits and names the real edit
    path), or a filetype with no comment syntax to carry a banner.

    `surface` decides where a markdown file with no frontmatter of its own puts
    the banner, on the same split render_template already makes: a command is
    given a minimal frontmatter block (its first BODY line is the description
    Claude Code lists it by, so nothing may displace it), while frontmatter-less
    markdown under agents/ takes an HTML comment instead — frontmatter there
    would present supporting material as a dispatchable definition, which it is
    not.
    """
    if not bannerable(source):
        return None
    text = source.read_text(encoding="utf-8")
    if source.suffix != MARKDOWN_SUFFIX:
        return stamp_installed(text, style="hash")
    if banner_claim(text) is not None:
        return None
    if text.startswith("---\n"):
        style = "frontmatter"
    else:
        style = "bare-frontmatter" if surface == COMMAND_SURFACE else "html"
    return stamp_installed(text, style=style)


def install_file(source: Path, target: Path, content: str | None) -> None:
    """Write one copied file into a destination this install has just emptied.

    Every file the copy half delivers lands inside a shipped package's
    destination, and replace_package_destinations removed each of those
    directories entire before the first write — so no target here outlives the
    install, and there is nothing extant to compare against, set aside, or
    refuse. The unit inside a package destination is the directory, and that is
    the whole of the rule there (SPEC.md, Write Safety).

    Bytes throughout: the copy set includes filetypes this tool never decodes
    (a stamped file's content is already utf-8 text, encoded here), and the
    write has to be byte-exact.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes() if content is None else content.encode("utf-8"))
    if source.stat().st_mode & EXEC_BITS:
        target.chmod(target.stat().st_mode | EXEC_BITS)


def quiet_pass(run: Callable[[], bool], *, verbose: bool) -> bool:
    """Run an install's integrity or render pass, holding its file-by-file
    report back unless it has something to say.

    An install reports by exception: a fresh install and a clean overwrite are
    both non-events, so the pass prints only when it came back unclean — or when
    --verbose asked for everything. The pass's own verdict is returned either
    way, so what the install does with it never depends on what was printed.

    A pass that raises has already printed the most useful part of its report —
    how far it got before the template it could not render — and the buffer is
    the only copy of it. Releasing the buffer in a finally is what keeps "held
    back" from meaning "discarded on exactly the run that needed it".
    """
    buffer = io.StringIO()
    ok = False
    try:
        with contextlib.redirect_stdout(buffer):
            ok = run()
    finally:
        if verbose or not ok:
            print(buffer.getvalue(), end="")
    return ok


def install(
    binding: TierBinding,
    smap: dict[str, tuple[Path, Path]],
    *,
    root: Path,
    overlays: OverlaySource,
    source_root: Path = REPO_ROOT,
    verbose: bool = False,
    tuning: Tuning,
) -> bool:
    """Install the full product into `root` (a consuming project's .claude).

    Two halves and a sweep, in order. First a recursive copy of everything package_pairs
    names under `source_root` — the shipped packages, at their frozen
    destinations — minus the exclusion list, with an !INSTALLED!
    banner stamped into every copied file whose type admits one and whose
    provenance is this repository's (so never under `_vendor/`). Each package's
    destination directory is removed entire before that copy begins
    (replace_package_destinations): the directory is this repository's whole,
    so it is replaced as a unit rather than reconciled file by file, and a file
    whose source here was deleted is retired by construction instead of
    surviving in a consumer's tree forever. Nothing inside one is set aside
    first. Then the
    ordinary generation pass, which renders the definitions into the surfaces
    under `root`.

    The definitions are rendered, never copied: this repository keeps no
    checked-in render for a copy to read. The (family, tier-map, alias-map)
    triple the install was given is simply the triple that render runs under,
    which is why a default install and a tuned one are one code path rather
    than a copy and a special case. Every target the pass meets is absent or
    provably untouched output, so it leaves no backups behind.

    Then the stale-output prune (prune_stale), which deletes what the two
    halves did NOT write and this repository can prove it wrote earlier —
    yesterday's definition whose template has since been deleted. Nothing else:
    a hand-edited file and a file with no banner of ours are both left where
    they are.

    Reports by exception. A clean install is one summary line and nothing else:
    what landed where. The lines beyond it are problems only, and each names
    its files — today, a pass that came back unclean, and what the prune did.
    No copied file can contribute one: each lands in a destination this run
    emptied first, so there is no extant content to be set aside and no .bak a
    copy can produce. --verbose still lists every file and names the two
    verbatim populations apart: the unbannered ones, whose filetype (never
    their state) is the whole of what makes them so, and the vendored ones
    under `_vendor/`, which a banner would misattribute to this repository.
    The prune reports the same
    way and is never silent when it acts: deleting a file in a tree the operator
    owns is a problem-class event by definition, so every pruned path is named
    whether or not --verbose asked, and so is every file kept back from the
    prune because its content is not ours.

    The copy finishes before the render begins, so a render that raises leaves
    the packages complete and the definitions partial under ROOT. What landed
    is printed on the way out too — an operator shown only the error would read
    it as "nothing happened."

    A replaced package directory is named on the summary line rather than in a
    block of its own. It is the ordinary path — every install that finds one
    replaces it — so a block would fire on every run and report-by-exception
    would mean nothing; but it is still a directory whose contents went,
    operator edits included, so it is never unnamed either.
    """
    assert_install_root(root, source_root=source_root)
    pairs = package_pairs(smap, source_root=source_root)
    if not pairs:
        # The copy set is exactly the shipped packages, so an empty one means
        # their sources are not where SHIPPED_PACKAGES says — a broken
        # invocation, not a product with nothing to copy. Refused before the
        # first write, since the render half alone would deliver definitions
        # whose toolchain never arrived.
        print(f"ERROR: no shipped package source found under {rel(source_root)}/ — nothing to copy")
        return False

    # Before the first write, and after the check that there is anything to
    # write at all: a run with nothing to deliver removes nothing.
    wiped = replace_package_destinations(smap)

    landed: dict[str, int] = {}
    unbannered: list[str] = []
    unstamped: list[str] = []
    for key, source, target in pairs:
        surface = key.split("/", 1)[0]
        # Two ways a copied file goes out verbatim, reported apart because the
        # reasons are: a filetype with no comment syntax, and foreign source
        # under _vendor/ whose provenance is not ours to claim.
        is_vendored = vendored(Path(key))
        content = None if is_vendored else install_content(source, surface=surface)
        if is_vendored and bannerable(source):
            unstamped.append(key)
        elif content is None and not bannerable(source):
            unbannered.append(key)
        install_file(source, target, content)
        landed[surface] = landed.get(surface, 0) + 1
        if verbose:
            print(f"  written    {key}")

    def summary(counts: dict[str, int]) -> str:
        return ", ".join(f"{n} under {surface}/" for surface, n in sorted(counts.items()))

    copied = summary(landed)
    try:
        # One pass, one triple, whatever the triple is. Both the effective
        # triple and the tier resolver reach it — arguments this function was
        # itself handed, and which a call site that dropped them would turn
        # into a tree of definitions tuned differently from what their own
        # banners claim.
        integrity = quiet_pass(
            lambda: generate(binding, smap, overlays=overlays, tuning=tuning, verbose=verbose),
            verbose=verbose,
        )
        renders = all_renders(binding, smap, overlays=overlays, tuning=tuning)
        for target, _ in renders:
            for surface, (_, out_dir) in smap.items():
                if target.is_relative_to(out_dir):
                    landed[surface] = landed.get(surface, 0) + 1
                    break
        rendered = len(renders)
        ok = integrity
    except InputError:
        # The copy finishes before the render starts, so ROOT already holds the
        # shipped packages entire, and however far the render got, neither of
        # which the error on its way out says anything about. An operator told
        # only "error: unknown chunk" reads it as "the install did not happen";
        # this is the last point at which anything can tell them otherwise.
        print(f"installed: {copied} → {rel(root)} — the packages are in place; the render after them failed")
        raise

    # Last, and only on a run that got this far: the write set is now a fact on
    # disk, and a run that failed above leaves a stale file behind rather than
    # a live definition missing.
    stale = prune_stale(smap, written={target for _, _, target in pairs} | {target for target, _ in renders})

    counts = summary(landed)

    tuned = ""
    if not tuning.is_default:
        # Report by exception, and every install renders now: a DEFAULT-triple
        # render is the non-event, so only a triple that differs from the
        # default one earns a clause. Keying this on `rendered` instead would
        # append a count and a restatement of the defaults to every ordinary
        # install — nothing an operator needs, and a description of nothing.
        tuned = (
            f"; {rendered} rendered under family {rel(tuning.family)}, "
            f"{display_maps(tuning)} harness {tuning.harness}"
        )
    # On the summary line rather than in a block of its own: a package
    # directory is replaced whole on EVERY install that finds one, so it is the
    # ordinary path and not a problem, and a clean re-install stays one line.
    # It is named all the same, because the operator's own edits inside one go
    # with it and nothing sets them aside.
    whole = f"; replaced whole, local edits included: {', '.join(wiped)}" if wiped else ""
    print(f"installed: {counts} → {rel(root)}{whole}{tuned}")
    if verbose and unbannered:
        print(f"unbannered (type admits no banner):{len(unbannered)} file(s) — " + ", ".join(unbannered))
    if verbose and unstamped:
        print(f"unstamped (vendored third-party source): {len(unstamped)} file(s) — " + ", ".join(unstamped))
    if verbose and stale.foreign:
        print(f"left alone (no banner of this repository's): {stale.foreign} file(s) under the surfaces")
    if not integrity:
        print("integrity: NOT CLEAN — see the report above")
    if stale.pruned:
        print(
            f"pruned: {len(stale.pruned)} installed file(s) this repository no longer produces, "
            "each still provably unmodified since it was installed, deleted:"
        )
        for key in stale.pruned:
            print(f"  {key}")
    if stale.kept_edited:
        print(
            f"kept: {len(stale.kept_edited)} installed file(s) this repository no longer produces "
            "hold content no install of this repo wrote; each is left where it is, yours to delete:"
        )
        for key in stale.kept_edited:
            print(f"  {key}")
    return ok
