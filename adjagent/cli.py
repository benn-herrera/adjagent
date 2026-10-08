"""`python3 -m adjagent render` and `explain`: the argparse surface and dispatch.

The report is `print`: a short-lived CLI whose exit code is its contract, where
a logging setup would be a second reporting regime.
"""

import argparse
import sys
from pathlib import Path

from adjagent.context import ALIAS_MAP_FLAG, TIER_MAP_FLAG, build_render, map_spec
from adjagent.errors import InputError
from adjagent.render import explain_definition, render_all, write_renders


def _add_tuning_flags(verb: argparse.ArgumentParser) -> None:
    verb.add_argument("--harness", default="claude", metavar="NAME", help="the harness to render for")
    verb.add_argument("--family", default="claude", metavar="NAME", help="the model family to tune for")
    verb.add_argument(TIER_MAP_FLAG, dest="tier_spec", metavar="SPEC", help="tier=member for every tier, or all=")
    verb.add_argument(ALIAS_MAP_FLAG, dest="alias_spec", metavar="SPEC", help="tier=alias for every tier, or all=")


def build_parser() -> argparse.ArgumentParser:
    """Two verbs, one required. `render --out DIR` writes every definition; `explain NAME` prints one,
    each section headed by the class and non-default fields that produced it. Both take --harness NAME
    (default claude), --family NAME (default claude), --model-tier-map SPEC and
    --model-pin-tier-alias-map SPEC. allow_abbrev=False on every parser."""
    parser = argparse.ArgumentParser(prog="python3 -m adjagent", allow_abbrev=False)
    verbs = parser.add_subparsers(dest="verb", required=True)
    render = verbs.add_parser("render", help="render every definition into DIR", allow_abbrev=False)
    render.add_argument("--out", required=True, type=Path, metavar="DIR", help="an existing output root")
    _add_tuning_flags(render)
    explain = verbs.add_parser("explain", help="print one definition with each section's source", allow_abbrev=False)
    explain.add_argument("name", help="the definition's output name")
    _add_tuning_flags(explain)
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run the verb. render reports the tuning and each file written; explain prints the definition.
    An InputError prints `error: <msg>` on stderr and exits 2."""
    args = build_parser().parse_args(argv)
    try:
        ctx = build_render(
            harness=args.harness, family=args.family, tier_spec=args.tier_spec, alias_spec=args.alias_spec
        )
        if args.verb == "explain":
            print(explain_definition(args.name, ctx), end="")
            return
        renders = render_all(ctx)
        aliases = "" if ctx.alias_map is None else f" alias[{map_spec(ctx.alias_map)}]"
        print(f"tuning: family={ctx.family.name} tier[{map_spec(ctx.tier_map)}]{aliases} harness={ctx.harness.name}")
        for path in write_renders(args.out, renders):
            print(f"wrote {path}")
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
