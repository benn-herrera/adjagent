"""The agents-file render and installer, and the definition install, each case checked against values
the code under test did not compute: the marker span, the bytes kept outside it, the refusals that
write nothing, the redirects, the kb-tools package and its banner, the docdicer tools package and its
venv rebuild, the kb install path, the MCP
settings merge, the runner include line, the harness resources a harness ships as they stand, the
prune, the refusal to overwrite a file without this repository's banner, the claude guardrail hook's
probe and registration, the removal of entries earlier installs registered, and the checkout premise with the checks that stand down outside one.

The package is imported from the repository root, which `just test` puts on PYTHONPATH.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import cast

import pytest

from adjagent import __version__
from adjagent.agents_file import install_agents_file, marker_span, scope_name
from adjagent.cli import main
from adjagent.context import Render, build_render
from adjagent.definition import Definition
from adjagent.definitions import discover
from adjagent.errors import InputError
from adjagent.families.claude import FAMILY as CLAUDE_FAMILY
from adjagent.harness import Harness, McpSite
from adjagent.harnesses.claude import HARNESS as CLAUDE
from adjagent.harnesses.mage import HARNESS as MAGE
from adjagent.harnesses.opencode import HARNESS as OPENCODE
from adjagent.install import (
    HARNESS_RESOURCES_SOURCE,
    KBASE_NAME,
    PACKAGE_ROOT,
    REPO_ROOT,
    _is_our_resource,
    _named_harnesses,
    _refuse_root,
    checkout_root,
    excluded,
    harness_resource_copies,
    install,
    install_kb_include_line,
    kb_include_line,
    preflighted_install,
    uncommitted_sources,
)
from adjagent.loading import load
from adjagent.render import definitions, filled_body, render_agents_file, render_all, render_definition
from adjagent.vocabulary import Kind, reference

_BEGIN = " <!-- vvv-adjagent do not edit at or between marker lines. adjagent-vvv -->"
"""The begin marker line an earlier, unstamped revision wrote."""
_STAMPED_BEGIN = f" <!-- vvv-adjagent {__version__} do not edit at or between marker lines. adjagent-vvv -->"
_END = " <!-- ^^^-adjagent do not edit at or between marker lines. adjagent-^^^ -->"


def _block(harness: Harness) -> list[str]:
    lines, begin, end = marker_span(render_agents_file(harness, scope="x"), where="render")
    return lines[begin : end + 1]


def _files(root: Path) -> dict[str, bytes]:
    """Every file under `root` with its bytes, symlinks as their target text."""
    return {
        path.relative_to(root).as_posix(): (str(path.readlink()).encode() if path.is_symlink() else path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_symlink() or path.is_file()
    }


# The agents-file render.


def test_the_fresh_render_holds_the_title_and_one_marker_span() -> None:
    user_dir = Path(CLAUDE.user_harness_dir).expanduser()
    text = render_agents_file(CLAUDE, scope=scope_name(CLAUDE, user_dir))
    lines, begin, end = marker_span(text, where="render")
    assert (lines[0], lines[begin], lines[end]) == ("# Global info and directives", _STAMPED_BEGIN, _END)
    assert text.endswith(_END + "\n")


def test_an_agents_file_hole_in_any_other_kind_is_an_unknown_placeholder() -> None:
    defn = Definition(name="probe", kind=Kind.COMMAND, body="for @!agf-scope-name!@")
    ctx = Render(harness=CLAUDE, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
    with pytest.raises(InputError, match=re.escape("definition 'probe': unknown placeholder @!agf-scope-name!@")):
        filled_body(defn, ctx)


# The installer. A project directory under opencode writes AGENTS.md and nothing else.


def _install(directory: Path, harness: Harness = OPENCODE, uncommitted: tuple[str, ...] = ()) -> None:
    install_agents_file(directory, harness, uncommitted=uncommitted)


def test_install_replaces_only_the_span_and_keeps_every_other_byte(tmp_path: Path, capsys) -> None:
    above = "# My rules\r\n\r\nmine above\r\n"
    below = "\nmine below\r\n\r\n  trailing  "
    begin = " <!-- vvv-adjagent version[abc1234] an earlier revision's wording adjagent-vvv -->"
    prior = f"{above}{begin}\r\nold block\r\n{_END}\r{below}"
    target = tmp_path / "AGENTS.md"
    target.write_bytes(prior.encode())
    _install(tmp_path)
    expected = (above + "\n".join(_block(OPENCODE)) + below).encode()
    assert target.read_bytes() == expected
    assert (tmp_path / "backup.AGENTS.md").read_bytes() == prior.encode()
    capsys.readouterr()
    _install(tmp_path)
    assert capsys.readouterr().out == f"unchanged {target}\n"
    assert target.read_bytes() == expected
    assert (tmp_path / "backup.AGENTS.md").read_bytes() == prior.encode()


@pytest.mark.parametrize(
    "prior, message",
    [
        (f"{_BEGIN}\n{_BEGIN}\n{_END}\n", "found 2 begin and 1 end"),
        (f"# mine\n{_END}\n", "found 0 begin and 1 end"),
        (f"{_END}\n{_BEGIN}\n", "found 1 begin and 1 end"),
    ],
)
def test_a_file_without_one_ordered_marker_pair_is_refused(tmp_path: Path, prior: str, message: str) -> None:
    (tmp_path / "AGENTS.md").write_text(prior, encoding="utf-8")
    with pytest.raises(InputError, match=message):
        _install(tmp_path)
    assert _files(tmp_path) == {"AGENTS.md": prior.encode()}


@pytest.mark.parametrize(
    "prior, separator",
    [
        ("", ""),
        ("# mine\r\nkeep\r\n\n", ""),
        ("# mine\r\nkeep\r\n", "\n"),
        ("# mine\r\nkeep  ", "\n\n"),
    ],
)
def test_a_file_without_marker_lines_gets_the_block_appended(
    tmp_path: Path, capsys, prior: str, separator: str
) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_bytes(prior.encode())
    _install(tmp_path)
    expected = (prior + separator + "\n".join(_block(OPENCODE)) + "\n").encode()
    assert target.read_bytes() == expected
    assert (tmp_path / "backup.AGENTS.md").read_bytes() == prior.encode()
    capsys.readouterr()
    _install(tmp_path)
    assert capsys.readouterr().out == f"unchanged {target}\n"
    assert target.read_bytes() == expected


def _stamped(stamp: str, *, content: list[str]) -> str:
    """A file holding the rendered block with its begin line stamped `stamp` in place of this version
    and `content` between the marker lines."""
    begin, *_, end = _block(OPENCODE)
    return "\n".join(["mine", begin.replace(__version__, stamp), *content, end, ""])


_CURRENT = _block(OPENCODE)[1:-1]


@pytest.mark.parametrize(
    "stamp, content, rewritten",
    [
        ("0.0.1", _CURRENT, False),
        ("99.0.0", _CURRENT, False),
        ("0.0.1", ["old"], True),
        (__version__, ["old"], True),
        ("99.0.0", ["old"], False),
    ],
    ids=["identical-older", "identical-newer", "older", "same", "newer"],
)
def test_the_stamp_decides_a_differing_block_and_identical_content_is_never_rewritten(
    tmp_path: Path, capsys, stamp: str, content: list[str], rewritten: bool
) -> None:
    target = tmp_path / "AGENTS.md"
    prior = _stamped(stamp, content=content)
    target.write_text(prior, encoding="utf-8")
    _install(tmp_path)
    captured = capsys.readouterr()
    if rewritten:
        assert target.read_text(encoding="utf-8") == "\n".join(["mine", *_block(OPENCODE), ""])
        assert (tmp_path / "backup.AGENTS.md").read_text(encoding="utf-8") == prior
    else:
        assert _files(tmp_path) == {"AGENTS.md": prior.encode()}
    downgrade = stamp == "99.0.0" and content != _CURRENT
    assert ("not downgraded" in captured.err and f"99.0.0, newer than this {__version__}" in captured.err) is downgrade


def test_an_unstamped_block_is_rewritten_and_stamped(tmp_path: Path) -> None:
    """The not-a-release row is the planted `version[abc1234]` fence above."""
    target = tmp_path / "AGENTS.md"
    target.write_text(f"{_BEGIN}\nold\n{_END}\n", encoding="utf-8")
    _install(tmp_path)
    assert target.read_text(encoding="utf-8") == "\n".join([*_block(OPENCODE), ""])


def _non_utf8(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_bytes(b"\xff\xfe" + f"{_BEGIN}\n{_END}\n".encode())


def _redirect_chain(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("@one.md\n", encoding="utf-8")
    (tmp_path / "one.md").write_text("@two.md\n", encoding="utf-8")


def _redirect_outside(tmp_path: Path) -> None:
    (tmp_path / "inner").mkdir()
    (tmp_path / "inner" / "AGENTS.md").write_text("@../outside.md\n", encoding="utf-8")


@pytest.mark.parametrize(
    "plant, directory, message",
    [
        (_non_utf8, ".", "AGENTS.md is not UTF-8 text"),
        (_redirect_chain, ".", "which is itself a redirect"),
        (_redirect_outside, "inner", "which is outside"),
    ],
)
def test_an_unsafe_destination_is_refused_with_nothing_written(
    tmp_path: Path, plant, directory: str, message: str
) -> None:
    plant(tmp_path)
    before = _files(tmp_path)
    with pytest.raises(InputError, match=message):
        _install(tmp_path / directory)
    assert _files(tmp_path) == before


def test_uncommitted_sources_refuse_no_install_into_a_project_directory(tmp_path: Path) -> None:
    _install(tmp_path, uncommitted=("?? adjagent/x.py",))
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == render_agents_file(OPENCODE, scope=tmp_path.name)


@pytest.mark.parametrize("git_entry", ["directory", "file", None])
def test_a_checkout_is_a_package_parent_holding_a_git_entry(tmp_path: Path, git_entry: str | None) -> None:
    package = tmp_path / "adjagent"
    package.mkdir()
    if git_entry == "directory":
        (tmp_path / ".git").mkdir()
    elif git_entry == "file":
        (tmp_path / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    assert checkout_root(package) == (None if git_entry is None else tmp_path)


def test_this_checkout_is_one_and_its_commit_state_reads() -> None:
    assert REPO_ROOT == PACKAGE_ROOT.parent
    uncommitted_sources()


def test_outside_a_checkout_nothing_is_uncommitted_and_git_is_not_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("adjagent.install.REPO_ROOT", None)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert uncommitted_sources() == ()


def test_a_checkout_git_cannot_read_still_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".git").write_text("", encoding="utf-8")
    monkeypatch.setattr("adjagent.install.REPO_ROOT", tmp_path)
    with pytest.raises(InputError, match="cannot read the commit state"):
        uncommitted_sources()


@pytest.fixture
def _site_packages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A site-packages directory holding the package, with no repository around it."""
    site = (tmp_path / "site").resolve()
    (site / "adjagent" / "kb-tools").mkdir(parents=True)
    monkeypatch.setattr("adjagent.install.PACKAGE_ROOT", site / "adjagent")
    monkeypatch.setattr("adjagent.install.REPO_ROOT", None)
    return site


def test_outside_a_checkout_site_packages_is_an_install_root_and_the_package_sources_are_not(
    _site_packages: Path,
) -> None:
    _refuse_root(_site_packages)
    with pytest.raises(InputError, match="is this repository or inside a source it copies from"):
        _refuse_root(_site_packages / "adjagent" / "kb-tools" / "x")


def test_outside_a_checkout_a_project_at_site_packages_gets_its_include_line(_site_packages: Path) -> None:
    (_site_packages / "justfile").write_text("", encoding="utf-8")
    install_kb_include_line(_site_packages, harness_relpath=".claude")
    lines = (_site_packages / "justfile").read_text(encoding="utf-8").splitlines()
    assert kb_include_line(runner="just", harness_relpath=".claude") in lines


def test_a_project_directory_under_claude_writes_agents_md_and_the_redirect(tmp_path: Path) -> None:
    _install(tmp_path, CLAUDE)
    assert _files(tmp_path) == {
        "AGENTS.md": render_agents_file(CLAUDE, scope=tmp_path.name).encode(),
        "CLAUDE.md": b"@AGENTS.md\n",
    }
    assert render_agents_file(CLAUDE, scope=tmp_path.name).startswith(f"# {tmp_path.name} info and directives\n")


def test_this_repositorys_claude_redirect_is_followed_and_left_alone(tmp_path: Path) -> None:
    """This repository's own pair: CLAUDE.md is `@AGENTS.md`, and AGENTS.md is the operator's text
    with no block, which the install appends."""
    redirect = (REPO_ROOT / "CLAUDE.md").read_bytes()
    own = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert redirect == b"@AGENTS.md\n" and _BEGIN not in own and own.endswith("\n")
    (tmp_path / "CLAUDE.md").write_bytes(redirect)
    (tmp_path / "AGENTS.md").write_text(own, encoding="utf-8")
    _install(tmp_path, CLAUDE)
    assert (tmp_path / "CLAUDE.md").read_bytes() == redirect
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == "\n".join([own, *_block(CLAUDE), ""])


def test_a_claude_native_file_holding_its_own_content_is_refused(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("# my own rules\n", encoding="utf-8")
    with pytest.raises(InputError, match="CLAUDE.md holds its own content"):
        _install(tmp_path, CLAUDE)
    assert _files(tmp_path) == {"CLAUDE.md": b"# my own rules\n"}


def test_a_destination_redirect_is_followed_one_hop_into_its_target(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "AGENTS.md").write_text("@docs/rules.md\n", encoding="utf-8")
    _install(tmp_path)
    assert _files(tmp_path) == {
        "AGENTS.md": b"@docs/rules.md\n",
        "docs/rules.md": render_agents_file(OPENCODE, scope=tmp_path.name).encode(),
    }


def test_the_user_directory_writes_the_native_file_and_no_redirect(tmp_path: Path) -> None:
    harness = dataclasses.replace(CLAUDE, user_harness_dir=str(tmp_path))
    _install(tmp_path, harness)
    assert _files(tmp_path) == {"CLAUDE.md": render_agents_file(harness, scope="Global").encode()}


def test_a_relative_user_directory_is_the_destination_itself(tmp_path: Path) -> None:
    """Mage's `.` names the directory being installed into — the native file, no `AGENTS.md`
    redirect — and leaves a harness whose user directory is absolute writing `AGENTS.md` elsewhere."""
    _install(tmp_path, MAGE)
    assert _files(tmp_path) == {"CLAUDE.md": render_agents_file(MAGE, scope="Global").encode()}
    project = tmp_path / "project"
    project.mkdir()
    _install(project, CLAUDE)
    assert _files(project) == {
        "AGENTS.md": render_agents_file(CLAUDE, scope=project.name).encode(),
        "CLAUDE.md": b"@AGENTS.md\n",
    }


# The definition install. A consumer project receives the product under its harness directory, and —
# when the install includes kb — the kb-tools package in the kbase skill's own directory, with the
# `kbase` MCP entry and the runner include line.

_CLAUDE_RENDER = Render(harness=CLAUDE, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
_MAGE_RENDER = Render(harness=MAGE, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
_OPENCODE_RENDER = build_render(harness="opencode", family="claude", tier_spec="all=inherit", alias_spec=None)
_NEW_BANNER = "---\n# !GENERATED! from adjagent/definitions/gone.py — x\n# !TUNING! y\n---\n\nbody\n"
_OLD_BANNER = "---\n#\n# !GENERATED! from templates/agents/gone.tmpl.md\n# !TUNING! y\n#\n---\n\nbody\n"
# A skill's supporting file: no frontmatter, so its banner rides on two HTML comment lines.
_COMMENT_BANNER = "<!-- !GENERATED! from adjagent/definitions/kbase.py — x -->\n<!-- !TUNING! y -->"
_KBASE_BYTES = b"KBASE-STUB-v1\n"
# The kb set is the kbase skill alone, so its definition-side footprint is empty.
_KB_DEFINITIONS: tuple[str, ...] = ()
# The kbase skill's files: one definition owning a directory, so a run keeps or drops all seven.
_KB_SKILL_FILES = (
    "skills/kbase/SKILL.md",
    "skills/kbase/references/reading.md",
    "skills/kbase/references/building.md",
    "skills/kbase/references/scoring.md",
    "skills/kbase/references/maintaining.md",
    "skills/kbase/references/scoring-system.md",
    "skills/kbase/references/installing.md",
)


def _definition_install(
    root: Path,
    ctx: Render = _CLAUDE_RENDER,
    *,
    with_kb: bool = False,
    project_root: Path | None = None,
) -> None:
    install(
        root,
        ctx,
        verbose=False,
        with_kb=with_kb,
        project_root=project_root,
        uncommitted=_committed,
        tool_install=_ToolInstalls(),
    )


def _committed() -> tuple[str, ...]:
    """No uncommitted sources, so a mage install's agents file does not turn on this tree's git state."""
    return ()


class _ToolInstalls:
    """A stand-in for `run_tool_install`, so no test reaches the network: it records each script it is
    asked to run with `--install` and answers `failure`."""

    def __init__(self, failure: str | None = None) -> None:
        self.scripts: list[Path] = []
        self.failure = failure

    def __call__(self, script: Path) -> str | None:
        self.scripts.append(script)
        return self.failure


# The harness resources: the files a harness ships for its own harness directory, copied into ROOT as
# they stand. A harness that ships none copies nothing.

_PLUGIN = "plugins/guardrail.ts"
_GUARDRAIL = "hooks/guardrail.pl"
_SETTINGS = ".claude/settings.json"
# A claude install writes the set into its plugin, below the harness directory it is given.
_CLAUDE_PLUGIN_RELPATH = f".claude/{CLAUDE.plugin_dir}"


def _claude_plugin(harness_dir: Path) -> Path:
    return harness_dir / CLAUDE.plugin_dir


def _claude_mcp_file(harness_dir: Path) -> Path:
    """The plugin's own MCP settings file, its directory created so a test can seed it."""
    plugin = _claude_plugin(harness_dir)
    plugin.mkdir(parents=True, exist_ok=True)
    return plugin / CLAUDE.mcp.canonical


_REGISTRATION = "hooks/hooks.json"


def _retired_hook_entry(harness_relpath: str, *, matcher: str = "Bash|Read|Write|Edit|NotebookEdit|Grep|Glob") -> dict:
    """The PreToolUse entry an earlier install registered in the project's settings file, its script
    under `harness_relpath`, spelled as that install wrote it: the entry an install now removes."""
    prefix = "" if harness_relpath == "." else f"{harness_relpath}/"
    command = (
        f's="$CLAUDE_PROJECT_DIR/{prefix}hooks/guardrail.pl"; if [ -f "$s" ] && [ -r "$s" ]; then exec perl "$s"; '
        'fi; echo "guardrail hook: no readable script at $s" >&2; exit 1'
    )
    return {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}


def test_an_opencode_install_copies_the_harnesss_plugin_byte_verbatim(tmp_path: Path) -> None:
    """The opencode plugin is the harness's own file, not this repository's generated product: it lands
    under ROOT byte for byte, so a stamp anywhere in the copy would show as a difference from the
    source."""
    root = tmp_path / ".opencode"
    root.mkdir()
    _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
    copied = root / _PLUGIN
    assert copied.read_bytes() == (PACKAGE_ROOT / HARNESS_RESOURCES_SOURCE / "opencode" / _PLUGIN).read_bytes()


def test_a_fresh_claude_install_ships_the_guardrail_and_registers_it_in_the_plugin(tmp_path: Path) -> None:
    """Where the probe passes, the hook script lands byte-verbatim and executable under ROOT beside the
    plugin's one registration, and the project gains no settings file."""
    root = tmp_path / ".claude"
    root.mkdir()
    _definition_install(root, project_root=tmp_path)
    copied = _claude_plugin(root) / _GUARDRAIL
    assert copied.read_bytes() == (PACKAGE_ROOT / HARNESS_RESOURCES_SOURCE / "claude" / _GUARDRAIL).read_bytes()
    assert os.access(copied, os.X_OK)
    registration = json.loads((_claude_plugin(root) / _REGISTRATION).read_text(encoding="utf-8"))
    assert list(registration) == ["hooks"] and len(registration["hooks"]["PreToolUse"]) == 1
    assert not (tmp_path / _SETTINGS).exists()


def test_a_second_install_leaves_the_copied_plugin_standing_and_prunes_only_the_stale_render(
    tmp_path: Path, capsys
) -> None:
    """The copied file is in `keep`, so a re-install neither rewrites it away nor prunes it: the one
    rendered file planted beside it is what goes."""
    root = tmp_path / ".opencode"
    root.mkdir()
    _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
    copied = root / _PLUGIN
    before = copied.read_bytes()
    stale = root / "agents/gone.md"
    stale.write_text(_NEW_BANNER, encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
    assert copied.read_bytes() == before
    assert not stale.exists()
    out = capsys.readouterr().out
    assert f"pruned {stale}" in out
    assert f"pruned {copied}" not in out


def test_a_resource_copy_skips_the_unshipped_vocabulary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The resource walk is filtered by the same vocabulary the packages are: a `.DS_Store`, a
    `__pycache__` and a `.bak` copy never land beside the harness's own files."""
    harness = tmp_path / "repo" / HARNESS_RESOURCES_SOURCE / "probe"
    (harness / "plugins").mkdir(parents=True)
    (harness / "plugins/keep.ts").write_text("export const keep = 1\n", encoding="utf-8")
    (harness / "plugins/.DS_Store").write_bytes(b"\x00")
    (harness / "plugins/keep.ts.bak").write_text("old\n", encoding="utf-8")
    (harness / "__pycache__").mkdir()
    (harness / "__pycache__/probe.pyc").write_bytes(b"\x00")
    monkeypatch.setattr("adjagent.install.PACKAGE_ROOT", tmp_path / "repo")
    root = tmp_path / ".probe"
    copies = harness_resource_copies(root, harness="probe")
    assert [target.relative_to(root).as_posix() for _, target in copies] == ["plugins/keep.ts"]


def test_the_resources_tree_is_not_read_as_a_harness_module() -> None:
    """`resources/` holds no `__init__.py`, so `pkgutil` lists it as a tree rather than a module and
    `load` returns every harness module. A `resources` package appearing later would break that, so the
    same case pins the tree's presence: a resource tree that went missing fails here too, rather than
    the plugin copy silently landing nothing."""
    assert sorted(load("adjagent.harnesses", "HARNESS")) == ["claude", "mage", "opencode"]
    assert (PACKAGE_ROOT / HARNESS_RESOURCES_SOURCE / "opencode").is_dir()


def test_every_harness_omits_a_name_the_package_discovers() -> None:
    """`omits` is matched against definition names by string, so a name nothing discovers drops nothing
    and ships the file it was meant to, silently. Each name is checked against discovery instead."""
    discovered = {defn.name for _, defn in definitions()}
    harnesses = cast(dict[str, Harness], load("adjagent.harnesses", "HARNESS"))
    unknown = [
        (harness_name, omitted)
        for harness_name, harness in harnesses.items()
        for omitted in sorted(harness.omits)
        if omitted not in discovered
    ]
    assert unknown == []


@pytest.mark.parametrize("name", sorted(load("adjagent.harnesses", "HARNESS")))
def test_every_skill_the_agents_file_cites_ships_in_the_harness_default_install(name: str) -> None:
    """The agents file points at skills through reference holes; a name a default install does not ship
    points at nothing. A plugin always takes the kb set; any other harness's default install leaves it
    out."""
    ctx = build_render(harness=name, family="claude", tier_spec=None, alias_spec=None)
    every = [defn for _, entries in discover() for defn in entries]
    [agents_file] = [defn for defn in every if defn.kind is Kind.AGENTS_FILE]
    cited = {defn.name for defn in every if defn.kind is Kind.SKILL and reference(defn.name) in agents_file.body}
    assert cited, "the agents file references no skill, so the check below would pass vacuously"
    renders = render_all(ctx, include=lambda defn: ctx.harness.is_standalone_plugin or not excluded(defn.name))
    shipped = {path.parts[1] for path, _ in renders if path.parts[0] == "skills" and path.name == "SKILL.md"}
    assert cited <= shipped, sorted(cited - shipped)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("kb-maintainer", True),
        ("kbase", True),
        ("kbase-router", False),
        ("kbases", False),
        ("python-coder", False),
    ],
)
def test_the_not_by_default_pattern_covers_the_kb_definition_names(name: str, expected: bool) -> None:
    assert excluded(name) is expected


def test_a_duplicate_output_is_refused_even_when_both_definitions_are_excluded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The duplicate check runs over what discovery found, before `include`: a kb-only install would
    otherwise be the only one to refuse a collision that a plain install renders past."""
    first = Definition(name="kb-probe", kind=Kind.COMMAND, body="one")
    second = Definition(name="kb-probe", kind=Kind.COMMAND, body="two")
    monkeypatch.setattr("adjagent.render.discover", lambda: [("m.a", (first,)), ("m.b", (second,))])
    with pytest.raises(InputError, match=re.escape("'commands/kb-probe.md' is produced by both m.a and m.b")):
        definitions(include=lambda defn: not excluded(defn.name))


def test_a_default_install_writes_no_kb_definition_and_no_kb_side_config(tmp_path: Path) -> None:
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    _definition_install(root, project_root=project)
    plugin = _claude_plugin(root)
    files = _files(plugin)
    assert "agents/python-coder.md" in files
    for relative in (
        *_KB_DEFINITIONS,
        *_KB_SKILL_FILES,
        "skills/kbase/kb-tools/runner-snippets/kb.just",
    ):
        assert relative not in files
    assert not (plugin / "skills/kbase").exists()
    assert not (plugin / ".mcp.json").exists() and not (project / ".mcp.json").exists()
    assert (project / "justfile").read_text(encoding="utf-8") == "# mine\n"
    assert not (project / "Makefile").exists()


def test_a_kb_install_writes_the_kb_definitions_the_package_the_mcp_entry_and_the_include_line(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    _definition_install(root, with_kb=True, project_root=project)
    plugin = _claude_plugin(root)
    for relative in (*_KB_DEFINITIONS, *_KB_SKILL_FILES):
        assert (plugin / relative).is_file()
    kb_just = (plugin / "skills/kbase/kb-tools/runner-snippets/kb.just").read_text(encoding="utf-8").split("\n")
    source_just = (PACKAGE_ROOT / "kb-tools/runner-snippets/kb.just").read_text(encoding="utf-8").split("\n")
    kb_mk = (plugin / "skills/kbase/kb-tools/runner-snippets/kb.mk").read_text(encoding="utf-8").split("\n")
    assert kb_just[0].startswith("# !INSTALLED! from adjagent/kb-tools/runner-snippets/kb.just — ")
    assert kb_just[1:] == source_just
    assert kb_mk[0].startswith("# !INSTALLED! from adjagent/kb-tools/runner-snippets/kb.mk — ")
    assert json.loads((plugin / ".mcp.json").read_text(encoding="utf-8")) == {
        "mcpServers": {"kbase": {"command": "kbase", "args": ["mcp"]}}
    }
    assert not (project / ".mcp.json").exists()
    assert (project / "justfile").read_text(encoding="utf-8") == (
        f"# mine\n\nimport? '{_CLAUDE_PLUGIN_RELPATH}/skills/kbase/kb-tools/runner-snippets/kb.just'\n"
    )
    captured = capsys.readouterr()
    assert f"wrote {plugin / '.mcp.json'} with the kbase MCP entry" in captured.out
    assert "appended the KB include line" in captured.out


def test_an_installed_kbase_router_makes_a_plain_install_sticky(tmp_path: Path) -> None:
    """A plain install into a root whose kbase router carries this repository's banner is a kb install:
    the kbase skill's files and the kb-tools package stay."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    _definition_install(root, with_kb=True, project_root=project)
    _definition_install(root, project_root=project)
    after = _files(_claude_plugin(root))
    for relative in (*_KB_DEFINITIONS, *_KB_SKILL_FILES, "skills/kbase/kb-tools/runner-snippets/kb.just"):
        assert relative in after


def test_a_flat_layout_kbase_router_makes_a_plain_install_into_the_plugin_sticky(tmp_path: Path) -> None:
    """An install over the layout that wrote straight into the harness directory reads that layout's
    router too, so the first plain install after the upgrade keeps kb, in the plugin."""
    project = tmp_path
    root = project / ".claude"
    router = root / "skills/kbase/SKILL.md"
    router.parent.mkdir(parents=True)
    router.write_text(_rendered(_CLAUDE_RENDER, "skills/kbase/SKILL.md"), encoding="utf-8")
    _definition_install(root, project_root=project)
    after = _files(_claude_plugin(root))
    for relative in (*_KB_SKILL_FILES, "skills/kbase/kb-tools/runner-snippets/kb.just"):
        assert relative in after
    assert not router.exists()


def test_a_sticky_install_removes_the_executable_an_earlier_version_installed(tmp_path: Path) -> None:
    """A root the router makes a kb install, still holding the `kbase` executable and its signature an
    earlier version placed in kb-tools/, loses both — the destination is replaced whole — and its MCP
    entry names the bare command rather than the installed executable."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    _definition_install(root, with_kb=True, project_root=project)
    plugin = _claude_plugin(root)
    executable = plugin / "skills/kbase/kb-tools/kbase"
    executable.write_bytes(_KBASE_BYTES)
    signature = executable.with_name("kbase.asc")
    signature.write_bytes(b"-----BEGIN PGP SIGNATURE-----\n")
    (plugin / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"kbase": {"command": "skills/kbase/kb-tools/kbase", "args": ["mcp"]}}}),
        encoding="utf-8",
    )
    _definition_install(root, project_root=project)
    assert not executable.exists() and not signature.exists()
    assert (plugin / "skills/kbase/kb-tools/runner-snippets/kb.just").is_file()
    settings = json.loads((plugin / ".mcp.json").read_text(encoding="utf-8"))
    assert settings == {"mcpServers": {"kbase": {"command": "kbase", "args": ["mcp"]}}}


def test_a_projects_own_unbannered_kbase_skill_leaves_a_plain_install_plain(tmp_path: Path) -> None:
    """The router counts only when it carries this repository's banner: a `skills/kbase/SKILL.md` the
    project wrote is not a kb install's evidence — no kb definitions, no MCP entry, and the runner file
    and that file untouched."""
    project = tmp_path
    root = project / ".claude"
    router = root / "skills/kbase/SKILL.md"
    router.parent.mkdir(parents=True)
    mine = "---\nname: kbase\ndescription: mine\n---\n\nmy own skill\n"
    router.write_text(mine, encoding="utf-8")
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    _definition_install(root, project_root=project)
    files = _files(root)
    for relative in (*_KB_DEFINITIONS, *_KB_SKILL_FILES):
        if relative != "skills/kbase/SKILL.md":
            assert relative not in files
    assert not (root / "skills/kbase/kb-tools").exists()
    assert router.read_text(encoding="utf-8") == mine
    assert not (project / ".mcp.json").exists()
    assert (project / "justfile").read_text(encoding="utf-8") == "# mine\n"


def test_a_kb_tools_tree_without_the_router_is_not_sticky(tmp_path: Path) -> None:
    """The router is the signal, not the directory: a tree whose kb-tools destination holds files but
    no kbase router beside it is not a kb install's evidence, so a plain install stays plain — no kb
    definitions, no MCP entry, no runner include line, and the tree left as it was found."""
    project = tmp_path
    root = project / ".claude"
    plugin = _claude_plugin(root)
    snippets = plugin / "skills/kbase/kb-tools/runner-snippets"
    snippets.mkdir(parents=True)
    (snippets / "kb.just").write_text("# stale snippet\n", encoding="utf-8")
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    _definition_install(root, project_root=project)
    files = _files(plugin)
    for relative in (*_KB_DEFINITIONS, *_KB_SKILL_FILES):
        assert relative not in files
    assert (snippets / "kb.just").read_text(encoding="utf-8") == "# stale snippet\n"
    assert not (plugin / ".mcp.json").exists()
    assert (project / "justfile").read_text(encoding="utf-8") == "# mine\n"


def test_the_version_flag_prints_the_constant_and_nothing_else(capsys) -> None:
    """A recipe parses this line to cut the tag, so it is the constant alone: no `v`, no suffix, no
    prose, one line — and the constant carries that shape, which a manifest would inherit too."""
    with pytest.raises(SystemExit) as exited:
        main(["--version"])
    assert exited.value.code == 0
    assert capsys.readouterr().out == f"{__version__}\n"
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_version_is_refused_as_a_verb(capsys) -> None:
    with pytest.raises(SystemExit) as exited:
        main(["version"])
    assert exited.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_the_cli_with_kb_flag_installs_the_kb_skill_files_and_the_skill_kb_tools_destination(
    tmp_path: Path,
) -> None:
    """`--with-kb` reaches `install()`: driven through the CLI entry point, the flag's own effect —
    the kbase skill's files and the runner snippets — is what appears under ROOT."""
    root = tmp_path / ".claude"
    root.mkdir()
    main(["install", str(root), "--harness=claude", "--with-kb"])
    plugin = _claude_plugin(root)
    assert all((plugin / relative).is_file() for relative in _KB_SKILL_FILES)
    snippets = plugin / "skills/kbase/kb-tools/runner-snippets"
    assert (snippets / "kb.just").is_file() and (snippets / "kb.mk").is_file()


def test_an_excluded_run_prunes_a_stale_kb_definition_it_did_not_write(tmp_path: Path, capsys) -> None:
    root = tmp_path / ".claude"
    (root / "agents").mkdir(parents=True)
    (root / "agents/kb-maintainer.md").write_text(_NEW_BANNER, encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    assert not (root / "agents/kb-maintainer.md").exists()
    assert f"pruned {root / 'agents/kb-maintainer.md'}" in capsys.readouterr().out


def test_a_kb_install_prunes_a_stale_reference_and_keeps_a_user_file(tmp_path: Path, capsys) -> None:
    """A supporting file is ours by its own first line, so prune needs no rule keyed on the skill."""
    root = tmp_path / ".claude"
    plugin = _claude_plugin(root)
    references = plugin / "skills/kbase/references"
    references.mkdir(parents=True)
    stale = references / "gone.md"
    stale.write_text(f"{_COMMENT_BANNER}\n\nold text\n", encoding="utf-8")
    mine = plugin / "skills/kbase/notes.md"
    mine.write_text("---\nmine\n---\n", encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, with_kb=True, project_root=tmp_path)
    assert not stale.exists()
    assert mine.read_text(encoding="utf-8") == "---\nmine\n---\n"
    assert all((plugin / relative).is_file() for relative in _KB_SKILL_FILES)
    assert f"pruned {stale}" in capsys.readouterr().out


def test_a_plain_install_prunes_every_kbase_reference_left_without_its_router(tmp_path: Path, capsys) -> None:
    """A skill is one keep/drop decision: a ROOT holding the skill's references without its router —
    the router being the sticky signal — is a plain install, and every reference goes."""
    root = tmp_path / ".claude"
    references = [relative for relative in _KB_SKILL_FILES if not relative.endswith("SKILL.md")]
    for relative in references:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{_COMMENT_BANNER}\n\nbody\n", encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    assert not (root / "skills/kbase").exists()
    pruned = {line for line in capsys.readouterr().out.splitlines() if line.startswith("pruned ")}
    assert pruned == {f"pruned {root / relative}" for relative in references}


def test_prune_recognizes_the_banner_the_renderer_writes(tmp_path: Path, capsys) -> None:
    """The recognizer reads what `render_definition` emits, not a prefix typed into the test."""
    root = tmp_path / ".claude"
    (root / "commands").mkdir(parents=True)
    stale = root / "commands/stale.md"
    stale.write_text(
        render_definition(
            Definition(name="stale", kind=Kind.COMMAND, body="body"),
            _CLAUDE_RENDER,
            module="adjagent.definitions.probe",
        ),
        encoding="utf-8",
    )
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    assert not stale.exists()
    assert f"pruned {stale}" in capsys.readouterr().out


def test_a_banner_naming_a_foreign_module_is_not_ours(tmp_path: Path) -> None:
    """The payload has to name a module path this repository writes; the bare mark is not enough."""
    root = tmp_path / ".claude"
    (root / "skills/probe/references").mkdir(parents=True)
    mine = root / "skills/probe/references/mine.md"
    text = "<!-- !GENERATED! from someone/else.md — x -->\n<!-- !TUNING! y -->\n\nbody\n"
    mine.write_text(text, encoding="utf-8")
    _definition_install(root, project_root=tmp_path)
    assert mine.read_text(encoding="utf-8") == text


def test_prune_leaves_a_symlink_standing(tmp_path: Path) -> None:
    """Prune removes regular files only: a symlink under a surface is the consumer's, whatever it
    points at."""
    root = tmp_path / ".claude"
    (root / "agents").mkdir(parents=True)
    target = tmp_path / "outside.md"
    target.write_text(_NEW_BANNER, encoding="utf-8")
    link = root / "agents/link.md"
    link.symlink_to(target)
    _definition_install(root, project_root=tmp_path)
    assert link.is_symlink()
    assert target.read_text(encoding="utf-8") == _NEW_BANNER


@pytest.mark.parametrize("kb", [False, True], ids=["plain", "kb"])
def test_every_install_removes_each_legacy_tree_and_names_it(tmp_path: Path, capsys, kb: bool) -> None:
    project = tmp_path
    root = project / ".claude"
    planted = (
        "agents/kb_tools/kb_util.py",
        "adj-tools/kb-tools/stale.py",
        "agents/kb-tools/stale.py",
        "agents/liaison_tools/liaison_util.py",
    )
    for relative in planted:
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text("# legacy\n", encoding="utf-8")
    capsys.readouterr()
    if kb:
        _definition_install(root, with_kb=True, project_root=project)
    else:
        _definition_install(root, project_root=project)
    out = capsys.readouterr().out
    for relative in planted:
        tree = root / Path(relative).parent
        assert not tree.exists()
        assert f"removed legacy tree {tree}" in out
    message = "legacy kb_tools removed. if you are using kb functionality install using `install-with-kb`"
    assert (message in out) == (not kb)


def test_the_mcp_merge_keeps_every_unrelated_key(tmp_path: Path) -> None:
    """The entry is replaced where it stands — the installed-executable command an earlier version
    wrote does not survive, so an upgraded project needs no hand edit — and every key beside it is
    kept."""
    project = tmp_path
    root = project / ".claude"
    settings = _claude_mcp_file(root)
    settings.write_text(
        json.dumps(
            {
                "permissions": {"allow": ["Bash"]},
                "mcpServers": {
                    "other": {"command": "x"},
                    "kbase": {"command": "skills/kbase/kb-tools/kbase", "args": ["mcp"]},
                },
            }
        ),
        encoding="utf-8",
    )
    _definition_install(root, with_kb=True, project_root=project)
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["permissions"] == {"allow": ["Bash"]}
    assert data["mcpServers"]["other"] == {"command": "x"}
    assert data["mcpServers"]["kbase"] == {"command": "kbase", "args": ["mcp"]}


def test_the_opencode_mcp_entry_lands_in_the_discovered_file_in_the_v2_shape(tmp_path: Path) -> None:
    project = tmp_path
    root = project / ".opencode"
    root.mkdir()
    discovered = root / "opencode.json"
    discovered.write_text(
        json.dumps({"theme": "omlx", "mcp": {"servers": {"other": {"type": "local"}}}}), encoding="utf-8"
    )
    _definition_install(root, _OPENCODE_RENDER, with_kb=True, project_root=project)
    text = discovered.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["theme"] == "omlx"
    assert data["mcp"]["servers"]["other"] == {"type": "local"}
    assert data["mcp"]["servers"]["kbase"] == {"type": "local", "command": ["kbase", "mcp"]}
    assert "enabled" not in text
    assert not (root / "opencode.jsonc").exists()


@pytest.mark.parametrize(
    "harness_dir, ctx, canonical, kbase_entry",
    [
        (
            ".claude",
            _CLAUDE_RENDER,
            f"{_CLAUDE_PLUGIN_RELPATH}/.mcp.json",
            {"mcpServers": {"kbase": {"command": "kbase", "args": ["mcp"]}}},
        ),
        (
            ".opencode",
            _OPENCODE_RENDER,
            ".opencode/opencode.jsonc",
            {"mcp": {"servers": {"kbase": {"type": "local", "command": ["kbase", "mcp"]}}}},
        ),
    ],
    ids=["claude", "opencode"],
)
def test_the_mcp_settings_file_is_created_when_absent(
    tmp_path: Path, harness_dir: str, ctx: Render, canonical: str, kbase_entry: dict
) -> None:
    root = tmp_path / harness_dir
    root.mkdir()
    _definition_install(root, ctx, with_kb=True, project_root=tmp_path)
    text = (tmp_path / canonical).read_text(encoding="utf-8")
    assert json.loads(text) == kbase_entry
    assert "enabled" not in text
    # The server finds the KB from the directory it is started in, so the written entry names no root.
    assert "--kb-root" not in text


# mage's settings file is the plugin's own, at ROOT rather than at the project the plugin is installed
# under.


def test_a_mage_kb_install_keeps_its_mcp_entry_beside_the_plugin_at_root(tmp_path: Path) -> None:
    """ROOT is the plugin's own directory, so the settings file resolves against ROOT — the project root
    holds no `.mcp.json` at all — and the manifest is still the three-key one carrying `__version__`. No
    runner include line is written and no `Makefile` created at either root: a plugin is not a repo
    project."""
    project = tmp_path
    root = project / "plugins/adjagent"
    root.mkdir(parents=True)
    _definition_install(root, _MAGE_RENDER, with_kb=True, project_root=project)
    settings = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
    assert settings == {"mcpServers": {"kbase": {"command": "kbase", "args": ["mcp", "--project-dir-required"]}}}
    assert not (project / ".mcp.json").exists()
    manifest = json.loads((root / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert set(manifest) == {"name", "version", "description"}
    assert manifest["version"] == __version__
    assert not (root / "Makefile").exists()
    assert not (project / "Makefile").exists()


def test_a_mage_install_includes_kb_without_the_flag(tmp_path: Path) -> None:
    """A plugin's product is the kb set, so a plain mage install is a kb install: no `with_kb` argument
    is passed and the settings file lands beside the plugin carrying the entry, beside the kbase skill
    and its kb-tools package."""
    project = tmp_path
    root = project / "plugins/adjagent"
    root.mkdir(parents=True)
    _definition_install(root, _MAGE_RENDER, project_root=project)
    settings = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
    assert settings == {"mcpServers": {"kbase": {"command": "kbase", "args": ["mcp", "--project-dir-required"]}}}
    assert all((root / relative).is_file() for relative in _KB_SKILL_FILES)
    assert (root / "skills/kbase/kb-tools/runner-snippets/kb.just").is_file()
    assert not (project / ".mcp.json").exists()


def test_a_later_mage_install_over_a_kb_root_leaves_the_mcp_entry_standing(tmp_path: Path) -> None:
    """ROOT's top-level settings file is outside every prune surface, so a later install neither
    removes it nor rewrites it: it re-splices the same entry, byte for byte."""
    project = tmp_path
    root = project / "plugins/adjagent"
    root.mkdir(parents=True)
    _definition_install(root, _MAGE_RENDER, with_kb=True, project_root=project)
    written = (root / ".mcp.json").read_text(encoding="utf-8")
    _definition_install(root, _MAGE_RENDER, project_root=project)
    assert (root / ".mcp.json").read_text(encoding="utf-8") == written


# A mage install is a plugin directory that is carried or published from where it stands: nothing in it
# names this machine, nothing in it fires a hook, and the manifest is owned by the marker it states.

_MAGE_MANIFEST = ".claude-plugin/plugin.json"


def test_a_mage_install_names_no_absolute_path_and_no_home_directory(tmp_path: Path) -> None:
    """Nothing the plugin writes names the directory it lands in, because that directory moves. The `~/`
    search is over the manifest and the MCP settings file alone: a definition's prose names `~/.config` in
    order to forbid hardcoding it, so a tree-wide search reports the advice rather than a path."""
    project = tmp_path
    root = project / "plugins/adjagent"
    root.mkdir(parents=True)
    _definition_install(root, _MAGE_RENDER, with_kb=True, project_root=project)
    files = _files(root)
    ours = (_MAGE_MANIFEST, ".mcp.json")
    assert set(ours) <= set(files)
    absolute = str(root.resolve()).encode()
    assert [relative for relative, data in files.items() if absolute in data] == []
    assert [relative for relative in ours if b"~/" in files[relative]] == []


def test_a_mage_install_ships_no_hook_and_writes_no_settings_file(tmp_path: Path) -> None:
    """mage has no guardrail, so no script lands under ROOT and no guardrail settings file appears
    either beside the plugin or at the project it installs into — as an opencode install writes none."""
    project = tmp_path
    root = project / "plugins/adjagent"
    root.mkdir(parents=True)
    _definition_install(root, _MAGE_RENDER, project_root=project)
    assert not (root / "hooks").exists()
    assert not (project / ".claude/settings.json").exists()
    assert not (root / ".claude/settings.json").exists()


def test_a_second_mage_install_passes_over_its_own_manifest_byte_identical(tmp_path: Path) -> None:
    """The manifest is JSON, which no generated banner rides in front of, so the marker the file states
    about itself is what makes it ours: an install over one this repository wrote is not refused and
    not pruned, and rewrites the same bytes."""
    project = tmp_path
    root = project / "plugins/adjagent"
    root.mkdir(parents=True)
    _definition_install(root, _MAGE_RENDER, project_root=project)
    manifest = root / _MAGE_MANIFEST
    written = manifest.read_bytes()
    _definition_install(root, _MAGE_RENDER, project_root=project)
    assert manifest.read_bytes() == written


def test_an_operators_manifest_without_the_marker_is_refused_with_nothing_written(tmp_path: Path) -> None:
    """A plugin of another name at that path is the operator's own, so the install refuses it whole and
    names it, writing nothing — no render lands before the refusal."""
    project = tmp_path
    root = project / "plugins/adjagent"
    manifest = root / _MAGE_MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"name": "other"}\n', encoding="utf-8")
    before = _files(tmp_path)
    with pytest.raises(InputError, match=re.escape(f"'{manifest}'")):
        _definition_install(root, _MAGE_RENDER, project_root=project)
    assert _files(tmp_path) == before


def test_a_verbose_mage_install_lists_the_manifest_as_written(tmp_path: Path, capsys) -> None:
    project = tmp_path
    root = project / "plugins/adjagent"
    root.mkdir(parents=True)
    capsys.readouterr()
    install(
        root, _MAGE_RENDER, verbose=True, project_root=project, uncommitted=_committed, tool_install=_ToolInstalls()
    )
    assert f"wrote {root / _MAGE_MANIFEST}" in capsys.readouterr().out.splitlines()


def test_an_mcp_file_carrying_jsonc_comments_is_reported_and_left_untouched(tmp_path: Path, capsys) -> None:
    root = tmp_path / ".opencode"
    root.mkdir()
    discovered = root / "opencode.json"
    prior = '{\n  // my own server\n  "mcp": {"servers": {}}\n}\n'
    discovered.write_text(prior, encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, _OPENCODE_RENDER, with_kb=True, project_root=tmp_path)
    assert discovered.read_text(encoding="utf-8") == prior
    assert f"{discovered} carries JSONC comments — left untouched; merge this entry by hand:" in capsys.readouterr().err


def _built_entry(harness: Harness) -> dict:
    """The `kbase` entry `harness`'s builder makes for the bare `kbase` command — the value the splice
    is expected to have placed, read from the builder rather than restated."""
    entry, _ = harness.mcp.entry(command=KBASE_NAME)
    return entry


def test_the_mcp_splice_leaves_every_byte_outside_the_entry_slot(tmp_path: Path) -> None:
    """A settings file the consumer wrote is theirs: four-space indentation, a compact one-line object
    beside ours, key order and the number spelling `2.50` all come back as they were, only our slot
    being touched."""
    project = tmp_path
    root = project / ".claude"
    mcp = _claude_mcp_file(root)
    seed = (
        "{\n"
        '    "permissions": {"allow": ["Bash", "Read"], "deny": []},\n'
        '    "mcpServers": {\n'
        '        "other": {"command": "x", "args": [1, 2.50, true]}\n'
        "    },\n"
        '    "theme": "dark"\n'
        "}\n"
    )
    mcp.write_text(seed, encoding="utf-8")
    _definition_install(root, with_kb=True, project_root=project)
    text = mcp.read_text(encoding="utf-8")
    head, other, tail = seed.partition('"other": {"command": "x", "args": [1, 2.50, true]}')
    assert other and text.startswith(head) and text.endswith(tail)
    before = json.loads(seed)
    before["mcpServers"]["kbase"] = _built_entry(CLAUDE)
    assert json.loads(text) == before


def test_a_compact_one_line_mcp_file_gains_the_entry_inline(tmp_path: Path) -> None:
    """The file states no indent, so none is invented: the entry goes in on the line it finds."""
    project = tmp_path
    root = project / ".claude"
    mcp = _claude_mcp_file(root)
    mcp.write_text('{"mcpServers": {}}', encoding="utf-8")
    _definition_install(root, with_kb=True, project_root=project)
    text = mcp.read_text(encoding="utf-8")
    assert "\n" not in text
    assert json.loads(text) == {"mcpServers": {"kbase": _built_entry(CLAUDE)}}


def test_a_settings_file_without_the_container_gains_it_whole(tmp_path: Path) -> None:
    """`mcpServers` absent is not a reason to reserialize: the container goes in as one member, on a
    line indented like the sibling it lands beside."""
    project = tmp_path
    root = project / ".claude"
    mcp = _claude_mcp_file(root)
    seed = '{\n  "permissions": {"allow": ["Bash"]}\n}\n'
    mcp.write_text(seed, encoding="utf-8")
    _definition_install(root, with_kb=True, project_root=project)
    text = mcp.read_text(encoding="utf-8")
    assert text.startswith('{\n  "permissions": {"allow": ["Bash"]},\n  "mcpServers": ')
    assert text.endswith("\n}\n")
    assert json.loads(text) == {
        "permissions": {"allow": ["Bash"]},
        "mcpServers": {"kbase": _built_entry(CLAUDE)},
    }


def test_an_existing_kbase_entry_is_replaced_where_it_stands(tmp_path: Path) -> None:
    """Our value replaces the entry's, and every other member — including the one written after it —
    keeps its bytes: an upgraded project loses an absolute command without a hand edit."""
    project = tmp_path
    root = project / ".claude"
    mcp = _claude_mcp_file(root)
    prior = '{"command": "/old/absolute/kbase", "args": ["mcp", "--kb-root", "/old"]}'
    seed = f'{{\n  "mcpServers": {{\n    "kbase": {prior},\n    "other": {{"command": "x"}}\n  }}\n}}\n'
    mcp.write_text(seed, encoding="utf-8")
    _definition_install(root, with_kb=True, project_root=project)
    text = mcp.read_text(encoding="utf-8")
    head, found, tail = seed.partition(prior)
    assert found and text.startswith(head) and text.endswith(tail)
    assert json.loads(text)["mcpServers"] == {"kbase": _built_entry(CLAUDE), "other": {"command": "x"}}


def test_a_crlf_mcp_file_keeps_its_line_endings(tmp_path: Path) -> None:
    """Byte reading and writing with no newline translation, and the entry's own lines take the file's
    ending: a CRLF file stays CRLF through the merge."""
    project = tmp_path
    root = project / ".claude"
    mcp = _claude_mcp_file(root)
    seed = '{\r\n  "mcpServers": {\r\n  }\r\n}\r\n'
    mcp.write_bytes(seed.encode("utf-8"))
    _definition_install(root, with_kb=True, project_root=project)
    raw = mcp.read_bytes()
    assert b"\n" not in raw.replace(b"\r\n", b"")
    assert json.loads(raw.decode("utf-8")) == {"mcpServers": {"kbase": _built_entry(CLAUDE)}}


def test_a_duplicate_container_key_is_reported_and_left_byte_identical(tmp_path: Path, capsys) -> None:
    """The file names `mcpServers` twice, so the splice cannot say which one is meant: it reports and
    writes nothing — the install still succeeded — rather than picking one."""
    project = tmp_path
    root = project / ".claude"
    mcp = _claude_mcp_file(root)
    seed = '{"mcpServers": {"other": {"command": "x"}}, "mcpServers": {}}\n'
    mcp.write_text(seed, encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, with_kb=True, project_root=project)
    assert mcp.read_text(encoding="utf-8") == seed
    err = capsys.readouterr().err
    entry = _built_entry(CLAUDE)
    assert f"{mcp} could not be edited safely — left untouched; merge this entry by hand:" in err
    assert json.dumps(entry) in err


def test_the_opencode_container_is_spliced_into_a_plain_json_file(tmp_path: Path) -> None:
    """opencode reaches the splice whenever the file it discovers is plain JSON — the `.jsonc` name it
    prefers says nothing about the content — so its three-level `mcp.servers` container is placed the
    same way, every other byte kept."""
    project = tmp_path
    root = project / ".opencode"
    root.mkdir()
    discovered = root / "opencode.json"
    seed = '{\n  "theme": "omlx",\n  "mcp": {\n    "servers": {\n      "other": {"type": "local"}\n    }\n  }\n}\n'
    discovered.write_text(seed, encoding="utf-8")
    _definition_install(root, _OPENCODE_RENDER, with_kb=True, project_root=project)
    text = discovered.read_text(encoding="utf-8")
    head, other, tail = seed.partition('"other": {"type": "local"}')
    assert other and text.startswith(head) and text.endswith(tail)
    assert json.loads(text)["mcp"]["servers"]["kbase"] == _built_entry(OPENCODE)


def test_the_include_line_is_appended_to_an_existing_justfile(tmp_path: Path) -> None:
    root = tmp_path / ".claude"
    root.mkdir()
    (tmp_path / "justfile").write_text("default:\n  @echo hi\n", encoding="utf-8")
    _definition_install(root, with_kb=True, project_root=tmp_path)
    assert (tmp_path / "justfile").read_text(encoding="utf-8") == (
        f"default:\n  @echo hi\n\nimport? '{_CLAUDE_PLUGIN_RELPATH}/skills/kbase/kb-tools/runner-snippets/kb.just'\n"
    )


def test_a_makefile_is_created_when_the_project_has_neither_runner_file(tmp_path: Path) -> None:
    root = tmp_path / ".opencode"
    root.mkdir()
    _definition_install(root, _OPENCODE_RENDER, with_kb=True, project_root=tmp_path)
    text = (tmp_path / "Makefile").read_text(encoding="utf-8")
    assert text.startswith("# Makefile — created by the adjagent installer.\n")
    assert "-include .opencode/skills/kbase/kb-tools/runner-snippets/kb.mk\n" in text
    assert not (tmp_path / "justfile").exists()


def test_a_second_harness_writes_no_include_line_and_reports_the_first(tmp_path: Path, capsys) -> None:
    project = tmp_path
    first = project / ".claude"
    first.mkdir()
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    _definition_install(first, with_kb=True, project_root=project)
    before = (project / "justfile").read_bytes()
    second = project / ".opencode"
    second.mkdir()
    capsys.readouterr()
    _definition_install(second, _OPENCODE_RENDER, with_kb=True, project_root=project)
    assert (project / "justfile").read_bytes() == before
    err = capsys.readouterr().err
    assert "no include line written" in err and "'claude'" in err


@pytest.mark.parametrize(
    "snippets_path",
    [
        "agents/kb-tools/runner-snippets",
        "agents/kb_tools/runner-snippets",
        "adj-tools/kb-tools/runner-snippets",
        "custom/kb-tools/runner-snippets",
        "kb-tools/runner-snippets",
        "skills/kbase/kb-tools/runner-snippets",
    ],
    ids=["hyphen", "underscore", "adj-tools", "hand-written", "short-tree", "flat-layout"],
)
def test_an_include_line_for_this_harness_under_any_tree_is_rewritten_in_place(
    tmp_path: Path, capsys, snippets_path: str
) -> None:
    """A line naming this harness directory is this install's line whatever tree its path spells — a
    legacy destination's, the layout that wrote straight into the harness directory, or one no release
    here wrote — so its whole path is replaced where it stands, naming the plugin's snippets, and the
    file keeps one include line rather than gaining a second beside a dead one."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    (project / "justfile").write_text(f"default:\n  @echo hi\n\nimport? '.claude/{snippets_path}/kb.just'\n")
    capsys.readouterr()
    _definition_install(root, with_kb=True, project_root=project)
    text = (project / "justfile").read_text(encoding="utf-8")
    expected = f"import? '{_CLAUDE_PLUGIN_RELPATH}/skills/kbase/kb-tools/runner-snippets/kb.just'"
    assert text == f"default:\n  @echo hi\n\n{expected}\n"
    assert text.count("runner-snippets") == 1
    assert "rewrote the KB include line" in capsys.readouterr().out


@pytest.mark.parametrize(
    "snippets_path",
    ["agents/kb-tools/runner-snippets", "custom/kb-tools/runner-snippets"],
    ids=["legacy", "hand-written"],
)
def test_an_include_line_for_another_harness_is_reported_and_left(tmp_path: Path, capsys, snippets_path: str) -> None:
    project = tmp_path
    root = project / ".opencode"
    root.mkdir()
    line = f"import? '.claude/{snippets_path}/kb.just'"
    (project / "justfile").write_text(f"{line}\n", encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, _OPENCODE_RENDER, with_kb=True, project_root=project)
    assert (project / "justfile").read_text(encoding="utf-8") == f"{line}\n"
    err = capsys.readouterr().err
    assert "no include line written" in err and "'claude'" in err


@pytest.mark.parametrize(
    "prior, expected",
    [
        (
            "# import? '.claude/agents/kb-tools/runner-snippets/kb.just'\n",
            "# import? '.claude/agents/kb-tools/runner-snippets/kb.just'\n"
            "\nimport? '.claude/skills/kbase/kb-tools/runner-snippets/kb.just'\n",
        ),
        (
            "import? '.claude/agents/kb-tools/runner-snippets/kb.just'  # mine\n",
            "import? '.claude/skills/kbase/kb-tools/runner-snippets/kb.just'  # mine\n",
        ),
        (
            "default:\r\n  @echo hi\r\n\r\nimport? '.claude/agents/kb-tools/runner-snippets/kb.just'\r\n",
            "default:\r\n  @echo hi\r\n\r\nimport? '.claude/skills/kbase/kb-tools/runner-snippets/kb.just'\r\n",
        ),
    ],
    ids=["commented-out", "trailing-comment", "crlf"],
)
def test_the_include_line_rewrite_touches_only_its_own_path_token(tmp_path: Path, prior: str, expected: str) -> None:
    """A commented line is not an include; a rewrite replaces the snippets path alone, keeping an
    assignment's left-hand side, a trailing comment and the file's own line endings."""
    (tmp_path / "justfile").write_bytes(prior.encode("utf-8"))
    install_kb_include_line(tmp_path, harness_relpath=".claude")
    assert (tmp_path / "justfile").read_bytes() == expected.encode("utf-8")


def test_a_makefile_include_line_is_recognized_by_the_same_shape(tmp_path: Path) -> None:
    """The `-include` form is matched on the path's shape too, the Makefile's own snippet being
    `kb.mk`: a stale tree is rewritten in place and no second line lands beside it."""
    prior = "all:\n\t@echo hi\n\n-include .opencode/adj-tools/kb-tools/runner-snippets/kb.mk\n"
    (tmp_path / "Makefile").write_text(prior, encoding="utf-8")
    install_kb_include_line(tmp_path, harness_relpath=".opencode")
    text = (tmp_path / "Makefile").read_text(encoding="utf-8")
    assert text == "all:\n\t@echo hi\n\n-include .opencode/skills/kbase/kb-tools/runner-snippets/kb.mk\n"


def test_two_include_lines_are_reported_and_left(tmp_path: Path, capsys) -> None:
    """Rewriting one of two would leave the other stale, so the operator merges them by hand."""
    prior = (
        "import? '.claude/agents/kb-tools/runner-snippets/kb.just'\n"
        "import? '.claude/skills/kbase/kb-tools/runner-snippets/kb.just'\n"
    )
    (tmp_path / "justfile").write_text(prior, encoding="utf-8")
    install_kb_include_line(tmp_path, harness_relpath=".claude")
    assert (tmp_path / "justfile").read_text(encoding="utf-8") == prior
    assert "names the kb snippets on lines 1, 2" in capsys.readouterr().err


def test_an_include_line_naming_no_harness_reports_its_raw_prefix() -> None:
    [match] = _named_harnesses(
        "default:\n  @echo hi\nimport? 'tools/skills/kbase/kb-tools/runner-snippets/kb.just'\n", runner="just"
    )
    assert (match.name, match.index) == ("tools", 2)


@pytest.mark.parametrize("runner, matched", [("just", True), ("make", False)], ids=["its-own", "the-others"])
def test_a_line_is_a_line_for_the_runner_whose_snippet_it_names(runner: str, matched: bool) -> None:
    """`kb.just` is the justfile's snippet and `kb.mk` the Makefile's, so one runner's snippet named in
    the other's file is not an include line that install has to rewrite."""
    text = "import? '.claude/kb-tools/runner-snippets/kb.just'\n"
    assert bool(_named_harnesses(text, runner=runner)) is matched


def test_a_non_utf8_runner_file_is_refused_before_the_first_write(tmp_path: Path) -> None:
    """The runner file is decoded with every other check: the refusal writes nothing, where a decode
    after the writes would leave a half-updated install and refuse the retry too."""
    root = tmp_path / ".claude"
    root.mkdir()
    (tmp_path / "justfile").write_bytes(b"\xff\xfe default:\n")
    before = _files(tmp_path)
    with pytest.raises(InputError, match="justfile"):
        _definition_install(root, with_kb=True, project_root=tmp_path)
    assert _files(tmp_path) == before


def test_the_repositorys_own_project_root_gets_no_include_line() -> None:
    before = (REPO_ROOT / "justfile").read_bytes()
    install_kb_include_line(REPO_ROOT, harness_relpath=".claude")
    assert (REPO_ROOT / "justfile").read_bytes() == before
    assert not (REPO_ROOT / "Makefile").exists()


@pytest.mark.parametrize(
    "root",
    [REPO_ROOT, PACKAGE_ROOT / "kb-tools", PACKAGE_ROOT / HARNESS_RESOURCES_SOURCE / "opencode"],
    ids=["repository", "kb-tools-source", "harness-resources-source"],
)
def test_install_refuses_the_repository_and_a_source_it_copies_from(root: Path) -> None:
    """Every tree a later install reads from is refused as a root: the repository itself, the kb
    toolchain's package, and a harness's resources — writes there would land inside this run's own
    input."""
    with pytest.raises(InputError, match="is this repository or inside a source it copies from"):
        install(root, _CLAUDE_RENDER, verbose=False, uncommitted=_committed, tool_install=_ToolInstalls())
    assert not (root / "agents" / "python-coder.md").exists() and not (root / "commands").exists()


def test_a_shipped_package_leaves_its_tests_and_documents_behind_and_refuses_a_root_inside_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What the docdicer tools row cannot exercise, its source holding neither: a package's tests and
    project documents do not ship, and a root inside a package's source is refused with nothing
    written. A row over a temporary source stands in for the table."""
    repo = tmp_path / "repo"
    package = repo / "adjagent" / "probe_pkg"
    (package / "tests").mkdir(parents=True)
    (package / "tool.py").write_text("print('probe')\n", encoding="utf-8")
    (package / "tests/test_tool.py").write_text("pass\n", encoding="utf-8")
    (package / "SPEC.md").write_text("# probe\n", encoding="utf-8")
    monkeypatch.setattr("adjagent.install.PACKAGE_ROOT", repo / "adjagent")
    monkeypatch.setattr("adjagent.install.SHIPPED_PACKAGES", (("probe_pkg", "adj-tools/probe_pkg"),))
    project = tmp_path / "project"
    root = project / ".claude"
    install(
        root, _CLAUDE_RENDER, verbose=False, project_root=project, uncommitted=_committed, tool_install=_ToolInstalls()
    )
    plugin = _claude_plugin(root)
    assert (plugin / "adj-tools/probe_pkg/tool.py").is_file()
    assert not (plugin / "adj-tools/probe_pkg/tests").exists()
    assert not (plugin / "adj-tools/probe_pkg/SPEC.md").exists()
    before = _files(tmp_path)
    with pytest.raises(InputError, match="is this repository or inside a source it copies from"):
        install(package, _CLAUDE_RENDER, verbose=False, uncommitted=_committed, tool_install=_ToolInstalls())
    assert _files(tmp_path) == before


def test_a_direct_install_into_the_user_directory_is_user_level(_home: Path) -> None:
    root = _home / ".claude"
    root.mkdir(parents=True)
    install(
        root, _CLAUDE_RENDER, verbose=False, project_root=_home, uncommitted=_committed, tool_install=_ToolInstalls()
    )
    assert (_claude_plugin(root) / "agents").is_dir()
    assert not (_claude_plugin(root) / "hooks").exists() and not (root / "settings.json").exists()


# The docdicer tools package: copied into the docdicer skill's own directory, its launcher stamped by
# name, and its venv rebuilt after an install that replaced it.

# Below a claude harness directory: the plugin's own docdicer tools destination.
_DOCDICER_TOOLS = f"{CLAUDE.plugin_dir}/skills/docdicer/tools"
_DOCDICER_SOURCE = PACKAGE_ROOT / "docdicer-tools"


def _preflighted(root: Path, *, project: Path, tool_install: _ToolInstalls, dry_run: bool = False) -> None:
    preflighted_install(
        root,
        _CLAUDE_RENDER,
        verbose=False,
        project_root=project,
        uncommitted=_committed,
        tool_install=tool_install,
        dry_run=dry_run,
    )


def _claude_project(tmp_path: Path) -> tuple[Path, Path]:
    """A project and its `.claude/` ROOT, both created."""
    project = tmp_path / "project"
    root = project / ".claude"
    root.mkdir(parents=True)
    return project, root


def _plant(path: Path, text: str = "planted\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_a_reinstall_replaces_the_docdicer_tools_whole_and_rebuilds_the_venv_that_stood(tmp_path: Path) -> None:
    """The stale file is a difference, so the install proceeds past the preflight; the copy it runs into
    holds no `.venv`, so only the real install calls the runner."""
    project, root = _claude_project(tmp_path)
    _preflighted(root, project=project, tool_install=_ToolInstalls())
    tools = root / _DOCDICER_TOOLS
    stale = _plant(tools / "stale.txt")
    marker = _plant(tools / ".venv/marker")
    runner = _ToolInstalls()
    _preflighted(root, project=project, tool_install=runner)
    script = tools / "docdicer"
    lines = script.read_text(encoding="utf-8").split("\n")
    source_lines = (_DOCDICER_SOURCE / "docdicer").read_text(encoding="utf-8").split("\n")
    assert lines[0] == source_lines[0] and lines[0].startswith("#!")
    assert lines[1].startswith("# !INSTALLED! from adjagent/docdicer-tools/docdicer")
    assert lines[2:] == source_lines[1:]
    assert os.access(script, os.X_OK)
    gitignore = (tools / ".gitignore").read_bytes()
    assert gitignore == (_DOCDICER_SOURCE / ".gitignore").read_bytes()
    assert ".venv/" in gitignore.decode("utf-8").splitlines()
    assert not stale.exists() and not marker.exists()
    assert runner.scripts == [script]


def test_an_install_with_no_docdicer_venv_runs_no_tool_install(tmp_path: Path) -> None:
    project, root = _claude_project(tmp_path)
    _plant(root / _DOCDICER_TOOLS / "stale.txt")
    runner = _ToolInstalls()
    install(root, _CLAUDE_RENDER, verbose=False, project_root=project, uncommitted=_committed, tool_install=runner)
    assert (root / _DOCDICER_TOOLS / "docdicer").is_file()
    assert runner.scripts == []


def test_an_up_to_date_target_with_a_docdicer_venv_runs_nothing(tmp_path: Path, capsys) -> None:
    project, root = _claude_project(tmp_path)
    _preflighted(root, project=project, tool_install=_ToolInstalls())
    _plant(root / _DOCDICER_TOOLS / ".venv/marker")
    state = _state(project)
    runner = _ToolInstalls()
    capsys.readouterr()
    _preflighted(root, project=project, tool_install=runner)
    assert _UP_TO_DATE in capsys.readouterr().out
    assert _state(project) == state
    assert runner.scripts == []


def test_a_dry_run_says_the_install_would_rebuild_the_docdicer_venv_and_runs_nothing(tmp_path: Path, capsys) -> None:
    """The venv is outside the comparison, so the one stale render is what makes the install proceed;
    the dry run names the venv rebuild that install would also make."""
    project, root = _claude_project(tmp_path)
    _preflighted(root, project=project, tool_install=_ToolInstalls())
    marker = _plant(root / _DOCDICER_TOOLS / ".venv/marker")
    _plant(root / "agents/gone.md", _NEW_BANNER)
    runner = _ToolInstalls()
    capsys.readouterr()
    _preflighted(root, project=project, tool_install=runner, dry_run=True)
    out = capsys.readouterr().out
    assert marker.is_file() and runner.scripts == []
    assert f".claude/{_DOCDICER_TOOLS}/.venv" in out and f".claude/{_DOCDICER_TOOLS}/docdicer --install" in out


def test_a_mode_change_alone_is_a_difference(tmp_path: Path, capsys) -> None:
    project, root = _claude_project(tmp_path)
    _preflighted(root, project=project, tool_install=_ToolInstalls())
    script = root / _DOCDICER_TOOLS / "docdicer"
    script.chmod(0o644)
    capsys.readouterr()
    _preflighted(root, project=project, tool_install=_ToolInstalls(), dry_run=True)
    assert _dry_run_groups(capsys.readouterr().out) == {"changed": {f".claude/{_DOCDICER_TOOLS}/docdicer"}}
    _preflighted(root, project=project, tool_install=_ToolInstalls())
    assert _UP_TO_DATE not in capsys.readouterr().out
    assert os.access(script, os.X_OK)


def test_a_failed_tool_install_is_reported_and_the_install_completes(tmp_path: Path, capsys) -> None:
    project, root = _claude_project(tmp_path)
    _definition_install(root, project_root=project)
    _plant(root / _DOCDICER_TOOLS / ".venv/marker")
    capsys.readouterr()
    install(
        root,
        _CLAUDE_RENDER,
        verbose=False,
        project_root=project,
        uncommitted=_committed,
        tool_install=_ToolInstalls(failure="exited 1"),
    )
    assert all(
        (_claude_plugin(root) / path).is_file()
        for path, _ in render_all(_CLAUDE_RENDER, include=lambda d: not excluded(d.name))
    )
    assert (root / _DOCDICER_TOOLS / "docdicer").is_file() and (root / _DOCDICER_TOOLS / ".gitignore").is_file()
    script = str(root / _DOCDICER_TOOLS / "docdicer")
    assert len([line for line in capsys.readouterr().out.splitlines() if script in line]) == 1


def test_a_user_level_install_ships_no_docdicer_tools_and_runs_no_tool_install(_home: Path) -> None:
    root = _home / ".claude"
    marker = _plant(root / _DOCDICER_TOOLS / ".venv/marker")
    runner = _ToolInstalls()
    install(root, _CLAUDE_RENDER, verbose=False, project_root=_home, uncommitted=_committed, tool_install=runner)
    assert not (root / _DOCDICER_TOOLS / "docdicer").exists()
    assert marker.is_file()
    assert runner.scripts == []


def test_the_install_verb_hands_the_tool_install_runner_to_the_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    runner = _ToolInstalls()
    monkeypatch.setattr("adjagent.cli.run_tool_install", runner)
    argv = ["install", str(project), "--harness=claude"]
    main(argv)
    tools = project / ".claude" / _DOCDICER_TOOLS
    _plant(tools / ".venv/marker")
    _plant(tools / "stale.txt")
    main(argv)
    assert runner.scripts == [tools / "docdicer"]


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A consumer's ROOT, the claude plugin, installed with kb included: the whole product plus the
    kb-tools package."""
    project = tmp_path_factory.mktemp("consumer")
    root = project / ".claude"
    root.mkdir()
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("HOME", str(project / "home"))
        install(
            root,
            _CLAUDE_RENDER,
            verbose=False,
            with_kb=True,
            project_root=project,
            uncommitted=_committed,
            tool_install=_ToolInstalls(),
        )
    return _claude_plugin(root)


def test_install_writes_every_render_and_stamps_the_packages_once(installed: Path) -> None:
    assert all((installed / path).is_file() for path, _ in render_all(_CLAUDE_RENDER))
    kb_mk = (installed / "skills/kbase/kb-tools/runner-snippets/kb.mk").read_text(encoding="utf-8").split("\n")
    source_mk = (PACKAGE_ROOT / "kb-tools/runner-snippets/kb.mk").read_text(encoding="utf-8").split("\n")
    assert kb_mk[0].startswith("# !INSTALLED! from adjagent/kb-tools/runner-snippets/kb.mk — ")
    assert kb_mk[1:] == source_mk


def test_reinstall_prunes_only_our_stale_definitions(tmp_path: Path, capsys) -> None:
    install(tmp_path, _CLAUDE_RENDER, verbose=False, uncommitted=_committed, tool_install=_ToolInstalls())
    planted = {
        "agents/kb-maintainer.md": _NEW_BANNER,
        "agents/gone/old.md": _NEW_BANNER,
        "agents/gone-too/deeper/old.md": _OLD_BANNER,
        "agents/mine.md": "---\nname: mine\n---\n",
        "agents/x.md.00.bak": _OLD_BANNER,
    }
    for relative, text in planted.items():
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text(text, encoding="utf-8")
    capsys.readouterr()
    install(tmp_path, _CLAUDE_RENDER, verbose=False, uncommitted=_committed, tool_install=_ToolInstalls())
    left = {relative for relative in planted if (tmp_path / relative).exists()}
    assert left == {"agents/mine.md", "agents/x.md.00.bak"}
    assert not (tmp_path / "agents/gone").exists() and not (tmp_path / "agents/gone-too").exists()
    pruned = {line for line in capsys.readouterr().out.splitlines() if line.startswith("pruned ")}
    assert pruned == {
        f"pruned {tmp_path / 'agents/gone-too/deeper/old.md'}",
        f"pruned {tmp_path / 'agents/gone/old.md'}",
        f"pruned {tmp_path / 'agents/kb-maintainer.md'}",
    }


# The overwrite refusal: an install writes over a file at a render or resource target only when that
# file carries this repository's banner for its kind, and otherwise refuses before the first write.

# A resource header as a file of the harness's own carries it, in a syntax the predicate does not parse.
_RESOURCE_HEADER = "// !INSTALLED! from elsewhere — request changes from the adjagent project\n"


def _rendered(ctx: Render, relative: str) -> str:
    """The text the renderer writes at `relative`, so a planted file that must pass is rendered output."""
    return dict(render_all(ctx))[PurePosixPath(relative)]


def test_a_hand_written_file_at_a_render_target_is_refused_with_nothing_written(tmp_path: Path) -> None:
    root = tmp_path / ".claude"
    mine = _claude_plugin(root) / "agents/python-coder.md"
    mine.parent.mkdir(parents=True)
    mine.write_text("---\nname: python-coder\n---\n\nmy own agent\n", encoding="utf-8")
    before = _files(tmp_path)
    with pytest.raises(InputError, match=re.escape(f"'{mine}'")):
        _definition_install(root, project_root=tmp_path)
    assert _files(tmp_path) == before


def _symlink_to_rendered_output(target: Path) -> None:
    """A symlink whose referent carries the banner: the link itself is what fails."""
    referent = target.parent.parent / "referent.md"
    referent.write_text(_rendered(_CLAUDE_RENDER, "agents/python-coder.md"), encoding="utf-8")
    target.symlink_to(referent)


def _directory(target: Path) -> None:
    target.mkdir()
    (target / "inside.md").write_text("mine\n", encoding="utf-8")


@pytest.mark.parametrize("plant", [_symlink_to_rendered_output, _directory], ids=["symlink", "directory"])
def test_a_symlink_or_directory_at_a_render_target_is_refused_with_nothing_written(tmp_path: Path, plant) -> None:
    root = tmp_path / ".claude"
    target = _claude_plugin(root) / "agents/python-coder.md"
    target.parent.mkdir(parents=True)
    plant(target)
    before = _files(tmp_path)
    with pytest.raises(InputError, match=re.escape(f"'{target}'")):
        _definition_install(root, project_root=tmp_path)
    assert _files(tmp_path) == before


def test_every_failing_target_is_named_in_one_refusal(tmp_path: Path) -> None:
    """Render and resource targets are collected together, so the operator clears them in one pass."""
    root = tmp_path / ".opencode"
    first, second = (root.joinpath(*relative.parts) for relative, _ in render_all(_OPENCODE_RENDER)[:2])
    plugin = root / _PLUGIN
    for path in (first, second, plugin):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("mine\n", encoding="utf-8")
    before = _files(tmp_path)
    with pytest.raises(InputError) as refusal:
        _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
    assert all(f"'{path}'" in str(refusal.value) for path in (first, second, plugin))
    assert _files(tmp_path) == before


def test_a_reinstall_overwrites_its_own_renders_kb_skill_files_included(tmp_path: Path) -> None:
    """A local edit that keeps the banner is still ours: the frontmatter carrier and a supporting
    file's comment carrier each pass, and the render replaces the edit."""
    root = tmp_path / ".claude"
    root.mkdir()
    _definition_install(root, with_kb=True, project_root=tmp_path)
    plugin = _claude_plugin(root)
    edited = ("agents/python-coder.md", "skills/kbase/references/reading.md")
    for relative in edited:
        with (plugin / relative).open("a", encoding="utf-8") as handle:
            handle.write("a local edit\n")
    _definition_install(root, with_kb=True, project_root=tmp_path)
    for relative in edited:
        assert (plugin / relative).read_text(encoding="utf-8") == _rendered(_CLAUDE_RENDER, relative)


@pytest.mark.parametrize(
    "head, refused",
    [
        ("", True),
        ("// filler\n" * 9 + _RESOURCE_HEADER, False),
        ("// filler\n" * 10 + _RESOURCE_HEADER, True),
    ],
    ids=["no-header", "header-on-line-10", "header-on-line-11"],
)
def test_a_resource_target_passes_only_with_the_header_in_its_first_ten_lines(
    tmp_path: Path, head: str, refused: bool
) -> None:
    root = tmp_path / ".opencode"
    plugin = root / _PLUGIN
    plugin.parent.mkdir(parents=True)
    plugin.write_text(f"{head}export const mine = 1\n", encoding="utf-8")
    source = (PACKAGE_ROOT / HARNESS_RESOURCES_SOURCE / "opencode" / _PLUGIN).read_bytes()
    before = _files(tmp_path)
    if refused:
        with pytest.raises(InputError, match=re.escape(f"'{plugin}'")):
            _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
        assert _files(tmp_path) == before
    else:
        _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
        assert plugin.read_bytes() == source


def test_a_prior_installs_resource_is_overwritten(tmp_path: Path) -> None:
    root = tmp_path / ".opencode"
    root.mkdir()
    _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
    plugin = root / _PLUGIN
    with plugin.open("a", encoding="utf-8") as handle:
        handle.write("// a local edit\n")
    _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
    assert plugin.read_bytes() == (PACKAGE_ROOT / HARNESS_RESOURCES_SOURCE / "opencode" / _PLUGIN).read_bytes()


def test_every_shipped_resource_carries_the_header_its_reinstall_needs(tmp_path: Path) -> None:
    """A resource without the header would refuse its own second install."""
    harnesses = load("adjagent.harnesses", "HARNESS")
    sources = [source for name in harnesses for source, _ in harness_resource_copies(tmp_path, harness=name)]
    assert sources
    assert [source for source in sources if not _is_our_resource(source)] == []


@pytest.mark.parametrize(
    "settings, message",
    [
        (b"\xff\xfe{}\n", "is not readable UTF-8 text"),
        (b'{"mcpServers": ["other"]}\n', "holds a 'mcpServers' that is not an object"),
        (b'{"mcpServers": null}\n', "holds a 'mcpServers' that is not an object"),
    ],
    ids=["non-utf8", "non-object-container", "null-container"],
)
def test_mcp_settings_the_merge_cannot_use_are_refused_before_the_first_write(
    tmp_path: Path, settings: bytes, message: str
) -> None:
    root = tmp_path / ".claude"
    _claude_mcp_file(root).write_bytes(settings)
    before = _files(tmp_path)
    with pytest.raises(InputError, match=re.escape(message)):
        _definition_install(root, with_kb=True, project_root=tmp_path)
    assert _files(tmp_path) == before


# The claude guardrail hook: shipped and registered in the plugin's own `hooks/hooks.json` when one run
# of the script on this machine succeeds, and the entry an earlier install registered in the project's
# `.claude/settings.json` then removed, every other byte of that file kept.

# A hook the project registered itself, which no install may touch.
_SED_HOOK = '{"matcher": "Bash", "hooks": [{"type": "command", "command": "./block-sed.sh"}]}'
_REMOVE_BY_HAND = "left untouched; remove this entry by hand:"
_UNREAD = "left untouched; it names an earlier install's 'hooks.PreToolUse' element: remove that by hand"


def _unparsed_settings(hook: dict) -> str:
    """A settings file Claude Code would not read as strict JSON, holding `hook`."""
    return f'{{\n  // mine\n  "hooks": {{"PreToolUse": [{json.dumps(hook)}]}}\n}}\n'


def _claude_root(project: Path, settings: str | bytes | None = None) -> Path:
    """`project/.claude`, created, with `settings` planted as its settings file where given."""
    root = project / ".claude"
    root.mkdir()
    if settings is not None:
        data = settings if isinstance(settings, bytes) else settings.encode("utf-8")
        (project / _SETTINGS).write_bytes(data)
    return root


def test_an_earlier_entry_after_the_projects_own_hook_is_removed_and_every_other_byte_kept(tmp_path: Path) -> None:
    """The earlier entry goes with the separator before it; every other byte — other keys, the
    project's hook, CRLF endings — is kept."""
    head = f'{{\r\n  "permissions": {{"allow": ["Bash"]}},\r\n  "hooks": {{\r\n    "PreToolUse": [\r\n      {_SED_HOOK}'
    earlier = f",\r\n      {json.dumps(_retired_hook_entry('.claude'))}"
    tail = '\r\n    ]\r\n  },\r\n  "model": "opus"\r\n}\r\n'
    root = _claude_root(tmp_path, head + earlier + tail)
    _definition_install(root, project_root=tmp_path)
    assert (tmp_path / _SETTINGS).read_bytes() == (head + tail).encode()


@pytest.mark.parametrize(
    "earlier",
    [
        _retired_hook_entry(".claude"),
        _retired_hook_entry("a"),
        _retired_hook_entry(_CLAUDE_PLUGIN_RELPATH),
        _retired_hook_entry(".claude", matcher="Bash"),
    ],
    ids=["flat-layout", "another-subdir", "plugin-script", "bash-only"],
)
def test_an_earlier_entry_ahead_of_the_projects_own_hook_is_removed_and_a_second_install_changes_no_byte(
    tmp_path: Path, capsys, earlier: dict
) -> None:
    """Whatever harness directory or matcher an earlier install wrote, its entry is ours: one guardrail
    per project. It goes with the separator after it, and the next install finds nothing to change."""
    head = '{\n  "hooks": {\n    "PreToolUse": [\n      '
    tail = f"{_SED_HOOK}\n    ]\n  }}\n}}\n"
    root = _claude_root(tmp_path, f"{head}{json.dumps(earlier)},\n      {tail}")
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    settings = tmp_path / _SETTINGS
    assert settings.read_text(encoding="utf-8") == head + tail
    assert _REMOVE_BY_HAND not in capsys.readouterr().err
    _definition_install(root, project_root=tmp_path)
    assert settings.read_text(encoding="utf-8") == head + tail


def test_an_earlier_entry_alone_in_its_array_leaves_the_array_empty_in_place(tmp_path: Path) -> None:
    seed = json.dumps({"hooks": {"PreToolUse": [_retired_hook_entry(".claude")]}}, indent=2) + "\n"
    root = _claude_root(tmp_path, seed)
    _definition_install(root, project_root=tmp_path)
    assert (tmp_path / _SETTINGS).read_text(encoding="utf-8") == '{\n  "hooks": {\n    "PreToolUse": []\n  }\n}\n'


@pytest.mark.parametrize(
    "pre_tool_use",
    [
        [_retired_hook_entry("a"), _retired_hook_entry(".claude")],
        [{"matcher": "Bash", "hooks": [*_retired_hook_entry(".claude")["hooks"], *json.loads(_SED_HOOK)["hooks"]]}],
    ],
    ids=["two-entries", "beside-the-projects-own"],
)
def test_settings_naming_our_command_ambiguously_are_reported_and_left_untouched(
    tmp_path: Path, capsys, pre_tool_use: list
) -> None:
    """Removing one of two entries leaves the other, and removing an entry that also runs the project's
    hook deletes it, so the operator removes by hand, shown each entry."""
    seed = json.dumps({"hooks": {"PreToolUse": pre_tool_use}}, indent=2) + "\n"
    root = _claude_root(tmp_path, seed)
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    assert (tmp_path / _SETTINGS).read_text(encoding="utf-8") == seed
    err = capsys.readouterr().err
    assert _REMOVE_BY_HAND in err and all(json.dumps(element) in err for element in pre_tool_use)


# How each settings file the removal cannot edit holds a PreToolUse element: strict JSON or not, decodable
# or not, the container wrong-typed, or reached through a symlink.
_UNEDITABLE_SETTINGS = {
    "unparsed": lambda hook: _unparsed_settings(hook).encode(),
    "non-utf8": lambda hook: b"\xff\xfe" + json.dumps({"hooks": {"PreToolUse": [hook]}}).encode() + b"\n",
    "non-object-hooks": lambda hook: json.dumps({"hooks": [hook]}).encode() + b"\n",
    "symlink": lambda hook: json.dumps({"hooks": {"PreToolUse": [hook]}}).encode() + b"\n",
}


@pytest.mark.parametrize("names_ours", [True, False], ids=["names-our-command", "names-none"])
@pytest.mark.parametrize("kind", list(_UNEDITABLE_SETTINGS))
def test_settings_the_removal_cannot_edit_are_never_refused_and_reported_only_where_they_name_our_command(
    tmp_path: Path, capsys, names_ours: bool, kind: str
) -> None:
    """The install completes and the file is not edited. Only a file whose text holds the command an
    earlier install wrote may strand that entry, so only it is reported; a symlink is read through."""
    project, outside = tmp_path / "project", tmp_path / "outside"
    outside.mkdir()
    project.mkdir()
    seed = _UNEDITABLE_SETTINGS[kind](_retired_hook_entry(".claude") if names_ours else json.loads(_SED_HOOK))
    if kind == "symlink":
        settings = outside / "settings.json"
        settings.write_bytes(seed)
        root = _claude_root(project)
        (project / _SETTINGS).symlink_to(settings)
        reason = f"{project / _SETTINGS} is a symlink"
    else:
        root = _claude_root(project, seed)
        settings = project / _SETTINGS
        reason = f"{settings} is not a JSON object the removal can edit"
    capsys.readouterr()
    _definition_install(root, project_root=project)
    assert (_claude_plugin(root) / _REGISTRATION).is_file()
    assert settings.read_bytes() == seed
    reported = [line for line in capsys.readouterr().err.splitlines() if _UNREAD in line]
    assert [reason in line for line in reported] == ([True] if names_ours else [])


@pytest.mark.parametrize(
    "interpreter, reason",
    [("adjagent-no-such-perl", "'adjagent-no-such-perl' could not be run: "), ("false", "'false ")],
    ids=["missing-interpreter", "failing-run"],
)
def test_a_failed_probe_installs_everything_else_and_neither_ships_nor_registers_the_hook(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch, interpreter: str, reason: str
) -> None:
    monkeypatch.setattr("adjagent.install.GUARDRAIL_INTERPRETER", interpreter)
    root = _claude_root(tmp_path)
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    assert (_claude_plugin(root) / "agents/python-coder.md").is_file()
    assert not (_claude_plugin(root) / _GUARDRAIL).exists()
    assert not (_claude_plugin(root) / _REGISTRATION).exists()
    assert not (tmp_path / _SETTINGS).exists()
    [skipped] = [line for line in capsys.readouterr().err.splitlines() if line.startswith("guardrail hook skipped")]
    assert reason in skipped and "left in place" not in skipped


def test_a_failed_probe_leaves_every_earlier_script_and_registration_and_names_them(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing replaces them, so the plugin's script and registration, the flat layout's script and the
    settings entry an earlier install wrote all stay, each named."""
    root = _claude_root(tmp_path)
    _definition_install(root, project_root=tmp_path)
    flat = _plant(root / _GUARDRAIL, (_claude_plugin(root) / _GUARDRAIL).read_text(encoding="utf-8"))
    seed = json.dumps({"hooks": {"PreToolUse": [_retired_hook_entry(".claude")]}}) + "\n"
    (tmp_path / _SETTINGS).write_text(seed, encoding="utf-8")
    before = _files(tmp_path)
    monkeypatch.setattr("adjagent.install.GUARDRAIL_INTERPRETER", "adjagent-no-such-perl")
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    after = _files(tmp_path)
    left = [_claude_plugin(root) / _GUARDRAIL, flat, _claude_plugin(root) / _REGISTRATION, tmp_path / _SETTINGS]
    for path in left:
        relative = path.relative_to(tmp_path).as_posix()
        assert after[relative] == before[relative]
    named = ", ".join(str(path) for path in left)
    assert f"left in place from an earlier install: {named}" in capsys.readouterr().err


def test_an_opencode_install_writes_no_claude_settings_file(tmp_path: Path) -> None:
    root = tmp_path / ".opencode"
    root.mkdir()
    _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
    assert not (tmp_path / ".claude").exists()
    assert not (root / _GUARDRAIL).exists()


@pytest.mark.parametrize("subdir", ["tools/agents", ".", 'a"b $c'], ids=["subdir", "project-root", "shell-syntax"])
def test_the_registered_command_runs_the_script_the_install_wrote(tmp_path: Path, subdir: str) -> None:
    """The command the plugin registers, run as Claude Code runs it, reaches the script under ROOT
    wherever ROOT sits, a directory name a shell reads as syntax included: it blocks an in-place edit and
    allows a plain command."""
    root = tmp_path / subdir
    root.mkdir(parents=True, exist_ok=True)
    _definition_install(root, project_root=tmp_path)
    assert (_claude_plugin(root) / _GUARDRAIL).is_file()
    assert _run_registered_hook(_claude_plugin(root), project=tmp_path, command="sed -i x f").returncode == 2
    assert _run_registered_hook(_claude_plugin(root), project=tmp_path, command="echo hi").returncode == 0


def test_a_missing_script_does_not_block_and_names_the_path(tmp_path: Path) -> None:
    """Perl exits 2 on a script it cannot open, which Claude Code reads as a block, so a plugin left
    without its script would block every call the matcher names. The registered command instead exits 1
    and names the missing script."""
    root = _claude_root(tmp_path)
    _definition_install(root, project_root=tmp_path)
    script = _claude_plugin(root) / _GUARDRAIL
    script.unlink()
    result = _run_registered_hook(_claude_plugin(root), project=tmp_path, command="sed -i x f")
    assert result.returncode == 1
    assert result.stderr.count("\n") == 1 and str(script) in result.stderr


def _run_registered_hook(plugin: Path, *, project: Path, command: str) -> subprocess.CompletedProcess:
    """The one command `plugin`'s registration names, run under `sh -c` with `CLAUDE_PLUGIN_ROOT` and
    `CLAUDE_PROJECT_DIR` set and a Bash payload for `command` on stdin."""
    registration = json.loads((plugin / _REGISTRATION).read_text(encoding="utf-8"))
    [[hook]] = [element["hooks"] for element in registration["hooks"]["PreToolUse"]]
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(project)}
    return subprocess.run(
        ["sh", "-c", hook["command"]],
        input=json.dumps(payload),
        capture_output=True,
        encoding="utf-8",
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(plugin), "CLAUDE_PROJECT_DIR": str(project)},
        check=False,
    )


# A project's own hook running a script of the same name, spelled as the project would write it.
_PROJECT_GUARDRAIL = {
    "matcher": "Bash",
    "hooks": [{"type": "command", "command": 'perl "$CLAUDE_PROJECT_DIR/tools/hooks/guardrail.pl"'}],
}


def test_a_projects_own_hook_running_a_guardrail_pl_is_kept_byte_for_byte(tmp_path: Path) -> None:
    """Only the command an earlier install wrote is ours: a project hook naming a `hooks/guardrail.pl` of
    its own is the project's, and removing it would delete it."""
    seed = json.dumps({"hooks": {"PreToolUse": [_PROJECT_GUARDRAIL]}}, indent=2) + "\n"
    root = _claude_root(tmp_path, seed)
    _definition_install(root, project_root=tmp_path)
    assert (tmp_path / _SETTINGS).read_text(encoding="utf-8") == seed


def test_a_flat_layout_script_without_the_installed_header_is_kept(tmp_path: Path) -> None:
    root = _claude_root(tmp_path)
    mine = _plant(root / _GUARDRAIL, "print 'mine';\n")
    _definition_install(root, project_root=tmp_path)
    assert mine.read_text(encoding="utf-8") == "print 'mine';\n"


def test_a_failed_probe_names_neither_a_script_nor_an_entry_an_install_did_not_write(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _claude_root(tmp_path, json.dumps({"hooks": {"PreToolUse": [_PROJECT_GUARDRAIL]}}) + "\n")
    _plant(_claude_plugin(root) / _GUARDRAIL, "print 'mine';\n")
    monkeypatch.setattr("adjagent.install.GUARDRAIL_INTERPRETER", "adjagent-no-such-perl")
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    [skipped] = [line for line in capsys.readouterr().err.splitlines() if line.startswith("guardrail hook skipped")]
    assert "left in place" not in skipped


def test_a_probe_that_hangs_fails_within_its_timeout(tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    slow = tmp_path / "slow-perl"
    slow.write_text("#!/bin/sh\nexec sleep 30\n", encoding="utf-8")
    slow.chmod(0o755)
    monkeypatch.setattr("adjagent.install.GUARDRAIL_INTERPRETER", str(slow))
    monkeypatch.setattr("adjagent.install.GUARDRAIL_PROBE_SECONDS", 0.5)
    project = tmp_path / "project"
    project.mkdir()
    root = _claude_root(project)
    capsys.readouterr()
    _definition_install(root, project_root=project)
    assert not (project / _SETTINGS).exists()
    [skipped] = [line for line in capsys.readouterr().err.splitlines() if line.startswith("guardrail hook skipped")]
    assert "did not exit within 0.5 seconds" in skipped


def _plant_file(path: Path, outside: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("mine\n", encoding="utf-8")


def _plant_directory(path: Path, outside: Path) -> None:
    path.mkdir(parents=True)
    (path / "inside.json").write_text("{}\n", encoding="utf-8")


def _plant_link(path: Path, outside: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(outside / "shared.json")


def _plant_dangling_link(path: Path, outside: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(outside / "missing.json")


def _plant_directory_link(path: Path, outside: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(outside, target_is_directory=True)


def _standing(path: Path) -> object:
    """What stands at `path`, compared without following it: a link's target text, a directory's files,
    a file's bytes."""
    if path.is_symlink():
        return str(path.readlink())
    return _files(path) if path.is_dir() else path.read_bytes()


@pytest.mark.parametrize(
    "planted, plant",
    [(f"{_CLAUDE_PLUGIN_RELPATH}/agents", _plant_file), (f"{_CLAUDE_PLUGIN_RELPATH}/hooks", _plant_directory_link)],
    ids=["file-on-a-render-path", "symlink-on-a-resource-path"],
)
def test_a_symlink_or_file_on_a_targets_path_is_refused_with_nothing_written(
    tmp_path: Path, planted: str, plant
) -> None:
    project, outside = tmp_path / "project", tmp_path / "outside"
    outside.mkdir()
    project.mkdir()
    root = _claude_root(project)
    plant(project / planted, outside)
    before = _files(tmp_path)
    with pytest.raises(InputError, match=re.escape(f"'{project / planted}'")):
        _definition_install(root, project_root=project)
    assert _files(tmp_path) == before


@pytest.mark.parametrize(
    "ctx, kb, subdir, planted, plant, reason",
    [
        (
            _CLAUDE_RENDER,
            True,
            ".claude",
            f"{_CLAUDE_PLUGIN_RELPATH}/.mcp.json",
            _plant_directory,
            "is not a regular file",
        ),
        (_CLAUDE_RENDER, True, ".claude", f"{_CLAUDE_PLUGIN_RELPATH}/.mcp.json", _plant_link, "is a symlink"),
        (_CLAUDE_RENDER, True, ".claude", f"{_CLAUDE_PLUGIN_RELPATH}/.mcp.json", _plant_dangling_link, "is a symlink"),
        (_OPENCODE_RENDER, True, "tools", ".opencode", _plant_file, "is not a directory"),
    ],
    ids=[
        "mcp-directory",
        "mcp-symlink",
        "mcp-dangling-symlink",
        "mcp-parent-file",
    ],
)
def test_a_settings_path_a_merge_cannot_write_in_place_is_reported_and_left_standing(
    tmp_path: Path, capsys, ctx: Render, kb: bool, subdir: str, planted: str, plant, reason: str
) -> None:
    """The install completes; the merge writes nothing there or through it — a symlink's target,
    dangling or not, outside the project included — and names the path with the entry to merge by
    hand."""
    project, outside = tmp_path / "project", tmp_path / "outside"
    outside.mkdir()
    (outside / "shared.json").write_text('{"shared": true}\n', encoding="utf-8")
    root = project / subdir
    root.mkdir(parents=True)
    plant(project / planted, outside)
    before = (_standing(project / planted), _files(outside))
    capsys.readouterr()
    _definition_install(root, ctx, with_kb=kb if kb else None, project_root=project)
    assert (_standing(project / planted), _files(outside)) == before
    err = capsys.readouterr().err
    assert any(f"{project / planted} {reason}" in line and "left untouched; " in line for line in err.splitlines())


# The preflight: `install` and `install-agents-file` first run into a scratch copy of the paths they
# manage and compare it with the target, so an up-to-date target is left untouched and `--dry-run`
# prints the difference without writing.

_UP_TO_DATE = "up to date: "


def _state(base: Path) -> dict[str, tuple[bytes, int, int]]:
    """Every directory, file and symlink below `base`, symlinks not followed: its bytes (a symlink's
    target text, a directory's none), modification time and mode — what "touched nothing" compares."""
    state = {}
    for directory, subdirs, names in os.walk(base):
        for name in [*subdirs, *names]:
            path = Path(directory, name)
            info = path.lstat()
            if path.is_symlink():
                data = str(path.readlink()).encode()
            elif path.is_file():
                data = path.read_bytes()
            else:
                data = b""
            state[path.relative_to(base).as_posix()] = (data, info.st_mtime_ns, info.st_mode)
    return state


def _dry_run_groups(out: str) -> dict[str, set[str]]:
    """The paths a dry run printed under each of its `created`, `changed` and `removed` headings."""
    groups: dict[str, set[str]] = {}
    current: set[str] | None = None
    for line in out.splitlines():
        if line in ("created:", "changed:", "removed:"):
            current = groups.setdefault(line[:-1], set())
        elif line.startswith("  ") and current is not None:
            current.add(line.strip())
        else:
            current = None
    return groups


@pytest.fixture
def _no_uncommitted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI's commit-state check standing down, so an agents-file write does not turn on this tree."""
    monkeypatch.setattr("adjagent.cli.uncommitted_sources", _committed)


def _assert_dry_run_predicts(argv: list[str], *, project: Path, capsys) -> dict[str, set[str]]:
    """Run `argv` with `--dry-run`, then for real: the dry run touches nothing under `project`, and the
    paths it prints are exactly those the real run then creates, changes and removes. Its groups."""
    files, state = _files(project), _state(project)
    capsys.readouterr()
    main([*argv, "--dry-run"])
    groups = _dry_run_groups(capsys.readouterr().out)
    assert _state(project) == state
    main(argv)
    after = _files(project)
    actual = {
        "created": set(after) - set(files),
        "changed": {path for path in set(after) & set(files) if after[path] != files[path]},
        "removed": set(files) - set(after),
    }
    assert groups == {group: paths for group, paths in actual.items() if paths}
    return groups


def _kb_install_with_a_runner_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], Path]:
    """The settings file and the runner include line are in play: each is already what the second run
    writes."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    return ["install", str(project), "--harness=claude", "--with-kb"], project


def _user_level_with_global_agents_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], Path]:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    return ["install", str(home), "--harness=claude", "--install-global-agents-file"], home


def _agents_file_in_a_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], Path]:
    """An agents file holding an earlier block, so the first run also writes the backup."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "AGENTS.md").write_text(f"mine\n{_BEGIN}\nold\n{_END}\n", encoding="utf-8")
    return ["install-agents-file", str(project), "--harness=claude"], project


def _the_repository_as_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], Path]:
    """The project is this repository, whose runner file no install writes: the copy must read that from
    the real project, not from its scratch one."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "justfile").write_text("# generator\n", encoding="utf-8")
    monkeypatch.setattr("adjagent.install.REPO_ROOT", project.resolve())
    return ["install", str(project), "--harness=claude", "--with-kb"], project


def _mage_below_its_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], Path]:
    """The plugin's own `.mcp.json` and agents file at ROOT."""
    project = tmp_path / "project"
    project.mkdir()
    return ["install", str(project), "--harness=mage", "--subdir=plugins/adjagent"], project


@pytest.mark.usefixtures("_no_uncommitted")
@pytest.mark.parametrize(
    "setup",
    [
        _kb_install_with_a_runner_file,
        _user_level_with_global_agents_file,
        _agents_file_in_a_project,
        _the_repository_as_project,
        _mage_below_its_project,
    ],
    ids=["kb-runner-file", "user-level-global-agents-file", "agents-file", "repository-project", "mage-subdir"],
)
def test_a_second_identical_run_whose_decisions_read_the_real_location_is_up_to_date(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch, setup
) -> None:
    """Nothing under the target changes, a modification time included."""
    argv, base = setup(tmp_path, monkeypatch)
    main(argv)
    state = _state(base)
    capsys.readouterr()
    main(argv)
    out = capsys.readouterr().out
    assert _UP_TO_DATE in out and "installed:" not in out
    assert _state(base) == state


def test_a_changed_kb_set_installs(tmp_path: Path, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    argv = ["install", str(project), "--harness=opencode", "--family=gemma-4"]
    main(argv)
    files = _files(project)
    capsys.readouterr()
    main([*argv, "--with-kb"])
    assert _UP_TO_DATE not in capsys.readouterr().out
    assert _files(project) != files


@pytest.mark.usefixtures("_no_uncommitted")
@pytest.mark.parametrize(
    "harness_args",
    [
        ["--harness=claude", "--with-kb"],
        ["--harness=opencode", "--with-kb"],
        ["--harness=mage", "--subdir=plugins/adjagent"],
    ],
    ids=["claude-kb", "opencode-kb", "mage-subdir"],
)
def test_a_dry_run_on_a_fresh_target_lists_as_created_what_the_install_creates(
    tmp_path: Path, capsys, harness_args: list[str]
) -> None:
    """The project's runner file is in play too: under a kb install it gains the include line, so it is
    listed as changed."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    groups = _assert_dry_run_predicts(["install", str(project), *harness_args], project=project, capsys=capsys)
    assert groups["created"]


@pytest.mark.usefixtures("_no_uncommitted")
def test_a_dry_run_on_a_user_directory_predicts_the_install(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The agents file holds an earlier block: only a copy that holds it too predicts that the file
    changes and its backup is created."""
    argv, home = _user_level_with_global_agents_file(tmp_path, monkeypatch)
    (home / ".claude/CLAUDE.md").write_text(f"mine\n{_BEGIN}\nold\n{_END}\n", encoding="utf-8")
    groups = _assert_dry_run_predicts(argv, project=home, capsys=capsys)
    assert ".claude/CLAUDE.md" in groups["changed"] and ".claude/backup.CLAUDE.md" in groups["created"]


def test_a_dry_run_after_a_family_change_lists_the_renders_as_changed(tmp_path: Path, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    argv = ["install", str(project), "--harness=opencode"]
    main([*argv, "--family=gemma-4"])
    groups = _assert_dry_run_predicts([*argv, "--family=qwen3"], project=project, capsys=capsys)
    assert groups["changed"] and set(groups) == {"changed"}


def test_a_dry_run_lists_a_legacy_tree_and_a_stale_render_as_removed(tmp_path: Path, capsys) -> None:
    project = tmp_path / "project"
    root = project / ".claude"
    root.mkdir(parents=True)
    argv = ["install", str(project), "--harness=claude"]
    main(argv)
    (root / "agents/kb_tools").mkdir(parents=True)
    (root / "agents/kb_tools/helper.py").write_text("x = 1\n", encoding="utf-8")
    (root / "agents/gone.md").write_text(_NEW_BANNER, encoding="utf-8")
    groups = _assert_dry_run_predicts(argv, project=project, capsys=capsys)
    assert groups == {"removed": {".claude/agents/kb_tools/helper.py", ".claude/agents/gone.md"}}


@pytest.mark.usefixtures("_no_uncommitted")
@pytest.mark.parametrize(
    "argv",
    [["install", "{project}", "--harness=claude"], ["install-agents-file", "{project}", "--harness=claude"]],
    ids=["install", "install-agents-file"],
)
def test_a_dry_run_on_an_up_to_date_target_says_so(tmp_path: Path, capsys, argv: list[str]) -> None:
    project = tmp_path / "project"
    project.mkdir()
    argv = [part.format(project=project) for part in argv]
    main(argv)
    state = _state(project)
    capsys.readouterr()
    main([*argv, "--dry-run"])
    out = capsys.readouterr().out
    assert _UP_TO_DATE in out and _dry_run_groups(out) == {}
    assert _state(project) == state


@pytest.mark.usefixtures("_no_uncommitted")
def test_an_agents_file_dry_run_names_the_files_and_writes_nothing(tmp_path: Path, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    groups = _assert_dry_run_predicts(
        ["install-agents-file", str(project), "--harness=claude"], project=project, capsys=capsys
    )
    assert groups == {"created": {"AGENTS.md", "CLAUDE.md"}}


def test_no_printed_path_or_refusal_names_the_scratch_copy(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refusal the copy run raises names the real file; the scratch copy is gone afterwards."""
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setattr("tempfile.tempdir", str(scratch))
    project = tmp_path / "project"
    root = project / ".claude"
    root.mkdir(parents=True)
    argv = ["install", str(project), "--harness=claude", "--dry-run"]
    main(argv)
    printed = capsys.readouterr().out
    mine = _plant(_claude_plugin(root) / "agents/python-coder.md", "mine\n")
    with pytest.raises(SystemExit) as exit_info:
        main(argv)
    assert exit_info.value.code == 2
    refusal = capsys.readouterr().err
    assert f"'{mine}'" in refusal
    assert str(scratch) not in printed + refusal
    assert list(scratch.iterdir()) == []


def test_a_dry_run_through_a_symlinked_skill_directory_writes_nowhere(tmp_path: Path, capsys) -> None:
    """The copy dereferences the link, so the kbase skill the run into it writes there cannot land in
    the link's destination."""
    project, outside = tmp_path / "project", tmp_path / "outside"
    outside.mkdir()
    (outside / "notes.txt").write_text("mine\n", encoding="utf-8")
    skills = _claude_plugin(project / ".claude") / "skills"
    skills.mkdir(parents=True)
    (skills / "kbase").symlink_to(outside.resolve(), target_is_directory=True)
    before = (_state(project), _state(outside))
    capsys.readouterr()
    main(["install", str(project), "--harness=claude", "--with-kb", "--dry-run"])
    created = _dry_run_groups(capsys.readouterr().out)["created"]
    assert f"{_CLAUDE_PLUGIN_RELPATH}/skills/kbase/SKILL.md" in created
    assert (_state(project), _state(outside)) == before


@pytest.mark.parametrize("dry_run", [[], ["--dry-run"]], ids=["install", "dry-run"])
def test_a_settings_file_left_alone_is_reported_on_an_up_to_date_target(
    tmp_path: Path, capsys, dry_run: list[str]
) -> None:
    """What to remove by hand is printed on every run that leaves the file alone, not only the one that
    first wrote the rest."""
    project = tmp_path / "project"
    project.mkdir()
    _claude_root(project, _unparsed_settings(_retired_hook_entry(".claude")))
    argv = ["install", str(project), "--harness=claude"]
    main(argv)
    capsys.readouterr()
    main([*argv, *dry_run])
    printed = capsys.readouterr()
    assert _UP_TO_DATE in printed.out
    assert f"{project / _SETTINGS} is not a JSON object the removal can edit — {_UNREAD}" in printed.err


@pytest.mark.parametrize("linked", ["{}\n", None], ids=["link-outside-the-project", "dangling-link"])
def test_a_symlinked_settings_file_the_install_leaves_alone_is_up_to_date(
    tmp_path: Path, capsys, linked: str | None
) -> None:
    """The copy keeps the link a link, so the run into it leaves the file alone as the real install does."""
    project, outside = tmp_path / "project", tmp_path / "outside"
    outside.mkdir()
    project.mkdir()
    if linked is not None:
        (outside / "settings.json").write_text(linked, encoding="utf-8")
    _claude_root(project)
    (project / _SETTINGS).symlink_to(outside / "settings.json")
    argv = ["install", str(project), "--harness=claude"]
    main(argv)
    capsys.readouterr()
    main(argv)
    assert _UP_TO_DATE in capsys.readouterr().out
    main([*argv, "--dry-run"])
    assert _dry_run_groups(capsys.readouterr().out) == {}


# The claude plugin: an install over the layout that wrote the set straight into the harness directory
# leaves none of that layout's generated files or package destinations, and a user-level plugin
# shadowing a project's is reported.

# The layout an earlier release wrote: the set straight into `.claude/`, its guardrail script beside it,
# the MCP entry in the project's own `.mcp.json`, no manifest, and every reference bare. Its guardrail
# entry in the project's settings file is planted as that release wrote it.
_FLAT_CLAUDE_RENDER = Render(
    harness=dataclasses.replace(
        CLAUDE,
        plugin_dir="",
        reference_prefix="",
        mcp=dataclasses.replace(CLAUDE.mcp, site=McpSite.PROJECT),
        rendered_files=(),
        guardrail=None,
        retired_entries=(),
    ),
    family=CLAUDE_FAMILY,
    tier_map=dict(CLAUDE_FAMILY.tiers),
)
_FLAT_SETTINGS_HEAD = f'{{\n  "hooks": {{\n    "PreToolUse": [\n      {_SED_HOOK}'
_FLAT_SETTINGS_TAIL = "\n    ]\n  }\n}\n"


def _flat_claude_project(tmp_path: Path) -> tuple[Path, Path]:
    """A project holding a kb install in the flat layout, with a runner file and the guardrail entry
    beside the project's own hook: the project and its `.claude/`."""
    project, root = _claude_project(tmp_path)
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    _definition_install(root, _FLAT_CLAUDE_RENDER, with_kb=True, project_root=project)
    earlier = f",\n      {json.dumps(_retired_hook_entry('.claude'))}"
    (project / _SETTINGS).write_text(_FLAT_SETTINGS_HEAD + earlier + _FLAT_SETTINGS_TAIL, encoding="utf-8")
    return project, root


def test_an_install_over_the_flat_layout_leaves_none_of_its_generated_files_package_destinations_or_entries(
    tmp_path: Path, capsys
) -> None:
    """Below the harness directory only the plugin, the project's own files and settings file remain,
    every retired package destination is named as removed, the include line names the plugin's snippets,
    and the earlier guardrail and kbase entries are gone from the project's settings files with every
    other byte kept."""
    project, root = _flat_claude_project(tmp_path)
    assert (root / _GUARDRAIL).is_file()
    assert "kbase" in json.loads((project / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    mine = _plant(root / "skills/mine/SKILL.md", "---\nname: mine\n---\n\nmy own skill\n")
    capsys.readouterr()
    _definition_install(root, with_kb=True, project_root=project)
    out = capsys.readouterr().out
    outside_plugin = {relative for relative in _files(root) if not relative.startswith(f"{CLAUDE.plugin_dir}/")}
    assert outside_plugin == {"settings.json", "skills/mine/SKILL.md"}
    assert not (root / "hooks").exists()
    assert mine.read_text(encoding="utf-8") == "---\nname: mine\n---\n\nmy own skill\n"
    for destination in ("skills/docdicer/tools", "skills/kbase/kb-tools"):
        assert f"removed retired package destination {root / destination}" in out
    assert not (_claude_plugin(root) / "SKILL.md").exists()
    line = f"import? '{_CLAUDE_PLUGIN_RELPATH}/skills/kbase/kb-tools/runner-snippets/kb.just'"
    assert (project / "justfile").read_text(encoding="utf-8") == f"# mine\n\n{line}\n"
    assert (project / _SETTINGS).read_text(encoding="utf-8") == _FLAT_SETTINGS_HEAD + _FLAT_SETTINGS_TAIL
    assert (project / ".mcp.json").read_text(encoding="utf-8") == '{\n  "mcpServers": {}\n}\n'


@pytest.mark.parametrize(
    "kbase, removed",
    [
        ({"command": "kbase", "args": ["mcp"]}, True),
        ({"command": "/opt/kb/bin/kbase", "args": ["mcp", "--root", "/p"]}, True),
        ({"command": "node", "args": ["kbase"]}, False),
    ],
    ids=["bare-command", "path-to-kbase", "another-server"],
)
def test_only_a_kb_install_removes_an_earlier_kbase_entry_from_the_projects_mcp_file(
    tmp_path: Path, kbase: dict, removed: bool
) -> None:
    """The plugin's own entry replaces it, so only an install writing that removes it; the recogniser
    reads the command alone, and the project's other server stays byte for byte."""
    project, root = _claude_project(tmp_path)
    other = '"other": {"command": "x"}'
    seed = f'{{\n  "mcpServers": {{\n    {other},\n    "kbase": {json.dumps(kbase)}\n  }}\n}}\n'
    mcp_file = _plant(project / ".mcp.json", seed)
    _definition_install(root, project_root=project)
    assert mcp_file.read_text(encoding="utf-8") == seed
    _definition_install(root, with_kb=True, project_root=project)
    expected = f'{{\n  "mcpServers": {{\n    {other}\n  }}\n}}\n' if removed else seed
    assert mcp_file.read_text(encoding="utf-8") == expected


def test_a_dry_run_over_the_flat_layout_predicts_the_migration_and_a_second_run_is_up_to_date(
    tmp_path: Path, capsys
) -> None:
    project, _ = _flat_claude_project(tmp_path)
    argv = ["install", str(project), "--harness=claude", "--with-kb"]
    groups = _assert_dry_run_predicts(argv, project=project, capsys=capsys)
    assert ".claude/agents/python-coder.md" in groups["removed"]
    assert ".claude/skills/kbase/kb-tools/runner-snippets/kb.just" in groups["removed"]
    assert f".claude/{_GUARDRAIL}" in groups["removed"]
    assert {_SETTINGS, ".mcp.json"} <= groups["changed"]
    assert f"{_CLAUDE_PLUGIN_RELPATH}/agents/python-coder.md" in groups["created"]
    main(argv)
    assert _UP_TO_DATE in capsys.readouterr().out


def test_a_docdicer_venv_at_the_flat_destination_is_rebuilt_in_the_plugin(tmp_path: Path, capsys) -> None:
    project, root = _flat_claude_project(tmp_path)
    flat_venv = _plant(root / "skills/docdicer/tools/.venv/marker").parent
    runner = _ToolInstalls()
    _preflighted(root, project=project, tool_install=runner, dry_run=True)
    assert ".claude/skills/docdicer/tools/.venv" in capsys.readouterr().out
    _preflighted(root, project=project, tool_install=runner)
    assert not flat_venv.exists()
    assert runner.scripts == [root / _DOCDICER_TOOLS / "docdicer"]


def test_a_user_level_install_removes_no_package_destination(_home: Path) -> None:
    """A user-level install ships no package, so it writes no replacement and removes none."""
    root = _home / ".claude"
    planted = _plant(root / "skills/kbase/kb-tools/runner-snippets/kb.just")
    install(
        root, _CLAUDE_RENDER, verbose=False, project_root=_home, uncommitted=_committed, tool_install=_ToolInstalls()
    )
    assert planted.is_file()


def _user_level_plugin(home: Path) -> Path:
    """A user-level claude plugin installed under `home`: its manifest's path."""
    root = home / ".claude"
    root.mkdir(parents=True)
    install(
        root, _CLAUDE_RENDER, verbose=False, project_root=home, uncommitted=_committed, tool_install=_ToolInstalls()
    )
    return _claude_plugin(root) / ".claude-plugin/plugin.json"


def test_a_project_plugin_a_user_level_one_shadows_is_reported_on_every_run(
    tmp_path: Path, _home: Path, capsys
) -> None:
    """The report reads the real home, so an up-to-date run and a dry run make it too."""
    _user_level_plugin(_home)
    project = tmp_path / "project"
    project.mkdir()
    argv = ["install", str(project), "--harness=claude"]
    shadowed = f"{_claude_plugin(project / '.claude')} is shadowed by {_claude_plugin(_home / '.claude')}"
    for run in (argv, argv, [*argv, "--dry-run"]):
        capsys.readouterr()
        main(run)
        assert shadowed in capsys.readouterr().err


def test_no_shadow_is_reported_without_a_user_level_plugin(tmp_path: Path, _home: Path, capsys) -> None:
    """A user-level manifest that is not ours shadows nothing this install can name."""
    _plant(_home / ".claude" / CLAUDE.plugin_dir / ".claude-plugin/plugin.json", '{"name": "other"}\n')
    project = tmp_path / "project"
    project.mkdir()
    capsys.readouterr()
    main(["install", str(project), "--harness=claude"])
    assert "shadowed" not in capsys.readouterr().err


def test_a_user_level_plugin_reports_that_it_shadows_every_projects(_home: Path, capsys) -> None:
    capsys.readouterr()
    _user_level_plugin(_home)
    assert f"{_claude_plugin(_home / '.claude')} is user-level" in capsys.readouterr().err


@pytest.mark.parametrize("harness, printed", [("claude", True), ("opencode", False)], ids=["claude", "opencode"])
def test_the_reload_rule_is_printed_after_an_install_that_writes_and_not_when_up_to_date(
    tmp_path: Path, capsys, harness: str, printed: bool
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    argv = ["install", str(project), f"--harness={harness}"]
    capsys.readouterr()
    main(argv)
    assert (CLAUDE.reload_rule in capsys.readouterr().out) is printed
    main(argv)
    out = capsys.readouterr().out
    assert _UP_TO_DATE in out and CLAUDE.reload_rule not in out


# The agents file follows the set: a claude or opencode project install keeps the block current in the
# user-global agents file where that holds it, and otherwise in the project's AGENTS.md.

_HARNESS_NAMED = {"claude": CLAUDE, "opencode": OPENCODE}


def _global_agents_file(home: Path, harness: Harness) -> Path:
    return home / Path(harness.user_harness_dir).relative_to("~") / harness.agents_file


def _dirty() -> tuple[str, ...]:
    return ("M adjagent/x.py",)


@pytest.mark.parametrize("uncommitted", [False, True], ids=["committed", "uncommitted"])
@pytest.mark.parametrize("name, redirect", [("claude", True), ("opencode", False)], ids=["claude", "opencode"])
def test_without_a_global_block_a_project_install_keeps_it_in_the_projects_agents_md(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, redirect: bool, uncommitted: bool
) -> None:
    """The global file holds no block, so its text is not touched, and the commit state is not read."""
    monkeypatch.setattr("adjagent.cli.uncommitted_sources", _dirty if uncommitted else _committed)
    harness = _HARNESS_NAMED[name]
    _plant(_global_agents_file(tmp_path / "home", harness), "# my global rules\n")
    project = tmp_path / "project"
    project.mkdir()
    main(["install", str(project), f"--harness={name}"])
    rendered = render_agents_file(harness, scope=project.name).encode()
    top = {path: data for path, data in _files(project).items() if "/" not in path}
    assert top == {"AGENTS.md": rendered, **({"CLAUDE.md": b"@AGENTS.md\n"} if redirect else {})}
    assert _global_agents_file(tmp_path / "home", harness).read_text(encoding="utf-8") == "# my global rules\n"


def test_on_the_fallback_a_claude_redirect_is_left_and_the_block_appended(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _plant(project / "CLAUDE.md", "@AGENTS.md\n")
    _plant(project / "AGENTS.md", "# mine\n")
    main(["install", str(project), "--harness=claude"])
    assert (project / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"
    assert (project / "AGENTS.md").read_text(encoding="utf-8") == "\n".join(["# mine", "", *_block(CLAUDE), ""])


def test_on_the_fallback_a_claude_native_file_with_its_own_content_refuses_the_install(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "project"
    _plant(project / "CLAUDE.md", "# my own rules\n")
    before = _state(project)
    with pytest.raises(SystemExit):
        main(["install", str(project), "--harness=claude"])
    assert "CLAUDE.md holds its own content" in capsys.readouterr().err
    assert _state(project) == before


def _project_with_a_copy(tmp_path: Path, *, native: str | None, own: str) -> Path:
    """A project whose AGENTS.md holds `own` and then a stale block, and whose CLAUDE.md, where `native` is
    given, holds it."""
    project = tmp_path / "project"
    _plant(project / "AGENTS.md", f"{own}{_BEGIN}\nold\n{_END}\n")
    if native is not None:
        _plant(project / "CLAUDE.md", native)
    return project


@pytest.mark.usefixtures("_no_uncommitted")
@pytest.mark.parametrize("own", ["# mine\n\n", ""], ids=["own-text", "only-the-block"])
@pytest.mark.parametrize(
    "name, native",
    [("claude", "@AGENTS.md\n"), ("claude", "# my own rules\n"), ("opencode", None)],
    ids=["claude-redirect", "claude-own-content", "opencode"],
)
def test_with_a_global_block_the_install_keeps_it_there_and_removes_the_project_copy(
    tmp_path: Path, capsys, name: str, native: str | None, own: str
) -> None:
    """The project's AGENTS.md stays, emptied or not; its native file is neither read nor refused."""
    harness = _HARNESS_NAMED[name]
    global_file = _plant(_global_agents_file(tmp_path / "home", harness), f"# my global rules\n{_BEGIN}\nold\n{_END}\n")
    global_prior = global_file.read_text(encoding="utf-8")
    project = _project_with_a_copy(tmp_path, native=native, own=own)
    project_prior = (project / "AGENTS.md").read_text(encoding="utf-8")
    capsys.readouterr()
    main(["install", str(project), f"--harness={name}"])
    out = capsys.readouterr().out
    assert global_file.read_text(encoding="utf-8") == "\n".join(["# my global rules", *_block(harness), ""])
    assert (global_file.parent / f"backup.{global_file.name}").read_text(encoding="utf-8") == global_prior
    assert (project / "AGENTS.md").read_text(encoding="utf-8") == own
    assert (project / "backup.AGENTS.md").read_text(encoding="utf-8") == project_prior
    assert f"removed the adjagent block from {project / 'AGENTS.md'}" in out
    assert (None if native is None else (project / "CLAUDE.md").read_text(encoding="utf-8")) == native
    assert native is not None or not (project / "CLAUDE.md").exists()


@pytest.mark.usefixtures("_no_uncommitted")
def test_once_the_global_file_holds_the_block_every_project_install_keeps_it_there(
    tmp_path: Path, capsys
) -> None:
    """Sticky: a project with no agents file gets none, and a second install is up to date."""
    global_file = _plant(_global_agents_file(tmp_path / "home", CLAUDE), f"{_BEGIN}\nold\n{_END}\n")
    for project in (tmp_path / "one", tmp_path / "two"):
        project.mkdir()
        main(["install", str(project), "--harness=claude"])
        assert not (project / "AGENTS.md").exists() and not (project / "CLAUDE.md").exists()
        assert global_file.read_text(encoding="utf-8") == "\n".join([*_block(CLAUDE), ""])
        capsys.readouterr()
        main(["install", str(project), "--harness=claude"])
        assert _UP_TO_DATE in capsys.readouterr().out


def test_the_global_write_under_uncommitted_sources_is_refused_with_nothing_written(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("adjagent.cli.uncommitted_sources", _dirty)
    _plant(_global_agents_file(tmp_path / "home", CLAUDE), f"{_BEGIN}\nold\n{_END}\n")
    project = _project_with_a_copy(tmp_path, native="@AGENTS.md\n", own="# mine\n")
    before = {"home": _state(tmp_path / "home"), "project": _state(project)}
    with pytest.raises(SystemExit):
        main(["install", str(project), "--harness=claude"])
    assert "uncommitted changes" in capsys.readouterr().err
    assert {"home": _state(tmp_path / "home"), "project": _state(project)} == before


@pytest.mark.usefixtures("_no_uncommitted")
def test_a_dry_run_names_the_global_files_whole_and_the_projects_relative(tmp_path: Path, capsys) -> None:
    global_file = _plant(_global_agents_file(tmp_path / "home", CLAUDE), f"{_BEGIN}\nold\n{_END}\n")
    project = _project_with_a_copy(tmp_path, native=None, own="# mine\n")
    argv = ["install", str(project), "--harness=claude"]
    capsys.readouterr()
    main([*argv, "--dry-run"])
    groups = _dry_run_groups(capsys.readouterr().out)
    assert {str(global_file), "AGENTS.md"} <= groups["changed"]
    assert {str(global_file.parent / "backup.CLAUDE.md"), "backup.AGENTS.md"} <= groups["created"]
    assert not (global_file.parent / "backup.CLAUDE.md").exists() and not (project / "backup.AGENTS.md").exists()


# A symlink is the file it names: read and written through, the link kept.


@pytest.mark.usefixtures("_no_uncommitted")
def test_a_symlinked_global_agents_file_holding_the_block_is_updated_through_the_link(tmp_path: Path) -> None:
    dotfiles = _plant(tmp_path / "dotfiles" / "CLAUDE.md", f"# my global rules\n{_BEGIN}\nold\n{_END}\n")
    link = _global_agents_file(tmp_path / "home", CLAUDE)
    link.parent.mkdir(parents=True)
    link.symlink_to(dotfiles)
    project = tmp_path / "project"
    project.mkdir()
    main(["install", str(project), "--harness=claude"])
    assert link.is_symlink() and link.readlink() == dotfiles
    assert dotfiles.read_text(encoding="utf-8") == "\n".join(["# my global rules", *_block(CLAUDE), ""])
    assert not (project / "AGENTS.md").exists()


@pytest.mark.parametrize("dangling", [False, True], ids=["to-a-file", "dangling"])
def test_a_symlinked_project_agents_md_gets_the_block_through_the_link(tmp_path: Path, dangling: bool) -> None:
    """A dangling link reads as an absent file, and the write creates its target."""
    target = tmp_path / "shared" / "AGENTS.md"
    target.parent.mkdir()
    if not dangling:
        target.write_text("# mine\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    (project / "AGENTS.md").symlink_to(target)
    main(["install", str(project), "--harness=claude"])
    assert (project / "AGENTS.md").is_symlink() and (project / "AGENTS.md").readlink() == target
    expected = render_agents_file(CLAUDE, scope=project.name) if dangling else "\n".join(
        ["# mine", "", *_block(CLAUDE), ""]
    )
    assert target.read_text(encoding="utf-8") == expected
    assert (project / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"
