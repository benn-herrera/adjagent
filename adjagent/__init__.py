"""adjagent 1.0: agent definitions as code.

A definition module is its rendered text with holes: `DEFINITIONS`, a tuple of
`Definition` values whose body is a string built at import from the module's
own triple-quoted text and the shared text of `adjagent.text`, so two
definitions cannot disagree about text they share. The only holes left for
render time are the placeholders `vocabulary.hole` spells for a harness string
or a family overlay anchor, filled once by `render.filled_body`.

    errors.py        the one error, InputError, reported as exit 2
    vocabulary.py    tiers, tools, anchors, kinds, harness texts and the placeholder spelling
    loading.py       the one loader of the instance packages below
    definition.py    the Definition value: kind, output path, frontmatter values, body
    text.py          shared text: constants, and small functions for text with slots
    harness.py       the harness dataclass
    harnesses/       one module per harness, each defining HARNESS
    family.py        the family dataclass and its overlays, and how to author one
    families/        one module per family, each defining FAMILY
    context.py       Render, and the two map flags' grammar
    definitions/     one module per definition, each defining DEFINITIONS
    render.py        definition to file text, the banner, and the writer
    cli.py           the argparse surface
    __main__.py      the `-m` entry

Usage, from the repository root with it on PYTHONPATH:

    python3 -m adjagent render --out DIR [--harness NAME] [--family NAME]
        [--model-tier-map SPEC] [--model-pin-tier-alias-map SPEC]

The render is deterministic: the text of every file is a function of the
definition, the harness, the family and the two maps, and of nothing else.
"""
