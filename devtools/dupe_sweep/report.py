"""dupe_sweep — the report: a pass's header, its candidate lists, and the file-pair tally above each."""

from collections import Counter
from collections.abc import Sequence
from itertools import combinations

from .clustering import Cluster
from .constants import Constant
from .normalization import ellipsis


def file_pairs(found: Sequence[Cluster]) -> list[tuple[int, str, str]]:
    """(shared candidates, path, path) for file pairs that cluster together repeatedly.

    Forty near-identical sentences between two definitions is one finding, not
    forty, and the forty rows are what stops a report from being read. A file
    paired with itself is a rule stated twice inside one file.
    """
    counts: Counter[tuple[str, str]] = Counter()
    for cluster in found:
        paths = sorted(unit.path for unit, _ in cluster.members)
        counts.update({(left, right) for left, right in combinations(paths, 2)})
    return sorted(
        ((shared, left, right) for (left, right), shared in counts.items() if shared > 1),
        key=lambda row: (-row[0], row[1], row[2]),
    )


def render_pairs(found: Sequence[Cluster], *, out) -> None:
    pairs = file_pairs(found)
    if not pairs:
        return
    print(f"\n### file pairs sharing more than one candidate — {len(pairs)}", file=out)
    for shared, left, right in pairs:
        print(f"    {shared:>4}  {left}  <->  {'itself' if left == right else right}", file=out)


def render_clusters(title: str, found: Sequence[Cluster], *, out) -> None:
    print(f"\n## {title} — {len(found)} candidate{'' if len(found) == 1 else 's'}", file=out)
    render_pairs(found, out=out)
    for number, cluster in enumerate(found, start=1):
        scores = [score for _, score in cluster.members]
        span = f"{min(scores):.0%}" if min(scores) == max(scores) else f"{min(scores):.0%}-{max(scores):.0%}"
        print(
            f"\n[{number}] {len(cluster.members)} sites, {span} of a "
            f"{len(cluster.representative.tokens)}-token span shared",
            file=out,
        )
        print(f"    {ellipsis(cluster.representative.text)}", file=out)
        for unit, score in cluster.members:
            print(f"    {score:>4.0%}  {unit.site}", file=out)


def render_constants(found: Sequence[tuple[str, list[Constant]]], *, out) -> None:
    print(f"\n## one constant, two definitions — {len(found)} candidate{'' if len(found) == 1 else 's'}", file=out)
    for number, (why, sites) in enumerate(found, start=1):
        print(f"\n[{number}] {ellipsis(why)}", file=out)
        for site in sites:
            print(f"    {site.path}:{site.line} {site.name} = {ellipsis(site.value, 60)}", file=out)


def render_header(pass_name: str, rev: str | None, scope: str, compared: str, out) -> None:
    print(f"# {pass_name} sweep — {scope}", file=out)
    print(f"# tree: {rev or 'working tree'} — {compared} compared", file=out)
    print("# candidates, not verdicts: every one below is a question for a reader.", file=out)
