# Install in Python

**Not yet dispatchable: the prompt-engineer review and the architect's revision after it are still
pending.**

This plan serves the ROADMAP.md item "adjagent as an installable package, with two skills that drive
tools". That item's packaging needs every shipped source under `adjagent/`, and the `install` verb as
the one install entry point. The plan is not under way. When it is picked up, it becomes
ACTIVE_PLAN.md (CONVENTIONS.md, Planning and Execution, "The active plan").

## Status

| package | dispatch | rating | seat | state |
|---|---|---|---|---|
| WP5 | WP5.1 | mechanical | `python-coder`, `model: sonnet` | not started |
| WP5 | WP5.2 | expert | `python-coder`, coordinator's model | not started |
| WP5 | WP5.3 | expert | `python-coder`, coordinator's model | not started |
| WP5 | WP5.4 | expert | `tech-writer`, coordinator's model | not started |

- **Landing unit.** WP5 lands as one commit, and no commit lands between its dispatches. The contract
  documents and README follow the code only in WP5.4, and a checkpoint does not land before the
  documents it invalidates are updated.
- **Order.** WP5.1, then WP5.2, then WP5.3, then WP5.4, one at a time. Each one edits files the next
  one reads.

## Preconditions

Run these before WP5.1's dispatch. If any answer differs, stop and report it, and dispatch nothing.

| check | must answer |
|---|---|
| `git status --porcelain --untracked-files=no` | nothing, or only the plan file itself |
| `just test` | passes |
| every row of "Facts acted on" | the answer recorded there |

Record `git rev-parse --short HEAD` as **BASE**. The post-sprint review uses it.

## Rule for every dispatch

Before editing, re-run every fact row the dispatch's brief carries. If a command's output does not
contain the row's quoted answer, stop and report that row, and edit nothing. A quoted answer
shortened with "…" is matched on the text it shows. An answer that says "and nothing else" also
fails when the output holds anything beyond what it quotes.

---

## WP5 — `just install` and `python3 -m adjagent install` are one thing

### Outcome

`just install`, `just install-with-kb` and `python3 -m adjagent install` take the same arguments and
do the same thing.

- The product logic lives in the package: the target, harness detection, ROOT and the project root,
  the plugin harness's agents file, and user-level targets.
- Each install recipe is one line.
- opencode renders without `--model-tier-map`.
- The install reads no file outside `adjagent/`.

### Requirements

- **R1 — target and recipes.** The verb is `python3 -m adjagent install TARGET [flags]`, and TARGET is
  its first non-flag argument.
  - A TARGET that does not exist is refused.
  - **ROOT and the project root:**
    - With `--subdir=DIR` given, ROOT is `<target>/<DIR>` and the project root is the target.
      `--subdir=` installs into the target itself.
    - A target that is itself a harness directory (R2 rule (c)) is installed into directly: ROOT is
      the target, and the project root is the target's parent. Mage is the exception: ROOT is
      `<target>/adjagent` and the project root is the target.
    - A target that is the user's home directory gives ROOT = the selected harness's
      user-harness-dir inside it, and the install is user-level (R3).
    - Any other target gives ROOT = `<target>/<project-harness-dir>`, and the project root is the
      target.
    - Today a `/p/.claude` target installs into `/p/.claude/.claude` (F1, F3). That is a defect, and
      this package fixes it.
  - The project root is resolved in the package, following symlinks as `pwd -P` did.
  - A plugin harness's agents file is written at ROOT when ROOT is not the project root.
  - `install` and `install-with-kb` are one line each. A recipe body of more than three command lines
    stays a script (CONVENTIONS.md, "Long recipe bodies are scripts").
- **R2 — harness detection, in precedence order.**
  - (a) `--harness` always wins.
  - (b) Otherwise, a harness directory present inside the target. In a project target the directories
    looked for are the project-harness-dirs, `.claude/` and `.opencode/`. In a home-directory target
    they are the user-harness-dirs, `.claude/` and `.config/opencode/`. If more than one is present,
    refuse and require `--harness`.
  - (c) Otherwise, the target is itself a harness directory, matched exactly on its trailing path
    elements:
    - `.claude`, `.opencode` and `.config/opencode`, all derived from the harnesses'
      project-harness-dir and user-harness-dir values
    - `Mage/Skills` for mage, which mage's values do not yield, so mage's `Harness` gains a field
      for it
  - (d) Otherwise, refuse, naming `--harness`.
  - No path-substring matching remains: the `*claude*`, `*opencode*` and `*/mage/*` patterns go (F1).
- **R3 — user-level installs.** An install is user-level when ROOT resolves to claude's or opencode's
  user-harness-dir, however the target reached it.
  - A user-level install renders the definitions its type carries, including the kb set when it
    includes kb.
  - It prunes, and removes the legacy trees, as every install does.
  - It writes nothing else: no shipped harness file, no guardrail probe or registration, no kb-tools
    package, no MCP entry, no runner include line and no runner file.
  - `--install-global-agents-file` is the one opt-in. It writes the harness agents file at ROOT
    through the existing agents-file install.
  - On a project install the flag is ignored, without error.
- **R4 — opencode's default tier spec.** opencode gets a default tier spec of `default`, used
  whenever `--model-tier-map` is not given. This is one `Harness` field and one branch in
  `build_render`, with no condition on the family. README's consumer examples and
  `install-agents-here` drop their `--model-tier-map=default`.
- **R5 — `kb-tools/` moves under `adjagent/`.** The install reads nothing outside the package.
  `KB_TOOLS_SOURCE`, the REPO_ROOT-relative source paths and refusal checks, and the docs follow.
  pyproject.toml and the console script are not part of this package.
- **R6 — scripts.**

  | script | outcome | why |
  |---|---|---|
  | `install.sh` | retired | its body moves into the package (R1, R2) |
  | `install-agents-file.sh` | retired | its one piece of logic, inferring the harness from a user directory, moves into the `install-agents-file` verb and shares invariant I4's predicate |
  | `_harness-names.sh` | retired | its one caller is `install-agents-file.sh` (F5). The `harnesses` verb, which only this script calls, goes with it |
  | `_harness-value.sh` | stays | `_render-slot.sh` and `mage-dist.sh` still read harness values from shell (F6) |
  | `_render-slot.sh` | stays; calls the verb | removing and rebuilding a slot, `RENDER-FLAGS.txt`, and where the agents file sits in a slot are repository tooling, not product |
  | `mage-dist.sh` | stays; calls the verb | it is build orchestration: tar, gpg and exit traps |
  | `render-agents-file.sh` | stays unchanged | it is a stable interface that an earlier revision's worktree calls; its name and its two arguments do not change |
  | `render.sh` | stays | its comment on line 6 names `install.sh` and is corrected |

- **R7 — contract and tests.** The SPEC, ARCHITECTURE and CONVENTIONS leaves and README follow the
  change within WP5. Unit tests cover:
  - the detection precedence, home-directory targets included
  - the refusals
  - user-level installs and the flag
  - the opencode default

  Existing install tests keep passing, or are rewritten where they pinned the removed heuristic or
  the removed refusal.

### Invariants

These hold across every dispatch. Each one closes a path to a wrong system.

- **I1 — resolution is one function that writes nothing.** It lives in a new module,
  `adjagent/install_target.py`. It takes the target as given, `--harness` (or None) and `--subdir`
  (or None). It returns the harness name, ROOT and the project root; WP5.3 adds whether ROOT is
  user-level. `cli.py` calls it once, before `build_render`, and passes its result on. `cli.py` holds
  no path logic.
- **I2 — detection reads directory names from `Harness` values.**
  - Rule (b) reads each non-plugin harness's `project_harness_dir`, or, in a home-directory target,
    each absolute `user_harness_dir` with its leading `~/` removed.
  - Rule (c) reads all of those, and mage's new field.
  - A plugin harness, one whose `user_harness_dir` is `.`, contributes only its new field. Its
    `project_harness_dir`, `adjagent`, is the name of the plugin's own directory, and matching it
    would detect a clone of this repository as mage.
  - The module spells no harness directory name: none of `.claude`, `.opencode` or
    `.config/opencode` appears in it.
- **I3 — rule (c) matches the path as given.** It matches on the target's path made absolute without
  following symlinks: `Path.absolute()`, not `resolve()`. Whether a target is the home directory, and
  whether ROOT is user-level, are decided by comparing resolved paths.
- **I4 — one predicate answers "which harness's absolute user-harness-dir is this directory".** It
  serves the `install-agents-file` inference and the user-level decision. It skips a relative value,
  as `install-agents-file.sh:24` does (F7). `agents_file._in_user_dir` stays for naming the scope,
  where mage's `.` means the destination itself (F17). Using `_in_user_dir` for the user-level
  decision would make every directory mage's user directory.
- **I5 — every check runs before the first write** (ARCHITECTURE.md, Install Consumption Model,
  "Install entry"). The checks include:
  - the agents-file install's own checks: uncommitted sources, the marker pair, redirects, symlinks
  - the creation of ROOT: ROOT is created only after every check has passed, so a refused install
    leaves no directory behind, and no leftover `.claude/` or `.opencode/` misleads a later rule (b)

  Today the agents file is checked only after the install has written (F16).

  `uncommitted_sources()` runs only when this install will write the agents file. It reaches the
  install as a parameter, as `install_agents_file` already takes it, so tests inject it. A test that
  drives `main([...])` down that path monkeypatches `adjagent.cli.uncommitted_sources`.
- **I6 — existing callers keep working.** These calls stay valid as the tests make them:
  - `install(root, ctx, verbose=…, with_kb=…, project_root=…)`
  - `install_agents_file(directory, harness, uncommitted=…)`

  New behaviour arrives as keyword parameters with defaults.
- **I7 — a mechanism is retired only after its replacement has done the job.** `install.sh`,
  `install-agents-file.sh` and `_harness-names.sh` are deleted only in the step after `just
  test-changed` passes with every recipe and caller already running the Python verbs.
- **I8 — tests never read the real home directory.** A home-directory or user-level test sets `HOME`
  with `monkeypatch.setenv` to a directory under `tmp_path`.

### Facts acted on

Run these from the adjagent root. The answers were taken at HEAD `d71d9c9`.

| # | fact | command → answer |
|---|---|---|
| F1 | `install.sh` infers the harness from path substrings | `grep -n -E '\*claude\*\|\*opencode\*\|\*/mage/\*' devtools/scripts/install.sh` → `33:            *claude*) harness="claude";;`, `34:            *opencode*) harness="opencode";;`, `35:            */Mage/*\|*/mage/*) harness="mage";;` |
| F2 | When both directories are present, `.opencode` wins without a word | `grep -n 'target}/\.' devtools/scripts/install.sh` → `59:  [[ -d "${target}/.opencode" ]] && harness="opencode" \|\| true`, `60:  [[ -z "${harness}" && -d "${target}/.claude" ]] && harness="claude" \|\| true` |
| F3 | `--subdir` defaults to project-harness-dir whatever the target is; ROOT is created before any check; the plugin agents file is installed after the install has written | `grep -n -E 'project-harness-dir\)\|mkdir -p\|python3 -m\|install-agents-file.sh' devtools/scripts/install.sh` → `77:` "…project-harness-dir)\"", `80:mkdir -p "${root}"`, `83:PYTHONPATH="${PROJECT_ROOT}" python3 -m "${GEN}" install "${root}" --project-root=…`, `92:    "${PROJECT_ROOT}/devtools/scripts/install-agents-file.sh" "${root}" "${harness}"` (`3:` also matches, in a comment) |
| F4 | The verb's positional is ROOT, and the project root is a flag | `grep -n -E '"root", type=Path\|"--project-root"' adjagent/cli.py` → `53:    installing.add_argument("root", type=Path, metavar="ROOT", …`, `59:        "--project-root",` |
| F5 | Only `_harness-names.sh` calls the `harnesses` verb, and only `install-agents-file.sh` calls `_harness-names.sh` | `git grep -n -E 'harnesses$' -- devtools justfile` → `devtools/scripts/_harness-names.sh:7:PYTHONPATH="${PROJECT_ROOT}" python3 -m "${GEN}" harnesses` and nothing else; `git grep -n '_harness-names' -- devtools justfile` → `_harness-names.sh:2:` (its own comment), `install-agents-file.sh:20:`, `justfile:89:_harness-names:`, `justfile:90:` |
| F6 | Who calls `_harness-value.sh` | `git grep -n '_harness-value.sh' -- devtools justfile` → `_render-slot.sh:23:`, `:24:`, `:25:`; `install-agents-file.sh:21:`; `install.sh:77:`, `:89:`; `mage-dist.sh:18:`, `:19:`; `justfile:86:` |
| F7 | The agents-file inference skips a relative user-harness-dir | `grep -n '== /\*' devtools/scripts/install-agents-file.sh` → `24:        [[ "${user_dir}" == /* ]] \|\| continue` |
| F8 | A recipe parameter left at its default still arrives as a positional | `grep -n '^test-changed' justfile` → `170:test-changed base="":`; `grep -n -E '^set -euo\|^base=' devtools/scripts/test-changed.sh` → `16:set -euo pipefail`, `23:base="${1}"` (under `-u`, so `$1` is set when the default is used) |
| F9 | The harness directory values | `grep -n -E 'project_harness_dir=\|user_harness_dir=\|^_PROJECT_HARNESS_DIR' adjagent/harnesses/*.py` → `claude.py:98:` `".claude"`, `claude.py:100:` `"~/.claude"`, `mage.py:63:` `"adjagent"`, `mage.py:66:` `"."`, `opencode.py:8:_PROJECT_HARNESS_DIR = ".opencode"`, `opencode.py:35:`, `opencode.py:37:` `"~/.config/opencode"` |
| F10 | Mage's skills directory | `grep -n 'Mage/Skills' PROJECT_DOCS/SPEC/mage-plugin-distribution.md` → `20:it into \`~/Mage/Skills/\`; …` |
| F11 | `build_render` takes the family's tiers when no spec is given | `grep -n -E 'if tier_spec is None\|tier_map = dict\(loaded.tiers\)' adjagent/context.py` → `139:    if tier_spec is None:`, `140:        tier_map = dict(loaded.tiers)` |
| F12 | A test pins opencode's refusal without a tier map; claude with gemma-4 refuses the same way | `grep -n 'def test_build_render_refuses_a_model_outside' tests/test_adjagent.py` → `156:`; `PYTHONPATH=. python3 -I -c 'import sys; sys.path.insert(0, "."); from adjagent.context import build_render; build_render(harness="claude", family="gemma-4", tier_spec=None, alias_spec=None)'` → raises `InputError`, beginning "harness 'claude' does not accept model 'gemma-4-31B-it' at tier highest, supplied by the family 'gemma-4' tiers (--family) — …" |
| F13 | The install's source anchors | `grep -n -E '^REPO_ROOT\|^HARNESS_RESOURCES_SOURCE\|^KB_TOOLS_SOURCE\|resolved == REPO_ROOT\|if project == REPO_ROOT\|origin=source.relative_to' adjagent/install.py` → `26:REPO_ROOT = Path(__file__).resolve().parent.parent`, `39:HARNESS_RESOURCES_SOURCE = "adjagent/harnesses/resources"`, `50:KB_TOOLS_SOURCE = "kb-tools"`, `190:` (the root refusal), `929:    if project == REPO_ROOT:`, `1073:` "data = stamped(data, origin=source.relative_to(REPO_ROOT).as_posix())" |
| F14 | What `kb-tools/` holds | `git ls-files kb-tools` → `kb-tools/runner-snippets/kb.just`, `kb-tools/runner-snippets/kb.mk` and nothing else |
| F15 | Tests that name the source anchors | `grep -n REPO_ROOT tests/test_adjagent_install.py` → `35:`, `193:`, `194:`, `302:`, `312:`, `350:`, `362:`, `436:`, `1160:`–`1163:`, `1168:`, `1196:`, `1232:`, `1355:`, `1374:`; `grep -n -E 'INSTALLED! from kb-tools' tests/test_adjagent_install.py` → `438:`, `440:`, `1233:`; `grep -n -E 'HARNESS_RESOURCES_SOURCE, REPO_ROOT\|^_RESOURCES' tests/test_guardrail.py` → `30:`, `32:_RESOURCES = REPO_ROOT / HARNESS_RESOURCES_SOURCE` |
| F16 | The agents-file install refuses on uncommitted sources inside its own call, and `install.sh` makes that call after the install has written | `grep -n 'if uncommitted:' adjagent/agents_file.py` → `122:`; F3's lines `83:` and `92:` |
| F17 | `_in_user_dir` reads a relative user directory against the destination | `grep -n 'return (directory / Path' adjagent/agents_file.py` → `64:    return (directory / Path(harness.user_harness_dir).expanduser()).resolve() == directory.resolve()` |
| F18 | The recipes this package rewrites | `grep -n -E '^install\|^_harness-names\|install\.sh\|install-agents-file\.sh' justfile` → `30:install target *args:`, `31:` (runs `install.sh "$@"`), `34:install-with-kb target *args:`, `35:` (runs `install.sh "$@" --with-kb`), `38:install-agents-file dir harness="":`, `39:`, `89:_harness-names:`, `176:install-agents-here:`, `177:`, `178:` (the opencode line, with `--model-tier-map=default`) |
| F19 | Script lines that call `install.sh`, and a value `_render-slot.sh` reads but never uses | `git grep -n 'install.sh' -- devtools/scripts/_render-slot.sh devtools/scripts/mage-dist.sh devtools/scripts/render.sh` → `_render-slot.sh:41:`, `mage-dist.sh:31:` (comment), `mage-dist.sh:35:`, `render.sh:6:` (comment); `grep -c project_harness_dir devtools/scripts/_render-slot.sh` → `1` (the assignment on line 24) |
| F20 | The contract already contradicts itself on who writes the agents file | `grep -n 'never installs it' PROJECT_DOCS/SPEC/harness-agents-file.md` → `5:` "…; \`install\` never installs it."; `grep -n 'writes it too' README.md` → `231:` "\`just install <plugins-parent> --harness=mage\` writes it too, …" |

### WP5.1 — mechanical (`python-coder`, `model: sonnet`)

**Brief:** §Rule for every dispatch, WP5 §Outcome, R4, R5, invariant I6, fact rows F11–F15, and this
section.

**Outcome:** `kb-tools/` is `adjagent/kb-tools/`, and every source the install copies is anchored on
the package directory. opencode renders without `--model-tier-map`.

**Scope:**

- `kb-tools/`, which moves to `adjagent/kb-tools/`
- `adjagent/install.py`: its constants and source paths only
- `adjagent/harness.py`, `adjagent/harnesses/opencode.py`, `adjagent/context.py` (`build_render`)
- `tests/test_adjagent_install.py`, `tests/test_guardrail.py`, `tests/test_adjagent.py`

**First, record the pre-package render footprint.** Run these before any edit:

1. `just render latest`, then `just render-diff`
2. `just render latest-opencode --harness=opencode --model-tier-map=all=inherit`, then
   `just render-diff reference-opencode latest-opencode`

**Edits:**

1. `git mv kb-tools adjagent/kb-tools`.
2. `adjagent/install.py`:
   - Line 26 becomes `PACKAGE_ROOT = Path(__file__).resolve().parent`, followed by
     `REPO_ROOT = PACKAGE_ROOT.parent`.
   - `HARNESS_RESOURCES_SOURCE` (line 39) becomes `"harnesses/resources"`. It and `KB_TOOLS_SOURCE`
     (line 50, value unchanged) are now relative to `PACKAGE_ROOT`.
   - Every source-tree join changes from `REPO_ROOT / …` to `PACKAGE_ROOT / …`. The joins are in
     `package_copies`, `harness_resource_copies`, `_refuse_root`'s `sources` list and `install`'s
     `script =` line.
   - Line 1073's origin becomes `source.relative_to(PACKAGE_ROOT.parent)`, so a banner reads
     `from adjagent/kb-tools/runner-snippets/kb.just`.
   - `resolved == REPO_ROOT` (line 190) and `project == REPO_ROOT` (line 929) stay.
   - Comments and docstrings that place a source "in this repository" now say "in this package",
     beginning with `SHIPPED_PACKAGES`' comment (line 27) and the `KB_TOOLS_PACKAGE` comment (line 47).
3. `adjagent/harness.py`: add one field after `omits`, as
   `default_tier_spec: str | None = None  # the --model-tier-map value used when none is given; None: the family's tiers`.
   `adjagent/harnesses/opencode.py`: `default_tier_spec="default",`.
4. `adjagent/context.py`, `build_render`: replace lines 139–142 with exactly this:

   ```python
       spec = loaded_harness.default_tier_spec if tier_spec is None else tier_spec
       if spec is None:
           tier_map = dict(loaded.tiers)
       else:
           tier_map = parse_tier_map(_bare_tier_spec_expanded(loaded_harness, spec), flag=TIER_MAP_FLAG)
   ```

   The supplier block below it is unchanged. The docstring gains this sentence: "With no tier spec
   given, the harness's `default_tier_spec` stands in for one."
5. Tests:
   - `tests/test_guardrail.py:30,32`: import `PACKAGE_ROOT`, and set
     `_RESOURCES = PACKAGE_ROOT / HARNESS_RESOURCES_SOURCE`.
   - `tests/test_adjagent_install.py`: import `PACKAGE_ROOT`. Make these changes:
     - Every `REPO_ROOT / HARNESS_RESOURCES_SOURCE` and every `REPO_ROOT / "kb-tools…"` becomes
       `PACKAGE_ROOT / …`. That covers lines 302, 312, 362, 436, 1168 (its second and third
       parameters), 1232, 1355 and 1374.
     - The banner assertions at lines 438, 440 and 1233 expect `from adjagent/kb-tools/…`.
     - Line 350 patches `adjagent.install.PACKAGE_ROOT` with the same `tmp_path / "repo"`.
     - The test at line 1196 builds its package at `repo / "adjagent" / "probe_pkg"`, patches
       `adjagent.install.PACKAGE_ROOT` to `repo / "adjagent"`, and expects
       `from adjagent/probe_pkg/tool.py`.
     - Lines 193–194, 1160–1163 and line 1168's first parameter keep `REPO_ROOT`.
   - `tests/test_adjagent.py:156`: the test keeps its name. It calls
     `build_render(harness="claude", family="gemma-4", tier_spec=None, alias_spec=None)` and asserts
     two strings in the message: `"model 'gemma-4-31B-it' at tier highest"` and `"--family"`.
   - Add one test beside `test_opencode_reads_a_bare_tier_spec_as_the_whole_map`:
     `build_render(harness="opencode", family="claude", tier_spec=None, alias_spec=None)` gives a tier
     map of `default` for every tier, and `model("medium") == ""`.

**Done-line (WP5.1):**

- `just test-changed` passes.
- `just sweep-python` runs. Its candidate list is read, and every candidate pair touching a changed
  file is reported with a verdict: one idea, or not.
- `just render latest`, then `just render-diff`: no pair beyond the footprint.
- `just render latest-opencode --harness=opencode`, with no tier map, exits 0. Before this package
  it was refused (F12). Then `just render-diff reference-opencode latest-opencode`: beyond the
  footprint, exactly one pair, `RENDER-FLAGS.txt`.

**Return:**

- the done-line results
- both pre-package `render-diff` outputs, verbatim. Later dispatches compare against them.
- `git ls-files adjagent/kb-tools`, and the exit status of `test -e kb-tools`

### WP5.2 — expert (`python-coder`, coordinator's model)

**Brief:** §Rule for every dispatch, WP5 in full except WP5.1's and WP5.3's sections, the
render-diff outputs WP5.1 returned, and this section.

**Outcome:** the install verb resolves its own target, harness, ROOT and project root for project
targets and harness-directory targets, and writes a plugin harness's agents file.
`install-agents-file` infers its own harness. Every recipe and script that reached the install
through `install.sh` runs the verb, and the three retired scripts are gone. Home-directory targets and
user-level installs are WP5.3's.

**Scope:**

- new: `adjagent/install_target.py`
- `adjagent/cli.py`
- `adjagent/install.py`: `_refuse_root`, the creation of ROOT, and the agents-file step
- `adjagent/agents_file.py`
- `adjagent/harness.py` and `adjagent/harnesses/mage.py`: the field rule (c) needs
- `adjagent/__init__.py`: the module list and the usage lines
- `justfile`: lines 29–39, 88–90 and 173–178
- `devtools/scripts/`: delete `install.sh`, `install-agents-file.sh` and `_harness-names.sh`; edit
  `_render-slot.sh`, `mage-dist.sh` and `render.sh`
- `tests/test_adjagent_install.py`, and a new `tests/test_install_target.py` if the resolver's tests
  read better apart

**Resolution (R1, R2)** is I1's function.

1. A target that is not an existing directory is refused with nothing written.
2. The harness is chosen by R2 (a) to (d), using I2 and I3, with rule (b) looking for
   project-harness-dirs.
   - When rule (b) finds two directories, the refusal names both and says to pass `--harness`.
   - Rule (d)'s refusal names `--harness` and the harness names.
3. ROOT and the project root follow R1:
   - With `--subdir` given, ROOT is `<target>/<subdir>` (`--subdir=` gives the target), and the
     project root is the target.
   - Otherwise, if the target matched rule (c) for the selected non-plugin harness, ROOT is the target
     and the project root is its parent.
   - Otherwise, ROOT is `<target>/<project_harness_dir>`, and the project root is the target.
   - Every project root is resolved.
4. Mage gains a field, `plugin_parent_dir = "Mage/Skills"` (F10). Every other harness leaves it
   empty.

**The install (`adjagent/install.py`):**

- **ROOT may be absent when the install starts.** `_refuse_root` refuses a ROOT that exists and is
  not a directory. The checks read an absent ROOT as empty, and ROOT is created after the last check
  (I5).
- **The plugin agents file.** It is written when the harness's `user_harness_dir` is `.` and ROOT
  does not resolve to the project root. That is the condition at `install.sh:91`.
  - It goes through `agents_file`'s install, whose checks run in `install`'s check phase and whose
    write comes after the renders (I5).
  - Split `agents_file.py` so its checks can be called apart from its write.
    `install_agents_file(directory, harness, uncommitted=…)` keeps its signature and its behaviour
    (I6).

**The CLI (`adjagent/cli.py`):**

- **`install TARGET`.**
  - Add `--subdir` (default None).
  - `--harness` defaults to None for `install` alone. `render` keeps `claude`.
  - Remove `--project-root`.
  - The flow is resolve, then `build_render(harness=<resolved>)`, then `install(...)`.
  - `uncommitted_sources()` is called only when the plugin agents file will be written (I5).
- **`install-agents-file DIR [HARNESS]`.**
  - HARNESS is optional. `""` is the same as absent, because the recipe passes its default (F8).
  - The harness is inferred by I4's predicate. Zero or several matches are refused, naming the
    harnesses inference covers, as `install-agents-file.sh:31` does.
- **The `harnesses` verb is deleted (F5).** `harness NAME KEY` stays.

**Recipes (F18).** Each `[doc]` string states what the recipe now does. The note above
`install-agents-here` loses its sentence about the tier map.

```just
install target *args:
    @PYTHONPATH="{{PROJECT_ROOT}}" python3 -m "{{GEN}}" install "$@"
install-with-kb target *args:
    @PYTHONPATH="{{PROJECT_ROOT}}" python3 -m "{{GEN}}" install "$@" --with-kb
install-agents-file dir harness="":
    @PYTHONPATH="{{PROJECT_ROOT}}" python3 -m "{{GEN}}" install-agents-file "$@"
install-agents-here:
  @PYTHONPATH="{{PROJECT_ROOT}}" python3 -m "{{GEN}}" install "{{PROJECT_ROOT}}" --harness=claude
  @PYTHONPATH="{{PROJECT_ROOT}}" python3 -m "{{GEN}}" install "{{PROJECT_ROOT}}" --harness=opencode
```

The `_harness-names` recipe (lines 88–90) is deleted.

**Scripts (F19):**

- `_render-slot.sh`:
  - Line 41 runs `PYTHONPATH="${PROJECT_ROOT}" python3 -m "${GEN}" install "${out}" --subdir= --with-kb "${args[@]}"`.
  - Line 24 is deleted.
  - The script gains a `GEN` guard: `: "${GEN:?…}"`, whose message holds no apostrophe.
- `mage-dist.sh`:
  - Lines 35–36 run the same verb with `--subdir= --harness=mage`.
  - The comment on line 31 names the install instead of `install.sh`.
- `render.sh:6`: the comment no longer cites `install.sh`.

**Order inside the dispatch (I7):**

1. Build the resolver, the CLI, the install changes and their tests.
2. Rewire every recipe and script caller.
3. Run `just test-changed` and see it pass.
4. Only then, delete `install.sh`, `install-agents-file.sh` and `_harness-names.sh`.
5. Run `just test-changed` again.

**Tests:** each of these must fail before the change. Drive a flag's effect through `main([...])`
(CONVENTIONS.md, "Install parameters ship with their flags").

- **Precedence.**
  - (a) beats a `.opencode/` present in the target.
  - (b) with one directory present.
  - (b) with both present is refused, the refusal names `--harness`, and nothing is written.
  - (c) for `<p>/.claude`: ROOT is `<p>/.claude`, the project root is `<p>`, and no
    `<p>/.claude/.claude` exists.
  - (c) for `…/Mage/Skills`: ROOT is `<target>/adjagent`, and `CLAUDE.md` is written there.
  - (d) is refused.
  - A target whose path holds `claude`, `opencode` or `mage` as a substring, and holds no harness
    directory, is refused under (d). This pins the removal of the substring heuristic.
- **Refusals.**
  - A nonexistent target is refused.
  - A refused install leaves no ROOT behind. A mage install with injected uncommitted sources is
    refused before anything is written, ROOT included.
- **`--subdir=`.** With `--subdir=`, a mage install writes no agents file. This is the slot and
  mage-dist path.
- **`install-agents-file`.**
  - An empty HARNESS infers like an absent one.
  - A project directory with no HARNESS is refused.
- **Existing test.** `test_the_cli_with_kb_flag_installs_…` passes unchanged: its target is a
  `.claude` directory, which is now ROOT.

**Done-line (WP5.2):**

- `just test-changed` passes. `justfile` and `devtools/scripts/` select every surface.
- `just sweep-python` runs. Its candidate list is read, and every candidate pair touching a changed
  file is reported with a verdict: one idea, or not.
- `just render latest`, then `just render-diff`: no pair beyond WP5.1's footprint.
- `just render latest-opencode --harness=opencode`, then
  `just render-diff reference-opencode latest-opencode`: the same result WP5.1 returned.
- `just render mage-wp5 --harness=mage` exits 0.

**Return:**

- the done-line results
- the output of
  `git grep -n -E 'install\.sh|install-agents-file\.sh|_harness-names' -- adjagent devtools justfile tests`,
  which must be empty

### WP5.3 — expert (`python-coder`, coordinator's model)

**Brief:** §Rule for every dispatch, WP5 in full except WP5.1's section, and this section.

**Outcome:** a home-directory target is detected by the user-harness-dirs it holds. Any install whose
ROOT is claude's or opencode's user directory writes the definitions only.
`--install-global-agents-file` adds the agents file there, and does nothing on a project install.

**Scope:**

- `adjagent/install_target.py`: home-directory targets, and whether ROOT is user-level
- `adjagent/cli.py`: the flag
- `adjagent/install.py`: the user-level branch
- tests

**Requirements:**

- **R1 — home-directory targets.** A target that resolves to the home directory (`Path.home()`,
  resolved) is resolved this way:
  - Rule (b) looks inside it for each absolute user-harness-dir (I2).
  - Exactly one present selects that harness. Both present is refused, requiring `--harness`.
  - Without `--subdir`, ROOT is the selected harness's user-harness-dir. This holds whether the
    harness came from rule (b) or from `--harness`.
- **R2 — the user-level decision.** ROOT is user-level when I4's predicate names the selected harness
  for the resolved ROOT, however the target reached it. That includes a `~/.claude` or
  `~/.config/opencode` target matched by rule (c). A user-level install writes what WP5 R3 lists, and
  nothing else.
- **R3 — `--install-global-agents-file`.** The flag applies only on a user-level install. It writes
  the agents file at ROOT through WP5.2's agents-file step, scope `Global`, with the uncommitted
  refusal running before the first write.
- **R4 — the flag on a project install.** On a project install the flag is ignored, with no error and
  no write.

**Tests:** I8 applies to every case. Drive each case through `main([...])`, with
`adjagent.cli.uncommitted_sources` patched where the agents file is written.

- **Home-directory target.**
  - `$HOME` holding only `.claude/` is a claude user-level install into `$HOME/.claude/`.
  - `$HOME` holding only `.config/opencode/` is an opencode user-level install into
    `$HOME/.config/opencode/`.
  - `$HOME` holding both is refused, the refusal names `--harness`, and nothing is written.
  - `$HOME` holding both, with `--harness=opencode`, installs into `$HOME/.config/opencode/`.
- **A claude user-level kb install, with no flag** (target `$HOME/.claude`).
  - The definitions are under `$HOME/.claude/`, the kb set included.
  - None of these exists: `hooks/guardrail.pl`, `skills/kbase/kb-tools/`, `CLAUDE.md`,
    `$HOME/.claude/settings.json`, `$HOME/Makefile`, `$HOME/.mcp.json`, `$HOME/.claude.json`.
- **An opencode user-level kb install.** Neither `plugins/guardrail.ts` nor any `opencode.json` or
  `opencode.jsonc` is written.
- **`--install-global-agents-file`.**
  - It writes `$HOME/.claude/CLAUDE.md`.
  - With injected uncommitted sources, the whole install is refused and nothing is written.
- **The flag on a project install.** It changes nothing in the project, and nothing under `$HOME`.

**Done-line (WP5.3):** the first four lines of WP5.2's done-line hold.

**Return:** the done-line results.

### WP5.4 — expert (`tech-writer`, coordinator's model)

**Brief:** WP5 §Outcome, R1–R7, fact row F20, and this section. The seat reads the diff since BASE.

**Outcome:** the contract documents and README state what WP5.1–WP5.3 built. They cite rather than
restate (CONVENTIONS.md, "Project Documents"), and they record no decision history. Edit leaves only,
never the root pointer files.

**Scope, with what each must state:**

- **SPEC**
  - `PROJECT_DOCS/SPEC/deployed-surfaces/surfaces-and-layout.md`: the install synopsis gains
    `[--subdir=DIR]` and `[--install-global-agents-file]`, and states that `python3 -m adjagent
    install` takes the same arguments.
  - `PROJECT_DOCS/SPEC/deployed-surfaces/install-destination.md`:
    - the target, and the nonexistent-target refusal
    - detection (a) to (d), the home-directory form of (b), and the refusals
    - ROOT and the project root for each kind of target (R1)
    - user-level installs (R3)
  - `PROJECT_DOCS/SPEC/deployed-surfaces/base-and-kb-installs.md`: a user-level kb install writes the
    kb-set definitions and nothing else of the kb install: no kb-tools package, no MCP entry, no
    include line and no runner file.
  - `PROJECT_DOCS/SPEC/deployed-surfaces/shipped-files.md`:
    - Line 11's "repository-top-level package" becomes a package under `adjagent/`.
    - The `kb-tools/` source is `adjagent/kb-tools/`.
    - A user-level install copies no harness file.
  - `PROJECT_DOCS/SPEC/harness-agents-file.md`: line 5's "`install` never installs it" is false (F20).
    State the two cases where `install` writes the file, through the same mechanism and refusals: a
    plugin harness's ROOT, and a user-level ROOT with `--install-global-agents-file`.
  - `PROJECT_DOCS/SPEC/generation-system.md`: lines 15–16. The tier map comes from the family, from a
    harness's default tier spec where it declares one, or whole from the tier-map argument.
- **ARCHITECTURE**
  - `install-consumption-model/install-entry.md`:
    - the one-line recipes
    - the resolution in `install_target.py`
    - the new refusals
    - ROOT created after the checks
  - `install-consumption-model/base-and-kb-installs.md`: the `adjagent/kb-tools/` source, and the
    user-level branch.
  - `install-consumption-model/installing-this-repository.md`: `install-agents-here` runs the verb,
    with no tier map for opencode.
  - `install-consumption-model/guardrail-registration.md`: no probe and no registration on a
    user-level install.
  - `sanctioned-invocation.md`:
    - `install.sh` is gone.
    - `install-agents-file` runs the verb.
    - `_render-slot.sh` and `mage-dist.sh` call `python3 -m adjagent install`.
    - `_harness-value.sh` is still the one shell reader of harness values, for those two scripts.
  - `repo-layout.md`: the `kb-tools/` row moves under `adjagent/`.
  - `composition-model/harnesses-and-families.md`: `default_tier_spec` and `plugin_parent_dir`.
  - `agents-file.md`: the install's two uses of the agents-file install, and its checks running
    before the install's first write.
- **CONVENTIONS**
  - `code-definitions-and-install/harness-agent-file-changes-explicitly.md`: name
    `--install-global-agents-file` as the second explicit act of adoption.
  - Re-read `install-sources-are-filtered.md` and `kb-installation-is-sticky.md`, and edit only a
    sentence the change made false.
- **README.md**
  - "Install": detection, `--subdir`, home-directory and user-level targets, and the flag.
  - "Runner snippets for adding to a project": lines 193 and 209 drop `--model-tier-map=default`.
  - "Harness Agents File": the flag.
  - "Model Tuning": lines 264–266 no longer say opencode needs the tier map overridden.
  - "Repository Layout": line 431's `kb-tools/` row moves under `adjagent/`.

**Done-line (WP5.4, and WP5's):**

- `just check-links` passes.
- `just test-changed` passes.
- This command returns nothing:
  `git grep -n -E 'install\.sh|install-agents-file\.sh|_harness-names|model-tier-map=default|never installs it|repository-top-level' -- PROJECT_DOCS README.md justfile`

**Return:** the done-line results, and each edited leaf named with the sentence or sentences it
changed.

---

## Post-sprint review

Run this once WP5 has landed. It reviews the change, not the plan.

1. **Review.** Dispatch three reviewers. Each has THESIS.md, SPEC.md, ARCHITECTURE.md and
   CONVENTIONS.md as pre-task reading, and none receives this plan.
   - `architect`
   - `python-coder`
   - `tech-writer`

   **Each reviews `git diff BASE`** against those standards and for fitness for its purpose: one
   install entry point whose logic lives in the package. Each review covers the tests the diff
   touches: `tests/test_adjagent_install.py`, `tests/test_adjagent.py`, `tests/test_guardrail.py`,
   and `tests/test_install_target.py` where it exists. The `tech-writer` reviews SPEC.md,
   ARCHITECTURE.md, CONVENTIONS.md and README.md. It checks them for accuracy against the code, and for
   whether a reader without the work thread can act on them.
2. **Burndown.** The architect merges the three reports into one burndown list. It goes beside the
   plan, as `<plan>_REVIEW_BURNDOWN.md`.
3. **Burndown review and revision.** The `prompt-engineer` reviews the burndown for usability, and the
   architect revises it on those findings. Only then is any burndown item dispatched.
4. **Close.** The burndown is done when every item is closed and two things hold on the result:
   - `just test` passes.
   - `just test-changed BASE` passes.

   No `just retake-reference` runs. WP5 changes no rendered content: an installed banner's origin is
   normalised by `render-diff`, and the reference slots keep their explicit flags.
