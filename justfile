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

KBASE_VERSION := "v0.8.0"
TOOL_DIST_CACHE := justfile_dir() / ".tool-dist-cache"

default:
    @just --list | grep -v '\[dev\]'
    @echo "===="
    @just --list | grep '\[dev\]'

[doc("install into <project>/<subdir>/; <project> is the first non-flag argument, resolved and passed as the project root the harness directory ROOT sits under; [--subdir=<subdir>] defaults to the project-harness-dir of --harness=NAME (default claude: .claude/)")]
install target *args:
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" TOOL_DIST_CACHE="{{TOOL_DIST_CACHE}}" KBASE_VERSION="{{KBASE_VERSION}}" ./devtools/scripts/install.sh "$@"

[doc("install with the kb set as well as the base product: the kb- definitions, the kb-tools package with a kbase from the dist cache beside its runner snippets, and the project-root kbase MCP entry and runner include line; every argument means what it means to install")]
install-with-kb target *args: _download-kbase-dist
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" TOOL_DIST_CACHE="{{TOOL_DIST_CACHE}}" KBASE_VERSION="{{KBASE_VERSION}}" ./devtools/scripts/install-with-kb.sh "$@"

[private]
_download-kbase-dist:
  @TOOL_DIST_CACHE="{{TOOL_DIST_CACHE}}" KBASE_VERSION="{{KBASE_VERSION}}" ./devtools/scripts/_download-kbase-dist.sh

[private]
_kbase-bin:
    @TOOL_DIST_CACHE="{{TOOL_DIST_CACHE}}" KBASE_VERSION="{{KBASE_VERSION}}" ./devtools/scripts/_kbase-bin.sh

[private]
_harness-value harness key:
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" ./devtools/scripts/_harness-value.sh "$@"

[private]
_harness-names:
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" ./devtools/scripts/_harness-names.sh

[doc("install the harness agents file into <dir>, replacing only the adjagent block and keeping everything outside it; refuses a file without one ordered marker pair; <dir> is ~/.claude, ~/.config/opencode, or a project root; [harness] (claude, opencode — the two whose user-harness-dir is absolute) is inferred when <dir> is that harness's user directory and required otherwise; a relative user-harness-dir, as mage's is, is never an inference basis")]
install-agents-file dir harness="":
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" ./devtools/scripts/install-agents-file.sh "$@"

[doc("tag the current commit v<version>, <version> read from `python3 -m adjagent version`; refuses while adjagent/ has uncommitted changes or the tag already exists, and never pushes")]
tag:
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" ./devtools/scripts/tag.sh


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

[doc("[dev] render the full install product, kb set included, into rendered/<slug>/ (slug defaults to latest; the first non-flag argument, in any position, is the slug), plus the agents file for --harness=NAME (default claude) into rendered/<slug>/harness/<NAME>/, or at the slot root for a plugin (`mage`) — refuses a slug starting with reference; every --* flag, --harness included, forwards verbatim to `python3 -m adjagent install` via install (--family, --model-tier-map, --model-pin-tier-alias-map, --harness, --verbose, ...)")]
render *args: _download-kbase-dist
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" RENDERED_DIR="{{RENDERED_DIR}}" TOOL_DIST_CACHE="{{TOOL_DIST_CACHE}}" KBASE_VERSION="{{KBASE_VERSION}}" ./devtools/scripts/render.sh "$@"

[private]
_render-slot slug *args:
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" RENDERED_DIR="{{RENDERED_DIR}}" TOOL_DIST_CACHE="{{TOOL_DIST_CACHE}}" KBASE_VERSION="{{KBASE_VERSION}}" ./devtools/scripts/_render-slot.sh "$@"

[doc("[dev] re-take the three oracle slots rendered/reference, reference-opencode and reference-gemma from the current generator with their fixed flags — the deliberate counterpart of render's refusal to touch them; run only after a content change is accepted")]
retake-reference: _download-kbase-dist
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" RENDERED_DIR="{{RENDERED_DIR}}" TOOL_DIST_CACHE="{{TOOL_DIST_CACHE}}" KBASE_VERSION="{{KBASE_VERSION}}" ./devtools/scripts/retake-reference.sh

[private]
render-agents-file harness out:
    @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" ./devtools/scripts/render-agents-file.sh "$@"

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
# headings, table rows, list items, fenced blocks and frontmatter stay exact
# (devtools/render_diff.py states the rules). A copied file's `!INSTALLED!` banner
# is replaced the same way. Two files are the same when that text is identical. The
# output keeps `diff -rq`'s two line forms.
[doc("[dev] diff two rendered slots under rendered/ (a defaults to reference, b defaults to latest) by text, each file's banner block replaced by one constant line — reports differences and exits zero; exits non-zero only when the comparison could not be made")]
render-diff a="reference" b="latest":
    @PYTHONPATH="{{PROJECT_ROOT}}" python3 -m devtools.render_diff "{{a}}" "{{b}}"

[doc("[dev] run tooling python tests: no argument runs both (adjagent + dupe_sweep); a surface argument (adjagent, dupe_sweep) runs only that one; further arguments forward to pytest: a flag (-k, -x, -q, ...) keeps the surface directory, a file or file::test path narrows the run to it, and a path outside the surface's directory is refused")]
test surface="" *pytest_args: _venv
    @PROJECT_ROOT="{{PROJECT_ROOT}}" VENV_PYTHON="{{VENV_PYTHON}}" ./devtools/scripts/test.sh "$@"

FLAKE8_IGNORE := "E122,E201,E202,E203,E225,E226,E228,E261,E265,E302,E303,E501,E704,E731,W291,W293,W391,W503"
[doc("[dev] black-format, isort, flake8 the generator (adjagent), the tests and devtools, or the given path(s) in place of all of them")]
format-python *paths: _venv
    @VENV_PYTHON="{{VENV_PYTHON}}" FLAKE8_IGNORE="{{FLAKE8_IGNORE}}" ./devtools/scripts/format-python.sh "$@"


[doc("[dev] list one-idea-two-places candidates across the owned python trees (the corpus devtools/dupe_sweep/python_corpus.py names) — structural twins, repeated constants, repeated docstring and comment rules; trailing args forward to the sweep (--rev, --min-words, --coverage)")]
sweep-python *args:
    @PROJECT_ROOT="{{PROJECT_ROOT}}" ./devtools/scripts/sweep-python.sh "$@"


# test-changed: run only the test surfaces a change touches.
#
# Changed paths are the uncommitted tree (`git status`: staged, unstaged and
# untracked, both sides of a rename) plus, when <base> is given, everything
# committed since it (`git diff base...HEAD`). Each path selects the surface
# its prefix names in TEST_SURFACE_MAP below; a path matching no row (docs,
# plans, scratch) selects nothing. There are no cross-surface
# "just in case" rows. The one exception is the runner itself: `justfile`,
# `python.just` and `devtools/scripts/` — where every recipe body lives — select
# every surface, because a change to the `test` recipe, or to the script it
# runs, cannot be validated by skipping it. With nothing selected, it says so
# and exits zero without running tests. Git is only read.
#
# One row per line: "<path prefix, or exact file> <surface | ALL>". A prefix
# ending in `/` matches everything under it.
TEST_SURFACE_MAP := "
adjagent/ adjagent
tests/ adjagent
devtools/render_diff.py adjagent
devtools/ dupe_sweep
justfile ALL
python.just ALL
devtools/scripts/ ALL
"

[doc("[dev] run only the test surfaces a change touches: uncommitted changes plus, with <base>, commits since <base>; prints each chosen surface and the paths that chose it, and runs none when nothing maps to a surface")]
test-changed base="":
    @PROJECT_ROOT="{{PROJECT_ROOT}}" TEST_SURFACE_MAP="{{TEST_SURFACE_MAP}}" JUST="{{just_executable()}}" JUSTFILE="{{justfile()}}" ./devtools/scripts/test-changed.sh "$@"

[private]
install-agents-here:
  @PROJECT_ROOT="{{PROJECT_ROOT}}" GEN="{{GEN}}" ./devtools/scripts/install-agents-here.sh
