### Guardrail hook

A harness that declares a `guardrail` (`Harness.guardrail`, a `GuardrailHook`) ships a hook the
install registers rather than only copies; claude declares one, opencode sets `None` because its
plugin registers itself, and mage sets `None` and ships no hook at all. The `GuardrailHook` names the
`script` under `resources/<harness>/`, which is also its path under ROOT, and a `registration`, the
`HarnessFile` for the plugin's `hooks/hooks.json`: a text builder and a `marker`, the missing-script
report below, which only this repository writes. The registration holds one `PreToolUse` entry, in
Claude's settings shape under a top-level `hooks` key, whose matcher is
`Bash|Read|Write|Edit|NotebookEdit|Grep|Glob` on every claude install. Every claude install therefore
runs the script on each file-tool call as well as each Bash call, and on a base install the script
finds the kb signal absent and lets a file-tool call through. The entry's
command is a short `sh` program that `exec`s `perl` on
`${CLAUDE_PLUGIN_ROOT}/hooks/guardrail.pl` only when that is a readable file, and
otherwise writes `guardrail hook: no readable script at <path>` to stderr and exits 1. Claude Code
gives a plugin's hook processes `CLAUDE_PLUGIN_ROOT`, so the command names no harness directory and
needs no quoting refusal. The guard exists because perl exits 2 for a script it
cannot open, which Claude Code reads as a block: a plugin that loses its `hooks/` directory would
have every call the matcher names blocked. The interpreter is `perl` on `PATH`, never an absolute
path, because the plugin is often committed and read on other machines. Earlier installs registered
the same program in the project's `.claude/settings.json`, naming the script from
`$CLAUDE_PROJECT_DIR`; the harness's retired entries ([Guardrail registration](guardrail-registration.md))
recognise that command, which the install now removes.

The script is Perl with core `JSON::PP` and `Cwd` and nothing else at session time, a port of
`guardrail.ts`'s `mutation`, its `.index/` check and their helpers. It reads Claude Code's
`PreToolUse` JSON on stdin. Its mutation check judges Bash calls only, resolves relative targets
lexically against the input's `cwd`, else the project root (`$CLAUDE_PROJECT_DIR`, else `cwd`), and
treats `.claude-temp` and `test-data/transient` under that root as scratch; `guardrail.ts` resolves
against the shell call's `workdir`, else the project directory. Every path word of a Bash command
— a redirect or `tee` target, a `cp`/`mv` argument, a word the `.index/` check reads — goes through
`shell_path_of`, which reads a word that, its surrounding quote stripped, opens with
`$CLAUDE_PROJECT_DIR` or `${CLAUDE_PROJECT_DIR}` followed by `/` or the word's end as the rest of the
word under `$ENV{CLAUDE_PROJECT_DIR}`; where that variable is unset or empty, and for every other
word, it is `path_of`. File-tool arguments go through `path_of` alone. The redirect scan does not read
heredoc bodies, which are not shell; a redirect on the heredoc's own command line is still seen, and
the inline-script write check still reads the body.

The `.index/` check runs only when `<harness-dir>/skills/kbase/SKILL.md` exists, tested on every
call. Each script finds its harness directory from its own path, never from the root or the working
directory, which `--subdir` would make wrong: `guardrail.pl` from `$0`, which is
`<harness-dir>/hooks/guardrail.pl`, and `guardrail.ts` from `import.meta.url`, which is
`<harness-dir>/plugins/guardrail.ts`. Its resolution differs from the mutation check's: a path
collapses `..` lexically against the call's working directory, else the root (opencode's file tools:
the root), then follows symlinks through the longest prefix that exists, so a link into `.index/` is
caught. The root's own `kb-root/` and `kb-root/.index/` take the same step, so both sides of a
comparison resolve alike (on macOS a root under `/var` resolves to `/private/var`). A Glob's search
root is its `path` extended by the pattern's leading literal segments. A refusal is
`Blocked: <reason>` alone, without the mutation check's pointer to the edit tools. When both checks
would refuse a shell command, the `.index/` refusal is the one reported.

Exit 2 is the block path alone: a failed `use` or `die` in Perl can itself exit 2, which would block
every call the matcher names, so every module beyond `strict` and `warnings` is loaded with `require`
and the whole body runs in an `eval` that writes to stderr and exits 1, which Claude Code reports as
a hook error without blocking.

