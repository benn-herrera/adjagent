### Installing this repository

`just install-agents-here` installs this repository's own `.claude/` and `.opencode/` with the plain
`install` verb, once per harness, as base installs, naming this repository as TARGET and the
harness with `--harness`. opencode needs no tier map: its `default_tier_spec` stands in. Each install also keeps the agents-file
block current, in the user-global agents file where that holds a marker line and else in this
repository's `AGENTS.md`. The sticky rule is per ROOT, reads the router at both ROOT and the harness
directory, and reaches these two directories: one already holding a generated `skills/kbase/SKILL.md` would be a kb install
under this recipe too, and neither does. Under claude the install lands in the plugin,
`.claude/skills/adjagent/`, and the flat layout an earlier release wrote directly under `.claude/`
is removed by the same run, its package folders included, since this is a project install. No
include line is written here whatever the install type — `install_kb_include_line` returns without
writing when the project is this repository, which it can be only when running from a clone
(Packaging); from an installed package it writes the line for any project. Nor is one written for a harness whose
`project_harness_dir` is `.`: the install skips that call there, because a plugin is not a repo
project, so a mage kb install writes no include line and creates no `Makefile`.

