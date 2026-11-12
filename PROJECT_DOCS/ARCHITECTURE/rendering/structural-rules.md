### Structural rules

The substitution-depth, shared-paragraph and prompt checks fix the properties in SPEC.md, Rendering; the clause
group check holds a group's shared clauses. Each is a test in the suite (`just test devpro`).
`render` runs none: a syntax-tree analysis has no place on an operator's machine of unknown Python.
The sweeps that read rendered text run per plugin (`_PLUGIN_RENDERS`), each plugin's definitions as it
ships them, so a paragraph an optional reference drops from one plugin is judged in the other, and
each prompt takes its own plugin's agents file.

- **Substitution depth is one.** `tests/_structure.py` walks the syntax trees of the definition
  modules and `clauses.py`. A module-level constant is a string literal or an f-string over
  constants in the same module, never a call. The only calls in a definition module are
  `Definition(...)` in `DEFINITIONS`, `SkillFile(...)` as a `files=` element, and, inside a `body=`
  or `description=` value or a `SkillFile` body, `clauses.<name>(...)` and `<constant>.format(...)` on a
  string-literal constant, every argument a literal or a constant. A
  `Definition(...)` call takes keyword arguments only. A `clauses.py` function takes at most three keyword-only parameters and returns one string over its
  parameters and constants, with no call. A chain of constants cannot defeat the depth, because
  nothing a call returns can be bound to a constant or passed as an argument: a slot constant is always
  fixed text, and filling a slot constant is the last substitution. Every `SkillFile` body is walked under the
  `body=` rule, so a supporting file takes shared text from `clauses` as a definition body does and
  cannot carry a call of its own — a `SkillFile` path is a string literal and nothing else. The same
  walk confirms a definition module's top level holds only imports, string constants and
  `DEFINITIONS`.
- **A paragraph two rendered definitions share has one source.** `tests/test_devpro.py` renders
  every definition twice, once as written and once with each `clauses` constant, function and
  private constant standing as a sentinel, and fails on a paragraph or list item that survives both
  in two rendered definitions: it was written out rather than taken from a constant. A skill is
  swept the same way, each of its files walked as a rendered definition in its own right and
  labelled by the path it renders to, so a paragraph a skill entry file and a supporting file both
  carry is found as readily as one two definitions share.
- **No shared clause twice in one prompt.** `tests/test_devpro.py` runs two checks over every
  prompt, and fails on either.
  - A prompt is one rendered definition taken together with the installed agents file; the agents
    file's own rendered definition is a prompt alone. A command or a skill entry file also takes
    each rendered definition an `@<path>` line in its text names, and follows the `@` lines of each
    such rendered definition that is itself a command or a skill entry file, transitively; a
    skill's supporting file does not load what it names. A line names a rendered definition when
    its path ends in that definition's rendered path.
  - Each shared clause is reached once. The check reads the source, so it sees a clause through the
    clauses that compose it. A clause passed to a text function counts once for each time the
    function interpolates it. A repeat is reported with both paths to it.
  - Each paragraph or list item appears once. The check reads the rendered text, filled under the
    claude rendering, collapsed as in the check above, and counts across every rendered definition
    in the prompt.
  - A `clauses.py` constant that only fills a placeholder, of any kind, is not counted by the first
    check.
- **A clause group's members carry what the group carries.** A clause group is the definitions
  whose own `Definition(...)` call names its membership clause: `CODE_PRINCIPLES_CODER` for the
  coders, `CODE_PRINCIPLES_PLATFORM` for the platform experts. `tests/test_clause_groups.py` holds,
  per group, the member list, the plain entries (clauses every member carries) and the alternative
  entries (two clauses, exactly one carried), and `EXEMPTIONS`, a `(definition, clause)` to reason
  map admitting one member's omission of one plain entry. `carried_clauses` in `tests/_structure.py`
  reads the source: a definition carries a clause when its `Definition(...)` call names
  `clauses.<name>`, called or read. A clause reached only inside another constant is not carried.
  The test fails on any of these, each message naming what it concerns:
  - a member lacks a plain entry and has no exemption, or carries both or neither of an alternative
    pair;
  - a listed member does not carry the membership clause, or a definition outside the member list
    carries it;
  - an exemption is stale (its definition is not a member, or it now carries the clause) or names
    something that is not a plain entry;
  - a table names a clause `clauses.py` does not define;
  - `check_clause_groups` places agents: an agent is in no group and not in `UNGROUPED`, an agent
    is in both a group and `UNGROUPED`, or `UNGROUPED` names a definition that is no agent.

