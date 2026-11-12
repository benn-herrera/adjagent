## Why There Is No Verification Verb

There is no `check` verb. A render is the only thing that knows what a definition produces, so a verb that
re-rendered a tree and compared would be asking the producer whether it agrees with itself: a
rendering defect reaches both sides and the report reads clean. What such a verb could genuinely
detect — staleness of a build product — a free re-render fixes.

The comparison is `just render-diff`, which reads rendered output only. It replaces each banner
block with one constant line and collapses whitespace inside a paragraph outside fenced code;
headings, thematic breaks, list items, table rows, fenced blocks and frontmatter stay exact
(`devtools/render_diff.py` states the rules). `just render <slug>` renders into `rendered/<slug>/`
and refuses a slug starting with `reference`. A slot holds one slot project per plugin
(`rendered/<slug>/devpro/`, `rendered/<slug>/kbase/`), each an install of its plugin with itself as
project root, so beside the definitions the kbase slot project holds the kb-tools package, the harness's
MCP entry and the runner include lines (the docdicer line for either plugin, the kb line for kbase; none in the mage slot, a harness-directory plugin), and each slot project
holds, where the harness ships them, its own harness resources — the whole install product of both
plugins, which is what makes a `render-diff` a comparison of both. A slot holds the claude hook
script only where `perl` passes the probe on that machine, so a `render-diff` against a reference
slot taken elsewhere can show it. Those four reference slots (`reference-claude`,
`reference-mage`, `reference-opencode`, and `reference-gemma`, the gemma-4 family, which fills the
anchors) are the baseline, written only by `just retake-reference`, so a `render-diff` after a
change reports that change and nothing the baseline already held. The plugin manifest (claude and
mage) and every slot's agents-file begin marker carry `__version__`.

`tests/test_devpro.py` holds the package's properties: each kind's frontmatter against literal
lines, a skill's directory — its two fields and a comment-bannered supporting file — against
literal output, every definition under `agents/` extracting frontmatter-free, placeholder filling
and refusal, tuning-text resolution, the line cap on every rendered definition but a supporting file, and the structural rules
(Rendering). `tests/test_devpro_install.py` holds the install and agents-file cases.
`tests/test_opencode_entry.py` runs the opencode plugin entry under `bun` against a stub plugin
context, and `tests/test_plugins.py` holds the plugin membership and per-plugin content cases. The
two guardrails are held to one behaviour by `tests/test_guardrail.py`, which runs every case of
`tests/guardrail_cases.json` through `guardrail.pl` under `perl` and through `guardrail.ts` under
`bun`, but a case whose `harness` field (`claude` or `opencode`) names one implementation runs
under that one alone (`tests/guardrail_ts_runner.ts` loads the opencode guardrail outside
`bun test`, with its package import stubbed), and asserts each implementation's reason equals the
table's. A case may name a
working directory: `guardrail.pl` receives it as the input `cwd` beside `CLAUDE_PROJECT_DIR` set to
the case's root, as Claude Code sends both, and `guardrail.ts` as the shell call's `workdir`. A
missing `bun` fails the test rather than skipping it, because a skip would hide drift between the
two. There is no verdict code: `cli.main` maps every `InputError` and `OSError` to exit 2.

