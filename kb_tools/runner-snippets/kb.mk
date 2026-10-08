# KB maintenance targets. This file is installed at
# <harness-dir>/agents/kb_tools/runner-snippets/ — <harness-dir> being the
# project's .claude or .opencode — and is included from the consuming
# project's Makefile by one installed line (never copied into it), e.g.
#
#     -include .claude/agents/kb_tools/runner-snippets/kb.mk
#
# The line is managed by the installer (run from the consumer root):
#     PYTHONPATH=<harness-dir>/agents python3 -m kb_tools.kb_util install-targets
# The non-fatal `-include` form is deliberate: if the installed tree is
# absent — not yet installed, or removed — the consumer's Makefile keeps
# working and only these KB targets go missing.
#
# Assumed consumer layout: the repo root (where make runs) contains kb-root/
# and <harness-dir>/agents, which holds the kb_tools package. KB_PY_ENV's
# PYTHONPATH is that agents directory, found from this fragment's own
# location: the last word of MAKEFILE_LIST is this file only while it is being
# read, so KB_SNIPPET_DIR is expanded immediately (:=) and before anything
# else is included. The tools are stdlib-only and run under the system
# python3.
#
# Target names carry a `kb-` prefix and variables a `KB_` prefix, so neither
# collides with a project's own verify/refresh/stats. Plain POSIX recipe
# lines — no SHELL override; existing recipes keep their own shell.
#
# Targets:
#   kb-verify          verify KB link integrity and claim-graph metadata
#   kb-refresh         refresh mechanically maintained KB metadata
#   kb-stats           print KB claim-graph stats
#   kb-build           launch a detached KB build over SOURCES="a.tex b.tex"
#   kb-build-await     block until the detached build's card changes or it exits
#   kb-build-kill      TERM the detached build's driver

KB_SNIPPET_DIR := $(dir $(lastword $(MAKEFILE_LIST)))
KB_PY_ENV := PYTHONPATH=$(abspath $(KB_SNIPPET_DIR)../..)
PYTHON ?= python3

.PHONY: kb-verify kb-refresh kb-stats

# Composite, not sequential: both verifiers run, and the target carries the
# worst outcome. Two plain lines stop at the first failure, so a report would
# cover one verifier's faults while the other's stayed invisible until it went
# green. One continued line is one shell invocation, which is what lets the rc
# be collected instead of enforced per line. The verifiers label their own
# output ([verify-md-links], [claim-quality]), so suppressing the echo costs
# the report nothing.
kb-verify:
	@rc=0; \
	$(KB_PY_ENV) $(PYTHON) -m kb_tools.verify_md_links || rc=1; \
	$(KB_PY_ENV) $(PYTHON) -m kb_tools.verify_kb_metadata || rc=1; \
	exit $$rc

kb-refresh:
	$(KB_PY_ENV) $(PYTHON) -m kb_tools.refresh_kb_metadata

kb-stats:
	$(KB_PY_ENV) $(PYTHON) -m kb_tools.kb_cmd stats

# The detached build. Its scratch dir is the project's <harness-dir>-temp — the
# harness dir's sibling, named from the harness dir (.claude-temp, .opencode-temp)
# — found from this fragment's location as KB_PY_ENV is. It holds driver.pid,
# console.log and runs/ (the driver's --run-dir parent). Sources are
# SOURCES="a.tex b.tex", space-separated, so a path holding a space is not
# supported; DRIVER_FLAGS="--decide s.k=a ..." is appended after the --source
# list, split on spaces the same way.
KB_LIVE_DIR := $(abspath $(KB_SNIPPET_DIR)../../..)-temp/kb-driver-live

.PHONY: kb-build kb-build-await kb-build-kill

kb-build:
	@set -eu; \
	live="$(KB_LIVE_DIR)"; \
	pid_file="$${live}/driver.pid"; \
	set -- run; \
	for s in $(SOURCES); do set -- "$${@}" --source "$${s}"; done; \
	if [ "$${#}" -eq 1 ]; then \
	  printf 'error: no sources — usage: make kb-build SOURCES="a.tex b.tex"\n' >&2; \
	  exit 1; \
	fi; \
	for f in $(DRIVER_FLAGS); do set -- "$${@}" "$${f}"; done; \
	if [ -f "$${pid_file}" ] && kill -0 "$$(cat "$${pid_file}")" 2>/dev/null; then \
	  printf 'error: build driver pid %s is alive — `make kb-build-kill` it first.\n' "$$(cat "$${pid_file}")" >&2; \
	  exit 1; \
	fi; \
	mkdir -p "$${live}/runs"; \
	$(KB_PY_ENV) nohup $(PYTHON) -m kb_tools.kb_driver "$${@}" \
	  --run-dir "$${live}/runs" < /dev/null > "$${live}/console.log" 2>&1 & \
	printf '%s\n' "$${!}" > "$${pid_file}"; \
	printf 'launched pid %s\n' "$${!}"; \
	printf 'console log: %s\n' "$${live}/console.log"; \
	printf 'then: make kb-build-await\n'

kb-build-await:
	$(KB_PY_ENV) $(PYTHON) -m kb_tools.kb_util await-build

kb-build-kill:
	@set -eu; \
	pid_file="$(KB_LIVE_DIR)/driver.pid"; \
	if [ ! -f "$${pid_file}" ]; then \
	  printf 'no pid file — nothing to kill.\n'; \
	  exit 0; \
	fi; \
	pid="$$(cat "$${pid_file}")"; \
	if ! kill -0 "$${pid}" 2>/dev/null; then \
	  printf 'pid %s already not alive.\n' "$${pid}"; \
	  exit 0; \
	fi; \
	kill -TERM "$${pid}"; \
	for _ in 1 2 3 4 5 6 7 8 9 10; do \
	  if ! kill -0 "$${pid}" 2>/dev/null; then \
	    printf 'sent TERM to pid %s — exited.\n' "$${pid}"; \
	    exit 0; \
	  fi; \
	  sleep 1; \
	done; \
	printf 'error: sent TERM to pid %s but it is still alive after 10s.\n' "$${pid}" >&2; \
	exit 1
