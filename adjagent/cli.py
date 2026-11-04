"""`adjagent <verb>` (or `python3 -m adjagent <verb>`): the argparse surface and dispatch.

The report is `print`: a short-lived CLI whose exit code is its contract, where
a logging setup would be a second reporting regime.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from adjagent import __version__
from adjagent.agents_file import install_agents_file, scope_name
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
from adjagent.install import install, uncommitted_sources
from adjagent.install_target import agents_file_harness, resolve_install_target
from adjagent.render import render_agents_file, render_all, write_renders
from adjagent.vocabulary import HarnessText, key


def _add_tuning_flags(verb: argparse.ArgumentParser, *, harness_default: str | None, harness_help: str) -> None:
    verb.add_argument("--harness", default=harness_default, metavar="NAME", help=harness_help)
    verb.add_argument("--family", default=DEFAULT_FAMILY, metavar="NAME", help="the model family to tune for")
    verb.add_argument(
        TIER_MAP_FLAG,
        dest="tier_spec",
        metavar="SPEC",
        help="each tier=member; all=<model>+exceptions; bare=all",
    )
    verb.add_argument(ALIAS_MAP_FLAG, dest="alias_spec", metavar="SPEC", help="tier=alias for every tier, or all=")


def build_parser() -> argparse.ArgumentParser:
    """One verb, required: `render --out DIR` and `install TARGET [--subdir DIR] [--verbose]
    [--with-kb] [--install-global-agents-file]`, each with the tuning flags; `install-agents-file DIR [HARNESS]`;
    `render-agents-file HARNESS OUT`; `version`; and `harness NAME KEY`.
    allow_abbrev=False on every parser."""
    parser = argparse.ArgumentParser(prog="adjagent", allow_abbrev=False)
    verbs = parser.add_subparsers(dest="verb", required=True)
    render = verbs.add_parser("render", help="render every definition into DIR", allow_abbrev=False)
    render.add_argument("--out", required=True, type=Path, metavar="DIR", help="an existing output root")
    _add_tuning_flags(render, harness_default=DEFAULT_HARNESS, harness_help="the harness to render for")
    installing = verbs.add_parser(
        "install", help="render into the target's ROOT and copy the packages", allow_abbrev=False
    )
    installing.add_argument("target", type=Path, metavar="TARGET", help="an existing project or harness directory")
    installing.add_argument(
        "--subdir",
        metavar="DIR",
        default=None,
        help="install into TARGET/DIR, TARGET being the project root; empty installs into TARGET itself",
    )
    installing.add_argument("--verbose", "-v", action="store_true", help="report every file written")
    installing.add_argument(
        "--with-kb", action="store_true", help="install the kb definitions and the kb-tools package"
    )
    installing.add_argument(
        "--install-global-agents-file",
        action="store_true",
        help="on a user-level install, also install the agents file at ROOT; ignored on a project install",
    )
    _add_tuning_flags(
        installing,
        harness_default=None,
        harness_help="the harness to install for; detected from TARGET when not given",
    )
    agents_file = verbs.add_parser("install-agents-file", help="install the agents file block", allow_abbrev=False)
    agents_file.add_argument("directory", type=Path, metavar="DIR")
    agents_file.add_argument(
        "harness",
        metavar="HARNESS",
        nargs="?",
        default=None,
        help="inferred, when absent or empty, from DIR being a harness's user directory",
    )
    fresh = verbs.add_parser("render-agents-file", help="write a fresh agents file to OUT", allow_abbrev=False)
    fresh.add_argument("harness", metavar="HARNESS")
    fresh.add_argument("out", type=Path, metavar="OUT")
    verbs.add_parser("version", help="print the version, bare", allow_abbrev=False)
    query = verbs.add_parser("harness", help="print one harness value", allow_abbrev=False)
    query.add_argument("name", metavar="NAME")
    query.add_argument("key", choices=[key(part) for part in HarnessText], metavar="KEY")
    return parser


def _tuned(args: argparse.Namespace, *, harness: str) -> Render:
    ctx = build_render(harness=harness, family=args.family, tier_spec=args.tier_spec, alias_spec=args.alias_spec)
    aliases = "" if ctx.alias_map is None else f" alias[{map_spec(ctx.alias_map)}]"
    print(f"tuning: family={ctx.family.name} tier[{map_spec(ctx.tier_map)}]{aliases} harness={ctx.harness.name}")
    return ctx


def _run(args: argparse.Namespace) -> None:
    if args.verb == "render":
        renders = render_all(_tuned(args, harness=args.harness))
        for path in write_renders(args.out, renders):
            print(f"wrote {path}")
    elif args.verb == "install":
        target = resolve_install_target(args.target, harness=args.harness, subdir=args.subdir)
        install(
            target.root,
            _tuned(args, harness=target.harness),
            verbose=args.verbose,
            with_kb=args.with_kb,
            project_root=target.project_root,
            uncommitted=uncommitted_sources,
            global_agents_file=args.install_global_agents_file,
        )
    elif args.verb == "install-agents-file":
        harness = harness_named(agents_file_harness(args.directory, args.harness))
        install_agents_file(args.directory, harness, uncommitted=uncommitted_sources())
    elif args.verb == "render-agents-file":
        harness = harness_named(args.harness)
        args.out.write_text(render_agents_file(harness, scope=scope_name(harness, args.out.parent)), encoding="utf-8")
        print(f"wrote {args.out}")
    elif args.verb == "version":
        print(__version__)
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
