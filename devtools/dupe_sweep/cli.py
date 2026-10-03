"""dupe_sweep — the command line: argparse surface and pass dispatch."""

import argparse
import logging
import sys
from collections.abc import Sequence

from .corpus import SweepError
from .passes import CODE_DEFAULTS, PROSE_DEFAULTS, prose_pass, python_pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dupe_sweep",
        description="Enumerate one-idea-two-places candidates. Emits candidates, never verdicts.",
    )
    parser.add_argument("pass_name", choices=("prose", "python"), metavar="PASS", help="prose | python")
    parser.add_argument("--rev", help="sweep the tree at this git revision instead of the working tree")
    parser.add_argument(
        "--min-words",
        type=int,
        help="shortest passage reported, in words (prose, default 12; runs under 8 are never found)"
        " / shortest function compared, in AST nodes (python, default 30)",
    )
    parser.add_argument(
        "--coverage",
        type=float,
        help="containment two exact runs need to merge into one passage (prose, default 0.85)"
        " / a pair needs to be a candidate (python, default 0.9)",
    )
    return parser


def main(argv: Sequence[str] | None = None, *, out=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)
    out = out or sys.stdout
    settings = dict(PROSE_DEFAULTS if args.pass_name == "prose" else CODE_DEFAULTS)
    if args.min_words is not None:
        settings["min_tokens"] = args.min_words
    if args.coverage is not None:
        settings["coverage"] = args.coverage
    try:
        if args.pass_name == "prose":
            prose_pass(rev=args.rev, settings=settings, out=out)
        else:
            python_pass(rev=args.rev, settings=settings, out=out)
    except SweepError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
