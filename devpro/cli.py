"""`devpro <verb>` (or `python3 -m devpro <verb>`): the argparse surface and dispatch.

The report is `print`: a short-lived CLI whose exit code is its contract, where
a logging setup would be a second reporting regime.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from devpro import __version__
from devpro.agents_file import preflighted_agents_file_install, scope_name
from devpro.context import (
    ALIAS_MAP_FLAG,
    DEFAULT_FAMILY,
    DEFAULT_HARNESS,
    DEFAULT_PLUGIN,
    TIER_MAP_FLAG,
    Render,
    build_render,
    harness_named,
    map_spec,
    plugin_named,
    plugins,
)
from devpro.errors import InputError
from devpro.install import preflighted_install, uncommitted_sources
from devpro.install_target import agents_file_harness, resolve_install_target
from devpro.render import render_agents_file, render_all, write_renders
from devpro.vocabulary import HarnessText, key

_DRY_RUN_HELP = "print what the install would create, change and remove; write nothing"


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


def _add_plugin(verb: argparse.ArgumentParser) -> None:
    verb.add_argument(
        "--plugin",
        choices=list(plugins()),
        default=DEFAULT_PLUGIN,
        metavar="NAME",
        help=f"one of {', '.join(plugins())}; default %(default)s",
    )


def build_parser() -> argparse.ArgumentParser:
    """One verb, required: `render --out DIR` and `install TARGET [--subdir DIR] [--verbose] [--dry-run]`,
    each with the tuning flags; `install-agents-file DIR [--harness NAME] [--dry-run]`;
    `render-agents-file HARNESS OUT`; and two maintainer helpers hidden from `--help`: `harness NAME KEY`,
    and `plugins`, which prints each plugin's name, one per line. Each verb but `plugins` takes
    `[--plugin=NAME]`, default `context.DEFAULT_PLUGIN`. The top-level `--version` prints the bare version.
    allow_abbrev=False on every parser.
    """
    parser = argparse.ArgumentParser(prog="devpro", allow_abbrev=False)
    parser.add_argument("--version", action="version", version=__version__)
    # The hidden verbs are added without help, and the verb list is set below from every other: argparse
    # (3.9) still prints a subparser added with help=SUPPRESS, as "==SUPPRESS==", and lists every choice
    # in the usage line.
    verbs = parser.add_subparsers(dest="verb", required=True)
    render = verbs.add_parser("render", help="render the plugin's definitions into DIR", allow_abbrev=False)
    _add_plugin(render)
    render.add_argument("--out", required=True, type=Path, metavar="DIR", help="an existing output root")
    _add_tuning_flags(render, harness_default=DEFAULT_HARNESS, harness_help="the harness to render for")
    installing = verbs.add_parser(
        "install", help="render the plugin into its install directory and copy its packages", allow_abbrev=False
    )
    _add_plugin(installing)
    installing.add_argument("target", type=Path, metavar="TARGET", help="an existing project or harness directory")
    installing.add_argument(
        "--subdir",
        metavar="DIR",
        default=None,
        help="the harness directory is TARGET/DIR, TARGET being the project root, DIR inside it; empty makes it TARGET itself",
    )
    installing.add_argument("--verbose", "-v", action="store_true", help="report every file written")
    installing.add_argument("--dry-run", action="store_true", help=_DRY_RUN_HELP)
    _add_tuning_flags(
        installing,
        harness_default=None,
        harness_help="the harness to install for; detected from TARGET when not given",
    )
    agents_file = verbs.add_parser(
        "install-agents-file", help="install the plugin's agents file block", allow_abbrev=False
    )
    _add_plugin(agents_file)
    agents_file.add_argument("directory", type=Path, metavar="DIR")
    agents_file.add_argument(
        "--harness",
        metavar="NAME",
        default=None,
        help="inferred, when absent or empty, from DIR being a harness's user directory",
    )
    agents_file.add_argument(
        "--dry-run", action="store_true", help="print which files the install would create or change; write nothing"
    )
    fresh = verbs.add_parser(
        "render-agents-file", help="write the plugin's fresh agents file to OUT", allow_abbrev=False
    )
    _add_plugin(fresh)
    fresh.add_argument("harness", metavar="HARNESS")
    fresh.add_argument("out", type=Path, metavar="OUT")
    query = verbs.add_parser("harness", allow_abbrev=False)
    _add_plugin(query)
    query.add_argument("name", metavar="NAME")
    query.add_argument("key", choices=[key(part) for part in HarnessText], metavar="KEY")
    verbs.add_parser("plugins", allow_abbrev=False)
    hidden = {"harness", "plugins"}
    verbs.metavar = "{" + ",".join(name for name in verbs.choices if name not in hidden) + "}"
    return parser


def _tuned(args: argparse.Namespace, *, harness: str) -> Render:
    ctx = build_render(
        harness=harness, plugin=args.plugin, family=args.family, tier_spec=args.tier_spec, alias_spec=args.alias_spec
    )
    aliases = "" if ctx.alias_map is None else f" alias[{map_spec(ctx.alias_map)}]"
    print(f"tuning: family={ctx.family.name} tier[{map_spec(ctx.tier_map)}]{aliases} harness={ctx.harness.name}")
    return ctx


def _run(args: argparse.Namespace) -> None:
    if args.verb == "render":
        renders = render_all(_tuned(args, harness=args.harness))
        for path in write_renders(args.out, renders):
            print(f"wrote {path}")
    elif args.verb == "install":
        target = resolve_install_target(args.target, harness=args.harness, plugin=args.plugin, subdir=args.subdir)
        preflighted_install(
            target.harness_dir,
            _tuned(args, harness=target.harness),
            verbose=args.verbose,
            project_root=target.project_root,
            uncommitted=uncommitted_sources,
            dry_run=args.dry_run,
        )
    elif args.verb == "install-agents-file":
        harness = harness_named(agents_file_harness(args.directory, args.harness))
        preflighted_agents_file_install(
            args.directory, harness, plugin_named(args.plugin), uncommitted=uncommitted_sources, dry_run=args.dry_run
        )
    elif args.verb == "render-agents-file":
        harness = harness_named(args.harness)
        text = render_agents_file(harness, plugin_named(args.plugin), scope=scope_name(harness, args.out.parent))
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    elif args.verb == "plugins":
        print("\n".join(plugins()))
    else:
        bound = harness_named(args.name).bound(plugin_named(args.plugin).name)
        print(bound.text(HarnessText("_".join(args.key.split("-")))))


def main(argv: list[str] | None = None) -> None:
    """Run the verb. An InputError or OSError prints `error: <msg>` on stderr and exits 2."""
    args = build_parser().parse_args(argv)
    try:
        _run(args)
    except (InputError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
