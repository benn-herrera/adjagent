"""Read-only comparison of replayed claim-graph asks against the build's own answers.

Invoked through `just compare-claimgraph-asks` (kb-testing/justfile), with
PYTHONPATH at the fixture's installed agents directory so every answer is read
by the parse the build ran. Positional arguments name the replayed models — the
directories `replay-claimgraph-asks.py` wrote under ``.claude-temp/ask-replay/``.

The baseline is each ask's capture in ``<fixture>/<ASKS_RELPATH>``, read as the
build read it (the last ``result`` event wins). Each answer is parsed by its
kind's own parse — ``parse_answer`` for a dependency ask, ``parse_identify_answer``
for a node-pass identify ask, ``parse_claim_reask_answer`` for a per-claim
re-ask — so a verdict means what the build means. Only asks a model has a
completed capture for are counted for that model.

Produces, under ``.claude-temp/ask-replay/`` at the repository root:
  summary.md         per ask kind: agreement with the baseline, parse failures,
                     a confusion breakdown of disagreements, duration and
                     output tokens per ask
  disagreements.tsv  every ask where a model's verdict differs from the baseline

Writes nothing else.
"""

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from kb_tools.inference import claude
from kb_tools.kb_claimgraph import ask
from kb_tools.kb_claimgraph.__main__ import ASKS_RELPATH
from kb_tools.kb_claimgraph.identify import Trigger
from kb_tools.kb_claimgraph.report import AnswerFormatError

OUT = Path(__file__).resolve().parents[2] / ".claude-temp" / "ask-replay"
BASELINE = "baseline"
PROMPT_SUFFIX = ".prompt.md"
CAPTURE_SUFFIX = ".capture.jsonl"
COMPLETED_EXITS = frozenset({0, 3, 4})

KINDS = ("depends", "identify", "claim-reask")
REASK_RE = re.compile(r"\.md-(" + "|".join(trigger.value for trigger in Trigger) + r")$")
CANDIDATE_RE = re.compile(r"^- `(clm-[a-z0-9]+)`")


@dataclass(frozen=True)
class Call:
    """One answered ask: the text that came back, and what it cost."""

    text: str | None
    duration_ms: float | None
    output_tokens: int | None
    model: str | None


@dataclass
class Reading:
    """One answer read by its kind's parse: a comparable verdict, or why there is none."""

    status: str  # "parsed", "parse-failure" or "no-answer"
    verdict: object = None
    detail: str = ""
    refusals: int = 0


@dataclass
class Tally:
    compared: int = 0
    agreed: int = 0
    readings: Counter = field(default_factory=Counter)
    confusion: Counter = field(default_factory=Counter)
    durations: list[float] = field(default_factory=list)
    #: The baseline's durations over the same asks, so a replay's are read against like for like.
    baseline_durations: list[float] = field(default_factory=list)
    tokens: list[int] = field(default_factory=list)
    refusals: int = 0


def kind_of(stem: str) -> str:
    name = stem.split("-", 1)[1]
    if name.startswith("clm-"):
        return "depends"
    return "claim-reask" if REASK_RE.search(name) else "identify"


def baseline_call(capture: Path) -> Call:
    state = claude._StreamState()
    model = None
    for line in capture.read_text(encoding="utf-8").splitlines():
        inits = state.inits
        state.record(line)
        if state.inits > inits:
            model = json.loads(line).get("model")
    result = state.result
    if result is None or claude._result_errored(result):
        return Call(text=None, duration_ms=None, output_tokens=None, model=model)
    usage = result.get("usage") or {}
    return Call(
        text=result.get("result"),
        duration_ms=result.get("duration_ms"),
        output_tokens=usage.get("output_tokens"),
        model=model,
    )


def replay_call(capture: Path) -> Call | None:
    if not capture.is_file():
        return None
    record = json.loads(capture.read_text(encoding="utf-8"))
    if record.get("exit") not in COMPLETED_EXITS:
        return None
    return Call(
        text=record.get("text") if record.get("exit") == 0 else None,
        duration_ms=record.get("duration_ms"),
        output_tokens=(record.get("usage") or {}).get("completion_tokens"),
        model=record.get("served_model"),
    )


def claim_id(stem: str) -> str:
    return stem.split("-", 1)[1]


def candidates(prompt: str) -> tuple[str, ...]:
    """The candidate ids a dependency ask enumerated: its own claim's line excluded."""
    return tuple(found.group(1) for line in prompt.splitlines() if (found := CANDIDATE_RE.match(line)))


def read(kind: str, stem: str, call: Call) -> Reading:
    if not call.text:
        return Reading("no-answer")
    try:
        if kind == "depends":
            return Reading("parsed", frozenset(ask.parse_answer(call.text, claim=claim_id(stem))))
        if kind == "claim-reask":
            record = ask.parse_claim_reask_answer(call.text, document=stem)
            return Reading("parsed", "none-of-these" if record is None else record.label)
        answer = ask.parse_identify_answer(call.text, document=stem)
    except AnswerFormatError as error:
        return Reading("parse-failure", detail=str(error).replace("\n", " ")[:300])
    verdict = (
        frozenset(record.label for record in answer.claims),
        tuple(sorted((v.paragraph, "claim" if v.title is not None else "not-a-claim") for v in answer.verdicts)),
        bool(answer.no_claim),
        answer.nothing_further,
    )
    return Reading("parsed", verdict, refusals=len(answer.refusals))


def show(kind: str, verdict: object) -> str:
    if kind == "depends":
        return " ".join(sorted(verdict)) or "(none)"
    if kind == "claim-reask":
        return str(verdict)
    labels, verdicts, no_claim, nothing_further = verdict
    parts = [f"claims={','.join(sorted(labels)) or '-'}"]
    parts.append("paragraphs=" + (",".join(f"{p}:{v}" for p, v in verdicts) or "-"))
    if no_claim:
        parts.append("no-claim")
    if nothing_further:
        parts.append("nothing-further")
    return "; ".join(parts)


def set_relation(base: frozenset, other: frozenset) -> str:
    if base == other:
        return "same"
    if other < base:
        return "subset of baseline"
    if other > base:
        return "superset of baseline"
    return "overlapping" if base & other else "disjoint"


def confusion(kind: str, base: object, other: object, *, offered: tuple[str, ...]) -> list[str]:
    """The disagreement's shape, as counted categories."""
    if kind == "depends":
        rows = [f"selection {set_relation(base, other)}"]
        rows += [
            f"candidate baseline={'yes' if c in base else 'no'} replay={'yes' if c in other else 'no'}"
            for c in offered
            if (c in base) != (c in other)
        ]
        return rows
    if kind == "claim-reask":
        return [
            f"{'none-of-these' if base == 'none-of-these' else 'label'} -> {'none-of-these' if other == 'none-of-these' else 'label'}"
        ]
    base_labels, base_verdicts, base_no, base_further = base
    labels, verdicts, no_claim, further = other
    rows = []
    if base_labels != labels:
        rows.append(f"claim labels {set_relation(base_labels, labels)}")
    base_map, other_map = dict(base_verdicts), dict(verdicts)
    for paragraph in sorted(set(base_map) | set(other_map)):
        if base_map.get(paragraph) != other_map.get(paragraph):
            rows.append(f"paragraph {base_map.get(paragraph, 'missing')} -> {other_map.get(paragraph, 'missing')}")
    if base_no != no_claim:
        rows.append(f"no-claim {'dropped' if base_no else 'added'}")
    if base_further != further:
        rows.append(f"nothing-further {'dropped' if base_further else 'added'}")
    return rows


def stats(values: list[float]) -> str:
    if not values:
        return "– / –"
    return f"{statistics.fmean(values):,.0f} / {statistics.median(values):,.0f}"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--fixture", type=Path, required=True, help="repository root the build ran in")
    parser.add_argument("models", nargs="+", help="replayed model directories under .claude-temp/ask-replay/")
    arguments = parser.parse_args(argv)

    asks_dir = arguments.fixture.resolve() / ASKS_RELPATH
    stems = sorted(p.name[: -len(PROMPT_SUFFIX)] for p in asks_dir.glob(f"*{PROMPT_SUFFIX}"))
    tallies: dict[tuple[str, str], Tally] = {}
    disagreements: list[tuple[str, ...]] = []
    baseline_models: Counter = Counter()

    for stem in stems:
        kind = kind_of(stem)
        prompt = (asks_dir / f"{stem}{PROMPT_SUFFIX}").read_text(encoding="utf-8")
        base_call = baseline_call(asks_dir / f"{stem}{CAPTURE_SUFFIX}")
        baseline_models[base_call.model] += 1
        base = read(kind, stem, base_call)
        for model, call in [(BASELINE, base_call)] + [
            (m, replay_call(OUT / m / f"{stem}{CAPTURE_SUFFIX}")) for m in arguments.models
        ]:
            if call is None:
                continue
            tally = tallies.setdefault((kind, model), Tally())
            reading = base if model == BASELINE else read(kind, stem, call)
            tally.readings[reading.status] += 1
            tally.refusals += reading.refusals
            if call.duration_ms is not None:
                tally.durations.append(call.duration_ms / 1000)
                if model != BASELINE and base_call.duration_ms is not None:
                    tally.baseline_durations.append(base_call.duration_ms / 1000)
            if call.output_tokens is not None:
                tally.tokens.append(call.output_tokens)
            if model == BASELINE:
                continue
            if base.status != "parsed" or reading.status != "parsed":
                if base.status != reading.status:
                    disagreements.append(
                        (
                            kind,
                            stem,
                            model,
                            base.status,
                            reading.status,
                            "parse outcome differs",
                            reading.detail or base.detail,
                        )
                    )
                continue
            tally.compared += 1
            if base.verdict == reading.verdict:
                tally.agreed += 1
                continue
            rows = confusion(kind, base.verdict, reading.verdict, offered=candidates(prompt))
            tally.confusion.update(rows)
            disagreements.append(
                (kind, stem, model, show(kind, base.verdict), show(kind, reading.verdict), "; ".join(rows), "")
            )

    models = [BASELINE] + arguments.models
    lines = [
        "# Claim-graph ask replay: replayed models vs the build's answers",
        "",
        f"script: {Path(__file__).resolve()}",
        f"asks: {asks_dir} ({len(stems)})",
        f"baseline: the build's own captures, model per init event {dict(baseline_models)}",
        "",
        "Agreement is over asks both answers parsed; a verdict is the parse's own reading — "
        "dependency: the selected id set; identify: claim labels, per-paragraph verdicts, "
        "no-claim and nothing-further; per-claim re-ask: the label or none-of-these. "
        "Durations are wall seconds per call (baseline: the CLI's duration_ms); tokens are output "
        "tokens (baseline: CLI usage.output_tokens; replay: completion_tokens), thinking included where the endpoint counts it.",
        "",
    ]
    for kind in KINDS:
        if not any((kind, m) in tallies for m in models):
            continue
        lines += [
            f"## {kind}",
            "",
            "| model | asks | parsed | parse failures | no answer | refused blocks | compared | agree | agreement | duration s mean / median | baseline s, same asks | output tokens mean / median |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for model in models:
            tally = tallies.get((kind, model))
            if tally is None:
                continue
            total = sum(tally.readings.values())
            failure_rate = tally.readings["parse-failure"] / total if total else 0
            agreement = "–" if model == BASELINE or not tally.compared else f"{tally.agreed / tally.compared:.1%}"
            lines.append(
                f"| {model} | {total} | {tally.readings['parsed']} | {tally.readings['parse-failure']} ({failure_rate:.1%}) | "
                f"{tally.readings['no-answer']} | {tally.refusals} | {'–' if model == BASELINE else tally.compared} | "
                f"{'–' if model == BASELINE else tally.agreed} | {agreement} | {stats(tally.durations)} | "
                f"{'–' if model == BASELINE else stats(tally.baseline_durations)} | {stats(tally.tokens)} |"
            )
        for model in arguments.models:
            tally = tallies.get((kind, model))
            if tally is None or not tally.confusion:
                continue
            lines += ["", f"Disagreements, {model} (counted per category; one ask may carry several):", ""]
            lines += [f"  {category}: {count}" for category, count in tally.confusion.most_common()]
        lines.append("")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    header = ("kind", "ask", "model", "baseline", "replay", "confusion", "detail")
    body = ["\t".join(header)] + ["\t".join(cell.replace("\t", " ") for cell in row) for row in disagreements]
    (OUT / "disagreements.tsv").write_text("\n".join(body) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
