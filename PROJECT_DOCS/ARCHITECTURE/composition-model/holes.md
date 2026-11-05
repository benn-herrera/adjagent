### Holes

The renderer fills one closed set of holes, spelled by `vocabulary.hole`: `@!hrn-<key>!@` for the
seven harness strings, in two classes — the five `HarnessText` members, which every harness supplies
(agents file name, project harness directory, project scratch directory, user harness directory,
MCP tool prefix), and `OptionalHarnessText`'s two members, `recipe_rule` (the rule a dispatched
agent follows running recipes) and `kbase_project_rule` (how a kbase session locates its project where
the server serves many), which a harness supplies as text or as the empty string, an empty one
dropping the paragraph it stands in — and
`@!fam-<anchor>!@` for the family overlay anchors a definition exposes (`gap-aversion`,
`ask-vs-stipulate`). The agents file alone also carries `@!agf-<key>!@` for its scope name. A body of
any kind may carry `@!tun-<key>!@` for a tuning value, one computed from the render's tier map and
harness rather than supplied by either: `TuningText`'s one member, `step_down_model`, which is
`Render.step_down_model` (Harnesses and Families). A body or description may carry
`@!ref-<name>!@`, spelled by `vocabulary.reference` and written in definitions as
`clauses.ref(name=…)`, for a reference to another definition. Its closed set is the name of every
discovered definition, the agents file's text included, each filled with `Harness.reference_prefix`
followed by the name; the prefix is `""` for every harness today, so a reference renders as the bare
name. No prose in the repository contains `@!`.

`render.filled_text` fills a body in one pass over its paragraphs and does not rescan what it
filled, so a family's overlay text or a harness string cannot introduce a further hole;
`render.filled_body` runs that fill over a definition's own body, and `render.filled_description`
over its description, so the frontmatter an agent or skill renders carries the same fills (the
description is filled in `agent_fields` and `_field_lines`). A placeholder-shaped span naming
no key, a reference to an undiscovered name included, is refused, naming the definition and the span. Each of three fills may leave nothing: an
anchor the family does not fill, an optional harness text the harness supplies as the empty string,
and a tuning value that is empty (`step_down_model` where the step-down tier renders as the harness's
inherit text). `filled_text` drops a paragraph that fills to nothing, with its blank line. It drops a
paragraph whose source holds a tuning hole that fills to nothing whatever else the paragraph says,
so a sentence that cites the value goes with it. `Render.overlay` gives an anchor's text: the family's text for the definition's tier-mapped
member, else the family-wide text, else nothing (`family.py` states the rules for authoring one).

