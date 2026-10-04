"""The unmarked-reference shortlist: every claim node ranked against every other by what their statements share.

Mechanical, and the draft an ask judges rather than a verdict: a similarity score
is not evidence that one claim's text points at another. For each source the
pool is every other node, less every pair whose unordered form is already an
edge candidate (``attribute.narrow``) — that pair is asked about already.

The ranking is cosine similarity of TF-IDF vectors, sublinear term frequency
and smoothed IDF, with the IDF taken over the target statements; ties go to the
lower target id, so the same statements always give the same ranking. A
statement's terms are its words through :func:`kb_write.ops.canonical_form` —
the fold tier 2 searches with, which drops maths — plus the maths symbols of its
inline spans and display fences, so two claims about ``\\lambda_c`` meet on it.
"""

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

from .. import kb_links
from ..kb_write import ops
from .inventory import math_fence_extents

#: How many of a source's best-ranked targets are asked about.
K = 5

#: Words too common to tell two claims apart, and the LaTeX control words the fold leaves behind.
STOPWORDS = frozenset("""the and for that this with from are is be as by of to in on at or an it its not no
    which when where then than these those their there such can may must will would into
    under over between each every both only also more most any all one two has have had
    was were been being what how why who whom our we us but if so do does done per via
    text mathrm frac left right cdot quad mathbb begin end href data reference type class
    span id label eqref ref qquad operatorname displaystyle""".split())

#: A maths symbol: a control word or a single letter, carrying one subscript or none — a bare letter
#: needs the subscript, since ``x`` alone tells no two claims apart.
_SYMBOL_RE = re.compile(r"\\[A-Za-z]+(?:_\{[^{}]*\}|_[A-Za-z0-9])?|[A-Za-z](?:_\{[^{}]*\}|_[A-Za-z0-9])")


def _maths(text: str) -> list[str]:
    """The LaTeX of every inline maths span, then of every display fence, in text order."""
    lines = text.splitlines()
    fences, _ = math_fence_extents(lines)
    inline = [span[2:-2] for span in kb_links.INLINE_MATH_RE.findall(text)]
    return inline + ["\n".join(lines[start + 1 : end - 1]) for start, end in fences]


def _symbols(text: str) -> list[str]:
    found = []
    for span in _maths(text):
        for raw in _SYMBOL_RE.findall(span):
            if raw.lstrip("\\").split("_", 1)[0].lower() in STOPWORDS:
                continue
            found.append("m:" + re.sub(r"_\{(\w)\}", r"_\1", raw.replace(" ", "")))
    return found


def tokens(text: str) -> list[str]:
    """``text``'s terms: its folded words longer than two letters, then its maths symbols, prefixed ``m:``."""
    words = [
        word
        for word in ops.canonical_form(text).split()
        if len(word) > 2 and not word.isdigit() and word not in STOPWORDS
    ]
    return words + _symbols(text)


def idf(bags: Mapping[str, Sequence[str]]) -> dict[str, float]:
    """Smoothed inverse document frequency of every term over ``bags``."""
    frequency = Counter(term for words in bags.values() for term in set(words))
    count = len(bags)
    return {term: math.log((1 + count) / (1 + df)) + 1 for term, df in frequency.items()}


def weigh(words: Sequence[str], idf: Mapping[str, float]) -> dict[str, float]:
    """The L2-normalised sublinear-tf vector of ``words``; a term ``idf`` lacks carries no weight."""
    weights = {term: (1 + math.log(tf)) * idf[term] for term, tf in Counter(words).items() if term in idf}
    norm = math.sqrt(sum(value * value for value in weights.values())) or 1.0
    return {term: value / norm for term, value in weights.items()}


def cosine(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    """The dot product of two normalised vectors."""
    if len(a) > len(b):
        a, b = b, a
    return sum(value * b.get(term, 0.0) for term, value in a.items())


def rank(
    statements: Mapping[str, str], *, sources: Iterable[str], candidate_pairs: Iterable[tuple[str, str]]
) -> dict[str, list[str]]:
    """Per source, every other node of ``statements`` best first, less pairs already candidates either way round.

    ``statements`` is every node's statement, keyed by node id; every source is one of its keys.
    """
    excluded = {frozenset(pair) for pair in candidate_pairs}
    bags = {node: tokens(statement) for node, statement in statements.items()}
    weights = idf(bags)
    vectors = {node: weigh(words, weights) for node, words in bags.items()}
    ranked = {}
    for source in sources:
        scored = sorted(
            (-cosine(vectors[source], vectors[target]), target)
            for target in statements
            if target != source and frozenset((source, target)) not in excluded
        )
        ranked[source] = [target for _, target in scored]
    return ranked


def top_k(ranked: Mapping[str, Sequence[str]], k: int = K) -> dict[str, list[str]]:
    """Each source's first ``k`` targets of :func:`rank`, or all of them where it has fewer."""
    return {source: list(targets[:k]) for source, targets in ranked.items()}
