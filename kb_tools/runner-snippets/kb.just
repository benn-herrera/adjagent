# KB maintenance recipes. This file is installed at
# <harness-dir>/agents/kb_tools/runner-snippets/ — <harness-dir> being the
# project's .claude or .opencode — and is imported from the consuming
# project's justfile by one installed line (never copied into it), e.g.
#
#     import? '.claude/agents/kb_tools/runner-snippets/kb.just'
#
# The line is managed by the installer (run from the consumer root):
#     PYTHONPATH=<harness-dir>/agents python3 -m kb_tools.kb_util install-targets
# `import?` requires just >= 1.33; the optional form is deliberate: if the
# installed tree is absent — not yet installed, or removed — the consumer's
# justfile keeps working and only these KB recipes go missing.
#
# Assumed consumer layout: the repo root contains kb-root/ and
# <harness-dir>/agents, which holds the kb_tools package. KB_PYTHONPATH is
# that agents directory, found from this fragment's own location:
# source_directory() is this file's directory inside the installed tree,
# and two levels up is the directory holding kb_tools. The tools are
# stdlib-only and run under the system python3.
#
# Recipe names carry a `kb-` prefix and variables a `KB_` prefix, so neither
# collides with a project's own verify/refresh/stats. Plain recipe lines, no
# `set shell` — nothing here needs bash.
#
# Recipes:
#   kb-verify          verify KB link integrity and claim-graph metadata
#   kb-refresh         refresh mechanically maintained KB metadata
#   kb-stats           print KB claim-graph stats
#   kb-build           launch a detached KB build over the given sources
#   kb-build-await     block until the detached build's card changes or it exits
#   kb-build-kill      TERM the detached build's driver

KB_PYTHONPATH := parent_directory(parent_directory(source_directory()))
PYTHON := "python3"

# Composite, not sequential: both verifiers run, and the recipe carries the
# worst outcome. Two plain lines stop at the first failure, so a report would
# cover one verifier's faults while the other's stayed invisible until it went
# green. One continued line is one shell invocation, which is what lets the rc
# be collected instead of enforced per line. The verifiers label their own
# output ([verify-md-links], [claim-quality]), so suppressing the echo costs
# the report nothing.
[doc("verify KB link integrity and claim-graph metadata")]
kb-verify:
    @rc=0; \
    PYTHONPATH="{{ KB_PYTHONPATH }}" {{PYTHON}} -m kb_tools.verify_md_links || rc=1; \
    PYTHONPATH="{{ KB_PYTHONPATH }}" {{PYTHON}} -m kb_tools.verify_kb_metadata || rc=1; \
    exit $rc

[doc("refresh mechanically maintained KB metadata")]
kb-refresh:
    PYTHONPATH="{{ KB_PYTHONPATH }}" {{PYTHON}} -m kb_tools.refresh_kb_metadata

[doc("print KB claim-graph stats")]
kb-stats:
    PYTHONPATH="{{ KB_PYTHONPATH }}" {{PYTHON}} -m kb_tools.kb_cmd stats

# The detached build. Its scratch dir is the project's <harness-dir>-temp — the
# harness dir's sibling, named from the harness dir (.claude-temp, .opencode-temp)
# — found from this fragment's location as KB_PYTHONPATH is. It holds driver.pid,
# console.log and runs/ (the driver's --run-dir parent). These three are shebang
# recipes under plain sh, so they need no bash and share one body with kb.mk.
KB_LIVE_DIR := parent_directory(KB_PYTHONPATH) + "-temp/kb-driver-live"

[doc("launch a detached KB build over the given LaTeX sources (kb_driver run; relaunching resumes from the ledger); refuses while a launched build is alive; usage: kb-build a.tex b.tex [--driver-flag ...]; the arguments from the first one starting with -- onward are driver flags, appended after the --source list")]
kb-build +args:
    #!/usr/bin/env sh
    set -eu
    set -- run
    n=0
    mode=source
    for a in {{ args }}; do
      case "${a}" in --*) mode=flag ;; esac
      if [ "${mode}" = source ]; then
        set -- "${@}" --source "${a}"
        n=$((n + 1))
      else
        set -- "${@}" "${a}"
      fi
    done
    if [ "${n}" -eq 0 ]; then
      printf 'error: no sources — usage: just kb-build a.tex b.tex [--driver-flag ...]\n' >&2
      exit 1
    fi
    live="{{ KB_LIVE_DIR }}"
    pid_file="${live}/driver.pid"
    if [ -f "${pid_file}" ] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
      printf 'error: build driver pid %s is alive — `just kb-build-kill` it first.\n' "$(cat "${pid_file}")" >&2
      exit 1
    fi
    mkdir -p "${live}/runs"
    PYTHONPATH="{{ KB_PYTHONPATH }}" nohup {{PYTHON}} -m kb_tools.kb_driver "${@}" \
      --run-dir "${live}/runs" < /dev/null > "${live}/console.log" 2>&1 &
    printf '%s\n' "${!}" > "${pid_file}"
    printf 'launched pid %s\n' "${!}"
    printf 'console log: %s\n' "${live}/console.log"
    printf 'then: just kb-build-await\n'

[doc("block until the detached build's card changes (exit 0), the driver exits (3), or there is nothing to await (2)")]
kb-build-await:
    PYTHONPATH="{{ KB_PYTHONPATH }}" {{PYTHON}} -m kb_tools.kb_util await-build

[doc("send TERM to the detached build's driver if alive; the pid file is left for the driver's own cleanup")]
kb-build-kill:
    #!/usr/bin/env sh
    set -eu
    pid_file="{{ KB_LIVE_DIR }}/driver.pid"
    if [ ! -f "${pid_file}" ]; then
      printf 'no pid file — nothing to kill.\n'
      exit 0
    fi
    pid="$(cat "${pid_file}")"
    if ! kill -0 "${pid}" 2>/dev/null; then
      printf 'pid %s already not alive.\n' "${pid}"
      exit 0
    fi
    kill -TERM "${pid}"
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      if ! kill -0 "${pid}" 2>/dev/null; then
        printf 'sent TERM to pid %s — exited.\n' "${pid}"
        exit 0
      fi
      sleep 1
    done
    printf 'error: sent TERM to pid %s but it is still alive after 10s.\n' "${pid}" >&2
    exit 1
