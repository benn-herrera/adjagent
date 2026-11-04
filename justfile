# agents task recipes.

# Recipe bodies are bash, not just's default `sh`. Stating it makes the
# contract explicit rather than inherited from whatever /bin/sh happens to be
# on the host. `-u` (just's own default, kept) makes an unset variable a
# failure instead of an empty string. `-o pipefail` makes a pipeline fail
# when any stage does, not just its last.
set shell := ["bash", "-cuo", "pipefail"]
# Without this, a variadic parameter reaches a recipe body only through
# `{{args}}` textual interpolation, which just renders as a bare
# space-joined string — a multi-word value like `-k "a and b"` arrives as
# four separate shell words, indistinguishable from four short ones. With
# it, recipe parameter values are also passed as the shell's own positional
# parameters ($1, $2, ...), so `"$@"` (or a slice of it) carries each
# argument through with its original word boundaries intact.
set positional-arguments := true

# consumed in python.just
PROJECT_ROOT := justfile_directory()
import 'python.just'

GEN := "adjagent"

default:
    @just --list | grep -v '\[dev\]'
    @echo "===="
    @just --list | grep '\[dev\]'

[doc("install into an existing <target>: [--harness=NAME] [--subdir=DIR] [--install-global-agents-file] [--dry-run] [tuning flags]; an up-to-date target is left untouched; --dry-run prints what would be created, changed and removed and writes nothing; docs/install-reference.md has the rules")]
install target *args:
    @PYTHONPATH="{{PROJECT_ROOT}}" python3 -m "{{GEN}}" install "$@"

[doc("as install, plus the kb set (docs/knowledge-base.md); takes --dry-run as install does")]
install-with-kb target *args:
    @PYTHONPATH="{{PROJECT_ROOT}}" python3 -m "{{GEN}}" install "$@" --with-kb

[doc("install the harness agents file into <dir>, replacing only the adjagent block and keeping everything outside it; refuses a file without one ordered marker pair; <dir> is ~/.claude, ~/.config/opencode, or a project root; [--harness NAME] (claude, opencode — the two whose user-harness-dir is absolute) is inferred when <dir> is that harness's user directory and required otherwise; a relative user-harness-dir, as mage's is, is never an inference basis; an up-to-date file is left untouched; [--dry-run] prints whether the agents file and any redirect would be created or changed and writes nothing")]
install-agents-file dir *args:
    @PYTHONPATH="{{PROJECT_ROOT}}" python3 -m "{{GEN}}" install-agents-file "$@"

##
##
## mmmm                        mmmmm                  "
## #   "m  mmm   m   m         #   "#  mmm    mmm   mmm    mmmm    mmm    mmm
## #    # #"  #  "m m"         #mmmm" #"  #  #"  "    #    #" "#  #"  #  #   "
## #    # #""""   #m#          #   "m #""""  #        #    #   #  #""""   """m
## #mmm"  "#mm"    #           #    " "#mm"  "#mm"  mm#mm  ##m#"  "#mm"  "mmm"
##                                                          #
##                                                          "

# The root the repository's own render slots sit under: gitignored, never
# committed, and the conventional place to inspect the product or diff it in
# a PR. No slot is ever read back as input to another render (see `render`
# and `render-diff` below), so this names a location under which slots live,
# not a privileged tree.
RENDERED_DIR := "rendered"

[doc("tag the current commit v<version>, <version> read from `python3 -m adjagent --version`; refuses while adjagent/ has uncommitted changes or the tag already exists, and never pushes")]
tag:
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" ./devtools/scripts/tag.sh

[doc("build the mage plugin from the working tree into dist/ (override with DIST_DIR) as adjagent-mage-v<version>.tgz with a detached .asc signed by the release key; removes stale outputs and the stage on exit; uploads nothing")]
mage-dist:
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" ./devtools/scripts/mage-dist.sh

[doc("build the wheel and sdist of the working tree into dist/ with the venv's setuptools; makes no git check and fetches nothing")]
build: _venv
    @{{VENV_PYTHON}} -m build --no-isolation --outdir "{{PROJECT_ROOT}}/dist" "{{PROJECT_ROOT}}"

[doc("[dev] build, then prove the wheel: its package data equals the non-.py files under adjagent/ that git tracks or would track, and installed into a throwaway venv made from <python> (default /usr/bin/python3) it imports from that venv, runs as the adjagent console script, installs byte-identically to the checkout, and writes the mage plugin's agents file outside a checkout")]
check-wheel python="/usr/bin/python3": build
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" PYBIN="{{PYBIN}}" EXE="{{EXE}}" ./devtools/scripts/check-wheel.sh "$@"

[doc("[dev] render the full install product, kb set included, into rendered/<slug>/ (slug defaults to latest; the first non-flag argument, in any position, is the slug), plus the agents file for --harness=NAME (default claude) into rendered/<slug>/harness/<NAME>/, or at the slot root for a plugin (`mage`) — refuses a slug starting with reference; every --* flag, --harness included, forwards verbatim to `python3 -m adjagent install` via install (--family, --model-tier-map, --model-pin-tier-alias-map, --harness, --verbose, ...)")]
render *args:
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" RENDERED_DIR="{{RENDERED_DIR}}" ./devtools/scripts/render.sh "$@"

[private]
_render-slot slug *args:
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" RENDERED_DIR="{{RENDERED_DIR}}" ./devtools/scripts/_render-slot.sh "$@"

[doc("[dev] re-take the three oracle slots rendered/reference, reference-opencode and reference-gemma from the current generator with their fixed flags — the deliberate counterpart of render's refusal to touch them; run only after a content change is accepted")]
retake-reference:
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" RENDERED_DIR="{{RENDERED_DIR}}" ./devtools/scripts/_render-slot.sh reference
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" RENDERED_DIR="{{RENDERED_DIR}}" ./devtools/scripts/_render-slot.sh reference-opencode --harness=opencode --model-tier-map=all=inherit
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" RENDERED_DIR="{{RENDERED_DIR}}" ./devtools/scripts/_render-slot.sh reference-gemma --family=gemma-4 --model-pin-tier-alias-map=all=sonnet

[private]
render-agents-file harness out:
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" ./devtools/scripts/render-agents-file.sh "$@"

[private]
_harness-value harness key:
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" ./devtools/scripts/_harness-value.sh "$@"

[doc("split a markdown monolith by heading level into linked leaves under out (optional link map TSV), then check the leaves reassemble it and every relative link resolves")]
dice-doc monolith out map="": _venv
    @{{DOCDICER}} dice-doc "{{monolith}}" "{{out}}" "{{map}}"

[doc("dice the documents listed in a manifest TSV, read from src-dir, into linked volumes, with intermediates in work-dir, then verify all trees")]
dice-docs manifest src work: _venv
    @{{DOCDICER}} dice-docs "{{manifest}}" "{{src}}" "{{work}}"

[doc("write a diced tree (the directory holding its entry-point.md) back out as one markdown document at monolith, which must not exist, then check it dices back to the same tree")]
undice tree monolith: _venv
    @{{DOCDICER}} undice "{{tree}}" "{{monolith}}"

[doc("check every relative link and #anchor in PROJECT_DOCS, docs and the top-level *.md files, then that every PROJECT_DOCS document is listed by its parent and reachable from its entry point; exit 1 on a broken link or an orphan")]
check-links: _venv
    @{{DOCDICER}} check-links PROJECT_DOCS docs *.md
    @{{DOCDICER}} check-tree PROJECT_DOCS

# Reports and never gates: a difference between two slots is the expected
# outcome of doing work, so differences exit zero. Only a comparison that could
# not be MADE is fatal — a missing slot, or a file that cannot be read.
#
# Files compare by text, not by bytes: a file whose first line is `---` and whose
# next lines have exactly one of the two frontmatter banner shapes has those lines
# replaced by the one constant line `# !BANNER!`; so does a skill's supporting file,
# which has no frontmatter and carries the third shape, the two HTML comments
# `<!-- !GENERATED! ... -->` and `<!-- !TUNING! ... -->` from its first line. Then,
# outside fenced code, whitespace inside a paragraph collapses to one space, while
# headings, thematic breaks, table rows, list items, fenced blocks and frontmatter stay exact
# (devtools/render_diff.py states the rules). A copied file's `!INSTALLED!` banner
# is replaced the same way. Two files are the same when that text is identical. The
# output keeps `diff -rq`'s two line forms.
[doc("[dev] diff two rendered slots under rendered/ (a defaults to reference, b defaults to latest) by text, each file's banner block replaced by one constant line — reports differences and exits zero; exits non-zero only when the comparison could not be made")]
render-diff a="reference" b="latest":
    @PYTHONPATH="{{PROJECT_ROOT}}" python3 -m devtools.render_diff "{{a}}" "{{b}}"

[doc("[dev] run tooling python tests and the markdown link check: no argument runs all four (adjagent + dupe_sweep pytest, then docs: just check-links with its defaults, then wheel: just check-wheel); a surface argument (adjagent, dupe_sweep, docs, wheel) runs only that one; further arguments, never given to docs or wheel, forward to pytest: a flag (-k, -x, -q, ...) keeps the surface directory, a file or file::test path narrows the run to it, and a path outside the surface's directory is refused")]
test surface="" *pytest_args: _venv
    @PROJECT_ROOT="{{PROJECT_ROOT}}" VENV_PYTHON={{VENV_PYTHON}} JUST="{{just_executable()}}" JUSTFILE="{{justfile()}}" ./devtools/scripts/test.sh "$@"

FLAKE8_IGNORE := "E122,E201,E202,E203,E225,E226,E228,E261,E265,E302,E303,E501,E704,E731,W291,W293,W391,W503"
[doc("[dev] black-format, isort, flake8 the generator (adjagent), the tests and devtools, or the given path(s) in place of all of them")]
format-python *paths: _venv
    @VENV_PYTHON={{VENV_PYTHON}} FLAKE8_IGNORE="{{FLAKE8_IGNORE}}" ./devtools/scripts/format-python.sh "$@"

# Emits candidates, never verdicts, and exits zero with findings: whether two sites are one idea is
# a judgment, and a gate here would be claiming it.
[doc("[dev] list one-idea-two-places candidates across the owned python trees (the corpus devtools/dupe_sweep/python_corpus.py names) — structural twins, repeated constants, repeated docstring and comment rules; trailing args forward to the sweep (--rev, --min-words, --coverage)")]
sweep-python *args:
    @PYTHONPATH="{{PROJECT_ROOT}}" python3 -m devtools.dupe_sweep python "$@"


# test-changed: run only the test surfaces a change touches.
#
# Changed paths are the uncommitted tree (`git status`: staged, unstaged and
# untracked, both sides of a rename) plus, when <base> is given, everything
# committed since it (`git diff base...HEAD`). Each path selects the surface
# its prefix names in TEST_SURFACE_MAP below; a path matching no row
# (ROADMAP_PLANS/, scratch) selects nothing. There are no cross-surface
# "just in case" rows. The one exception is the runner itself: `justfile`,
# `python.just` and `devtools/scripts/` — where every recipe body lives, inline or scripted — select
# every surface, because a change to the `test` recipe, or to the script it
# runs, cannot be validated by skipping it. With nothing selected, it says so
# and exits zero without running tests. Git is only read.
#
# One row per line: "<path prefix, or exact file> <surface | ALL>". A prefix
# ending in `/` matches everything under it; one starting `*` is a glob over
# top-level file names. `docs` is the link check: the documents it reads
# (PROJECT_DOCS/, docs/, top-level *.md), and the dicer that runs it. `wheel` is
# check-wheel: the build configuration it builds from, and the package tree
# whose data it checks.
TEST_SURFACE_MAP := "
adjagent/ adjagent
adjagent/ wheel
tests/ adjagent
devtools/render_diff.py adjagent
devtools/ dupe_sweep
PROJECT_DOCS/ docs
*.md docs
docs/ docs
devtools/dicer/ docs
pyproject.toml wheel
justfile ALL
python.just ALL
devtools/scripts/ ALL
"

[doc("[dev] run only the test surfaces a change touches: uncommitted changes plus, with <base>, commits since <base>; prints each chosen surface and the paths that chose it, and runs none when nothing maps to a surface")]
test-changed base="":
    @PROJECT_ROOT="{{PROJECT_ROOT}}" TEST_SURFACE_MAP="{{TEST_SURFACE_MAP}}" JUST="{{just_executable()}}" JUSTFILE="{{justfile()}}" ./devtools/scripts/test-changed.sh "$@"

# This repository's own install: base product only, once per harness.
[private]
install-agents-here:
    @PYTHONPATH="{{PROJECT_ROOT}}" python3 -m "{{GEN}}" install "{{PROJECT_ROOT}}" --harness=claude
    @PYTHONPATH="{{PROJECT_ROOT}}" python3 -m "{{GEN}}" install "{{PROJECT_ROOT}}" --harness=opencode

[doc("[dev] list each definition-body unit that joins a clauses.* interpolation to the module's own text, one line per unit naming its first clause's line, then the count; given paths, only those definition modules")]
clause-join-sites *paths:
    @PYTHONPATH="{{PROJECT_ROOT}}" python3 -m devtools.clause_join_sites "$@"
