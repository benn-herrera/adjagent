### Long recipe bodies are scripts

A recipe body of up to three command lines stays in the justfile; moving it to a script buys only
indirection. A recipe in a single-purpose runner file the justfile imports, such as `python.just`'s
`_venv`, is already broken out of the justfile and stays where it is, whatever its length. A longer
body is `devtools/scripts/<recipe-name>.sh`, and the justfile line hands it its variables as an env
prefix. The recipe keeps its name, parameters, `[doc]` string and dependency list; its body is one
line running the script, with each variable the script reads passed as `NAME="{{NAME}}"` ahead of
the command — `just` variables are not exported, so a script reads nothing it was not handed. The
line also passes the variables of the scripts it calls, which then inherit them; no script
re-passes an environment it was given. The script guards every variable the recipe hands it with
`: "${NAME:?...}"`, or `: "${NAME?...}"` where empty is a valid value (`EXE`), since `set -u`
catches unset and not empty — and that guard message holds no
apostrophe, because under the bash 3.2 this host runs as `/bin/bash`, a `'` inside a
`${NAME:?word}` opens a quote region and the script stops parsing. Arguments arrive as shell
positionals (`"$@"`), never as textual interpolation, which loses word boundaries. A note the body
needs travels with it into the script, beside the code it explains; the one-line recipe carries
only its `[doc]` string, which does not change because the body moved.
