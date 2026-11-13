### Placeholders

Rendering is string formatting with named placeholders: a body's placeholders are filled per
harness and model family, and the result is written to one file per output path (Install, Renders
and copies). It departs from plain formatting in three places.

- Filled text is not rescanned, so a family's tuning text or a harness string cannot introduce a
  further placeholder.
- A placeholder standing as its own paragraph and filled with nothing leaves no empty paragraph, so
  the dropped paragraph leaves no gap in the rendered file.
- The spelling is `@!<namespace>-<key>!@`, not Python's `{name}`. The `@!…!@` spelling predates the
  bodies being plain Python strings; it was chosen so a placeholder cannot collide with
  format-string braces or inlined JSON.

The renderer fills one closed set of placeholders, spelled by `vocabulary.hole`: `@!hrn-<key>!@`
for the eight harness strings, the `HarnessText` members, which every harness supplies (agents file
name, project harness directory, project scratch directory, display name — the harness's name in
prose, which the `development` skill's attribution postscript names — user harness directory, MCP
tool prefix, `scratch_rule`, the agents file's rule for where scratch goes, and `memory_file`, the
agents file's name for the operator's own instructions file), and for the five harness-specific
paragraphs, the `OptionalHarnessText` members, each
a whole rule: `recipe_rule` (the rule a dispatched agent follows running recipes),
`kbase_project_rule` (how a kbase session locates its project where the server serves many),
`reload_rule` (what to do when an install's agents are not offered, in its own paragraph of the
`guide` skill's installation reference), `side_by_side_rule` (what to do where a claude install of any plugin the devpro project
ships also reaches an opencode session, in its own paragraph of that reference) and `cold_read_rule` (how a cold
reader is run, a whole bullet of the `development` skill's project-documents reference, naming
the `development` skill's script), which a
harness supplies as text or as the empty string, an empty one dropping the paragraph it stands in —
and `@!fam-<anchor>!@` for an anchor, an `Anchor` member (`gap-aversion`, `ask-vs-stipulate`; only
`ask-vs-stipulate` is exposed by a definition today).
A body of any kind may carry `@!plg-name!@` (`PluginText.NAME`, filled from `ctx.plugin.name`) where
the text must spell the plugin's name, such as the `devpro install --plugin=<plugin>` command.
The agents file alone also carries `@!agf-<key>!@` for its scope name and the package version. A
body of any kind may carry `@!tun-<key>!@` for a derived value, one computed from the `Render`'s
tier map and harness rather than supplied by either: `TuningText`'s one member, `step_down_model`,
which is `Render.step_down_model` (Harnesses and Families). A body or description may carry
`@!ref-<name>!@`, spelled by `vocabulary.reference` and written in definitions as
`clauses.ref(name=…)`, for a reference to another definition. Its closed set is the shipped set,
the definitions the render's plugin carries, each filled with
`Harness.reference_prefix` followed by the name; the prefix is `{plugin}:` under claude and mage and
`{plugin}-` under opencode, bound to the render's plugin, so a reference renders as `<plugin>:<name>` or
`<plugin>-<name>`. The map is built once per prefix and shipped set (`render._references`), not on
every fill. A plain reference to a definition outside the shipped set refuses the render, naming the
citing definition and the referent.

An **optional reference**, `@!opt-<name>!@`, spelled by `vocabulary.optional_reference` and written
`clauses.optional_ref(name=…)`, fills exactly as a plain one does where the referent ships. Where it
does not, it fills to nothing and its paragraph is dropped whole, with its blank line, as the
`tun` rule below drops one: the site is explicit, so no paragraph vanishes because of a plain
reference. It stands in a paragraph of its own, so the drop takes a bullet and not the heading
beside it. No definition text contains `@!` except as a placeholder.

`render.filled_text` fills a body in one pass over its paragraphs and does not rescan what it
filled, so a family's tuning text or a harness string cannot introduce a further placeholder;
`render.filled_body` runs that fill over a definition's own body, and `render.filled_description`
over its description, so the frontmatter an agent or skill renders carries the same fills (the
description is filled in `agent_fields` and `_field_lines`). A placeholder-shaped span naming no
key, a reference to an undiscovered name included, is refused, naming the definition and the span.
Each of four fills may leave nothing: an anchor the family does not fill, an `OptionalHarnessText`
member the harness supplies as the empty string, a derived value that is empty
(`step_down_model` where the step-down tier renders as the harness's inherit text), and an optional
reference to a definition the render does not ship. `filled_text`
drops a paragraph that fills to nothing, with its blank line. It drops a paragraph whose source
holds a `tun` placeholder that fills to nothing, an `OptionalHarnessText` placeholder that fills to
the empty string, or an optional reference that fills to nothing,
whatever else the paragraph says, so a sentence that cites the value goes with it. `Render.overlay` gives an anchor's text: the family's text for
the definition's tier-mapped member, else the family-wide text, else nothing (`family.py` states
the rules for authoring one).

