## Generation System

The mechanism behind every definition in the deployed surfaces guarantees four observable
properties, independent of how they are implemented (see ARCHITECTURE.md):

- **Single-sourcing.** Text shared across two or more definitions has exactly one source. Wherever
  rendered output shares text across definitions, that text is identical by construction — not by
  maintenance discipline that could silently drift apart.
- **Single delivery.** No rendered prompt delivers one shared clause, paragraph or list item twice.
  A prompt is one rendered output, or a command or skill taken together with each output its
  `@<path>` lines name directly. The property covers a definition's base text; text added by a
  family's tuning, and a harness's names for its own paths and tools, are not held to it.
- **Additive-only model tuning.** A family's tuning may extend a definition's base text at declared
  anchor points; it can never replace, suppress, or fork that text. A definition whose
  anchors the loaded family does not fill is byte-identical, below its banner, to its base render
  under the same harness and tier map. Base text may itself carry a value taken from the tier map
  (the model a step-down names); no family tuning reaches it. The step-down default the process
  skill offers appears in a render only where the tier map pins a model for the `medium` tier, and
  nowhere else.
- **Tier-keyed tuning, with recorded provenance.** Every agent definition declares a tier —
  one of `highest`, `high`, `medium`, `low`, `lowest`, ordered by capability — and the family's tier
  map, the one model source on every harness, resolves it: the tier's family member is both what
  the definition is tuned against and the model it renders with. The tier map comes from the family,
  from a harness's default tier spec where it declares one, or whole from the tier-map argument. Each map argument covers all five tiers, naming each or
  giving one value for all and naming any exceptions; one leaving a tier unnamed is refused, with no
  fallback to the family. An optional alias map, with no
  default, renders an alias in place of each tier's member and changes nothing else, so what a
  definition is tuned for and what it dispatches on may diverge; it exists for a harness that
  resolves aliases through its own remapping, such as Claude Code's `ANTHROPIC_*` model variables,
  and any harness may use it. A tier-map value naming no tier and holding neither `=` nor `,` has a
  third reading — the whole map, that one value for every tier — on a harness whose vocabulary reads
  a bare value so; a harness whose vocabulary does not refuses it as no `tier=value` pair, and the
  alias map has no bare form anywhere. A harness declares the shape a rendered model must have — a
  model outside it fails the render before anything is written, naming the tier, the value, and the
  argument or family that supplied it — and the text each of its inherit words renders as, `inherit`
  among them; an empty rendering leaves the definition without a model line. Every generated
  definition's tuning line records the family's name, the tier map, the alias map where one was
  given, and the harness it was rendered for, so what it is tuned for and what it dispatches on are
  readable from the definition alone.
  Documents and commands declare no tier and stand outside this resolution; family-wide tuning text
  still fills their anchors. A family whose member-scoped tuning names a member no tier reaches — in
  neither its own tier map nor the effective one — is refused before anything is rendered.

A definition's reference to another definition renders with the installing harness's name for it:
under claude and mage the plugin's namespace, `adjagent:<name>` for an agent, a command or a skill, and the
bare name under opencode. A render under a harness differs from the same render without that prefix
at reference sites alone.

An install that requests a tuning other than the default (Deployed Surfaces, above) renders the
generated definitions under it; Generated-Definition Integrity, below, holds for the tuning the
install was given exactly as it holds for the default one.

