### Holes

The renderer fills one closed set of holes, spelled by `vocabulary.hole`: `@!hrn-<key>!@` for the
seven harness strings, in two classes — the five `HarnessText` members, which every harness supplies
(agents file name, project harness directory, project scratch directory, user harness directory,
MCP tool prefix), and `OptionalHarnessText`'s two members, `recipe_rule` (the rule a dispatched
agent follows running recipes) and `kbase_project_rule` (how a kbase session locates its project where
the server serves many), which a harness supplies as text or as the empty string, an empty one
dropping the paragraph it stands in — and
`@!fam-<anchor>!@` for the family overlay anchors a definition exposes (`gap-aversion`,
`ask-vs-stipulate`). The agents file alone also carries `@!agf-<key>!@` for its scope name and its
coder-dispatch bullet, a harness callable taking the rendered default family's medium tier where the
harness can choose a model per dispatch, and `None` where it cannot, which drops the paragraph. No
prose in the repository contains `@!`.

`render.filled_text` fills a body in one pass over its paragraphs and does not rescan what it
filled, so a family's overlay text or a harness string cannot introduce a further hole;
`render.filled_body` runs that fill over a definition's own body. A placeholder-shaped span naming
no key is refused, naming the definition and the span. Each of three fills may leave nothing: an
anchor the family does not fill, an optional harness text the harness supplies as the empty string,
and the agents file's coder-dispatch bullet where the harness cannot choose a model per dispatch
(`coder_dispatch` is `None`). `filled_text` drops a paragraph that fills to nothing, with its blank
line. `Render.overlay` gives an anchor's text: the family's text for the definition's tier-mapped
member, else the family-wide text, else nothing (`family.py` states the rules for authoring one).

