"""docdicer: the skill that dices markdown into trees of small linked files, and undices them, through
the launcher shipped beside it in `tools/`."""

from adjagent import clauses
from adjagent.definition import Definition
from adjagent.vocabulary import Kind

DEFINITIONS = (
    Definition(
        name="docdicer",
        kind=Kind.SKILL,
        description=(
            "Use when a markdown document is to be diced into a tree of small linked files or a diced tree "
            "undiced back into one document, when a project's contract documents are to be diced or a diced "
            "tree's links and structure checked, when a plan or design has grown too large to read whole, "
            "when a plan's status form is to be checked (`check-plan`), or when the project's kanban board "
            "is to be shown (`kanban`); NOT for ordinary markdown editing, a leaf of a diced tree included."
        ),
        body=f"""## When

- **Dice** a project's contract documents when the user or the project's own documents call for it,
  and a plan or design too large to read whole.
- **Undice** a diced plan, design or document for a whole-body revision, which one document serves
  more efficiently and effectively than a tree: undicing repacks the tree into one monolith document,
  not necessarily in the original's exact formatting, so it is no stand-in for the original where
  exact formatting matters; from then on the undiced document and its tree convert into each other
  exactly. General process: undice to a new monolithic document (it will not overwrite an existing one).
  If the monolith was modified you can re-dice it back to another doc tree.
- **An undice that does not dice back to the same tree** names the leaves that would dice
  differently. Fix the tree, then undice again to a new monolith name (the failed one stays until
  the user directs its removal). A leaf holding a heading at a level the dicer splits on: make that
  heading a bold run-in title opening its paragraph, or fold it into the text around it, changing
  no wording (do not run `refactor` on the result; it turns run-in titles back into headings). A
  leaf whose heading disagrees with its file name: edit the heading to match the name, not the
  file, which would move the path. A changed tree shape is never the accepted cost of an undice,
  because other documents cite the tree's paths and a split moves them.
- After each operation, both versions remain. Removing the one(s) no longer wanted is a separate step,
  taken at the user's direction.

`kb-root/` and everything under it belongs to the `{clauses.optional_ref(name="kbase")}` skill: do not
dice, undice or link-check any of it unless the user directs that for it specifically.

## The script

Where the project's justfile or Makefile includes a `docdicer.just` or `docdicer.mk` snippet, use
its recipes in place of `tools/docdicer`: `just docdicer <arguments>` or
`make docdicer DOCDICER_ARGS='<arguments>'`, and `docdicer-check-plan` by name under either.
`docdicer-check-plan` checks the active plan only; check another plan with
`just docdicer check-plan <path>` or `make docdicer DOCDICER_ARGS='check-plan <path>'`.

Without those recipes, docdicer runs through `tools/docdicer` in this skill's directory, which
passes its arguments to docdicer; run the script by its path under that directory, and check a plan
with `tools/docdicer check-plan <path>`. Its first run installs docdicer beside it, which needs `git`
and the network. `tools/docdicer --help` is the command list, and `tools/docdicer <command> --help`
gives each command's arguments. Where this skill's directory has no `tools/docdicer`, as under a
user-level install, a project install provides it.

`kanban` serves a live board of the project's roadmap, design and plan until stopped; give the user
the command to run rather than running it yourself: `docdicer-kanban` where the recipes are
included, `tools/docdicer kanban` without them. `tools/docdicer kanban --help` gives the details.""",
    ),
)
