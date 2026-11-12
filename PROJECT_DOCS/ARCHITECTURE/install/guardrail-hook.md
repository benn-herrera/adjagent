### Guardrail hook

What the guardrails block and allow, and what a refusal reads, is SPEC.md, Deployed Surfaces,
[Shipped files](../../SPEC/deployed-surfaces/shipped-files.md); this leaf is how they are built.

A harness that declares a `guardrail` (`Harness.guardrail`, a `GuardrailHook`) ships a hook the
install registers rather than only copies; claude declares one, opencode sets `None` because its
plugin entry (`index.ts`) imports `guardrail.ts` and runs its `setup` inside its own, and mage sets
`None` and ships no hook at all. `guardrail.ts` keeps its `Plugin.define` export so the bun runner
loads it alone, and the entry imports it only where the file stands beside it, which a user-level
install does not copy. Plugin discovery lists only the direct children of `plugins/`, so the file
inside the plugin directory is not also loaded as an opencode plugin module of its own. The `GuardrailHook`
names the `script` under `resources/<harness>/`, which is also its path under the install
directory, and a `registration`, the
`HarnessFile` for the plugin's `hooks/hooks.json`: a text builder, `_guardrail_registration`
(`devpro/harnesses/claude.py`), and a `marker`, the missing-script report (Shipped files), which
only this repository writes. The registration holds one `PreToolUse` entry, in Claude's settings
shape under a top-level `hooks` key, whose matcher is `Bash|Read|Write|Edit|NotebookEdit|Grep|Glob`
on every claude install, as the text builder writes it. Every claude install therefore runs the
script on each file-tool call as well as each Bash call, and on an install of the devpro plugin the script finds
the kbase signal absent and lets a file-tool call through. The entry's command is a short `sh` program that
`exec`s `perl` on `${CLAUDE_PLUGIN_ROOT}/hooks/guardrail.pl` only when that is a readable file, and
otherwise writes the missing-script report to stderr and exits 1. Claude Code gives a plugin's hook
processes `CLAUDE_PLUGIN_ROOT`, so the command names no harness directory and needs no quoting
refusal. The guard exists because perl exits 2 for a script it cannot open, which Claude Code reads
as a block: a plugin that loses its `hooks/` directory would have every call the matcher names
blocked. The interpreter is `perl` on `PATH`, never an absolute path, because the plugin may be
committed or shared and read on other machines.

The script is Perl with core `JSON::PP` and nothing else at session time, a port of
`guardrail.ts`'s `mutation`, its `.index/` check and their helpers. It reads Claude Code's
`PreToolUse` JSON on stdin. It resolves a relative destination against the input's `cwd`, else the
project root (`$CLAUDE_PROJECT_DIR`, else `cwd`); `guardrail.ts` resolves against the shell call's
`workdir`, else the project root, which is also its base for file-tool calls. Every path word of a
Bash command — a shell redirection or `tee` destination, a `cp`/`mv` argument, a word the
`.index/` check reads — goes through `shell_path_of`, which implements the `$CLAUDE_PROJECT_DIR`
spelling Shipped files states, reading the variable from `$ENV{CLAUDE_PROJECT_DIR}`, and otherwise
is `path_of`.
File-tool arguments go through `path_of` alone. `path_of` collapses `..` lexically, the
`.index/` check's one resolution step.

Each script finds the kbase signal, the `kbase` skill's `SKILL.md`, from its own path, never
from the root or the working directory, which `--subdir` would make wrong: `guardrail.pl` from
`$0`, which is `<install-dir>/hooks/guardrail.pl`, so its signal is
`<install-dir>/skills/kbase/SKILL.md`; and `guardrail.ts` from
`import.meta.url`, which is `<install-dir>/guardrail.ts`, so its signal is
`<install-dir>/skills/kbase/SKILL.md` as well, `./skills/kbase/SKILL.md` from the script. Both are
relative to the install directory, so the signal is present where the kbase plugin is installed and absent where the devpro plugin is.

Exit 2 is the block path alone: a failed `use` or `die` in Perl can itself exit 2, which would block
every call the matcher names, so every module beyond `strict` and `warnings` is loaded with `require`
and the whole body runs in an `eval` that writes to stderr and exits 1, which Claude Code reports as
a hook error without blocking.
