"""The harness agents-file render: the `hrn.` namespace, the harness file
schema, the `_resolve` fence, the templates status probe, and the dev render's
write refusal. The install is tested in test_agents_file_install.py.

Render tests use the real template and harness files, and no outcome depends
on this repository's git state; the templates status probe is exercised against a git repository built under `tmp_path`. Nothing
here reads or writes a harness's live configuration directory.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from gen_defs import agents_file, banners, discovery, markers, rendering
from gen_defs.errors import InputError
from gen_defs.model_tuning import DEFAULT_PIN_MAP

_REPO_ROOT = Path(__file__).resolve().parent.parent

#: A minimal harness file: every key the real template reads.
HARNESS = """
[harness.project-temp-dir]
text = ".x-temp"

[harness.project-harness-dir]
text = ".x"

[harness.user-harness-dir]
text = "~/.x"

[harness.agents-file]
text = "X.md"
"""


def _agents_file_body(middle: str) -> str:
    """A minimal valid agents-file body: H1, both user-content placeholders,
    and one marker pair around `middle`."""
    return (
        "# @!dyn.agents-file-scope-name!@\n\n@!dyn.existing-user-content-before-rendered-minus-h1!@\n\n"
        "<!-- vvv-adjagent adjagent-vvv -->\n"
        f"{middle}\n"
        "<!-- ^^^-adjagent adjagent-^^^ -->\n\n"
        "@!dyn.existing-user-content-after-rendered!@\n"
    )


def _rendered_body(middle: str, *, scope: str) -> str:
    """What _agents_file_body renders to with empty user content."""
    return f"# {scope}\n\n\n\n<!-- vvv-adjagent adjagent-vvv -->\n{middle}\n" "<!-- ^^^-adjagent adjagent-^^^ -->\n\n\n"


def _plant_template(path: Path, *resolve_texts: str, body: str = _agents_file_body("body @!hrn.agents-file!@")) -> Path:
    entries = "".join(f'[[outputs._resolve]]\ntext = "{text}"\n' for text in resolve_texts)
    path.write_text(f"+++\n{entries}+++\n{body}", encoding="utf-8")
    return path


def _plant_harness(directory: Path, text: str = HARNESS, name: str = "x") -> Path:
    directory.mkdir(exist_ok=True)
    (directory / f"{name}.toml").write_text(text, encoding="utf-8")
    return directory


DIR_FILE = "@!dyn.agents-file-install-dir-arg!@/@!hrn.agents-file!@"


# --- the real template and harness files ------------------------------------


def _directives(harness: str, directory: Path) -> str:
    """The rendered text of the plan that carries the directives — the first."""
    return agents_file.render_agents_file(harness, directory)[0].text


def test_claude_renders_agents_md_and_the_claude_md_redirect_into_a_project_dir(tmp_path):
    [(path, existing, text, _), redirect] = agents_file.render_agents_file("claude", tmp_path)
    assert (path, existing) == (tmp_path / "AGENTS.md", None)
    assert redirect == (tmp_path / "CLAUDE.md", None, "@AGENTS.md\n", None)
    assert ".claude-temp" in text
    assert "~/.claude/CLAUDE.md" in text
    assert "@!" not in text and "!@" not in text
    assert [line for line in text.split("\n") if "-adjagent" in line] == [
        " <!-- vvv-adjagent do not edit at or between marker lines. adjagent-vvv -->",
        " <!-- ^^^-adjagent do not edit at or between marker lines. adjagent-^^^ -->",
    ]


def test_opencode_renders_agents_md_into_dir(tmp_path):
    [(path, _, text, _)] = agents_file.render_agents_file("opencode", tmp_path)
    assert path == tmp_path / "AGENTS.md"
    assert ".opencode-temp" in text
    assert "~/.config/opencode/AGENTS.md" in text


def test_every_tier_token_renders_its_default_pin(tmp_path):
    template = _plant_template(
        tmp_path / "t.tmpl.md",
        DIR_FILE,
        body=_agents_file_body(" ".join(f"{tier}=@!dyn.tier-{tier}!@" for tier in DEFAULT_PIN_MAP)),
    )
    text = agents_file.render_agents_file_text("claude", tmp_path, template=template)
    expected = " ".join(f"{tier}={pin}" for tier, pin in DEFAULT_PIN_MAP.items())
    assert text == _rendered_body(expected, scope=tmp_path.name)


def test_an_unknown_harness_lists_the_available_ones(tmp_path):
    with pytest.raises(InputError, match=r"unknown harness 'nope'.*claude, opencode"):
        agents_file.render_agents_file("nope", tmp_path)


def test_a_missing_dir_is_an_error(tmp_path):
    with pytest.raises(InputError, match="not an existing directory"):
        agents_file.render_agents_file("claude", tmp_path / "absent")


# --- planted harness files and templates ------------------------------------


def test_a_harness_missing_a_key_the_template_reads_is_an_error(tmp_path):
    harness_dir = _plant_harness(tmp_path / "harness", HARNESS.replace("[harness.project-temp-dir]", "[harness.other]"))
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(InputError, match=r"unknown harness key 'project-temp-dir'.*agents-file, other"):
        agents_file.render_agents_file("x", out, harness_dir=harness_dir)
    assert list(out.iterdir()) == []


@pytest.mark.parametrize(
    "text, message",
    [
        (HARNESS + '\n[other]\ntext = "y"\n', "unknown top-level table"),
        (HARNESS + '\n[harness.Bad_Key]\ntext = "y"\n', "is not a harness key"),
        (HARNESS + '\n[harness.extra]\nvalue = "y"\n', "exactly one string 'text'"),
    ],
    ids=["stray-table", "non-kebab-key", "not-text"],
)
def test_harness_schema_errors(tmp_path, text, message):
    harness_dir = _plant_harness(tmp_path / "harness", text)
    with pytest.raises(InputError, match=message):
        agents_file.load_harness("x", harness_dir)


def test_a_resolve_entry_outside_dir_is_an_error(tmp_path):
    template = _plant_template(tmp_path / "t.tmpl.md", "@!dyn.agents-file-install-dir-arg!@/../@!hrn.agents-file!@")
    harness_dir = _plant_harness(tmp_path / "harness")
    with pytest.raises(InputError, match="not directly inside"):
        agents_file.render_agents_file("x", tmp_path, template=template, harness_dir=harness_dir)


def test_two_resolve_entries_give_two_outputs(tmp_path):
    template = _plant_template(tmp_path / "t.tmpl.md", DIR_FILE, "@!dyn.agents-file-install-dir-arg!@/ALSO.md")
    harness_dir = _plant_harness(tmp_path / "harness")
    renders = agents_file.render_agents_file("x", tmp_path, template=template, harness_dir=harness_dir)
    expected = _rendered_body("body X.md", scope=tmp_path.name)
    assert renders == [
        (tmp_path / "AGENTS.md", None, expected, None),
        (tmp_path / "ALSO.md", None, expected, None),
        (tmp_path / "X.md", None, "@AGENTS.md\n", None),
    ]


def test_the_unplaced_text_binds_the_install_dir_and_ignores_resolve(tmp_path):
    template = _plant_template(
        tmp_path / "t.tmpl.md",
        "@!dyn.agents-file-install-dir-arg!@/../escape.md",
        body=_agents_file_body("in @!dyn.agents-file-install-dir-arg!@"),
    )
    harness_dir = _plant_harness(tmp_path / "harness")
    text = agents_file.render_agents_file_text("x", tmp_path, template=template, harness_dir=harness_dir)
    assert text == _rendered_body(f"in {tmp_path}", scope=tmp_path.name)


def test_the_placed_and_unplaced_renders_agree(tmp_path):
    assert agents_file.render_agents_file_text("claude", tmp_path) == _directives("claude", tmp_path)


def test_split_outputs_refuses_a_non_table_output(tmp_path):
    template = _plant_template(tmp_path / "t.tmpl.md", "anything")
    with pytest.raises(InputError, match="outputs._resolve is not a table"):
        discovery.split_outputs(template)


# --- surface sites naming the agents file -----------------------------------


#: A path written against Claude Code's own directories or file names.
CLAUDE_PATH = re.compile(r"\.claude/|~/\.claude|CLAUDE\.md|\.claude-temp")


def _claude_path_lines(tmp_path: Path, harness: str) -> list[str]:
    """Every body line, below the banner block, of a full render under
    `harness` that names a claude path."""
    out = tmp_path / harness
    out.mkdir()
    result = _cli("generate", str(out), "--harness", harness, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    return [
        f"{path.relative_to(out)}: {line}"
        for path in sorted(out.rglob("*.md"))
        for line in banners.banner_body(path.read_text(encoding="utf-8")).splitlines()
        if CLAUDE_PATH.search(line)
    ]


def test_a_non_claude_render_writes_no_claude_path_into_any_body(tmp_path):
    # Every path in a definition body is written against the installing
    # harness's directories. The claude render is the control: the pattern
    # has to find something there, or its silence under opencode means nothing.
    assert _claude_path_lines(tmp_path, "opencode") == []
    assert _claude_path_lines(tmp_path, "claude")


# --- the harness namespace in render ----------------------------------------


def _expand(text, chunk_table, dynamic, harness=None):
    """`text` expanded under a surface render's routes, plus `hrn` when a
    harness table is given."""
    routes = rendering.routing_table(chunk_table, dynamic, {})
    if harness is not None:
        routes = {**routes, markers.HARNESS_NAMESPACE: markers.TableSource(harness, "hrn", "harness key")}
    return markers.expand(text, routes, args={}).text


def test_a_harness_marker_with_no_harness_table_is_an_error():
    with pytest.raises(InputError, match="does not route"):
        _expand("@!hrn.k!@", {}, {"tier-low": "haiku"})


def test_a_harness_namespace_is_not_an_overlay():
    # An overlay key nobody fills renders as nothing; a harness key never may.
    with pytest.raises(InputError, match="unknown harness key 'missing'"):
        _expand("@!hrn.missing!@", {}, {}, {"k": "v"})


# --- the templates status ----------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@invalid", *args],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "a.tmpl.md").write_text("a\n", encoding="utf-8")
    (tmp_path / "other.txt").write_text("o\n", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


@pytest.mark.parametrize(
    "change, dirty",
    [
        (None, False),
        ("templates/a.tmpl.md", True),
        ("templates/new.tmpl.md", True),
        ("other.txt", False),
    ],
    ids=["clean", "modified-under-templates", "untracked-under-templates", "modified-outside-templates"],
)
def test_the_dirty_templates_probe(repo, change, dirty):
    if change is not None:
        (repo / change).write_text("changed\n", encoding="utf-8")
    assert bool(agents_file.probe_dirty_templates(repo)) is dirty


def test_the_dirty_templates_probe_outside_a_repository_is_an_error(tmp_path):
    with pytest.raises(InputError, match="cannot read the templates status"):
        agents_file.probe_dirty_templates(tmp_path)


# --- writing -----------------------------------------------------------------


def test_write_creates_then_leaves_identical_content_alone(tmp_path):
    target = tmp_path / "X.md"
    agents_file.write_agents_file_renders([(target, "v1\n")])
    assert target.read_text(encoding="utf-8") == "v1\n"
    before = target.stat().st_mtime_ns
    agents_file.write_agents_file_renders([(target, "v1\n")])
    assert target.stat().st_mtime_ns == before


def test_write_refuses_a_differing_file_and_writes_nothing(tmp_path):
    fresh, existing = tmp_path / "A.md", tmp_path / "B.md"
    existing.write_text("theirs\n", encoding="utf-8")
    with pytest.raises(InputError, match="refusing to overwrite"):
        agents_file.write_agents_file_renders([(fresh, "ours\n"), (existing, "ours\n")])
    assert not fresh.exists()
    assert existing.read_text(encoding="utf-8") == "theirs\n"


def _cli(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "gen_defs", *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(_REPO_ROOT)},
    )


def test_dev_render_with_one_positional_exits_2(tmp_path):
    result = _cli("dev", "render-agents-file", "claude", cwd=tmp_path)
    assert result.returncode == 2
    assert "OUT" in result.stderr


@pytest.mark.parametrize("harness, name", [("claude", "CLAUDE.md"), ("opencode", "AGENTS.md")])
def test_dev_agents_file_for_harness_prints_the_name(tmp_path, harness, name):
    result = _cli("dev", "agents-file-for-harness", harness, cwd=tmp_path)
    assert (result.returncode, result.stdout) == (0, f"{name}\n")


def test_dev_agents_file_for_an_unknown_harness_exits_2_listing_the_valid_ones(tmp_path):
    result = _cli("dev", "agents-file-for-harness", "nope", cwd=tmp_path)
    assert result.returncode == 2
    assert "unknown harness 'nope'" in result.stderr and "claude, opencode" in result.stderr


@pytest.mark.parametrize("args", [("dev", "help"), ("dev",)], ids=["dev-help", "bare-dev"])
def test_dev_help_lists_the_dev_subcommands(tmp_path, args):
    result = _cli(*args, cwd=tmp_path)
    assert result.returncode == 0
    assert "agents-file-for-harness" in result.stdout and "render-agents-file" in result.stdout


def test_dev_is_absent_from_the_main_help(tmp_path):
    result = _cli("--help", cwd=tmp_path)
    assert result.returncode == 0
    assert re.search(r"\bdev\b", result.stdout) is None
    assert "{generate,install,install-agents-file}" in result.stdout
