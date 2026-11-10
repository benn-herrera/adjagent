### Installing this repository

`just install-agents-here` installs this repository's own `.claude/` and `.opencode/` with the plain
`install` verb, once per harness, as the devpro plugin, naming this repository as TARGET and the
harness with `--harness`. opencode needs no tier map: its `default_tier_spec` stands in. Each
install also keeps the agents-file block current, in the global agents file where that holds
a marker line and else in this repository's `AGENTS.md`. Under claude the install lands in the
plugin, `.claude/skills/devpro/`, and under opencode in `.opencode/plugins/devpro/`.
`install_kb_include_line` returns without writing when the project is
`REPO_ROOT`, which is set only in a checkout (Packaging). Nor is one written for a harness-directory plugin
(mage, whose `project_harness_dir` is `{plugin}` and whose `user_harness_dir` is `.`): the install
skips that call there, so a mage install of the kbase plugin writes no include line and creates no `Makefile`.
