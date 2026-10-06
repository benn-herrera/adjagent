"""Stage A — the conformance gate over SPEC.md's Document-Tree Contract.

**A non-conforming tree does not produce a missing graph, it produces a wrong
one.** So the run opens here, writes nothing, and stops on the first failed
assertion naming the point it belongs to. The check is cheap because the
contract is mechanical, and it is not a defensive parser: it *asserts* the
guarantees rather than tolerating their absence. A tolerant reader would be
building for a contract that does not exist while the one that does went
unenforced.

**The cleanliness check is the declared pass's double-run guard.** That pass
mints ids; a second run over its own output would mint a second set and double
the graph. Point 14 guarantees a fresh tree carries none of the artifacts it
writes, so the presence of any one of them means the input is not a fresh tree,
and :func:`gate` refuses.

**The later invocations' entry condition is a different one.** They extend the
tree additively — SPEC declares nodes additively in leaf frontmatter — so a
whole-tree refusal on "any frontmatter at all" would forbid them entirely.
:func:`pass_two_gate` makes the structural checks alone and partitions the tree
by :func:`determination` for the report. What keeps the node pass from
re-minting is not here: it is the node-pass record's read state.

**The forbidden artifacts are read off the modules that own them** — the
markers' openers off :mod:`kb_tools.kb_write.render` (:data:`tree.MARKER_OPENERS`),
frontmatter by :func:`kb_index_lib.find_frontmatter` — rather than re-typed
here. A cleanliness check carrying its own copy of the spellings would pass a
tree holding an artifact whose spelling had since moved, which is the
silent-clean failure this gate exists to prevent.

**One clause of point 14 is not checked, and that is a ruling rather than an
omission.** Point 14 also forbids a ``.index/`` directory, and what it describes
is what the *front end* leaves behind. Between that front end and this stage
runs ``graph-init``, whose landed behaviour is to create ``.index/`` and install
the runner include line over an already-populated tree (ARCHITECTURE.md,
Initialising the Claim-Graph Spine). Refusing on its presence here would refuse
every run of this stage as designed. Derived space is out of this gate's scope
in both directions: nothing under it is authored, and nothing this stage writes
lands there.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .. import kb_index_lib, kb_schema, kb_util, verify_md_links
from .report import ClaimGraphError
from .tree import ANCHOR_RE, DECLARING_KINDS, MARKER_OPENERS, Tree, document_kind, resolve, strip_markers, unquote


class ConformanceError(ClaimGraphError):
    """The input tree fails the contract. ``check`` names the point it fails."""


def _refuse(point: int, detail: str) -> ConformanceError:
    return ConformanceError(f"point-{point}", detail)


def _entry_point(tree: Tree) -> None:
    """Point 1 — the root lists every volume, and nothing else."""
    root = kb_index_lib.ENTRY_POINT_FILENAME
    if root not in tree.documents:
        raise _refuse(1, f"no {root} at the KB root")
    volumes = {
        path for path in tree.documents if path.count("/") == 1 and path.endswith(f"/{kb_index_lib.INDEX_FILENAME}")
    }
    listed = set(tree.children[root])
    if listed != volumes:
        raise _refuse(
            1,
            f"{root}'s link set is not the depth-1 volume-index set: unlisted {sorted(volumes - listed)}, "
            f"listed but not a volume index {sorted(listed - volumes)}",
        )


def _uplinks(tree: Tree) -> None:
    """Points 3 and 4 — the up-link's line (``kb_index_lib.uplink_index``) holds one, and the parent names it back."""
    for path in sorted(tree.documents):
        if path == kb_index_lib.ENTRY_POINT_FILENAME:
            continue
        parent = tree.parents.get(path)
        if parent is None:
            raise _refuse(
                3,
                f"{path} has no up-link carrying {kb_index_lib.UPLINK_MARKER!r} on its first line, or on the "
                f"first line after its frontmatter's closing fence",
            )
        if parent not in tree.documents:
            raise _refuse(3, f"{path}'s up-link names {parent}, which is not a document of this tree")
        if path not in tree.children[parent]:
            raise _refuse(4, f"{path} up-links to {parent}, whose child list does not name it")


def _path_shape(tree: Tree) -> None:
    """Point 2 — descendants decide the filename, in both directions."""
    index = kb_index_lib.INDEX_FILENAME
    for path, children in sorted(tree.children.items()):
        if path == kb_index_lib.ENTRY_POINT_FILENAME:
            continue
        sits_at_index = path.rsplit("/", 1)[-1] == index
        if children and not sits_at_index:
            raise _refuse(2, f"{path} lists {len(children)} children but does not sit at <dir>/{index}")
        if sits_at_index and not children:
            raise _refuse(2, f"{path} sits at an index path but lists no children")


def _spine(tree: Tree) -> None:
    """Point 5 — total, acyclic, and inverting the up-link relation exactly."""
    root = kb_index_lib.ENTRY_POINT_FILENAME
    seen: set[str] = set()
    stack = [(root, (root,))]
    while stack:
        path, trail = stack.pop()
        if path in seen:
            raise _refuse(5, f"the down-link spine is not acyclic: {' -> '.join(trail)}")
        seen.add(path)
        stack.extend((child, trail + (child,)) for child in tree.children[path])
    unreached = sorted(set(tree.documents) - seen)
    if unreached:
        raise _refuse(5, f"{len(unreached)} document(s) unreachable from {root} by down-links: {unreached[:5]}")
    for path, children in sorted(tree.children.items()):
        for child in children:
            if tree.parents.get(child) != path:
                raise _refuse(5, f"{path} lists {child} as a child, but {child}'s up-link does not name {path}")


def _markdown_links(tree: Tree) -> None:
    """Point 7, for the link form the dead-link gate can see."""
    broken = verify_md_links.scan_tree(tree.root, repo_root=tree.root)
    if broken:
        first = broken[0]
        raise _refuse(
            7,
            f"{len(broken)} dead markdown link(s), first at "
            f"{first.file.relative_to(tree.root)}:{first.line} {first.kind} {first.target!r}",
        )


def _anchors(tree: Tree) -> None:
    """Point 7, for the link form it cannot.

    ``kb_links.LINK_RE`` matches ``[text](target)`` and nothing else, so every
    rewritten cross-reference in the tree is invisible to the gate above. This
    stage resolves them itself, against the same document set. A bare fragment
    is not a failure — point 7 admits a label that cannot be resolved rendering
    as its own text, and a fragment with no path in front of it is what that
    looks like.

    **Read over the marker-stripped text, because :func:`pass_two_gate` runs
    this after a minting pass has written to the tree.** An anchor may be
    hard-wrapped between its attributes (SPEC.md, the cross-reference join) and
    ``ops._insert_marker`` appends to the end of the located line, so a marker
    landing on such an anchor's first line sits between two attributes
    :data:`tree.ANCHOR_RE` requires to be adjacent. The pattern would then match
    nothing there and the anchor would go *unchecked* rather than reported —
    the one failure this check cannot survive, since its whole subject is the
    links no other gate can see. On :func:`gate`'s run the strip changes
    nothing: a tree carrying a marker at all is one :func:`_cleanliness`
    refuses.
    """
    for path, document in sorted(tree.documents.items()):
        for match in ANCHOR_RE.finditer(unquote(strip_markers(document.text))):
            target, _, _ = match.group(1).partition("#")
            if target and resolve(path, target) not in tree.documents:
                raise _refuse(7, f"{path}: cross-reference anchor {match.group(1)!r} lands on no document")


def _carries_frontmatter(relative: Path, text: str) -> bool:
    """Whether ``text`` carries frontmatter point 14 forbids.

    Point 14's ``claims:`` key is a *field of* the frontmatter and cannot exist
    outside it, so the block's absence is what checks it — a bare substring test
    would read an author's own sentence about a framework's core claims as a
    metadata key. The one block allowed is the entry point's holding the format
    stamp alone, which ``graph-init``'s refresh writes before this gate runs: a
    property of the KB, not claim-graph metadata.
    """
    if kb_index_lib.find_frontmatter(text) is None:
        return False
    if relative.as_posix() != kb_index_lib.ENTRY_POINT_FILENAME:
        return True
    return set(kb_index_lib.parse_frontmatter(text) or {}) != {kb_schema.FORMAT_KEY}


def _cleanliness(tree: Tree) -> None:
    """Point 14 — and the double-run guard, over every file the tree holds.

    The markers are found by their openers anywhere in a document; frontmatter
    by the locator.
    """
    for path in sorted(tree.root.rglob("*.md")):
        relative = path.relative_to(tree.root)
        if set(relative.parts[:-1]) & kb_index_lib.EXCLUDE_DIRS:
            continue
        text = path.read_text(encoding="utf-8")
        if _carries_frontmatter(relative, text):
            artifact = "frontmatter"
        else:
            artifact = next((opener for opener in MARKER_OPENERS if opener in text), None)
        if artifact is not None:
            raise _refuse(
                14,
                f"{relative.as_posix()} already carries {artifact!r}. This is not a tree the front end "
                f"just wrote: this stage mints ids, so a second run over its own output would mint a "
                f"second set and double the graph. Rebuild the tree from the corpus and run once",
            )


#: The structural half of the gate, ordered by what each check's own subject
#: depends on rather than by the contract's numbering. Point 7 comes first
#: because every relation below it is *derived from links*: a dead link is a
#: phantom child, and a tree checked for its shape before its links resolve
#: reports the phantom's consequence — a leaf with a child — instead of the dead
#: link that invented it. Both passes rely on every one of these, and neither
#: adds to them: the shape of the tree does not change when metadata lands on
#: it.
_STRUCTURE = (_markdown_links, _anchors, _entry_point, _uplinks, _path_shape, _spine)

#: Point 14 comes last because a fresh tree passes every structural check
#: anyway, so a double run is refused by naming the artifact rather than a
#: symptom of one.
_CHECKS = (*_STRUCTURE, _cleanliness)


def gate(tree: Tree) -> None:
    """Assert every guarantee the later stages rely on, or raise :class:`ConformanceError`."""
    for check in _CHECKS:
        check(tree)


# --- the later invocations' entry condition ---------------------------------


class Determination(StrEnum):
    """What one leaf's frontmatter declares about its claims.

    A reading for the report and nothing more: no value here admits a leaf to
    a minting stage or closes one to it. Which leaves the node pass reads, and
    how far it got with each, is the node-pass record's.
    """

    #: Declares ids.
    HOSTS_CLAIMS = "hosts-claims"
    #: Carries a no-claim reason.
    AUTHORED_NO_CLAIM = "authored-no-claim"
    #: Declares neither, and is a kind that must — including one carrying no
    #: frontmatter block at all. The refusal, where the state is a defect, is the
    #: runner's: ``verify_kb_metadata``'s frontmatter-presence and tier-1
    #: coverage checks, over what a pass leaves behind.
    UNDECLARED = "undeclared"


def determination(fields: dict) -> Determination:
    """What ``fields`` — one document's parsed frontmatter — says about its claims."""
    if fields.get("claims"):
        return Determination.HOSTS_CLAIMS
    reason = fields.get("no-claim")
    if not isinstance(reason, str) or not reason:
        return Determination.UNDECLARED
    return Determination.AUTHORED_NO_CLAIM


@dataclass(frozen=True)
class PassTwoState:
    """The leaves partitioned by :func:`determination`, for a run's census line."""

    undeclared: tuple[str, ...] = ()
    hosting: tuple[str, ...] = ()
    determined: tuple[str, ...] = ()


def pass_two_gate(tree: Tree) -> PassTwoState:
    """The later invocations' entry condition: the structural checks, then the partition.

    **Which documents are counted is read off the tree rather than off what an
    earlier pass recorded about it.** A ``kind:`` field is
    :func:`tree.document_kind`'s answer written down — :mod:`assemble` stamps it
    from exactly this call. Asking the function is what makes the partition
    total over the tree: a document whose frontmatter is missing has no
    ``kind:`` either, and reading the field would drop it through the gap where
    an absent value and a non-declaring one look alike.
    """
    for check in _STRUCTURE:
        check(tree)

    partition: dict[Determination, list[str]] = {determined: [] for determined in Determination}
    for path in sorted(tree.documents):
        if document_kind(path, has_children=bool(tree.children[path])) not in DECLARING_KINDS:
            continue
        fields = kb_index_lib.parse_frontmatter(tree.documents[path].text) or {}
        partition[determination(fields)].append(path)

    return PassTwoState(
        undeclared=tuple(partition[Determination.UNDECLARED]),
        hosting=tuple(partition[Determination.HOSTS_CLAIMS]),
        determined=tuple(partition[Determination.AUTHORED_NO_CLAIM]),
    )


def spine_seeded(kb_root: Path) -> str | None:
    """Why the claim-graph spine is absent, or ``None`` when it is there.

    The spine is the derived-index directory ``graph-init`` creates. This stage
    assumes that verb has run rather than seeding anything itself, and checks
    only that the directory exists.
    """
    if not (kb_root / kb_util.INDEX_DIRNAME).is_dir():
        return f"{kb_root.name}/{kb_util.INDEX_DIRNAME}/ does not exist"
    return None
