"""adjagent: agent definitions as code.

A definition module is its rendered text with holes: `DEFINITIONS`, a tuple of
`Definition` values whose body is a string built at import from the module's
own triple-quoted text and the shared text of `adjagent.clauses`, so two
definitions cannot disagree about text they share. The only holes left for
render time are the placeholders `vocabulary.hole` spells for a harness string
or a family overlay anchor, filled once by `render.filled_body`.

    errors.py        the one error, InputError, reported as exit 2
    vocabulary.py    tiers, tools, anchors, kinds, harness texts and the placeholder spelling
    loading.py       the one loader of the instance packages below
    definition.py    the Definition and SkillFile values: kind, output paths, frontmatter values, text
    clauses.py       shared text: constants, and small functions for text with slots
    harness.py       the harness dataclass, its `{plugin}` templates and their binding
    harnesses/       one module per harness, each defining HARNESS
    plugin.py        the plugin dataclass: a name and the definitions it ships
    plugins/         one module per plugin, each defining PLUGIN
    family.py        the family dataclass and its overlays, and how to author one
    families/        one module per family, each defining FAMILY
    context.py       Render, and the two map flags' grammar
    definitions/     one module per definition, each defining DEFINITIONS
    render.py        definition to file text, the banner, the writer, and the agents file's text
    install_target.py where an install lands: its harness, harness directory and project root, from the target
    preflight.py     the install run into a scratch copy first: up to date, --dry-run, or the real run
    install_base.py  what the install modules share: package and checkout roots, the kb-tools package
                     paths, path checks, UTF-8 reading
    runner_file.py   the runner include lines, one per snippet set the install passes in
    install.py       the install: renders, the shipped packages' stamped copy, and the prune
    agents_file.py   the agents-file install: the marker span, redirects, and the rolling backup
    cli.py           the argparse surface
    __main__.py      the `-m` entry

Usage, where `python3 -m adjagent` is the same command as `adjagent`; a checkout
runs it from the repository root with that root on PYTHONPATH:

    adjagent render PLUGIN --out DIR [--harness NAME] [--family NAME]
        [--model-tier-map SPEC] [--model-pin-tier-alias-map SPEC]
    adjagent install PLUGIN TARGET [--subdir DIR] [--verbose]
        [--dry-run] [the same tuning flags]
    adjagent install-agents-file PLUGIN DIR [--harness NAME] [--dry-run]
    adjagent render-agents-file PLUGIN HARNESS OUT
    adjagent --version

PLUGIN is the name of a module in `plugins/`, and has no default. The render is deterministic:
the text of every file is a function of the definition, the plugin, the harness,
the family and the two maps, and of nothing else.
"""

__version__ = "0.16.1"
