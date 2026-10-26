# ACTIVE_PLAN — Add the `mage` harness (plugin `adjagent`)

**Normative page:** `MAGE_HARNESS_DESIGN.md` (tracked, 512 lines). On this subject the design page is
the requirement and this plan is the route. Where a plan row and the page disagree, the work
implements the page and the plan's line is reported as moved, in the commit that lands it. The
design's "## Implementation steps (one coder seat)" (`:399-458`) is the spine; its §6 tables
(`:252-335`) are the whole document change; its §7 assertions (`:341-390`) are the acceptance
criteria; its "Chosen not to specify" (`:460-471`), "Accepted frictions" (`:473-482`) and "Required
fixes" (`:484-512`) are stated limits.

## Decisions confirmed at kickoff — outcomes and their consequences

1. **The plugin is named `adjagent`.** The harness is `mage`; the plugin it renders is `adjagent`.
   Consequence: `_PLUGIN_NAME = "adjagent"`; the manifest's `"name"` field and the ownership marker
   both read `adjagent`; the module is `adjagent/harnesses/mage.py`, **already committed**, and this
   change revises it rather than creating it.
2. **The plugin ROOT is the plugin directory.** Definitions land unchanged beside
   `.claude-plugin/plugin.json` (rendered) and, on a kb install, `.mcp.json` (the MCP settings
   merge). Consequence: output paths stay harness-relative; no hook; no `imgread`; no absolute path
   anywhere in its output.
3. **`MAGE_HARNESS_DESIGN.md` is the sole authority.** Anything not stated there or forced by a file
   read in the tree is out of scope. No extra files, document edits or features are added beyond its
   eight steps and §6 rows.

## Verified facts from the current tree

Re-read against the working tree at `68472ef`. **The baseline is red:** `adjagent/harnesses/mage.py`
is committed, so the harness list `load` returns has three entries while the ownership pin still
expects two. Package 1 clears that before any other package is dispatched; every later done-line is
"no failure", not "green after a known failure".

| Fact | Command | Answer |
|---|---|---|
| `VERSION` is `0.12.2` | `cat adjagent/version.py` | `VERSION = "0.12.2"` |
| `mage.py` is tracked | `git ls-files adjagent/harnesses/mage.py` | `adjagent/harnesses/mage.py` |
| `mage.py` last moved in `68472ef` | `git log --oneline -1 -- adjagent/harnesses/mage.py` | `68472ef checkpoint - plan written, pending PE review.` |
| The suite is red today | `just test adjagent` | `1 failed, 423 passed`; the failure is `test_the_resources_tree_is_not_read_as_a_harness_module` at `tests/test_adjagent_install.py:359` |
| That pin still expects two harnesses | `sed -n '359p' tests/test_adjagent_install.py` | `assert sorted(load("adjagent.harnesses", "HARNESS")) == ["claude", "opencode"]` |
| `render-diff` is clean today | `just render-diff` | no output, exit 0 |
| `install.py:45` is the kb-tools destination | `sed -n '45p' adjagent/install.py` | `KB_TOOLS_PACKAGE = "skills/kbase/kb-tools"` |
| `install.py:52` is the executable basename | `sed -n '52p' adjagent/install.py` | `KBASE_BASENAME = "kbase.exe" if os.name == "nt" else "kbase"` |
| `install.py:78` is the exclusion pattern | `sed -n '78p' adjagent/install.py` | `NOT_BY_DEFAULT = re.compile(r"^(kb-\|kbase$)")` |
| `install.py:93` names the three surfaces | `sed -n '93p' adjagent/install.py` | `SURFACES = ("agents", "commands", "skills")` |
| `install.py:155-156` is the "no resources directory" sentence | `sed -n '155,156p' adjagent/install.py` | `…later install knows the target is one it wrote…` / `a harness shipping no resources directory copies nothing, which is not an error.` |
| `install.py:205` opens `_is_ours` | `sed -n '205p' adjagent/install.py` | `def _is_ours(path: Path) -> bool:` |
| `install.py:253` opens `_refuse_foreign_targets` | `sed -n '253p' adjagent/install.py` | `def _refuse_foreign_targets(root: Path, *, render_targets: Iterable[Path], resource_targets: Iterable[Path]) -> None:` |
| `install.py:272` opens `prune` | `sed -n '272p' adjagent/install.py` | `def prune(root: Path, *, keep: set[Path]) -> list[Path]:` |
| `install.py:671` opens `_mcp_settings_file` | `sed -n '671p' adjagent/install.py` | `def _mcp_settings_file(project: Path, *, harness: Harness) -> Path:` |
| `install.py:679` opens `_settings_obstacle` | `sed -n '679p' adjagent/install.py` | `def _settings_obstacle(target: Path, *, project: Path) -> str \| None:` |
| `install.py:694` opens `_settings_to_read` | `sed -n '694p' adjagent/install.py` | `def _settings_to_read(target: Path, *, project: Path) -> bool:` |
| `install.py:699` opens `_check_settings` | `sed -n '699p' adjagent/install.py` | `def _check_settings(target: Path, *, project: Path, container: tuple[str, ...], leaf: type) -> None:` |
| `install.py:726` opens `mcp_merge` | `sed -n '726p' adjagent/install.py` | `def mcp_merge(project: Path, *, harness: Harness, command: str) -> None:` |
| `install.py:738` is the entry call inside `mcp_merge` | `sed -n '738p' adjagent/install.py` | `entry, container = harness.mcp.entry(command=command, project_root=project)` |
| `install.py:1054` computes `project` | `sed -n '1054p' adjagent/install.py` | `project = root.resolve() if project_root is None else Path(project_root).resolve()` |
| `install.py:1070` is the install's `render_all` call | `sed -n '1070p' adjagent/install.py` | `renders = render_all(ctx, include=lambda defn: kb_included or not excluded(defn.name))` |
| The install calls `_refuse_foreign_targets` at `:1080` | `sed -n '1080p' adjagent/install.py` | `_refuse_foreign_targets(` |
| The pre-write `entry` call is at `:1093` | `sed -n '1093p' adjagent/install.py` | `_, mcp_container = ctx.harness.mcp.entry(command=kbase_command, project_root=project)` |
| `written = write_renders(root, renders)` is at `:1128` | `sed -n '1128p' adjagent/install.py` | `written = write_renders(root, renders)` |
| `if verbose:` is at `:1144` | `sed -n '1144p' adjagent/install.py` | `if verbose:` |
| The MCP merge call is at `:1148`, positional | `sed -n '1148p' adjagent/install.py` | `mcp_merge(project, harness=ctx.harness, command=kbase_command)` |
| `if guardrail is None:` is at `:1150` | `sed -n '1150p' adjagent/install.py` | `if guardrail is None:` |
| `render.py:44` opens `definitions`; `:166` `render_all`; `:190` `write_renders` | `sed -n '44p;166p;190p' adjagent/render.py` | `def definitions(…)`, `def render_all(`, `def write_renders(…)` |
| `mage.py` already constructs `McpSettings` without `site` | `grep -n "mcp=McpSettings" adjagent/harnesses/mage.py` | `62:    mcp=McpSettings(canonical=".mcp.json", alternatives=(), entry=_mcp_entry),` |
| `harness.py:114` opens `__post_init__` | `sed -n '114p' adjagent/harness.py` | `    def __post_init__(self) -> None:` |
| Every `project_relative` site | `grep -rn "project_relative" adjagent tests --include="*.py"` | `harness.py:58` (the definition), `claude.py:7`, `:36`, `mage.py:6`, `:29`, `opencode.py:6`, `:30` — seven sites |
| Every `mcp.entry(...)` call site | `grep -rn "\.entry(" adjagent tests --include="*.py"` | `install.py:738`, `install.py:1093`, `tests/test_adjagent_install.py:709`, `:710`, `:814` |
| `_CLAUDE_RENDER` sits at `test_adjagent_install.py:230` | `sed -n '230p' tests/test_adjagent_install.py` | `_CLAUDE_RENDER = Render(harness=CLAUDE, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))` |
| The trigger pin is at `:359` | `sed -n '359p' tests/test_adjagent_install.py` | `assert sorted(load("adjagent.harnesses", "HARNESS")) == ["claude", "opencode"]` |
| `_HARNESS_RENDERS` holds claude and opencode only | `sed -n '324,327p' tests/test_adjagent.py` | `_HARNESS_RENDERS = [Render(harness=CLAUDE, …), Render(harness=OPENCODE, …)]` |
| The opencode "no claude settings" case is at `:1495-1499` | `sed -n '1495,1499p' tests/test_adjagent_install.py` | `def test_an_opencode_install_writes_no_claude_settings_file(tmp_path: Path) -> None:` |
| `_in_user_dir` and `scope_name` | `sed -n '61,67p' adjagent/agents_file.py` | `def _in_user_dir(harness: Harness, directory: Path) -> bool:` / `    return Path(harness.user_harness_dir).expanduser().resolve() == directory.resolve()` / `def scope_name(harness: Harness, directory: Path) -> str:` / `    return GLOBAL_SCOPE if _in_user_dir(harness, directory) else directory.resolve().name` |
| `GLOBAL_SCOPE` is `"Global"` | `sed -n '25p' adjagent/agents_file.py` | `GLOBAL_SCOPE = "Global"` |
| The agents file's first line is the scope hole | `sed -n '12p' adjagent/definitions/harness_agents_file.py` | `        body=f"""# @!agf-scope-name!@ info and directives` |
| mage's user-harness-dir is relative | `PYTHONPATH=. python3 -m adjagent harness mage user-harness-dir` | `.` (claude answers `~/.claude`, opencode `~/.config/opencode`) |
| The shell's inference block | `sed -n '13,30p' devtools/scripts/install-agents-file.sh` | resolves each harness's `user-harness-dir` against `DIR` and matches on equality |
| `justfile:56` is the recipe's `[doc]` string | `sed -n '56p' justfile` | the `install-agents-file` doc, naming `[harness] (claude, opencode)` |
| CONVENTIONS' `NOT_BY_DEFAULT` bullet opens at `:58` | `sed -n '58,59p' CONVENTIONS.md` | `- **A set a default install excludes is excluded by its definitions' names, held in` / ``  `NOT_BY_DEFAULT`.** … `` |
| CONVENTIONS' review roster | `sed -n '167,168p' CONVENTIONS.md` | `- Unless otherwise specified the reviewers are an architect and a coder reviewing with THESIS.md,` / `SPEC.md, ARCHITECTURE.md, and CONVENTIONS.md as their pre-task reading list.` |
| The render slots are not per-harness | `command ls rendered/` | `check-reference`, `check-reference-gemma`, `check-reference-opencode`, `latest`, `reference`, `reference-gemma`, `reference-opencode`, `retake-reference` (no `mage`, no `claude`, no `opencode`) |
| Recipe bodies are scripts under `devtools/scripts/` | `command ls devtools/scripts/` | 17 files: `_download-kbase-dist.sh`, `_harness-names.sh`, `_harness-value.sh`, `_kbase-bin.sh`, `_render-slot.sh`, `format-python.sh`, `install-agents-file.sh`, `install-agents-here.sh`, `install-with-kb.sh`, `install.sh`, `render-agents-file.sh`, `render.sh`, `retake-reference.sh`, `sweep-python.sh`, `tag.sh`, `test-changed.sh`, `test.sh` |
| The runner targets exist | `just --summary` | `default format-python install install-agents-file install-with-kb render render-diff retake-reference sweep-python tag test test-changed` |

The three settings-file pins the design cites are not byte assertions:
`tests/test_adjagent_install.py:430-437` is a JSON equality on `<project>/.mcp.json`; `:758` is
`assert "enabled" not in text`; `:771-779` is the parametrise table feeding
`test_the_mcp_settings_file_is_created_when_absent`. The design's other file citations land on the
current tree; its rows this pass revised are `CONVENTIONS.md:58-72` and `ARCHITECTURE.md:84`, `:278`,
`:285`, `:291`, `:308`, and its §5 sentence citation `install.py:155-156`.

---

## Work packages

The design's eight implementation steps are packaged below. Each package states its scope in
files/symbols, the command and answer for every fact it acts on, and its done-line in runner targets.
Judgment marks at design `:394` (the partition's shape) and `:405` (the test-file split) remain
judgment.

**Ordering.** Packages run in the order below, one at a time, each landing green. Two merges are
deliberate and are not splittable: Package 2 carries design steps 1-2 (a required field with no
default cannot land without its suppliers), and Package 3 carries steps 3-4 (the manifest is
unobservable until `render_all` emits it). No package may be dispatched until the one before it
lands, because each one's done-line reads the same suite.

### Package 1 — the ownership pin: a green baseline

**Status:** done — `424 passed`; committed with the plan status.

**Scope:** `tests/test_adjagent_install.py` — `:359`, and the docstring sentence at `:355-358` that
states how many harnesses `load` returns.

**Facts to act on:**
- `sed -n '359p' tests/test_adjagent_install.py` → `assert sorted(load("adjagent.harnesses", "HARNESS")) == ["claude", "opencode"]`.
- `just test adjagent` → `1 failed, 423 passed`; the only failure is that line.
- `git ls-files adjagent/harnesses/mage.py` → `adjagent/harnesses/mage.py` — the module is already
  committed, which is why the assertion fails.

**Actions:**
1. `:359` → `assert sorted(load("adjagent.harnesses", "HARNESS")) == ["claude", "mage", "opencode"]`.
2. `:356` docstring "`load` returns the two harnesses" → "`load` returns every harness module"; the
   `:360` resources assertion (`(REPO_ROOT / HARNESS_RESOURCES_SOURCE / "opencode").is_dir()`) stays.

**Done-line:** `just test adjagent` → `424 passed, 0 failed` (today's 423 passing plus the one that
was failing); `just test-changed` prints surface `adjagent`.

### Package 2 — `harness.py` types, and `site` on every harness (design steps 1-2, one seat)

**Status:** done — `424 passed`; `render-diff` no pairs.

**Scope:** `adjagent/harness.py` (`HarnessFile`; `McpSite`; `Harness.rendered_files`;
`Harness.omits`; `McpSettings.site`; `project_relative` → `command_relative(command, base)` with the
builder keyword `base`; `__post_init__`; module docstring); `adjagent/harnesses/claude.py`,
`adjagent/harnesses/opencode.py`, `adjagent/harnesses/mage.py` (each `McpSettings(...)` and
`_mcp_entry`); `adjagent/install.py:738` and `:1093` (the builder keyword); `tests/test_adjagent_install.py:709`,
`:710`, `:814`; `adjagent/vocabulary.py:54`.

**Facts to act on:**
- `grep -rn "project_relative" adjagent tests --include="*.py"` → `harness.py:58` (the definition),
  `claude.py:7` and `:36`, `mage.py:6` and `:29`, `opencode.py:6` and `:30` — seven sites, no caller
  outside the package and its tests.
- `grep -rn "\.entry(" adjagent tests --include="*.py"` → `install.py:738`, `install.py:1093`,
  `tests/test_adjagent_install.py:709`, `:710`, `:814` — five call sites, all keyword.
- `grep -n "mcp=McpSettings" adjagent/harnesses/mage.py` → `62:    mcp=McpSettings(canonical=".mcp.json", alternatives=(), entry=_mcp_entry),`
  — mage is already loaded by the suite, so it must supply `site` in this package or the suite is red
  at import.
- `sed -n '114p' adjagent/harness.py` → `    def __post_init__(self) -> None:`.
- Design `:46-55` (`HarnessFile`), `:148-155` (`McpSite`), `:157-163` (`site` and the `base`
  keyword), `:201-203` (`Harness.omits` and `__post_init__`'s check on it).

**Actions:**
1. Add `HarnessFile` frozen dataclass exactly as design `:46-55`: `path: str`, `text: Callable[[], str]`,
   `marker: str`.
2. Add `McpSite` enum (`PROJECT = "project"`, `HARNESS = "harness"`) as design `:148-155`.
3. Add `Harness.rendered_files: tuple[HarnessFile, ...] = ()`.
4. Add `Harness.omits: frozenset[str] = frozenset()`.
5. Add `McpSettings.site: McpSite` **required, no default** — design `:157`; a new harness must
   decide.
6. Rename `project_relative(command, project_root)` to `command_relative(command, base)`; its
   docstring drops the "install root always sits inside the project root" claim.
7. Change `McpEntryBuilder.__call__`'s keyword to `base` (`harness.py:38-44`) and update the five
   call sites named above, each passing `base=<what it already passes>`. The call at `install.py:738`
   and `:1093` passes `base=project` until Package 4 introduces `mcp_base`.
8. Extend `__post_init__` with the `omits` check: each name must be IDENTIFIER-shaped
   (`vocabulary.IDENTIFIER`). **No `site` check** — a field with no default cannot be absent, and
   `isinstance(self.mcp.site, McpSite)` would restate the type checker.
9. In `claude.py` and `opencode.py`: `site=McpSite.PROJECT`; `command_relative(command, base)` in
   `_mcp_entry`, whose signature becomes `(*, command: str, base: Path)`; the import line and
   docstrings per design §2-§3. In `mage.py`: the same edits, import included, with
   `site=McpSite.HARNESS` — nothing else in that module in this package.
10. `adjagent/vocabulary.py:54` — "the two fields both harnesses read" → "the two fields every
    harness reads" (design's ARCHITECTURE note names the same sentence in the document).
11. Update `harness.py`'s module docstring.

**Done-line:** `just test adjagent` reports no failure, the settings-file pins included —
`tests/test_adjagent_install.py:430-437`, `:758` and `:771-779` assert claude's and opencode's exact
paths and command strings unchanged, which is what proves the rename changed no behaviour.

### Package 3 — the harness-file seam: `mage.py` and `render.py` (design steps 3-4)

**Status:** done — `424 passed`; `render-diff` no pairs; manifest has three keys.

**Scope:** `adjagent/harnesses/mage.py` (revise the committed module: `_PLUGIN_NAME`,
`_PLUGIN_DESCRIPTION`, `_plugin_json()`, `FILES`, `omits`, docstring); `adjagent/render.py`
(`harness_renders`; `render_all` applies `ctx.harness.omits` and appends the harness files;
docstrings).

**Facts to act on:**
- `cat adjagent/harnesses/mage.py` → the module already holds `HARNESS` with `agents_file="CLAUDE.md"`,
  `project_harness_dir="."`, `user_harness_dir="."`, `project_temp_dir=".mage-temp"`,
  `mcp_tool_prefix="mcp__kbase__"`, claude's copied `_RECIPE_RULE`/tool table/model
  pattern/`_frontmatter`, `coder_dispatch=None`, `guardrail=None`, and `document_frontmatter=()`.
  It holds no `FILES`, no `omits`, no `_PLUGIN_NAME`, no `_PLUGIN_DESCRIPTION`.
- `sed -n '166,177p' adjagent/render.py` → `render_all`'s body: the loop over `definitions`, then
  `return tuple(sorted(rendered))`.
- Design `:37-99` (§1) and `:63-77` (the manifest builder and its marker).
- `cat adjagent/version.py` → `VERSION = "0.12.2"`, imported in-process.

**Actions:**
1. `mage.py`: `_PLUGIN_NAME = "adjagent"`; `_PLUGIN_DESCRIPTION = "Adjagent skills, agents, and MCP
   tools"`; `_plugin_json()` returning exactly
   `json.dumps({"name": _PLUGIN_NAME, "version": VERSION, "description": _PLUGIN_DESCRIPTION}, indent=2) + "\n"`
   with `VERSION` imported from `adjagent.version`. The serialization is fixed, not a judgment: the
   marker `'"name": "adjagent"'` is a substring of it, so `separators=(",", ":")` would make a second
   install refuse its own manifest (design `:63-77`).
2. `FILES = (HarnessFile(path=".claude-plugin/plugin.json", text=_plugin_json, marker=f'"name": "{_PLUGIN_NAME}"'),)`.
3. `HARNESS` gains `rendered_files=FILES` and `omits=frozenset({"imgread"})`; every other value
   stands as committed.
4. Add/refresh the module docstring.
5. `render.py`: add `harness_renders(ctx)` as design `:80-83` — `(path, text)` for every file
   `ctx.harness` renders into the output root, sorted by path, empty where none.
6. In `render_all`, compose the caller's `include` with `ctx.harness.omits` via the design's `keep`
   lambda (`:207`): `keep = lambda defn: defn.name not in ctx.harness.omits and (include is None or include(defn))`.
7. Append `harness_renders(ctx)` after the definition loop, before the final `sorted`.
8. Update `render.py`'s docstrings.

**Judgment marks:** "copied, not shared" is design `:30-33`; `just sweep-python` will list the
copies and the intended verdict belongs in the commit message.

**Done-line:** `just test adjagent` reports no failure; `just render mage --harness=mage` then
`cat rendered/mage/.claude-plugin/plugin.json` → exactly three keys with `"version": "0.12.2"`, and
`ls rendered/mage/commands/imgread.md` reports no such file, while claude's slot holds it.

### Package 4 — `install.py`: `mcp_base`, the third target class, and the settings tests

**Status:** done — `427 passed`; `render-diff` no pairs.

**Scope:** `adjagent/install.py` — `mcp_base` beside `project`; `project` → `base` in
`_settings_obstacle`, `_settings_to_read`, `_check_settings`, `mcp_merge`; `_is_our_harness_file`;
third target class in `_refuse_foreign_targets`; the partition of `renders` at `:1080-1084`;
docstrings of `install`, `mcp_merge`, `prune`'s note. Tests: design §7 assertions 4, 7 and 8 in
`tests/test_adjagent_install.py`.

**Facts to act on:**
- `sed -n '1054p' adjagent/install.py` → `project = root.resolve() if project_root is None else Path(project_root).resolve()`.
- `grep -n "^def mcp_merge\|mcp_merge(project" adjagent/install.py` → `726:def mcp_merge(project: Path, …)`
  and `1148:        mcp_merge(project, harness=ctx.harness, command=kbase_command)` — the call is
  **positional**, so a missed site is not an error; it silently puts mage's `.mcp.json` at the project
  root.
- `sed -n '671p;679p;694p;699p' adjagent/install.py` → `_mcp_settings_file`, `_settings_obstacle`,
  `_settings_to_read`, `_check_settings`, each taking `project`.
- `sed -n '1070p;1080p;1086p;1093p;1128p;1144p;1148p;1150p' adjagent/install.py` → the render call,
  the refusal call, the `copies` list, the pre-write entry call, the write, `if verbose:`, the MCP
  call, `if guardrail is None:`.
- `sed -n '253,268p' adjagent/install.py` → `_refuse_foreign_targets`'s two-class body.
- Design `:101-139` (§2), `:141-194` (§3), `:111-114` (`_is_our_harness_file`).

**Actions:**
1. Add `mcp_base` beside `project` at `:1054`: `mcp_base = project if ctx.harness.mcp.site is McpSite.PROJECT else root`.
2. Thread it into `_mcp_settings_file` (`:671-676`), `_check_settings` (`:699-708`), `mcp_merge`'s
   definition (`:726`) **and its call at `:1148`** — `mcp_merge(mcp_base, harness=ctx.harness, command=kbase_command)`
   — and the pre-write `entry`/settings calls at `:1093-1094`.
3. Rename the `project` parameter to `base` in `_mcp_settings_file`, `_settings_obstacle`,
   `_settings_to_read`, `_check_settings` and `mcp_merge`; `guardrail_merge` passes `base=project` and
   is otherwise untouched. `_check_runner` and `install_kb_include_line` keep the **project** root.
4. Add `_is_our_harness_file(path, *, marker)` as design `:111-114`: the marker the file states about
   itself appears in it; a file that cannot be read is not ours.
5. Extend `_refuse_foreign_targets` with a third class `harness_targets: Iterable[tuple[Path, str]]`;
   the install partitions `renders` by whether its path is one of `ctx.harness.rendered_files` —
   compare `relative == PurePosixPath(file.path)`, since `renders` carries `PurePosixPath` and
   `HarnessFile.path` is a `str`. Render targets keep `_is_ours`, harness targets a closure over each
   file's marker. A file at that path without the marker refuses the install naming the path; nothing
   is overwritten.
6. **Judgment (design `:394`):** express the partition and marker closure however reads
   cleanest — a list of `(target, ours)` pairs at the call site, or a per-file closure. Behaviour is
   fixed; shape is not.
7. Update the docstrings of `install`, `mcp_merge` and `prune`'s note.
8. Tests (assertions 4, 7, 8): the kb install into `<project>/plugins/adjagent` asserts
   `<root>/.mcp.json` parses to the relative `kbase` entry and `<project>/.mcp.json` is **absent**;
   the base install writes no `.mcp.json` and no `skills/`, and a base install over a kb ROOT leaves
   `.mcp.json` standing. Without the absence assertion a test reading `<project>/.mcp.json` passes
   over exactly the bug this package fixes.

**Done-line:** `just test adjagent` reports no failure, the new kb-install cases included — a kb
install into `<project>/plugins/adjagent` with `<root>/.mcp.json` present and `<project>/.mcp.json`
absent is the case that fails if `mcp_base` is not threaded into the `:1148` call.

### Package 5 — the agents file: the relative user directory, in code and in the shell

**Status:** done — `428 passed`; rendered harness file opens `# Global info and directives`.

**Scope:** `adjagent/agents_file.py` (`_in_user_dir`; `scope_name` **not** edited);
`devtools/scripts/install-agents-file.sh:13-30`; `justfile:56`; `tests/test_adjagent_install.py`
(assertion 12, beside the existing agents-file cases at `:190-220`).

**Facts to act on:**
- `sed -n '61,67p' adjagent/agents_file.py` → `_in_user_dir` compares
  `Path(harness.user_harness_dir).expanduser().resolve()` to `directory.resolve()`; `scope_name`
  returns `GLOBAL_SCOPE` when it holds, else `directory.resolve().name`.
- `sed -n '25p' adjagent/agents_file.py` → `GLOBAL_SCOPE = "Global"`;
  `sed -n '12p' adjagent/definitions/harness_agents_file.py` → `body=f"""# @!agf-scope-name!@ info and directives`.
- `PYTHONPATH=. python3 -m adjagent harness mage user-harness-dir` → `.`; the shell's
  `resolve(".")` is the process's working directory.
- `sed -n '13,30p' devtools/scripts/install-agents-file.sh` → the inference loop; `sed -n '56p'
  justfile` → the `[doc]` string naming `[harness] (claude, opencode)`.
- Design "Required fixes", both bullets (`:484-512`).

**Actions:**
1. `_in_user_dir` resolves a relative value against the destination:
   `(directory / Path(harness.user_harness_dir).expanduser()).resolve() == directory.resolve()`.
   An absolute value (`~/.claude`, `~/.config/opencode`) behaves exactly as today, because joining a
   directory with an absolute path yields the absolute path.
2. **Do not edit `scope_name`.** `_in_user_dir` returns True for mage in every directory, so its
   existing first branch applies: the installed `CLAUDE.md` and
   `rendered/<slug>/harness/mage/CLAUDE.md` both open `# Global info and directives`. A scope named
   for the directory would be a `scope_name` change and a design line, not a coder's pick.
3. `install-agents-file.sh`: skip a harness whose `user-harness-dir` is relative (not `~`-rooted and
   not absolute) when inferring — a relative value names no directory and is never an inference
   basis; with no harness named and no match, refuse and name the harnesses it can infer.
4. `justfile:56`'s `[doc]` string states the same: `[harness] (claude, opencode — the two whose
   user-harness-dir is absolute) is inferred when <dir> is that harness's user directory and required
   otherwise; a relative user-harness-dir, as mage's is, is never an inference basis`.
5. Add assertion 12 beside the existing agents-file cases: `install_agents_file(target, MAGE,
   uncommitted=())` writes `target/CLAUDE.md` and leaves `target/AGENTS.md` absent; and
   `install_agents_file(target, CLAUDE, uncommitted=())` where `target` is no user directory writes
   `target/AGENTS.md` plus `target/CLAUDE.md` holding only `@AGENTS.md`. It lands here, not with the
   rest of the tests, because otherwise the fix is revertible with the suite green.

**Done-line:** `just test adjagent` reports no failure; `just test-changed` green. Manual check on
`rendered/mage/harness/mage/CLAUDE.md` after a mage render: first line `# Global info and
directives`.

### Package 6 — the remaining mage tests (design step 7)

**Status:** done — `437 passed`; `test-changed` green.

**Scope:** `tests/test_adjagent_install.py` (the mage install, ownership and `omits` cases);
`tests/test_adjagent.py` (render-tree and manifest cases); optionally a new
`tests/test_adjagent_mage.py` (**judgment**, design `:405`). Each test module that needs a mage
render defines its own `_MAGE_RENDER` at module scope, as each already does for claude; do not import
test constants across modules. Add `from adjagent.harnesses.mage import HARNESS as MAGE` beside that
module's claude/opencode imports.

**Facts to act on:**
- Assertions 1, 2, 3, 5, 6, 9 and 10 at design `:341-390`; assertions 4, 7, 8 landed in Package 4 and
  12 in Package 5.
- `sed -n '230p' tests/test_adjagent_install.py` → `_CLAUDE_RENDER = Render(harness=CLAUDE, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))`.
- The "Not added" paragraph (design `:352-355`): mage is **not** appended to
  `test_adjagent.py:324-327` `_HARNESS_RENDERS` or to the claude/opencode parametrisations at
  `test_adjagent.py:287`, `:305`, `test_adjagent_install.py:65`, `:784`.
- `:1324-1330` passes with mage contributing no sources.

**Actions:**
1. In each test module that needs it, add `_MAGE_RENDER = Render(harness=MAGE, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))` beside that module's `_CLAUDE_RENDER`, and the `MAGE` import. `tests/test_adjagent.py` and `tests/test_adjagent_install.py` each carry their own, as they already do for claude.
2. Implement assertions 1, 2, 3, 5, 6, 9 and 10 exactly as design §7 states, against `_MAGE_RENDER`.
3. Do not append mage to `_HARNESS_RENDERS` or to any claude/opencode parametrisation.
4. Optionally split the mage cases into `tests/test_adjagent_mage.py` (**judgment**: file split only).

**Done-line:** `just test adjagent` reports no failure; `just test-changed` green.

### Package 7 — contract documents (design step 8)

**Status:** done — documents applied; `test-changed` 437 passed; `render-diff` no pairs.

**Scope:** `SPEC.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `README.md` — the design's §6 tables
(`:252-335`) are the whole document change; no document edit a row does not name. The one source file
here is `adjagent/version.py`'s docstring (`:3-4`), whose version-rule sentence the change makes
false; `adjagent/vocabulary.py:54` is made in Package 2.

**Facts to act on:**
- The §6 tables: SPEC `:254-274`, ARCHITECTURE `:276-299`, CONVENTIONS `:301-316`, README `:318-335`.
- `sed -n '58,59p' CONVENTIONS.md` → the `NOT_BY_DEFAULT` bullet opens at `:58`; `sed -n '81,84p'` →
  the recogniser bullet; `sed -n '131,134p'` → the version bullet; `sed -n '167,168p'` → the review
  roster sentence.
- The ARCHITECTURE lines the three-harness change touches: `:13`, `:82-88`, `:84`, `:99-119`,
  `:126-141`, `:143-145`, `:278`, `:285`, `:291`, `:294-308`, `:387-391`, `:408-424`.
- `git log --oneline -3` → the three commits since `v0.12.1` (version source and `just tag`; recipe
  bodies moved to `devtools/scripts/*.sh`; the kb-reference rename); the documents already reflect
  them.

**Actions:**
1. `SPEC.md`: the seventeen rows at design `:258-274`, including the two agents-file rows (the project-name sentence at 139-141 and the Harness Agents File sentence at 307-314), the include-line exception at 42-43, and the two base-install rows at 34 and 50.
2. `ARCHITECTURE.md`: the sixteen rows at design `:280-295`, with the `vocabulary.py:54` note at
   `:296-299`, including the four three-harness rows —
   `:84` ("Under both harnesses …" → "Under every harness … relative to the directory that harness's
   settings file is resolved against — the project root, or, under mage, ROOT"), `:278` ("on both
   harnesses" → "on every harness"), `:285` ("the two fields both harnesses read" → "the two fields
   every harness reads"), `:291` ("because both harnesses read the same two fields" → "because every
   harness reads the same two fields") — and `:294-308`'s field list and `:308`'s count.
3. `CONVENTIONS.md`: the four rows at design `:305-308` — `NOT_BY_DEFAULT` (`:58-72`), the recogniser
   (`:81-84`), the version (`:131-134`), and the review roster (`:167-168`): the reviewers become
   "an architect, a coder and a tech-writer", and the added sentence states what the tech-writer
   reviews. The plan's review block below is the three-seat one this row creates.
4. `README.md`: the install-layout, harness-list and plugin-install sentences at design `:318-335`,
   and the agents-file paragraph at `:159-169` (inference is absolute-only, so mage is always named;
   mage writes `CLAUDE.md` directly with no `AGENTS.md` redirect). The plugin install command is
   `just install <plugin-dir> --subdir= --harness=mage`; the design's earlier order forwards
   `--subdir=` to argparse and fails.
5. `adjagent/version.py:3-4`: "No rendered file carries it, so bumping it changes no output" →
   "No rendered file carries it except mage's `.claude-plugin/plugin.json`, whose purpose is to; no
   reference slot is rendered for mage, so a bump still churns nothing under `rendered/`."

**Done-line:** `just test-changed` selects the adjagent surface (`adjagent/version.py` is a source
file) and exits 0 with `437 passed`; `just render-diff` reports no pairs.

### Package 8 — plugin output shape: CLAUDE.md at ROOT, no Makefile

**Status:** done — `437 passed`; `rendered/mage` has `CLAUDE.md`, `.mcp.json`, no `Makefile`, no `harness/`; documents applied.

**Scope:** `adjagent/install.py` (skip the runner include line when `ctx.harness.project_harness_dir`
is `.`); `devtools/scripts/_render-slot.sh` and the slot comment in `render.sh`; a mage install
assertion in `tests/test_adjagent_install.py`; the §6 rows in `SPEC.md`, `ARCHITECTURE.md` and
`README.md`.

**Facts to act on:**
- `grep -n "install_kb_include_line" adjagent/install.py` → the call at `:1190` inside
  `if kb_included:`, after `mcp_merge`; the function creates a `Makefile` when the project has no
  runner file (`:999-1007`).
- `sed -n '1,35p' devtools/scripts/_render-slot.sh` → it always `mkdir -p "${out}/harness/${harness}"`
  and writes the agents file to `out/harness/<name>/<agents-file>`.
- `devtools/scripts/_harness-value.sh mage project-harness-dir` → `.`.

**Actions:**
1. In `install()`'s `if kb_included:` block, write the include line only when
   `ctx.harness.project_harness_dir != "."`; `mcp_merge` stays unconditional.
2. `_render-slot.sh`: read the harness's `project-harness-dir`; when it is `.`, write the agents file
   at `out/<agents-file>`; otherwise keep `out/harness/<name>/<agents-file>`. The `.` branch creates
   `out` itself (`mkdir -p "${out}"`): `rm -rf` removed it and `RENDER-FLAGS.txt` is written into it.
   The other branch creates `out/harness/<name>/`. `render-agents-file` (`adjagent/cli.py:107`)
   writes with `Path.write_text` and creates no parent, so the slot script pre-creates the directory.
   Update the slot comments in `render.sh` and `_render-slot.sh`.
3. Add to the mage kb-install test: no `Makefile` at ROOT or the project.
4. Documents: the design's §6 rows — SPEC `:42-43`, ARCHITECTURE `:214-221`, README `:86`/`:403` and
   the slot agents-file sentence.

**Done-line:** `just test adjagent` reports no failure; `just render mage --harness=mage` writes
`rendered/mage/CLAUDE.md` and `.mcp.json`, no `rendered/mage/Makefile`, no `rendered/mage/harness/`;
`just render-diff` reports no pairs.

### Package 9 — a mage install always includes the kb set

**Status:** done — `438 passed`; a plain mage install with a dist writes `.mcp.json` and the kbase tree; without one it refuses; documents applied.

**Scope:** `adjagent/install.py` (`kb_included`); `tests/test_adjagent_install.py` (the two mage
base-install cases); `SPEC.md`, `ARCHITECTURE.md`, `README.md` (the design's added rows).

**Facts to act on:**
- `sed -n '1094,1097p' adjagent/install.py` → `kb_included = with_kb or any(...)`; add
  `or ctx.harness.project_harness_dir == "."`.
- `_kbase_source` (`:340-367`) refuses when no `--kbase-dist` and no installed executable; that
  refusal is a plain mage install's outcome.
- `tests/test_adjagent_install.py:855` (`test_a_mage_base_install_writes_no_mcp_entry_and_no_skills`)
  asserts the opposite; `:868` (the base-over-kb case) still holds because the installed executable
  is the source.

**Actions:**
1. `kb_included` is true for `ctx.harness.project_harness_dir == "."`, regardless of `--with-kb`;
   `_kbase_source` and the rest follow.
2. Replace the mage base-install case with two: a plain mage install with a `kbase_dist` and no
   `with_kb` writes `.mcp.json` and `skills/kbase/kb-tools/kbase`; the same without a dist and
   without an installed executable refuses, naming `--kbase-dist`.
3. Documents: the design's added rows — SPEC `:34`, `:50`; ARCHITECTURE `:55-66`, `:73-100`,
   `:464`; README `:51`, `:271`, `:320`.

**Done-line:** `just test adjagent` reports no failure; a plain mage install with a dist writes
`.mcp.json` and the kbase tree; without one it refuses naming `--kbase-dist`; `just render-diff` no
pairs.

### Package 10 — the plugin's `adjagent` subdirectory and its agents file

**Status:** done — `438 passed`; render slot clean; `install.sh` writes `ROOT/CLAUDE.md` for a subdir plugin; documents applied.

**Scope:** `adjagent/harnesses/mage.py` (`project_harness_dir="adjagent"`, `user_harness_dir="."`);
`adjagent/install.py` (the plugin marker); `devtools/scripts/_render-slot.sh`;
`devtools/scripts/install.sh`; `tests/test_adjagent_install.py`; `SPEC.md`, `ARCHITECTURE.md`,
`README.md`.

**Facts to act on:**
- `grep -n "project_harness_dir\|user_harness_dir" adjagent/harnesses/mage.py` → the working tree has
  `"adjagent"` for both; `user_harness_dir` must be `"."` (the destination is the harness's own
  directory).
- `grep -n "project_harness_dir ==\|project_harness_dir !=" adjagent/install.py` → the Package 8/9
  markers; replace them with `user_harness_dir`.
- `devtools/scripts/_render-slot.sh` and `install.sh` as design step 9 states.

**Actions:**
1. `mage.py`: `project_harness_dir="adjagent"`, `user_harness_dir="."`.
2. `install.py`: the always-KB and no-include-line conditions use `user_harness_dir == "."`.
3. `install.sh`: after the install verb, if the harness's user-harness-dir is `.`, call
   `install-agents-file "${harness}" "${root}"`, so `ROOT/<agents-file>` is written.
4. `_render-slot.sh`: the root-agents-file condition uses user-harness-dir.
5. Keep the Python tests' no-Makefile and always-KB assertions; assertion 12 already pins
   `install_agents_file` writing `CLAUDE.md` for a mage directory.
6. Documents: the design's rows — SPEC `:68-70`, README plugin-install and agents-file paragraphs.

**Done-line:** `just test adjagent`; `just render mage --harness=mage` writes
`rendered/mage/CLAUDE.md` beside `.mcp.json`, no `Makefile`, no `harness/`; a scratch
`just install-with-kb --harness=mage <tmp>/Plugins` writes
`<tmp>/Plugins/adjagent/{CLAUDE.md,.mcp.json,agents,skills}` with no `<tmp>/Plugins/Makefile`;
`just render-diff` no pairs.

### Final gate — "Re-run before the change is called done"

**Status:** done — `438 passed`; `render-diff` no pairs; scratch install into `<parent>/Plugins` writes `Plugins/adjagent/{CLAUDE.md,.mcp.json,agents,skills}`, no parent `Makefile`; slot `rendered/mage` has `CLAUDE.md` at root, no `harness/`; sweep candidates answered (mage's copies intended; the rest pre-date the change).

**Actions:** run all four, in order:
1. `just test-changed`
2. `just sweep-python` — read the candidates and answer them (the copied constants are the intended
   verdict; say so in the commit message).
3. `just render mage --harness=mage` — inspect `rendered/mage` by hand (`find rendered/mage -maxdepth 2`),
   including `CLAUDE.md`'s `# Global info and directives` first line at ROOT beside `.mcp.json`, the
   absence of `harness/mage/`, of `Makefile`, and of `commands/imgread.md`.
4. `just render` then `just render-diff` — **must report nothing**: the reference slots are
   `reference`, `reference-opencode`, `reference-gemma` and no existing harness's output has changed.

**Done-line:** all four commands green; `just render-diff` reports no pairs.

---

## Acceptance criteria (design §7, twelve assertions)

1. **The plugin tree for a mage render.** `write_renders(tmp, render_all(MAGE_RENDER))` yields
   `agents/python-coder.md` and `skills/kbase/SKILL.md` at the tree root (no extra nesting), plus
   `.claude-plugin/plugin.json`, and no `commands/imgread.md` — claude's slot holds it, and it is the
   only command, so mage has no `commands/` directory.
2. **The manifest.** `json.loads(...)` equals exactly
   `{"name": "adjagent", "version": VERSION, "description": "Adjagent skills, agents, and MCP tools"}`
   — the exact dict pins the three keys; the version compared to `adjagent.version.VERSION`, never a literal.
3. **The manifest is the only version carrier.** For every other path `render_all(MAGE_RENDER)`
   produces, `VERSION not in text`.
4. **`.mcp.json` relative to its own directory.** A kb install into `<project>/plugins/adjagent` writes
   `<root>/.mcp.json`, which parses to
   `{"mcpServers": {"kbase": {"command": "skills/kbase/kb-tools/kbase", "args": ["mcp"]}}}`; assert
   `<project>/.mcp.json` is absent and that `(root / command)` is the installed executable. The exact
   literal dict pins the relative command; a separate `is_absolute` assertion could not fail
   independently.
5. **No absolute path in mage's output.** For every file in the installed tree, `str(root.resolve()) not in`
   its text; the `"~/"` check applies to the files mage's own configuration writes
   (`.claude-plugin/plugin.json`, `.mcp.json`), since shipped definition prose may mention it.
6. **No hook, no settings edit.** No `hooks/` under ROOT; no `.claude/settings.json` at the project
   root or ROOT after a mage install (mirrors the opencode case at `test_adjagent_install.py:1495-1499`).
7. **The same on a kb install:** kb definitions and `skills/kbase/kb-tools/kbase` present, the
   manifest still exactly three keys with `VERSION`, `.mcp.json` at `<root>/.mcp.json` with
   `<project>/.mcp.json` absent.
8. **A fresh base install writes no `.mcp.json` and no `skills/`** — and a base install over a kb
   ROOT leaves `.mcp.json` where it stands (the claude behaviour, locked so it stays deliberate).
9. **Ownership.** A second mage install passes over its own manifest, byte-identical; an operator's
   `.claude-plugin/plugin.json` without the marker (`{"name": "other"}`) refuses with nothing
   written, naming the path; `--verbose` lists the manifest as written.
10. **`omits` names real definitions.** For every harness from `load("adjagent.harnesses", "HARNESS")`,
    every name in `harness.omits` is a discovered definition name — a typo would otherwise ship the
    file silently.
11. **Existing pins that move:** `tests/test_adjagent_install.py:359` (done in Package 1). Nothing
    else moves: `:354-360`'s resources claim still holds, `:1324-1330` passes with mage contributing
    no sources, and the settings-file pins at `:430-437`, `:758`, `:771-779` are the guard that the
    refactor changed no existing harness's output.
12. **The agents file in its own directory.** `install_agents_file(target, MAGE, uncommitted=())`
    writes `target/CLAUDE.md` and leaves `target/AGENTS.md` absent; and
    `install_agents_file(target, CLAUDE, uncommitted=())` where `target` is no user directory writes
    `target/AGENTS.md` plus `target/CLAUDE.md` holding only `@AGENTS.md`.

**Not added:** mage is **not** appended to `test_adjagent.py:324-327` `_HARNESS_RENDERS` or to the
claude/opencode parametrisations at `test_adjagent.py:287`, `:305`, `test_adjagent_install.py:65`,
`:784`. Those cases pin a frontmatter shape per harness; mage's is an assumption, and a mage case
belongs beside the assumptions it tests, not inside another harness's pin.

---

## Limits (design "Chosen not to specify", "Accepted frictions" and "Required fixes")

### Chosen not to specify (`MAGE_HARNESS_DESIGN.md:460-471`)

1. The partition expression and closure style inside `_refuse_foreign_targets` — fixed behaviour, free
   shape.
2. Whether the mage tests live in the existing install test file or a new one.
3. A collision check between a harness file's path and a definition's output path: the two roots
   (`.claude-plugin/` vs `agents|commands|skills`) cannot meet by construction, and no authoring path
   reaches it. Revisit only if a harness file is ever authored under a surface.
4. A runtime check that `Harness.omits` names a real definition: the harness dataclass must not import
   the definitions package, so it is a test (assertion 10), which is also where a typo is caught.
5. Whether a future mage-specific frontmatter needs the `Render` in `HarnessFile.text`; the field's
   type is the one line that changes if so.

### Accepted frictions (`MAGE_HARNESS_DESIGN.md:473-482`)

1. **A staging ROOT.** `install.sh` derives the project root from the directory it names, so
   `just install <staging> --harness=mage --subdir=` makes the plugin root its own project root: a kb
   install then creates a `Makefile` and merges `.mcp.json` inside the plugin tree, and
   `install_kb_include_line` has nothing meaningful to include from. The remedy already exists and
   needs no code: an operator-supplied `--project-root=<project>` reaches the verb after the recipe's
   own (argparse takes the last), or the plugin is installed inside the consuming project with
   `--subdir=<rel>`, which is the shape a project wanting the `kb-` targets should use.
2. **`imgread` under mage.** A session loses the clipboard-image command; there is no mage-side
   substitute in this change.

### Required fixes (`MAGE_HARNESS_DESIGN.md:484-512`)

1. **`install-agents-file` and the relative user directory.** `_in_user_dir` must resolve a relative
   `user_harness_dir` against the destination. This is a defect fixed in this change. Two outcomes
   are fixed, not left to the coder: `scope_name`'s `Global` branch applies untouched, so the
   installed file and the rendered harness file open `# Global info and directives`; and the shell's
   predicate in `install-agents-file.sh:13-30` agrees with it — a relative `user-harness-dir` is never
   an inference basis, and an unnamed harness with no match is refused with the inferable harnesses
   named.
2. **The shell's inference is part of the same fix.** `just install-agents-file <dir>` run from inside
   `<dir>` selected mage silently before this change and wrote a generated `CLAUDE.md` where the
   script's own comment promises a project root takes an explicit harness. Package 5 lands both
   halves and `justfile:56`'s `[doc]` string.

---

## Recommended seat count and model, per package

Per `CONVENTIONS.md:175-177`, a dispatch names its seats and model before the tool call; more than one
seat at the family's highest tier waits for a go that names the count. One seat per package, in the
order above.

| Package | Seats | Model tier | Rationale |
|---|---|---|---|
| 1 — the `:359` pin | 1 coder | high | One assertion and one docstring sentence; the baseline every later package reads. |
| 2 — `harness.py` + three harness modules | 1 coder | highest | A new dataclass, an enum, a required field and a total keyword rename across seven files; the type base for every later package. Cannot be split. |
| 3 — `mage.py` + `render.py` | 1 coder | highest | The manifest's serialization and marker are one decision, and `harness_renders` is the seam three writers go through. Cannot be split. |
| 4 — `install.py` | 1 coder | highest | The widest change: `mcp_base` through four functions and two call sites, `_is_our_harness_file`, the third target class, the partition judgment. |
| 5 — the agents file, code and shell | 1 coder | high | Two small predicates and a refusal message, plus the regression pin that makes the fix non-revertible. |
| 6 — the remaining mage tests | 1 coder | high | Assertions 1-3, 5, 6, 9, 10 against `_MAGE_RENDER`; judgment only on the file split. |
| 7 — contract documents | 1 tech-writer | high | The §6 tables are mechanical; the review-roster row is wording, which is the seat the roster change names. |
| 8 — plugin output shape | 1 coder + 1 tech-writer | high | Two predicates, a slot path and a test; the documents are the §6 rows. |
| 9 — mage always includes kb | 1 coder + 1 tech-writer | high | One boolean expression, two tests and the base-install document rows. |
| 10 — `adjagent` subdirectory and agents file | 1 coder + 1 tech-writer | high | A harness value, two shell steps and the plugin-install rows. |
| Final gate | 1 coder | high | Run the four commands and inspect `rendered/mage`. |

**Total recommended seats:** 14. Packages 2 and 3 each carry two design steps and are dispatched as
one seat; Packages 8-10 are follow-ons. Ten packages plus the gate. Nothing runs in parallel: every
done-line reads the suite the package before it left.

---

## Post-sprint review

Runs after the final gate passes. It is not optional and is not a rehash of the implementation.

### Seats and models

- **Architect — `highest`** (`CONVENTIONS.md:167-168` as this change amends it, design `:285`).
- **Coder — `highest`.**
- **Tech-writer — `high`.**

Three seats, because Package 7 lands the roster change: the review this plan describes is the first
one under it. Pre-task reading list is `THESIS.md`, `SPEC.md`, `ARCHITECTURE.md` and `CONVENTIONS.md`
(`CONVENTIONS.md:167-168`). They do **not** get this plan document; their job is to review the changes
against standards and suitability for purpose. The review brief includes the tests
(`CONVENTIONS.md:171`). The tech-writer reviews what the change ships as documentation — the contract
documents, README, and `MAGE_HARNESS_DESIGN.md` as the normative page — for accuracy against the code
and for whether a reader without the work thread can act on it.

### Burn-down

The burndown list is written to **`ACTIVE_PLAN_REVIEW_BURNDOWN.md`** at the repository root. It gets
the same prompt-engineer review and revision pass as any other document containing agent instructions
(`CONVENTIONS.md:172-173`). Each item carries Severity (Critical / Warning / Note), Finding, Location
(file and section/function), and Guidance specific enough for a coder to act without follow-up.

### Remediation

The three seats triage the burndown; the architect revises this plan where a finding needs a choice no
written rule settles, and the coder lands the fixes. Retractions are explicit: each reversed prior
criticism names the withdrawn criticism, the reason, and the correct approach, and has the same
priority as a Critical finding.
