"""adjagent 1.0: agent definitions as code.

A definition is a value: a `Definition` whose body is a tuple of `Section`
instances. Shared text is a section class, written once in `adjagent.sections`
and instantiated by every definition that renders it, so two definitions cannot
disagree about text they share. Variation is a field; facts that vary by
language or platform are a `Profile`; harness, family and tier maps reach a
section only through the `Render` its `render` receives.

    errors.py        the one error, InputError, reported as exit 2
    definition.py    the vocabulary: tiers, tools, anchors, and the Definition value
    section.py       the Section base class, and Prose for a definition's own text
    profile.py       Profile: the facts about one language or platform
    harness.py       the harness dataclass, its frontmatter emitters, claude and opencode
    family.py        the family dataclass and its overlays, claude, qwen3 and gemma-4
    context.py       Render, and the two map flags' grammar
    sections/        shared section classes, one module per family
    definitions/     one module per definition, each defining DEFINITIONS
    render.py        definition to file text, the banner, explain, and the writer
    cli.py           the argparse surface
    __main__.py      the `-m` entry

Usage, from the repository root with it on PYTHONPATH:

    python3 -m adjagent render --out DIR [--harness NAME] [--family NAME]
        [--model-tier-map SPEC] [--model-pin-tier-alias-map SPEC]
    python3 -m adjagent explain NAME [the same four flags]

The render is deterministic: the text of every file is a function of the
definition, the harness, the family and the two maps, and of nothing else.
"""
