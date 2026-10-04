"""Replay recorded claim-graph letter-ask groups through the production reader, at each concurrency named.

Invoked through `just replay-claimgraph-asks` (kb-testing/justfile), with the
local-inference env file sourced into the environment and PYTHONPATH at an
installed toolchain's agents directory: the reader and its ``reader-system``
fragment are that toolchain's, and the server and model are the env file's,
the way a build's are.

Each ``--record`` is a group record ``letters.ask_group`` wrote. The replay puts
the record's own prompts — its prefix and each call's tail — through
``ask.ask_without_tools`` by way of ``letters.ask_group``, so the scheduling is
the build's: the first item alone, then ``KB_READER_CONCURRENCY`` asks in
flight, set from each ``--concurrency`` level in turn. A re-ask the replay
needs and the record does not hold re-issues the item's first prompt; the
summary counts those.

Per level, under ``--out/<record-stem>/w<N>/``: the replay's own group record
and each call's captured stream. On stdout, one tab-separated line per call,
then one summary line per level. ``W_eff`` is the plan's: the serial time of a
group's warm asks over the time they took at that level, the serial time being
the mean warm-item wall time at concurrency 1; it is ``-`` unless 1 is among the
levels.
"""

import argparse
import json
import logging
import os
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from kb_tools.kb_claimgraph import ask, letters

OUT = Path(__file__).resolve().parents[2] / ".claude-temp" / "ask-replay"

_log = logging.getLogger("replay-claimgraph-asks")

CALL_COLUMNS = (
    "record",
    "concurrency",
    "item",
    "call",
    "wall-s",
    "duration-api-ms",
    "cache-read-tokens",
    "prompt-tokens",
    "output-tokens",
    "thinking-blocks",
    "letter",
    "recorded-letter",
)


@dataclass(frozen=True)
class Level:
    """One replay of one record at one concurrency."""

    concurrency: int
    elapsed: float
    replayed: letters.GroupRecord


def _recorded_prompt(prefix: str, calls: Sequence[Mapping[str, object]], returned: str | None) -> str:
    """The prompt the record holds for this call: the first, or the re-ask where it holds one."""
    call = calls[1] if returned is not None and len(calls) > 1 else calls[0]
    return prefix + str(call["tail"])


def _items(record: Mapping[str, object]) -> tuple[letters.LetterItem, ...]:
    prefix = str(record["prefix"])
    return tuple(
        letters.LetterItem(str(item["item"]), tuple(item["offered"]), partial(_recorded_prompt, prefix, item["calls"]))
        for item in record["items"]
    )


def _replay(record: Mapping[str, object], *, concurrency: int, reader: letters.LetterReader, out: Path) -> Level:
    os.environ[letters.READER_CONCURRENCY_ENV] = str(concurrency)
    started = time.monotonic()
    replayed = letters.ask_group(
        kind=letters.Kind(record["kind"]),
        group=str(record["group"]),
        items=_items(record),
        reader=reader,
        record_dir=out,
    )
    return Level(concurrency, time.monotonic() - started, replayed)


def _item_wall(item: letters.ItemRecord) -> float:
    return sum(call.wall_seconds for call in item.calls)


def _field(value: object) -> str:
    return "-" if value is None else str(value)


def _call_lines(stem: str, level: Level, recorded: Mapping[str, str | None]) -> list[str]:
    lines = []
    for item in level.replayed.items:
        for number, call in enumerate(item.calls, start=1):
            stats = call.stats
            figures = (
                (None, None, None, None, None)
                if stats is None
                else (
                    stats.duration_api_ms,
                    stats.cache_read_input_tokens,
                    stats.prompt_tokens,
                    stats.output_tokens,
                    stats.thinking_blocks,
                )
            )
            row = (stem, level.concurrency, item.item, number, f"{call.wall_seconds:.2f}", *figures)
            lines.append("\t".join(map(_field, (*row, call.letter, recorded[item.item]))))
    return lines


def _summary(stem: str, level: Level, *, serial_warm_item: float | None, recorded: Mapping[str, object]) -> str:
    items = level.replayed.items
    first = _item_wall(items[0])
    warm_elapsed = level.elapsed - first
    warm = len(items) - 1
    w_eff = "-" if serial_warm_item is None or warm_elapsed <= 0 else f"{warm * serial_warm_item / warm_elapsed:.2f}"
    held = {str(item["item"]): len(item["calls"]) for item in recorded["items"]}
    reissued = sum(len(item.calls) > held[item.item] for item in items)
    changed = sum(item.letter != entry["letter"] for item, entry in zip(items, recorded["items"], strict=True))
    return (
        f"summary\t{stem}\tconcurrency={level.concurrency} elapsed-s={level.elapsed:.1f} first-item-s={first:.2f} "
        f"warm-items={warm} warm-elapsed-s={warm_elapsed:.1f} W_eff={w_eff} letters-changed={changed} "
        f"unrecorded-reasks-reissued={reissued} {letters.AskTotals.of([level.replayed]).detail()}"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--record", type=Path, action="append", required=True, help="a group record (repeatable)")
    parser.add_argument(
        "--concurrency", type=int, nargs="+", default=[1], help="asks in flight after each group's first (default 1)"
    )
    parser.add_argument("--out", type=Path, default=OUT, help=f"where replay records land (default {OUT})")
    arguments = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", stream=sys.stderr)
    if any(level < 1 for level in arguments.concurrency):
        parser.error("--concurrency levels are whole numbers of asks, at least 1")

    print("\t".join(CALL_COLUMNS))
    summaries = []
    for path in arguments.record:
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("kind") not in set(letters.Kind) or not record.get("items"):
            parser.error(f"{path} is not a letter-ask group record with items")
        stem = path.stem
        recorded = {str(item["item"]): item["letter"] for item in record["items"]}
        levels = []
        for concurrency in arguments.concurrency:
            out = arguments.out.resolve() / stem / f"w{concurrency}"
            reader = partial(ask.ask_without_tools, captures=out / "captures")
            _log.info("%s: %d item(s) at concurrency %d -> %s", stem, len(record["items"]), concurrency, out)
            level = _replay(record, concurrency=concurrency, reader=reader, out=out)
            levels.append(level)
            print("\n".join(_call_lines(stem, level, recorded)), flush=True)
        serial = next((level for level in levels if level.concurrency == 1), None)
        warm_items = serial.replayed.items[1:] if serial is not None else ()
        serial_warm_item = sum(map(_item_wall, warm_items)) / len(warm_items) if warm_items else None
        summaries += [_summary(stem, level, serial_warm_item=serial_warm_item, recorded=record) for level in levels]
    print("\n".join(summaries))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
