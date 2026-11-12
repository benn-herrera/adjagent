# THESIS - devpro

What this project is and why

This thesis does not:

- Design user-facing behaviors or outcomes, that belongs to SPEC
- Put forth project mechanisms or code structure, that belongs to ARCHITECTURE
- Dictate project-specific process, that belongs to CONVENTIONS

## devpro in plain terms

devpro generates a set of agent, command and skill definitions — the instruction files a coding
harness such as Claude Code, opencode, or a general harness application like Mage loads — and installs
them into a project, or into a user's own harness setup. The definitions are written in Python as string
constants; text several definitions share is written once and filled into each; the result is
rendered per harness and per model family (a line of models, such as Claude's), and copied into the
harness's directory. Each agent names a tier — the capability level it needs — and a tier map names
the model for each tier: the family's own, unless the harness or the operator supplies another.

Almost all of that is assembled from well-known building blocks, used at small scale. Two results
are new, and they are the reason the project exists. This page names both, so that work on a
standard piece gets the standard answer and attention goes to the new ones.

## The building blocks

Each row names the standard pattern a piece is most like. The last column names the larger system
the piece resembles and is not — the direction work on it must not drift.

| devpro piece | Most like | It is not |
|---|---|---|
| Definitions | A Python module per agent, command or skill, holding string constants | A DSL or a prompt framework |
| Shared text | Named string constants, referenced by name from the definitions that carry them | A macro engine |
| Rendering | String formatting with named placeholders, filled per harness and model family and written to files | A template engine or a compiler |
| Harnesses | A profile per harness: its paths, file names, frontmatter or registry shape, the paragraphs it carries and the strings it fills in | A plugin framework |
| Plugins | A package group: a named list of definitions, one module each, that an install delivers whole | A dependency resolver |
| Model tuning | A table of model names per tier for each model family, and text added at anchors — named points in a definition's text | A prompt optimiser or an evaluation system |
| Install | A deploy step: each harness has its own layout, and the rendered files are copied to the places and names that layout gives | A package manager |
| The agents file | A marked block in the `AGENTS.md` (or `CLAUDE.md`) a harness loads into every session | A configuration layering system |
| Installed resources | Files the install copies into place: helper scripts, hook scripts | A dependency installer |

Where a piece is in this table, its conventional answer is the default. A design that grows a piece
toward its "is not" column is out of scope, however natural the next step looks.

## What is new

Two things, and only these. The machinery behind both is standard, and listed above.

**Shared text exists once.** Agents in a set share text because they must share behaviour: a rule
stated to one agent and not its neighbour is two agents that will act differently in the same
situation, and agents that hand work to one another — an architect's design, the coder who builds
it, the reviewer who checks it — hold their handoffs only by judging to the same standard. In
hand-kept files nothing shows that ten agents got a rule and the eleventh did not; the gap surfaces
later, in unrelated work. Here a span several definitions share is one constant, and every
definition is rendered from it, so two copies of a shared clause cannot disagree, and which agents
must carry it is declared, not remembered.

**One source renders to order.** The same definitions can render, on demand, for any supported
harness and model family. A harness selects which harness-specific
paragraphs it carries, and supplies its own layout and names. A family supplies its default model
for each tier, and may add text at anchors but never replace or remove a definition's base text.

Volumes:

- [SPEC](SPEC/entry-point.md): The devpro project renders agent, command and skill definitions to order, for any supported harness and model family, from one source in which shared text is written once; the two plugins it ships, consumed by other projects, are its flagship renderings.
- [ARCHITECTURE](ARCHITECTURE/entry-point.md): How the generation system, and the agent and skill set it ships, are built to satisfy SPEC.md.
- [CONVENTIONS](CONVENTIONS/entry-point.md): House rules and project-specific traps only.
