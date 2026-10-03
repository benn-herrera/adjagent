"""
Per-target safety — a target is only ever written when it is provably ours,
and an overwrite never destroys content this tool did not itself write:

    target missing                  -> created
    banner, render identical        -> no write at all (counted as unchanged)
    banner, body hash matches the
      banner's claim, render differs-> overwritten in place, NO backup: the
                                       prior content is provably this tool's
                                       own output, reproducible from the
                                       template, so a copy of it is landfill
    banner, body hash absent or
      mismatched, render differs    -> hand-edited (or pre-hash) content:
                                       copied to <name>.md.<NN>.bak, then
                                       written in place
    target exists without a banner  -> REFUSED, never written, reported, nonzero

The hash-verified branch is what keeps routine regeneration — and an install's
render pass over a freshly copied tree — from churning out backups
nobody reads. A backup sits beside the file it backs up —
agents/go-coder.md.00.bak next to agents/go-coder.md — and the repo's root
*.bak gitignore rule keeps it out of git. Serials are per-target, zero-padded
from 00, allocated as the highest existing serial plus one, and never reused.

Every write in this tool is a CONTENT write and nothing else. An extant target
is written in place — its inode, owner and mode survive untouched — and a
backup is a plain content copy into a new file the tool itself owns, never a
metadata clone of the file it copies. That is a portability property, not a
detail: writing bytes into an existing file needs only write permission, while
cloning mtime or mode (utime, chmod — what shutil.copy2/copystat/copymode do)
requires OWNERSHIP of the target, which fails outright in a shared group-writable
tree whose files another user installed. Timestamps carry no meaning anywhere in
this system — integrity is decided by the banner's content hash — so cloned
metadata bought nothing and cost a mid-run EACCES that could split an install
into a partial apply. The one metadata write left is on the creation path
alone: a file the tool has just created takes the source's executable bit (a
chmod on a file it owns by construction, always legal), so an installed shell
tool stays runnable.

There is no wrong-output-directory-constant guard, because there is no
constant: every run names its ROOT, ROOT is asserted to exist, and the report
states where the files landed. The surface directories under ROOT and the
mirrored subdirectories beneath them come from the template tree rather than
from a constant, and are created as needed.
"""

import re
from pathlib import Path

from .banners import banner_claim, body_untouched
from .discovery import GlobMap, template_targets
from .model_tuning import OverlaySource, TierBinding, Tuning
from .paths import TEMPLATES_DIR, rel
from .rendering import all_renders

REFUSAL = (
    "exists without the generated banner — refusing to overwrite. If it should "
    "be generated, delete it and re-run; otherwise rename the colliding file."
)

# A backup sits beside the file it backs up. The repo's root *.bak gitignore
# rule keeps them out of git. Serials are per-target and never reused.
SERIAL = re.compile(r"\.(\d+)\.bak$")


def next_backup(target: Path) -> Path:
    """Allocate <target>.<NN>.bak beside the target, NN = highest existing + 1."""
    used = []
    for path in target.parent.glob(f"{target.name}.*.bak"):
        match = SERIAL.search(path.name)
        if match:
            used.append(int(match.group(1)))
    return target.with_name(f"{target.name}.{max(used) + 1 if used else 0:02d}.bak")


def back_up(target: Path) -> Path:
    """Copy the extant definition's CONTENT aside before it is overwritten.

    Copy, not rename: the subsequent write goes through the original inode, so
    the live definition keeps its identity, owner and mode no matter who runs
    the tool. Renaming would hand the original inode to the disposable backup
    and leave the tracked file owned by whoever regenerated it.

    Content only — the .bak is a recovery artifact, not a mirror. It is a new
    file this run owns, with this run's default mode and its own timestamps;
    cloning the original's metadata would need ownership of a file the runner
    may not own, and would buy nothing, since nothing in this system reads a
    timestamp (integrity is the banner's content hash).
    """
    backup = next_backup(target)
    backup.write_bytes(target.read_bytes())
    return backup


def generate(
    binding: TierBinding,
    smap: dict[str, tuple[Path, Path]],
    *,
    overlays: OverlaySource,
    globs: GlobMap | None = None,
    verbose: bool = False,
    tuning: Tuning,
) -> bool:
    clean = True
    unchanged = 0
    print("Generating definitions")
    print("=" * 60)
    found = template_targets(smap, globs)
    if not found:
        print(f"  ERROR      no templates found under {rel(TEMPLATES_DIR)}/")
        return False

    pairs = all_renders(binding, smap, overlays=overlays, globs=globs, tuning=tuning)
    # The output root itself was asserted to exist when the surface map was
    # built. Everything below it — each surface directory, and the mirrored
    # subdirectories under those — is created as needed.
    for out_dir in sorted({target.parent for target, _ in pairs}):
        out_dir.mkdir(parents=True, exist_ok=True)
    landed: dict[str, int] = {}
    for target, rendered in pairs:
        landed[rel(target.parent)] = landed.get(rel(target.parent), 0) + 1
        if not target.exists():
            target.write_text(rendered, encoding="utf-8")
            print(f"  {'created':<10} {rel(target)}")
            continue

        # Compare before writing: an identical render is not a write at all, so
        # an unchanged definition never accumulates a backup.
        actual = target.read_text(encoding="utf-8")
        if banner_claim(actual) is None:
            print(f"  {'REFUSED':<10} {rel(target)} {REFUSAL}")
            clean = False
            continue

        if actual == rendered:
            unchanged += 1
            if verbose:
                print(f"  {'unchanged':<10} {rel(target)}")
            continue

        if body_untouched(actual):
            # Provably this tool's own output: reproducible from the template,
            # so a backup of it would be landfill.
            target.write_text(rendered, encoding="utf-8")
            print(f"  {'updated':<10} {rel(target)}")
            continue

        backup = back_up(target)
        target.write_text(rendered, encoding="utf-8")
        print(
            f"  {'updated':<10} {rel(target)} (hand-edited or pre-hash content "
            f"backed up beside it as {backup.name})"
        )

    print()
    print(f"  {'unchanged':<10} {unchanged} definition(s)")
    where = ", ".join(f"{d}/ ({n})" for d, n in sorted(landed.items()))
    print(f"{len(pairs)} definition(s) from {len(found)} template(s), in: {where}")
    return clean
