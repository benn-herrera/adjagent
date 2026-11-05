### Harnesses and families

A harness is a `Harness` dataclass (`adjagent/harness.py`) holding everything that differs between
harnesses: the seven hole strings — `HarnessText.MCP_TOOL_PREFIX` among them, `mcp__kbase__`
under claude, `mcp_kbase_` under mage and `kbase_` under opencode, a server tool's offered name
being that prefix plus the tool's own, and the last two, `recipe_rule` and `kbase_project_rule`
(supplied under mage alone, whose server is started `--project-dir-required`), typed
`OptionalHarnessText` where the other five are `HarnessText` — the tool spellings, the model shape it accepts, the text
`inherit` renders as (`inherit_text`) with the further `inherit_synonyms` rendering that same text, whether a bare
`--model-tier-map` value is the whole map (`bare_tier_spec_is_all`), the frontmatter emitter,
`mcp` (`McpSettings`), the settings file and server entry a kb install registers, its `site` (`McpSite`)
naming the directory that file sits in — the project root, or, under mage, ROOT — `guardrail`
(`GuardrailHook` or `None`), the hook script and settings entry a claude install registers (Install
Consumption Model), `rendered_files` (`HarnessFile`), the files it renders of its own beside the
definitions — mage's manifest — `omits`, the definition names it renders nothing for, `default_tier_spec`, the
`--model-tier-map` value used when none is given (`None`: the family's tiers; opencode's is
`default`, read by `build_render`), and `plugin_parent_dir`, a plugin's trailing path of the
directory its plugins sit in (`Mage/Skills`; empty otherwise), by which install target detection
knows a plugin.
`inherit_synonyms` and `bare_tier_spec_is_all` differ between claude and opencode, as the strings
above do, and mage holds claude's assumed values (model pattern, aliases, tool spellings,
frontmatter) as copies it may revise independently: opencode holds `("default",)` and `True`, with
`inherit_text` empty, so a tier rendering either word leaves the agent without a model line and so
on the project's own model; claude holds `()` and `False`, `inherit_text` `inherit`, and refuses a
bare tier-map value as no `tier=value` pair. A family is a `Family` dataclass (`adjagent/family.py`)
holding the tier map and the overlays by anchor. An instance is one module, in `adjagent/harnesses/` or
`adjagent/families/`, defining `HARNESS` or `FAMILY`, with no class in it. `loading.load` reads the
modules of a package in name order and keys each by its module name with `_` read as `-`
(`gemma_4.py` is `gemma-4`). The constructor is the validator: an instance missing a field, or a
family not staffing exactly the five tiers, fails at import. The `Render` record
(`adjagent/context.py`) carries the harness, the family and the invocation's two tier maps, and
resolves a tier to its rendered model text and an anchor to its overlay: a tier whose text is
`inherit` or a synonym becomes `inherit_text`, and the tier-map argument, alone, gains the
bare-to-`all=` expansion before parsing. `Render.step_down_model` is the `medium` tier's rendered
model (`context.STEP_DOWN_TIER`) where this render pins one, and the empty string where that tier
renders as `inherit_text`, as under opencode's default tier map. It is the one value behind the
`tun` hole (Holes).

