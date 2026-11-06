## Why There Is No Verification Verb

There is no `check` verb, and adding one back is a decision to be argued rather than an omission to
be filled. A render is the only thing that knows what a definition produces, so a verb that
re-rendered a tree and compared would be asking the producer whether it agrees with itself: a
rendering defect reaches both sides and the report reads clean. What such a verb could genuinely
detect — staleness of a build product — a free re-render fixes.

The comparison is `just render-diff`, which reads rendered output only. It replaces each banner
block with one constant line and collapses whitespace inside a paragraph outside fenced code;
headings, thematic breaks, list items, table rows, fenced blocks and frontmatter stay exact
(`devtools/render_diff.py` states the rules). `just render <slug>` renders into `rendered/<slug>/`
and refuses a slug starting with `reference`. A slot is a kb install with itself as project root, so
beside the definitions it holds the kb-tools package, the harness's MCP entry, the runner include
line and, where the harness ships them, its own resource files — the whole product, which is what
makes a `render-diff` a comparison of the kb half too. A slot holds the claude hook script only
where `perl` passes the probe on that machine, so a `render-diff` against a reference taken
elsewhere can show it. Those four slots (`reference-claude`, `reference-mage`, `reference-opencode`,
and `reference-gemma`, the gemma-4 family, which fills the overlay anchors) are the baseline, written
only by `just retake-reference`, so a `render-diff` after a change reports that change and nothing the
baseline already held. The claude and mage manifests and every slot's agents-file begin marker carry `__version__`, so after
a bump the claude and mage slots each show the manifest line and the marker line, and the other
slots the marker line alone (CONVENTIONS.md, Version has one home).

`tests/test_adjagent.py` holds the package's properties: each kind's frontmatter against literal
lines, a skill's directory — its two fields and a comment-bannered reference — against literal
output, every definition under `agents/` extracting frontmatter-free, placeholder filling and
refusal, overlay resolution, the line cap on a rendered agent, and the structural rules
(Composition Model).
`tests/test_adjagent_install.py` holds the install and agents-file cases. The two guardrails are
held to one behaviour by `tests/test_guardrail.py`, which runs every case of
`tests/guardrail_cases.json` through `guardrail.pl` under `perl` and through `guardrail.ts` under
`bun`, but a case whose `harness` field (`claude` or `opencode`) names one implementation runs under
that one alone (`tests/guardrail_ts_runner.ts` loads the plugin outside `bun test`, with its package
import stubbed), and asserts each implementation's reason equals the table's. A case may name a
working directory: `guardrail.pl` receives it as the input `cwd` beside `CLAUDE_PROJECT_DIR` set to
the case's root, as Claude Code sends both, and `guardrail.ts` as the shell call's `workdir`. A
missing `bun` fails the test rather than skipping it, because a skip would hide drift between the
two. Every verb of the generator exits 0 on success and 2 on a refusal; there is no verdict code.

