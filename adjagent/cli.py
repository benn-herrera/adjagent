"""`python3 -m adjagent <verb>`: the argparse surface and dispatch.

The report is `print`: a short-lived CLI whose exit code is its contract, where
a logging setup would be a second reporting regime.
"""

import argparse
import sys
from pathlib import Path

from adjagent.agents_file import install_agents_file, scope_name, uncommitted_sources
from adjagent.context import (
    ALIAS_MAP_FLAG,
    DEFAULT_FAMILY,
    DEFAULT_HARNESS,
    TIER_MAP_FLAG,
    Render,
    build_render,
    harness_named,
    map_spec,
)
from adjagent.errors import InputError
from adjagent.install import install
from adjagent.loading import load
from adjagent.render import render_agents_file, render_all, write_renders
from adjagent.version import VERSION
from adjagent.vocabulary import HarnessText, key


def _add_tuning_flags(verb: argparse.ArgumentParser) -> None:
    verb.add_argument("--harness", default=DEFAULT_HARNESS, metavar="NAME", help="the harness to render for")
    verb.add_argument("--family", default=DEFAULT_FAMILY, metavar="NAME", help="the model family to tune for")
    verb.add_argument(
        TIER_MAP_FLAG,
        dest="tier_spec",
        metavar="SPEC",
        help="each tier=member; all=<model>+exceptions; bare=all",
    )
    verb.add_argument(ALIAS_MAP_FLAG, dest="alias_spec", metavar="SPEC", help="tier=alias for every tier, or all=")


def build_parser() -> argparse.ArgumentParser:
    """One verb, required: `render --out DIR` and `install ROOT [--verbose] [--with-kb]
    [--kbase-dist PATH] [--project-root DIR]`, each with the tuning flags; `install-agents-file
    HARNESS DIR`; `render-agents-file HARNESS OUT`; `harnesses`; `version`; and `harness NAME KEY`.
    allow_abbrev=False on every parser."""
    parser = argparse.ArgumentParser(prog="python3 -m adjagent", allow_abbrev=False)
    verbs = parser.add_subparsers(dest="verb", required=True)
    render = verbs.add_parser("render", help="render every definition into DIR", allow_abbrev=False)
    render.add_argument("--out", required=True, type=Path, metavar="DIR", help="an existing output root")
    _add_tuning_flags(render)
    installing = verbs.add_parser("install", help="render into ROOT and copy the packages", allow_abbrev=False)
    installing.add_argument("root", type=Path, metavar="ROOT", help="the consumer's harness directory")
    installing.add_argument("--verbose", "-v", action="store_true", help="report every file written")
    installing.add_argument(
        "--with-kb", action="store_true", help="install the kb definitions and the kb-tools package"
    )
    installing.add_argument("--kbase-dist", type=Path, metavar="PATH", help="the signed kbase executable to install")
    installing.add_argument(
        "--project-root",
        type=Path,
        metavar="DIR",
        default=None,
        help="the project root the MCP entry and the runner include line are written against, "
        "defaulting to ROOT itself",
    )
    _add_tuning_flags(installing)
    agents_file = verbs.add_parser("install-agents-file", help="install the agents file block", allow_abbrev=False)
    agents_file.add_argument("harness", metavar="HARNESS")
    agents_file.add_argument("directory", type=Path, metavar="DIR")
    fresh = verbs.add_parser("render-agents-file", help="write a fresh agents file to OUT", allow_abbrev=False)
    fresh.add_argument("harness", metavar="HARNESS")
    fresh.add_argument("out", type=Path, metavar="OUT")
    verbs.add_parser("harnesses", help="print every harness name", allow_abbrev=False)
    verbs.add_parser("version", help="print the version, bare", allow_abbrev=False)
    query = verbs.add_parser("harness", help="print one harness value", allow_abbrev=False)
    query.add_argument("name", metavar="NAME")
    query.add_argument("key", choices=[key(part) for part in HarnessText], metavar="KEY")
    return parser


def _tuned(args: argparse.Namespace) -> Render:
    ctx = build_render(harness=args.harness, family=args.family, tier_spec=args.tier_spec, alias_spec=args.alias_spec)
    aliases = "" if ctx.alias_map is None else f" alias[{map_spec(ctx.alias_map)}]"
    print(f"tuning: family={ctx.family.name} tier[{map_spec(ctx.tier_map)}]{aliases} harness={ctx.harness.name}")
    return ctx


def _run(args: argparse.Namespace) -> None:
    if args.verb == "render":
        renders = render_all(_tuned(args))
        for path in write_renders(args.out, renders):
            print(f"wrote {path}")
    elif args.verb == "install":
        install(
            args.root,
            _tuned(args),
            verbose=args.verbose,
            with_kb=args.with_kb,
            kbase_dist=args.kbase_dist,
            project_root=args.project_root,
        )
    elif args.verb == "install-agents-file":
        install_agents_file(args.directory, harness_named(args.harness), uncommitted=uncommitted_sources())
    elif args.verb == "render-agents-file":
        harness = harness_named(args.harness)
        args.out.write_text(render_agents_file(harness, scope=scope_name(harness, args.out.parent)), encoding="utf-8")
        print(f"wrote {args.out}")
    elif args.verb == "harnesses":
        print("\n".join(load("adjagent.harnesses", "HARNESS")))
    elif args.verb == "version":
        print(VERSION)
    else:
        print(harness_named(args.name).text(HarnessText("_".join(args.key.split("-")))))


def main(argv: list[str] | None = None) -> None:
    """Run the verb. An InputError prints `error: <msg>` on stderr and exits 2."""
    args = build_parser().parse_args(argv)
    try:
        _run(args)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
