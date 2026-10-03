"""dupe_sweep — containment scoring, and grouping comparable spans into clusters.

Two spans are scored by containment: the fraction of the shorter token run found, in order, in
the longer (``difflib`` matching blocks over the shorter length). Not symmetric ratio, which
scores a statement restated with an added parenthetical 0.77 where containment scores it 0.94.

:func:`clusters` scores only the pairs that share a shingle (a window of ``width`` tokens), never
all pairs; a shingle shared by more than :data:`MAX_BUCKET` units is skipped as framing, and a
real duplicate still reaches its partners through its rarer windows. Sites that share a finding
are unioned, so a seven-way duplicate is one cluster with seven sites, not twenty-one pairs.
"""

import difflib
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import combinations

#: A shingle shared by more than this many units is shared framing, not a
#: duplicate, and expanding it to pairs costs more than it can find.
MAX_BUCKET = 400


@dataclass(frozen=True)
class Unit:
    """One comparable span: a prose passage, a sentence, or one function's structural shape."""

    path: str
    line: int
    label: str
    text: str
    tokens: tuple[str, ...]

    @property
    def site(self) -> str:
        return f"{self.path}:{self.line}" + (f" {self.label}" if self.label else "")

    @property
    def sort_key(self) -> tuple[str, int, str]:
        return (self.path, self.line, self.label)


@dataclass(frozen=True)
class Cluster:
    """Units that say the same thing, with each one's containment against the shortest."""

    representative: Unit
    members: tuple[tuple[Unit, float], ...]


def containment(left: Sequence[str], right: Sequence[str]) -> float:
    """Fraction of the shorter token run that also appears, in order, in the longer."""
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched / min(len(left), len(right))


def find_root(parent: list[int], index: int) -> int:
    """Union-find lookup over `parent`, halving the path as it goes."""
    while parent[index] != index:
        parent[index] = parent[parent[index]]
        index = parent[index]
    return index


def gather_clusters(units: Sequence[Unit], parent: list[int]) -> list[Cluster]:
    """One cluster per union-find group of two or more `units`, sorted."""
    groups: dict[int, list[Unit]] = {}
    for index, unit in enumerate(units):
        groups.setdefault(find_root(parent, index), []).append(unit)

    found = []
    for members in groups.values():
        if len(members) < 2:
            continue
        # The shortest member is the tightest statement of the shared idea, and
        # the one a reader should be shown.
        representative = min(members, key=lambda unit: (len(unit.tokens), unit.sort_key))
        scored = tuple(
            sorted(
                ((unit, containment(unit.tokens, representative.tokens)) for unit in members),
                key=lambda scored_unit: (-scored_unit[1], scored_unit[0].sort_key),
            )
        )
        found.append(Cluster(representative, scored))
    found.sort(key=lambda cluster: (-len(cluster.members), cluster.representative.sort_key))
    return found


def _shingles(tokens: tuple[str, ...], width: int) -> set[tuple[str, ...]]:
    if len(tokens) <= width:
        return {tokens}
    return {tokens[at : at + width] for at in range(len(tokens) - width + 1)}


def clusters(
    units: Iterable[Unit], *, min_tokens: int, coverage: float, width: int, length_ratio: float, probes: int | None
) -> list[Cluster]:
    """Group units whose token runs contain one another, shingle-blocked and sorted.

    `length_ratio` is what keeps containment from chaining: a short span sits
    inside a long one at 100% and would otherwise link everything the long one
    touches. Two spans whose lengths differ by more than this are not compared.

    `probes` indexes each unit under only its rarest windows, and is for a corpus
    whose token vocabulary is small — a code shape draws on a few dozen AST node
    types, so its common windows say nothing and expanding them to pairs costs
    tens of millions of comparisons. None indexes every window, which is what
    natural-language spans want: a restatement's rarest windows are often exactly
    the words it added, so probing is where it would lose its partner.
    """
    kept = sorted((unit for unit in units if len(unit.tokens) >= min_tokens), key=lambda unit: unit.sort_key)

    per_unit = [_shingles(unit.tokens, width) for unit in kept]
    frequency: Counter[tuple[str, ...]] = Counter()
    for shingles in per_unit:
        frequency.update(shingles)

    buckets: dict[tuple[str, ...], list[int]] = {}
    for index, shingles in enumerate(per_unit):
        indexed = sorted(shingles, key=lambda window: (frequency[window], window))
        for shingle in indexed[:probes] if probes else indexed:
            buckets.setdefault(shingle, []).append(index)

    pairs: set[tuple[int, int]] = set()
    for members in buckets.values():
        if len(members) > MAX_BUCKET:
            continue
        pairs.update(combinations(members, 2))  # members are appended in index order

    parent = list(range(len(kept)))
    for left, right in sorted(pairs):
        if find_root(parent, left) == find_root(parent, right):  # already linked — this edge can change nothing
            continue
        sizes = (len(kept[left].tokens), len(kept[right].tokens))
        if min(sizes) / max(sizes) < length_ratio:
            continue
        if containment(kept[left].tokens, kept[right].tokens) >= coverage:
            parent[find_root(parent, right)] = find_root(parent, left)
    return gather_clusters(kept, parent)
