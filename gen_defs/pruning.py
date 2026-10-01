"""
Last, an install PRUNES (prune_stale). Overwriting is only half of keeping an
artifact tree true to its source: a definition whose template has since been
deleted is written by nothing and so survives every re-install, drifting there
forever — carried by a diff between two render slots as a permanent `Only in`
line. So a file under a deployed surface that
this run did NOT write, that carries one of this tool's banners, and whose
body still hashes to that banner's claim is DELETED, together with any
directory the deletion empties. The two complements are the point of the rule
and not exceptions to it: a banner whose hash does not match is hand-edited and
is never deleted (that is the .bak branch's territory and it stays there), and
a file carrying no banner of ours is not ours at all — a consuming project's
.claude/ holds other people's files. The shipped packages' destinations are
outside the sweep entirely, and need nothing from it: the copy half replaced
each of them whole. The prune runs AFTER both halves have written, so
the write set is a fact on disk rather than a prediction and a run that failed
mid-render leaves one stale file too many rather than one live definition too
few. Every path it deletes is named in the report, --verbose or not.
"""

from dataclasses import dataclass
from pathlib import Path

from .banners import banner_body, body_untouched
from .product import excluded_from_install, package_destinations

# The three states a file under a deployed surface can be in when this run did
# not write it, and what the prune does with each. Named as three, because the
# rule is as much the two it refuses to touch as the one it deletes.
PRUNE_STALE = "stale"  # our banner, body hashes to it -> deleted
PRUNE_EDITED = "edited"  # our banner, body does NOT hash to it -> kept
PRUNE_FOREIGN = "foreign"  # no banner of ours to read a claim from -> kept


def prune_verdict(extant: bytes) -> str:
    """Which of the three states these extant bytes are in.

    The prune is the only reader of this question now — no write path asks it,
    because a generation target is provably the tool's own output or refused,
    and a copy target never outlives the install that wrote it. Three states
    and not two: "hand-edited" and "not ours" are both kept, but for different
    reasons and reported differently.

    A file whose banner predates the hash line reads PRUNE_FOREIGN, not
    PRUNE_EDITED: it carries no claim to read back, which is the same nothing a
    consuming project's own file carries. Both are kept, so only the bucket
    differs — and the conservative bucket is the right one for a claim that
    cannot be read.
    """
    try:
        text = extant.decode("utf-8")
    except UnicodeDecodeError:
        # Bytes that are not utf-8 text carry no banner to read a claim from.
        return PRUNE_FOREIGN
    if banner_body(text) is None:
        return PRUNE_FOREIGN
    return PRUNE_STALE if body_untouched(text) else PRUNE_EDITED


@dataclass(frozen=True)
class Prune:
    """What one prune pass found, in the three states the rule distinguishes.

    `pruned` and `kept_edited` are ROOT-relative keys, the same vocabulary the
    rest of the install report names files in. `foreign` is a count and not a
    list: naming a consuming project's own files back at it is noise, and the
    install has no opinion about any of them.
    """

    pruned: list[str]
    kept_edited: list[str]
    foreign: int


def remove_emptied(directory: Path, *, stop: Path) -> None:
    """Remove `directory` and each ancestor the prune left empty, deepest
    first, never removing `stop` (a surface root) or anything above it.

    An emptied directory is exactly as stale as the file that was in it — a
    `diff -rq` between two render slots reports `Only in latest: design-topics`
    as loudly as it reports a file — and only a directory the prune itself
    emptied is ever reachable here, since the climb stops at the first one
    still holding anything.
    """
    while directory != stop and directory.is_relative_to(stop) and directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent


def prune_stale(smap: dict[str, tuple[Path, Path]], *, written: set[Path]) -> Prune:
    """Delete the files under ROOT's deployed surfaces that this repository no
    longer produces — and only those.

    Four states, and the rule is as much the three it leaves alone as the one
    it takes:

        in `written`                  -> this run just wrote it: never a
                                         candidate, decided on path identity
                                         and never on content
        our banner, body hashes to it -> unmodified output of an earlier
                                         install whose templates no longer
                                         declare it. DELETED: nothing will ever
                                         rewrite it, and a diff between two
                                         render slots carries it as a permanent
                                         `Only in` line
        our banner, body does not     -> hand-edited. KEPT, always. This is the
                                         content the numbered-.bak branch
                                         preserves rather than destroys, and a
                                         template no longer claiming it makes it
                                         more the consumer's, not less
        no banner of ours             -> not ours. KEPT, and not named: a
                                         consuming project's .claude/ holds
                                         other people's files

    The shipped packages' destinations are stepped around entire
    (package_destinations): what lands there is a copy set, and this rule is
    about the definition surfaces.

    Runs AFTER both halves of the install have written, which is what makes
    `written` a fact on disk rather than a prediction, and what keeps a render
    that raised from ever reaching it: a failed run leaves the tree with a
    stale file too many, never a live definition too few.
    """
    packages = [destination for _, _, destination in package_destinations(smap)]
    pruned: list[str] = []
    kept_edited: list[str] = []
    foreign = 0
    for surface, (_, out_dir) in sorted(smap.items()):
        stale: list[Path] = []
        for path in sorted(out_dir.rglob("*")):
            if path in written or path.is_symlink() or not path.is_file():
                continue
            if any(path.is_relative_to(destination) for destination in packages):
                continue
            relpath = path.relative_to(out_dir)
            # A path no install would ever emit is not a path an install wrote.
            # The *.bak safety copies above all: they hold precisely the
            # hand-edited content this rule exists to preserve, and they would
            # otherwise be reported as kept on every run forever.
            if excluded_from_install(relpath):
                continue
            key = (Path(surface) / relpath).as_posix()
            verdict = prune_verdict(path.read_bytes())
            if verdict == PRUNE_FOREIGN:
                foreign += 1
            elif verdict == PRUNE_EDITED:
                kept_edited.append(key)
            else:
                stale.append(path)
                pruned.append(key)
        for path in stale:
            path.unlink()
        # After every unlink in this surface, so emptiness is final rather than
        # a function of walk order.
        for directory in {path.parent for path in stale}:
            remove_emptied(directory, stop=out_dir)
    return Prune(pruned=pruned, kept_edited=kept_edited, foreign=foreign)
