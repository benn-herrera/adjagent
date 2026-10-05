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
