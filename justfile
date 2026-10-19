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

KBASE_VERSION := "v0.6.0"
TOOL_DIST_CACHE := justfile_dir() / ".tool-dist-cache"

default:
    @just --list | grep -v '\[dev\]'
    @echo "===="
    @just --list | grep '\[dev\]'

# Renders every definition into <target>/<subdir>/ and copies the shipped packages beside them
# through `python3 -m adjagent install`, overwriting what is there; a consuming project's git is
# the record of what changed. Every flag forwards verbatim; adjagent's argparse is the single
# source of flag truth. `--subdir=X`, read only as the first flag, is this recipe's own and
# defaults to the --harness's project-harness-dir.
#
# The recipe also resolves <target> — the first non-flag argument — and passes it beside ROOT as
# the project root, because ROOT is only the harness directory a project keeps under it: the MCP
# entry an install registers and the runner include line it appends belong at the project root,
# never at the harness directory they spell their paths from.
[doc("install into <project>/<subdir>/; <project> is the first non-flag argument, resolved and passed as the project root the harness directory ROOT sits under; [--subdir=<subdir>] defaults to the project-harness-dir of --harness=NAME (default claude: .claude/)")]
install target *args:
    #!/usr/bin/env bash
    set -euo pipefail
    # `just` binds the first positional to `target` whatever it looks like, so
    # a caller leading with flags would have a flag taken as the path. The
    # target is the first argument that is not a `--` flag, wherever it sits;
    # everything else keeps its order and forwards.
    positional=("{{target}}" {{args}})
    target=""
    subdir=""
    have_subdir=""
    harness="claude"
    args=()
    for arg in ${positional[@]+"${positional[@]}"}; do
        if [[ -z "${target}" && "${arg}" != --* ]]; then
            target="${arg}"
        elif [[ "${#args[@]}" -eq 0 && "${arg}" == --subdir=* ]]; then
            subdir="${arg#--subdir=}"
            have_subdir=1
        else
            if [[ "${arg}" == --harness=* ]]; then
                harness="${arg#--harness=}"
            fi
            args+=("${arg}")
        fi
    done
    if [[ -z "${target}" ]]; then
        printf '%s\n' "error: no target project root given — every argument is a flag" >&2
        exit 1
    fi
    # A consuming project that does not exist is an operator mistake — a typo'd
    # path would otherwise be silently populated as a new project root.
    if [[ ! -d "${target}" ]]; then
        printf '%s\n' "error: target project root '${target}' does not exist — create the project first" >&2
        exit 1
    fi
    # pwd -P so a symlinked path resolves to the tree the install reads; the
    # harness arguments name paths from the project root, not from ROOT. The
    # assignment's status is `cd`'s own, so an unenterable directory stops the
    # recipe here rather than at the install with no project root.
    project_root="$(cd "${target}" && pwd -P)"
    if [[ -z "${have_subdir}" ]]; then
        subdir="$("{{just_executable()}}" --justfile "{{justfile()}}" _harness-value "${harness}" project-harness-dir)"
    fi
    root="${target}${subdir:+/${subdir}}"
    mkdir -p "${root}"
    # ${arr[@]+...} guard: expanding an empty array trips `set -u` on the
    # bash 3.2 that macOS ships at /bin/bash.
    PYTHONPATH="{{PROJECT_ROOT}}" python3 -m {{GEN}} install "${root}" --project-root="${project_root}" ${args[@]+"${args[@]}"}

# The bare install above with the kb set added. "$@" is the caller's own $1
# (the target) and flags, unchanged: `install`'s leading-flag scan and
# existence check own them, so this recipe resolves no target of its own.
# Only the `kbase` executable is this recipe's to name.
[doc("install with the kb set as well as the base product: the kb- definitions, the kb-tools package with a kbase from the dist cache beside its runner snippets, and the project-root kbase MCP entry and runner include line; every argument means what it means to install")]
install-with-kb target *args: _download-kbase-dist
    #!/usr/bin/env bash
    set -euo pipefail
    kbase_bin="$("{{just_executable()}}" --justfile "{{justfile()}}" _kbase-bin)"
    "{{just_executable()}}" --justfile "{{justfile()}}" install "$@" --with-kb --kbase-dist="${kbase_bin}"

# The release script unpacks either `kbase` or, under a Windows shell, `kbase.exe`, so the probe
# accepts both names; a probe testing only `kbase` never matched there and re-ran the script on
# every invocation. `_kbase-bin` below is the one place that decides which name runs.
[private]
_download-kbase-dist:
  @mkdir -p "{{TOOL_DIST_CACHE}}"
  @cd "{{TOOL_DIST_CACHE}}"; [[ -f install-kbase-{{KBASE_VERSION}}.sh ]] || \
    curl -OL https://github.com/benn-herrera/kbase/releases/download/{{KBASE_VERSION}}/install-kbase-{{KBASE_VERSION}}.sh
  @cd "{{TOOL_DIST_CACHE}}"; [[ -x "kbase-{{KBASE_VERSION}}"/kbase || -x "kbase-{{KBASE_VERSION}}"/kbase.exe ]] || bash ./install-kbase-{{KBASE_VERSION}}.sh

# The executable `_download-kbase-dist` leaves in the cache: the release
# script's one unsuffixed name, which carries `.exe` under a Windows shell —
# msys, cygwin and mingw all report it from `uname -s`. Printed, not
# interpolated, so the one platform decision is made where `uname` is readable.
[private]
_kbase-bin:
    #!/usr/bin/env bash
    set -euo pipefail
    exe=""
    case "$(uname -s)" in
        MSYS*|CYGWIN*|MINGW*) exe=".exe" ;;
    esac
    printf '%s\n' "{{TOOL_DIST_CACHE}}/kbase-{{KBASE_VERSION}}/kbase${exe}"

# The one reader of a harness's values for recipes: prints KEY of harness NAME
# through `python3 -m adjagent harness`, a leading `~` expanded to $HOME.
[private]
_harness-value harness key:
    #!/usr/bin/env bash
    set -euo pipefail
    value="$(PYTHONPATH="{{PROJECT_ROOT}}" python3 -m {{GEN}} harness "${1}" "${2}")"
    printf '%s\n' "${value/#\~/${HOME}}"

# Every harness name, one per line.
[private]
_harness-names:
    @PYTHONPATH="{{PROJECT_ROOT}}" python3 -m {{GEN}} harnesses

# A thin invocation on purpose: every protection the agents-file install
# carries — block-only replacement, malformed-marker refusal, the
# uncommitted-sources refusal, the rolling backup — lives in
# adjagent/agents_file.py. The one thing
# done here is naming the harness when the caller omits it: the one whose
# user-harness-dir is DIR (resolved to an absolute path). Zero or several
# matches fail rather than guess — a project root matches none, so it takes an
# explicit harness.
[doc("install the harness agents file into <dir>, replacing only the adjagent block and keeping everything outside it; refuses a file without one ordered marker pair; <dir> is ~/.claude, ~/.config/opencode, or a project root; [harness] (claude, opencode) is inferred when <dir> is a harness's user directory and required otherwise")]
install-agents-file dir harness="":
    #!/usr/bin/env bash
    set -euo pipefail
    dir="${1}"
    harness="${2}"
    if [[ -z "${harness}" ]]; then
        # pwd -P so a symlinked path compares equal to its target.
        function resolve() { (cd "${1}" 2>/dev/null && pwd -P) || printf '%s\n' "${1}"; }
        want="$(resolve "${dir}")"
        matches=()
        for name in $("{{just_executable()}}" --justfile "{{justfile()}}" _harness-names); do
            user_dir="$("{{just_executable()}}" --justfile "{{justfile()}}" _harness-value "${name}" user-harness-dir)"
            if [[ "$(resolve "${user_dir}")" == "${want}" ]]; then
                matches+=("${name}")
            fi
        done
        if [[ "${#matches[@]}" -ne 1 ]]; then
            printf '%s\n' "error: cannot infer the harness for '${dir}' (${#matches[@]} harnesses use it as their user directory) — pass it explicitly, e.g. just install-agents-file ${dir} <harness>" >&2
            exit 1
        fi
        harness="${matches[0]}"
    fi
    PYTHONPATH="{{PROJECT_ROOT}}" python3 -m {{GEN}} install-agents-file "${harness}" "${dir}"


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

# render / render-diff: a slot is rebuilt on demand and never read back as
# input to itself, so no slot is ever mistaken for a baseline. The working
# sequence is to do the work, `just render`, then `just render-diff` against
# the reference slots.
#
# `render` mirrors `install`'s own leading-flag scan: the first argument that
# is not a `--` flag, wherever it sits, is the slug (default `latest`) rather
# than a fixed positional parameter, so `just render --family=gemma-4` tunes
# the `latest` slot instead of mistaking the flag for a slug. `--subdir=` is
# fixed ahead of the forwarded flags, so the render always lands directly
# under the slot with no .claude nest.
#
# The flags that produced a slot are recorded in it as RENDER-FLAGS.txt, so a
# `render-diff` between two slots rendered under different tunings shows why
# they differ instead of reading as unexplained drift. A comparison's flag sets
# belong to the invocations that produced each side, never to what an operator
# recalls between them.
#
# The slot also holds the harness agents file for one harness, at
# harness/<name>/<the harness's agents-file name>, written through the
# render-agents-file recipe: `--harness=NAME` (default claude) is the one flag
# this recipe reads as well as forwards, in any position — the agents file and
# the install's definitions render under the same harness — and it is
# recorded in RENDER-FLAGS.txt like any other flag given. The file's name is
# read from the harness ahead of anything else, so an unknown harness fails
# before the slot is touched.
#
# The slot is removed and rebuilt on every render. A slug starting with
# `reference` is refused with nothing touched: those slots are the pre-1.0
# oracle until stage 6 re-renders them.
#
# A slot is rendered with the kb set as well as the base product — the kb
# definitions, the kb-tools package with the dist `kbase`, and the slot's own
# MCP entry and runner include line (the slot is its own project root) — so a
# `render-diff` compares the kb half too, and `_download-kbase-dist` runs
# before the slot is touched.
[doc("[dev] render the full install product, kb set included, into rendered/<slug>/ (slug defaults to latest; the first non-flag argument, in any position, is the slug), plus the agents file for --harness=NAME (default claude) into rendered/<slug>/harness/<NAME>/ — refuses a slug starting with reference; every --* flag, --harness included, forwards verbatim to `python3 -m adjagent install` via install (--family, --model-tier-map, --model-pin-tier-alias-map, --harness, --verbose, ...)")]
render *args: _download-kbase-dist
    #!/usr/bin/env bash
    set -euo pipefail
    slug="latest"
    args=()
    have_slug=""
    for arg in "$@"; do
        if [[ -z "${have_slug}" && "${arg}" != --* ]]; then
            slug="${arg}"
            have_slug=1
        else
            args+=("${arg}")
        fi
    done
    if [[ "${slug}" == reference* ]]; then
        printf '%s\n' "error: slot '${slug}' is protected — a slug starting with 'reference' is the pre-1.0 oracle, which render never renders" >&2
        exit 1
    fi
    "{{just_executable()}}" --justfile "{{justfile()}}" _render-slot "${slug}" ${args[@]+"${args[@]}"}

# Everything `render` does once the slug is accepted: the slot is removed and
# rebuilt from the flags given, which are recorded in it. `--harness=NAME` is
# read here as well as forwarded.
[private]
_render-slot slug *args:
    #!/usr/bin/env bash
    set -euo pipefail
    slug="${1}"
    shift
    harness="claude"
    for arg in "$@"; do
        if [[ "${arg}" == --harness=* ]]; then
            harness="${arg#--harness=}"
        fi
    done
    agents_file="$("{{just_executable()}}" --justfile "{{justfile()}}" _harness-value "${harness}" agents-file)"
    out="{{PROJECT_ROOT / RENDERED_DIR}}/${slug}"
    rm -rf "${out}"
    mkdir -p "${out}/harness/${harness}"
    if [[ "$#" -gt 0 ]]; then
        printf '%s\n' "$@" > "${out}/RENDER-FLAGS.txt"
    else
        : > "${out}/RENDER-FLAGS.txt"
    fi
    "{{just_executable()}}" --justfile "{{justfile()}}" render-agents-file "${harness}" "${out}/harness/${harness}/${agents_file}"
    kbase_bin="$("{{just_executable()}}" --justfile "{{justfile()}}" _kbase-bin)"
    "{{just_executable()}}" --justfile "{{justfile()}}" install "${out}" --subdir= --with-kb --kbase-dist="${kbase_bin}" ${@+"${@}"}

# The three `reference*` slots are the oracle `render-diff` reads. `render`
# refuses their names so a render never overwrites the oracle by accident; this
# recipe is the one deliberate way to re-take them, run after a change to what
# the definitions say has been reviewed and accepted, so that the next
# `render-diff` measures the next change and not that one. Each slot is
# rendered with the kb set, as `render` renders one.
[doc("[dev] re-take the three oracle slots rendered/reference, reference-opencode and reference-gemma from the current generator with their fixed flags — the deliberate counterpart of render's refusal to touch them; run only after a content change is accepted")]
retake-reference: _download-kbase-dist
    #!/usr/bin/env bash
    set -euo pipefail
    render_slot=("{{just_executable()}}" --justfile "{{justfile()}}" _render-slot)
    "${render_slot[@]}" reference
    "${render_slot[@]}" reference-opencode --harness=opencode --model-tier-map=all=inherit
    "${render_slot[@]}" reference-gemma --family=gemma-4 --model-pin-tier-alias-map=all=sonnet

# A stable interface, not a convenience: a later revision of this repository
# invokes it inside a worktree of an earlier one to render that revision's
# agents file. Its name and its two arguments never change incompatibly; the
# body, and the `render-agents-file` verb behind it, may change.
[private]
render-agents-file harness out:
    PYTHONPATH="{{PROJECT_ROOT}}" python3 -m {{GEN}} render-agents-file "$1" "$2"

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

# The one shipped python package is `liaison_tools`, imported as a top-level
# package from its source at the repository root — so the repository root IS
# the import path, here and in the tests. The installed `kb-tools/` tree is
# not an importable package: it holds the runner snippets and the `kbase`
# binary the same install writes. The consumer-side invocation is unaffected:
# there `liaison_tools` arrives under <harness-dir>/adj-tools/ and is imported
# with PYTHONPATH=<harness-dir>/adj-tools.
# `surface` is always positional parameter $1 (positional-arguments, set
# above); the pytest arguments follow it from $2, and are forwarded as the
# separate words `just` received them as, so `-k "a and b"` stays one argument.
# A path argument (not starting with `-`, and an existing path or containing
# `::`) narrows the run: pytest gets the paths and flags but not the surface
# directory. A flag alone does not narrow: pytest gets the directory plus the
# flags. A path outside the surface's directory is refused. The word after a
# flag that takes a separate value (`-k expr`) is that value, never a path.
[doc("[dev] run tooling python tests: no argument runs all three (liaison_tools + adjagent + dupe_sweep); a surface argument (liaison_tools, adjagent, dupe_sweep) runs only that one; further arguments forward to pytest: a flag (-k, -x, -q, ...) keeps the surface directory, a file or file::test path narrows the run to it, and a path outside the surface's directory is refused")]
test surface="" *pytest_args: _venv
    #!/usr/bin/env bash
    set -euo pipefail
    read -ra dirs <<< "{{ \
      if surface == "" { "liaison_tools/tests tests devtools/tests" } \
      else if surface == "liaison_tools" { "liaison_tools/tests" } \
      else if surface == "adjagent" { "tests" } \
      else if surface == "dupe_sweep" { "devtools/tests" } \
      else { error("unknown test surface '" + surface + "' — valid values: liaison_tools, adjagent, dupe_sweep; a leading flag binds here instead — pass it with an explicit empty surface: just test \"\" " + surface) } \
    }}"
    root="{{PROJECT_ROOT}}"
    has_path=0
    skip_next=0
    for arg in "${@:2}"; do
        if [[ "${skip_next}" -eq 1 ]]; then
            skip_next=0
            continue
        fi
        case "${arg}" in
            -k|-m|-p|-o|-c|-n|--deselect|--ignore|--ignore-glob|--maxfail|--tb|--durations) skip_next=1; continue ;;
            -*) continue ;;
        esac
        [[ -e "${arg}" || "${arg}" == *::* ]] || continue
        has_path=1
        rel="${arg#"${root}"/}"
        rel="${rel#./}"
        rel="${rel%%::*}"
        under=0
        for dir in "${dirs[@]}"; do
            if [[ "${rel}" == "${dir}" || "${rel}" == "${dir}/"* ]]; then
                under=1
            fi
        done
        if [[ "${under}" -eq 0 ]]; then
            printf "error: test path '%s' is outside surface '%s' (directory: %s)\n" \
                "${arg}" "{{surface}}" "${dirs[*]}" >&2
            exit 1
        fi
    done
    if [[ "${has_path}" -eq 1 ]]; then
        targets=()
    else
        targets=("${dirs[@]}")
    fi
    PYTHONPATH="${root}" "{{VENV_PYTHON}}" -m pytest ${targets[@]+"${targets[@]}"} "${@:2}"

FLAKE8_IGNORE := "E122,E201,E202,E203,E225,E226,E228,E261,E265,E302,E303,E501,E704,E731,W291,W293,W391,W503"
# `*paths` (positional-arguments, set above) arrives as "$@" with each path
# its own word, so a path containing a space still reaches every tool as one
# argument. No paths given reproduces today's four-surface, tool-by-tool
# argument order exactly — the order flake8 was already called with differs
# from black/isort's, and that difference is preserved rather than
# normalized away.
[doc("[dev] black-format, isort, flake8 the shipped python packages, the generator (adjagent), the tests and devtools, or the given path(s) in place of all of them")]
format-python *paths: _venv
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "$#" -eq 0 ]]; then
        black_isort_paths=(liaison_tools tests adjagent devtools)
        flake8_paths=(liaison_tools adjagent devtools tests)
    else
        black_isort_paths=("$@")
        flake8_paths=("$@")
    fi
    "{{VENV_PYTHON}}" -m black --line-length=120 "${black_isort_paths[@]}"
    "{{VENV_PYTHON}}" -m isort --profile black --line-length 120 "${black_isort_paths[@]}"
    "{{VENV_PYTHON}}" -m flake8 --ignore="{{FLAKE8_IGNORE}}" "${flake8_paths[@]}"


# The duplication sweep. One idea in two places is invisible inside either
# of them — nothing in a file reports a fact about two files — so it has been
# found here by adversarial multi-model review or by accident, and both are too
# expensive to be the standing instrument. This is the standing instrument.
#
# It EMITS CANDIDATES AND NEVER VERDICTS, and exits zero with findings on
# purpose: whether two sites are one idea is a judgment, and a gate here would
# be claiming it. Read the output, or hand it to a seat that will.
#
# Stdlib only under the system python3, like every other tool here, with
# PYTHONPATH at the repository root, the one import path every recipe uses.
# `--rev` sweeps a past tree.
#
# The prose half is
# `tests/test_adjagent.py::test_a_paragraph_two_outputs_carry_has_one_source`,
# which runs in `just test`: shared prose is one constant by construction.
[doc("[dev] list one-idea-two-places candidates across the owned python trees (the corpus devtools/dupe_sweep/python_corpus.py names) — structural twins, repeated constants, repeated docstring and comment rules; trailing args forward to the sweep (--rev, --min-words, --coverage)")]
sweep-python *args:
    PYTHONPATH="{{PROJECT_ROOT}}" python3 -m devtools.dupe_sweep python "$@"


# test-changed: run only the test surfaces a change touches.
#
# Changed paths are the uncommitted tree (`git status`: staged, unstaged and
# untracked, both sides of a rename) plus, when <base> is given, everything
# committed since it (`git diff base...HEAD`). Each path selects the surface
# its prefix names in TEST_SURFACE_MAP below; a path matching no row (docs,
# plans, scratch) selects nothing. There are no cross-surface
# "just in case" rows. The one exception is the runner itself: `justfile` and
# `python.just` select every surface, because a change to the `test` recipe
# cannot be validated by skipping it. With nothing selected, it says so and
# exits zero without running tests. Git is only read.
#
# One row per line: "<path prefix, or exact file> <surface | ALL>". A prefix
# ending in `/` matches everything under it.
TEST_SURFACE_MAP := "
adjagent/ adjagent
tests/ adjagent
devtools/render_diff.py adjagent
devtools/ dupe_sweep
liaison_tools/ liaison_tools
justfile ALL
python.just ALL
"

[doc("[dev] run only the test surfaces a change touches: uncommitted changes plus, with <base>, commits since <base>; prints each chosen surface and the paths that chose it, and runs none when nothing maps to a surface")]
test-changed base="":
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{PROJECT_ROOT}}"
    base="${1}"
    all_surfaces=(liaison_tools adjagent dupe_sweep)
    rows="{{TEST_SURFACE_MAP}}"

    changed=()
    # -z: NUL-separated, unquoted paths; a rename or copy entry (R/C in either
    # status column) is followed by its source path as a separate entry.
    # Both sides count — the source leaving a surface is a change to it.
    while IFS= read -r -d '' entry; do
        changed+=("${entry:3}")
        if [[ "${entry:0:1}" == [RC] || "${entry:1:1}" == [RC] ]]; then
            IFS= read -r -d '' source
            changed+=("${source}")
        fi
    done < <(git status --porcelain -z --untracked-files=all)
    if [[ -n "${base}" ]]; then
        if ! git rev-parse --verify --quiet "${base}^{commit}" > /dev/null; then
            printf '%s\n' "error: base '${base}' is not a commit" >&2
            exit 1
        fi
        while IFS= read -r -d '' path; do
            changed+=("${path}")
        done < <(git diff --name-only --no-renames -z "${base}...HEAD")
    fi

    # "<surface> <path>" lines, one per (surface, changed path) match.
    hits=""
    for path in ${changed[@]+"${changed[@]}"}; do
        while read -r prefix surface; do
            [[ -n "${prefix}" ]] || continue
            if [[ "${path}" == "${prefix}" || ( "${prefix}" == */ && "${path}" == "${prefix}"* ) ]]; then
                if [[ "${surface}" == ALL ]]; then
                    for each in "${all_surfaces[@]}"; do
                        hits+="${each} ${path}"$'\n'
                    done
                else
                    hits+="${surface} ${path}"$'\n'
                fi
            fi
        done <<< "${rows}"
    done

    chosen=()
    for surface in "${all_surfaces[@]}"; do
        matched="$(printf '%s' "${hits}" | sed -n "s/^${surface} //p" | sort -u)"
        if [[ -n "${matched}" ]]; then
            chosen+=("${surface}")
            printf '%s\n' "${surface}:"
            printf '%s\n' "${matched}" | sed 's/^/  /'
        fi
    done
    if [[ "${#chosen[@]}" -eq 0 ]]; then
        printf '%s\n' "no test surface touched by the changed paths; nothing to run"
        exit 0
    fi

    failed=()
    for surface in "${chosen[@]}"; do
        if ! "{{just_executable()}}" --justfile "{{justfile()}}" test "${surface}"; then
            failed+=("${surface}")
        fi
    done
    if [[ "${#failed[@]}" -gt 0 ]]; then
        printf '%s\n' "FAILED surfaces: ${failed[*]}" >&2
        exit 1
    fi

# update this project's own agent installation, base product only: the plain `install` verb once per
# harness. The kb set belongs to a target project, which is what `just install-with-kb <that-project>`
# is for — this repository builds the kb definitions and the kb-tools package but does not use them,
# so nothing here writes adj-tools/kb-tools/, the kbase executable, or a project-root MCP entry.
# No runner include line either: an install never writes one into this repository's own justfile.
# A harness directory that already holds adj-tools/kb-tools/ or the legacy agents/kb-tools/ is a kb
# install even here — the one way this recipe can still install kb.
# The opencode line overrides the tier map because the default family's tier texts name claude
# models, which opencode refuses.
[private]
install-agents-here:
  just install "{{justfile_directory()}}" --harness=claude
  just install "{{justfile_directory()}}" --harness=opencode --model-tier-map=default
