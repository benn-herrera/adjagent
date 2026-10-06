"""Per-harness agent frontmatter and model shape: the harness file's
structural tables, their load refusals, and how each tier's rendered model is
checked against the harness and bound.

Harness files for the load tests are planted from in-test text. The shipped
harness files are read by the vocabulary test, which holds them to the field
lists and tool names each harness documents, and by the render tests, which
render in-test fixture templates under each and compare the text below the
banner against in-test goldens. The working templates are never read.
"""

from pathlib import Path

import pytest

from gen_defs import banners, markers, model_tuning, paths, rendering
from gen_defs.errors import InputError
from gen_defs.harness import load_harness

#: A minimal harness file: one `hrn.` value and nothing structural.
BASE = '[harness.agents-file]\ntext = "AGENTS.md"\n'


def _plant(tmp_path: Path, text: str) -> Path:
    (tmp_path / "x.toml").write_text(BASE + text, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "text, message",
    [
        ("[harness.agent-frontmatter]\nname = { injected = true }\n", "needs a 'text'"),
        ('[harness.agent-frontmatter]\nname = { text = "x", when = "y" }\n', r"unknown key\(s\) \['when'\]"),
        ('[harness.agent-frontmatter]\nname = { text = "x", injected = "yes" }\n', "'injected' must be true or false"),
        ("[harness.agent-frontmatter]\nname = { text = 1 }\n", "'text' must be a string"),
        ("[harness.agent-frontmatter]\nname = true\n", "an entry is a string"),
        ('[harness.agent-frontmatter]\n"bad key" = "x"\n', "not a frontmatter field name"),
        ('[harness.tools]\nRead = "Read"\n', "not a tool name"),
        ("[harness.tools]\nread = []\n", "non-empty string or a non-empty list"),
        ('[harness.tools]\nread = ["Read", 1]\n', "non-empty string or a non-empty list"),
        ("[harness.model]\npattern = '('\nshape = \"x\"\n", "not a valid regular expression"),
        ('[harness.model]\npattern = 1\nshape = "x"\n', "pattern must be a string"),
        ("[harness.model]\ninherit-text = false\n", "inherit-text must be a string"),
        ("[harness.model]\npattern = 'x'\n", r"x\.toml: \[harness.model\]: pattern is declared without shape"),
        ('[harness.model]\nshape = "x"\n', r"x\.toml: \[harness.model\]: shape is declared without pattern"),
        ("[harness.model]\npattern = 'x'\nshape = \"\"\n", "shape must be a non-empty string"),
        ("[harness.model]\npattern = 'x'\nshape = 1\n", "shape must be a non-empty string"),
        ("[harness.model]\nwords = \"x\"\n", r"unknown key\(s\) \['words'\]"),
        ('[harness]\nmodel = "x"\n', r"\[harness.model\]: must be a table"),
        ('[other]\ntext = "y"\n', "unknown top-level table"),
    ],
    ids=[
        "entry-without-text",
        "unknown-entry-key",
        "non-bool-injected",
        "non-string-text",
        "true-entry",
        "bad-field-name",
        "non-kebab-tool",
        "empty-tool-list",
        "non-string-spelling",
        "model-bad-pattern",
        "model-non-string-pattern",
        "model-non-string-inherit-text",
        "model-pattern-without-shape",
        "model-shape-without-pattern",
        "model-empty-shape",
        "model-non-string-shape",
        "model-unknown-key",
        "model-not-a-table",
        "stray-table",
    ],
)
def test_a_malformed_harness_file_is_refused_at_load(tmp_path, text, message):
    with pytest.raises(InputError, match=message):
        load_harness("x", _plant(tmp_path, text))


@pytest.mark.parametrize("key", ["agent-frontmatter", "tools", "model"])
def test_a_structural_table_is_not_an_hrn_value(tmp_path, key):
    text = '[harness.agent-frontmatter]\n[harness.tools]\nread = "Read"\n[harness.model]\n'
    values = load_harness("x", _plant(tmp_path, text)).values
    assert set(values) == {"agents-file"}
    with pytest.raises(InputError, match=f"unknown harness key '{key}'"):
        markers.expand(f"@!hrn.{key}!@", rendering.routing_table({}, {}, None, values), args={})


def test_entries_and_model_shape_load_in_their_declared_shapes(tmp_path):
    loaded = load_harness(
        "x",
        _plant(
            tmp_path,
            '[harness.agent-frontmatter]\nname = false\nmodel = "m"\nmode = { text = "s", injected = true }\n'
            '[harness.tools]\nglob = ["glob", "list"]\nread = "Read"\n'
            "[harness.model]\npattern = '^p/x$'\nshape = \"p/x\"\ninherit-text = \"\"\n",
        ),
    )
    assert loaded.model.shape == "p/x"
    assert loaded.frontmatter.entries == {"name": None, "model": ("m", False), "mode": ("s", True)}
    assert loaded.frontmatter.tools == {"glob": ("glob", "list"), "read": ("Read",)}
    assert loaded.model.pattern.pattern == "^p/x$"
    assert loaded.model.inherit_text == ""
    bare = load_harness("x", _plant(tmp_path, "")).model
    assert (bare.pattern, bare.shape, bare.inherit_text) == (None, None, None)


# --- the shipped harness files, held to what each harness documents ----------

#: Claude Code subagent frontmatter fields — https://code.claude.com/docs/en/sub-agents
CLAUDE_FIELDS = {
    "name", "description", "tools", "disallowedTools", "model", "permissionMode", "skills", "mcpServers",
    "hooks", "memory", "background", "omitClaudeMd", "effort", "isolation", "initialPrompt", "maxTurns",
    "experimental", "color",
}  # fmt: skip
#: opencode agent fields — https://opencode.ai/docs/agents/, https://opencode.ai/docs/config/
OPENCODE_FIELDS = {
    "description", "mode", "model", "temperature", "top_p", "prompt", "tools", "permission", "disable",
    "hidden", "steps", "color",
}  # fmt: skip
#: opencode permission keys — https://opencode.ai/docs/permissions/
OPENCODE_PERMISSION_KEYS = {
    "read", "edit", "glob", "grep", "list", "bash", "task", "external_directory", "todowrite", "webfetch",
    "websearch", "lsp", "skill", "question", "doom_loop",
}  # fmt: skip
#: Claude Code tool names — https://code.claude.com/docs/en/sub-agents
CLAUDE_TOOL_NAMES = {
    "Read", "Grep", "Glob", "Edit", "Write", "Bash", "WebFetch", "WebSearch", "Agent", "NotebookEdit", "TodoWrite",
}  # fmt: skip

SHIPPED = {"claude": (CLAUDE_FIELDS, CLAUDE_TOOL_NAMES), "opencode": (OPENCODE_FIELDS, OPENCODE_PERMISSION_KEYS)}


@pytest.mark.parametrize("name", sorted(SHIPPED))
def test_a_shipped_harness_renders_only_fields_it_documents(name):
    documented, _ = SHIPPED[name]
    entries = load_harness(name).frontmatter.entries
    assert {field for field, entry in entries.items() if entry is not None} <= documented
    assert {field for field, entry in entries.items() if entry is None} <= CLAUDE_FIELDS | OPENCODE_FIELDS


@pytest.mark.parametrize("name", sorted(SHIPPED))
def test_a_shipped_harness_spells_tools_in_its_own_names(name):
    _, spellings = SHIPPED[name]
    tools = load_harness(name).frontmatter.tools
    assert {spelling for values in tools.values() for spelling in values} <= spellings


def test_the_shipped_harnesses_share_one_tool_vocabulary():
    assert load_harness("claude").frontmatter.tools.keys() == load_harness("opencode").frontmatter.tools.keys()


# --- the render: in-test fixtures, goldens per shipped harness ---------------

#: Fixture templates, by path under the agents template tree.
FIXTURES = {
    "allowlisted.tmpl.md": (
        "---\n"
        "name: allowlisted\n"
        'description: "Reads and reports."\n'
        "model: @!dyn.tier-high!@\n"
        'color: "#0000FF"\n'
        "tools: read, grep, glob, write, edit\n"
        "---\n"
        "Body text.\n"
    ),
    "unrestricted.tmpl.md": (
        "---\n"
        "name: unrestricted\n"
        'description: "Does anything."\n'
        "model: @!dyn.tier-medium!@\n"
        'color: "#00FF00"\n'
        "---\n"
        "Body text.\n"
    ),
    "nested/contract.tmpl.md": "---\n---\nContract body.\n",
}

#: What each fixture renders below its banner, per shipped harness.
GOLDENS = {
    ("claude", "allowlisted"): (
        "name: allowlisted\n"
        'description: "Reads and reports."\n'
        "model: opus\n"
        'color: "#0000FF"\n'
        "tools: Read, Grep, Glob, Write, Edit\n"
        "---\n"
        "Body text.\n"
    ),
    ("opencode", "allowlisted"): (
        'description: "Reads and reports."\n'
        "model: omlx/X\n"
        'color: "#0000FF"\n'
        "permission:\n"
        "  read: allow\n"
        "  grep: allow\n"
        "  glob: allow\n"
        "  list: allow\n"
        "  edit: allow\n"
        "  bash: deny\n"
        "  webfetch: deny\n"
        "  websearch: deny\n"
        "  task: deny\n"
        "mode: subagent\n"
        "---\n"
        "Body text.\n"
    ),
    ("claude", "unrestricted"): (
        "name: unrestricted\n"
        'description: "Does anything."\n'
        "model: sonnet\n"
        'color: "#00FF00"\n'
        "---\n"
        "Body text.\n"
    ),
    ("opencode", "unrestricted"): (
        'description: "Does anything."\n'
        "model: omlx/X\n"
        'color: "#00FF00"\n'
        "mode: subagent\n"
        "---\n"
        "Body text.\n"
    ),
    ("claude", "contract"): "---\nContract body.\n",
    ("opencode", "contract"): "mode: subagent\ndisable: true\n---\nContract body.\n",
}


#: Every opencode tier on one provider-qualified model: the shipped default
#: family's members are claude aliases, which opencode's model shape refuses.
OPENCODE_TIERS = "all=omlx/X"


def _tuning(
    harness_name: str,
    *,
    family: str = model_tuning.DEFAULT_FAMILY,
    tier_spec: str | None = None,
    alias_spec: str | None = None,
) -> model_tuning.Tuning:
    """A shipped family's tuning under a shipped harness, checked against its
    model shape as the CLI checks it."""
    path = paths.FAMILY_DIR / f"{family}{paths.FAMILY_SUFFIX}"
    model = load_harness(harness_name).model
    return model_tuning.effective_tuning(
        path,
        model_tuning.load_family(path),
        tier_spec=tier_spec,
        alias_spec=alias_spec,
        harness=harness_name,
        model_pattern=model.pattern,
        model_shape=model.shape,
    )


def _render(
    tmp_path: Path, relative: str, text: str, harness_name: str, *, tier_spec: str | None = None
) -> list[tuple[Path, str]]:
    """Render one fixture template under a shipped harness, as generate does.
    Under opencode the tier map defaults to OPENCODE_TIERS."""
    template = tmp_path / "templates" / "agents" / relative
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_text(text, encoding="utf-8")
    loaded = load_harness(harness_name)
    if tier_spec is None and harness_name == "opencode":
        tier_spec = OPENCODE_TIERS
    tuning = _tuning(harness_name, tier_spec=tier_spec)
    binding = model_tuning.tier_binding(
        {},
        models=tuning.models,
        harness=loaded.values,
        frontmatter=loaded.frontmatter,
        inherit_text=loaded.model.inherit_text,
    )
    return rendering.render_template(
        template, binding, tmp_path / "out", surface="agents", overlays=None, tuning=tuning
    )


@pytest.mark.parametrize("harness_name, output", sorted(GOLDENS))
def test_a_fixture_renders_its_golden_under_each_shipped_harness(tmp_path, harness_name, output):
    relative = next(path for path in FIXTURES if Path(path).name == f"{output}.tmpl.md")
    [(target, text)] = _render(tmp_path, relative, FIXTURES[relative], harness_name)
    assert target.name == f"{output}.md"
    assert banners.banner_body(text) == GOLDENS[harness_name, output]
    assert banners.body_untouched(text)


ALLOWLISTED = FIXTURES["allowlisted.tmpl.md"]


@pytest.mark.parametrize(
    "harness_name, text, message",
    [
        ("claude", ALLOWLISTED.replace("tools:", "effort: high\ntools:"), "authors 'effort', for which"),
        ("opencode", ALLOWLISTED.replace("tools:", "mode: primary\ntools:"), "authors 'mode', which .* injects"),
        ("opencode", ALLOWLISTED.replace("read, grep", "read, Grep"), "authors tool 'Grep', which .*opencode.toml"),
        ("opencode", ALLOWLISTED.replace("read, grep", "read, ,grep"), "holds an empty item"),
        ("opencode", ALLOWLISTED.replace("read, grep, glob, write, edit", "[read]"), "is not a flat"),
        ("claude", ALLOWLISTED.replace('"Reads and reports."', "|\n  Reads."), "is not a flat"),
        (
            "claude",
            ALLOWLISTED.replace("tools: read, grep, glob, write, edit", "tools: read\n  - grep"),
            "is not a flat",
        ),
        ("claude", ALLOWLISTED.replace("color: ", "color:  "), "is not a flat"),
        ("claude", ALLOWLISTED.replace("color: ", "color:"), "is not a flat"),
        ("claude", ALLOWLISTED.replace('"Reads and reports."', "*alias"), "is not a flat"),
        ("claude", ALLOWLISTED.replace('"Reads and reports."', "&anchor reads"), "is not a flat"),
        ("claude", ALLOWLISTED.replace('"#0000FF"', "# blue"), "is not a flat"),
        ("claude", ALLOWLISTED.replace('"Reads and reports."', "`reads`"), "is not a flat"),
        ("claude", ALLOWLISTED.replace('"Reads and reports."', "@reads"), "is not a flat"),
        ("claude", ALLOWLISTED.replace('"Reads and reports."', "- reads"), "is not a flat"),
        ("opencode", ALLOWLISTED.replace("---\nBody", "Body"), "never closes"),
        ("claude", ALLOWLISTED.replace("tools:", "color: x\ntools:"), "authors 'color' twice"),
        ("claude", ALLOWLISTED.replace("name: allowlisted", "name: other"), "authors name 'other'"),
        ("opencode", ALLOWLISTED.replace("name: allowlisted", "name: other"), "authors name 'other'"),
    ],
    ids=[
        "no-entry-claude",
        "injected-and-authored",
        "tool-outside-vocabulary",
        "empty-tool-item",
        "flow-list",
        "block-scalar",
        "sequence",
        "two-spaces",
        "no-space",
        "alias",
        "anchor",
        "comment",
        "backtick",
        "at-sign-without-marker",
        "blank-led-dash",
        "unclosed-block",
        "duplicate-key",
        "name-not-stem-claude",
        "name-not-stem-opencode",
    ],
)
def test_a_frontmatter_the_harness_cannot_render_is_refused(tmp_path, harness_name, text, message):
    with pytest.raises(InputError, match=message):
        _render(tmp_path, "allowlisted.tmpl.md", text, harness_name)


@pytest.mark.parametrize(
    "slot", ["authored-value", "output-stem", "tools", "tools-as-permission", "undispatchable-marker"]
)
def test_an_entry_slot_is_unknown_in_a_template_body(tmp_path, slot):
    text = FIXTURES["unrestricted.tmpl.md"].replace("Body text.", f"Body @!dyn.{slot}!@.")
    with pytest.raises(InputError, match=f"unknown invocation parameter '{slot}'"):
        _render(tmp_path, "unrestricted.tmpl.md", text, "opencode")


# --- the model: one source, its shape per harness, and inherit -------------


def test_inherit_elides_the_model_line_under_opencode(tmp_path):
    [(_, text)] = _render(tmp_path, "allowlisted.tmpl.md", ALLOWLISTED, "opencode", tier_spec="all=inherit")
    assert banners.banner_body(text) == GOLDENS["opencode", "allowlisted"].replace("model: omlx/X\n", "")
    # The banner records the word, not its empty rendering.
    assert " tier=highest=inherit,high=inherit,medium=inherit,low=inherit,lowest=inherit " in text


def test_the_alias_map_replaces_every_tiers_rendered_model_and_nothing_else():
    tuning = _tuning("claude", alias_spec="all=haiku,high=opus")
    assert tuning.models == {**dict.fromkeys(model_tuning.TIERS, "haiku"), "high": "opus"}
    assert tuning.tier_map == model_tuning.load_family(paths.FAMILY_DIR / "claude.toml").tiers


@pytest.mark.parametrize(
    "harness_name, tier_spec, alias_spec, model, supplier",
    [
        ("opencode", None, None, "fable", "the family file templates/family/claude.toml [tiers] (--family)"),
        ("opencode", "all=sonnet", None, "sonnet", "--model-tier-map"),
        ("opencode", None, "all=sonnet", "sonnet", "--model-pin-tier-alias-map"),
        ("claude", "all=Qwen3.8-Flash-Next", None, "Qwen3.8-Flash-Next", "--model-tier-map"),
    ],
    ids=["family-file", "tier-map", "alias-map", "claude-shape"],
)
def test_a_model_refusal_names_its_supplier_and_the_shape_in_words(
    harness_name, tier_spec, alias_spec, model, supplier
):
    declared = load_harness(harness_name).model
    with pytest.raises(InputError) as refusal:
        _tuning(harness_name, tier_spec=tier_spec, alias_spec=alias_spec)
    message = str(refusal.value)
    assert message == (
        f"harness '{harness_name}' does not accept model '{model}' at tier highest, supplied by {supplier} — "
        f"a model for this harness is {declared.shape}"
    )
    assert declared.pattern.pattern not in message


@pytest.mark.parametrize(
    "harness_name, model, accepted",
    [
        ("claude", "opus", True),
        ("claude", "claude-sonnet-4-5", True),
        ("claude", "inherit", True),
        ("claude", "omlx/X", False),
        ("opencode", "inherit", True),
        ("opencode", "omlx/Qwen3.8-Flash-Next", True),
        ("opencode", "opus", False),
        ("opencode", "a/", False),
    ],
)
def test_each_shipped_harness_accepts_its_documented_model_shape(harness_name, model, accepted):
    pattern = load_harness(harness_name).model.pattern
    assert (pattern.fullmatch(model) is not None) is accepted


@pytest.mark.parametrize(
    "alias_spec, notices",
    [(None, False), ("all=opus,medium=sonnet,low=haiku,lowest=haiku,highest=fable", False)],
)
def test_the_alias_notice_speaks_only_where_an_alias_differs_from_its_member(capsys, alias_spec, notices):
    model_tuning.report_aliases(_tuning("claude", alias_spec=alias_spec))
    assert ("notice: the alias map rewrites" in capsys.readouterr().out) is notices
