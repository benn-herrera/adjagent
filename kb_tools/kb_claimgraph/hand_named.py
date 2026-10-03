"""Claims named by hand: a claim's printed name and number, written with no ``\\ref``.

*follows directly from Lemma 4.6*, *This proves Theorem B* — the mechanical half
of THESIS gap 2. The author named a claim the way a reader would, and the markup
carries no anchor for stage D to read, so the mention is found here off the
words themselves and offered as an **edge candidate**: never an edge, and
neither asked about nor recorded until classification offers it.

**The names are the corpus's own.** The display names of the blocks this corpus
states its results in (:func:`claim_names`) — whatever its ``\\newtheorem``
declarations printed — and never a list of what mathematicians usually call
things. A corpus naming its results *Result* is read for *Result 3* and not for
*Theorem 3*.

**The number is the printed one**: any dotted depth, a single capital for
headline and appendix results, a lowercase sub-item suffix matched and dropped —
*Lemma 4.6a* names Lemma 4.6. A printed list names each of its items: *Lemmas 2
and 3* is two mentions (:data:`tree.LIST_SEPARATOR`).

**A mention is a candidate only where it joins** (:func:`printed_claims`): some
claim-bearing block renders that exact name and number on its display line, or a
claim with no block carries it as its whole title. A mention joining nothing
produces nothing. Where the name and number join claims in several volumes, the
mention's own volume is preferred, a multi-paper KB numbering each paper's
results from one.

**Scanned only within the bodies of the node set**: a claim-bearing block's
extent, and the paragraph a prose claim was minted from. A proof is no node, and
prose no claim was minted from is no node's body. Inside a body three things are
skipped: an anchor, already a ``\\ref`` stage D reads; a citation, so
``\\cite[Theorem 2.4]{…}`` — another work's theorem — never counts; and a
mention its next words hand to a citation, *Theorem 3 of* ``\\cite{…}``, which
names the same other work's theorem from outside the bracket. A block's own
display line is its label, not a mention, and is skipped too: corpora number two
blocks alike often enough that reading it would join each to the other.

**The join reads the number the tree prints, and that is not always the
author's.** The reader numbers theorem-like blocks on a counter of its own, so
a paper numbering *Proposition 1.3* within its section may render that block's
display line *Proposition 17*, and the author's *Proposition 1.3* then joins
nothing.
"""

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

from . import prose
from .graph import AuthoredGraph, ClaimNode
from .inventory import CITATION_SPAN_RE, PRINTED_NAME_RE, Inventory
from .tree import ANCHOR_RENDERING_RE, LIST_SEPARATOR, Tree, strip_markers, unquote

#: A printed result number. The sub-item suffix sits outside this and is never
#: part of a join.
NUMBER = r"(?:[A-Z]|\d+)(?:\.\d+)*"
_ITEM = rf"{NUMBER}[a-z]?(?!\w)"
_ITEM_RE = re.compile(rf"({NUMBER})[a-z]?(?!\w)")

#: A mention handed to a citation by its next words — *Theorem 3 of* [Smith],
#: *Proposition 5 in* [Jones]. The citation's own bracket is the form skipped by
#: blanking; this is the same naming of another work's result, written outside it.
_CITED_AFTER_RE = re.compile(r'\s+(?:of|in)\s+<span\s+class="citation"')


@dataclass(frozen=True)
class HandNamed:
    """One edge candidate a hand-written name produced: ``source``'s body names ``target``."""

    source: str
    target: str
    document: str
    #: 0-based line of the mention, in the document's own line numbering.
    line: int
    #: The mention as the page writes it, whitespace collapsed — *Lemmas 2 and 3*.
    mention: str


def claim_names(inventory: Inventory) -> frozenset[str]:
    """The display names this corpus states its results under."""
    return frozenset(block.environment for block in inventory.claim_blocks())


def _forms(name: str) -> tuple[str, ...]:
    """``name`` and its plurals, as a list continuation writes them."""
    plural = name[:-1] + "ies" if name.endswith("y") else name + "s"
    return (name, plural)


def _form_pattern(form: str) -> str:
    """One spelling of a name, its first letter in either case and a wrap allowed between words."""
    head, tail = form[0], form[1:]
    return f"[{head.upper()}{head.lower()}]" + r"\s+".join(re.escape(word) for word in tail.split(" "))


def _blank(match: re.Match[str]) -> str:
    return re.sub(r"[^\n]", " ", match.group())


class Vocabulary:
    """One corpus's claim names, compiled into the two readings this module makes of them."""

    def __init__(self, names: frozenset[str]):
        spellings = {form: name for name in names for form in _forms(name)}
        # Longest first, so a name that extends another (*Main Theorem*) is tried before it.
        alternation = "|".join(_form_pattern(form) for form in sorted(spellings, key=len, reverse=True))
        self._canonical = {form.casefold(): name.casefold() for form, name in spellings.items()}
        self._mention_re = re.compile(
            rf"(?<!\w)(?P<name>{alternation})\s+(?P<items>{_ITEM}(?:{LIST_SEPARATOR}{_ITEM})*)"
        )
        self._label_re = re.compile(rf"(?P<name>{alternation})\s+(?P<number>{NUMBER})[a-z]?\.?(?:\s*\(.*\))?")

    def _name(self, spelled: str) -> str:
        return self._canonical[" ".join(spelled.split()).casefold()]

    def mentions(self, text: str) -> Iterator[tuple[int, str, tuple[str, ...], str]]:
        """Every hand-written mention in ``text``: offset, name, numbers, and the words as written.

        Anchors and citations are blanked first, line breaks kept, so an offset
        still counts lines.
        """
        page = text
        text = CITATION_SPAN_RE.sub(_blank, ANCHOR_RENDERING_RE.sub(_blank, text))
        for match in self._mention_re.finditer(text):
            if _CITED_AFTER_RE.match(page, match.end()):
                continue
            numbers = tuple(dict.fromkeys(_ITEM_RE.findall(match.group("items"))))
            yield match.start(), self._name(match.group("name")), numbers, " ".join(match.group().split())

    def label(self, text: str) -> tuple[str, str] | None:
        """``text``'s name and number where the whole of it is one printed label, else ``None``."""
        found = self._label_re.fullmatch(text.strip())
        return None if found is None else (self._name(found.group("name")), found.group("number"))


def _block_claims(graph: AuthoredGraph, inventory: Inventory) -> Iterator[tuple[ClaimNode, int, int]]:
    """Each claim-bearing block's claim, with the block's extent — the join ``graph.read`` made, by locator."""
    for block in inventory.claim_blocks():
        node = next((found for found in graph.hosted_by(block.document) if found.locator == block.display), None)
        if node is not None:
            yield node, block.start, block.end


def printed_claims(
    graph: AuthoredGraph, inventory: Inventory, vocabulary: Vocabulary
) -> Mapping[tuple[str, str], tuple[ClaimNode, ...]]:
    """Every claim a printed name and number joins, by ``(name, number)``.

    A block joins by its display line's printed span; a claim with no block by
    its title, where the title is that label and nothing more — a prose claim
    titled *Lemma 2 implies the bound* names a lemma rather than being one.
    """
    joined: dict[tuple[str, str], list[ClaimNode]] = {}
    in_blocks = set()
    for node, _, _ in _block_claims(graph, inventory):
        in_blocks.add(node.id)
        printed = PRINTED_NAME_RE.match(node.locator or "")
        key = vocabulary.label(printed.group(1)) if printed is not None else None
        if key is not None:
            joined.setdefault(key, []).append(node)
    for node in graph.nodes.values():
        if node.equation is None and node.id not in in_blocks:
            key = vocabulary.label(node.title)
            if key is not None:
                joined.setdefault(key, []).append(node)
    return {key: tuple(nodes) for key, nodes in joined.items()}


def _bodies(tree: Tree, graph: AuthoredGraph, inventory: Inventory) -> Iterator[tuple[ClaimNode, str, int, str]]:
    """Each node's body: the claim, its document, the body's first line and its text.

    The text is marker-stripped and unquoted, line for line, so a line counted
    in it is a line of the written document.
    """
    lines: dict[str, list[str]] = {}

    def text_of(document: str) -> list[str]:
        if document not in lines:
            lines[document] = unquote(strip_markers(tree.documents[document].text)).splitlines()
        return lines[document]

    in_blocks = set()
    for node, start, end in _block_claims(graph, inventory):
        in_blocks.add(node.id)
        body = "\n".join(text_of(node.document)[start:end])
        # The display line opens with the block's own printed name and number —
        # its label, not a mention of anything. Read as one, it names every other
        # block a corpus printed under the same number.
        own = PRINTED_NAME_RE.search(body, len(text_of(node.document)[start]) + 1)
        if own is not None:
            body = body[: own.start()] + _blank(own) + body[own.end() :]
        yield node, node.document, start, body

    in_prose: dict[str, list[ClaimNode]] = {}
    for node in graph.nodes.values():
        if node.equation is None and node.id not in in_blocks:
            in_prose.setdefault(node.document, []).append(node)
    for document, nodes in sorted(in_prose.items()):
        leaf = prose.readable(tree.documents[document], inventory)
        for paragraph in leaf.render.paragraphs:
            numbers = sorted(paragraph.lines)
            for node in nodes:
                if prose.marks(leaf, paragraph, node.id):
                    yield node, document, numbers[0], "\n".join(text_of(document)[line] for line in numbers)


def harvest(tree: Tree, graph: AuthoredGraph, inventory: Inventory) -> tuple[HandNamed, ...]:
    """Every candidate a hand-written name joins, one per ``(source, target)``, in id order."""
    names = claim_names(inventory)
    if not names:
        return ()
    vocabulary = Vocabulary(names)
    printed = printed_claims(graph, inventory, vocabulary)

    found: dict[tuple[str, str], HandNamed] = {}
    for source, document, first, body in _bodies(tree, graph, inventory):
        volume = tree.documents[document].domain
        for offset, name, numbers, written in vocabulary.mentions(body):
            for number in numbers:
                joined = printed.get((name, number), ())
                local = [node for node in joined if tree.documents[node.document].domain == volume]
                for target in local or joined:
                    if target.id != source.id:
                        found.setdefault(
                            (source.id, target.id),
                            HandNamed(
                                source=source.id,
                                target=target.id,
                                document=document,
                                line=first + body.count("\n", 0, offset),
                                mention=written,
                            ),
                        )
    return tuple(found[pair] for pair in sorted(found))
