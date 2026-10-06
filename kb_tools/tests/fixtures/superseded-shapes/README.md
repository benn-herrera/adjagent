# superseded-shapes — a `0.9.0` KB, as a migration's input only

A small synthetic repository whose `kb-root/` is a KB in metadata format `0.9.0` (comment-block
frontmatter, a `.jsonl` index, no stamp), fresh as the `0.9.0` toolchain left it. It holds, one
synthetic instance each, the structural shapes a hand-built KB of that format carries and the other
fixtures do not. Every word of it is invented.

It exists only as a migration's input. `test_superseded_shapes.py` copies it out, refreshes the copy
(which migrates it), and reads the result; nothing reads it in place, and it is never refreshed or
edited into `1.0.0`. It is not kbase's golden pair (`format-1.0.0/`), which pins the conversion byte
for byte; this one pins that a whole KB in these shapes migrates, refreshes and verifies green.

These are inputs to tests only: `INSTALL_EXCLUDED_DIRS` carries `tests`, so nothing under
`kb_tools/tests/` reaches a consuming project.

## What it holds

| Shape | Where |
|---|---|
| A register at the KB root beside per-volume registers; its claims' leaves sit in a directory with no register of its own | `kb-root/claim-quality.md`, `core/`, `alpha/` and `beta/claim-quality.md` |
| Claim titles holding an em dash and a dotted number (`Proposition 2.4 — Bounded Drift`) | `kb-root/claim-quality.md` |
| Register entries: a build-status legend table and `---` separators, a `Leaf references` footer in `./` form, depends-on contexts both quoted (`["…"]`) and bare (`[…]`), a `[= min(a, b)]` trace, a `None — …` strengthen-by item, items naming ids | every `claim-quality.md` |
| Bare claim ids in prose: a register preamble, an index's bold result headings with a link inside, the entry point's domain list | `kb-root/claim-quality.md`, `*/index.md`, `entry-point.md` |
| Tier-2 markers on their own lines above paragraphs, one above a bold-labelled paragraph outside any blockquote, under a title that reads as a block | `core/sub2.4/s2-4-bounded-drift.md` |
| `kind: leaf` with a two-claim `claims:` list; single-claim leaves with no marker | `core/sub2.4/`, `alpha/`, `beta/` |
| `no-claim: true`, unquoted; `no-claim:` an unquoted value holding an em dash; a `depends-on:` key beside `no-claim:` | `core/s1-scope.md`, `core/s3-remarks.md` |
| The up-link above the comment block; an up-link label holding inline maths and parentheses | every document but the entry point; `alpha/a1-monotonicity.md` |
| A nested index in a directory whose name holds a dot | `core/sub2.4/index.md` |
| A volume directory holding an `index.md` and no claim | `gamma/` |
| An empty (zero-byte) `.jsonl` stream; a hand document inside `.index/` | `.index/supported-by.jsonl`, `.index/SCHEMA.md` |
| `AGENTS.md` declaring no invariant, its `CLAUDE.md` redirect, a `README.md`, and a `session/` note naming ids | `kb-root/` |
