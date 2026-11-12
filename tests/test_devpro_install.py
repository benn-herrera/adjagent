"""The agents-file render and installer, and the definition install, each case checked against values
the code under test did not compute: the marker span, the bytes kept outside it, the refusals that
write nothing, the redirects, the kb-tools package and its banner, the docdicer tools package replaced
around its venv, the kb install path, the kbase
`.mcp.json`, the runner include line, the harness resources a harness ships as they stand, the
prune, the refusal to overwrite a file without this repository's banner, the claude guardrail hook's
probe and registration, the removal of entries earlier installs registered, and the checkout premise with the checks that stand down outside one.

The package is imported from the repository root, which `just test` puts on PYTHONPATH.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import subprocess
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import cast

import pytest

from devpro import __version__
from devpro.agents_file import install_agents_file, marker_span, scope_name
from devpro.cli import build_parser, main
from devpro.context import Render, build_render
from devpro.definition import Definition
from devpro.errors import InputError
from devpro.families.claude import FAMILY as CLAUDE_FAMILY
from devpro.harness import Harness
from devpro.harnesses.claude import HARNESS as CLAUDE
from devpro.harnesses.mage import HARNESS as MAGE
from devpro.harnesses.opencode import HARNESS as OPENCODE
from devpro.install import (
    HARNESS_RESOURCES_SOURCE,
    SHIPPED_PACKAGES,
    ShippedPackage,
    _is_our_resource,
    harness_resource_copies,
    install,
    preflighted_install,
    uncommitted_sources,
)
from devpro.install_base import PACKAGE_ROOT, REPO_ROOT, checkout_root
from devpro.loading import load
from devpro.plugin import Plugin
from devpro.plugins.devpro import PLUGIN as DEVPRO
from devpro.plugins.kbase import PLUGIN as KBASE
from devpro.render import (
    definitions,
    filled_body,
    render_agents_file,
    render_all,
    render_definition,
)
from devpro.runner_file import _named_harnesses, include_line, install_include_lines
from devpro.vocabulary import Kind

_SNIPPET_SETS = {
    package.source: snippets for package in SHIPPED_PACKAGES if (snippets := package.installed_snippets()) is not None
}
_KB_SNIPPETS = _SNIPPET_SETS["kb-tools"]

_BEGIN = " <!-- vvv-devpro do not edit at or between marker lines. devpro-vvv -->"
"""The begin marker line an earlier, unstamped revision wrote: a block of no plugin."""
_STAMPED_BEGIN = f" <!-- vvv-devpro devpro {__version__} do not edit at or between marker lines. devpro-vvv -->"
_END = " <!-- ^^^-devpro do not edit at or between marker lines. devpro-^^^ -->"


def _block(harness: Harness) -> list[str]:
    lines, begin, end = marker_span(render_agents_file(harness, DEVPRO, scope="x"), where="render")
    return lines[begin : end + 1]


def _files(root: Path) -> dict[str, bytes]:
    """Every file under `root` with its bytes."""
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


# The agents-file render.


def test_the_fresh_render_holds_the_title_and_one_marker_span() -> None:
    user_dir = Path(CLAUDE.user_harness_dir).expanduser()
    text = render_agents_file(CLAUDE, DEVPRO, scope=scope_name(CLAUDE, user_dir))
    lines, begin, end = marker_span(text, where="render")
    assert (lines[0], lines[begin], lines[end]) == ("# Global info and directives", _STAMPED_BEGIN, _END)
    assert text.endswith(_END + "\n")


def test_an_agents_file_hole_in_any_other_kind_is_an_unknown_placeholder() -> None:
    defn = Definition(name="probe", kind=Kind.COMMAND, body="for @!agf-scope-name!@")
    ctx = Render(harness=CLAUDE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
    with pytest.raises(InputError, match=re.escape("definition 'probe': unknown placeholder @!agf-scope-name!@")):
        filled_body(defn, ctx)


# The installer. A project directory under opencode writes AGENTS.md and nothing else.


def _install(directory: Path, harness: Harness = OPENCODE, uncommitted: tuple[str, ...] = ()) -> None:
    install_agents_file(directory, harness, DEVPRO, uncommitted=lambda: uncommitted)


def test_install_replaces_only_the_span_and_keeps_every_other_byte(tmp_path: Path, capsys) -> None:
    above = "# My rules\r\n\r\nmine above\r\n"
    below = "\nmine below\r\n\r\n  trailing  "
    begin = " <!-- vvv-devpro version[abc1234] an earlier revision's wording devpro-vvv -->"
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
    _install(tmp_path, uncommitted=("?? devpro/x.py",))
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == render_agents_file(
        OPENCODE, DEVPRO, scope=tmp_path.name
    )


@pytest.mark.parametrize("git_entry", ["directory", "file", None])
def test_a_checkout_is_a_package_parent_holding_a_git_entry(tmp_path: Path, git_entry: str | None) -> None:
    package = tmp_path / "devpro"
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
    monkeypatch.setattr("devpro.install_base.REPO_ROOT", None)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert uncommitted_sources() == ()


def test_a_checkout_git_cannot_read_still_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".git").write_text("", encoding="utf-8")
    monkeypatch.setattr("devpro.install_base.REPO_ROOT", tmp_path)
    with pytest.raises(InputError, match="cannot read the commit state"):
        uncommitted_sources()


@pytest.fixture
def _site_packages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A site-packages directory holding the package, with no repository around it."""
    site = (tmp_path / "site").resolve()
    (site / "devpro" / "kb-tools").mkdir(parents=True)
    monkeypatch.setattr("devpro.install.PACKAGE_ROOT", site / "devpro")
    monkeypatch.setattr("devpro.install_base.REPO_ROOT", None)
    return site


def test_outside_a_checkout_a_project_at_site_packages_gets_its_include_line(_site_packages: Path) -> None:
    (_site_packages / "justfile").write_text("", encoding="utf-8")
    install_include_lines(_site_packages, [_KB_SNIPPETS], harness_relpath=".claude")
    lines = (_site_packages / "justfile").read_text(encoding="utf-8").splitlines()
    assert include_line(_KB_SNIPPETS, runner="just", harness_relpath=".claude") in lines


def test_a_project_directory_under_claude_writes_agents_md_and_the_redirect(tmp_path: Path) -> None:
    _install(tmp_path, CLAUDE)
    assert _files(tmp_path) == {
        "AGENTS.md": render_agents_file(CLAUDE, DEVPRO, scope=tmp_path.name).encode(),
        "CLAUDE.md": b"@AGENTS.md\n",
    }
    assert render_agents_file(CLAUDE, DEVPRO, scope=tmp_path.name).startswith(
        f"# {tmp_path.name} info and directives\n"
    )


def test_a_claude_redirect_is_followed_and_the_text_around_the_block_kept(tmp_path: Path) -> None:
    above = "# Project rules\n\nmine above\n"
    below = "\nmine below\n"
    prior = f"{above}{_STAMPED_BEGIN}\nold block\n{_END}{below}"
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text(prior, encoding="utf-8")
    _install(tmp_path, CLAUDE)
    assert _files(tmp_path) == {
        "AGENTS.md": (above + "\n".join(_block(CLAUDE)) + below).encode(),
        "CLAUDE.md": b"@AGENTS.md\n",
        "backup.AGENTS.md": prior.encode(),
    }


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
        "docs/rules.md": render_agents_file(OPENCODE, DEVPRO, scope=tmp_path.name).encode(),
    }


def test_the_user_directory_writes_the_native_file_and_no_redirect(tmp_path: Path) -> None:
    harness = dataclasses.replace(CLAUDE, user_harness_dir=str(tmp_path))
    _install(tmp_path, harness)
    assert _files(tmp_path) == {"CLAUDE.md": render_agents_file(harness, DEVPRO, scope="Global").encode()}


def test_a_relative_user_directory_is_the_destination_itself(tmp_path: Path) -> None:
    """Mage's `.` names the directory being installed into — the native file, no `AGENTS.md`
    redirect — and leaves a harness whose user directory is absolute writing `AGENTS.md` elsewhere."""
    _install(tmp_path, MAGE)
    assert _files(tmp_path) == {"CLAUDE.md": render_agents_file(MAGE, DEVPRO, scope="Global").encode()}
    project = tmp_path / "project"
    project.mkdir()
    _install(project, CLAUDE)
    assert _files(project) == {
        "AGENTS.md": render_agents_file(CLAUDE, DEVPRO, scope=project.name).encode(),
        "CLAUDE.md": b"@AGENTS.md\n",
    }


# The definition install. A consumer project receives its plugin under its harness directory, and —
# where the kbase plugin is installed — the kb-tools package in the kbase skill's own directory, with
# the `kbase` MCP entry and the runner include line.

_CLAUDE_RENDER = Render(harness=CLAUDE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
_KBASE_CLAUDE_RENDER = dataclasses.replace(_CLAUDE_RENDER, plugin=KBASE)
_MAGE_RENDER = Render(harness=MAGE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
_OPENCODE_RENDER = build_render(
    harness="opencode", plugin="devpro", family="claude", tier_spec="all=inherit", alias_spec=None
)
_NEW_BANNER = "---\n# !GENERATED! from devpro/definitions/gone.py — x\n# !TUNING! y\n---\n\nbody\n"
# A skill's supporting file: no frontmatter, so its banner rides on two HTML comment lines.
_COMMENT_BANNER = "<!-- !GENERATED! from devpro/definitions/kbase.py — x -->\n<!-- !TUNING! y -->"
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
    plugin: Plugin = DEVPRO,
    project_root: Path | None = None,
) -> None:
    """`install` of `plugin` into the harness directory `root`, rendered as `ctx` with its plugin replaced."""
    install(
        root,
        dataclasses.replace(ctx, plugin=plugin),
        verbose=False,
        project_root=project_root,
        uncommitted=_committed,
    )


def _committed() -> tuple[str, ...]:
    """No uncommitted sources, so a mage install's agents file does not turn on this tree's git state."""
    return ()


# The harness resources: the files a harness ships for its own harness directory, copied into ROOT as
# they stand. A harness that ships none copies nothing.

_TS_GUARDRAIL = "guardrail.ts"
_GUARDRAIL = "hooks/guardrail.pl"
_SETTINGS = ".claude/settings.json"
# A claude install writes its plugin into its plugin, below the harness directory it is given.
_CLAUDE_PLUGIN_RELPATH = f".claude/{CLAUDE.bound(DEVPRO.name).plugin_dir}"
_CLAUDE_KBASE_RELPATH = f".claude/{CLAUDE.bound(KBASE.name).plugin_dir}"


def _claude_plugin(harness_dir: Path, plugin: Plugin = DEVPRO) -> Path:
    return harness_dir / CLAUDE.bound(plugin.name).plugin_dir


def _opencode_plugin(harness_dir: Path, plugin: Plugin = DEVPRO) -> Path:
    return harness_dir / OPENCODE.bound(plugin.name).plugin_dir


_REGISTRATION = "hooks/hooks.json"


def test_an_opencode_install_copies_the_harnesss_plugin_byte_verbatim(tmp_path: Path) -> None:
    """The opencode plugin is the harness's own file, not this repository's generated product: it lands
    under ROOT byte for byte, so a stamp anywhere in the copy would show as a difference from the
    source."""
    root = tmp_path / ".opencode"
    root.mkdir()
    _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
    copied = _opencode_plugin(root) / _TS_GUARDRAIL
    assert copied.read_bytes() == (PACKAGE_ROOT / HARNESS_RESOURCES_SOURCE / "opencode" / _TS_GUARDRAIL).read_bytes()


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
    copied = _opencode_plugin(root) / _TS_GUARDRAIL
    before = copied.read_bytes()
    stale = _opencode_plugin(root) / "agents/gone.md"
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
    monkeypatch.setattr("devpro.install.PACKAGE_ROOT", tmp_path / "repo")
    root = tmp_path / ".probe"
    copies = harness_resource_copies(root, harness="probe")
    assert [target.relative_to(root).as_posix() for _, target in copies] == ["plugins/keep.ts"]


def test_the_resources_tree_is_not_read_as_a_harness_module() -> None:
    """`resources/` holds no `__init__.py`, so `pkgutil` lists it as a tree rather than a module and
    `load` returns every harness module. A `resources` package appearing later would break that, so the
    same case pins the tree's presence: a resource tree that went missing fails here too, rather than
    the plugin copy silently landing nothing."""
    assert sorted(load("devpro.harnesses", "HARNESS")) == ["claude", "mage", "opencode"]
    assert (PACKAGE_ROOT / HARNESS_RESOURCES_SOURCE / "opencode").is_dir()


def test_every_harness_omits_a_name_the_package_discovers() -> None:
    """`omits` is matched against definition names by string, so a name nothing discovers drops nothing
    and ships the file it was meant to, silently. Each name is checked against discovery instead."""
    discovered = {defn.name for _, defn in definitions()}
    harnesses = cast(dict[str, Harness], load("devpro.harnesses", "HARNESS"))
    unknown = [
        (harness_name, omitted)
        for harness_name, harness in harnesses.items()
        for omitted in sorted(harness.omits)
        if omitted not in discovered
    ]
    assert unknown == []


def test_a_duplicate_output_is_refused_even_when_the_plugin_ships_neither_definition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The duplicate check runs over what discovery found, before the plugin filter: a plugin shipping
    neither definition would otherwise render past a collision another plugin refuses."""
    first = Definition(name="probe", kind=Kind.COMMAND, body="one")
    second = Definition(name="probe", kind=Kind.COMMAND, body="two")
    monkeypatch.setattr("devpro.render.discover", lambda: [("m.a", (first,)), ("m.b", (second,))])
    assert not KBASE.ships("probe")
    with pytest.raises(InputError, match=re.escape("'commands/probe.md' is produced by both m.a and m.b")):
        render_all(dataclasses.replace(_CLAUDE_RENDER, plugin=KBASE))


_DOCDICER_PACKAGE = "skills/docdicer/tools/docdicer"
_DEVELOPMENT_SCRIPTS = "skills/development/scripts/cold-read.sh"
_KBASE_PACKAGE = "skills/kbase/kb-tools/runner-snippets/kb.just"
_OPENCODE_SETTINGS_NAMES = {"opencode.json", "opencode.jsonc"}


def _delivers_the_kbase_server(project: Path, root: Path) -> bool:
    """Whether an install delivered the `kbase` MCP server: in a `.mcp.json` anywhere in the project,
    or as a record of ROOT's registry."""
    registry = root / "registry.json"
    if registry.is_file() and json.loads(registry.read_text(encoding="utf-8"))["mcp"]:
        return True
    return any(path.name == ".mcp.json" for path in project.rglob("*"))


@pytest.mark.parametrize(
    "harness, plugin_dir_of",
    [
        ("claude", lambda project, plugin: _claude_plugin(project / ".claude", plugin)),
        ("opencode", lambda project, plugin: _opencode_plugin(project / ".opencode", plugin)),
    ],
    ids=["claude", "opencode"],
)
@pytest.mark.parametrize("plugin", [DEVPRO, KBASE], ids=lambda plugin: plugin.name)
def test_supporting_artifacts_ship_with_the_definition_that_owns_them(
    tmp_path: Path, harness: str, plugin_dir_of: Callable[[Path, Plugin], Path], plugin: Plugin
) -> None:
    """Both plugins carry the development scripts. Both carry the docdicer tools; devpro carries none of the
    kbase toolchain; kbase carries the kb-tools package, the kbase MCP entry and the kb runner include
    line. Both write the docdicer include line, kbase beside the kb one in the same runner file. No
    install writes a project's opencode settings file."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    main(["install", str(project), f"--plugin={plugin.name}", f"--harness={harness}"])
    root = plugin_dir_of(project, plugin)
    kbase = plugin is KBASE
    assert (root / _DEVELOPMENT_SCRIPTS).is_file()
    assert (root / _DOCDICER_PACKAGE).is_file()
    assert (root / _KBASE_PACKAGE).is_file() is kbase
    assert _delivers_the_kbase_server(project, root) is kbase
    assert not any(path.name in _OPENCODE_SETTINGS_NAMES for path in project.rglob("*"))
    justfile = (project / "justfile").read_text(encoding="utf-8")
    assert "runner-snippets/docdicer.just" in justfile
    assert ("runner-snippets/kb.just" in justfile) is kbase
    assert not (project / "Makefile").exists()


def test_an_install_changes_nothing_outside_its_own_install_directory(tmp_path: Path) -> None:
    """Another plugin's install directory sits beside this one inside the harness directory's `skills/`,
    and so may an earlier layout's: a devpro install leaves every file of both as it found them."""
    project = tmp_path / "project"
    project.mkdir()
    main(["install", str(project), "--plugin=kbase", "--harness=claude"])
    _plant(project / ".claude/skills/earlier-layout/agents/python-coder.md", _NEW_BANNER)
    others = {
        relative: data
        for relative, data in _files(project).items()
        if relative.startswith((f"{_CLAUDE_KBASE_RELPATH}/", ".claude/skills/earlier-layout/"))
    }
    assert any(relative.startswith(_CLAUDE_KBASE_RELPATH) for relative in others)
    main(["install", str(project), "--harness=claude"])
    after = _files(project)
    assert {relative: after.get(relative) for relative in others} == others
    assert (project / _CLAUDE_PLUGIN_RELPATH / "agents/python-coder.md").is_file()


def test_a_kbase_install_writes_the_kbase_skill_the_package_the_mcp_entry_and_the_include_line(
    tmp_path: Path,
) -> None:
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    _definition_install(root, plugin=KBASE, project_root=project)
    plugin = _claude_plugin(root, KBASE)
    for relative in _KB_SKILL_FILES:
        assert (plugin / relative).is_file()
    kb_just = (plugin / "skills/kbase/kb-tools/runner-snippets/kb.just").read_text(encoding="utf-8").split("\n")
    source_just = (PACKAGE_ROOT / "kb-tools/runner-snippets/kb.just").read_text(encoding="utf-8").split("\n")
    kb_mk = (plugin / "skills/kbase/kb-tools/runner-snippets/kb.mk").read_text(encoding="utf-8").split("\n")
    assert kb_just[0].startswith("# !INSTALLED! from devpro/kb-tools/runner-snippets/kb.just — ")
    assert kb_just[1:] == source_just
    assert kb_mk[0].startswith("# !INSTALLED! from devpro/kb-tools/runner-snippets/kb.mk — ")
    assert json.loads((plugin / ".mcp.json").read_text(encoding="utf-8")) == {
        "mcpServers": {"kbase": {"command": "kbase", "args": ["mcp"]}}
    }
    assert not (project / ".mcp.json").exists()
    relpath = plugin.relative_to(project).as_posix()
    assert (project / "justfile").read_text(encoding="utf-8") == (
        f"# mine\n\nimport? '{relpath}/skills/docdicer/tools/runner-snippets/docdicer.just'\n"
        f"\nimport? '{relpath}/skills/kbase/kb-tools/runner-snippets/kb.just'\n"
    )


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


def test_an_operating_system_failure_is_reported_as_an_error_and_exits_2(tmp_path: Path, capsys) -> None:
    out = tmp_path / "missing" / "AGENTS.md"
    with pytest.raises(SystemExit) as exited:
        main(["render-agents-file", "claude", str(out)])
    assert exited.value.code == 2
    assert capsys.readouterr().err.startswith("error: ")
    assert not out.parent.exists()


def test_the_help_usage_line_lists_every_verb_but_the_hidden_ones(capsys) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    usage = capsys.readouterr().out.split("\n\n")[0]
    listed = re.search(r"\{([^}]*)\}", usage)
    assert listed is not None
    verbs = next(action for action in build_parser()._actions if isinstance(action, argparse._SubParsersAction))
    assert listed.group(1).split(",") == [name for name in verbs.choices if name not in {"harness", "plugins"}]


def test_the_plugins_verb_prints_each_plugin_name_one_per_line(capsys) -> None:
    main(["plugins"])
    assert capsys.readouterr().out.splitlines() == sorted(load("devpro.plugins", "PLUGIN"))


def _rendered_plugin(out: Path, stdout: str) -> str:
    return KBASE.name if (out / "skills/kbase/SKILL.md").is_file() else DEVPRO.name


def _installed_plugin(out: Path, stdout: str) -> str:
    (plugin,) = (plugin.name for plugin in (DEVPRO, KBASE) if _claude_plugin(out / ".claude", plugin).is_dir())
    return plugin


def _agents_file_plugin(out: Path, stdout: str) -> str:
    text = (out / "AGENTS.md").read_text(encoding="utf-8")
    scope = scope_name(CLAUDE, out)
    (plugin,) = (plugin.name for plugin in (DEVPRO, KBASE) if text == render_agents_file(CLAUDE, plugin, scope=scope))
    return plugin


def _harness_plugin(out: Path, stdout: str) -> str:
    return stdout.strip()


@pytest.mark.parametrize(
    ("verb", "args", "plugin_used"),
    [
        ("render", ["--out", "{out}"], _rendered_plugin),
        ("install", ["{out}", "--harness=claude"], _installed_plugin),
        ("install-agents-file", ["{out}", "--harness=claude"], _agents_file_plugin),
        ("render-agents-file", ["claude", "{out}/AGENTS.md"], _agents_file_plugin),
        ("harness", ["mage", "project-harness-dir"], _harness_plugin),
    ],
    ids=["render", "install", "install-agents-file", "render-agents-file", "harness"],
)
def test_a_plugin_verb_takes_the_plugin_as_a_flag_defaulting_to_devpro(
    tmp_path: Path, capsys, verb: str, args: list[str], plugin_used: Callable[[Path, str], str]
) -> None:
    def run(name: str, *plugin_flag: str) -> str:
        out = tmp_path / name
        out.mkdir()
        main([verb, *plugin_flag, *(arg.format(out=out) for arg in args)])
        return plugin_used(out, capsys.readouterr().out)

    assert run("default") == "devpro"
    assert run("flagged", "--plugin=kbase") == "kbase"
    positional = tmp_path / "positional"
    positional.mkdir()
    with pytest.raises(SystemExit) as exited:
        main([verb, "kbase", *(arg.format(out=positional) for arg in args)])
    assert exited.value.code == 2
    assert not any(positional.iterdir())


def test_the_cli_plugin_argument_installs_the_kbase_skill_files_and_the_skill_kb_tools_destination(
    tmp_path: Path,
) -> None:
    """The plugin argument reaches `install()`: driven through the CLI entry point, its own effect —
    the kbase skill's files and the runner snippets — is what appears under the plugin's ROOT."""
    root = tmp_path / ".claude"
    root.mkdir()
    main(["install", str(root), "--plugin=kbase", "--harness=claude"])
    plugin = _claude_plugin(root, KBASE)
    assert all((plugin / relative).is_file() for relative in _KB_SKILL_FILES)
    snippets = plugin / "skills/kbase/kb-tools/runner-snippets"
    assert (snippets / "kb.just").is_file() and (snippets / "kb.mk").is_file()


def test_a_run_prunes_a_stale_definition_of_ours_its_plugin_does_not_ship(tmp_path: Path, capsys) -> None:
    root = tmp_path / ".claude"
    plugin = _claude_plugin(root)
    (plugin / "agents").mkdir(parents=True)
    (plugin / "agents/kb-maintainer.md").write_text(_NEW_BANNER, encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    assert not (plugin / "agents/kb-maintainer.md").exists()
    assert f"pruned {plugin / 'agents/kb-maintainer.md'}" in capsys.readouterr().out


def test_a_kbase_install_prunes_a_stale_reference_and_keeps_a_user_file(tmp_path: Path, capsys) -> None:
    """A supporting file is ours by its own first line, so prune needs no rule keyed on the skill."""
    root = tmp_path / ".claude"
    plugin = _claude_plugin(root, KBASE)
    references = plugin / "skills/kbase/references"
    references.mkdir(parents=True)
    stale = references / "gone.md"
    stale.write_text(f"{_COMMENT_BANNER}\n\nold text\n", encoding="utf-8")
    mine = plugin / "skills/kbase/notes.md"
    mine.write_text("---\nmine\n---\n", encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, plugin=KBASE, project_root=tmp_path)
    assert not stale.exists()
    assert mine.read_text(encoding="utf-8") == "---\nmine\n---\n"
    assert all((plugin / relative).is_file() for relative in _KB_SKILL_FILES)
    assert f"pruned {stale}" in capsys.readouterr().out


def test_prune_recognizes_the_banner_the_renderer_writes(tmp_path: Path, capsys) -> None:
    """The recognizer reads what `render_definition` emits, not a prefix typed into the test."""
    root = tmp_path / ".claude"
    (_claude_plugin(root) / "commands").mkdir(parents=True)
    stale = _claude_plugin(root) / "commands/stale.md"
    stale.write_text(
        render_definition(
            Definition(name="stale", kind=Kind.COMMAND, body="body"),
            _CLAUDE_RENDER,
            module="devpro.definitions.probe",
        ),
        encoding="utf-8",
    )
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    assert not stale.exists()
    assert f"pruned {stale}" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("beside", "kept", "removed"),
    [
        ("agents/sub/mine.md", ["agents/sub", "agents/sub/mine.md"], ["agents/sub/gone.md"]),
        ("agents/empty/", ["agents/empty", "."], ["agents/sub"]),
    ],
    ids=["beside-a-user-file", "beside-an-empty-directory"],
)
def test_the_prune_removes_only_the_directories_it_empties(
    tmp_path: Path, beside: str, kept: list[str], removed: list[str]
) -> None:
    """The upward walk stops at a directory still holding something; one that was already empty, and the
    install directory, stay."""
    root = tmp_path / ".claude"
    plugin = _claude_plugin(root)
    (plugin / "agents/sub").mkdir(parents=True)
    (plugin / "agents/sub/gone.md").write_text(_NEW_BANNER, encoding="utf-8")
    if beside.endswith("/"):
        (plugin / beside).mkdir()
    else:
        (plugin / beside).write_text("mine\n", encoding="utf-8")
    _definition_install(root, project_root=tmp_path)
    assert all((plugin / path).exists() for path in kept)
    assert not any((plugin / path).exists() for path in removed)


def test_a_banner_naming_a_foreign_module_is_not_ours(tmp_path: Path) -> None:
    """The payload has to name a module path this repository writes; the bare mark is not enough."""
    root = tmp_path / ".claude"
    (_claude_plugin(root) / "skills/probe/references").mkdir(parents=True)
    mine = _claude_plugin(root) / "skills/probe/references/mine.md"
    text = "<!-- !GENERATED! from someone/else.md — x -->\n<!-- !TUNING! y -->\n\nbody\n"
    mine.write_text(text, encoding="utf-8")
    _definition_install(root, project_root=tmp_path)
    assert mine.read_text(encoding="utf-8") == text


def test_an_opencode_kb_install_registers_the_server_in_its_registry_and_leaves_the_projects_settings(
    tmp_path: Path,
) -> None:
    """The server's entry is a record of the plugin's own registry, in opencode's v2 shape; the project's
    settings file stays as the project wrote it, and none is created beside it."""
    project = tmp_path
    root = project / ".opencode"
    root.mkdir()
    discovered = root / "opencode.json"
    prior = json.dumps({"theme": "omlx", "mcp": {"servers": {"other": {"type": "local"}}}})
    discovered.write_text(prior, encoding="utf-8")
    _definition_install(root, _OPENCODE_RENDER, plugin=KBASE, project_root=project)
    assert discovered.read_text(encoding="utf-8") == prior
    assert not (root / "opencode.jsonc").exists() and not (project / "opencode.json").exists()
    registry = json.loads((_opencode_plugin(root, KBASE) / "registry.json").read_text(encoding="utf-8"))
    assert registry["mcp"] == {"kbase": {"type": "local", "command": ["kbase", "mcp"]}}


# mage's `.mcp.json` is the plugin's own, at ROOT rather than at the project the plugin is installed under.


def test_a_mage_kbase_install_renders_its_mcp_json_whole_beside_the_plugin_at_root(tmp_path: Path) -> None:
    """ROOT is the plugin's own, so `.mcp.json` there is rendered whole: a prior one of ours is replaced,
    a server beside the entry included, and the project root holds no `.mcp.json` at all. The manifest
    is still the three-key one carrying `__version__`. No runner include line is written and no
    `Makefile` created at either root: a plugin is not a repo project."""
    project = tmp_path
    root = project / "plugins/kbase"
    root.mkdir(parents=True)
    entry = {"command": "kbase", "args": ["mcp", "--project-dir-required"]}
    prior = {"mcpServers": {"kbase": {"command": "kbase", "args": ["mcp"]}, "other": {"command": "x"}}}
    (root / ".mcp.json").write_text(json.dumps(prior), encoding="utf-8")
    _definition_install(root, _MAGE_RENDER, plugin=KBASE, project_root=project)
    settings = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
    assert settings == {"mcpServers": {"kbase": entry}}
    assert not (project / ".mcp.json").exists()
    manifest = json.loads((root / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert set(manifest) == {"name", "version", "description"}
    assert manifest["version"] == __version__
    assert not (root / "Makefile").exists()
    assert not (project / "Makefile").exists()


def test_a_mage_devpro_install_ships_no_part_of_the_kbase_toolchain(tmp_path: Path) -> None:
    """Under mage too the plugin decides: a devpro plugin holds no kbase skill, no kb-tools package and
    no MCP settings file."""
    project = tmp_path
    root = project / "plugins/devpro"
    root.mkdir(parents=True)
    _definition_install(root, _MAGE_RENDER, project_root=project)
    assert not (root / ".mcp.json").exists()
    assert not (root / "skills/kbase").exists()
    assert (root / "agents/python-coder.md").is_file()


# A mage install is a plugin directory that is carried or published from where it stands: nothing in it
# names this machine, nothing in it fires a hook, and the manifest is owned by the marker it states.

_MAGE_MANIFEST = ".claude-plugin/plugin.json"


def test_a_mage_install_names_no_absolute_path_and_no_home_directory(tmp_path: Path) -> None:
    """Nothing the plugin writes names the directory it lands in, because that directory moves. The `~/`
    search is over the manifest and the MCP settings file alone: a definition's prose names `~/.config` in
    order to forbid hardcoding it, so a tree-wide search reports the advice rather than a path."""
    project = tmp_path
    root = project / "plugins/devpro"
    root.mkdir(parents=True)
    _definition_install(root, _MAGE_RENDER, plugin=KBASE, project_root=project)
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
    root = project / "plugins/devpro"
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
    root = project / "plugins/devpro"
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
    root = project / "plugins/devpro"
    manifest = root / _MAGE_MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"name": "other"}\n', encoding="utf-8")
    before = _files(tmp_path)
    with pytest.raises(InputError, match=re.escape(f"'{manifest}'")):
        _definition_install(root, _MAGE_RENDER, project_root=project)
    assert _files(tmp_path) == before


def test_a_verbose_mage_install_lists_the_manifest_as_written(tmp_path: Path, capsys) -> None:
    project = tmp_path
    root = project / "plugins/devpro"
    root.mkdir(parents=True)
    capsys.readouterr()
    install(root, _MAGE_RENDER, verbose=True, project_root=project, uncommitted=_committed)
    assert f"wrote {root / _MAGE_MANIFEST}" in capsys.readouterr().out.splitlines()


def test_the_include_line_is_appended_to_an_existing_justfile(tmp_path: Path) -> None:
    root = tmp_path / ".claude"
    root.mkdir()
    (tmp_path / "justfile").write_text("default:\n  @echo hi\n", encoding="utf-8")
    _definition_install(root, plugin=KBASE, project_root=tmp_path)
    assert (tmp_path / "justfile").read_text(encoding="utf-8") == (
        f"default:\n  @echo hi\n\nimport? '{_CLAUDE_KBASE_RELPATH}/skills/docdicer/tools/runner-snippets/docdicer.just'\n"
        f"\nimport? '{_CLAUDE_KBASE_RELPATH}/skills/kbase/kb-tools/runner-snippets/kb.just'\n"
    )


def test_a_makefile_is_created_when_the_project_has_neither_runner_file(tmp_path: Path) -> None:
    """Created once, holding every set's line in `SHIPPED_PACKAGES` order."""
    root = tmp_path / ".opencode"
    root.mkdir()
    _definition_install(root, _OPENCODE_RENDER, plugin=KBASE, project_root=tmp_path)
    text = (tmp_path / "Makefile").read_text(encoding="utf-8")
    assert text.startswith("# Makefile — created by the devpro installer.\n")
    assert text.endswith(
        "\n-include .opencode/plugins/kbase/skills/docdicer/tools/runner-snippets/docdicer.mk\n"
        "-include .opencode/plugins/kbase/skills/kbase/kb-tools/runner-snippets/kb.mk\n"
    )
    assert not (tmp_path / "justfile").exists()


def test_a_second_harness_writes_no_include_line_and_reports_the_first(tmp_path: Path, capsys) -> None:
    project = tmp_path
    first = project / ".claude"
    first.mkdir()
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    _definition_install(first, plugin=KBASE, project_root=project)
    before = (project / "justfile").read_bytes()
    second = project / ".opencode"
    second.mkdir()
    capsys.readouterr()
    _definition_install(second, _OPENCODE_RENDER, plugin=KBASE, project_root=project)
    assert (project / "justfile").read_bytes() == before
    err = capsys.readouterr().err
    assert "no include line written" in err and "'claude'" in err


@pytest.mark.parametrize(
    "snippets_path",
    [
        "custom/kb-tools/runner-snippets",
        "kb-tools/runner-snippets",
    ],
    ids=["hand-written", "short-tree"],
)
def test_an_include_line_for_this_harness_under_any_tree_is_rewritten_in_place(
    tmp_path: Path, snippets_path: str
) -> None:
    """A line naming this harness directory is this install's line whatever tree its path spells, one
    no release here wrote included, so its whole path is replaced where it stands, naming the
    plugin's snippets, and the file keeps one include line rather than gaining a second beside a dead one."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    (project / "justfile").write_text(f"default:\n  @echo hi\n\nimport? '.claude/{snippets_path}/kb.just'\n")
    _definition_install(root, plugin=KBASE, project_root=project)
    text = (project / "justfile").read_text(encoding="utf-8")
    expected = f"import? '{_CLAUDE_KBASE_RELPATH}/skills/kbase/kb-tools/runner-snippets/kb.just'"
    docdicer = f"import? '{_CLAUDE_KBASE_RELPATH}/skills/docdicer/tools/runner-snippets/docdicer.just'"
    assert text == f"default:\n  @echo hi\n\n{expected}\n\n{docdicer}\n"
    assert text.count("runner-snippets/kb.just") == 1


@pytest.mark.parametrize(
    "present, appended, label",
    [
        (
            "import? '.claude/skills/kbase/skills/docdicer/tools/runner-snippets/docdicer.just'",
            "import? '.opencode/plugins/kbase/skills/kbase/kb-tools/runner-snippets/kb.just'",
            "docdicer",
        ),
        (
            "import? '.claude/skills/kbase/skills/kbase/kb-tools/runner-snippets/kb.just'",
            "import? '.opencode/plugins/kbase/skills/docdicer/tools/runner-snippets/docdicer.just'",
            "kb",
        ),
    ],
    ids=["docdicer-present", "kb-present"],
)
def test_each_snippet_set_is_judged_alone(tmp_path: Path, capsys, present: str, appended: str, label: str) -> None:
    """One set's line naming another harness is reported and left byte for byte; it neither counts as
    the other set's line nor stops that line being appended."""
    project = tmp_path
    root = project / ".opencode"
    root.mkdir()
    (project / "justfile").write_text(f"{present}\n", encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, _OPENCODE_RENDER, plugin=KBASE, project_root=project)
    assert (project / "justfile").read_text(encoding="utf-8") == f"{present}\n\n{appended}\n"
    err = capsys.readouterr().err
    assert err.count("no include line written") == 1
    assert f" {label} snippets" in err and "'claude'" in err


@pytest.mark.parametrize(
    "prior, expected",
    [
        (
            "# import? '.claude/custom/kb-tools/runner-snippets/kb.just'\n",
            "# import? '.claude/custom/kb-tools/runner-snippets/kb.just'\n"
            "\nimport? '.claude/skills/kbase/kb-tools/runner-snippets/kb.just'\n",
        ),
        (
            "import? '.claude/custom/kb-tools/runner-snippets/kb.just'  # mine\n",
            "import? '.claude/skills/kbase/kb-tools/runner-snippets/kb.just'  # mine\n",
        ),
        (
            "default:\r\n  @echo hi\r\n\r\nimport? '.claude/custom/kb-tools/runner-snippets/kb.just'\r\n",
            "default:\r\n  @echo hi\r\n\r\nimport? '.claude/skills/kbase/kb-tools/runner-snippets/kb.just'\r\n",
        ),
    ],
    ids=["commented-out", "trailing-comment", "crlf"],
)
def test_the_include_line_rewrite_touches_only_its_own_path_token(tmp_path: Path, prior: str, expected: str) -> None:
    """A commented line is not an include; a rewrite replaces the snippets path alone, keeping an
    assignment's left-hand side, a trailing comment and the file's own line endings."""
    (tmp_path / "justfile").write_bytes(prior.encode("utf-8"))
    install_include_lines(tmp_path, [_KB_SNIPPETS], harness_relpath=".claude")
    assert (tmp_path / "justfile").read_bytes() == expected.encode("utf-8")


def test_a_makefile_include_line_is_recognized_by_the_same_shape(tmp_path: Path) -> None:
    """The `-include` form is matched on the path's shape too, the Makefile's own snippet being
    `kb.mk`: a stale tree is rewritten in place and no second line lands beside it."""
    prior = "all:\n\t@echo hi\n\n-include .opencode/custom/kb-tools/runner-snippets/kb.mk\n"
    (tmp_path / "Makefile").write_text(prior, encoding="utf-8")
    install_include_lines(tmp_path, [_KB_SNIPPETS], harness_relpath=".opencode")
    text = (tmp_path / "Makefile").read_text(encoding="utf-8")
    assert text == "all:\n\t@echo hi\n\n-include .opencode/skills/kbase/kb-tools/runner-snippets/kb.mk\n"


def test_two_include_lines_are_reported_and_left(tmp_path: Path, capsys) -> None:
    """Rewriting one of two would leave the other stale, so the operator merges them by hand."""
    prior = (
        "import? '.claude/custom/kb-tools/runner-snippets/kb.just'\n"
        "import? '.claude/skills/kbase/kb-tools/runner-snippets/kb.just'\n"
    )
    (tmp_path / "justfile").write_text(prior, encoding="utf-8")
    install_include_lines(tmp_path, [_KB_SNIPPETS], harness_relpath=".claude")
    assert (tmp_path / "justfile").read_text(encoding="utf-8") == prior
    assert "names the kb snippets on lines 1, 2" in capsys.readouterr().err


def test_an_include_line_naming_no_harness_reports_its_raw_prefix() -> None:
    [match] = _named_harnesses(
        "default:\n  @echo hi\nimport? 'tools/skills/kbase/kb-tools/runner-snippets/kb.just'\n",
        _KB_SNIPPETS,
        runner="just",
    )
    assert (match.name, match.index) == ("tools", 2)


@pytest.mark.parametrize("runner, matched", [("just", True), ("make", False)], ids=["its-own", "the-others"])
def test_a_line_is_a_line_for_the_runner_whose_snippet_it_names(runner: str, matched: bool) -> None:
    """`kb.just` is the justfile's snippet and `kb.mk` the Makefile's, so one runner's snippet named in
    the other's file is not an include line that install has to rewrite."""
    text = "import? '.claude/kb-tools/runner-snippets/kb.just'\n"
    assert bool(_named_harnesses(text, _KB_SNIPPETS, runner=runner)) is matched


def test_a_non_utf8_runner_file_is_refused_before_the_first_write(tmp_path: Path) -> None:
    """The runner file is decoded with every other check: the refusal writes nothing, where a decode
    after the writes would leave a half-updated install and refuse the retry too."""
    root = tmp_path / ".claude"
    root.mkdir()
    (tmp_path / "justfile").write_bytes(b"\xff\xfe default:\n")
    before = _files(tmp_path)
    with pytest.raises(InputError, match="justfile"):
        _definition_install(root, plugin=KBASE, project_root=tmp_path)
    assert _files(tmp_path) == before


def test_the_repositorys_own_project_root_gets_no_include_line() -> None:
    before = (REPO_ROOT / "justfile").read_bytes()
    install_include_lines(REPO_ROOT, list(_SNIPPET_SETS.values()), harness_relpath=".claude")
    assert (REPO_ROOT / "justfile").read_bytes() == before
    assert not (REPO_ROOT / "Makefile").exists()


def test_no_two_snippet_sets_name_the_same_snippet() -> None:
    """An include line is recognized by its snippets directory's name and snippet file alone, so a pair
    two sets shared would let one set's line count as the other's."""
    pairs = [
        (PurePosixPath(snippet_set.directory).name, snippet)
        for snippet_set in _SNIPPET_SETS.values()
        for snippet in snippet_set.snippets.values()
    ]
    assert len(pairs) == len(set(pairs))


def test_a_shipped_package_leaves_its_tests_and_documents_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What the docdicer tools row cannot exercise, its source holding neither: a package's tests and
    project documents do not ship. A row over a temporary source stands in for the table."""
    repo = tmp_path / "repo"
    package = repo / "devpro" / "probe_pkg"
    (package / "tests").mkdir(parents=True)
    (package / "tool.py").write_text("print('probe')\n", encoding="utf-8")
    (package / "tests/test_tool.py").write_text("pass\n", encoding="utf-8")
    (package / "SPEC.md").write_text("# probe\n", encoding="utf-8")
    monkeypatch.setattr("devpro.install.PACKAGE_ROOT", repo / "devpro")
    monkeypatch.setattr(
        "devpro.install.SHIPPED_PACKAGES", (ShippedPackage("probe_pkg", "adj-tools/probe_pkg", "python-coder"),)
    )
    project = tmp_path / "project"
    root = project / ".claude"
    install(root, _CLAUDE_RENDER, verbose=False, project_root=project, uncommitted=_committed)
    plugin = _claude_plugin(root)
    assert (plugin / "adj-tools/probe_pkg/tool.py").is_file()
    assert not (plugin / "adj-tools/probe_pkg/tests").exists()
    assert not (plugin / "adj-tools/probe_pkg/SPEC.md").exists()


def test_a_direct_install_into_the_user_directory_is_user_level(_home: Path) -> None:
    root = _home / ".claude"
    root.mkdir(parents=True)
    install(root, _CLAUDE_RENDER, verbose=False, project_root=_home, uncommitted=_committed)
    assert (_claude_plugin(root) / "agents").is_dir()
    assert not (_claude_plugin(root) / "hooks").exists() and not (root / "settings.json").exists()


def test_a_user_level_opencode_install_copies_the_entry_and_no_guardrail(
    _home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A user-level install delivers no guardrail, but the plugin registers only through its entry, so
    the entry is the one harness resource it copies."""
    resources = tmp_path / "repo" / HARNESS_RESOURCES_SOURCE / "opencode"
    resources.mkdir(parents=True)
    for name in ("index.ts", _TS_GUARDRAIL):
        (resources / name).write_text(f"{_RESOURCE_HEADER}export const probe = 1\n", encoding="utf-8")
    monkeypatch.setattr("devpro.install.PACKAGE_ROOT", tmp_path / "repo")
    root = _home / ".config/opencode"
    root.mkdir(parents=True)
    install(root, _OPENCODE_RENDER, verbose=False, project_root=_home, uncommitted=_committed)
    plugin = _opencode_plugin(root)
    assert (plugin / "index.ts").read_bytes() == (resources / "index.ts").read_bytes()
    assert not (plugin / _TS_GUARDRAIL).exists()


# The docdicer tools package: copied into the docdicer skill's own directory, its launcher stamped by
# name, keeping any venv its launcher built there.

# Below a claude harness directory: the plugin's own docdicer tools destination.
_DOCDICER_TOOLS = f"{CLAUDE.bound(DEVPRO.name).plugin_dir}/skills/docdicer/tools"
_DOCDICER_SOURCE = PACKAGE_ROOT / "docdicer-tools"


def _preflighted(root: Path, *, project: Path, dry_run: bool = False) -> None:
    preflighted_install(
        root,
        _CLAUDE_RENDER,
        verbose=False,
        project_root=project,
        uncommitted=_committed,
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


def test_a_reinstall_replaces_the_docdicer_tools_and_keeps_their_venv(tmp_path: Path) -> None:
    """The stale file is a difference, so the install proceeds past the preflight and replaces the
    package's files; the launcher's `.venv` stays, for the launcher's own check on its next run."""
    project, root = _claude_project(tmp_path)
    _preflighted(root, project=project)
    tools = root / _DOCDICER_TOOLS
    stale = _plant(tools / "stale.txt")
    marker = _plant(tools / ".venv/marker")
    _preflighted(root, project=project)
    script = tools / "docdicer"
    lines = script.read_text(encoding="utf-8").split("\n")
    source_lines = (_DOCDICER_SOURCE / "docdicer").read_text(encoding="utf-8").split("\n")
    assert lines[0] == source_lines[0] and lines[0].startswith("#!")
    assert lines[1].startswith("# !INSTALLED! from devpro/docdicer-tools/docdicer")
    assert lines[2:] == source_lines[1:]
    assert os.access(script, os.X_OK)
    gitignore = (tools / ".gitignore").read_bytes()
    assert gitignore == (_DOCDICER_SOURCE / ".gitignore").read_bytes()
    assert ".venv/" in gitignore.decode("utf-8").splitlines()
    assert not stale.exists() and marker.is_file()


def test_an_up_to_date_target_with_a_docdicer_venv_is_left_untouched(tmp_path: Path, capsys) -> None:
    project, root = _claude_project(tmp_path)
    _preflighted(root, project=project)
    _plant(root / _DOCDICER_TOOLS / ".venv/marker")
    state = _state(project)
    capsys.readouterr()
    _preflighted(root, project=project)
    assert _UP_TO_DATE in capsys.readouterr().out
    assert _state(project) == state


def test_a_mode_change_alone_is_a_difference(tmp_path: Path, capsys) -> None:
    project, root = _claude_project(tmp_path)
    _preflighted(root, project=project)
    script = root / _DOCDICER_TOOLS / "docdicer"
    script.chmod(0o644)
    capsys.readouterr()
    _preflighted(root, project=project, dry_run=True)
    assert _dry_run_groups(capsys.readouterr().out) == {"changed": {f".claude/{_DOCDICER_TOOLS}/docdicer"}}
    _preflighted(root, project=project)
    assert _UP_TO_DATE not in capsys.readouterr().out
    assert os.access(script, os.X_OK)


def test_a_user_level_install_ships_no_docdicer_tools(_home: Path) -> None:
    root = _home / ".claude"
    marker = _plant(root / _DOCDICER_TOOLS / ".venv/marker")
    install(root, _CLAUDE_RENDER, verbose=False, project_root=_home, uncommitted=_committed)
    assert not (root / _DOCDICER_TOOLS / "docdicer").exists()
    assert marker.is_file()


# The development scripts package: copied into the development skill's own directory on every project
# install, its script stamped by name.

_COLD_READ_SOURCE = PACKAGE_ROOT / "development-tools" / "cold-read.sh"


def _installed_cold_reads(base: Path) -> list[Path]:
    return sorted(base.rglob("skills/development/scripts/cold-read.sh"))


@pytest.mark.parametrize(
    "harness_args",
    [["--harness=claude"], ["--harness=opencode"], ["--harness=mage", "--subdir=plugins/devpro"]],
    ids=["claude", "opencode", "mage"],
)
def test_a_project_install_ships_the_cold_read_script_stamped_and_executable(
    tmp_path: Path, harness_args: list[str]
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    main(["install", str(project), *harness_args])
    (script,) = _installed_cold_reads(project)
    lines = script.read_text(encoding="utf-8").split("\n")
    source_lines = _COLD_READ_SOURCE.read_text(encoding="utf-8").split("\n")
    assert lines[0] == source_lines[0] and lines[0].startswith("#!")
    assert lines[1].startswith("# !INSTALLED! from devpro/development-tools/cold-read.sh")
    assert lines[2:] == source_lines[1:]
    assert os.access(script, os.X_OK)


def test_a_user_level_install_ships_no_cold_read_script(_home: Path) -> None:
    root = _home / ".claude"
    install(root, _CLAUDE_RENDER, verbose=False, project_root=_home, uncommitted=_committed)
    assert _installed_cold_reads(_home) == []


def test_the_cold_read_script_installed_under_mage_refuses(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    main(["install", str(project), "--harness=mage", "--subdir=plugins/devpro"])
    (script,) = _installed_cold_reads(project)
    brief = tmp_path / "brief.md"
    brief.write_text("brief\n", encoding="utf-8")
    result = subprocess.run(
        [str(script), "devpro:ghost", str(brief)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        stdin=subprocess.DEVNULL,
        timeout=30,
    )
    assert result.returncode == 1
    assert "claude and opencode only" in result.stderr


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A consumer's ROOT, the claude plugin of the kbase plugin: the plugin plus the kb-tools package."""
    project = tmp_path_factory.mktemp("consumer")
    root = project / ".claude"
    root.mkdir()
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("HOME", str(project / "home"))
        install(
            root,
            _KBASE_CLAUDE_RENDER,
            verbose=False,
            project_root=project,
            uncommitted=_committed,
        )
    return _claude_plugin(root, KBASE)


def test_install_writes_every_render_and_stamps_the_packages_once(installed: Path) -> None:
    assert all((installed / path).is_file() for path, _ in render_all(_KBASE_CLAUDE_RENDER))
    kb_mk = (installed / "skills/kbase/kb-tools/runner-snippets/kb.mk").read_text(encoding="utf-8").split("\n")
    source_mk = (PACKAGE_ROOT / "kb-tools/runner-snippets/kb.mk").read_text(encoding="utf-8").split("\n")
    assert kb_mk[0].startswith("# !INSTALLED! from devpro/kb-tools/runner-snippets/kb.mk — ")
    assert kb_mk[1:] == source_mk


def test_reinstall_prunes_only_our_stale_definitions(tmp_path: Path, capsys) -> None:
    install(tmp_path, _CLAUDE_RENDER, verbose=False, uncommitted=_committed)
    plugin = _claude_plugin(tmp_path)
    planted = {
        "agents/kb-maintainer.md": _NEW_BANNER,
        "agents/gone/old.md": _NEW_BANNER,
        "agents/gone-too/deeper/old.md": _NEW_BANNER,
        "agents/mine.md": "---\nname: mine\n---\n",
        "agents/x.md.00.bak": _NEW_BANNER,
    }
    for relative, text in planted.items():
        (plugin / relative).parent.mkdir(parents=True, exist_ok=True)
        (plugin / relative).write_text(text, encoding="utf-8")
    capsys.readouterr()
    install(tmp_path, _CLAUDE_RENDER, verbose=False, uncommitted=_committed)
    left = {relative for relative in planted if (plugin / relative).exists()}
    assert left == {"agents/mine.md", "agents/x.md.00.bak"}
    assert not (plugin / "agents/gone").exists() and not (plugin / "agents/gone-too").exists()
    pruned = {line for line in capsys.readouterr().out.splitlines() if line.startswith("pruned ")}
    assert pruned == {
        f"pruned {plugin / 'agents/gone-too/deeper/old.md'}",
        f"pruned {plugin / 'agents/gone/old.md'}",
        f"pruned {plugin / 'agents/kb-maintainer.md'}",
    }


# The overwrite refusal: an install writes over a file at a render or resource target only when that
# file carries this repository's banner for its kind, and otherwise refuses before the first write.

# A resource header as a file of the harness's own carries it, in a syntax the predicate does not parse.
_RESOURCE_HEADER = "// !INSTALLED! from elsewhere — request changes from the devpro project\n"


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


def test_a_directory_at_a_render_target_is_refused_with_nothing_written(tmp_path: Path) -> None:
    root = tmp_path / ".claude"
    target = _claude_plugin(root) / "agents/python-coder.md"
    target.mkdir(parents=True)
    (target / "inside.md").write_text("mine\n", encoding="utf-8")
    before = _files(tmp_path)
    with pytest.raises(InputError, match=re.escape(f"'{target}'")):
        _definition_install(root, project_root=tmp_path)
    assert _files(tmp_path) == before


def test_every_failing_target_is_named_in_one_refusal(tmp_path: Path) -> None:
    """Render and resource targets are collected together, so the operator clears them in one pass."""
    root = tmp_path / ".opencode"
    plugin_root = _opencode_plugin(root)
    first, second = (plugin_root.joinpath(*relative.parts) for relative, _ in render_all(_OPENCODE_RENDER)[:2])
    guardrail = plugin_root / _TS_GUARDRAIL
    for path in (first, second, guardrail):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("mine\n", encoding="utf-8")
    before = _files(tmp_path)
    with pytest.raises(InputError) as refusal:
        _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
    assert all(f"'{path}'" in str(refusal.value) for path in (first, second, guardrail))
    assert _files(tmp_path) == before


def test_a_reinstall_overwrites_its_own_renders_kb_skill_files_included(tmp_path: Path) -> None:
    """A local edit that keeps the banner is still ours: the frontmatter carrier and a supporting
    file's comment carrier each pass, and the render replaces the edit."""
    root = tmp_path / ".claude"
    root.mkdir()
    _definition_install(root, plugin=KBASE, project_root=tmp_path)
    plugin = _claude_plugin(root, KBASE)
    edited = ("agents/python-coder.md", "skills/kbase/references/reading.md")
    for relative in edited:
        with (plugin / relative).open("a", encoding="utf-8") as handle:
            handle.write("a local edit\n")
    _definition_install(root, plugin=KBASE, project_root=tmp_path)
    for relative in edited:
        assert (plugin / relative).read_text(encoding="utf-8") == _rendered(_KBASE_CLAUDE_RENDER, relative)


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
    guardrail = _opencode_plugin(root) / _TS_GUARDRAIL
    guardrail.parent.mkdir(parents=True)
    guardrail.write_text(f"{head}export const mine = 1\n", encoding="utf-8")
    source = (PACKAGE_ROOT / HARNESS_RESOURCES_SOURCE / "opencode" / _TS_GUARDRAIL).read_bytes()
    before = _files(tmp_path)
    if refused:
        with pytest.raises(InputError, match=re.escape(f"'{guardrail}'")):
            _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
        assert _files(tmp_path) == before
    else:
        _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
        assert guardrail.read_bytes() == source


def test_a_prior_installs_resource_is_overwritten(tmp_path: Path) -> None:
    root = tmp_path / ".opencode"
    root.mkdir()
    _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
    guardrail = _opencode_plugin(root) / _TS_GUARDRAIL
    with guardrail.open("a", encoding="utf-8") as handle:
        handle.write("// a local edit\n")
    _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
    assert guardrail.read_bytes() == (PACKAGE_ROOT / HARNESS_RESOURCES_SOURCE / "opencode" / _TS_GUARDRAIL).read_bytes()


def test_every_shipped_resource_carries_the_header_its_reinstall_needs(tmp_path: Path) -> None:
    """A resource without the header would refuse its own second install."""
    harnesses = load("devpro.harnesses", "HARNESS")
    sources = [source for name in harnesses for source, _ in harness_resource_copies(tmp_path, harness=name)]
    assert sources
    assert [source for source in sources if not _is_our_resource(source)] == []


# The claude guardrail hook: shipped and registered in the plugin's own `hooks/hooks.json` when one run
# of the script on this machine succeeds.


def _claude_root(project: Path) -> Path:
    """`project/.claude`, created."""
    root = project / ".claude"
    root.mkdir()
    return root


@pytest.mark.parametrize(
    "interpreter, reason",
    [("devpro-no-such-perl", "'devpro-no-such-perl' could not be run: "), ("false", "'false ")],
    ids=["missing-interpreter", "failing-run"],
)
def test_a_failed_probe_installs_everything_else_and_neither_ships_nor_registers_the_hook(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch, interpreter: str, reason: str
) -> None:
    monkeypatch.setattr("devpro.install.GUARDRAIL_INTERPRETER", interpreter)
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
    """Nothing replaces them, so the plugin's script and registration stay, each named."""
    root = _claude_root(tmp_path)
    _definition_install(root, project_root=tmp_path)
    before = _files(tmp_path)
    monkeypatch.setattr("devpro.install.GUARDRAIL_INTERPRETER", "devpro-no-such-perl")
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    after = _files(tmp_path)
    left = [_claude_plugin(root) / _GUARDRAIL, _claude_plugin(root) / _REGISTRATION]
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


def test_a_failed_probe_names_no_script_an_install_did_not_write(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _claude_root(tmp_path)
    _plant(_claude_plugin(root) / _GUARDRAIL, "print 'mine';\n")
    monkeypatch.setattr("devpro.install.GUARDRAIL_INTERPRETER", "devpro-no-such-perl")
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    [skipped] = [line for line in capsys.readouterr().err.splitlines() if line.startswith("guardrail hook skipped")]
    assert "left in place" not in skipped


def test_a_probe_that_hangs_fails_within_its_timeout(tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    slow = tmp_path / "slow-perl"
    slow.write_text("#!/usr/bin/env bash\nexec sleep 30\n", encoding="utf-8")
    slow.chmod(0o755)
    monkeypatch.setattr("devpro.install.GUARDRAIL_INTERPRETER", str(slow))
    monkeypatch.setattr("devpro.install.GUARDRAIL_PROBE_SECONDS", 0.5)
    project = tmp_path / "project"
    project.mkdir()
    root = _claude_root(project)
    capsys.readouterr()
    _definition_install(root, project_root=project)
    assert not (project / _SETTINGS).exists()
    [skipped] = [line for line in capsys.readouterr().err.splitlines() if line.startswith("guardrail hook skipped")]
    assert "did not exit within 0.5 seconds" in skipped


# The preflight: `install` and `install-agents-file` first run into a scratch copy of the paths they
# manage and compare it with the target, so an up-to-date target is left untouched and `--dry-run`
# prints the difference without writing.

_UP_TO_DATE = "up to date: "


def _state(base: Path) -> dict[str, tuple[bytes, int, int]]:
    """Every directory and file below `base`: its bytes (a directory's none), modification time and
    mode — what "touched nothing" compares."""
    state = {}
    for directory, subdirs, names in os.walk(base):
        for name in [*subdirs, *names]:
            path = Path(directory, name)
            info = path.stat()
            data = path.read_bytes() if path.is_file() else b""
            state[path.relative_to(base).as_posix()] = (data, info.st_mtime_ns, info.st_mode)
    return state


def _directories(root: Path) -> set[str]:
    """Every directory below `root`, each shown with the trailing `/` a dry run gives it."""
    return {
        f"{Path(directory, name).relative_to(root).as_posix()}/"
        for directory, subdirs, _ in os.walk(root)
        for name in subdirs
    }


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
    monkeypatch.setattr("devpro.cli.uncommitted_sources", _committed)


def _fail_if_called() -> tuple[str, ...]:
    pytest.fail("the commit state was read")


@pytest.fixture
def _uncommitted_never_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI's commit-state check failing the test if it runs: an install that writes no agents file
    has no reason to read it."""
    monkeypatch.setattr("devpro.cli.uncommitted_sources", _fail_if_called)


def _assert_dry_run_predicts(argv: list[str], *, project: Path, capsys) -> dict[str, set[str]]:
    """Run `argv` with `--dry-run`, then for real: the dry run touches nothing under `project`, and the
    paths it prints are exactly those the real run then creates, changes and removes — the directories
    it removes among them. Its groups."""
    files, directories, state = _files(project), _directories(project), _state(project)
    capsys.readouterr()
    main([*argv, "--dry-run"])
    groups = _dry_run_groups(capsys.readouterr().out)
    assert _state(project) == state
    main(argv)
    assert groups == _changed_since(files, directories, project=project)
    return groups


def _changed_since(files: dict[str, bytes], directories: set[str], *, project: Path) -> dict[str, set[str]]:
    """What changed under `project` since it held `files` and `directories`, as a dry run groups it,
    each group present only where it holds a path."""
    after = _files(project)
    actual = {
        "created": set(after) - set(files),
        "changed": {path for path in set(after) & set(files) if after[path] != files[path]},
        "removed": (set(files) - set(after)) | (directories - _directories(project)),
    }
    return {group: paths for group, paths in actual.items() if paths}


def _kb_install_with_a_runner_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], Path]:
    """The settings file and the runner include line are in play: each is already what the second run
    writes."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    return ["install", str(project), "--plugin=kbase", "--harness=claude"], project


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
    monkeypatch.setattr("devpro.install_base.REPO_ROOT", project.resolve())
    return ["install", str(project), "--plugin=kbase", "--harness=claude"], project


def _mage_below_its_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], Path]:
    """The plugin's own `.mcp.json` and agents file at ROOT."""
    project = tmp_path / "project"
    project.mkdir()
    return ["install", str(project), "--plugin=kbase", "--harness=mage", "--subdir=plugins/devpro"], project


@pytest.mark.usefixtures("_no_uncommitted")
@pytest.mark.parametrize(
    "setup",
    [
        _kb_install_with_a_runner_file,
        _agents_file_in_a_project,
        _the_repository_as_project,
        _mage_below_its_project,
    ],
    ids=["kb-runner-file", "agents-file", "repository-project", "mage-subdir"],
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


def test_a_changed_plugin_installs(tmp_path: Path, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    argv = [str(project), "--harness=claude"]
    main(["install", *argv])
    files = _files(project)
    capsys.readouterr()
    main(["install", *argv, "--plugin=kbase"])
    assert _UP_TO_DATE not in capsys.readouterr().out
    assert _files(project) != files


@pytest.mark.usefixtures("_no_uncommitted")
@pytest.mark.parametrize("plugin", ["devpro", "kbase"])
@pytest.mark.parametrize(
    "harness_args",
    [
        ["--harness=claude"],
        ["--harness=opencode"],
        ["--harness=mage", "--subdir=plugins/plugin"],
    ],
    ids=["claude", "opencode", "mage-subdir"],
)
def test_a_dry_run_on_a_fresh_target_lists_as_created_what_the_install_creates(
    tmp_path: Path, capsys, harness_args: list[str], plugin: str
) -> None:
    """The project's runner file is in play too: under a kbase install it gains the include line, so it
    is listed as changed."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    groups = _assert_dry_run_predicts(
        ["install", str(project), f"--plugin={plugin}", *harness_args], project=project, capsys=capsys
    )
    assert groups["created"]


@pytest.mark.usefixtures("_uncommitted_never_read")
@pytest.mark.parametrize(
    ("harness", "ships_kbase"),
    [(CLAUDE, True), (OPENCODE, False)],
    ids=["claude", "opencode"],
)
def test_a_dry_run_of_a_user_level_kbase_install_predicts_the_install(
    tmp_path: Path, capsys, harness: Harness, ships_kbase: bool
) -> None:
    """A user-level kbase install renders `.mcp.json` where the harness renders one: claude's, beside its
    plugin's manifest; opencode carries the entry in its registry instead."""
    home = tmp_path / "home"
    harness.user_dir.mkdir(parents=True)
    argv = ["install", str(home), "--plugin=kbase", f"--harness={harness.name}"]
    groups = _assert_dry_run_predicts(argv, project=home, capsys=capsys)
    assert any(PurePosixPath(path).name == ".mcp.json" for path in groups["created"]) is ships_kbase


def test_a_dry_run_after_a_family_change_lists_the_renders_as_changed(tmp_path: Path, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    argv = ["install", str(project), "--harness=opencode"]
    main([*argv, "--family=gemma-4"])
    groups = _assert_dry_run_predicts([*argv, "--family=qwen3"], project=project, capsys=capsys)
    assert groups["changed"] and set(groups) == {"changed"}


def test_a_dry_run_lists_a_stale_render_as_removed(tmp_path: Path, capsys) -> None:
    project = tmp_path / "project"
    root = project / ".claude"
    root.mkdir(parents=True)
    argv = ["install", str(project), "--harness=claude"]
    main(argv)
    (_claude_plugin(root) / "agents/gone.md").write_text(_NEW_BANNER, encoding="utf-8")
    groups = _assert_dry_run_predicts(argv, project=project, capsys=capsys)
    assert groups == {"removed": {f"{_CLAUDE_PLUGIN_RELPATH}/agents/gone.md"}}


@pytest.mark.usefixtures("_no_uncommitted")
@pytest.mark.parametrize(
    "argv",
    [
        ["install", "{project}", "--harness=claude"],
        ["install-agents-file", "{project}", "--harness=claude"],
    ],
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


# The claude plugin: a user-level plugin shadowing a project's is reported.


def _user_level_plugin(home: Path) -> Path:
    """A user-level claude plugin installed under `home`: its manifest's path."""
    root = home / ".claude"
    root.mkdir(parents=True)
    install(root, _CLAUDE_RENDER, verbose=False, project_root=home, uncommitted=_committed)
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
    _plant(_claude_plugin(_home / ".claude") / ".claude-plugin/plugin.json", '{"name": "other"}\n')
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
    return ("M devpro/x.py",)


@pytest.mark.parametrize("uncommitted", [False, True], ids=["committed", "uncommitted"])
@pytest.mark.parametrize("name, redirect", [("claude", True), ("opencode", False)], ids=["claude", "opencode"])
def test_without_a_global_block_a_project_install_keeps_it_in_the_projects_agents_md(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, redirect: bool, uncommitted: bool
) -> None:
    """The global file holds no block, so its text is not touched, and the commit state is not read."""
    monkeypatch.setattr("devpro.cli.uncommitted_sources", _dirty if uncommitted else _committed)
    harness = _HARNESS_NAMED[name]
    _plant(_global_agents_file(tmp_path / "home", harness), "# my global rules\n")
    project = tmp_path / "project"
    project.mkdir()
    main(["install", str(project), f"--harness={name}"])
    rendered = render_agents_file(harness, DEVPRO, scope=project.name).encode()
    top = {path: data for path, data in _files(project).items() if "/" not in path and path != "Makefile"}
    assert top == {"AGENTS.md": rendered, **({"CLAUDE.md": b"@AGENTS.md\n"} if redirect else {})}
    assert _global_agents_file(tmp_path / "home", harness).read_text(encoding="utf-8") == "# my global rules\n"


def test_on_the_fallback_a_claude_redirect_is_left_and_the_block_appended(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _plant(project / "CLAUDE.md", "@AGENTS.md\n")
    _plant(project / "AGENTS.md", "# mine\n")
    main(["install", str(project), "--harness=claude"])
    assert (project / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"
    assert (project / "AGENTS.md").read_text(encoding="utf-8") == "\n".join(["# mine", "", *_block(CLAUDE), ""])


def test_on_the_fallback_a_claude_native_file_with_its_own_content_refuses_the_install(tmp_path: Path, capsys) -> None:
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
    assert f"removed the devpro block from {project / 'AGENTS.md'}" in out
    assert (None if native is None else (project / "CLAUDE.md").read_text(encoding="utf-8")) == native
    assert native is not None or not (project / "CLAUDE.md").exists()


@pytest.mark.usefixtures("_no_uncommitted")
def test_once_the_global_file_holds_the_block_every_project_install_keeps_it_there(tmp_path: Path, capsys) -> None:
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


@pytest.mark.usefixtures("_no_uncommitted")
def test_a_global_block_is_kept_current_as_the_plugin_its_marker_names(tmp_path: Path) -> None:
    """A devpro project install under a global kbase block keeps kbase's block there, and writes no
    project block."""
    kbase_begin = " <!-- vvv-devpro kbase 0.0.1 do not edit at or between marker lines. devpro-vvv -->"
    global_file = _plant(_global_agents_file(tmp_path / "home", CLAUDE), f"{kbase_begin}\nold\n{_END}\n")
    project = tmp_path / "project"
    project.mkdir()
    main(["install", str(project), "--harness=claude"])
    lines, begin, end = marker_span(render_agents_file(CLAUDE, KBASE, scope="x"), where="render")
    assert global_file.read_text(encoding="utf-8") == "\n".join([*lines[begin : end + 1], ""])
    assert f"vvv-devpro kbase {__version__} " in lines[begin]
    assert not (project / "AGENTS.md").exists() and not (project / "CLAUDE.md").exists()


def test_the_global_write_under_uncommitted_sources_is_refused_with_nothing_written(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("devpro.cli.uncommitted_sources", _dirty)
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


# What stands on a path the install writes is met as it stands: an obstacle the operating system
# reports ends the run as an error, and a dry run ends the same way.


def _run_outcome(argv: list[str], capsys, *, planted: Path) -> tuple[object, list[str], dict[str, set[str]]]:
    """What a run of `argv` does about `planted`: its exit code, the stderr lines naming it, and the
    paths a dry run prints."""
    capsys.readouterr()
    try:
        main(argv)
        code: object = 0
    except SystemExit as exc:
        code = exc.code
    printed = capsys.readouterr()
    return code, [line for line in printed.err.splitlines() if str(planted) in line], _dry_run_groups(printed.out)


@pytest.mark.parametrize(
    "plugin, harness_args, planted",
    [
        ("devpro", ["--harness=claude"], f"{_CLAUDE_PLUGIN_RELPATH}/agents"),
        ("kbase", ["--harness=opencode", "--subdir=tools"], "tools/plugins/kbase/registry.json"),
        ("devpro", ["--harness=claude"], _CLAUDE_PLUGIN_RELPATH),
    ],
    ids=["render-target", "registry-target", "install-directory"],
)
def test_a_dry_run_foresees_a_file_on_the_way(
    tmp_path: Path, capsys, plugin: str, harness_args: list[str], planted: str
) -> None:
    project = tmp_path / "project"
    (project / "tools").mkdir(parents=True)
    path = _plant(project / planted, "mine\n")
    argv = ["install", str(project), f"--plugin={plugin}", *harness_args]
    files, directories = _files(project), _directories(project)
    dry_code, dry_lines, groups = _run_outcome([*argv, "--dry-run"], capsys, planted=path)
    real_code, real_lines, _ = _run_outcome(argv, capsys, planted=path)
    assert (dry_code, dry_lines) == (real_code, real_lines)
    assert groups == _changed_since(files, directories, project=project)


def test_a_file_at_a_package_destination_is_replaced_by_the_package(tmp_path: Path, capsys) -> None:
    project, root = _claude_project(tmp_path)
    tools = _plant(root / _DOCDICER_TOOLS)
    _assert_dry_run_predicts(["install", str(project), "--harness=claude"], project=project, capsys=capsys)
    assert (tools / "docdicer").is_file()
