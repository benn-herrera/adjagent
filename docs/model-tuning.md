# Model tuning

Model-specific defensive text is delivered through **anchors and model families**. A definition may
expose an anchor at a spot where an observed failure mode needs a targeted note; with no tuning text
for the anchor in the loaded family, it renders as nothing, so the base definitions are identical to
an anchor-free render.

A family is a Python module under `devpro/families/`, one per model family, with its fields
documented in the docstring of `devpro/family.py`. It fills anchors with tuning text: family-wide
text, and member-scoped text for one member of the family's tier map inside the same module.
Resolution, not accumulation: at most one tuning text renders per anchor, member-scoped winning over
family-wide, and the filled text renders verbatim in place with no lead-in or wrapper. An author who
wants a lead-in writes it into the tuning text. A family can never replace, suppress or modify base
text; it only fills anchors.

## Rendering a tuned set

Tuned sets are rendered to order, typically out of repo, with `--family NAME`, where `NAME` is a
module name under `devpro/families/`. A bare model name is not a family name, and a path is not
accepted.

```sh
devpro install <target> [--plugin=NAME] [--family=NAME] [--model-tier-map=SPEC] [--model-pin-tier-alias-map=SPEC] [--harness=NAME]
```

Either plugin takes the same flags, and so does the `just install <target> [--plugin=NAME]` recipe in a
clone. `devpro install --help` gives each flag's grammar.

Two independent flags carry the tuning further:

- `--model-tier-map` overrides which family member each tier is tuned against. A bare value is the
  whole map in one word.
- `--model-pin-tier-alias-map` renders an alias in place of each tier's member. It takes no bare
  value, and under claude a bare one is refused as no `tier=value` pair. It serves a harness that
  remaps aliases itself, such as Claude Code's `ANTHROPIC_*` model variables: the agent names the
  alias, and tuning still follows the member.

Under opencode, `--model-tier-map=inherit` or `=default`, two words that render alike there, means
"the project's own model for every tier": each agent renders with no `model:` line and runs on
whatever that project has configured. That is opencode's default when `--model-tier-map` is not
given.

A changed family or map changes the rendered bytes, so an install with a different tuning proceeds
rather than reporting the target up to date ([Install reference](install-reference.md)).

Authoring a new family, or extending an existing one, is repository work: see
[Development](development.md#authoring-a-family).
