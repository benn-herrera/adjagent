"""docdicer: the skill that dices markdown into trees of small linked files, and undices them, through
the launcher shipped beside it in `tools/`."""

from adjagent.definition import Definition
from adjagent.vocabulary import Kind

DEFINITIONS = (
    Definition(
        name="docdicer",
        kind=Kind.SKILL,
        description=(
            "Use when a markdown document is to be diced into a tree of small linked files or a diced tree "
            "undiced back into one document, when a project's contract documents are to be diced or a diced "
            "tree's links and structure checked, when a plan or design has grown too large to read whole, or "
            "when the user asks to install docdicer; NOT for ordinary markdown editing, a leaf of a diced "
            "tree included."
        ),
        body="""## When

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

## The script

docdicer runs through `tools/docdicer` in this skill's directory, which passes its arguments to
docdicer; run the script by its path under that directory. `tools/docdicer --help` tells you where
you stand:

- **It says docdicer is not installed here.** Offer `tools/docdicer --install`, which installs
  docdicer beside the script and needs `python3` 3.9 or later, `git` and the network. Run it only
  when the user directs you to.
- **It prints docdicer's usage.** docdicer is installed, and that usage is the command list:
  `tools/docdicer <command> --help` gives each command's arguments.

`kanban` serves a live board of the project's roadmap, design and plan until stopped; give the user
the command to run rather than running it yourself. `tools/docdicer kanban --help` gives the
details.

## Runner recipes

`tools/runner-snippets/` in this skill's directory holds `docdicer.just` and `docdicer.mk`, each giving a
project's runner two recipes: `docdicer`, which passes its arguments to docdicer, and `docdicer-check`,
which checks every link under its roots, then that every file of its tree is listed and reachable. The
tree defaults to `PROJECT_DOCS` and the roots to `PROJECT_DOCS *.md`; for another tree, pass `tree` and
`roots` (`DOCDICER_TREE` and `DOCDICER_ROOTS` for make).

- **The project has a justfile or Makefile and the user wants docdicer recipes.** Offer one line for
  that file, `<dir>` being this skill's directory relative to the project root:
  `import? '<dir>/tools/runner-snippets/docdicer.just'` in a justfile,
  `-include <dir>/tools/runner-snippets/docdicer.mk` in a Makefile. Add it only when the user directs
  you to.
- **The project's runner includes the snippet.** Run docdicer as `just docdicer <arguments>` or
  `make docdicer DOCDICER_ARGS='<arguments>'`, not by `tools/docdicer`, and run `docdicer-check` after
  editing a diced tree.""",
    ),
)
