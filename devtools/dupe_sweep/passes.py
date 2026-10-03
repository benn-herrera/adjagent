"""dupe_sweep — the two passes, ``prose`` and ``python``: each reads its corpus, compares, and reports.

``python`` answers three questions — one concept, two implementations; one constant, two
definitions; one rule, two homes — and prints :data:`UNANSWERED` for the fourth, one word with two
meanings: nothing in the source tells a term's referents apart, so it is reported as unanswered
rather than approximated.

Every stage sorts its output, so the same tree yields the same report, byte for byte.
"""

from .clustering import clusters
from .constants import constant_candidates, constants
from .doc_sentences import doc_units
from .prose_corpus import CHUNK_SOURCE, TEMPLATE_PREFIXES, prose_texts
from .python_corpus import CODE_PREFIX, CODE_UNSWEPT, code_corpus
from .report import render_clusters, render_constants, render_header
from .shapes import shape_units
from .window_index import overlap_clusters, overlaps

#: Defaults per pass, tuned on this tree for a list short enough to read. Twelve
#: words is about the shortest passage whose repetition is a statement rather
#: than a turn of phrase. Thirty AST nodes is roughly ten lines, and a structural
#: clone is worth a reader's time only when it is near-exact, hence the higher
#: containment bar and the tighter length window on code.
PROSE_DEFAULTS = {"min_tokens": 12, "coverage": 0.85}
CODE_DEFAULTS = {"min_tokens": 30, "coverage": 0.90, "width": 5, "length_ratio": 0.7, "probes": 8}
DOC_DEFAULTS = {"min_tokens": 12, "coverage": 0.85, "width": 4, "length_ratio": 0.6, "probes": None}

#: Printed in place of the fourth question's findings.
UNANSWERED = (
    "    No mechanical proxy for a term's referent survives contact with this tree.\n"
    '    The instance this was calibrated against is "row", used for a steps.Step and\n'
    "    for a line of a plan table — and every proxy for it (a name bound to two\n"
    "    types, a word appearing in two modules) fires on every common name here.\n"
    "    What would answer it is a glossary naming each project term and the one\n"
    "    thing it may refer to; the check is mechanical after that, guesswork before."
)


def prose_pass(*, rev: str | None, settings: dict, out) -> None:
    texts = prose_texts(rev=rev)
    found = overlap_clusters(texts, overlaps(texts, **settings))
    words = sum(len(text.words) for text in texts)
    render_header(
        "prose", rev, f"{CHUNK_SOURCE}, {', '.join(TEMPLATE_PREFIXES)}", f"{len(texts)} texts, {words} words", out
    )
    render_clusters("one passage, two places", found, out=out)


def python_pass(*, rev: str | None, settings: dict, out) -> None:
    files = code_corpus(rev=rev)
    shapes = shape_units(files)
    docs = doc_units(files)
    render_header(
        "python", rev, f"{CODE_PREFIX}/ less {', '.join(CODE_UNSWEPT)}", f"{len(shapes) + len(docs)} spans", out
    )
    render_clusters("one concept, two implementations", clusters(shapes, **settings), out=out)
    render_constants(constant_candidates(constants(files)), out=out)
    render_clusters("one rule, two homes", clusters(docs, **DOC_DEFAULTS), out=out)
    print("\n## one word, two meanings — UNANSWERED, not zero candidates", file=out)
    print(UNANSWERED, file=out)
