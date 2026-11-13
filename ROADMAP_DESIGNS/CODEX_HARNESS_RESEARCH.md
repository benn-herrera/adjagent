# Codex CLI as a devpro install target — research report

Date: 2026-11-13. Codex version examined: `rust-v0.168.0` (marked Latest on the releases page,
13 Nov 2026). Source reads are of `github.com/openai/codex` at that tag. The docs at `developers.openai.com/codex/*` now 308-redirect
to `learn.chatgpt.com/docs/*`; URLs below are the redirect targets. **[inferred]** marks anything
not read from a source.

## Verdict

**Feasible with gaps.**

**Delegation: yes, built in, on by default.** A custom agent is a standalone TOML file in
`.codex/agents/` (project) or `~/.codex/agents/` (user). The file has `name`, `description` and
`developer_instructions` (the body), plus optional `model` and `model_reasoning_effort`. The parent
session sees every role's name and description in the `spawn_agent` tool description and spawns one
with `agent_type = <name>`. The child starts with a fresh context unless the parent forks. Results
come back to the parent through `wait_agent`. Model selection per agent works: a `model` set in the
role file is locked, and the spawn tool tells the parent "This role's model is set to `X` ... cannot
be changed".

Gaps, in order of cost:
1. **No per-agent tool allowlist.** A role can only switch off `shell_tool`, `apps`, `plugins`,
   `memories` and `request_permissions_tool`. It cannot remove `apply_patch` (edits) or `web_search`,
   and it cannot set `sandbox_mode`, `approval_policy`, `model_provider` or `mcp_servers`. Codex has
   no separate read, grep or glob tool, since reading goes through the shell. So devpro's read-only
   seats (reviewers, scouts) can't be enforced: dropping the shell drops reading too. Their `tools:`
   become advisory under Codex.
2. **No single install directory.** Agents go in `.codex/agents/`, skills in `.agents/skills/`,
   hooks in `.codex/hooks.json`, and MCP servers in `.codex/config.toml`, which is a file the
   operator shares. A Codex *plugin* can bundle skills, MCP, hooks and commands, but no field in its
   manifest carries agents, and plugins install through a marketplace into
   `~/.codex/plugins/cache/`. devpro's `plugin_dir` model doesn't fit. This needs either a
   multi-root install or plugin plus loose agents.
3. **A third `definition_form`.** An agent body sits inside a TOML string (`developer_instructions`)
   instead of under frontmatter or in a registry. devpro's `Harness.definition_form` holds exactly
   `FrontmatterForm` or `HarnessFile`, so a per-file TOML envelope is a new form. It also needs a
   correct TOML string serializer. Python stdlib only reads TOML (`tomllib`).
4. **Documents (read, never dispatched) have no home.** Any `*.toml` under `agents/` becomes a
   spawnable role, and there is no hidden flag.
5. **Commands.** Custom prompts are deprecated and user-level only. Commands would have to render
   as skills.
6. **Models are Responses-API only.** `wire_api = "chat"` was removed, and a role cannot change the
   provider. All tiers must therefore come from the parent session's single provider.
7. **Trust gates.** Project `.codex/` layers, which hold the agents, hooks and MCP, load only in a
   trusted project. Hooks also need per-hook review (`/hooks`) before they run. `.codex` and
   `.agents` are read-only to Codex itself under `workspace-write`, so an in-session devpro install
   or update needs escalation.
8. **AGENTS.md has no `@` imports** and a 32 KiB combined cap.
9. **Surface churn.** The project is pre-1.0 with several alpha builds a day, and several
   breaking config changes landed in 2026 (see item 8 below).

None of these is the pi-style blocker. Delegation is first-party, stable and default-enabled.

## The deciding question: delegation

- **Feature status.** Subagents are enabled by default (`agents.enabled` defaults to `true`).
  - Source: https://learn.chatgpt.com/docs/agent-configuration/subagents
  - The default tool surface is "multi-agent v1": feature `multi_agent`, `Stage::Deprecated` as a
    *flag* name, `default_enabled: true`. "Multi-agent v2" (`multi_agent_v2`) is `Stage::Stable`,
    `default_enabled: false`.
  - Source: `codex-rs/features/src/lib.rs` @ rust-v0.168.0. The 0.168.0 release notes say setting
    `features.multi_agent` now warns and points to `agents.enabled`
    (https://github.com/openai/codex/releases, #59479).
- **Built-in roles.** `default`, `worker` and `explorer`. A custom role with the same name replaces
  the built-in (`codex-rs/core/src/agent/role.rs`).
- **File and location.** One TOML file per agent.
  - Discovery is per config layer: `<config_folder>/agents/`, walked **recursively**, `*.toml`,
    sorted (`codex-rs/agent-roles/src/discovery.rs`, `loader.rs`).
  - The layers are user `~/.codex/` (`CODEX_HOME`) and project `.codex/`. The project layer loads
    only for a trusted project.
  - Because the walk is recursive, `~/.codex/agents/devpro/*.toml` would work for a per-plugin
    subdirectory.
  - The role's identity is the `name` field, not the file name. A duplicate name in the same layer
    is an error. A higher layer overrides a lower one.
- **Fields** (`codex-rs/agent-roles/src/agent_role_config.rs`, `RawAgentRoleFileToml`,
  `deny_unknown_fields` with flattened `ConfigToml`):
  - Required: `name`, `description` (non-blank), `developer_instructions` (non-blank).
  - Optional: `nickname_candidates` (ASCII letters, digits, space, `-`, `_`).
  - Any `config.toml` key is accepted, but only these are applied (`role.rs`,
    `AgentRoleOverrides`): `developer_instructions`, `model`, `model_reasoning_effort`,
    `model_reasoning_summary`, `model_verbosity`, `personality`, `service_tier`, `features.*` set to
    `false` (only for the five features listed under gap 1), and `skills` used to disable skills.
  - The docs confirm that `sandbox_mode`, `approval_policy`, `model_provider` and `mcp_servers`
    "don't override the parent configuration" (subagents page).
- **Dispatch** (`codex-rs/core/src/tools/handlers/multi_agents/spawn.rs`, v1):
  - `spawn_agent` takes `{message | items, agent_type?, model?, reasoning_effort?, fork_context:
    bool = false}` and returns `{agent_id, nickname}`.
  - The other v1 tools are `send_input`, `wait_agent`, `resume_agent` and `close_agent`.
  - The `agent_type` description is built from all roles:
    `Available roles:\n<name>: {<description>[\n- This role's model is set to ...]}`
    (`role.rs`, `spawn_tool_spec`).
  - Under v2 (opt-in), `task_name` is required and `fork_turns` defaults to `all`, which gives the
    child the parent's full history (`multi_agents_v2/spawn.rs`). Under v2 a devpro dispatch would
    need to say `fork_turns: none` to get a clean context. The v2 tools are `spawn_agent`,
    `send_message`, `followup_task`, `wait_agent`, `list_agents` and `interrupt_agent`.
- **Model precedence.** A role file's `model` or `model_reasoning_effort` wins. Otherwise the spawn
  argument applies, then `[agents] default_subagent_model` / `default_subagent_reasoning_effort`,
  then the parent's (subagents page). A role that sets `model` but not effort keeps the inherited
  effort.
- **Limits.**
  - `agents.max_concurrent_threads_per_session` (legacy `max_threads`) defaults to 6.
  - `agents.max_depth` defaults to 1, so a subagent cannot spawn its own: "Agent depth limit
    reached" (`codex-rs/core/src/config/mod.rs`, `DEFAULT_AGENT_MAX_DEPTH = 1`). Claude Code also
    allows no nesting **[inferred from general knowledge; not checked here]**.
- **Results.** "The main thread collects the subagent results into its final response" (subagents
  page). `wait_agent` returns the final status and does not close the agent; `close_agent` frees the
  slot (secondary: https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/handlers/multi_agents.rs).
- **Approvals.** Subagents inherit the parent's sandbox and approval mode. In non-interactive runs,
  an action that needs new approval fails back to the parent (subagents page).

Conclusion: delegation can carry devpro's dispatch reliably. A named agent gets its own
instructions and model. Its own tool set is enforced only coarsely.

## The eight answers

### 1. Skills
- **Format.** A directory containing `SKILL.md` with YAML frontmatter.
  - `name`: at most 64 characters; defaults to the directory name if absent.
  - `description`: required, folded to one line.
  - Optional `metadata.short-description`.
  - Malformed scalar YAML is repaired line by line.
  - Source: `codex-rs/skills/src/parser.rs` @ rust-v0.168.0.
- **Optional folders and metadata.** `scripts/`, `references/`, `assets/`, and
  `agents/openai.yaml` (UI metadata; `policy.allow_implicit_invocation`, default `true`;
  `dependencies.tools`). Source: https://learn.chatgpt.com/docs/build-skills
- **Locations.**
  - Repo: `$CWD/.agents/skills` and each parent up to `$REPO_ROOT/.agents/skills`.
  - User: `$HOME/.agents/skills`.
  - Admin: `/etc/codex/skills`.
  - System skills are bundled.
  - Symlinked skill folders are followed.
  - Two skills with the same name are not merged; both are listed.
  - Source: same page.
- **Loading.** Progressive disclosure: only name and description are loaded up front, and the
  full `SKILL.md` on selection. The initial list is capped at 2% of the context window or 8,000
  characters (`skills.max_context_tokens`, up to 10,000). Invocation is implicit by description, or
  explicit with `$name` or `/skills`. Disabling is via `[[skills.config]]` in `config.toml`.
- **Plugin skills.** These live under the plugin's `skills/`. The manifest `name` is "the plugin
  identifier and component namespace" (https://developers.openai.com/codex/plugins/build). The
  rendered form of a namespaced skill name (for example `devpro:x`) was not found
  **[unknown]**.

### 2. Slash commands and custom prompts
- Custom prompts are **deprecated** ("Use skills for reusable instructions"). They are **user-level
  only**: `~/.codex/prompts/*.md`, top level only.
  - Frontmatter: `description`, `argument-hint`.
  - Placeholders: `$1`–`$9`, `$ARGUMENTS`, named `$FILE`, and `$$`.
  - Invoked as `/prompts:<name>`.
  - Source: https://learn.chatgpt.com/docs/custom-prompts
- Plugin `commands` (a Claude-compatible manifest field) are **migrated into skills**: the
  `source-command` prefix, names capped at 64 characters, and a description taken from frontmatter
  (`codex-rs/core-plugins/src/command_migration.rs`, `manifest.rs` `commands` field).
- There are no project-level commands. devpro commands would render as skills, with
  `allow_implicit_invocation: false` in `agents/openai.yaml` to make them explicit-only
  **[inferred mapping]**.

### 3. The agents file (`AGENTS.md`)
- **Global level.** The first non-empty of `~/.codex/AGENTS.override.md` or `~/.codex/AGENTS.md`.
- **Project level.** Walks from the Git root down to the working directory, taking at most one file
  per directory: `AGENTS.override.md`, then `AGENTS.md`, then the names in
  `project_doc_fallback_filenames`. Files are concatenated root-first, separated by blank lines.
  Inclusion stops at `project_doc_max_bytes`, which defaults to 32 KiB.
  - Sources: https://learn.chatgpt.com/docs/agent-configuration/agents-md and
    `codex-rs/core/src/config/mod.rs` (`AGENTS_MD_MAX_BYTES = DEFAULT_PROJECT_DOC_MAX_BYTES`).
- **No `@` imports.** Open feature requests: https://github.com/openai/codex/issues/6038 (open,
  updated 2026-05-03) and https://github.com/openai/codex/issues/17401 (open, updated 2026-10-20).
- **Effect on devpro.** devpro's own `CLAUDE.md`→`@AGENTS.md`→`@PROJECT_DOCS/...` chain does not
  expand under Codex. A devpro-marked block in `AGENTS.md` works, but anything it reaches by `@` is
  inert text.

### 4. Plugins, hooks, and the guardrail
- **Plugins.** The manifest is root `plugin.json` ("Agent Plugins", portable), or
  `.codex-plugin/plugin.json` as a fallback. `.claude-plugin/plugin.json` is also accepted.
  - Components: `skills/`, `mcp.json`/`.mcp.json` (`mcpServers`), `hooks/hooks.json`, `apps`,
    `commands`. There is no `agents` field (`codex-rs/core-plugins/src/manifest.rs`).
  - Plugins are distributed via a marketplace: `$REPO_ROOT/.agents/plugins/marketplace.json`,
    `~/.agents/plugins/marketplace.json`, or the legacy `$REPO_ROOT/.claude-plugin/marketplace.json`.
  - Installed copies go to `~/.codex/plugins/cache/$MARKETPLACE/$PLUGIN/$VERSION/`.
  - Codex sets `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` for hooks.
  - Plugin hooks are "supported only for plugins installed manually in Codex desktop" and are not
    auto-trusted.
  - Source: https://developers.openai.com/codex/plugins/build
- **Hooks.** These are stable and on by default (`features.hooks`, `Stage::Stable`).
  - Events: `PreToolUse`, `PermissionRequest`, `PostToolUse`, `SubagentStart`/`Stop`, `Stop`,
    `SessionStart`/`End`, and others.
  - Config: `~/.codex/hooks.json` or `config.toml`, and `<repo>/.codex/hooks.json` or `config.toml`
    for a trusted project.
  - `PreToolUse` fires for the shell (matched as `Bash`), `apply_patch` (matcher aliases `Edit`,
    `Write`), MCP tools (`mcp__<server>__<tool>`) and other local function tools. It does not fire
    for hosted `WebSearch`.
  - A hook blocks with exit code 2 and a reason on stderr, or with JSON
    `hookSpecificOutput.permissionDecision: "deny"`.
  - Every non-managed hook must be reviewed and trusted (`/hooks`) before it runs, and a changed
    hook is skipped until it is re-trusted.
  - Limits: "a useful guardrail, not a complete enforcement boundary"; `write_stdin` doesn't re-run
    `PreToolUse`.
  - Sources: https://learn.chatgpt.com/docs/hooks and `codex-rs/core/src/tools/hook_names.rs`.
- **Guardrail fit.** `guardrail.ts` (opencode) and the claude `guardrail.pl` block in-place
  `sed`/`perl`/`ruby` edits, redirects, `tee`, and `cp`/`mv` overwrites outside scratch. They also
  block inline scripts that write files and, under kbase, `kb-root/.index/` access. All of these
  are shell-path checks, so a `PreToolUse` hook matched on `Bash` covers them. `guardrail.ts`
  already parses `apply_patch` headers (`*** Update File:`), which is Codex's edit format.
  - Whether `guardrail.pl` can be reused depends on the hook stdin's `tool_input` shape for `Bash`.
    The model-side argument is `cmd` (`unified_exec.rs`, `ExecCommandArgs.cmd`); the hook payload
    field name was not confirmed **[unknown]**.
- **Codex's own sandbox compared with the guardrail.**
  - Sandbox modes: `read-only`, `workspace-write` (the default; no network unless enabled) and
    `danger-full-access`.
  - Approval modes: `on-request`, `never`, granular, `auto_review`. `untrusted` is retired.
  - `.git`, `.agents`, `.codex` and `.aws` are read-only even inside writable roots.
  - Source: https://learn.chatgpt.com/docs/agent-approvals-security
  - The sandbox limits *where* writes land. It does not tell `sed -i` apart from `apply_patch`, so
    devpro's guardrail (edits go through the edit tool) is still additive.

### 5. Tool names
Read from `codex-rs/core/src/tools/handlers/` @ rust-v0.168.0:
- `exec_command` and `write_stdin`: unified exec, the shell. The hook name is `Bash`.
- `apply_patch`: all file edits and writes.
- `view_image`, `update_plan`, `request_user_input`, `request_permissions`, `tool_search`.
- MCP resource tools.
- The multi-agent tools listed under "Dispatch" above.
- **Web search** is a *hosted* tool (`ToolSpec::WebSearch`, `codex-rs/core/src/tools/hosted_spec.rs`)
  with modes `cached`/`indexed`/`live`/`disabled`. It is not a local function, so hooks don't see
  it.
- **No web-fetch tool exists.** The shell (`curl`) is the only fetch path, subject to the sandbox's
  network setting **[inferred from the absence of a handler]**.
- **No read, grep or glob tools.** Reading is shell (`cat`, `rg`).
- Hosted web search needs a provider whose Responses API offers it. It is likely unavailable on
  local or OSS providers **[inferred]**.

### 6. Model configuration
- **Per agent.** `model` and `model_reasoning_effort` in the role TOML. These are locked, and the
  parent is told so.
- **Session level.** `model`, `model_provider`, and `[model_providers.<id>]` with `base_url`,
  `env_key` and headers. There is also `--oss` with `oss_provider` / `--local-provider` (Ollama,
  LM Studio). Source: https://learn.chatgpt.com/docs/config-file/config-advanced
- **Responses API only.** The only wire API is `responses`, and `wire_api = "chat"` errors as "no
  longer supported" (`codex-rs/model-provider-info/src/lib.rs`).
- **Non-OpenAI providers.** These are supported if they speak the Responses API at the session
  level. A role cannot set `model_provider`, so every tier in one session must come from the same
  provider.
- **Fit with devpro.** A devpro tier maps to a model id, and could also map to an effort level.
  devpro's `Family` holds models only. Anthropic models would need a Responses-compatible proxy
  **[inferred]**. Whether oMLX on reaper.local serves `/v1/responses` was not checked **[unknown]**.
- **Inherit.** Omit `model`, the same as opencode's empty `inherit_text`.

### 7. Install locations

| surface | project | user |
|---|---|---|
| agents | `.codex/agents/**.toml` (trusted project) | `~/.codex/agents/**.toml` |
| skills | `.agents/skills/<name>/` (cwd up to the repo root) | `~/.agents/skills/<name>/` |
| agents file | `AGENTS.md` per directory | `~/.codex/AGENTS.md` |
| hooks | `.codex/hooks.json` (trusted, reviewed) | `~/.codex/hooks.json` |
| MCP | `[mcp_servers.<name>]` in `.codex/config.toml` (trusted) | `~/.codex/config.toml` |
| prompts | none | `~/.codex/prompts/` (deprecated) |
| plugins | `.agents/plugins/marketplace.json` entry | `~/.agents/plugins/marketplace.json`, cache `~/.codex/plugins/cache/` |

The MCP fields are `command`, `args`, `env`, `cwd` and `env_vars`. Source:
https://learn.chatgpt.com/docs/extend/mcp?surface=cli

Whether Codex still also reads `~/.codex/skills` (legacy) was not confirmed **[unknown]**.

### 8. Versioning and stability
- The version is pre-1.0 (`0.168.0`), with several `-alpha` tags per day
  (https://github.com/openai/codex/releases).
- Breaking changes observed in 2026:
  - custom prompts deprecated;
  - `--profile` stopped reading `[profiles.*]` at 0.134.0;
  - `wire_api = "chat"` and `ollama-chat` removed;
  - `approval_policy = "untrusted"` retired;
  - the `multi_agent` flag deprecated in favour of `agents.enabled`;
  - a v2 agent tool surface with different spawn arguments;
  - the docs moved to `learn.chatgpt.com`.
- The surfaces devpro needs (role TOML, skills, hooks) are marked stable or default-on at 0.168.0.
- `codex-rs/config-schema` exists, a published config schema crate. It could back a machine check
  of rendered TOML **[inferred from the crate name; not read]**.

## Mapping onto devpro's `Harness` profile

The mapping is from `devpro/harness.py` fields as described in
`PROJECT_DOCS/ARCHITECTURE/rendering/harnesses-and-families.md`:

| field | Codex value | notes |
|---|---|---|
| `name` / `display_name` | `codex` / `codex` | |
| `agents_file` | `AGENTS.md` | no imports, 32 KiB cap |
| `project_harness_dir` | `.codex` | skills go in `.agents/`, outside it (gap 2) |
| `user_harness_dir` | `~/.codex` | user skills go in `~/.agents/skills` |
| `project_temp_dir` | `.codex-temp` **[proposed]** | not a protected path |
| `plugin_dir` | no single value. Agents in `agents/{plugin}/` under the harness dir; skills in `../.agents/skills/{plugin}-<name>/` | a recursive agents walk allows the subdirectory; skills are one directory each, flat **[inferred]** |
| `reference_prefix` | `{plugin}-` | role and skill names are flat strings; `:` in a role name not tested **[unknown]** |
| `mcp_tool_prefix` | `mcp__kbase__` | from the hook matcher example **[inferred for the model-facing name]** |
| `scratch_rule`, `memory_file` | `scratch_rule(.codex-temp, .codex)`, `` `~/.codex/AGENTS.md` `` | |
| `entry_resource` | none | no entry file is needed; Codex reads TOML and `SKILL.md` directly |
| `user_plugin_shadows` | false **[inferred]** | roles merge per layer with project over user; same-named skills both list |
| `reload_rule` | "start a new session" **[inferred]** | the docs say restart after config changes |
| `side_by_side_rule` | possibly needed | Codex reads `.claude-plugin` manifests and marketplaces. Whether it reads `.claude/skills` is **[unknown]** |
| `cold_read_rule` | `codex exec` with read-only sandbox **[unverified]** | no documented "no tools" switch |
| `recipe_rule`, `kbase_project_rule` | same as claude / empty | |
| `tools` | READ, GREP, GLOB, BASH → `exec_command`; EDIT, WRITE → `apply_patch`; WEBSEARCH → `web_search`; WEBFETCH → none; AGENT → `spawn_agent` | used only in prose; a role cannot restrict to these (gap 1) |
| `model_pattern` / `model_shape` | permissive `^(inherit\|\S+)$`; "a model id your Codex provider serves, e.g. gpt-5.4, or inherit" | ids depend on the provider |
| `inherit_text` / `inherit_synonyms` / `bare_tier_spec_is_all` | `""` (omit the key) / `("default",)` / `True` | follows opencode |
| `default_tier_spec` | the family's tiers, or `default` | depends on whether an `openai`/`gpt` family is added |
| `definition_form` | **new: `TomlRoleForm`** — the agent body goes in `developer_instructions`; skills keep `name`/`description` frontmatter | gap 3; needs a TOML string serializer |
| documents | no home as roles; could ship as plain `.md` beside a skill | gap 4 |
| commands | render as skills (explicit-only via `agents/openai.yaml`) | gap 5 |
| `rendered_files` | the kbase MCP entry must be a **merge** into `.codex/config.toml`, not an owned file | conflicts with "an owned `HarnessFile`" |
| `guardrail` | `GuardrailHook(script, registration=.codex/hooks.json)`, matcher `Bash\|apply_patch` | `hooks.json` is shared with the operator (needs a merge); activation needs the user's `/hooks` trust |
| `plugin_parent_dir` | empty | |

A different shape is possible: a Codex **plugin** (root `plugin.json`) carrying skills, the MCP
entry and hooks, with the agents installed separately into `.codex/agents/{plugin}/`. The plugin
would be registered through `.agents/plugins/marketplace.json`. It moves devpro from "copy into
the layout" to "register with a marketplace". Under THESIS's table that is the
"It is not: a package manager" direction, so the loose-file layout is the conventional fit
**[judgment]**.

## Unknowns
- The hook stdin `tool_input` field names for `Bash` (`command` or `cmd`) and for `apply_patch`
  (patch text or paths). This decides whether `guardrail.pl` can be reused.
- Whether a role `name` may contain `:`, and how plugin-namespaced skills render to the model.
- Whether a plugin can be loaded from a plain directory without a marketplace entry.
- Whether `~/.codex/skills` is still read; whether Codex reads `.claude/skills`.
- Whether `web_search` works on non-OpenAI or local providers, and whether oMLX serves the
  Responses API.
- A way to run a tool-less cold reader under `codex exec`.
- The exact text `wait_agent` returns (final message or status only). The docs say results reach
  the parent; the payload was not read.
- How the 32 KiB `AGENTS.md` cap interacts with a large devpro agents-file block.
