### Installing this repository

`just install-agents-here` installs this repository's own `.claude/` and `.opencode/` with the plain
`install` verb, once per harness, as base installs. The sticky rule is per ROOT and reaches these
two directories: one already holding a generated `skills/kbase/SKILL.md` would be a kb install
under this recipe too, and neither does. No
include line is written here whatever the install type — `install_kb_include_line` returns without
writing when the project is this repository. Nor is one written for a harness whose
`project_harness_dir` is `.`: the install skips that call there, because a plugin is not a repo
project, so a mage kb install writes no include line and creates no `Makefile`.

