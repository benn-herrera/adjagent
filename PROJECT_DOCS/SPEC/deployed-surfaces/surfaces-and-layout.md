### Surfaces and layout

The repository exposes exactly three deployed surfaces, `agents/`, `commands/` and `skills/`: the
trees of rendered definitions, and one part of the install product (below). Every definition is
produced to order into the output root an invocation names: `devpro render --out <dir> [--plugin=NAME]`
renders the plugin's definitions (Plugins) into `<dir>`, an existing directory, and `install` renders
into its install directory (Install destination). `agents/` holds one file per agent and per
**document**, a definition agents read but never dispatch; `commands/` holds one file per command.
The supported harnesses are `claude` (Claude Code), `opencode` and `mage` (Mage, an agent harness);
`--harness` takes these names. The supported model families are `claude`, the default, `gemma-4` and
`qwen3`; `--family` takes these names (Rendering). `skills/` holds one directory per definition of
the skill kind — `skills/<name>/SKILL.md`, the **skill entry file**, then its supporting files,
beneath that directory and nowhere else. A project install places each shipped package in the
directory of the skill it belongs to, where that skill ships:
- the docdicer tools package — the launcher for docdicer, a separately published tool that dices a
  markdown document into a tree of linked files — in the `docdicer` skill's own directory;
- the development scripts package — a script that runs one agent on a brief with no tools — in the
  `development` skill's;
- the kb-tools package in the `kbase` skill's.

None is a supporting file of its skill; what each is and where it sits is in SPEC.md, Deployed
Surfaces, Shipped files. Under claude and mage a skill entry file's frontmatter is `name` and
`description`, the two fields every harness reads; under opencode the surfaces sit inside the
plugin directory (Install destination) with no frontmatter, beside the registry `registry.json`
and `index.ts`, opencode's **plugin entry**, the file that registers it, and a skill entry file's `name` and `description` come from the registry. The
description is the whole of what a session sees before it loads the skill: it carries the conditions
under which the skill applies, so discovery needs no command of its own. A supporting file has no
frontmatter. A consuming project receives the install product — the three deployed surfaces
together with the shipped packages delivered alongside them, each at its package destination
(Shipped files), the harness resources (Shipped files), and the harness-rendered files: under claude
and mage `.claude-plugin/plugin.json`, the plugin manifest, and `.mcp.json` where `kbase` ships;
under claude `hooks/hooks.json`, the guardrail registration, written only where one trial run of the
guardrail at install time, the install-time probe, succeeds; under opencode `registry.json` (Shipped
files). Each is rendered and neither a deployed surface nor a definition. It arrives by **install**,
one of two distribution channels; the other, the mage release (SPEC.md, Mage Release), is unpacked
by an operator. Install delivers one plugin, `devpro` or `kbase`, and no other. Its usage:

```sh
devpro install TARGET [--plugin=NAME] [--harness=NAME] [--subdir=DIR] [--family=NAME] [--model-tier-map=SPEC] [--model-pin-tier-alias-map=SPEC] [--dry-run] [--verbose]
```

Plugins states `--plugin`'s default. From a checkout of this repository the same command runs as
`PYTHONPATH=<clone> python3 -m devpro install …`, with the same result (Package and Command).
`--dry-run` previews an install without writing anything (SPEC.md, Write Safety).
