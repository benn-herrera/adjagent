"""dupe_sweep — the command line: argparse surface and pass dispatch."""

import argparse
import logging
import sys
from collections.abc import Sequence

from .corpus import SweepError
from .passes import CODE_DEFAULTS, python_pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dupe_sweep",
        description="Enumerate one-idea-two-places candidates. Emits candidates, never verdicts.",
    )
    parser.add_argument(
        "pass_name",
        choices=("python",),
        metavar="PASS",
        help="the python pass: one idea in two places across the owned python trees",
    )
    parser.add_argument("--rev", help="sweep the tree at this git revision instead of the working tree")
    parser.add_argument(
        "--min-words",
        type=int,
        help="shortest function compared, in AST nodes (default 30)",
    )
    parser.add_argument(
        "--coverage",
        type=float,
        help="containment a pair needs to be a candidate (default 0.9)",
    )
    return parser


def main(argv: Sequence[str] | None = None, *, out=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)
    out = out or sys.stdout
    settings = dict(CODE_DEFAULTS)
    if args.min_words is not None:
        settings["min_tokens"] = args.min_words
    if args.coverage is not None:
        settings["coverage"] = args.coverage
    try:
        python_pass(rev=args.rev, settings=settings, out=out)
    except SweepError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
