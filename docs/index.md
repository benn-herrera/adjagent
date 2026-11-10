# adjagent documentation

The [README](../README.md) holds what adjagent is and its quick start. These pages hold the rest.

- [Installing](installing.md): requirements, plugins, the Makefile recipe, the agents file, what to
  commit, previewing, updating, upgrading, running adjagent by hand, customizing the set.
- [Mage plugin release](mage-release.md): downloading, verifying and unpacking a mage plugin.
- [Install reference](install-reference.md): where `adjagent install` writes for each plugin, what it
  writes, `--dry-run` and the up-to-date report, refusals.
- [Guardrail](guardrail.md): the claude and opencode hooks that block shell writes behind the edit tools.
- [Agents file](agents-file.md): the operator-level working rules and how they are installed.
- [Model tuning](model-tuning.md): model families, anchors and the tier maps.
- [Definition sets](definition-sets.md): the agents and skills each plugin carries.
- [Knowledge base](knowledge-base.md): the kbase plugin, its requirements and its toolchain.
- [Development](development.md): building, testing, the repository layout, releasing the mage plugin,
  authoring a family.

The project's contract documents are trees under `PROJECT_DOCS/`:
[THESIS](../PROJECT_DOCS/entry-point.md), [SPEC](../PROJECT_DOCS/SPEC/entry-point.md),
[ARCHITECTURE](../PROJECT_DOCS/ARCHITECTURE/entry-point.md) and
[CONVENTIONS](../PROJECT_DOCS/CONVENTIONS/entry-point.md).
