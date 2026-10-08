# ARCHITECTURE – Adjagent

How the generation system, and the agent/command set it ships, are built to satisfy SPEC.md. Cites
SPEC's requirements rather than restating them.

## Repo Layout

```
kb_tools/               shipped package — portable KB toolchain — stdlib-only python package + kb_cmd/ query package, its contract docs, tests, runner-include fragments; installed to .claude/agents/kb_tools/, and locates its harness directory from its own path (kb_tools/install_location.py) (SHIPPED_PACKAGES, gen_defs/product.py)
liaison_tools/          shipped package — shell/python helpers shared by guest-liaison.md and mad-guest-liaison.md; installed to .claude/agents/liaison_tools/
rendered/               gitignored build product — this repo's own render tree, the conventional target for inspecting or PR-diffing a render (justfile RENDERED); created on demand
templates/              template sources — maintenance-only, not session-visible
  agents/               *.tmpl.md — one per generated agent definition (or family), rendered into an output root's agents/ surface; subdirectories mirror into the surface (mad/participant-contract.tmpl.md -> agents/mad/participant-contract.md)
    mad/design-topics/  design methodology topics, read by mad-design-referee at dispatch
  commands/             *.tmpl.md — command templates, rendered into an output root's commands/ surface
  family/               *.toml — one per model family, named for it (claude.toml, gemma-4.toml); the overlay anchor text a tuned render fills, schema in templates/family/README.md
  harness/              the agents-file template (AGENTS.tmpl.md) plus one <harness>.toml per harness; not a surface, never discovered or installed
  shared-chunks.toml  the single source of shared text (chunks) for both template types
gen_defs/               the generator package, run as `python3 -m gen_defs` — renders templates/ into a named output root's surfaces
    __init__.py         package docstring (overview, routing, usage, determinism); version
    __main__.py         the `-m` entry
    paths.py            repo anchoring, path display
    errors.py           the exit-2 error
    markers.py          marker grammar, the expander, value kinds, residual guard
    chunks.py           chunk table, variants/defaults/`wrap=`, the chunk source
    discovery.py        surfaces, template discovery, a template's declared outputs, selection globs
    model_tuning.py     tiers, family files, overlay resolution, the tuning triple and its reports
    harness.py          harness files: the `hrn.` values, the frontmatter tables, and `[harness.model]`
    frontmatter.py      per-harness agent frontmatter: the entry grammar, the authored grammar, the five entry slots, assembly
    banners.py          both banners: writing, reading, the body hash
    rendering.py        one template to its rendered outputs
    generation.py       the `generate` verb, per-target write safety, backups
    product.py          what the install product holds: shipped-package table, exclusion vocabulary, destinations, copy set, root guard
    installation.py     the `install` verb
    pruning.py          install's stale-output sweep
    agents_file.py      the harness agents file: the templates status probe, its render, the `install-agents-file` verb, and the `dev` subcommands behind the `render-agents-file` recipe
    cli.py              argparse surface and dispatch
devtools/               repository-maintenance tooling — project space, never installed; imported from the repository root as `devtools.*`
  dupe_sweep/           the duplication sweep, run as `python3 -m devtools.dupe_sweep` — enumerates one-idea-two-places candidates over templates/ and kb_tools/ (justfile `sweep-prose` / `sweep-python`, CONVENTIONS.md)
    __init__.py         package docstring (what the sweep is for, its passes, candidates not verdicts)
    __main__.py         the `-m` entry
    corpus.py           the corpus read from git, never a directory walk; the sweep's error
    clustering.py       units, containment scoring, shingle-blocked clustering, union-find grouping
    normalization.py    text to lower-cased words, markers and fenced code dropped; prose texts, articles dropped
    window_index.py     the prose detector: exact-window index, run widening, passage merging, and its recall bound (every shared run of 15+ non-article words)
    prose_corpus.py     what the prose pass reads: chunk bodies, template bodies minus fence and frontmatter
    python_corpus.py    what the python pass reads: kb_tools/ less tests/ and _vendor/, parsed
    shapes.py           one concept, two implementations: function structural shapes
    constants.py        one constant, two definitions: module-level literals and their candidates
    doc_sentences.py    one rule, two homes: docstring and comment sentences
    report.py           headers, candidate lists, the file-pair tally
    passes.py           the `prose` and `python` passes and their per-pass defaults
    cli.py              argparse surface and dispatch
  tests/                the dupe_sweep test suite, including its import-structure test (`just test dupe_sweep`)
tests/                  the root test suite, `gen_defs` and the repository-wide checks, run as the `gen_defs` surface (`just test gen_defs`) — project space, never installed
```

The two deployed surfaces are absent from this listing because they are absent from the repository
(SPEC.md, Deployed Surfaces).

## Install Consumption Model

`just install` (SPEC.md, Deployed Surfaces, states the invocation and its flags) wraps the
generator's `install` verb: `python3 -m gen_defs install <project>/<subdir>`, where the recipe's
`--subdir=` (the one flag it consumes itself) defaults to the `project-harness-dir` of the
`--harness` named (default `claude`), read from `templates/harness/<harness>.toml` by the private
`_harness-value` recipe — the same reader `install-agents-file` uses to infer its harness. Every
flag forwards verbatim; `gen_defs`'s argparse (`gen_defs/cli.py`) owns the flag surface, and each of
its three verbs — `generate`, `install`, `install-agents-file` — declares only the flags it can act
on, so one a verb cannot honour is unrepresentable there rather than refused by hand. A fourth,
`dev`, is internal and unsupported: it serves this repository's own just recipes, is absent from the
main help, and `python3 -m gen_defs dev help` lists its subcommands.

The surface boundary is the repo's load-bearing partition, and the install is what enforces it: what
an install emits — the two rendered surfaces, plus the shipped-package sources (`kb_tools/`,
`liaison_tools/`) copied alongside them — is **session-visible**, and is therefore all a live Claude
Code session in a consuming project can read, while everything else (`templates/`, the contract
docs, the justfile) is **project space** that no install ever emits, visible only when working
inside this repository itself. On the surface side the partition holds by construction: a surface
holds exactly what the template tree declares, so there is no repository directory an unintended
file could be sitting in, and every piece of installed prose sits on that side. On the package side
it is a filesystem walk rooted at the package sources, and SPEC's exclusions (SPEC.md, Deployed
Surfaces) are named explicitly in `INSTALL_EXCLUDED_*` / `INSTALL_EXCLUDED_DOCS` rather than decided
by placement.

Mechanism, in three parts — two that write and one that sweeps:

- **Stamped copy.** Each shipped package's destination directory is removed entire
  (`replace_package_destinations`), and then the package source is copied recursively into it, minus
  the exclusions above. There is no complement computation and no inclusion list, so a new tool file
  ships with no enrollment step. Every destination goes before any file is written rather than each
  one going ahead of its own copy, so no removal can ever take files an earlier copy has just
  written — which a table row whose destination nested inside another's would otherwise do silently.
  Each copied file is stamped on the way in with the `!INSTALLED!` banner (below), save vendored
  third-party source under a shipped package's `_vendor/` directory, which ships unstamped for the
  provenance reason SPEC.md gives (Deployed Surfaces). The copy asks no per-target question:
  removing the destination first makes every copy target a fresh file, so no hash comparison,
  backup, or refusal has anything left to act on (SPEC.md, Write Safety). Re-installing an untouched
  tree is byte-stable.
- **Render.** The definitions are not copied from anywhere; the ordinary generation pass (below)
  runs against the installed tree, under whatever (family, tier-map, alias-map) triple the install
  was given, and *is* how they arrive. Because every target the pass meets is either absent or
  provably untouched output, it leaves no numbered backups behind.
- **Prune** (`prune_stale`). Both halves finish writing, and then the surfaces under ROOT are walked
  for files neither of them wrote. Running last is what makes the write set a fact on disk rather
  than a prediction, and what keeps a render that raised from ever reaching the prune: a failed
  install leaves one stale file too many, never one live definition too few. The three states the
  walk sorts a file into are SPEC.md's (Write Safety). The predicate answering the middle one —
  banner present, hash mismatched — is `body_untouched`, the same one the render path reads, reached
  here through `banner_body` so that "no banner" separates from "banner that does not match" rather
  than collapsing into it as a write's two-state question does. Directories the prune empties are
  removed by climbing parents, deepest first, stopping at the surface root. The shipped packages'
  destinations are stepped around whole, on the path `package_destinations` derives from the
  SHIPPED_PACKAGES row rather than on any pattern.

## Template System

The `gen_defs` modules' docstrings hold the mechanism detail, each for its own concern (Repo Layout
maps them); this section does not restate it and is a map into them.

- **Output routing**: a template's surface tree routes its output — `templates/agents/` renders into
  `agents/`, `templates/commands/` into `commands/`. Discovery recurses within each tree and a
  template's relative subpath is mirrored into its surface
  (`templates/agents/mad/participant-contract.tmpl.md` → `agents/mad/participant-contract.md`), so
  placement is declared by the filesystem alone — there is no metadata key for it. Every other
  mechanism below applies identically to both template types and unchanged at any nesting depth.
  `templates/commands/` may be absent or empty (git does not track an empty directory). Every render
  names its output root explicitly, as the required positional `ROOT` the `generate` and `install`
  verbs each take. The root must already exist; the surface directories under it, and the mirrored
  subdirectories beneath those, are created on demand, and the report states where files landed.

- **Chunks** (`shared-chunks.toml`, `[chunks.*]`): the single source for text shared across two or
  more definitions. A chunk has either a `text` body or a set of named `variants` — never both.
- **Marker syntax**, usable in templates and inside chunk bodies. A marker's **namespace names the
  source its value comes from**, and a marker with no namespace is a chunk; the expander routes on
  the prefix through a per-render routing table, with no precedence rule between the five sources,
  so a chunk and an argument sharing a name are two different markers rather than a collision to
  arbitrate:
  - `@!name!@` — expand chunk `name`
  - `@!name variant="x"!@` — expand a specific variant of a multi-variant chunk
  - `@!name key="value"!@` — bind a value the chunk body reads as `@!arg.key!@` (any key other than
    the reserved `variant`/`wrap`); falls back to `[chunks.name.defaults]` when the marker omits it.
    A value is authored text of the enclosing span, its markers expanding there before it is bound,
    so a chunk body forwards its own argument with `@!inner key="@!arg.key!@"!@`
  - `@!name wrap="70"!@` — greedy-wrap the expansion to 70 columns
  - `@!arg.<key>!@` — inside a chunk body or a multi-output template body: the value its call site
    bound, or the `[chunks.<name>.defaults]` entry. Only a bare (chunk) marker takes arguments;
    every namespaced one is a bare read
  - `@!fam.<key>!@` — model-tuning overlay anchor, filled from a family file's `[family.<key>]`
    tables; the anchor expands to nothing unless the loaded family fills the key, which is the
    family source's own rule. A marker naming an unregistered namespace is a hard error at parse,
    before any file is written
  - `@!dyn.tier-highest!@`, `@!dyn.tier-high!@`, `@!dyn.tier-medium!@`, `@!dyn.tier-low!@`,
    `@!dyn.tier-lowest!@` — the invocation's own parameters, bound at load time to each tier's
    rendered model (`Tuning.models`): the tier map's member, or the alias map's alias where one
    is set, with `inherit` bound to the harness's `inherit-text`. The dynamic table is routed to
    every span, so they reach template bodies, chunk bodies, and overlay text alike (see Model
    tuning and render-to-order, below)
  - `@!hrn.<key>!@` — a value from the loaded harness file (`templates/harness/<name>.toml`,
    `[harness.<key>] text`), bound in the agents-file render for its harness and in a surface render
    for the harness `generate`/`install --harness NAME` loads (default `claude`; an unknown name
    fails listing the harnesses there are). Strict like `dyn.`, never an overlay: a key the file
    does not define is an error. `[harness.agent-frontmatter]` and `[harness.tools]` are structural
    tables rather than values, so `@!hrn.agent-frontmatter!@` and `@!hrn.tools!@` are unknown keys
    like any other (Harness frontmatter, below). Template and chunk bodies spell the project harness
    directory, scratch directory and the user-global agents file through it
    (`hrn.project-harness-dir`, `hrn.project-temp-dir`, `hrn.user-harness-dir`/`hrn.agents-file`),
    never as Claude Code's literals; a project's agents file is the literal `AGENTS.md` under every
    harness (SPEC.md, Harness Agents File). The agents-file render also binds
    `dyn.agents-file-install-dir-arg`, `dyn.agents-file-scope-name`, and the two user-content
    parameters `dyn.existing-user-content-before-rendered-minus-h1` and
    `dyn.existing-user-content-after-rendered` beside the five tier tokens, which it binds to the
    default family's members under every harness; operator-supplied values — the two user-content
    parameters, DIR, the scope name, and every tier token's pin — are verbatim values, spliced in
    as themselves and never rescanned or residual-checked, while `hrn.` values and the remaining
    `dyn.` values are authored text and expand. A surface template spelling any of them is an unknown invocation parameter
    (`gen_defs/agents_file.py`)
  - Bare where a value is bound, prefixed where it is consumed (CONVENTIONS.md): a chunk marker's
    `key="value"` argument, a `[chunks.<name>.defaults]` key, and an `[outputs.<name>]` fence key
    all stay bare; the marker reading one inside a body carries `arg.`
  - Nothing is reserved: `[chunks.overlay]` and `[chunks.tier-low]` are ordinary chunks
  - The identifier class (CONVENTIONS.md) is spelled once as `IDENTIFIER` in `gen_defs/markers.py`
    and built into every regex site, so the sites cannot diverge
- **Model tuning and render-to-order**: a family file (`templates/family/<family>.toml`, authoring
  guide in `templates/family/README.md`) fills overlay anchors — at most one overlay renders per
  anchor, a member-scoped override winning over the family-wide text, and the filled text renders
  verbatim in place with no lead-in or wrapper of its own — which is how SPEC's additive-only
  guarantee is met. Each family file declares a `[tiers]` table naming the member that staffs each
  of the five tiers; the table is required and complete, and a family file that omits it, drops a
  tier, or names one outside the five fails to load rather than falling back — the default *family*
  is a selection, not a fallback value. Tier resolution runs **per output**, against the tier
  declared at that output's own pin site and read back from the rendered frontmatter, so that an
  outputs-table `model` parameter and a literal frontmatter line are the same thing. A pin site that
  resolves no tier — a literal pin, e.g. `model: opus`, standing where a tier token belongs — fails
  the render: `assert_tiered` refuses it, naming the output and its literal pin. Tuning is asked for
  through three flags: `--family NAME` (default `claude`), `--model-tier-map`, which replaces the
  family's tier map, and the optional `--model-pin-tier-alias-map`. Both map flags take
  comma-separated `tier=value` pairs that name every tier, or `all=value` followed by any named
  exceptions; `parse_tier_map` refuses a map leaving a tier unnamed. `effective_tuning` builds the
  `Tuning`, whose `models` property is each tier's rendered text — the alias where the alias map
  is set, else the member — and checks every one against the harness's `[harness.model]` pattern
  before anything is written, naming the flag or family file that supplied a refused value. The
  banner's `!TUNING!` line is where SPEC's recorded provenance (Generation System) lands: `tier=`,
  then `alias=` only where the alias map is set, then the tiers rendering *stock* — a mapped
  member for which the family declares no overrides, a legal state rather than a warning — and
  last the `harness=` the render's `hrn.` markers resolved from (a reader accepts a banner written
  before that field, as claiming no harness). The banner additionally records that definition's
  own `seat=` (the tier its pin site declared) and `member=` (the family member its overlays
  resolved against) — `none`/`none` for an output with no pin site — because a tier map need not
  be injective (the claude family staffs `low` and `lowest` with haiku), so the tier cannot be
  recovered by inverting the rendered model. A run states its effective triple and harness
  (`display_maps`, with `alias[...]` only where set), and reports two non-gating notices: tiers
  whose member the family tunes, and — only where the alias map is set — the tiers whose alias
  differs from their member.
  `--surfaces agents|commands|both` narrows which surfaces a run covers. A tuned set is not a
  special destination: every render names its root, so a default-triple render and a tuned one
  differ only in the triple — which is what makes two slots rendered under two triples comparable to
  each other by `just render-diff` (Verification, below).
- **Definition selection**: `--agent-glob PATTERNS` and `--command-glob PATTERNS` restrict a
  generate run to the outputs whose surface-relative path minus `.md` (`go-coder`,
  `mad/participant-contract`, `kb-start`) matches one of the `|`-joined fnmatch patterns — filtering
  **per output**, so a glob may render one output of a multi-output template and leave its siblings
  untouched and unreported. Either flag implies the surface(s) the run covers, so it cannot be
  combined with `--surfaces` (subsumed) and `install` takes neither (an install delivers the product
  entire); a pattern matching no output is a hard error listing what the surface declares, and the
  run report states the selection per surface (`agents: 12 of 24 outputs selected by --agent-glob`).
- **Multi-output templates**: a template may open with a fenced `+++ ... +++` TOML block declaring
  `[outputs.<definition-name>]` tables, one per rendered definition, each supplying the parameters
  that differ (e.g. `model`, `color`). The body below the fence renders once per declared output,
  with `@!name!@` bound to that output's own key plus its declared parameters.
  `templates/agents/mad-participant.tmpl.md` is the instance: one body, four model-pinned outputs
  (`mad-participant-fable/opus/sonnet/haiku`). A declared output must be a table; the agents-file
  template's `[[outputs._resolve]]` list — entries whose `text` renders to an output path — is a
  fence metakey only the agents-file render reads, and a surface template carrying it is refused.
- **Harness frontmatter** (`gen_defs/frontmatter.py`, whose docstring is the grammar): an agents
  template's frontmatter is the one authored source, in Claude Code's field names, held to a closed
  flat `key: value` grammar. Each harness file's `[harness.agent-frontmatter]` maps every output
  field to an entry — slot text expanded as a chunk's is, `injected` to emit it whatever the
  template authors, or `false` to elide it — and an authored field with no entry fails the render.
  Five `dyn.` slots are bound only while an entry expands: `authored-value`, `output-stem`, `tools`,
  `tools-as-permission` and `undispatchable-marker`. Authored fields emit first, in authored order,
  then injected entries in table order, so Claude's output order follows from the template alone.
  The render attaches inside `_expand_output`'s real pass (`gen_defs/rendering.py`); the
  tier-discovery pass and `assert_tiered` read the authored spelling, so a harness that elides or
  rewrites `model` can cost an output neither its tier nor the literal-pin refusal. Command
  templates keep their frontmatter as written. An authored `name` must render its output's own name
  on every harness, which is what lets opencode, whose filename is the name, elide it. `tools:` is
  authored in our own vocabulary — the key set of `[harness.tools]`, the same in both shipped files
  (`tests/test_harness_frontmatter.py`) — and a name a harness's table lacks fails the render.
  Under opencode it becomes a `permission` block allowing or denying each key the table maps to; the
  keys it does not govern (`external_directory`, `todowrite`, `lsp`, `skill`, `question`,
  `doom_loop`) and MCP tools keep opencode's defaults for an allowlisted agent, where Claude's
  allowlist denies them. That residual is accepted: every allowlisted agent is a
  read-and-report seat, and MCP tool keys are operator-chosen server names this repository cannot
  enumerate. A harness's `[harness.model]` (`gen_defs/harness.py`) declares `pattern`, the shape
  every tier's rendered model must match — claude's a Claude alias or a `claude-` model id,
  opencode's `provider/model` or `inherit` — with `shape`, the same rule in words with an example,
  which is what a refusal prints (the pattern reaches no message); and `inherit-text`, what a tier
  token renders for
  `inherit`; opencode's is empty, so an inherited `model` is elided as any empty entry is. It says
  nothing about which model a tier gets.
- **Single-source discipline**: CONVENTIONS.md, Chunk single-sourcing.

## Banner and Backup Mechanism

Two banners, one marking scheme: a provenance claim plus `# !BODY-SHA256! <hex>`, the sha256 of
everything the file holds after the banner block. `!GENERATED!` means rendered here from the
template it names; `!INSTALLED!` means copied here from this repository. A file carries exactly one
— an installed generated definition keeps its `!GENERATED!` banner, which already forbids in-place
edits and names the real edit path. The hash line is identical in both and read by the same code
(`banner_body` / `body_untouched` in `gen_defs/banners.py`), which is what lets one write-safety
implementation serve generation and install alike.

The `!INSTALLED!` banner goes inside the frontmatter block of a `*.md` that has one (so it never
reaches a prompt body, and a body extraction drops it with the rest of the frontmatter); `#` comment
lines at the top of `.py`/`.sh`/`.toml`/`.mk`/`.just`, below a shebang where there is one, so
`python -m` imports, `-include`/`import?` consumption, and shell sourcing are unaffected. Everything
else is copied verbatim and named as unbannered in the verbose install report. That population is
the shipped `kb_tools` templates today — the `.tmpl.md` prompt templates and document templates —
beside a data file whose type admits no comment; SPEC.md (Deployed Surfaces) states both rules, and
the templates are outside the set under its content rule rather than for want of a comment syntax.
`bannerable` therefore refuses any name ending in `TEMPLATE_SUFFIX` (`.tmpl.md`) before it consults
the final suffix — without that, a banner would ride into every document a build stamps into a
consuming KB and every prompt the driver composes.

A `*.md` with no frontmatter of its own splits by kind, on the same distinction `render_template`
already makes for templates: a **command** is given a minimal frontmatter block holding only the
banner, because Claude Code lists a frontmatter-less slash command by its first *body* line and a
banner in front of that line would become the listed description; a **shipped package's**
frontmatter-less `*.md` — a package `README.md`, the one such name that is not excluded from the
install (SPEC.md, Deployed Surfaces) — takes an HTML comment instead, because frontmatter there
would present a package document as a definition, which it is not. The split keys on filetype and
frontmatter state, not on where the file's source sits.

Every generated definition is stamped with a five-line YAML-comment banner naming its source
template (`# !GENERATED! from templates/agents/<name>.tmpl.md and templates/shared-chunks.toml`, or
`templates/commands/<name>.tmpl.md` for a command) above its hash line. The banner always lives in
frontmatter, never in the prompt body: agent templates must open with a frontmatter block and the
banner is injected at its top; a command template without one gets the minimal block described
above. The banner is stamped last, since it carries the hash of what follows it.

The banner is a definition's only claim to being generated, and drives every branch of SPEC.md's
write-safety table. The backup that table's mismatched-hash row calls for is a copy to
`<name>.md.<NN>.bak` beside the target — a copy, not a rename, so the live file keeps its inode,
owner, and mode regardless of who regenerates it. `NN` is per-target, zero-padded from `00`,
allocated as the highest existing serial plus one, and never reused. Backups are a consumer-tree
phenomenon: a render's targets are freshly created or provably its own output, so the only files
this rule ever produces are in an installed tree whose files something else wrote.

## Verification, and Why There Is No Verification Verb

There is no `check` verb, and adding one back is a decision to be argued rather than an omission to
be filled. A render is the only thing that knows what a template produces, so a verb that
re-rendered a tree and compared would be asking the producer whether it agrees with itself: a
rendering defect reaches both sides and the report reads clean. What such a verb could genuinely
detect — staleness of a build product — a free re-render fixes.

Three instruments cover the ground it stood on, each comparing two things that were produced
separately:

- **`just render-diff`** — `diff -rq` between two slots under `rendered/`, each produced by its own
  `just render` invocation (its flags recorded in the slot as `RENDER-FLAGS.txt`). This is where a
  refactor's blast radius is read, and where a definition no template declares any more shows up as
  an `Only in` line.
- **The install's prune** (`prune_stale`, above) — an installed tree's stale definitions are
  *retired* rather than reported, by the install that owns the tree, under SPEC.md's Write Safety
  rule that a banner plus a matching body hash is what makes a file ours to remove.
- **`tests/test_gen_defs.py`** — the render's own properties, asserted against values the render did
  not compute. `TestDeclaredPinsAgainstRenderedPins` is the pattern: the tier a template declares is
  read out of the template source by the test module's own regex, the pin is read out of the
  rendered frontmatter, and the run's rendered models are the only thing joining them, so a tier
  token bound to the wrong map entry is an inequality naming the template. It runs at four tunings
  because a map collapsed with `all=` is a constant function and would hide a misrouted tier, and
  because a member and an alias are two sources of rendered text. The banner's
  `!TUNING!` line is likewise held to account by rendering the same templates under two triples and
  comparing the two banners, never by re-reading one.

The exit code carries the same three-way contract in both modes — generate and install: `0` clean;
`1` the run completed and the answer is no (a `REFUSED` target); `2` the run could not proceed at
all (an unusable flag or flag combination, or a template, chunk source, or family file that would
not load). `1` is a verdict about the tree; `2` is the absence of one, and a caller that treats them
alike will read a broken invocation as a failing run. `install-agents-file` exits `0` or `2` only,
because it has no verdict.

## Sanctioned Invocation

`just install`, `just render`, and `just install-agents-file <dir> [harness]` (with no harness, the
one whose `user-harness-dir` is `<dir>`; none or several matching fails and asks for it explicitly)
are the sole sanctioned entry points to this mechanism — the template rendering that `generate`,
`install`, and `install-agents-file` perform; the last renders the harness agents file and installs
it by block replacement — into the native file in the harness's user-global directory, elsewhere
into `AGENTS.md` with the native file planned as its `@AGENTS.md` redirect — following a destination
that is a lone `@<path>` redirect one hop to its target (`gen_defs/agents_file.py`). Each reaches
`python3 -m gen_defs` — `install` and `install-agents-file` directly, `render` through `install`
and, for the harness agents file it adds to the slot, through the private
`render-agents-file HARNESS OUT` recipe, whose file name `render` looks up with `dev agents-file-for-harness`.
That recipe is a stable interface rather than a convenience: its name and arguments do not change
incompatibly, so a later revision can invoke it in a worktree of an earlier one, while the
`dev render-agents-file` subcommand behind it may change. `just render-diff` is not one of them: it
never invokes `gen_defs`, only `diff -rq` between two already-rendered trees under `rendered/`, so
it compares this mechanism's output rather than driving it. No other invocation (direct `python3`
calls, ad-hoc scripting against `shared-chunks.toml`, hand-copying a surface into a project) is
sanctioned.

## Subsystem Map

One level under `agents/`. Every entry below is generated (SPEC.md, Generated-Definition Integrity),
from the template its own path mirrors (Output routing, above); the entries name what each reads and
drives.

- **Coder family** — generalist-coder, language coders (c, cpp, go, python, rust), shell-dsl-coder,
  platform experts (android/ios/linux/macos/web/windows-app-expert, linux-kernel-driver-expert),
  architect, and — sharing the coding-review domain — security-reviewer, tech-writer, and
  tech-writer-reviewer.
- **MAD set + `agents/mad/`** — mad-review-referee, mad-design-referee, mad-alignment-assessor, the
  four model-pinned participants (mad-participant-fable/opus/sonnet/haiku), and mad-guest-liaison
  sit directly under `agents/` as dispatchable definitions. What the set reads rather than
  dispatches goes into `agents/mad/`, outside the dispatch namespace:
  `agents/mad/participant-contract.md` (the body the four participants share and a guest model
  receives as its system prompt), and the design referee's own methodology topic set, read at
  dispatch, `agents/mad/design-topics/`. A topic renders bannered like any other output, and a
  referee writes the run's own banner-free copy of it into the run directory before dispatching —
  one strip at the point the brief is assembled, so no seat reads generator metadata and a
  banner-format change reaches one chunk (`mad-topic-transport`).
- **kb set + kb_tools** — kb-claim-scorer, kb-maintainer, kb-docent. The `kb-orientation` chunk
  carrying the system model (two graphs, the leaf/summary contract, authored-vs-derived metadata,
  the cast) with a per-definition `role=` clause goes to the two seats that work a finished KB —
  kb-docent and kb-maintainer; the build seat, kb-claim-scorer, is told what its own job needs and
  reaches the rest through its dispatch. All three are project-portable — per-project facts live in
  the consuming project's `kb-root/AGENTS.md`, under every harness. `kb_tools/` is the toolchain the
  set drives: tools self-anchor by walking up from cwd to `.git` and requiring `kb-root/` beside it,
  read which harness directory they are installed under (and so the scratch directory, PYTHONPATH
  entry and include line they spell) off their own path, detect the consumer's runner for
  remediation hints, and install their runner targets via
  `python3 -m kb_tools.kb_util install-targets` (one non-fatal include line pulling `runner-snippets/kb.mk` or `kb.just`);
  the consumer surface is `kb-verify`/`kb-refresh`/`kb-stats` — `kb-`-prefixed so it cannot collide
  with a consuming project's own targets — and the tool self-tests run under this repo's
  `just test`.
- **Liaisons + liaison_tools** — guest-liaison.md (general-purpose) and mad-guest-liaison.md
  (MAD-only) share `liaison_tools/`'s helpers (`post-openai.py`, `msg-util.py`) for the wire
  protocol and the messages-file format; each strips a definition's frontmatter for itself with a
  `sed` range, the operation being one line. `relay-driver.py` — the corpus-relay eval instrument —
  composes those same helpers (`post-openai.py` as sole transport, `msg-util.py` as sole
  messages-file mutator) into a scripted READ/LIST/GREP retrieval-eval loop.
- **Specialists** — applied-mathematician, biz-dev-strategist, economic-historian, literature-scout,
  marketing-comms-expert, ml-engineer, prompt-engineer, prose-architect, theoretical-economist:
  single-purpose, invoked directly rather than as part of a coding or MAD pipeline.
  applied-mathematician carries the `fam.ask-vs-stipulate` overlay anchor; `fam.gap-aversion` sits
  on kb-claim-scorer.
