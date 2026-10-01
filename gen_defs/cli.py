"""
Flags common to generate and install:

    --family NAME           the model family whose tuning applies: a bare
                            family name resolved against templates/family/
                            (default: claude), or a path to a family file.
                            Bare MODEL names are not valid values.
    --model-tier-map SPEC   override the tier -> family member map the family
                            declares: comma-separated tier=member pairs, or
                            all=member. Named tiers mask only themselves.
    --model-pin-map SPEC    override the tier -> rendered pin map: same syntax,
                            over model_tuning.DEFAULT_PIN_MAP. Pin text is
                            always in the claude model namespace.
    --harness NAME          the harness whose templates/harness/<NAME>.toml
                            fills @!hrn.<key>!@ markers (default: claude).
    --verbose, -v           list every file, not just the exceptions.

`generate` additionally takes:

    --surfaces WHICH        agents | commands | both (default both): which
                            surface to render. Cannot be combined with the
                            selection globs, which imply it (`discovery`
                            module docstring).
    --agent-glob PATTERNS   restrict the run to the agents outputs matching
                            PATTERNS: one or more fnmatch patterns joined by
                            "|" ("*app-expert*|*-coder*"). See the
                            `discovery` module docstring.
    --command-glob PATTERNS the same, over the commands surface.

`install` takes none of those three: it delivers the product entire, and a
partial install is a future feature.

`install-agents-file HARNESS DIR` takes none of the flags above: it renders
templates/harness/AGENTS.md.tmpl for one harness and installs it into DIR by
block replacement (`agents_file` module docstring).

`dev` is internal and unsupported: it is absent from the main help, and
`dev help` lists its subcommands. They serve this repository's own just
recipes — `dev agents-file-for-harness NAME` prints a harness's agents-file
name, and `dev render-agents-file HARNESS OUT` renders the harness agents file
to the file OUT, whose parent must exist, never overwriting a differing file
(`agents_file` module docstring).

ROOT is asserted to be an existing directory and is otherwise unconstrained —
inside this repository or anywhere else; the surface subdirectories are created
under it as needed. The full per-target safety table (`generation` module
docstring; banner detection, numbered backups, refusal of bannerless files)
applies identically wherever it lands.
"""

import argparse
import sys
from pathlib import Path

from . import __version__
from .agents_file import (
    agents_file_name,
    install_agents_file,
    load_harness,
    probe_templates_revision,
    render_agents_file_text,
    write_agents_file_renders,
)
from .chunks import load_chunks
from .discovery import GlobMap, output_keys, report_selection, split_globs, surface_map, templates, validate_selection
from .errors import InputError
from .generation import generate
from .installation import install
from .markers import FAMILY_NAMESPACE, collect_anchors
from .model_tuning import (
    DEFAULT_FAMILY,
    DEFAULT_HARNESS,
    effective_tuning,
    load_family,
    report_divergence,
    report_overlays,
    report_tuned,
    report_tuning,
    resolve_family,
    tier_binding,
    tier_resolver,
    validate_family_anchors,
    validate_family_members,
)


def build_parser() -> argparse.ArgumentParser:
    """The three public verbs and the internal `dev` one, each declaring only
    the flags it can act on.

    A flag a verb does not declare is unrepresentable there rather than
    refused by hand: `install` takes neither `--surfaces` nor a selection glob,
    so a partial install cannot be asked for in the first place.

    Prefix abbreviation is off on every parser built here, main and subcommand
    alike: it would silently keep a renamed flag alive as a prefix of the
    spelling that replaced it, whose value means something else entirely, so a
    rename would land as a wrong-argument bug instead of an unknown-flag error.
    """
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "root",
        type=Path,
        metavar="ROOT",
        help="the output root: an existing directory, whose agents/ and "
        "commands/ subtrees this run writes or reads. There is no "
        "in-repository default — this repository keeps no rendered tree",
    )
    common.add_argument(
        "--family",
        metavar="NAME",
        default=DEFAULT_FAMILY,
        help=f"the model family whose tuning applies (default: {DEFAULT_FAMILY}): "
        "a bare family name resolved against templates/family/, or a path to a "
        "family file. Bare MODEL names are not valid values — the family's "
        "required [tiers] table names its members. See templates/family/README.md",
    )
    common.add_argument(
        "--model-tier-map",
        metavar="SPEC",
        help="override the tier -> family member map the family declares: "
        "comma-separated tier=member pairs, or all=member "
        "(--model-tier-map medium=haiku). Named tiers mask only themselves; "
        "the rest keep the family's own [tiers] value. Drives which member's "
        "overlay overrides render, never the rendered pin text",
    )
    common.add_argument(
        "--model-pin-map",
        metavar="SPEC",
        help="override the tier -> rendered pin map: the same syntax, over "
        "this tool's DEFAULT_PIN_MAP (--model-pin-map all=haiku). Pin text is "
        "always in the claude model namespace, and is the sole source of the "
        "five @!dyn.tier-*!@ tokens' text",
    )
    common.add_argument(
        "--harness",
        metavar="NAME",
        default=DEFAULT_HARNESS,
        help=f"the harness whose templates/harness/<NAME>.toml fills @!hrn.<key>!@ markers in the "
        f"rendered definitions (default: {DEFAULT_HARNESS})",
    )
    common.add_argument("--verbose", "-v", action="store_true", help="list every file")

    selection = argparse.ArgumentParser(add_help=False)
    selection.add_argument(
        "--surfaces",
        choices=("agents", "commands", "both"),
        # No default: the selection globs imply their surfaces, so combining
        # the two flags has to be distinguishable from not passing this one.
        help="which surface to render (default: both). Not combinable "
        "with --agent-glob/--command-glob, which imply their surfaces",
    )
    selection.add_argument(
        "--agent-glob",
        metavar="PATTERNS",
        help="restrict the run to the agents outputs matching PATTERNS — one "
        'or more fnmatch patterns joined by "|", matched against the '
        "surface-relative output path without its .md suffix "
        '(--agent-glob "*app-expert*|*-coder*"). Implies --surfaces agents '
        "unless --command-glob is given too; a pattern matching nothing is an "
        "error",
    )
    selection.add_argument(
        "--command-glob",
        metavar="PATTERNS",
        help="the same, over the commands surface",
    )

    parser = argparse.ArgumentParser(
        prog="python3 -m gen_defs",
        description="Generate and install the generated agent/command definitions, and "
        "install the harness agents file into a directory the operator names.",
        allow_abbrev=False,
    )
    parser.add_argument("--version", action="version", version=f"gen_defs {__version__}")
    # The metavar lists the public verbs only, and `dev` is added without
    # help=, which is what keeps it out of the listing: help=SUPPRESS on a
    # subparser still prints a "==SUPPRESS==" row.
    verbs = parser.add_subparsers(dest="verb", required=True, metavar="{generate,install,install-agents-file}")

    verbs.add_parser(
        "generate",
        parents=[common, selection],
        allow_abbrev=False,
        help="render the definitions into ROOT's two surfaces",
        description="Render every declared definition into ROOT's agents/ and commands/ "
        "surfaces, under the tuning triple this invocation names. The surface "
        "directories, and the mirrored subdirectories beneath them, are created "
        "as needed; the per-target write-safety table decides what may be "
        "overwritten.",
    )

    verbs.add_parser(
        "install",
        parents=[common],
        allow_abbrev=False,
        help="full-product install into ROOT (a project's existing .claude directory)",
        description="Install the whole product into ROOT: render both deployed surfaces and "
        "copy the shipped packages, minus test suites and caches, stamping each "
        "copied file with an !INSTALLED! banner. The render runs under whatever "
        "tuning triple the install was given. An installed tree is an artifact: "
        "re-install to update it, and local edits to installed files are "
        "replaced — not preserved, though the prior content of any file this "
        "tool did not write is kept beside it as a numbered *.bak, yours to "
        "delete. Reports by exception: a clean install is one summary line, and "
        "-v lists every file.",
    )

    dev = verbs.add_parser(
        "dev",
        allow_abbrev=False,
        description="Internal, unsupported subcommands serving this repository's own just recipes. "
        "Names and behavior may change without notice.",
    )
    dev.set_defaults(print_dev_help=dev.print_help)
    dev_verbs = dev.add_subparsers(dest="dev_verb", metavar="SUBCOMMAND")
    dev_verbs.add_parser("help", allow_abbrev=False, help="print this help")
    harness_name = dev_verbs.add_parser(
        "agents-file-for-harness",
        allow_abbrev=False,
        help="print the file name harness NAME reads its agents file from",
        description="Print the file name a harness reads its agents file from "
        "(templates/harness/<NAME>.toml, [harness.agents-file]).",
    )
    harness_name.add_argument("name", metavar="NAME", help="the harness name: claude, opencode, ...")
    agents_file = dev_verbs.add_parser(
        "render-agents-file",
        allow_abbrev=False,
        help="render templates/harness/AGENTS.md.tmpl for one harness to the file OUT",
        description="Render the harness agents file for HARNESS (templates/harness/<HARNESS>.toml) "
        "to the file OUT, stamped with this repository's short revision (suffixed **dirty** while "
        "templates/ has uncommitted changes). An OUT that already exists with different content "
        "is refused and nothing is written; identical content is left alone.",
    )
    agents_file.add_argument("harness", metavar="HARNESS", help="the harness name: claude, opencode, ...")
    agents_file.add_argument(
        "out", type=Path, metavar="OUT", help="the file the agents file is written to; its directory must exist"
    )

    agents_file_install = verbs.add_parser(
        "install-agents-file",
        allow_abbrev=False,
        help="install the harness agents file into DIR (a harness's user-global directory, or a project root)",
        description="Render templates/harness/AGENTS.md.tmpl for HARNESS and install it into DIR, replacing "
        "only the block between the adjagent marker lines. In the harness's user-global directory the file is "
        "the harness's own agents-file name; anywhere else it is AGENTS.md, and a harness reading another "
        "name gets that file as the one-line redirect '@AGENTS.md' — created when absent, left alone when "
        "already that, and refused when it holds anything else. Everything "
        "outside the block is yours and is kept; an existing file without markers is kept whole above the "
        "block. A file whose markers are not one ordered pair is refused, as is any install while templates/ "
        "has uncommitted changes, and nothing is written. A write that changes the file keeps its prior "
        "content as backup.<name> beside it; identical output writes nothing. A destination holding only "
        "one '@<path>' import is a redirect: the install goes into that target, one hop and inside DIR "
        "only, and the redirect itself is never written.",
    )
    agents_file_install.add_argument("harness", metavar="HARNESS", help="the harness name: claude, opencode, ...")
    agents_file_install.add_argument(
        "dir",
        type=Path,
        metavar="DIR",
        help="the existing directory to install into: ~/.claude, ~/.config/opencode, or a project root",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.verb == "install-agents-file":
            # No surfaces and no tuning triple; it has no verdict case, so it
            # exits 0 here or 2 through the InputError handler.
            install_agents_file(args.harness, args.dir, probe_templates_revision())
            sys.exit(0)
        if args.verb == "dev":
            if args.dev_verb in (None, "help"):
                args.print_dev_help()
            elif args.dev_verb == "agents-file-for-harness":
                print(agents_file_name(args.name))
            else:
                revision = probe_templates_revision()
                if revision.dirty:
                    print(f"templates/ has uncommitted changes — rendering as revision {revision.value}")
                text = render_agents_file_text(args.harness, args.out.parent, revision)
                write_agents_file_renders([(args.out, text)])
            sys.exit(0)

        # An install delivers the product entire, so it declares neither flag
        # and covers both surfaces unconditionally.
        globs: GlobMap = {}
        surfaces = "both"
        if args.verb != "install":
            globs = {
                surface: split_globs(spec)
                for surface, spec in (("agents", args.agent_glob), ("commands", args.command_glob))
                if spec is not None
            }
            if globs and args.surfaces is not None:
                parser.error(
                    "--agent-glob/--command-glob already select their surface(s) — drop --surfaces, which they subsume"
                )
            # The globs imply the surfaces they cover; without them, --surfaces
            # (or its default) does.
            surfaces = ("both" if len(globs) > 1 else next(iter(globs))) if globs else (args.surfaces or "both")

        smap = surface_map(args.root, surfaces=surfaces)
        if globs:
            validate_selection(output_keys(smap), globs)
        chunks = load_chunks()
        # A family is always loaded — --family defaults rather than being
        # absent — so there is no untuned path left to branch on.
        family_path = resolve_family(args.family)
        family = load_family(family_path)
        tuning = effective_tuning(
            family_path,
            family,
            tier_spec=args.model_tier_map,
            pin_spec=args.model_pin_map,
            harness=args.harness,
        )
        # Anchors are collected across ALL templates and chunks, not just the
        # --surfaces selection, so a filtered render never miscalls a real
        # anchor unknown. The second surface map is built for its template dirs
        # alone, so reusing this run's root keeps it an existing one.
        validate_family_anchors(
            family.entries, collect_anchors(chunks, templates(surface_map(args.root)), namespace=FAMILY_NAMESPACE)
        )
        validate_family_members(family, tuning.tier_map, family_path)
        binding = tier_binding(chunks, pin_map=tuning.pin_map, harness=load_harness(tuning.harness))
        overlays = tier_resolver(family.entries, tuning.tier_map)

        report_tuning(tuning)
        report_divergence(tuning)
        report_tuned(tuning)

        if args.verb == "install":
            ok = install(binding, smap, root=args.root, overlays=overlays, tuning=tuning, verbose=args.verbose)
        else:
            ok = generate(binding, smap, overlays=overlays, tuning=tuning, globs=globs, verbose=args.verbose)
        report_overlays(family.entries, overlays(None), tuning)
        if globs:
            report_selection(output_keys(smap), globs)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)

    sys.exit(0 if ok else 1)
