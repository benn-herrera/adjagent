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
