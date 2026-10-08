"""adjagent 1.0: agent definitions as code.

A definition is a value, a `Definition` returned by a function of one `Render`.
Shared prose is a section, written once in `adjagent.sections` and called by
every definition that renders it, so two definitions cannot disagree about text
they share. Variation is a parameter, and harness, family and tier maps reach a
definition only through its `Render`.

    errors.py        the one error, InputError, reported as exit 2
    definition.py    the vocabulary: tiers, tools, anchors, and the Definition value
    harness.py       the harness dataclass, its frontmatter emitters, claude and opencode
    family.py        the family dataclass and its overlays, claude, qwen3 and gemma-4
    context.py       Render, and the two map flags' grammar
    sections/        shared sections, one module per group
    definitions/     one module per definition; registration is the module existing
    render.py        definition to file text, the banner, and the writer
    cli.py           the argparse surface
    __main__.py      the `-m` entry

Usage, from the repository root with it on PYTHONPATH:

    python3 -m adjagent render --out DIR [--harness NAME] [--family NAME]
        [--model-tier-map SPEC] [--model-pin-tier-alias-map SPEC]

The render is deterministic: the text of every file is a function of the
definition, the harness, the family and the two maps, and of nothing else.
"""
