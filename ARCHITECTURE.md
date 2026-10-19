# ARCHITECTURE – Adjagent

How the generation system, and the agent, command and skill set it ships, are built to satisfy
SPEC.md. Cites SPEC's requirements rather than restating them.

## Repo Layout

```
kb-tools/               shipped package, delivered only by a kb install — the runner-snippets/ fragments (kb.just, kb.mk) an install writes the consumer's include line for, and nothing importable; installed beside the kbase executable under <harness-dir>/adj-tools/kb-tools/ (KB_TOOLS_PACKAGE, adjagent/install.py)
liaison_tools/          shipped package, delivered by every install — shell/python helpers shared by guest-liaison.md and mad-guest-liaison.md, imported from the repository root as `liaison_tools`; installed beside the definition surfaces under <harness-dir>/adj-tools/liaison_tools/ (SHIPPED_PACKAGES)
.tool-dist-cache/       gitignored — the signed kbase release a recipe downloads, <version>/kbase[.exe], which `install-with-kb` installs (justfile KBASE_VERSION, TOOL_DIST_CACHE)
rendered/               gitignored build product — this repo's own render tree, one slot per render, and the three `reference*` slots `render-diff` compares against (justfile RENDERED); created on demand
adjagent/               the generator package, run as python3 -m adjagent — definitions as Python values rendered into a named output root; the package docstring lists its modules
devtools/               repository-maintenance tooling — project space, never installed; imported from the repository root as `devtools.*`
  render_diff.py        the text comparison of two rendered slots (justfile `render-diff`); reads rendered output only and never imports the generator
  dupe_sweep/           the duplication sweep, run as `python3 -m devtools.dupe_sweep` — enumerates one-idea-two-places candidates over the owned python trees (justfile `sweep-python`)
    __init__.py         package docstring (what the sweep is for, its passes, candidates not verdicts)
    __main__.py         the `-m` entry
    corpus.py           the corpus read from git, never a directory walk; the sweep's error
    clustering.py       units, containment scoring, shingle-blocked clustering, union-find grouping
    normalization.py    text to lower-cased words, `@!…!@` placeholders dropped
    python_corpus.py    what the python pass reads: `CODE_PREFIXES` — liaison_tools, adjagent, devtools — less `CODE_UNSWEPT`, parsed
    shapes.py           one concept, two implementations: function structural shapes
    constants.py        one constant, two definitions: module-level literals and their candidates
    doc_sentences.py    one rule, two homes: docstring and comment sentences
    report.py           headers, candidate lists, the file-pair tally
    passes.py           the `python` pass and its defaults
    cli.py              argparse surface and dispatch
  tests/                the dupe_sweep test suite, including its import-structure test (`just test dupe_sweep`)
tests/                  the root test suite, `adjagent` and the repository-wide checks, run as the `adjagent` surface (`just test adjagent`) — project space, never installed
```

The three deployed surfaces are absent from this listing because they are absent from the repository
(SPEC.md, Deployed Surfaces).

## Install Consumption Model

`just install` wraps `python3 -m adjagent install <project>/<subdir>` (`adjagent/install.py`);
`just install-with-kb` wraps the same verb with `--with-kb` and a `--kbase-dist` naming the release
its recipe caches under the gitignored `.tool-dist-cache/`. It refuses, with nothing written, a ROOT
that is this repository or inside a shipped package's source, and a ROOT outside the project root it
is given; a kb install with no `kbase` executable to write refuses the same way.

The two install types differ by one filter and three emissions. The filter is `NOT_BY_DEFAULT`,
`^(kb-|kbase$)`, applied to the definition's name — its declared name, not a rendered file's stem —
before anything about it is rendered: a base install drops every match whole, so no file of a
dropped definition is written, and the skill's directory is never created by a run that excludes
it. A kb install is named by `--with-kb`, the flag `install-with-kb` passes beside its
`--kbase-dist`, or is sticky: the installed `kbase` executable standing under ROOT — at
`adj-tools/kb-tools/kbase`, `kbase.exe` where that is the installed name, or at the
`agents/kb-tools/` an earlier version installed there — already includes kb, per ROOT rather than
per project, so a later base-typed invocation refreshes that package instead of dropping it. The
test is that file's presence, and presence alone: the mode is never read, the runner snippets and any
include fragment beside it are never inspected, so a `kb-tools/` directory holding no such file — an
empty one, or one whose tracked executable was never pulled — is a base install. Selecting what a kb
install copies from is stricter, and the installed binary must run: a file there that cannot execute
is no source, the legacy `agents/kb-tools/` is consulted, and with nothing runnable there either the
install refuses with `InputError` naming the path and its remedies — `--kbase-dist`, or install kb
first — rather than register a command that cannot start. The underscore `agents/kb_tools/` tree is
not a signal; it never held an executable.

A kb install writes three things beside the renders:

- **The kb-tools package**, assembled from two sources: the `runner-snippets/` fragments copied from
  `kb-tools/`, and the executable the distribution names, which replaces the destination whole. With
  no distribution named, the executable already installed stays where it is and only the snippets are
  refreshed; one an earlier version installed under `agents/kb-tools/` is copied across before that
  tree is removed.
- **The `kbase` server entry**, merged into the harness's own project settings file (`Harness.mcp`):
  claude's `.mcp.json`, or for opencode the first discovered of `.opencode/opencode.json`,
  `opencode.jsonc`, `opencode.json`, else `.opencode/opencode.jsonc` created. The entry's command is
  the absolute path of the installed executable and its KB root is the project root. A settings file
  that is not plain JSON — JSONC comments a rewrite would destroy — is reported with the entry
  printed, and left as it stands.
- **The runner include line**, appended to the project's justfile or Makefile — or to a `Makefile`
  created carrying it, where the project has neither: the non-fatal `import?` or `-include` form
  naming the installed snippets. One line only: a line naming another harness is reported and left
  alone, and one naming this harness under a path an earlier version installed is rewritten in place.

An install renders every included definition — its own output, then each supporting file a skill
lists — replaces `liaison_tools/`'s destination whole (`SHIPPED_PACKAGES`) with a copy, writes the
renders over what is there, and removes each file under `agents/`, `commands/` or `skills/` that
this run did not write, that would ship, and that is ours by its own carrier: a frontmatter block
holding a `!GENERATED!` line, or a comment line opening with it, which is how a skill's supporting
file holds its banner. It then removes each directory that leaves empty, up to its surface. That walk
needs no carve-out for a package destination: both sit beside the surfaces, under `adj-tools/`, so
every file under a surface is either ours or untouched. A kb-set name is inside that would-ship
vocabulary, so under a base install one this run did not write is stale and goes — every one of its
files, a skill's included. Every install also removes each tree an earlier version installed under a
harness directory — `agents/kb_tools/`, `agents/kb-tools/` and `agents/liaison_tools/` — naming each
it removed, and reporting the underscore tree's removal on a run that excludes kb. A render that
fails writes nothing. There is no hash, backup or refusal of a modified file: the consumer tracks the
installed set, and its git is the record of what an install changed.

The package copy skips a vocabulary of names matched at any depth (test directories, caches,
`.DS_Store`, `.bak` files, the project documents) and carries the executable bit. A copied file of a
`#`-comment type (`.py`, `.sh`, `.toml`, `.mk`, `.just`) takes the installed banner; any other file
is copied byte-verbatim. `just install-agents-here` installs this repository's own `.claude/` and
`.opencode/` with the plain `install` verb, once per harness, as base installs. The sticky rule is
per ROOT and reaches these two directories: one already holding the installed `kbase` executable at
`adj-tools/kb-tools/` or in the legacy `agents/kb-tools/` would be a kb install under this recipe
too, and neither does. No include line is
written here whatever the install type — `install_kb_include_line` returns without writing when the
project is this repository.

## Composition Model

A definition is its rendered text with holes. A module under `adjagent/definitions/` reads top to
bottom as the file it renders and defines `DEFINITIONS`, a tuple of `Definition` records
(`adjagent/definition.py`): `name`, `body`, `kind`, `folder`, and for an agent `description`,
`tools`, `tier` and optionally `color`; a skill adds `files`, its supporting files as `SkillFile`
values of a path below the skill's directory and a body. `body` is a string built at import: an
f-string over the module's own triple-quoted text, its own constants, and the constants and text
functions of `adjagent/clauses.py` (imported as `from adjagent import clauses`, written
`{clauses.NAME}`). A module with several definitions has a longer tuple, and one definition may own
several output paths: a skill's own `SKILL.md`, then one per supporting file. A module is registered
by existing in the package (`definitions.discover`); an output path produced by two modules — a
supporting file's included — is refused, naming both, and one definition naming the same
supporting-file path twice is refused. Where a module goes and what it is called are in
CONVENTIONS.md, "Adding Definitions".

SPEC.md's single-sourcing property holds because of how text is shared, in three cases:

- **Identical in two definitions** is one constant: in `clauses.py` when the definitions are in
  different modules, in the module's private constants when they ship as a set.
- **Identical but for a few words** is a slot constant, a string with `{name}` holes filled by
  `.format` where each definition uses it in its body. Across modules the same shape is a function
  in `clauses.py` taking at most three keyword-only parameters, such as `clauses.kb_orientation`.
- **Different in structure** is written out in each definition. A sentence that belongs to one
  definition and sits among shared text is written inline in that paragraph around the constant;
  no field, class or profile carries it.

Definitions that ship as a set live in one group module (`mad_referees.py`, `mad_design_topics.py`,
`mad_debate.py`), and the text only that set shares is the module's private
constants, so a reader of the module needs nothing behind an import. `clauses.py` holds only text
shared across sets. A private constant cannot name `clauses.*`; shared text that holds a harness
string takes a hole filled at the call site, as `_GUEST_CONTRACT` takes `harness_dir` in
`mad_referees.py`.

### Holes

The renderer fills one closed set of holes, spelled by `vocabulary.hole`: `@!hrn-<key>!@` for the
five harness strings (agents file name, project harness directory, project scratch directory, user
harness directory, MCP tool prefix) and `@!fam-<anchor>!@` for the family overlay anchors a
definition exposes (`gap-aversion`, `ask-vs-stipulate`). The agents file alone also carries
`@!agf-<key>!@` for its scope name and its coder-dispatch bullet, a harness callable taking the
rendered default family's medium tier where the harness can choose a model per dispatch, and
`None` where it cannot, which drops the paragraph. No prose in the repository contains `@!`.

`render.filled_body` fills a body in one pass over its paragraphs and does not rescan what it
filled, so a family's overlay text or a harness string cannot introduce a further hole. A
placeholder-shaped span naming no key is refused, naming the definition and the span. An anchor the
family does not fill leaves nothing, and a paragraph that fills to nothing is dropped with its blank
line. The overlay for an anchor is the family's text for the definition's tier-mapped member, else
the family-wide text, else nothing (`family.py` states the rules for authoring one).

### Kinds

`kind` decides where the definition goes, what frontmatter the harness emits for it, and which
fields it takes. `folder` is the path below the output root for nested outputs, as in
`agents/mad/design-topics/`; a skill refuses it, because the directory name is the definition's
name on both harnesses.

| Kind | Output | Frontmatter | Fields |
|---|---|---|---|
| agent | `agents/<folder>/<name>.md` | the harness's agent fields, the model from `tier` through the tier map | `description`, `tools`, `tier` required; `color` optional |
| document | `agents/<folder>/<name>.md` | the harness's document fields: none under claude, `mode: subagent` and `disable: true` under opencode | none of the agent fields |
| command | `commands/<folder>/<name>.md` | no field lines, and no blank line after the closing fence | none of the agent fields |
| skill | `skills/<name>/SKILL.md`, then `skills/<name>/<file.path>` for each `SkillFile` | `name` and `description`, the two fields both harnesses read, between the banner and the closing fence | `description` required; no `tools`, `tier` or `color`; `files` optional |
| agents file | none | none; renders to a block, see Agents File | none of the agent fields |

Every rendered definition's own output opens with a frontmatter block carrying the banner; a skill's
supporting files open with the comment form of it (see Banner). The skill row's two field lines are
the renderer's own (`render._field_lines`), not the harness's: they are deliberately
harness-invariant, because both harnesses read the same two fields and neither has anything of its
own to say about them. A `Definition` refuses at construction any field outside its kind's contract.

### Harnesses and families

A harness is a `Harness` dataclass (`adjagent/harness.py`) holding everything that differs between
harnesses: the five hole strings — `HarnessText.MCP_TOOL_PREFIX` among them, `mcp__kbase__`
under claude and `kbase_` under opencode, a server tool's offered name being that prefix plus the
tool's own — the tool spellings, the model shape it accepts, the text `inherit` renders as
(`inherit_text`) with the further `inherit_synonyms` rendering that same text, whether a bare
`--model-tier-map` value is the whole map (`bare_tier_spec_is_all`), the frontmatter emitter,
`coder_dispatch`, a callable taking the rendered model and returning the agents file's
coder-dispatch bullet, or `None` where the harness cannot choose a model per dispatch, and `mcp`
(`McpSettings`), the project settings file and server entry a kb install registers.
`inherit_synonyms` and `bare_tier_spec_is_all` both differ between the two harnesses, as the
strings above do: opencode holds `("default",)` and `True`, with `inherit_text` empty, so a tier
rendering either word leaves the agent without a model line and so on the project's own model;
claude holds `()` and `False`, `inherit_text` `inherit`, and refuses a bare tier-map value as no
`tier=value` pair. A family is a `Family` dataclass (`adjagent/family.py`) holding the tier map and
the overlays by anchor. An instance is one module, in `adjagent/harnesses/` or
`adjagent/families/`, defining `HARNESS` or `FAMILY`, with no class in it. `loading.load` reads the
modules of a package in name order and keys each by its module name with `_` read as `-`
(`gemma_4.py` is `gemma-4`). The constructor is the validator: an instance missing a field, or a
family not staffing exactly the five tiers, fails at import. The `Render` record
(`adjagent/context.py`) carries the harness, the family and the invocation's two tier maps, and
resolves a tier to its rendered model text and an anchor to its overlay: a tier whose text is
`inherit` or a synonym becomes `inherit_text`, and the tier-map argument, alone, gains the
bare-to-`all=` expansion before parsing.

### Structural rules

Two checks over source and output fix the properties above, and both are tests in the suite
(`just test adjagent`). `render` runs neither: a syntax-tree analysis has no place on a consumer's
machine of unknown Python.

- **Substitution depth is one.** `tests/_structure.py` walks the syntax trees of the definition
  modules and `clauses.py`. A module-level constant is a string literal or an f-string over
  constants in the same module, never a call. The only calls in a definition module are
  `Definition(...)` in `DEFINITIONS`, `SkillFile(...)` as a `files=` element, and, inside a `body=`
  value or a `SkillFile` body, `clauses.<name>(...)` and `<constant>.format(...)` on a
  string-literal constant, every argument a literal or a constant. A
  `clauses.py` function takes at most three keyword-only parameters and returns one string over its
  parameters and constants, with no call. A chain of constants cannot defeat the depth, because
  nothing a call returns can be bound to a constant or passed as an argument: slot text is always
  fixed text, and filling it is the last substitution. Every `SkillFile` body is walked under the
  `body=` rule, so a reference takes shared text from `clauses` as a definition body does and cannot
  carry a call of its own — a `SkillFile` path is a string literal and nothing else. The same walk
  confirms a definition module's top level holds only imports, string constants and `DEFINITIONS`.
- **A paragraph two outputs share has one source.** `tests/test_adjagent.py` renders every
  definition twice, once as written and once with each `clauses` constant, function and private
  constant standing as a sentinel, and fails on a paragraph or list item that survives both in two
  outputs: it was written out rather than taken from a constant. A skill is swept the same way, each
  of its files walked as an output in its own right and labelled by the path it renders to, so a
  paragraph a router and a reference both carry is found as readily as one two definitions share.

### History

Before 1.0 definitions were Markdown templates with a marker grammar, namespaces and a chunk table,
expanded by a separate generator. It was replaced because every author and reviewer had to learn a
grammar a language already supplies as calls, scope and modules, and because the grammar owned the
boundaries between paragraphs and so left artefacts in the text.

## Banner

A rendered definition's own output carries two banner lines in its frontmatter: `# !GENERATED! from
adjagent/definitions/<module>.py`, with the edit rule and where change requests go, and
`# !TUNING!`, which records the family, the definition's seat and member, the tier map, the alias
map where one was given, the tiers the family tunes nothing for (`stock`), and the harness. Those
lines are YAML comments inside the block, so the opening `---` is still the file's first line — the
one thing a harness requires to read a frontmatter at all — and the block's field lines follow the
banner. A skill's supporting file has no frontmatter to hold them, so it carries the same two
payloads as HTML comment lines, `<!-- !GENERATED! … -->` and `<!-- !TUNING! … -->`, from its first
line, a blank line and the body after them; nothing about how the file reads depends on them, and
the same pair is what marks it as ours for removal. A copied package file of a `#`-comment type
carries one `# !INSTALLED! from <source>` line with the same edit rule, below its shebang where it
has one. Nothing carries a hash, and the only backup is the agents file's rolling `backup.<name>`.

## Verification, and Why There Is No Verification Verb

There is no `check` verb, and adding one back is a decision to be argued rather than an omission to
be filled. A render is the only thing that knows what a definition produces, so a verb that
re-rendered a tree and compared would be asking the producer whether it agrees with itself: a
rendering defect reaches both sides and the report reads clean. What such a verb could genuinely
detect — staleness of a build product — a free re-render fixes.

The comparison is `just render-diff`, which reads rendered output only. It replaces each banner
block with one constant line and collapses whitespace inside a paragraph outside fenced code;
headings, list items, table rows, fenced blocks and frontmatter stay exact
(`devtools/render_diff.py` states the rules). `just render <slug>` renders into `rendered/<slug>/`
and refuses a slug starting with `reference`. A slot is a kb install with itself as project root, so
beside the definitions it holds the kb-tools package, the harness's MCP entry and the runner include
line — the whole product, which is what makes a `render-diff` a comparison of the kb half too. Those
three slots (claude, opencode, and the gemma-4 family, which fills the overlay anchors) are the
baseline, written only by `just retake-reference`, so a `render-diff` after a change reports that
change and nothing the baseline already held.

`tests/test_adjagent.py` holds the package's properties: each kind's frontmatter against literal
lines, a skill's directory — its two fields and a comment-bannered reference — against literal
output, every definition under `agents/` extracting frontmatter-free and every participant
extracting to the contract document, placeholder filling and refusal, overlay resolution, the line
cap on a rendered agent, and the structural rules (Composition Model).
`tests/test_adjagent_install.py` holds the install and agents-file cases. Every verb of the
generator exits 0 on success and 2 on a refusal; there is no verdict code.

## Sanctioned Invocation

`just install`, `just install-with-kb`, `just install-agents-here`, `just render`,
`just retake-reference` and `just install-agents-file <dir> [harness]` reach `python3 -m adjagent`:
`install-agents-here` through `install`; `render` and `retake-reference` through the private
`_render-slot`, which calls `install` with `--with-kb` and `--kbase-dist`, and through the stable
private `render-agents-file HARNESS OUT` recipe, which a later revision calls inside a worktree of an
earlier one, so its name and two arguments do not change incompatibly. Recipes read a harness's
values through `python3 -m adjagent harness NAME KEY`, never from a copy of them.

## Agents File

The harness agents file is a definition of the agents-file kind
(`adjagent/definitions/harness_agents_file.py`). Its body is the whole file as a fresh install holds
it: the title carrying the scope-name hole, then the span from the begin marker line to the end
marker line. `render.render_agents_file(harness, scope=...)` fills it under the default family's own
tiers whatever the invocation's tuning, with no model-shape check, so its text is a function of the
harness and the scope alone. The scope is `Global` in the harness's user directory and otherwise the
directory's name.

`adjagent/agents_file.py` implements the install SPEC.md specifies. It finds the span by the
stripped ends of the marker lines, replaces it with the rendered span, and writes every other byte
back as read. Every check, including the git-status refusal over `adjagent/`, runs before the first
write.

## Subsystem Map

Every entry below is rendered from the definition module under `adjagent/definitions/` named for its
output path, or for its set (Composition Model). A shared-text name given here is a constant or
function in `adjagent/clauses.py`, and an overlay anchor is spelled `fam-<key>`.

- **Coder family** — generalist-coder, language coders (c, cpp, go, lua, python, rust, typescript),
  shell-dsl-coder, platform experts (android/ios/linux/macos/web/windows-app-expert,
  linux-kernel-driver-expert), architect, and — sharing the coding-review domain — security-reviewer
  and tech-writer, which is both the author and the review seat for technical documentation.
- **MAD set + `agents/mad/`** — mad-review-referee, mad-design-referee, mad-alignment-assessor, the
  four model-pinned participants (mad-participant-a/b/c/d), and mad-guest-liaison
  sit directly under `agents/` as dispatchable definitions. What the set reads rather than
  dispatches goes into `agents/mad/`, outside the dispatch namespace:
  `agents/mad/participant-contract.md` (the body the four participants share and a guest model
  receives as its system prompt), and the design referee's own methodology topic set, read at
  dispatch, `agents/mad/design-topics/`. A topic renders bannered like any other output, and a
  referee writes the run's own banner-free copy of it into the run directory before dispatching —
  one strip at the point the brief is assembled, so no seat reads generator metadata and a
  banner-format change does not reach the seats' text.
- **kb set + kbase** — the `kbase` skill and the two agents kb-claim-scorer and kb-maintainer: the
  definitions a base install excludes by name and a kb install delivers. `kbase.py` owns a
  directory, `skills/kbase/SKILL.md` routing by request and `skills/kbase/references/reading.md` and
  `skills/kbase/references/build.md` carrying what each route needs; the router is the only text
  every session pays for, and the rule that a reference is read only when its route is reached is
  the router's own — its *Route by the request* section says so, and nothing but that text stops a
  read.
  `clauses.kb_orientation`, carrying the system model (two graphs, the leaf/summary contract,
  authored-vs-derived metadata, the cast) with a per-definition `role=` clause, goes to the two
  seats that work a finished KB — the reading reference and kb-maintainer; the build seat,
  kb-claim-scorer, is told what its own job needs and reaches the rest through its dispatch. The
  skill and both agents are project-portable — per-project facts live in the consuming project's
  `kb-root/AGENTS.md`, under every harness. The toolchain they drive is kbase, the binary a kb
  install writes beside its snippets, and the set's route to it is MCP-only: every operation the
  set names is a tool of the harness's `kbase` MCP server, offered under that harness's
  `mcp_tool_prefix`, and the router says so and stops where that server is not connected —
  registering it, which the install does, is the fix, not a second interface.
  `clauses.KB_RUNNER_TARGETS` is kb-maintainer's: where the project's runner carries the installed
  `kb-` targets, `refresh`, `verify` and `stats` are `kb-refresh`, `kb-verify` and `kb-stats`. The
  consumer's runner targets are this repository's `kb-tools/runner-snippets/` fragments —
  `kb-verify`, `kb-refresh`, `kb-stats`, `kb-`-prefixed so they cannot collide with a consuming
  project's own targets — each running the executable it finds from the fragment's own directory.
- **Liaisons + liaison_tools** — guest-liaison.md (general-purpose) and mad-guest-liaison.md
  (MAD-only) share `liaison_tools/`'s helpers (`post-openai.py`, `msg-util.py`) for the wire
  protocol and the messages-file format; each strips a definition's frontmatter for itself with a
  `sed` range, the operation being one line. `relay-driver.py` — the corpus-relay eval instrument —
  composes those same helpers (`post-openai.py` as sole transport, `msg-util.py` as sole
  messages-file mutator) into a scripted READ/LIST/GREP retrieval-eval loop.
- **Specialists** — applied-mathematician, biz-dev-strategist, economic-historian, literature-scout,
  marketing-comms-expert, ml-engineer, prompt-engineer, prose-architect, theoretical-economist:
  single-purpose, invoked directly rather than as part of a coding or MAD pipeline.
  applied-mathematician carries the `fam-ask-vs-stipulate` overlay anchor; `fam-gap-aversion` sits
  on kb-claim-scorer.
