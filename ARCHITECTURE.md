# ARCHITECTURE – Adjagent

How the generation system, and the agent, command and skill set it ships, are built to satisfy
SPEC.md. Cites SPEC's requirements rather than restating them.

## Repo Layout

```
kb-tools/               shipped package, delivered only by a kb install — the runner-snippets/ fragments (kb.just, kb.mk) an install writes the consumer's include line for, and nothing importable; installed beside the kbase executable under <harness-dir>/skills/kbase/kb-tools/, inside the kbase skill's own directory (KB_TOOLS_PACKAGE, adjagent/install.py)
.tool-dist-cache/       gitignored — the signed kbase release a recipe downloads, <version>/kbase[.exe], which `install-with-kb` installs (justfile KBASE_VERSION, TOOL_DIST_CACHE)
rendered/               gitignored build product — this repo's own render tree, one slot per render, and the three `reference*` slots `render-diff` compares against (justfile RENDERED); created on demand
adjagent/               the generator package, run as python3 -m adjagent — definitions as Python values rendered into a named output root; the package docstring lists its modules
  harnesses/resources/  one directory per harness, named for it — the files that harness ships into its project harness directory, copied into ROOT as they stand and never rendered (HARNESS_RESOURCES_SOURCE, adjagent/install.py); `opencode/plugins/guardrail.ts` and `claude/hooks/guardrail.pl` today, and no `__init__.py`, so `load` still reads one harness per module; mage ships none
devtools/               repository-maintenance tooling — project space, never installed; imported from the repository root as `devtools.*`
  render_diff.py        the text comparison of two rendered slots (justfile `render-diff`); reads rendered output only and never imports the generator
  dupe_sweep/           the duplication sweep, run as `python3 -m devtools.dupe_sweep` — enumerates one-idea-two-places candidates over the owned python trees (justfile `sweep-python`)
    __init__.py         package docstring (what the sweep is for, its passes, candidates not verdicts)
    __main__.py         the `-m` entry
    corpus.py           the corpus read from git, never a directory walk; the sweep's error
    clustering.py       units, containment scoring, shingle-blocked clustering, union-find grouping
    normalization.py    text to lower-cased words, `@!…!@` placeholders dropped
    python_corpus.py    what the python pass reads: `CODE_PREFIXES` — adjagent, devtools — less `CODE_UNSWEPT`, parsed
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
that is this repository or inside a source it copies from — a shipped package's, the kb toolchain's,
or a harness's resource tree — and a ROOT outside the project root it is given; a kb install with no
`kbase` executable to write refuses the same way. So does a render or harness-resource target
holding a file without this repository's banner, or with a symlink or non-directory on its path
below ROOT; a harness settings file that is not UTF-8 or holds the wrong type, `null` included,
where the entry goes — the MCP settings file on a kb install, and the guardrail's
`.claude/settings.json` on a claude install whose probe passes; and, on that install, a harness
directory the guardrail entry cannot name. Every such check runs before the first write. The target
refusal names every failing path at once; a settings or entry refusal names the one it met. A
settings path that is a symlink or not a regular file is no refusal: the merge reports it and leaves
it (below).

The two install types differ by one filter and three emissions. The filter is `NOT_BY_DEFAULT`,
`^(kb-|kbase$)`, applied to the definition's name — its declared name, not a rendered file's stem —
before anything about it is rendered: a base install drops every match whole, so no file of a
dropped definition is written, and the skill's directory is never created by a run that excludes
it. A harness whose `user_harness_dir` is `.` is always a kb install, so the filter never applies
to it. A kb install is named by `--with-kb`, the flag `install-with-kb` passes beside its
`--kbase-dist`, or is sticky: the installed `kbase` executable standing under ROOT — at
`skills/kbase/kb-tools/kbase`, `kbase.exe` where that is the installed name, or at the
`agents/kb-tools/` an earlier version installed there — already includes kb, per ROOT rather than
per project, so a later base-typed invocation refreshes that package instead of dropping it. The
test is that file's presence, and presence alone: the mode is never read, the runner snippets and any
include fragment beside it are never inspected, so a destination holding no file of that name — an
empty `kb-tools/` directory, or one whose executable was never placed — is a base install. Presence
alone cuts the other way too: a `kbase` sitting there that cannot run — empty, or not executable —
still selects the kb set, and the source check below is what refuses the install. Selecting what a
kb install copies from is stricter, and the installed binary must run: a file there that cannot
execute is no source, the legacy `agents/kb-tools/` is consulted, and with nothing runnable there
either the install refuses with `InputError` naming the path and its remedies — `--kbase-dist`, or
install kb first — rather than register a command that cannot start. The underscore
`agents/kb_tools/` tree is not a signal; it never held an executable.

A kb install writes three things beyond the renders — two under a harness whose
`user_harness_dir` is `.`, with no runner include line and no `Makefile`:

- **The kb-tools package**, assembled from two sources: the `runner-snippets/` fragments copied from
  `kb-tools/`, and the executable the distribution names, which replaces the destination whole. The
  destination is `KB_TOOLS_PACKAGE` — `skills/kbase/kb-tools/`, its own directory inside the `kbase`
  skill's, within the `skills/` surface — so a replacement covers that directory and never the
  skill's `SKILL.md` or references beside it. With no distribution named, the executable already
  installed stays where it is and only the snippets are refreshed; one an earlier version installed
  under `agents/kb-tools/` is copied across before that tree is removed.
- **The `kbase` server entry**, merged into the harness's own settings file (`Harness.mcp`): claude's
  `.mcp.json`, at the plugin root under mage — `McpSettings.site` names the directory, `HARNESS`
  there and `PROJECT` for the other two — or for opencode the first discovered of
  `.opencode/opencode.json`, `opencode.jsonc`, `opencode.json`, else `.opencode/opencode.jsonc`
  created. Under every harness the entry's command is the installed executable's path relative to
  the directory that harness's settings file is resolved against — the project root, or, under mage,
  ROOT — so the settings file names no machine-specific path and a project can track it. Its argument
  list is `mcp` alone and names no KB path: the server locates the KB from the working directory it
  is started in, so it has to be started in the project root. An existing settings file is edited in
  place: the entry's own slot is spliced into the text as it stands, so every other byte — other
  entries, key order, indentation, line endings — is kept, while a file this install creates is
  written whole.
  One that is not plain JSON — JSONC comments a splice would destroy — or that the splice cannot
  place with certainty, or whose path `_settings_obstacle` names, is reported with the entry
  printed, and left as it stands.
- **The runner include line**, appended to the project's justfile or Makefile — or to a `Makefile`
  created carrying it, where the project has neither: the non-fatal `import?` or `-include` form
  naming the installed snippets. Written only for a harness whose user directory is not `.`:
  a plugin is not a repo project, so mage gets no line and no `Makefile`. One line only: a line
  naming another harness is reported and left alone, and one naming this harness under a path an
  earlier version installed is rewritten in place.

An install renders every included definition — its own output, then each supporting file a skill
lists — and every file the harness itself renders (mage's manifest), bar a definition the harness
declares it renders nothing for (`Harness.omits`), replaces each destination the `SHIPPED_PACKAGES`
table names whole with a copy, copies each file the installing harness ships into ROOT as it stands
— bar a guardrail script whose probe fails (below) — writes the renders over what is there, and
removes each file under `agents/`, `commands/` or `skills/` that this run did not write, that would
ship, and that is ours by its own carrier: a frontmatter block holding a `!GENERATED!` line, or a
comment line opening with it, which is how a skill's supporting file holds its banner. It then
removes each directory that leaves empty, up to its surface. That walk needs no carve-out for a
package destination: the table's destinations sit beside the surfaces, under `adj-tools/`, and the
kb toolchain's sits inside one — `skills/kbase/kb-tools/`, in the
`kbase` skill's own directory — where every file it holds is stamped installed or left unstamped,
never generated, so every file under a surface is still either ours or untouched. A kb-set name is
inside that would-ship vocabulary, so under a base install one this run did not write is stale and
goes — every one of its files, a skill's included. Every install also removes each tree an earlier
version installed under a harness directory — `agents/kb_tools/`, `agents/kb-tools/` and
`agents/liaison_tools/` — naming each it removed, and reporting the underscore tree's removal on a
run that excludes kb. A render that fails writes nothing. There is no hash or backup of a modified
file: a local edit that keeps the banner lives only until the next install, which rewrites the file
it touched or prunes it, while a file at a render target that has lost the banner, or is a directory
or symlink, refuses the install; where the consuming project tracks the installed set, its git is
the record of what an install changed.

The package copy skips a vocabulary of names matched at any depth (test directories, caches,
`.DS_Store`, `.bak` files, the project documents) and carries the executable bit. A copied file of a
`#`-comment type (`.py`, `.sh`, `.toml`, `.mk`, `.just`) takes the installed banner; any other file
is copied byte-verbatim.

The harness resource copy borrows that vocabulary and nothing else from the package path:
`harness_resource_copies` reads `resources/<harness>/` and writes each file into ROOT with
`copyfile` and `copymode`, so it lands as the harness ships it — no suffix is stamped, whatever the
file's type, and a header a file already holds travels with it as the file's own text. A guardrail
script is the exception to copying every file: it joins the copies only when the probe below
passes. Before the first write, a target that exists must be a regular file, not a symlink, with a
line matching `!INSTALLED! .* adjagent` among its first ten; one unreadable or without it refuses
the install. No component between ROOT and any render or resource target may be a symlink or a
non-directory (`_blocked_component`); one that is refuses the install in the same refusal, and
components at or above ROOT are not examined. Package destinations and the `kbase` executable are
exempt from both checks: this repository owns those entire and replaces them whole. The resource
files join the same `copies` list as the packages', so the prune's `keep` holds them and the report
counts them: a harness file never reads as a stale render, and the report line says `copied files`
for the lot. The copy is one-way, not a mirror — `prune` owns the three rendered surfaces and nothing
outside them — so a resource this repository stops shipping stays in a consumer until that project
removes it. A harness-rendered file is a third target class beside those two: recognised by the
marker it states about itself, and refused where a file at its path does not hold it.

A harness that declares a `guardrail` (`Harness.guardrail`, a `GuardrailHook`) ships a hook the
install registers rather than only copies; claude declares one, opencode sets `None` because its
plugin registers itself, and mage sets `None` and ships no hook at all. The `GuardrailHook` names the
`script` under `resources/<harness>/`, the `settings` file relative to the project root —
`.claude/settings.json` whatever `--subdir` is, the only path Claude Code reads — the `container`
path in it to the array the entry is an element of
(`hooks`, `PreToolUse`), an `entry` builder from the harness's path relative to the project to the
hook entry, and a `claim` that reads an element of that array as `entry` writes it. The entry's
command is a short `sh` program that `exec`s `perl` on
`$CLAUDE_PROJECT_DIR/<harness-relpath>/hooks/guardrail.pl` only when that is a readable file, and
otherwise writes `guardrail hook: no readable script at <path>` to stderr and exits 1. The guard exists because perl exits 2 for a script it
cannot open, which Claude Code reads as a block: a project that commits `settings.json` but not
`hooks/`, or loses the directory, would have every Bash call blocked. The interpreter is `perl` on
`PATH`, never an absolute path, because the settings file is often committed and read on other
machines. The builder refuses a harness path holding `"`, `$`, a backtick or `\`, which the
double-quoted word the path sits in would read as shell syntax.

The script is Perl with core `JSON::PP` and nothing else at session time, a port of
`guardrail.ts`'s `mutation` and its helpers. It reads Claude Code's `PreToolUse` JSON on stdin,
resolves relative targets lexically against the input's `cwd`, else the project root
(`$CLAUDE_PROJECT_DIR`, else `cwd`), and treats `.claude-temp` and `test-data/transient` under that
root as scratch; `guardrail.ts` resolves against the shell call's `workdir`, else the project
directory. The redirect scan does not read heredoc bodies, which are not shell; a redirect on the
heredoc's own command line is still seen, and the inline-script write check still reads the body.
Exit 2 is the block path alone: a failed `use` or `die` in Perl can itself exit 2, which would block
every Bash call, so every module beyond `strict` and `warnings` is loaded with `require` and the
whole body runs in an `eval` that writes to stderr and exits 1, which Claude Code reports as a hook
error without blocking.

- **Probe.** Before `_refuse_foreign_targets`, the install runs the source script once, with
  `GUARDRAIL_INTERPRETER` and no `CLAUDE_PROJECT_DIR`, on one allowed Bash call, and requires exit
  0 within `GUARDRAIL_PROBE_SECONDS`. A missing interpreter, a missing module, a broken script and
  a hang all fail it. A failed probe never refuses the install. It drops the script from the files
  copied, skips the settings merge and its pre-write check, and reports one line naming the exit
  status and first stderr line, the timeout, or the `OSError`. A script and entry an earlier
  install wrote stay, and the line names them — the script when it carries the installed header,
  the settings file when it holds an element `claim` accepts — since the copy is one-way and prune
  never removes an `!INSTALLED!` file. The probe is one allowed call, not the case table, which
  runs in the test suite only.
- **Settings merge**, which `guardrail_merge` runs as `mcp_merge` runs the MCP entry's, both behind
  one pre-write read, `_check_settings`, and one path report, `_settings_obstacle`. The read
  refuses a non-UTF-8 file, and, in plain JSON, a key on the container path of the wrong type,
  `null` included: for the guardrail a `hooks` that is not an object or a `PreToolUse` that is not
  an array. `_settings_obstacle` names a symlink at the settings path or below the project on the
  way to it, dangling or not, which is never written through; a non-directory on that way; and
  anything but a regular file at the path. The read passes such a path and the merge reports it with
  the entry printed and leaves it, so neither merge raises after the first write. An absent file is
  written whole with the one entry. A present file is spliced as the MCP entry's is, every other
  byte kept, with an array scanner beside `_object` and an element insert beside `_with_member`; an
  absent `hooks` or `PreToolUse` is created as `_splice` creates a missing container.
  `install.py` holds the splice and the one, ambiguous or append decision, and no Claude settings
  layout or command shape: the container, the entry and the recogniser come from the
  `GuardrailHook`. Ours is a `PreToolUse` element `claim` accepts, a `hooks` array holding a command
  that equals, in full, what the entry builder writes for some harness directory; no substring
  counts, so a project's own hook running another `guardrail.pl` is not ours, and a command in an
  earlier shape is not either. Exactly one such element holding only our command is replaced whole;
  none is appended. More than one, or one holding our command beside others, is reported for a hand
  merge and the file left untouched, because replacing it whole would delete the project's own
  hook. Ours is recognised for any harness directory, so two installs under different `--subdir`
  values share one settings file and the later replaces the earlier's entry: a project has one
  guardrail.
  A JSONC file, or one the splice cannot place with certainty, is reported with the entry printed
  and left as it stands. Other `PreToolUse` entries are never touched.

The merge runs on every claude install whose probe passes, kb or not, and on
`install-agents-here`'s: the settings file is the project's own, so it passes through no banner
check and has no `REPO_ROOT` exemption, unlike the include line below, which is not written when
the project is this repository.

`just install-agents-here` installs this repository's own `.claude/` and `.opencode/` with the plain
`install` verb, once per harness, as base installs. The sticky rule is per ROOT and reaches these
two directories: one already holding the installed `kbase` executable at `skills/kbase/kb-tools/` or
in the legacy `agents/kb-tools/` would be a kb install under this recipe too, and neither does. No
include line is written here whatever the install type — `install_kb_include_line` returns without
writing when the project is this repository. Nor is one written for a harness whose
`project_harness_dir` is `.`: the install skips that call there, because a plugin is not a repo
project, so a mage kb install writes no include line and creates no `Makefile`.

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

Definitions that ship as a set live in one group module, and the text only that set shares is the
module's private constants, so a reader of the module needs nothing behind an import; no group
module is defined today. `clauses.py` holds only text shared across sets. A private constant cannot
name `clauses.*`; shared text that holds a harness string takes a hole filled at the call site.

### Holes

The renderer fills one closed set of holes, spelled by `vocabulary.hole`: `@!hrn-<key>!@` for the
six harness strings, in two classes — the five `HarnessText` members, which every harness supplies
(agents file name, project harness directory, project scratch directory, user harness directory,
MCP tool prefix), and `OptionalHarnessText`'s one member `recipe_rule`, which a harness supplies as
text or as the empty string, an empty one dropping the paragraph it stands in — and
`@!fam-<anchor>!@` for the family overlay anchors a definition exposes (`gap-aversion`,
`ask-vs-stipulate`). The agents file alone also carries `@!agf-<key>!@` for its scope name and its
coder-dispatch bullet, a harness callable taking the rendered default family's medium tier where the
harness can choose a model per dispatch, and `None` where it cannot, which drops the paragraph. No
prose in the repository contains `@!`.

`render.filled_text` fills a body in one pass over its paragraphs and does not rescan what it
filled, so a family's overlay text or a harness string cannot introduce a further hole;
`render.filled_body` runs that fill over a definition's own body. A placeholder-shaped span naming
no key is refused, naming the definition and the span. Each of three fills may leave nothing: an
anchor the family does not fill, an optional harness text the harness supplies as the empty string,
and the agents file's coder-dispatch bullet where the harness cannot choose a model per dispatch
(`coder_dispatch` is `None`). `filled_text` drops a paragraph that fills to nothing, with its blank
line. `Render.overlay` gives an anchor's text: the family's text for the definition's tier-mapped
member, else the family-wide text, else nothing (`family.py` states the rules for authoring one).

### Kinds

`kind` decides where the definition goes, what frontmatter the harness emits for it, and which
fields it takes. `folder` is the path below the output root for a nested output, empty where the
definition's own output sits directly under its surface; a skill refuses it, because the directory
name is the definition's name on every harness.

| Kind | Output | Frontmatter | Fields |
|---|---|---|---|
| agent | `agents/<folder>/<name>.md` | the harness's agent fields, the model from `tier` through the tier map | `description`, `tools`, `tier` required; `color` optional |
| document | `agents/<folder>/<name>.md` | the harness's document fields: none under claude, `mode: subagent` and `disable: true` under opencode | none of the agent fields |
| command | `commands/<folder>/<name>.md` | no field lines, and no blank line after the closing fence | none of the agent fields |
| skill | `skills/<name>/SKILL.md`, then `skills/<name>/<file.path>` for each `SkillFile` | `name` and `description`, the two fields every harness reads, between the banner and the closing fence | `description` required; no `tools`, `tier` or `color`; `files` optional |
| agents file | none | none; renders to a block, see Agents File | none of the agent fields |

Every rendered definition's own output opens with a frontmatter block carrying the banner; a skill's
supporting files open with the comment form of it (see Banner). The skill row's two field lines are
the renderer's own (`render._field_lines`), not the harness's: they are deliberately
harness-invariant, because every harness reads the same two fields and none has anything of its
own to say about them. A `Definition` refuses at construction any field outside its kind's contract.

### Harnesses and families

A harness is a `Harness` dataclass (`adjagent/harness.py`) holding everything that differs between
harnesses: the six hole strings — `HarnessText.MCP_TOOL_PREFIX` among them, `mcp__kbase__`
under claude, `mcp_kbase_` under mage and `kbase_` under opencode, a server tool's offered name
being that prefix plus the tool's own, and the sixth, `recipe_rule`, typed `OptionalHarnessText`
where the other five are `HarnessText` — the tool spellings, the model shape it accepts, the text
`inherit` renders as (`inherit_text`) with the further `inherit_synonyms` rendering that same text, whether a bare
`--model-tier-map` value is the whole map (`bare_tier_spec_is_all`), the frontmatter emitter,
`coder_dispatch`, a callable taking the rendered model and returning the agents file's
coder-dispatch bullet, or `None` where the harness cannot choose a model per dispatch, `mcp`
(`McpSettings`), the settings file and server entry a kb install registers, its `site` (`McpSite`)
naming the directory that file sits in — the project root, or, under mage, ROOT — `guardrail`
(`GuardrailHook` or `None`), the hook script and settings entry a claude install registers (Install
Consumption Model), `rendered_files` (`HarnessFile`), the files it renders of its own beside the
definitions — mage's manifest — and `omits`, the definition names it renders nothing for.
`inherit_synonyms` and `bare_tier_spec_is_all` differ between claude and opencode, as the strings
above do, and mage holds claude's assumed values (model pattern, aliases, tool spellings,
frontmatter) as copies it may revise independently: opencode holds `("default",)` and `True`, with
`inherit_text` empty, so a tier rendering either word leaves the agent without a model line and so
on the project's own model; claude holds `()` and `False`, `inherit_text` `inherit`, and refuses a
bare tier-map value as no `tier=value` pair. A family is a `Family` dataclass (`adjagent/family.py`)
holding the tier map and the overlays by anchor. An instance is one module, in `adjagent/harnesses/` or
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
beside the definitions it holds the kb-tools package, the harness's MCP entry, the runner include
line and, where the harness ships them, its own resource files — the whole product, which is what
makes a `render-diff` a comparison of the kb half too. A slot holds the claude hook script only
where `perl` passes the probe on that machine, so a `render-diff` against a reference taken
elsewhere can show it. Those three slots (claude, opencode, and the
gemma-4 family, which fills the overlay anchors) are the baseline, written only by
`just retake-reference`, so a `render-diff` after a change reports that change and nothing the
baseline already held. No mage slot is taken: the manifest carries `VERSION`, so a mage baseline
would churn on every bump (CONVENTIONS.md, the version bullet). A mage render is inspected ad hoc
with `just render mage --harness=mage`.

`tests/test_adjagent.py` holds the package's properties: each kind's frontmatter against literal
lines, a skill's directory — its two fields and a comment-bannered reference — against literal
output, every definition under `agents/` extracting frontmatter-free, placeholder filling and
refusal, overlay resolution, the line cap on a rendered agent, and the structural rules
(Composition Model).
`tests/test_adjagent_install.py` holds the install and agents-file cases. The two guardrails are
held to one behaviour by `tests/test_guardrail.py`, which runs every case of
`tests/guardrail_cases.json` through `guardrail.pl` under `perl` and through `guardrail.ts` under
`bun` (`tests/guardrail_ts_runner.ts` loads the plugin outside `bun test`, with its package
import stubbed), and asserts each implementation's reason equals the table's. A case may name a
working directory: `guardrail.pl` receives it as the input `cwd` beside `CLAUDE_PROJECT_DIR` set to
the case's root, as Claude Code sends both, and `guardrail.ts` as the shell call's `workdir`. A
missing `bun` fails the test rather than skipping it, because a skip would hide drift between the
two. Every verb of the generator exits 0 on success and 2 on a refusal; there is no verdict code.

## Sanctioned Invocation

A recipe body is a script in `devtools/scripts/`, named for its recipe, and the recipe is the line
that runs it, handing it the variables it reads as an env prefix. `just install`,
`just install-with-kb`, `just install-agents-here`, `just render`, `just retake-reference`,
`just install-agents-file <dir> [harness]` and `just tag` reach `python3 -m adjagent`:
`install-agents-here` through `install.sh`; `render` and `retake-reference` through the private
`_render-slot.sh`, which calls `install.sh` with `--with-kb` and `--kbase-dist`, and through the
stable private `render-agents-file HARNESS OUT` script, which a later revision calls inside a
worktree of an earlier one, so its name and two arguments do not change incompatibly; and `tag`
through `version`, which prints the version bare and nothing else, so the `v` of `v<version>` is the
recipe's. Scripts read a harness's five `HarnessText` values through
`python3 -m adjagent harness NAME KEY`, never from a copy of them — `_harness-value.sh` is the one
reader — and the version through `python3 -m adjagent version`, never restated in a recipe or a
script. `just tag` reads it there to create the lightweight tag `v<version>`: it refuses while
`adjagent/` has uncommitted changes and again while that tag already exists, and it pushes nothing.
CONVENTIONS.md states where the version is written down, and the order a bump takes against its tag.

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
- **kb set + kbase** — the `kbase` skill alone: the definition a base install excludes by name and
  a kb install delivers — except under mage, which always includes it. `kbase.py` owns a directory,
  `skills/kbase/SKILL.md` routing by request and
  `skills/kbase/references/reading.md`, `building.md`, `maintaining.md`, `scoring.md`, and `scoring-system.md` carrying what
  each route needs; the router is the only text every session pays for, and the rule that a
  reference is read only when its route is reached is the router's own — its *Route by the request*
  section says so, and nothing but that text stops a read.
  `clauses.kb_orientation`, carrying the system model (two graphs, the leaf/summary contract,
  authored-vs-derived metadata, the cast) with a per-reference `role=` clause, goes to the two
  references that work a KB the build has finished with — reading, which reports, and maintaining,
  which modifies; `build.md` and `scoring.md` carry what their own job needs.
  The skill and its references are project-portable — per-project facts live in the consuming
  project's `kb-root/AGENTS.md`, under every harness. The toolchain they drive is kbase, the binary
  a kb install writes beside its snippets, and the set's route to it is MCP-only: every query, write
  op, `refresh`, `verify`, `build` and `score` the set names is a tool of the harness's `kbase` MCP
  server, offered under that harness's `mcp_tool_prefix`, and the one value outside its tools is
  that server's `kbase://model-hints` resource, read by uri. The router says so and stops where that
  server's tools are not offered — the executable and the `kb-` runner targets run only on the
  user's direction — and defers to kbase's own text, and to `kb-root/AGENTS.md`, wherever the skill
  disagrees with them.
  Scoring is the one whose call outlives it: `score` starts the run detached and answers once the
  run's ledger and pid stand, leaving `wait`, `status` and `cancel` to follow — the same three the
  build leaves. The loop is kbase's own — it enumerates the scoring set, renders the closed,
  score-free ask text, calls the configured provider, validates one value and lands it through the
  write ops, and records a run ledger — while `references/scoring.md` carries what kbase's own text
  does not: one quantity per ask and when a run is scoped to one pass, the model decision and what
  the run costs, the two values a run never scores and whose they are, and the ledger and
  resumption.
  `clauses.KB_RUNNER_TARGETS` is the maintaining reference's: where the project's runner carries the
  installed `kb-` targets, `refresh`, `verify` and `stats` are `kb-refresh`, `kb-verify` and
  `kb-stats`, run only on the user's direction. The consumer's runner targets are this repository's
  `kb-tools/runner-snippets/` fragments — `kb-verify`, `kb-refresh`, `kb-stats`, `kb-`-prefixed so they cannot collide with a
  consuming project's own targets — each running the executable it finds from the fragment's own
  directory.
- **Specialists** — applied-mathematician, biz-dev-strategist, economic-historian, literature-scout,
  marketing-comms-expert, ml-engineer, prompt-engineer, prose-architect, theoretical-economist:
  single-purpose, invoked directly rather than as part of a coding pipeline.
  applied-mathematician carries the `fam-ask-vs-stipulate` overlay anchor; `fam-gap-aversion` was
  authored in the retired `kb-claim-scorer` module and now renders nowhere.
