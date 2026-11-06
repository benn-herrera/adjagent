### Surfaces and layout

The repository exposes exactly three deployed surfaces, `agents/`, `commands/` and `skills/` — the
rendered-definition trees this repository's generation and validation mechanism governs. They are
names in the product, not directories in this repository: no render is kept here. Every definition
is produced to order into the output root an invocation names, so there is no checked-in copy for a
render to be served from, compared against, or drift away from. `agents/` and `commands/` hold one
file per definition. `skills/` holds one directory per definition of the skill kind —
`skills/<name>/SKILL.md`, then each supporting file that definition lists, beneath that directory
and nowhere else. Every project install places the docdicer tools package in `docdicer`'s own directory, and a kb
install also places its `kb-tools/` package in `kbase`'s; neither is a supporting file of its skill,
and the shipped-package paragraph below states what each is and where it sits. A `SKILL.md`'s frontmatter is `name` and `description`, the two fields every
harness reads, and the description is the whole of what a session sees before it loads the skill:
it carries the conditions under which the skill applies, so discovery needs no command of its own.
A supporting file has no frontmatter. A consuming project receives the install product — the three
surfaces together with the packages delivered alongside them by explicit mapping (below), the files
the installing harness ships (below), and, under claude and mage, `.claude-plugin/plugin.json`, the
manifest a plugin is discovered by, and, under claude, `hooks/hooks.json`, the guardrail's
registration, written only where the guardrail's install-time run succeeds, each rendered and neither
a surface nor a definition — by
**install**, one of two deployment shapes; the other, the mage plugin distribution (below), is a
release artifact an install builds and a consumer unpacks. Install has two types, and no
other:

```sh
just install <path-to-consuming-project> [--family=NAME] [--model-tier-map=SPEC] [--model-pin-tier-alias-map=SPEC] [--harness=NAME] [--subdir=DIR] [--install-global-agents-file] [--dry-run] [--verbose]
just install-with-kb <path-to-consuming-project> [the same arguments]
```

The installed package takes the same arguments as `adjagent install <path-to-consuming-project> […]`,
with `--with-kb` for the second type (Package and Command). `--dry-run` previews an install without
writing anything (Write Safety, below).

