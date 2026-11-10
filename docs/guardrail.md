# Guardrail

Claude and opencode each ship a hook that blocks shell commands which change a file behind the Edit
and Write tools; use those tools instead. The exact rule is in
[Shipped files](../PROJECT_DOCS/SPEC/deployed-surfaces/shipped-files.md). Writes into scratch are
allowed: `.claude-temp/` under claude and `.opencode-temp/` under opencode.
A refusal reads `Blocked: <reason>`. Commands the hook refuses include `sed -i`, a redirect onto a
file, `tee`, and `cp` or `mv` onto an existing file. The hook catches the forms agents habitually
use; it is not a boundary against a command written to evade it. Mage ships none, and a user-level
install installs none.

## The `.index/` check

In the kbase plugin, the hook also keeps sessions out of `kb-root/.index/`, where kbase keeps its
records: read them with kbase's `query` tool and change them with its `write` tool. Reading or
naming a path in `kb-root/.index/` is refused; an existence check, such as `stat` or `test -e`, is
not. A recursive search rooted in `kb-root/` is refused until it excludes `.index`; the refusal says
how. The check is on only while the kbase skill's `SKILL.md` is present, and the hook looks for it
on every call, so the devpro plugin never sees it.

## Claude

The hook is `guardrail.pl` inside the plugin, registered in the plugin's own
`hooks/hooks.json`. It needs `perl` on `PATH` with core `JSON::PP` when a session runs it. The
install runs it once to check; without perl or the module, or if the run takes more than a few
seconds, it skips the hook and its registration, reports the reason in one line and installs
everything else. A script and registration from an earlier install are left in place and named.

Where the plugin's script is missing, a call prints `guardrail hook: no readable script at <path>`
and goes ahead, rather than being blocked; run the install again to restore the script, which works
only where the install's perl check passes.

## Opencode

The guardrail is `guardrail.ts` inside the plugin's directory
(`.opencode/plugins/<plugin>/guardrail.ts`), copied as it stands. The plugin entry, `index.ts`, runs
it; the install writes no settings entry for it. A user-level install copies the entry but no
`guardrail.ts`, so it runs none.
