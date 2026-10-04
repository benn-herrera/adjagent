"""What a mechanical per-source shortlist reaches, and how many asks it costs.

Read-only. Run through measure-kb-roots (kb-testing/justfile), which hands every staged kb-root as
a positional argument:

    just -f kb-testing/justfile measure-kb-roots \
        tools/measure-unmarked-shortlist.py

Inputs:
  every kb-root handed     node counts by kind, sources, existing candidates, and the asks each K
                           implies (per-source top-K, and all-pairs) — the ask arithmetic per corpus;
  the kb-root under ModernCorp/
                           the shortlist itself, ranked four ways (below);
  .claude-temp/pristine-compare/edges.tsv
                           C9's per-edge table (kb-testing/tools/compare-to-pristine.py). Its rows whose
                           mark_split is "unmarked — needs reading" are the misses measured against;
                           ours_sources / ours_targets are the C9-matched node sets of each end.

What "reached" means here: some ordered pair (s, t) with s among a miss's ours_sources and t among
its ours_targets is on s's shortlist. Reached is the ceiling C7 can deliver on that miss — not that
a reader would answer yes, and not that the text carries the relationship.

The shortlist, per source claim s (every node that is not a minted equation): every other node t of
the build, less every pair whose unordered form is already an edge candidate (attribute.narrow over the
node-pass record), ranked by cosine of TF-IDF vectors, ties to the lower target id. Four rankings:
  c9/statement        compare-to-pristine's tokens over each node's statement (classify.statements)
  c9/statement+leaf   source side adds its whole leaf; targets stay statements
  wm/statement        the production ranking, kb_tools.kb_claimgraph.shortlist.rank: words
                      (kb_write.ops.canonical_form) plus maths symbols, statement only
  wm/statement+leaf   shortlist's tokens and weighting, source side adds its leaf
IDF is computed over the target statements only, so the leaf context adds no term a target lacks.

Embedding rankings, each asked for by a trailing ``--embed <model>=<templates>`` (repeatable):
  <model>/<templates>  one vector per statement from the server's embeddings endpoint, the source's
                       statement through the query template and every target's through the document
                       template (EMBED_TEMPLATES), ranked by cosine over the same pool, ties to the
                       lower target id
The server is ANTHROPIC_BASE_URL with /v1, authenticated by ANTHROPIC_AUTH_TOKEN, both read from the
environment. A model the server does not list is skipped, and the summary says so. Vectors are cached
per model and rendered text under the output directory, so a re-run asks for nothing it already has.
Templates are named rather than given inline because measure-kb-roots word-splits its trailing args.
The names, each model's card prompts and a ``-plain`` with no prompt: nomic, nomic-plain, qwen-instruct,
qwen-plain, gemma-search, gemma-factcheck, gemma-plain, nemotron, nemotron-plain, arctic, arctic-plain.
Statements are sent whole, with no client-side cap at the model's context.

    just -f kb-testing/justfile measure-kb-roots tools/measure-unmarked-shortlist.py \
        --embed nomicai-embed=nomic --embed nomicai-embed=nomic-plain

Outputs under .claude-temp/unmarked-shortlist/ at the repository root: roots.tsv, misses.tsv, curve.tsv,
summary.md, and the embedding cache embedding-cache/<model>.jsonl. Writes nothing else.
"""

import argparse
import hashlib
import importlib.util
import json
import math
import operator
import os
import re
import sys
import urllib.error
from collections import Counter
from pathlib import Path

from kb_tools import kb_pipeline
from kb_tools.kb_claimgraph import attribute, classify, graph, hand_named, inventory, shortlist, tree
from kb_tools.kb_claimgraph.tree import strip_markers, unquote
from liaison_tools import openai_chat

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / ".claude-temp" / "unmarked-shortlist"
EDGES = REPO / ".claude-temp" / "pristine-compare" / "edges.tsv"
COMPARE = REPO / "kb-testing" / "tools" / "compare-to-pristine.py"
UNMARKED = "unmarked — needs reading"
KS = (1, 2, 3, 5, 8, 10, 15, 20, 30, 50)
#: Measured per-call cost at concurrency 1 (the ModernCorp letter-ask build of 2026-10-03).
SECONDS_PER_ASK = 3.1
LOCALITY = ("same document", "same directory", "same paper", "cross paper")

COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def load_compare():
    spec = importlib.util.spec_from_file_location("compare_to_pristine", COMPARE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMPARE_MODULE = load_compare()


# --- reading a build ------------------------------------------------------------------


class Build:
    """One kb-root's nodes, statements, leaves and existing candidate pairs, read through production code."""

    def __init__(self, kb_root: Path):
        documents = tree.read(kb_root)
        sites = inventory.scan(documents)
        authored = graph.read(documents, sites)
        statement = classify.statements(documents, authored, sites)
        record = kb_pipeline.read_node_pass(kb_root.parent)
        narrowed = attribute.narrow(documents, authored, sites, record)
        blocks = {node.id for node, _, _ in hand_named._block_claims(authored, sites)}

        self.root = kb_root
        self.nodes = dict(sorted(authored.nodes.items()))
        self.kind = {
            nid: "equation" if node.equation is not None else "block" if nid in blocks else "prose"
            for nid, node in self.nodes.items()
        }
        self.document = {nid: node.document for nid, node in self.nodes.items()}
        self.statement = {nid: statement(node) for nid, node in self.nodes.items()}
        self.leaf = {
            path: COMMENT_RE.sub(" ", unquote(strip_markers(document.text)))
            for path, document in documents.documents.items()
        }
        self.sources = [nid for nid, kind in self.kind.items() if kind != "equation"]
        self.candidate_pairs = [candidate.pair for candidate in narrowed.candidates]
        self.excluded = {frozenset(pair) for pair in self.candidate_pairs}
        self.candidates = len(narrowed.candidates)

    def pool(self, source: str) -> list[str]:
        """Every target the shortlist may offer ``source``: any other node, less pairs already candidates."""
        return [t for t in self.nodes if t != source and frozenset((source, t)) not in self.excluded]


# --- tokens and vectors ---------------------------------------------------------------


def c9_tokens(text: str) -> list[str]:
    return COMPARE_MODULE.tokens(text)


def rankings(build: Build, tokenize, *, with_leaf: bool) -> dict[str, dict[str, int]]:
    """Per source, the 1-based rank of every pool target, by cosine descending then target id."""
    target_bags = {nid: tokenize(build.statement[nid]) for nid in build.nodes}
    idf = shortlist.idf(target_bags)
    targets = {nid: shortlist.weigh(words, idf) for nid, words in target_bags.items()}
    ranked = {}
    for source in build.sources:
        text = build.statement[source]
        if with_leaf:
            text = text + "\n" + build.leaf[build.document[source]]
        vector = shortlist.weigh(tokenize(text), idf)
        scored = sorted((-shortlist.cosine(vector, targets[t]), t) for t in build.pool(source))
        ranked[source] = {t: rank for rank, (_, t) in enumerate(scored, start=1)}
    return ranked


def production_ranking(build: Build) -> dict[str, dict[str, int]]:
    """wm/statement: the stage's own ranking, as the 1-based rank of every pool target per source."""
    ordered = shortlist.rank(build.statement, sources=build.sources, candidate_pairs=build.candidate_pairs)
    return {source: {t: rank for rank, t in enumerate(targets, start=1)} for source, targets in ordered.items()}


VARIANTS = {
    "c9/statement": lambda build: rankings(build, c9_tokens, with_leaf=False),
    "c9/statement+leaf": lambda build: rankings(build, c9_tokens, with_leaf=True),
    "wm/statement": production_ranking,
    "wm/statement+leaf": lambda build: rankings(build, shortlist.tokens, with_leaf=True),
}


# --- embedding rankings ---------------------------------------------------------------

PLAIN = ("{text}", "{text}")
#: Named (query, document) templates; ``{text}`` is the node's statement. The prefixes are the model
#: cards' own; the server is assumed to add none of its own.
EMBED_TEMPLATES = {
    "nomic": ("search_query: {text}", "search_document: {text}"),
    "nomic-plain": PLAIN,
    "qwen-instruct": (
        "Instruct: Given a mathematical claim, retrieve the claims whose results it relies on\nQuery: {text}",
        "{text}",
    ),
    "qwen-plain": PLAIN,
    "gemma-search": ("task: search result | query: {text}", "title: none | text: {text}"),
    "gemma-factcheck": ("task: fact checking | query: {text}", "title: none | text: {text}"),
    "gemma-plain": PLAIN,
    "nemotron": ("query: {text}", "passage: {text}"),
    "nemotron-plain": PLAIN,
    "arctic": ("query: {text}", "{text}"),
    "arctic-plain": PLAIN,
}
EMBED_BATCH = 32
EMBED_CACHE = OUT / "embedding-cache"
#: The K the threshold section looks under: misses reached at or inside it.
THRESHOLD_K = 5


def embed_spec(raw: str) -> tuple[str, str]:
    model, sep, templates = raw.rpartition("=")
    if not sep or not model or templates not in EMBED_TEMPLATES:
        raise argparse.ArgumentTypeError(f"expected <model>=<{'|'.join(EMBED_TEMPLATES)}>, got {raw!r}")
    return model, templates


def unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class Embedder:
    """One model's vectors, cached per rendered text in EMBED_CACHE/<model>.jsonl."""

    def __init__(self, *, base_url: str, token: str, model: str):
        self.base_url, self.token, self.model = base_url, token, model
        self.path = EMBED_CACHE / (re.sub(r"[^\w.-]", "_", model) + ".jsonl")
        self.cache: dict[str, list[float]] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                self.cache[record["sha"]] = record["vector"]

    @staticmethod
    def key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def unit_vectors(self, texts: list[str]) -> list[list[float]]:
        missing = list({key: text for text in texts if (key := self.key(text)) not in self.cache}.values())
        EMBED_CACHE.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as out:
            for start in range(0, len(missing), EMBED_BATCH):
                batch = missing[start : start + EMBED_BATCH]
                vectors = openai_chat.post_embeddings(
                    base_url=self.base_url, token=self.token, model=self.model, texts=batch
                )
                for text, vector in zip(batch, vectors):
                    self.cache[self.key(text)] = vector
                    out.write(json.dumps({"sha": self.key(text), "vector": vector}) + "\n")
        return [unit(self.cache[self.key(text)]) for text in texts]


def embedding_rankings(
    build: Build, embedder: Embedder, templates: str
) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, float]]]:
    """Per source, the 1-based rank of every pool target by cosine descending then target id, and the cosines."""
    query, document = EMBED_TEMPLATES[templates]
    targets = dict(
        zip(build.nodes, embedder.unit_vectors([document.format(text=build.statement[t]) for t in build.nodes]))
    )
    queries = embedder.unit_vectors([query.format(text=build.statement[s]) for s in build.sources])
    ranked, scores = {}, {}
    for source, vector in zip(build.sources, queries):
        scores[source] = {t: sum(map(operator.mul, vector, targets[t])) for t in build.pool(source)}
        ordered = sorted(scores[source], key=lambda t: (-scores[source][t], t))
        ranked[source] = {t: rank for rank, t in enumerate(ordered, start=1)}
    return ranked, scores


def embedders_served(specs: list[tuple[str, str]]) -> tuple[dict[str, Embedder], list[str]]:
    """An Embedder per requested model the server lists, and a note per model it could not serve."""
    if not specs:
        return {}, []
    base, token = os.environ.get("ANTHROPIC_BASE_URL", ""), os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    if not base or not token:
        return {}, ["embedding variants skipped: ANTHROPIC_BASE_URL or ANTHROPIC_AUTH_TOKEN is not set"]
    base = base.rstrip("/") + "/v1"
    if (problem := openai_chat.validate_base_url(base, allow_http=True)) is not None:
        return {}, [f"embedding variants skipped: {problem}"]
    try:
        listed = set(openai_chat.list_models(base, token))
    except (urllib.error.URLError, OSError, ValueError) as error:
        return {}, [f"embedding variants skipped: listing the server's models failed: {error}"]
    wanted = dict.fromkeys(model for model, _ in specs)
    notes = [f"skipped {model}: the server does not list it" for model in wanted if model not in listed]
    return {m: Embedder(base_url=base, token=token, model=m) for m in wanted if m in listed}, notes


# --- locality and asks ----------------------------------------------------------------


def locality(a: str, b: str) -> str:
    if a == b:
        return LOCALITY[0]
    if a.rsplit("/", 1)[0] == b.rsplit("/", 1)[0]:
        return LOCALITY[1]
    if a.split("/")[0] == b.split("/")[0]:
        return LOCALITY[2]
    return LOCALITY[3]


def asks_at(build: Build, k: int | None) -> int:
    """Per-source top-k asks; ``None`` is every pool pair (all-pairs)."""
    return sum(len(build.pool(s)) if k is None else min(k, len(build.pool(s))) for s in build.sources)


def scoped_pairs(build: Build, widest: str) -> int:
    limit = LOCALITY.index(widest)
    return sum(
        1
        for s in build.sources
        for t in build.pool(s)
        if LOCALITY.index(locality(build.document[s], build.document[t])) <= limit
    )


def hours(asks: int) -> str:
    return f"{asks * SECONDS_PER_ASK / 3600:.1f}"


# --- the misses -----------------------------------------------------------------------


def misses() -> list[dict[str, object]]:
    lines = EDGES.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    rows = [dict(zip(header, line.split("\t"))) for line in lines[1:] if line.strip()]
    return [
        {
            "edge": f"{row['ref_source']}->{row['ref_target']}",
            "sources": row["ours_sources"].split(),
            "targets": row["ours_targets"].split(),
        }
        for row in rows
        if row.get("mark_split") == UNMARKED
    ]


def best(ranked: dict[str, dict[str, int]], sources: list[str], targets: list[str]) -> tuple[int | None, str]:
    """The best rank any (s, t) pair reaches on s's shortlist, and that pair."""
    found = [(ranked[s][t], f"{s}->{t}") for s in sources if s in ranked for t in targets if t in ranked[s]]
    return min(found) if found else (None, "")


def threshold_lines(
    measured: list[dict[str, object]],
    name: str,
    ranked: dict[str, dict[str, int]],
    scores: dict[str, dict[str, float]],
) -> list[str]:
    """Each miss reached at K <= THRESHOLD_K: its pair's cosine beside its source's top-1, and the asks a
    threshold admitting all of them would cost, absolute or as a gap below each source's top-1."""
    top1 = {s: max(by_target.values(), default=0.0) for s, by_target in scores.items()}
    rows = []
    for miss in measured:
        forward, backward = miss[name]
        if min((r for r in (forward, backward) if r is not None), default=THRESHOLD_K + 1) > THRESHOLD_K:
            continue
        use_forward = forward is not None and (backward is None or forward <= backward)
        sources, targets = miss["ends"]
        rank, pair = best(ranked, sources, targets) if use_forward else best(ranked, targets, sources)
        s, t = pair.split("->")
        rows.append((miss["edge"], "fwd" if use_forward else "rev", rank, scores[s][t], top1[s]))
    lines = ["", f"### {name}: misses reached at K <= {THRESHOLD_K}, cosine against the source's top-1", ""]
    if not rows:
        return lines + ["  none"]
    lines += ["| edge | dir | rank | cosine | top-1 | gap |", "|---|---|---|---|---|---|"]
    lines += [
        f"| {e} | {d} | {r} | {c:.3f} | {t:.3f} | {t - c:.3f} |" for e, d, r, c, t in sorted(rows, key=lambda x: x[2])
    ]
    floor = min(row[3] for row in rows)
    widest = max(row[4] - row[3] for row in rows)
    absolute = sum(1 for s in scores for value in scores[s].values() if value >= floor)
    relative = sum(1 for s in scores for value in scores[s].values() if top1[s] - value <= widest)
    every = sum(len(by_target) for by_target in scores.values())
    lines += [
        "",
        f"  every source's cosines: min {min(top1.values()):.3f} / median "
        f"{sorted(top1.values())[len(top1) // 2]:.3f} / max {max(top1.values()):.3f} at top-1",
        f"  absolute threshold cosine >= {floor:.3f} (lowest reached pair): {absolute} of {every} pool pairs",
        f"  relative threshold gap <= {widest:.3f} below top-1 (widest reached gap): {relative} of {every} pool pairs",
    ]
    return lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="C7 shortlist measurement (module docstring).")
    parser.add_argument("roots", nargs="*", type=Path)
    parser.add_argument(
        "--embed",
        action="append",
        type=embed_spec,
        default=[],
        metavar="MODEL=TEMPLATES",
        help=f"repeatable; TEMPLATES is one of: {', '.join(EMBED_TEMPLATES)}",
    )
    arguments = parser.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    roots = sorted(raw.resolve() for raw in arguments.roots)

    root_rows, builds = [], {}
    for root in roots:
        try:
            build = Build(root)
        except Exception as error:  # a hand-made reference KB may not read as a build; say so and go on
            root_rows.append((str(root), f"unreadable: {error!r}"))
            continue
        builds[root] = build
        kinds = Counter(build.kind.values())
        root_rows.append(
            (
                str(root),
                str(len(build.nodes)),
                str(kinds.get("block", 0)),
                str(kinds.get("prose", 0)),
                str(kinds.get("equation", 0)),
                str(len(build.sources)),
                str(build.candidates),
                str(asks_at(build, None)),
                *[str(asks_at(build, k)) for k in KS],
            )
        )

    lines = ["# C7 shortlist measurement", "", f"script: {Path(__file__).resolve()}", ""]
    lines += ["## Asks per kb-root (per-source top-K, and all pairs)", ""]
    lines += [
        "| kb-root | nodes | block | prose | equation | sources | candidates | all-pairs | "
        + " | ".join(f"K={k}" for k in KS)
        + " |",
        "|" + "---|" * (8 + len(KS)),
    ]
    lines += ["| " + " | ".join(row) + " |" for row in root_rows if len(row) > 2]
    lines += [f"- {row[0]}: {row[1]}" for row in root_rows if len(row) == 2]
    others = [b for r, b in builds.items() if not r.parent.name.startswith("ModernCorp")]
    if others:
        lines += ["", f"every non-ModernCorp kb-root together ({len(others)} roots):"]
        lines += [
            f"  all-pairs {sum(asks_at(b, None) for b in others)} asks, {hours(sum(asks_at(b, None) for b in others))} h"
        ]
        lines += [
            f"  K={k}: {sum(asks_at(b, k) for b in others)} asks, {hours(sum(asks_at(b, k) for b in others))} h"
            for k in KS
        ]

    ours = next((b for r, b in builds.items() if r.parent.name == "ModernCorp"), None)
    if ours is None:
        lines += ["", "no ModernCorp kb-root among the arguments: no shortlist measured"]
    else:
        measured = misses()
        ranked = {name: ranking(ours) for name, ranking in VARIANTS.items()}
        embedders, skipped = embedders_served(arguments.embed)
        cosines = {}
        for model, templates in arguments.embed:
            if model in embedders:
                name = f"{model}/{templates}"
                ranked[name], cosines[name] = embedding_rankings(ours, embedders[model], templates)
        miss_rows = []
        for miss in measured:
            sources = [s for s in miss["sources"] if s in ours.nodes and ours.kind[s] != "equation"]
            targets = [t for t in miss["targets"] if t in ours.nodes]
            nearest = min(
                (locality(ours.document[s], ours.document[t]) for s in sources for t in targets if s != t),
                key=LOCALITY.index,
                default="",
            )
            miss["locality"] = nearest
            miss["ends"] = (sources, targets)
            row = [miss["edge"], nearest]
            for name in ranked:
                forward, pair = best(ranked[name], sources, targets)
                backward, _ = best(ranked[name], [t for t in targets if ours.kind.get(t) != "equation"], sources)
                miss[name] = (forward, backward)
                row += ["" if forward is None else str(forward), "" if backward is None else str(backward), pair]
            miss_rows.append(row)
        header = ["edge", "locality"] + [f"{name} {col}" for name in ranked for col in ("fwd", "rev", "best-pair")]
        (OUT / "misses.tsv").write_text(
            "\n".join(["\t".join(header)] + ["\t".join(row) for row in miss_rows]) + "\n", encoding="utf-8"
        )

        lines += ["", f"## Locality of the {len(measured)} unmarked misses (nearest matched pair)", ""]
        lines += [f"  {name}: {sum(1 for m in measured if m['locality'] == name)}" for name in LOCALITY]
        lines += ["", "## All pairs inside a locality scope (ModernCorp): asks and misses reached", ""]
        for name in LOCALITY:
            pairs = scoped_pairs(ours, name)
            reached = sum(
                1 for m in measured if m["locality"] and LOCALITY.index(m["locality"]) <= LOCALITY.index(name)
            )
            lines += [f"  up to {name}: {pairs} asks ({hours(pairs)} h), {reached} of {len(measured)} misses reachable"]

        curve_rows = []
        lines += ["", "## Per-source top-K (ModernCorp): misses reached, forward / either direction", ""]
        lines += [f"  {note}" for note in skipped] + ([""] if skipped else [])
        lines += ["| K | asks | hours | " + " | ".join(ranked) + " |", "|" + "---|" * (3 + len(ranked))]
        for k in KS:
            cells = []
            for name in ranked:
                forward = sum(1 for m in measured if m[name][0] is not None and m[name][0] <= k)
                either = sum(1 for m in measured if any(rank is not None and rank <= k for rank in m[name]))
                cells.append(f"{forward} / {either}")
                curve_rows.append((str(k), name, str(forward), str(either)))
            asks = asks_at(ours, k)
            lines.append(f"| {k} | {asks} | {hours(asks)} | " + " | ".join(cells) + " |")
        (OUT / "curve.tsv").write_text(
            "\n".join(["K\tvariant\tforward\teither"] + ["\t".join(row) for row in curve_rows]) + "\n",
            encoding="utf-8",
        )
        if cosines:
            lines += ["", "## Could a cosine threshold replace a fixed K? (embedding variants)"]
        for name, scores in cosines.items():
            lines += threshold_lines(measured, name, ranked[name], scores)

    (OUT / "roots.tsv").write_text(
        "\n".join(
            [
                "\t".join(
                    ["kb_root", "nodes", "block", "prose", "equation", "sources", "candidates", "all_pairs"]
                    + [f"k{k}" for k in KS]
                )
            ]
            + ["\t".join(row) for row in root_rows]
        )
        + "\n",
        encoding="utf-8",
    )
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
