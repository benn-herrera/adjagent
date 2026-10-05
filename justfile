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

GEN := "gen_defs"

default:
    @just --list | grep -v '\[dev\]'
    @echo "===="
    @just --list | grep '\[dev\]'

# The one deployment shape: copies both deployed
# surfaces into <target>/.claude/ via gen_defs install, minus test suites
# and caches, stamping each copied file with an !INSTALLED! banner carrying the
# hash of the content below it. Every flag forwards verbatim to
# gen_defs — --family, --model-tier-map, --model-pin-map, --verbose, and
# whatever it adds next: gen_defs's argparse is the single source of flag
# truth, so an unknown spelling fails there — stripping `--` to
# make the params positional would make the command line worse, not better. The
# one flag this recipe intercepts is `--subdir=X`, because it addresses this
# recipe's own target-composition, not gen_defs: read only when it is the
# *first* flag, stripped before the rest forwards. Absent, subdir defaults to
# the project-harness-dir of the harness named by `--harness=NAME` (default
# claude), read from templates/harness/<NAME>.toml; `--harness` still forwards
# to gen_defs. `--subdir=` (empty value) installs directly into <target>.
[doc("install into <project>/<subdir>/; <project> is the first non-flag argument; [--subdir=<subdir>] defaults to the project-harness-dir of --harness=NAME (default claude: .claude/)")]
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
    if [[ -z "${have_subdir}" ]]; then
        subdir="$("{{just_executable()}}" --justfile "{{justfile()}}" _harness-value "${harness}" project-harness-dir)"
    fi
    root="${target}${subdir:+/${subdir}}"
    mkdir -p "${root}"
    # ${arr[@]+...} guard: expanding an empty array trips `set -u` on the
    # bash 3.2 that macOS ships at /bin/bash.
    PYTHONPATH="{{PROJECT_ROOT}}" python3 -m {{GEN}} install "${root}" ${args[@]+"${args[@]}"}

# The one reader of templates/harness/<harness>.toml for recipes: prints the
# `text` of table [harness.<key>], with a leading `~` expanded to $HOME. An
# unknown harness fails listing the available harness files.
[private]
_harness-value harness key:
    #!/usr/bin/env bash
    set -euo pipefail
    dir="{{PROJECT_ROOT}}/templates/harness"
    if [[ ! -f "${dir}/${1}.toml" ]]; then
        available="$(cd "${dir}" && printf '%s ' *.toml)"
        printf "error: unknown harness '%s' — available harness files: %s\n" "${1}" "${available}" >&2
        exit 1
    fi
    value="$(sed -n '/^\[harness\.'"${2}"'\]/,/^\[/s/^text = "\(.*\)"$/\1/p' "${dir}/${1}.toml")"
    if [[ -z "${value}" ]]; then
        printf "error: harness '%s' defines no [harness.%s] text\n" "${1}" "${2}" >&2
        exit 1
    fi
    printf '%s\n' "${value/#\~/${HOME}}"

# A thin invocation on purpose: every protection the agents-file install
# carries — block-only replacement, malformed-marker refusal, dirty-templates
# refusal, the rolling backup — lives in gen_defs/agents_file.py. The one thing
# done here is naming the harness when the caller omits it: the one whose
# user-harness-dir is DIR (resolved to an absolute path). Zero or several
# matches fail rather than guess — a project root matches none, so it takes an
# explicit harness.
[doc("install the harness agents file into <dir>, replacing only the adjagent block and keeping everything outside it; <dir> is ~/.claude, ~/.config/opencode, or a project root; [harness] (claude, opencode) is inferred when <dir> is a harness's user directory and required otherwise")]
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
        for file in "{{PROJECT_ROOT}}"/templates/harness/*.toml; do
            name="$(basename "${file}" .toml)"
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
# sequence is `just render reference` to capture a known-good state, do the
# work, `just render`, then `just render-diff`.
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
# recorded in RENDER-FLAGS.txt like any other flag given. That recipe never
# overwrites a differing file, so the slot's harness/ subtree is removed
# before each render; the file's name is read from the harness file ahead of
# the install, so an unknown harness fails before the slot is touched further.
[doc("[dev] render the full install product into rendered/<slug>/ (slug defaults to latest; the first non-flag argument, in any position, is the slug) plus the agents file for --harness=NAME (default claude) into rendered/<slug>/harness/<NAME>/ — every --* flag, --harness included, forwards verbatim to gen_defs via install (--family, --model-tier-map, --model-pin-map, --harness, --verbose, ...)")]
render *args:
    #!/usr/bin/env bash
    set -euo pipefail
    slug="latest"
    harness="claude"
    args=()
    recorded=()
    have_slug=""
    for arg in "$@"; do
        if [[ -z "${have_slug}" && "${arg}" != --* ]]; then
            slug="${arg}"
            have_slug=1
        elif [[ "${arg}" == --harness=* ]]; then
            harness="${arg#--harness=}"
            args+=("${arg}")
            recorded+=("${arg}")
        else
            args+=("${arg}")
            recorded+=("${arg}")
        fi
    done
    out="{{PROJECT_ROOT / RENDERED_DIR}}/${slug}"
    mkdir -p "${out}"
    if [[ "${#recorded[@]}" -gt 0 ]]; then
        printf '%s\n' "${recorded[@]}" > "${out}/RENDER-FLAGS.txt"
    else
        : > "${out}/RENDER-FLAGS.txt"
    fi
    agents_file="$(PYTHONPATH="{{PROJECT_ROOT}}" python3 -m {{GEN}} dev agents-file-for-harness "${harness}")"
    rm -rf "${out}/harness"
    mkdir -p "${out}/harness/${harness}"
    "{{just_executable()}}" --justfile "{{justfile()}}" render-agents-file "${harness}" "${out}/harness/${harness}/${agents_file}"
    "{{just_executable()}}" --justfile "{{justfile()}}" install "${out}" --subdir= ${args[@]+"${args[@]}"}

# A stable interface, not a convenience: a later revision of this repository
# invokes it inside a worktree of an earlier one to render that revision's
# agents file. Its name and its two arguments never change incompatibly; the
# body, and the gen_defs verb behind it, may.
[private]
render-agents-file harness out:
    PYTHONPATH="{{PROJECT_ROOT}}" python3 -m {{GEN}} dev render-agents-file "$1" "$2"

# Reports and never gates: a difference between two slots is the expected
# outcome of doing work, so `diff -rq`'s exit 1 is swallowed. Only a
# comparison that could not be MADE is fatal — a missing slot, or `diff(1)`
# itself in trouble (status 2).
[doc("[dev] diff two rendered slots under rendered/ (a defaults to reference, b defaults to latest) — reports differences and exits zero; exits non-zero only when the comparison could not be made")]
render-diff a="reference" b="latest":
    #!/usr/bin/env bash
    set -euo pipefail
    a_dir="{{PROJECT_ROOT / RENDERED_DIR}}/{{a}}"
    b_dir="{{PROJECT_ROOT / RENDERED_DIR}}/{{b}}"
    if [[ ! -d "${a_dir}" ]]; then
        printf 'error: %s does not exist — run '"'"'just render {{a}}'"'"' first\n' "${a_dir}" >&2
        exit 1
    fi
    if [[ ! -d "${b_dir}" ]]; then
        printf 'error: %s does not exist — run '"'"'just render {{b}}'"'"' first\n' "${b_dir}" >&2
        exit 1
    fi
    diff_status=0
    diff -rq "${a_dir}" "${b_dir}" || diff_status="$?"
    if [[ "${diff_status}" -eq 2 ]]; then
        exit 1
    fi

# The shipped packages are imported as top-level packages (`kb_tools`,
# `liaison_tools`), and their sources sit at the repository root — so the
# repository root IS the import path. The consumer-side invocation is
# unaffected: there the same packages arrive under .claude/agents/ and are
# imported with PYTHONPATH=.claude/agents.
# `surface` is always positional parameter $1 (positional-arguments, set
# above), so the pytest arguments that follow it start at $2 — `"${@:2}"`
# forwards them to pytest as the separate words `just` received them as,
# not as a re-split string, so `-k "a and b"` survives as one argument.
[doc("[dev] run tooling python tests: no argument runs all four (kb_tools + liaison_tools + gen_defs + dupe_sweep); a surface argument (kb_tools, liaison_tools, gen_defs, dupe_sweep) runs only that one; any further arguments forward to pytest verbatim (flags, -k, a file::test path, ...)")]
test surface="" *pytest_args: _venv
    PYTHONPATH="{{PROJECT_ROOT}}" "{{VENV_PYTHON}}" -m pytest {{ \
      if surface == "" { "kb_tools/tests liaison_tools/tests tests devtools/tests" } \
      else if surface == "kb_tools" { "kb_tools/tests" } \
      else if surface == "liaison_tools" { "liaison_tools/tests" } \
      else if surface == "gen_defs" { "tests" } \
      else if surface == "dupe_sweep" { "devtools/tests" } \
      else { error("unknown test surface '" + surface + "' — valid values: kb_tools, liaison_tools, gen_defs, dupe_sweep; a leading flag binds here instead — pass it with an explicit empty surface: just test \"\" " + surface) } \
    }} "${@:2}"

FLAKE8_IGNORE := "E122,E201,E202,E203,E225,E226,E228,E261,E265,E302,E303,E501,E704,E731,W291,W293,W391,W503"
# `*paths` (positional-arguments, set above) arrives as "$@" with each path
# its own word, so a path containing a space still reaches every tool as one
# argument. No paths given reproduces today's four-surface, tool-by-tool
# argument order exactly — the order flake8 was already called with differs
# from black/isort's, and that difference is preserved rather than
# normalized away.
[doc("[dev] black-format, isort, flake8 the shipped python packages and the generator, or the given path(s) in place of all four")]
format-python *paths: _venv
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "$#" -eq 0 ]]; then
        black_isort_paths=(kb_tools liaison_tools tests gen_defs devtools)
        flake8_paths=(kb_tools liaison_tools gen_defs devtools tests)
    else
        black_isort_paths=("$@")
        flake8_paths=("$@")
    fi
    "{{VENV_PYTHON}}" -m black --line-length=120 "${black_isort_paths[@]}"
    "{{VENV_PYTHON}}" -m isort --profile black --line-length 120 "${black_isort_paths[@]}"
    "{{VENV_PYTHON}}" -m flake8 --ignore="{{FLAKE8_IGNORE}}" "${flake8_paths[@]}"


# The two duplication sweeps. One idea in two places is invisible inside either
# of them — nothing in a file reports a fact about two files — so it has been
# found here by adversarial multi-model review or by accident, and both are too
# expensive to be the standing instrument. These are the standing instrument.
#
# They EMIT CANDIDATES AND NEVER VERDICTS, and exit zero with findings on
# purpose: whether two sites are one idea is a judgment, and a gate here would
# be claiming it. Read the output, or hand it to a seat that will.
#
# Stdlib only under the system python3, like every other tool here, with
# PYTHONPATH at the repository root, the one import path every recipe uses:
# the sweep reads gen_defs's path constants, so the root must be on the path
# whatever else is. `--rev` sweeps a past tree.
[doc("[dev] list duplicated-prose candidates across templates/ — chunk bodies and template inline prose; trailing args forward to the sweep (--rev, --min-words, --coverage)")]
sweep-prose *args:
    PYTHONPATH="{{PROJECT_ROOT}}" python3 -m devtools.dupe_sweep prose "$@"

[doc("[dev] list one-idea-two-places candidates across kb_tools/ — structural twins, repeated constants, repeated docstring and comment rules; trailing args forward to the sweep (--rev, --min-words, --coverage)")]
sweep-python *args:
    PYTHONPATH="{{PROJECT_ROOT}}" python3 -m devtools.dupe_sweep python "$@"


# test-changed: run only the test surfaces a change touches.
#
# Changed paths are the uncommitted tree (`git status`: staged, unstaged and
# untracked, both sides of a rename) plus, when <base> is given, everything
# committed since it (`git diff base...HEAD`). Each path selects the surface
# its prefix names in TEST_SURFACE_MAP below; a path matching no row (docs,
# plans, scratch, kb-testing) selects nothing. There are no cross-surface
# "just in case" rows. The one exception is the runner itself: `justfile` and
# `python.just` select every surface, because a change to the `test` recipe
# cannot be validated by skipping it. With nothing selected, it says so and
# exits zero without running tests. Git is only read.
#
# One row per line: "<path prefix, or exact file> <surface | ALL>". A prefix
# ending in `/` matches everything under it.
TEST_SURFACE_MAP := "
gen_defs/ gen_defs
templates/ gen_defs
tests/ gen_defs
devtools/ dupe_sweep
kb_tools/ kb_tools
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
    all_surfaces=(kb_tools liaison_tools gen_defs dupe_sweep)
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
