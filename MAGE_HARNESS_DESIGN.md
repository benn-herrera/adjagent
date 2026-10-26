# Design — the `mage` harness

A harness whose ROOT *is* the plugin directory: the three definition surfaces land unchanged inside
it, beside `.claude-plugin/plugin.json` (rendered) and, on a kb install, `.mcp.json` (the MCP settings
merge). No hook, no `imgread`, no absolute path anywhere in its output.

Read as settled: output paths stay harness-relative; `plugin.json` is mage's alone and carries
`VERSION` in-process; `.mcp.json` sits at the plugin root and names its server command relative to
itself; `CLAUDE.md` at the plugin root via `install-agents-file`, written with no `AGENTS.md`
redirect; `guardrail=None`; `.mage-temp`;
`mcp__kbase__`; no `imgread`. There is no separate user-level directory: `.` names the destination
itself, so a relative `user_harness_dir` resolves against the directory `install-agents-file` is
given, and that directory receives `CLAUDE.md` directly.

## Assumptions (recorded, not verified — mage is not installed here)

Each is one line in `adjagent/harnesses/mage.py`; the seam is what this design is responsible for.

| value | assumed |
|---|---|
| `model_pattern`, `model_shape`, `inherit_text="inherit"`, `inherit_synonyms=()`, `bare_tier_spec_is_all=False` | claude's, verbatim (`harnesses/claude.py:108-112`) |
| `tools` | claude's nine spellings (`harnesses/claude.py:97-107`) |
| `frontmatter`, `document_frontmatter` | claude's (`harnesses/claude.py:11-20`, `:114`) |
| `user_harness_dir` | `.` — the destination target itself; a relative user-harness-dir resolves against the directory being installed into |
| `agents_file` | `CLAUDE.md`, written with no redirect: mage's user directory is the destination itself, so the named directory receives the file rather than a redirect to `AGENTS.md` (`agents_file.py:127`) |
| `project_harness_dir` | `adjagent` — the subdirectory the plugin is created under, as `.claude` is claude's; `just install … --harness=mage ~/Mage/Plugins` writes `~/Mage/Plugins/adjagent` |
| `recipe_rule` | claude's text copied (`harnesses/claude.py:29-31`): the rule *restricts* behaviour, so keeping it on an assumed-equal shell tool errs safe |
| `coder_dispatch` | `None`: the bullet *grants* a per-dispatch model, and granting unverified capability is the wrong direction of error. Adopting it later is not a one-liner — its sentence must then be single-sourced with claude's |

Two values are deliberately *copied, not shared* with `claude.py` (model pattern, tool table, recipe
rule text): mage's vocabulary is a hypothesis, and importing claude's would make a claude edit change
mage silently. `just sweep-python` will list them as one-constant-two-definitions candidates; that is
the intended verdict, and the reason belongs in the commit message.

---

## 1. An emitted file that is not a definition

**Outcome.** A harness declares the files it renders of its own, and `render_all` emits them beside
the definitions. `render_definition`'s banner rules are untouched: a harness file has no frontmatter
and no banner, because its format admits no comment.

**The seam** — `adjagent/harness.py`:

```python
@dataclass(frozen=True)
class HarnessFile:
    """A file a harness renders into the output root beside the definitions: the path below the root,
    the builder for its whole text, and the marker a file at that path must hold to be one this
    repository wrote (a format admitting no comment carries its ownership as a value inside it)."""

    path: str                              # harness-relative, e.g. ".claude-plugin/plugin.json"
    text: Callable[[], str]                # the whole file, final newline included
    marker: str                            # the value inside the file that makes it ours
```

`Harness` gains `rendered_files: tuple[HarnessFile, ...] = ()`. A harness with no such file leaves it
`()` and renders nothing extra — claude and opencode are byte-identical afterwards.

mage's one harness file is its manifest, and its text is fixed because the ownership marker is a
substring of it:

```python
_PLUGIN_NAME = "adjagent"
_PLUGIN_DESCRIPTION = "Adjagent skills, agents, and MCP tools"

def _plugin_json() -> str:
    return json.dumps({"name": _PLUGIN_NAME, "version": VERSION, "description": _PLUGIN_DESCRIPTION}, indent=2) + "\n"
```

`json.dumps`'s default separators leave a space after each colon, so `HarnessFile.marker`
(`'"name": "adjagent"'`) is a substring of the text it recognises. A builder passing
`separators=(",", ":")` writes `"name":"adjagent"`, the marker vanishes, and a second install refuses
the manifest the first one wrote. The serialization and the marker are therefore one decision, and
`VERSION` is imported from `adjagent.version`, never restated.

`adjagent/render.py` gains:

```python
def harness_renders(ctx: Render) -> tuple[tuple[PurePosixPath, str], ...]:
    """(path, text) for every file `ctx.harness` renders into the output root, sorted by path; empty for
    a harness that renders none."""
```

and `render_all` (render.py:166-177) appends it after the definition loop, before the final `sorted`.

**Why here.** Three writers must produce the same bytes — `cli.py:91` (`render --out DIR`), `install`
(install.py:1070 → 1128), and the slot render (which is `install` with `--subdir= --with-kb`,
`devtools/scripts/_render-slot.sh:29`). `render_all` is the one function all three go through, so
the seam sits there and no call site can forget it. `write_renders` (render.py:190-201) already
creates `.claude-plugin/`, so it needs no change.

**Not `.mcp.json`.** That file is the kb install's MCP settings entry, not a render: it must not
appear on a base install (its command would name a pruned executable — the rule `_kbase_source`
enforces at install.py:339-343), and its entry is `McpSettings.entry`'s single product, already
written by `mcp_merge` for claude and opencode alike (install.py:726-760). Routing it through the
render seam would make a second writer of one entry — the two drift the moment the entry shape moves —
and would make mage the only harness whose settings file the prune reaches, where claude's and
opencode's survive a base install. Its provenance is §3.

## 2. Ownership

Three carriers, three claims — the third is new and is the only code change in the install's refusal
path.

- **Manifest** (`<ROOT>/.claude-plugin/plugin.json`): a render target, so it meets
  `_refuse_foreign_targets` (install.py:253-269) and `_is_ours` (install.py:205-216) — which reads a
  banner it cannot have. New recogniser beside the other two:

  ```python
  def _is_our_harness_file(path: Path, *, marker: str) -> bool:
      """A harness-rendered file this repository wrote: the marker the file states about itself appears
      in it. A file that cannot be read is not ours."""
  ```

  `_refuse_foreign_targets` takes a third class, `harness_targets: Iterable[tuple[Path, str]]`, and
  the install partitions the `renders` list by whether its path is one of `ctx.harness.rendered_files`
  — render targets keep `_is_ours`, harness targets use a closure over each file's marker. A file at
  that path without the marker (an operator's own manifest, a reformat that split `"name": "adjagent"`)
  refuses the install naming the path, as every other foreign target does; nothing is overwritten.

- **Prune.** Unchanged. `prune` (install.py:272-300) walks `SURFACES` only (install.py:93), so
  `plugin.json` and `.mcp.json` are outside its reach: neither can be read as a stale render. The
  manifest is written on every mage install, so it is never stale. As with a harness resource, the
  copy is one-way: if a later version stopped emitting it, it would stay — accepted, and the same
  limitation SPEC already states for shipped harness files.

- **`.mcp.json`**: never a render target and never pruned, so it is never refused as foreign. It is
  the settings file `mcp_merge` owns, with the settings rules it already has — absent → written whole,
  plain JSON → splice keeping every other byte, JSONC or a path `_settings_obstacle` names (install.py:679-691)
  → reported with the entry printed and left alone. Re-running a kb install is a no-op splice.

**Report lines.** No new lines, no new counts.
- Manifest: counted in `installed: N rendered files, …` (it is one of `written`), and named by
  `--verbose`'s `wrote <ROOT>/.claude-plugin/plugin.json` (install.py:1138-1146).
- `.mcp.json`: the existing two — `wrote …/.mcp.json with the kbase MCP entry` (install.py:748) and
  `registered the kbase MCP entry in …` (install.py:760), printed again on a re-run over unchanged
  bytes; the guardrail's `already registers the guardrail hook` (install.py:849) is unreachable here.
- No guardrail line at all: `guardrail is None` returns before the hook report (install.py:1150-1151).

## 3. A settings file inside ROOT

**Outcome.** `McpSettings` names *where* its file lives; every path in it is relative to that site, and
the entry's command is named relative to the same directory. One field, one call-site expression.

`adjagent/harness.py`:

```python
class McpSite(Enum):
    """Where a harness's MCP settings file lives: at the project root, where the file is the project's own
    and the install edits it in place; or at ROOT, where it is the plugin's own, beside `skills/`."""

    PROJECT = "project"
    HARNESS = "harness"
```

`McpSettings` gains `site: McpSite` (required — no default, so a new harness must decide);
`McpEntryBuilder.__call__(*, command: str, base: Path)` — `base` is the directory the command is
named relative to; `project_relative` is renamed `command_relative(command, base)` and its docstring
loses the claim that the install root always sits inside the project root (`harness.py:58-61`). The
rename is total, with no alias left behind: every harness module's `_mcp_entry` takes `base`, and
every caller — the install's two `mcp.entry(...)` calls and each test that builds an entry directly —
names it `base`. A caller left on `project_root=` raises `TypeError` where it runs.

`adjagent/install.py`: one expression, computed once beside `project` (install.py:1054) and used
everywhere the MCP base is meant —

```python
mcp_base = project if ctx.harness.mcp.site is McpSite.PROJECT else root
```

threaded into `_mcp_settings_file` (install.py:671-676), `_check_settings` (install.py:699-708),
`mcp_merge` (install.py:726), and the pre-write `entry`/`container` call (install.py:1093-1095). The
`project` parameter of `_mcp_settings_file`, `_settings_obstacle`, `_settings_to_read`,
`_check_settings` and `mcp_merge` is renamed `base` (its meaning was already "the root those paths are
joined to"); `guardrail_merge`
passes `base=project` and is otherwise untouched. `_check_runner` keeps the **project** root — the
consumer's justfile is theirs, not the plugin's. `install_kb_include_line` is skipped when the
harness's `user_harness_dir` is `.`: a plugin is not a repo project, so a mage install writes no
include line and creates no `Makefile`.

**mage's value**: `McpSettings(canonical=".mcp.json", alternatives=(), site=McpSite.HARNESS,
entry=_mcp_entry)`; its command is `command_relative(command, ROOT)` →
`skills/kbase/kb-tools/kbase` (`KB_TOOLS_PACKAGE`, install.py:45 + `KBASE_BASENAME`, install.py:52).
The entry shape is claude's — `{"command": ..., "args": ["mcp"]}` under `("mcpServers", "kbase")` —
so mage's `_mcp_entry` is a copy of `claude.py:34-36`, not an import of it: harness modules are
leaves and importing one harness from another would let a claude edit change mage.

*The brief's `skills/kbase/kbase` is shorthand and is not reproducible from the frozen destination;
the command is `skills/kbase/kb-tools/kbase`, and a test asserts `ROOT / command` is the installed
executable.*

**The agents file and the plugin root.** A harness whose `user_harness_dir` is `.` is installed at
its own root: the slot render writes its agents file at the root (`rendered/<slug>/CLAUDE.md`, sibling
to `.mcp.json`), not under `harness/<name>/`, because there is no separate install in a disjoint
location. A real install writes it too: `install.sh`, after the install verb, calls
`install-agents-file` when the harness's user-harness-dir is `.`, so `just install-with-kb …
--harness=mage ~/Mage/Plugins` leaves `~/Mage/Plugins/adjagent/CLAUDE.md`. The `harness/<name>/` nest
exists for a harness whose files sit in a project subdirectory; mage has none.

**A plugin always carries the kb set.** An install whose harness has `user_harness_dir` `.` sets
`kb_included` regardless of `--with-kb`: the plugin's `kbase` skill is part of its product, so a mage
install is always a kb install. A plain mage install with no kbase source refuses through
`_kbase_source`, naming `--kbase-dist`; `just install-with-kb`, or an install carrying the flag,
supplies it.

**claude and opencode afterwards**: `site=McpSite.PROJECT`, the renamed helper, otherwise identical
call graph. Their `.mcp.json` / `opencode.jsonc` paths and command strings are pinned by
`tests/test_adjagent_install.py:430-437`, `:758`, `:771-779` — those assertions must pass unchanged,
which is the check that this refactor changed no behaviour.

## 4. Omitting `imgread`

**Outcome.** A harness declares the definitions it renders nothing for; `render_all` applies it, so
the `render` verb, `install` and the slot honour it without passing anything.

`Harness.omits: frozenset[str] = frozenset()` — "definition names this harness renders nothing for";
`__post_init__` refuses a name that is not an IDENTIFIER (`vocabulary.IDENTIFIER`), which catches a
typo's shape. mage: `frozenset({"imgread"})`.

`render_all` composes it with the caller's filter, one place:

```python
keep = lambda defn: defn.name not in ctx.harness.omits and (include is None or include(defn))
```

so install.py:1070's `include=lambda defn: kb_included or not excluded(defn.name)` stays exactly what
it is — the invocation's kb decision over `NOT_BY_DEFAULT` (install.py:78) — and the two rules compose
at the one call site without either knowing the other. `definitions()` (render.py:44-52) is untouched.

**Why not on the definition.** `Definition` is harness-neutral by contract (`definition.py:2-4`) and
`imgread` has a use under claude and opencode; a harness predicate on the definition would put harness
knowledge in the one value the single-sourcing property depends on being neutral, and would make the
omission invisible from the harness instance a reader opens to ask what mage renders.

**Pruning an earlier one.** If an older mage render wrote `commands/imgread.md`, this run does not
write it, and `prune` removes it (banner present, name would ship) and names it. No code.

## 5. Nothing for mage to hook

`guardrail=None` already gives exactly opencode's path and nothing more:
`harness_resource_copies(root, harness="mage")` returns `[]` because `adjagent/harnesses/resources/mage/`
does not exist (install.py:155-156: "A harness shipping no resources directory copies nothing, which
is not an error"); the probe (install.py:1075-1079), `_check_settings` for the guardrail
(install.py:1097-1099), `guardrail_merge` and `_earlier_guardrail` are all behind `guardrail is not
None`; and install.py:1150-1151 returns before the hook report. No install path special-cases a
harness with no settings file, and none is added.

Two things that must stay true, and are tests rather than code: `resources/` holds no `mage/`
directory and remains without `__init__.py` (install.py's `load` must keep reading one harness per
module), and no `.claude/settings.json` is created at the plugin root or the project root by a mage
install.

## 6. Contract documents

### SPEC.md

| line | now | becomes |
|---|---|---|
| 3-4 | "renders Claude Code agent, command and skill definitions" | "renders agent, command and skill definitions" |
| 11-26 (Deployed Surfaces) | three surfaces, then the install product | unchanged for the surfaces; append to that paragraph: a mage ROOT holds one file more — `.claude-plugin/plugin.json`, the manifest a plugin is discovered by, rendered and neither a surface nor a definition |
| 20-21 | "the two fields both harnesses read" | "the two fields every harness reads" |
| 34 | "A **base install** — `just install` — delivers every definition … except the kb set" | append "— except a mage install, which always includes the kb set" |
| 50 | "Exclusion is decided once per definition … a base install keeps no kb-set definition it finds" | append: a mage install is always a kb install, so the exclusion never applies to it |
| 37-42 | "the harness's `kbase` MCP server entry in the project's own settings file" | "in the harness's MCP settings file — the project's own, or, under mage, the plugin's at ROOT" |
| 42-43 | "… and one runner include line in the project's own justfile or Makefile …" | append "— except a plugin harness, whose ROOT is its own project and which writes no runner include line and creates no `Makefile`" |
| 68-70 | "(`.opencode/` for `opencode`)" | "(`.opencode/` for `opencode`; mage installs under its `adjagent` subdirectory, so the named ROOT is the parent that `adjagent/` is created in)" |
| 117-124 | banner rule, harness-shipped files excepted | add the manifest to the exceptions: it carries no banner because a JSON file admits none, and its `name` field states its origin |
| 139-141 | "A project's agents file is named `AGENTS.md` under every harness … only the operator's user-global agents file is named as the harness names it" | "A project's agents file is named `AGENTS.md` under claude and opencode, whose user directory is a separate scope; where the destination is the harness's own directory — mage — the harness's name is used, so the file is `CLAUDE.md`" |
| 161-181 | "A harness's shipped files are the fifth class" | one sentence in this paragraph: a harness also *renders* files of its own into ROOT — mage's manifest — which are generated, not copied, carry no banner, and are replaced whole |
| 164-165 | "opencode's sits at … and claude's at …" | append "(mage ships none)" — the "A harness shipping none copies nothing" sentence then has a live subject |
| 244-251 (Write Safety) | ours = a generated banner, or `!INSTALLED!` | add the third carrier: a harness-rendered file is ours when it holds the marker that file states, and any other file at that path refuses like any foreign target |
| 252-256 | shipped harness files replaced whole, never removed | add: so is a harness-rendered file, and prune never reaches ROOT's top level, so neither class is removable |
| 270-272 | "A kb install's `kbase` settings file is held to the same" | append "wherever it lives — under mage it sits at the plugin root, inside ROOT" |
| 298-299 | "`CLAUDE.md` for Claude Code, `AGENTS.md` for opencode" | "`CLAUDE.md` for Claude Code and mage, `AGENTS.md` for opencode" |
| 307-314 (Harness Agents File) | "… and nothing else is written. Installed anywhere else, it is `AGENTS.md` …" | append: mage's destination is always its own directory, so it writes `CLAUDE.md` there and never reaches the `AGENTS.md` redirect rule |

### ARCHITECTURE.md

| line | now | becomes |
|---|---|---|
| 13 | resources: "`opencode/plugins/guardrail.ts` and `claude/hooks/guardrail.pl` today" | append "; mage ships none" |
| 55-66 (base install / kb set) | the two install types differ by one filter and three emissions; a base install drops every `NOT_BY_DEFAULT` match | append: a harness whose `user_harness_dir` is `.` is always a kb install, so the filter never applies to it |
| 73-100 (what a kb install writes) | "A kb install writes three things beyond the renders" — the kb set, the MCP entry, the runner include line | for mage it writes two: the runner include line is not written and no `Makefile` created |
| 464 (kb set + kbase) | "the definition a base install excludes by name" | append "— except under mage, which always includes it" |
| 82-88 | "claude's `.mcp.json`, or for opencode …" | add mage's `.mcp.json` at its plugin root: the settings file is the harness's own, `McpSettings.site` (`HARNESS`) |
| 84 | "Under both harnesses the entry's command is the installed executable's path relative to the project root, which ROOT always sits inside" | "Under every harness the entry's command is the installed executable's path relative to the directory that harness's settings file is resolved against — the project root, or, under mage, ROOT — so the settings file names no machine-specific path and a project can track it" |
| 99-119 (install sequence) | "renders every included definition" → "copies each file the installing harness ships" | "renders every included definition and every file the harness itself renders (mage's manifest), bar a definition the harness declares it renders nothing for (`Harness.omits`)" |
| 126-141 | resource copy, `_is_our_resource` | one sentence: a harness-rendered file is a third target class, recognised by the marker it states, refused without it |
| 143-145 | "claude declares one, opencode sets `None` because its plugin registers itself" | append "; mage sets `None` and ships no hook at all" |
| 214-221 (the include-line exemption) | the include line is written whatever the install type, except when the project is this repository | add the second exemption: a harness whose `user_harness_dir` is `.` writes no include line and creates no `Makefile`, because a plugin is not a repo project |
| 278 | "the directory name is the definition's name on both harnesses" | "on every harness" |
| 285 | the skill row: "the two fields both harnesses read" | "the two fields every harness reads" |
| 291 | "because both harnesses read the same two fields" | "because every harness reads the same two fields" |
| 294-308 (Harnesses and families) | `Harness` field list | add `rendered_files` (`HarnessFile`), `omits`, and `mcp`'s `site`; replace "both differ between the two harnesses" (:308) with "differ between claude and opencode, and mage holds claude's assumed values (model pattern, aliases, tool spellings, frontmatter) as copies it may revise independently" |
| 387-391 | the three `reference*` slots | state that no mage slot is taken, and why: the manifest carries `VERSION`, so a mage baseline would churn on every bump (CONVENTIONS, version bullet). A mage render is inspected ad hoc with `just render mage --harness=mage` |
| 408-424 (Sanctioned Invocation) | recipe list | no recipe changes; `_harness-value.sh` already answers `project-harness-dir` for any harness, so `--harness=mage` needs no script edit |

`adjagent/vocabulary.py:54` states the same count in code — `Kind`'s docstring says "the two fields
both harnesses read". It becomes "the two fields every harness reads" with the rest of this change,
in `harness.py`'s step rather than the documents': a code docstring moves with the file it describes.

### CONVENTIONS.md

| line | now | becomes |
|---|---|---|
| 58-72 (`NOT_BY_DEFAULT`) | the pattern over definition names, passed as the `include` filter | append: a harness that renders nothing for a definition declares it on `Harness.omits`, which `render_all` applies itself; `NOT_BY_DEFAULT` stays the invocation's filter, over names, passed by the caller |
| 81-84 (recogniser spells the banner) | generated-file prefixes built from `render.GENERATED_MARK` | append: a harness-rendered file carries no banner; its `HarnessFile.marker` is what reads it as ours, and the test plants a real render rather than a literal marker, for the same reason |
| 131-134 (the version) | "No rendered, installed or copied file carries the version: a bump must not churn the render slots" | "No rendered file carries the version except mage's `.claude-plugin/plugin.json`, whose whole purpose is to carry it. No reference slot is rendered for mage, so a bump still churns nothing under `rendered/` and `just render-diff` after one shows nothing." |
| 167-168 (the review roster) | "Unless otherwise specified the reviewers are an architect and a coder reviewing with THESIS.md, SPEC.md, ARCHITECTURE.md, and CONVENTIONS.md as their pre-task reading list." | "Unless otherwise specified the reviewers are an architect, a coder and a tech-writer reviewing with THESIS.md, SPEC.md, ARCHITECTURE.md, and CONVENTIONS.md as their pre-task reading list. The tech-writer reviews what the change ships as documentation — the contract documents, README, and any page a plan makes normative — for accuracy against the code and for whether a reader without the work thread can act on it." |

The roster this change is reviewed under is the three-seat one, since this change lands it: the
plan's review block names the three seats and their models.

The version rule's other statement, `adjagent/version.py`'s docstring at `:3-4`, takes the same
exception in the same act: "No rendered file carries it except mage's `.claude-plugin/plugin.json`,
whose purpose is to; no reference slot is rendered for mage, so a bump still churns nothing under
`rendered/`."

### README.md (not in the brief; changed by the same act)

Lines 48-51 ("Both harnesses ship one"), 55 (`--harness=opencode` installs into `.opencode/`),
349-352 (layout: "one module per harness (claude, opencode)"), 396-397, and the Install/MCP sections
around 78-91 and 299-310, which enumerate two harnesses: each gains mage, and the README gains one
sentence on the plugin-shaped install (`just install <plugins-parent> --harness=mage`, which creates
`<plugins-parent>/adjagent`).

Lines 159-169 (the agents-file install) gain mage: inference applies only to a harness whose
user-harness-dir is absolute, so mage is always named; and because mage's destination is its own
directory, the install writes `<dir>/CLAUDE.md` directly, never an `AGENTS.md` redirect.

The install product's include-line sentences (86, 403) gain mage: no include line and no `Makefile`,
because a plugin is not a repo project; and `rendered/<slug>/CLAUDE.md` is named beside `.mcp.json`,
not under `harness/<name>/`.

The base-install sentences (51, 271) gain mage: the kb set is always in a mage install, so the
base-install exclusion never applies to it. The KB toolchain's item 2 (320) notes that under mage
the include-line step does not run: no include line and no `Makefile`.

## 7. Tests

Assertions a test can make (all against values the code under test did not compute):

1. **The plugin tree for a mage render.** `write_renders(tmp, render_all(MAGE_RENDER))` yields
   `agents/python-coder.md` and `skills/kbase/SKILL.md` at the tree root (no extra nesting), plus
   `.claude-plugin/plugin.json`, and no `commands/imgread.md` — claude's slot holds it, and it is the
   only command, so mage has no `commands/` directory.
2. **The manifest.** `json.loads(...)` equals exactly
   `{"name": "adjagent", "version": VERSION, "description": "Adjagent skills, agents, and MCP tools"}` —
   the exact dict pins the three keys; the version is compared to `adjagent.version.VERSION`, never a
   literal.
3. **The manifest is the only version carrier.** For every other path `render_all(MAGE_RENDER)`
   produces, `VERSION not in text`.
4. **`.mcp.json` relative to its own directory.** A kb install into `<project>/plugins/adjagent`
   (so `root` is `<project>/plugins/adjagent`) writes `<root>/.mcp.json`, which parses to
   `{"mcpServers": {"kbase": {"command": "skills/kbase/kb-tools/kbase", "args": ["mcp"]}}}`; assert
   `<project>/.mcp.json` is absent and that `(root / command)` is the installed executable. The exact
   literal dict pins the relative command; a separate `is_absolute` assertion could not fail
   independently.
5. **No absolute path in mage's output.** For every file in the installed tree,
   `str(root.resolve()) not in` its text; the `"~/"` check applies to the files mage's own
   configuration writes (`.claude-plugin/plugin.json`, `.mcp.json`), since shipped definition prose
   may mention it.
6. **No hook, no settings edit.** No `hooks/` under ROOT; no `.claude/settings.json` at the project
   root or ROOT after a mage install (mirrors the opencode case at test_adjagent_install.py:1495-1499).
7. **The same on a kb install**: kb definitions and `skills/kbase/kb-tools/kbase` present, the
   manifest still exactly three keys with `VERSION`, and `.mcp.json` at `<root>/.mcp.json` with
   `<project>/.mcp.json` absent, and no `Makefile` at ROOT or the project.
8. **A fresh base install writes no `.mcp.json` and no `skills/`** — for claude and opencode; a mage
   install always includes the kb set, so it writes both or refuses for want of a kbase source — and
   a base install over a kb ROOT leaves `.mcp.json` where it stands (the claude behaviour, locked so
   it stays deliberate).
9. **Ownership.** A second mage install passes over its own manifest, byte-identical; an operator's
   `.claude-plugin/plugin.json` without the marker (`{"name": "other"}`) refuses with nothing written,
   naming the path; `--verbose` lists the manifest as written.
10. **`omits` names real definitions.** For every harness from `load("adjagent.harnesses", "HARNESS")`,
    every name in `harness.omits` is a discovered definition name — a typo would otherwise ship the
    file silently.
11. **Existing pins that move**: `tests/test_adjagent_install.py:359`
    (`sorted(load(...)) == ["claude", "opencode"]` → `["claude", "mage", "opencode"]`). Nothing else
    moves: `:354-360`'s resources claim still holds (mage has no resources directory), `:1324-1330`
    passes with mage contributing no sources, and the settings-file pins at `:430-437` (a JSON
    equality on `<project>/.mcp.json`), `:758` (`assert "enabled" not in text`) and `:771-779` (the
    parametrise table feeding `test_the_mcp_settings_file_is_created_when_absent`) are the guard that
    §3 changed no existing harness's output.
12. **The agents file in its own directory.** `install_agents_file(target, MAGE, uncommitted=())`
    writes `target/CLAUDE.md` and leaves `target/AGENTS.md` absent; and
    `install_agents_file(target, CLAUDE, uncommitted=())` where `target` is no user directory writes
    `target/AGENTS.md` plus `target/CLAUDE.md` holding only `@AGENTS.md` — the regression pin for a
    `_in_user_dir` widened to resolve a relative user directory against the destination.
13. **A mage install always includes the kb set.** `install(root, MAGE, with_kb=False,
    kbase_dist=<exe>)` writes `.mcp.json` and `skills/kbase/kb-tools/kbase`; the same call with no
    `kbase_dist` and no installed executable refuses, naming `--kbase-dist`.

Not added: mage is **not** appended to `test_adjagent.py:324-327` `_HARNESS_RENDERS` or to the
claude/opencode parametrisations at `test_adjagent.py:287`, `:305`, `test_adjagent_install.py:65`,
`:784`. Those cases pin a frontmatter shape per harness; mage's is an assumption, and a mage
case belongs beside the assumptions it tests, not inside another harness's pin.

---

## Implementation steps (one coder seat)

Mechanical unless marked **judgment**.

Steps 1 and 2 are one landing: `McpSettings.site` is required, so claude, opencode and the committed
mage module must supply it in the same change — step 1 alone leaves `just test adjagent` red at import.

1. `adjagent/harness.py` — add `HarnessFile`, `McpSite`; `Harness.rendered_files`, `Harness.omits`;
   `McpSettings.site`; rename `project_relative` → `command_relative` with the `base` parameter;
   extend `__post_init__` with the `omits` check (each name IDENTIFIER-shaped) and the module
   docstring. No `site` check: a field with no default cannot be absent, and an `isinstance` test
   there restates what the type checker proves. `adjagent/vocabulary.py:54`'s "the two fields both
   harnesses read" becomes "the two fields every harness reads" here, with `harness.py`'s docstring.
2. `adjagent/harnesses/claude.py`, `opencode.py`, and the committed `mage.py` — `site=` on each
   `McpSettings` (`PROJECT` for the first two, `HARNESS` for mage), the renamed helper, its
   `base` keyword and docstrings. Mage's minimum here is what keeps it importing: its
   `McpSettings(...)` and its `_mcp_entry`. The install's two `mcp.entry(...)` calls and each test
   that builds an entry directly take `base=` in the same step. **Gate:** `just test adjagent` green
   with the existing settings-file pins untouched; any diff in `just render-diff` after step 8 is a
   regression in this step.

3. `adjagent/harnesses/mage.py` — revise the committed module: it already holds `HARNESS` with
   `agents_file="CLAUDE.md"`, `project_harness_dir="adjagent"`, `user_harness_dir="."`, `.mage-temp`,
   claude's copied `_frontmatter`/`_RECIPE_RULE`/tool table/model pattern, and `guardrail=None`.
   Add `_PLUGIN_NAME`, `_PLUGIN_DESCRIPTION`, `_plugin_json()` as §1 states,
   `FILES = (HarnessFile(path=".claude-plugin/plugin.json", text=_plugin_json, marker=f'"name": "{_PLUGIN_NAME}"'),)`,
   `omits=frozenset({"imgread"})`, `rendered_files=FILES`, and the module docstring.
4. `adjagent/render.py` — `harness_renders`; `render_all` applies `ctx.harness.omits` and appends the
   harness files; docstrings. Steps 3 and 4 are one landing: the manifest is unobservable until
   `render_all` emits it.
5. `adjagent/install.py` — `mcp_base` and the `base` renames of §3, threaded through
   `_mcp_settings_file`, `_check_settings`, and `mcp_merge` — its definition and its call at
   install.py:1148 both, the call being positional and so silent if missed; `_is_our_harness_file`;
   the third target class in `_refuse_foreign_targets` and the partition of `renders` at
   install.py:1080-1084 (**judgment**: express the partition and marker closure however reads
   cleanest — a list of `(target, ours)` pairs built at the call site, or a per-file closure;
   behaviour is fixed, shape is not); docstrings of `install`, `mcp_merge`, `prune`'s note.
   `install_kb_include_line` is skipped when `ctx.harness.user_harness_dir` is `.`, and
   `kb_included` is true for that harness regardless of `--with-kb`.
6. `adjagent/agents_file.py` and the shell — `_in_user_dir` resolves a relative `user_harness_dir`
   against the destination (§ "Required fixes"); `scope_name` is not edited, so mage's installed file
   and its rendered harness file open `# Global info and directives`; `devtools/scripts/install-agents-file.sh:13-30`
   stops treating a relative `user-harness-dir` as an inference basis and refuses naming the harnesses
   it can infer; `justfile:56`'s `[doc]` string says which those are. Assertion 12 lands here, because
   the fix is otherwise revertible with the suite green.
7. `tests/test_adjagent_install.py` (the mage install cases, ownership, `.mcp.json` at ROOT, the
   `omits` case), `tests/test_adjagent.py` (render-tree and manifest cases), plus a new
   `tests/test_adjagent_mage.py` if the two files get crowded (**judgment**: file split only).
   Assertions 4, 7, 8 and 12 land with steps 5 and 6 respectively; the rest here. *Re-run:*
   `just test adjagent`, then `just test-changed`.
8. Contract documents per §6: `SPEC.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `README.md`.
9. `devtools/scripts/_render-slot.sh` — write the agents file at `out/<agents-file>` when the
   harness's user-harness-dir is `.`, else at `out/harness/<name>/<agents-file>`; the slot comments
   in `render.sh` follow. `devtools/scripts/install.sh` — after the install verb, call
   `install-agents-file` when the harness's user-harness-dir is `.`, so a real plugin install writes
   `ROOT/<agents-file>`.

**Re-run before the change is called done:** `just test-changed`, `just sweep-python` (read the
candidates and answer them), `just render mage --harness=mage` and inspect `rendered/mage` by hand
(`find rendered/mage -maxdepth 2`), then `just render` and `just render-diff` — **which must report
nothing**, the reference slots being claude/opencode/gemma and no existing harness's output having
changed.

## Chosen not to specify

- The partition expression and closure style inside `_refuse_foreign_targets` — fixed behaviour, free
  shape.
- Whether the mage tests live in the existing install test file or a new one.
- A collision check between a harness file's path and a definition's output path: the two roots
  (`.claude-plugin/` vs `agents|commands|skills`) cannot meet by construction, and no authoring path
  reaches it. Revisit only if a harness file is ever authored under a surface.
- A runtime check that `Harness.omits` names a real definition: the harness dataclass must not import
  the definitions package, so it is a test (assertion 10), which is also where a typo is caught.
- Whether a future mage-specific frontmatter needs the `Render` in `HarnessFile.text`; the field's type
  is the one line that changes if so.

## Accepted frictions (not defects to fix here)

- **A staging ROOT.** `install.sh` derives the project root from the directory it names, so
  `just install <staging> --harness=mage --subdir=` makes the plugin root its own project root and
  merges `.mcp.json` inside the plugin tree. The plugin writes no runner include line, so there is
  nothing to include from. An operator-supplied `--project-root=<project>` still reaches the verb
  after the recipe's own (argparse takes the last), or the plugin is installed inside the consuming
  project with `--subdir=<rel>`.
- **`imgread` under mage.** A session loses the clipboard-image command; there is no mage-side
  substitute in this change.

## Required fixes

- **`install-agents-file` and the relative user directory.** `Harness.user_harness_dir` is resolved
  with `Path(...).expanduser()`, so a relative `"."` resolves against the process's working directory
  rather than the directory being installed into. For mage, `"."` means the destination target itself:
  `_in_user_dir` must resolve a relative user directory against the destination —
  `(directory / Path(harness.user_harness_dir).expanduser()).resolve() == directory.resolve()`, which
  leaves an absolute value (`~/.claude`, `~/.config/opencode`) behaving exactly as it does now — so no
  `AGENTS.md` redirect is written and `CLAUDE.md` is the file installed. This is a defect fixed in
  this change.

  Two outcomes follow and are not the coder's choice. First, `_in_user_dir` returns True for mage in
  **every** directory, so `scope_name`'s existing first branch applies unedited and the harness's own
  `Global` scope results: the installed `CLAUDE.md` and
  `rendered/<slug>/harness/mage/CLAUDE.md` both open `# Global info and directives`, never a
  directory's own name. A scope named for the directory would be a `scope_name` change and a line in
  this section, not an implementation pick. Second, the shell's copy of the same rule must agree —
  next bullet.

- **`install-agents-file`'s harness inference, in the shell.** `devtools/scripts/install-agents-file.sh:13-30`
  infers the harness by resolving each harness's `user-harness-dir` and comparing it to `DIR`
  resolved. `_harness-value.sh mage user-harness-dir` answers `.`, so the loop resolves mage against
  the process's working directory and mage matches whenever `DIR` *is* that directory — the script
  then writes a generated `CLAUDE.md` where its own comment promises "a project root matches none",
  and after the Python fix it disagrees with `_in_user_dir`, which is true everywhere. The predicate
  is one rule with two implementations, so they move together: **a relative `user_harness_dir` names
  no directory and is never an inference basis** — the loop skips such a harness — and with no harness
  named and no match the script refuses, naming the harnesses it can infer. `justfile:56`'s `[doc]`
  string states the same: which harnesses those are, and that a relative value infers nothing.
