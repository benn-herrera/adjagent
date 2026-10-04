"""dupe_sweep — prose as exact word runs: the window index, run widening, and passage merging.

Every window of :data:`WINDOW` words is indexed; only the window at each :data:`WINDOW`-th word is
looked up, before its own stride is inserted, so each text meets only what precedes it. A window
in more than :data:`MAX_WINDOW_SITES` places is framing and finds nothing. Each hit widens to the
exact run it sits in, and runs between one pair of texts merge across gaps of at most
:data:`MAX_MERGE_GAP` words while the merged pair still scores ``coverage``.

Bounds, in words of the prose text — articles already dropped: a run of ``2 * WINDOW - 1`` (15) or
more identical words is always found, so any shared run of 15 or more non-article words is. A run of
``WINDOW`` to 14 words is found only when a stride head of the later text falls far enough inside
it — its first word at most ``length - WINDOW`` words before a multiple of ``WINDOW`` — and a
shorter run never is. A paraphrase with no exact core of that length is invisible. Repeats inside
one text count. A passage's line is its first word's line.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .clustering import Cluster, containment, find_root, gather_clusters
from .normalization import ProseText

#: The prose pass's window width in words, and its query stride.
WINDOW = 8
#: A prose window occurring in more than this many places is shared framing.
MAX_WINDOW_SITES = 24
#: The most words, on either side, between two exact runs that merge into one
#: passage — room for an inserted parenthetical or a reworded clause.
MAX_MERGE_GAP = 12


@dataclass(frozen=True, order=True)
class Span:
    """Words `start` up to `end` of the text numbered `text`."""

    text: int
    start: int
    end: int


def window_hits(texts: Sequence[ProseText]) -> list[tuple[Span, Span]]:
    """Pairs of `WINDOW`-word spans holding the same words, the earlier site first.

    Each text is walked in strides of `WINDOW` words. At each stride's head the
    one window starting there is looked up, and only then are the stride's own
    windows inserted, so a text meets only the texts before it and its own
    earlier words, and every pair is found once. A shared run of
    `2 * WINDOW - 1` words or more always contains a stride head's whole window;
    a shorter one is found only when a head falls early enough inside it.
    """
    index: dict[tuple[str, ...], list[Span]] = {}
    found: list[tuple[tuple[str, ...], Span, Span]] = []
    for number, text in enumerate(texts):
        last = len(text.words) - WINDOW  # the last offset a whole window starts at
        for head in range(0, last + 1, WINDOW):
            query = text.words[head : head + WINDOW]
            sites = index.get(query, [])
            if len(sites) <= MAX_WINDOW_SITES:
                found.extend((query, site, Span(number, head, head + WINDOW)) for site in sites)
            for at in range(head, min(head + WINDOW, last + 1)):
                index.setdefault(text.words[at : at + WINDOW], []).append(Span(number, at, at + WINDOW))
    # A window can pass the cap after an early query read it; the cap is on where
    # it occurs in the whole corpus, so it is applied again against the full index.
    return [(left, right) for query, left, right in found if len(index[query]) <= MAX_WINDOW_SITES]


def _exact_run(texts: Sequence[ProseText], left: Span, right: Span) -> tuple[Span, Span]:
    """`left` and `right`, which hold the same words, widened to the longest run they share."""
    ours, theirs = texts[left.text].words, texts[right.text].words
    back = 0
    while left.start > back and right.start > back and ours[left.start - back - 1] == theirs[right.start - back - 1]:
        back += 1
    ahead = left.end - left.start
    while left.start + ahead < len(ours) and right.start + ahead < len(theirs):
        if ours[left.start + ahead] != theirs[right.start + ahead]:
            break
        ahead += 1
    return (
        Span(left.text, left.start - back, left.start + ahead),
        Span(right.text, right.start - back, right.start + ahead),
    )


def overlaps(texts: Sequence[ProseText], *, min_tokens: int, coverage: float) -> list[tuple[Span, Span]]:
    """Every passage two texts share, or one text holds twice, the earlier site first.

    Window hits widen to the exact runs they sit in, and consecutive runs between
    one pair of texts merge into one passage when they advance together — each
    gap at most `MAX_MERGE_GAP` words — and the merged pair still scores
    `coverage` by containment. That second stage is what keeps an inserted
    parenthetical or a reworded clause from splitting one copied paragraph into
    two findings; at `coverage` 1.0 it merges only across words one side
    inserted, never across words both sides changed.
    """
    runs = sorted(
        {_exact_run(texts, left, right) for left, right in window_hits(texts)},
        key=lambda pair: (pair[0].text, pair[1].text, pair[0].start, pair[1].start),
    )
    merged: list[tuple[Span, Span]] = []
    for left, right in runs:
        if merged:
            last_left, last_right = merged[-1]
            if (
                (last_left.text, last_right.text) == (left.text, right.text)
                and 0 <= left.start - last_left.end <= MAX_MERGE_GAP
                and 0 <= right.start - last_right.end <= MAX_MERGE_GAP
            ):
                joined_left = Span(left.text, last_left.start, left.end)
                joined_right = Span(right.text, last_right.start, right.end)
                if containment(_words(texts, joined_left), _words(texts, joined_right)) >= coverage:
                    merged[-1] = (joined_left, joined_right)
                    continue
        merged.append((left, right))
    return [pair for pair in merged if min(span.end - span.start for span in pair) >= min_tokens]


def _words(texts: Sequence[ProseText], span: Span) -> tuple[str, ...]:
    return texts[span.text].words[span.start : span.end]


def overlap_clusters(texts: Sequence[ProseText], found: Iterable[tuple[Span, Span]]) -> list[Cluster]:
    """Passages grouped across every site that shares them, sorted.

    Spans in one text that overlap are one site, so a paragraph copied into seven
    texts is one candidate with seven sites rather than twenty-one pairs.
    """
    pairs = list(found)
    sites: list[Span] = []
    site_of: dict[Span, int] = {}
    for span in sorted({span for pair in pairs for span in pair}):
        if sites and sites[-1].text == span.text and span.start < sites[-1].end:
            sites[-1] = Span(span.text, sites[-1].start, max(sites[-1].end, span.end))
        else:
            sites.append(span)
        site_of[span] = len(sites) - 1

    parent = list(range(len(sites)))
    for left, right in pairs:
        parent[find_root(parent, site_of[right])] = find_root(parent, site_of[left])
    return gather_clusters([texts[site.text].unit(site.start, site.end) for site in sites], parent)
