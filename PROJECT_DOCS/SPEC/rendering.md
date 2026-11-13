## Rendering

A **model family** (`--family`) is a named group of models that assigns a model to each tier and may
add tuning text at anchors (below). A **tier map** assigns one model, the tier's **member**, to each
of five **tiers**, `highest`, `high`, `medium`, `low`, `lowest`, ordered by capability. An optional
**alias map** (`--model-pin-tier-alias-map`, a tier spec's syntax with no bare form) pins, per tier,
an alias rendered in place of the member; tuning text still follows the member. It serves a harness
that remaps aliases itself, such as `claude` through Claude Code's `ANTHROPIC_*` model variables.

A definition's **base text** is its untuned text. An **anchor** is a named place in it where a
model family may add **tuning text**. Family-wide tuning text applies at every tier. Member-scoped
tuning text applies only where the definition's tier resolves to one named member.

Every rendering of the definitions in the deployed surfaces has four observable properties:

- **Single-sourcing.** Text shared across two or more definitions has exactly one source. Wherever
  a rendered definition shares text with another, that text is identical.
- **No shared clause twice in one prompt.** No prompt delivers one shared clause, paragraph or list
  item twice. A prompt is one rendered definition taken together with the installed agents file, and
  for a command or skill also every rendered definition reached from it through `@<path>` lines,
  following on from each reached command or skill (an agent or supporting file reached loads
  nothing further); the agents file's own rendered definition is a prompt alone. The property covers a
  definition's base text; tuning text and harness strings, the harness-specific values rendering
  fills into a definition (a directory name, a tool spelling, the agents-file name), are not held
  to it.
- **Additive-only tuning text.** A model family's tuning text may extend a definition's base text at
  anchors; it can never replace, suppress, or fork that text. A definition whose anchors the loaded
  family does not fill is byte-identical, below its banner, to its base text rendered under the same
  harness and tier map. Base text may itself carry the step-down model: the model the `medium` tier
  renders with, the alias where an alias map is given; no family tuning text reaches it. It appears
  in a rendered definition only where that is not the harness's **inherit text**, what the harness
  renders for `inherit` or a synonym it declares (an **inherit word**), which tells the harness to
  use the session's own model, and nowhere else.
- **Tuning by tier, recorded in the rendered definition.** Every agent definition declares a tier,
  and the effective tier map, the one model source on every harness, resolves it: the tier's member
  is both what the definition is tuned against and the model it renders with. The tier map comes
  from the family, from a harness's default tier spec where it declares one, or whole from a **tier
  spec**, the text form of a tier map, given with `--model-tier-map`: comma-separated `tier=model`
  pairs naming all five tiers, or `all=<model>` with any tiers named as exceptions
  (`all=<model>,high=<model>`). One leaving a tier unnamed is refused, with no fallback to the
  family. The alias map has no default; the tuning line records both maps (below), so what a
  definition is tuned for and what it dispatches on may diverge. A bare tier spec — a value naming
  no tier and holding neither `=` nor `,` — has a third reading, the whole map with that one value
  for every tier, on a harness that reads it that way; a harness that does not refuses it as no
  `tier=value` pair. A harness declares the model shape a rendered model must have — a model outside
  it fails rendering before anything is written, naming the tier, the value, and the argument or
  family that supplied it — and the text each of its inherit words renders as, `inherit` among them;
  an empty rendering leaves the definition without a model line. Every rendered definition's tuning
  line, its `!TUNING!` line, records the family's name, the definition's tier and that tier's member
  (each `none` for a definition that declares no tier), the effective tier map, the alias map where
  one was given, the tiers whose member the family has no member-scoped tuning text for (as `stock=`), and the
  harness it was rendered for, so what it is tuned for and what it dispatches on are readable from
  the definition alone. Documents and commands declare no tier and stand outside this resolution;
  family-wide tuning text still fills their anchors. A family whose member-scoped tuning text names
  a member no tier reaches — in neither its own tier map nor the effective tier map — is refused
  before anything is rendered.

A cross-definition reference renders with the plugin's namespace under the harness: under claude and
mage `<plugin>:<name>` for an agent, a command or a skill, and under opencode `<plugin>-<name>`.
Apart from the plugin's name and the namespace it gives references, text differs between plugins only
by an optional reference's paragraph being present or absent.

References close within the shipped set, the definitions the render's plugin carries. A render in
which a definition refers to one outside that set is refused,
naming the definition that refers and the one it refers to, and nothing is written. An **optional
reference** is the one exception: where its referent does not ship, the paragraph holding it is
dropped whole, and the rest of the definition is unchanged.

An install renders the definitions under the tuning arguments it was given; Generated files, below,
holds whatever they are.

