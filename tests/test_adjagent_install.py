"""The agents-file render and installer, and the definition install, each case checked against values
the code under test did not compute: the marker span, the bytes kept outside it, the refusals that
write nothing, the redirects, the kb-tools package and its banner, the kb install path, the MCP
settings merge, the runner include line, the harness resources a harness ships as they stand, the
prune, the refusal to overwrite a file without this repository's banner, and the claude guardrail
hook's probe and settings merge.

The package is imported from the repository root, which `just test` puts on PYTHONPATH.
"""

import dataclasses
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import cast

import pytest

from adjagent.agents_file import install_agents_file, marker_span, scope_name
from adjagent.cli import main
from adjagent.context import Render, build_render
from adjagent.definition import Definition
from adjagent.errors import InputError
from adjagent.families.claude import FAMILY as CLAUDE_FAMILY
from adjagent.harness import Harness
from adjagent.harnesses.claude import HARNESS as CLAUDE
from adjagent.harnesses.mage import HARNESS as MAGE
from adjagent.harnesses.opencode import HARNESS as OPENCODE
from adjagent.install import (
    HARNESS_RESOURCES_SOURCE,
    KBASE_NAME,
    REPO_ROOT,
    _is_our_resource,
    _named_harnesses,
    excluded,
    harness_resource_copies,
    install,
    install_kb_include_line,
)
from adjagent.loading import load
from adjagent.render import definitions, filled_body, render_agents_file, render_all, render_definition
from adjagent.version import VERSION
from adjagent.vocabulary import Kind

_BEGIN = " <!-- vvv-adjagent do not edit at or between marker lines. adjagent-vvv -->"
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


@pytest.mark.parametrize("harness", [CLAUDE, OPENCODE], ids=lambda harness: harness.name)
def test_the_fresh_render_cites_the_medium_member_under_claude_only(harness: Harness) -> None:
    user_dir = Path(harness.user_harness_dir).expanduser()
    text = render_agents_file(harness, scope=scope_name(harness, user_dir))
    lines, begin, end = marker_span(text, where="render")
    assert (lines[0], lines[begin], lines[end]) == ("# Global info and directives", _BEGIN, _END)
    if harness is CLAUDE:
        assert "`model: sonnet`" in text
        assert "Coder dispatches" in text
    else:
        assert "`model: sonnet`" not in text
        assert "Coder dispatches" not in text
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
        ("# mine\n\nno markers\n", "found 0 begin and 0 end"),
        (f"{_BEGIN}\n{_BEGIN}\n{_END}\n", "found 2 begin and 1 end"),
        (f"{_END}\n{_BEGIN}\n", "found 1 begin and 1 end"),
    ],
)
def test_a_file_without_one_ordered_marker_pair_is_refused(tmp_path: Path, prior: str, message: str) -> None:
    (tmp_path / "AGENTS.md").write_text(prior, encoding="utf-8")
    with pytest.raises(InputError, match=message):
        _install(tmp_path)
    assert _files(tmp_path) == {"AGENTS.md": prior.encode()}


def _symlink_destination(tmp_path: Path) -> None:
    (tmp_path / "real.md").write_text(f"{_BEGIN}\n{_END}\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").symlink_to("real.md")


def _symlink_backup(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text(f"{_BEGIN}\n{_END}\n", encoding="utf-8")
    (tmp_path / "elsewhere.md").write_text("x", encoding="utf-8")
    (tmp_path / "backup.AGENTS.md").symlink_to("elsewhere.md")


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
        (_symlink_destination, ".", "AGENTS.md is a symlink or not a regular file"),
        (_symlink_backup, ".", "backup.AGENTS.md is a symlink or not a regular file"),
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


def test_uncommitted_sources_refuse_the_install(tmp_path: Path) -> None:
    with pytest.raises(InputError, match=re.escape("has uncommitted changes (?? adjagent/x.py)")):
        _install(tmp_path, uncommitted=("?? adjagent/x.py",))
    assert _files(tmp_path) == {}


def test_a_project_directory_under_claude_writes_agents_md_and_the_redirect(tmp_path: Path) -> None:
    _install(tmp_path, CLAUDE)
    assert _files(tmp_path) == {
        "AGENTS.md": render_agents_file(CLAUDE, scope=tmp_path.name).encode(),
        "CLAUDE.md": b"@AGENTS.md\n",
    }
    assert render_agents_file(CLAUDE, scope=tmp_path.name).startswith(f"# {tmp_path.name} info and directives\n")


def test_this_repositorys_claude_redirect_is_followed_and_left_alone(tmp_path: Path) -> None:
    """This repository's own pair: CLAUDE.md is `@AGENTS.md`, and AGENTS.md is the operator's text
    with no block, refused until the operator places a marker pair in it."""
    redirect = (REPO_ROOT / "CLAUDE.md").read_bytes()
    own = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert redirect == b"@AGENTS.md\n" and _BEGIN not in own
    (tmp_path / "CLAUDE.md").write_bytes(redirect)
    (tmp_path / "AGENTS.md").write_text(own, encoding="utf-8")
    with pytest.raises(InputError, match="AGENTS.md: found 0 begin and 0 end"):
        _install(tmp_path, CLAUDE)
    (tmp_path / "AGENTS.md").write_text(f"{own}\n{_BEGIN}\n{_END}\n", encoding="utf-8")
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
    install(root, ctx, verbose=False, with_kb=with_kb, project_root=project_root)


# The harness resources: the files a harness ships for its own harness directory, copied into ROOT as
# they stand. A harness that ships none copies nothing.

_PLUGIN = "plugins/guardrail.ts"
_GUARDRAIL = "hooks/guardrail.pl"
_SETTINGS = ".claude/settings.json"


def _hook_entry(harness_relpath: str) -> dict:
    """The PreToolUse entry an install whose harness directory is `harness_relpath` writes. What the
    command does is pinned by running it (`test_the_registered_command_...`), not by its spelling."""
    assert CLAUDE.guardrail is not None
    return CLAUDE.guardrail.entry(harness_relpath)


def test_an_opencode_install_copies_the_harnesss_plugin_byte_verbatim(tmp_path: Path) -> None:
    """The opencode plugin is the harness's own file, not this repository's generated product: it lands
    under ROOT byte for byte, so a stamp anywhere in the copy would show as a difference from the
    source."""
    root = tmp_path / ".opencode"
    root.mkdir()
    _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
    copied = root / _PLUGIN
    assert copied.read_bytes() == (REPO_ROOT / HARNESS_RESOURCES_SOURCE / "opencode" / _PLUGIN).read_bytes()


def test_a_fresh_claude_install_ships_the_guardrail_and_registers_it_in_a_new_settings_file(tmp_path: Path) -> None:
    """Where the probe passes, the hook script lands byte-verbatim and executable under ROOT, and the
    project gains `.claude/settings.json` holding the one entry that runs it."""
    root = tmp_path / ".claude"
    root.mkdir()
    _definition_install(root, project_root=tmp_path)
    copied = root / _GUARDRAIL
    assert copied.read_bytes() == (REPO_ROOT / HARNESS_RESOURCES_SOURCE / "claude" / _GUARDRAIL).read_bytes()
    assert os.access(copied, os.X_OK)
    assert json.loads((tmp_path / _SETTINGS).read_text(encoding="utf-8")) == {
        "hooks": {"PreToolUse": [_hook_entry(".claude")]}
    }


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
    monkeypatch.setattr("adjagent.install.REPO_ROOT", tmp_path / "repo")
    root = tmp_path / ".probe"
    copies = harness_resource_copies(root, harness="probe")
    assert [target.relative_to(root).as_posix() for _, target in copies] == ["plugins/keep.ts"]


def test_the_resources_tree_is_not_read_as_a_harness_module() -> None:
    """`resources/` holds no `__init__.py`, so `pkgutil` lists it as a tree rather than a module and
    `load` returns every harness module. A `resources` package appearing later would break that, so the
    same case pins the tree's presence: a resource tree that went missing fails here too, rather than
    the plugin copy silently landing nothing."""
    assert sorted(load("adjagent.harnesses", "HARNESS")) == ["claude", "mage", "opencode"]
    assert (REPO_ROOT / HARNESS_RESOURCES_SOURCE / "opencode").is_dir()


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
    files = _files(root)
    assert "agents/python-coder.md" in files
    for relative in (
        *_KB_DEFINITIONS,
        *_KB_SKILL_FILES,
        "skills/kbase/kb-tools/runner-snippets/kb.just",
    ):
        assert relative not in files
    assert not (root / "skills").exists()
    assert not (project / ".mcp.json").exists()
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
    for relative in (*_KB_DEFINITIONS, *_KB_SKILL_FILES):
        assert (root / relative).is_file()
    kb_just = (root / "skills/kbase/kb-tools/runner-snippets/kb.just").read_text(encoding="utf-8").split("\n")
    source_just = (REPO_ROOT / "kb-tools/runner-snippets/kb.just").read_text(encoding="utf-8").split("\n")
    kb_mk = (root / "skills/kbase/kb-tools/runner-snippets/kb.mk").read_text(encoding="utf-8").split("\n")
    assert kb_just[0].startswith("# !INSTALLED! from kb-tools/runner-snippets/kb.just — ")
    assert kb_just[1:] == source_just
    assert kb_mk[0].startswith("# !INSTALLED! from kb-tools/runner-snippets/kb.mk — ")
    assert json.loads((project / ".mcp.json").read_text(encoding="utf-8")) == {
        "mcpServers": {"kbase": {"command": "kbase", "args": ["mcp"]}}
    }
    assert (project / "justfile").read_text(encoding="utf-8") == (
        "# mine\n\nimport? '.claude/skills/kbase/kb-tools/runner-snippets/kb.just'\n"
    )
    captured = capsys.readouterr()
    assert f"wrote {project / '.mcp.json'} with the kbase MCP entry" in captured.out
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
    after = _files(root)
    for relative in (*_KB_DEFINITIONS, *_KB_SKILL_FILES, "skills/kbase/kb-tools/runner-snippets/kb.just"):
        assert relative in after


def test_a_sticky_install_removes_the_executable_an_earlier_version_installed(tmp_path: Path) -> None:
    """A root the router makes a kb install, still holding the `kbase` executable and its signature an
    earlier version placed in kb-tools/, loses both — the destination is replaced whole — and its MCP
    entry names the bare command rather than the installed executable."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    _definition_install(root, with_kb=True, project_root=project)
    executable = root / "skills/kbase/kb-tools/kbase"
    executable.write_bytes(_KBASE_BYTES)
    signature = executable.with_name("kbase.asc")
    signature.write_bytes(b"-----BEGIN PGP SIGNATURE-----\n")
    (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"kbase": {"command": ".claude/skills/kbase/kb-tools/kbase", "args": ["mcp"]}}}),
        encoding="utf-8",
    )
    _definition_install(root, project_root=project)
    assert not executable.exists() and not signature.exists()
    assert (root / "skills/kbase/kb-tools/runner-snippets/kb.just").is_file()
    settings = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
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
    snippets = root / "skills/kbase/kb-tools/runner-snippets"
    snippets.mkdir(parents=True)
    (snippets / "kb.just").write_text("# stale snippet\n", encoding="utf-8")
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    _definition_install(root, project_root=project)
    files = _files(root)
    for relative in (*_KB_DEFINITIONS, *_KB_SKILL_FILES):
        assert relative not in files
    assert (snippets / "kb.just").read_text(encoding="utf-8") == "# stale snippet\n"
    assert not (project / ".mcp.json").exists()
    assert (project / "justfile").read_text(encoding="utf-8") == "# mine\n"


def test_the_version_verb_prints_the_constant_and_nothing_else(capsys) -> None:
    """A recipe parses this line to cut the tag, so it is the constant alone: no `v`, no suffix, no
    prose, one line — and the constant carries that shape, which a manifest would inherit too."""
    main(["version"])
    assert capsys.readouterr().out == f"{VERSION}\n"
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION)


def test_the_cli_with_kb_flag_installs_the_kb_skill_files_and_the_skill_kb_tools_destination(
    tmp_path: Path,
) -> None:
    """`--with-kb` reaches `install()`: driven through the CLI entry point, the flag's own effect —
    the kbase skill's files and the runner snippets — is what appears under ROOT."""
    root = tmp_path / ".claude"
    root.mkdir()
    main(["install", str(root), "--harness=claude", "--with-kb"])
    assert all((root / relative).is_file() for relative in _KB_SKILL_FILES)
    snippets = root / "skills/kbase/kb-tools/runner-snippets"
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
    references = root / "skills/kbase/references"
    references.mkdir(parents=True)
    stale = references / "gone.md"
    stale.write_text(f"{_COMMENT_BANNER}\n\nold text\n", encoding="utf-8")
    mine = root / "skills/kbase/notes.md"
    mine.write_text("---\nmine\n---\n", encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, with_kb=True, project_root=tmp_path)
    assert not stale.exists()
    assert mine.read_text(encoding="utf-8") == "---\nmine\n---\n"
    assert all((root / relative).is_file() for relative in _KB_SKILL_FILES)
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
    root.mkdir()
    (project / ".mcp.json").write_text(
        json.dumps(
            {
                "permissions": {"allow": ["Bash"]},
                "mcpServers": {
                    "other": {"command": "x"},
                    "kbase": {"command": ".claude/skills/kbase/kb-tools/kbase", "args": ["mcp"]},
                },
            }
        ),
        encoding="utf-8",
    )
    _definition_install(root, with_kb=True, project_root=project)
    data = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
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
            ".mcp.json",
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
    holds no `.mcp.json` at all — and the manifest is still the three-key one carrying VERSION. No
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
    assert manifest["version"] == VERSION
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
    install(root, _MAGE_RENDER, verbose=True, project_root=project)
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
    assert f"{discovered} carries JSONC comments — left untouched; merge this entry by hand:" in capsys.readouterr().out


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
    root.mkdir()
    seed = (
        "{\n"
        '    "permissions": {"allow": ["Bash", "Read"], "deny": []},\n'
        '    "mcpServers": {\n'
        '        "other": {"command": "x", "args": [1, 2.50, true]}\n'
        "    },\n"
        '    "theme": "dark"\n'
        "}\n"
    )
    (project / ".mcp.json").write_text(seed, encoding="utf-8")
    _definition_install(root, with_kb=True, project_root=project)
    text = (project / ".mcp.json").read_text(encoding="utf-8")
    head, other, tail = seed.partition('"other": {"command": "x", "args": [1, 2.50, true]}')
    assert other and text.startswith(head) and text.endswith(tail)
    before = json.loads(seed)
    before["mcpServers"]["kbase"] = _built_entry(CLAUDE)
    assert json.loads(text) == before


def test_a_compact_one_line_mcp_file_gains_the_entry_inline(tmp_path: Path) -> None:
    """The file states no indent, so none is invented: the entry goes in on the line it finds."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    (project / ".mcp.json").write_text('{"mcpServers": {}}', encoding="utf-8")
    _definition_install(root, with_kb=True, project_root=project)
    text = (project / ".mcp.json").read_text(encoding="utf-8")
    assert "\n" not in text
    assert json.loads(text) == {"mcpServers": {"kbase": _built_entry(CLAUDE)}}


def test_a_settings_file_without_the_container_gains_it_whole(tmp_path: Path) -> None:
    """`mcpServers` absent is not a reason to reserialize: the container goes in as one member, on a
    line indented like the sibling it lands beside."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    seed = '{\n  "permissions": {"allow": ["Bash"]}\n}\n'
    (project / ".mcp.json").write_text(seed, encoding="utf-8")
    _definition_install(root, with_kb=True, project_root=project)
    text = (project / ".mcp.json").read_text(encoding="utf-8")
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
    root.mkdir()
    prior = '{"command": "/old/absolute/kbase", "args": ["mcp", "--kb-root", "/old"]}'
    seed = f'{{\n  "mcpServers": {{\n    "kbase": {prior},\n    "other": {{"command": "x"}}\n  }}\n}}\n'
    (project / ".mcp.json").write_text(seed, encoding="utf-8")
    _definition_install(root, with_kb=True, project_root=project)
    text = (project / ".mcp.json").read_text(encoding="utf-8")
    head, found, tail = seed.partition(prior)
    assert found and text.startswith(head) and text.endswith(tail)
    assert json.loads(text)["mcpServers"] == {"kbase": _built_entry(CLAUDE), "other": {"command": "x"}}


def test_a_crlf_mcp_file_keeps_its_line_endings(tmp_path: Path) -> None:
    """Byte reading and writing with no newline translation, and the entry's own lines take the file's
    ending: a CRLF file stays CRLF through the merge."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    seed = '{\r\n  "mcpServers": {\r\n  }\r\n}\r\n'
    (project / ".mcp.json").write_bytes(seed.encode("utf-8"))
    _definition_install(root, with_kb=True, project_root=project)
    raw = (project / ".mcp.json").read_bytes()
    assert b"\n" not in raw.replace(b"\r\n", b"")
    assert json.loads(raw.decode("utf-8")) == {"mcpServers": {"kbase": _built_entry(CLAUDE)}}


def test_a_duplicate_container_key_is_reported_and_left_byte_identical(tmp_path: Path, capsys) -> None:
    """The file names `mcpServers` twice, so the splice cannot say which one is meant: it reports and
    writes nothing — the install still succeeded — rather than picking one."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    seed = '{"mcpServers": {"other": {"command": "x"}}, "mcpServers": {}}\n'
    (project / ".mcp.json").write_text(seed, encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, with_kb=True, project_root=project)
    assert (project / ".mcp.json").read_text(encoding="utf-8") == seed
    out = capsys.readouterr().out
    entry = _built_entry(CLAUDE)
    assert f"{project / '.mcp.json'} could not be edited safely — left untouched; merge this entry by hand:" in out
    assert json.dumps(entry) in out


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
        "default:\n  @echo hi\n\nimport? '.claude/skills/kbase/kb-tools/runner-snippets/kb.just'\n"
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
    out = capsys.readouterr().out
    assert "no include line written" in out and "'claude'" in out


@pytest.mark.parametrize(
    "snippets_path",
    [
        "agents/kb-tools/runner-snippets",
        "agents/kb_tools/runner-snippets",
        "adj-tools/kb-tools/runner-snippets",
        "custom/kb-tools/runner-snippets",
        "kb-tools/runner-snippets",
    ],
    ids=["hyphen", "underscore", "adj-tools", "hand-written", "short-tree"],
)
def test_an_include_line_for_this_harness_under_any_tree_is_rewritten_in_place(
    tmp_path: Path, capsys, snippets_path: str
) -> None:
    """A line naming this harness is this harness's line whatever tree its path spells — a legacy
    destination's, or one no release here wrote — so it is replaced where it stands and the file keeps
    one include line rather than gaining a second beside a dead one."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    (project / "justfile").write_text(f"default:\n  @echo hi\n\nimport? '.claude/{snippets_path}/kb.just'\n")
    capsys.readouterr()
    _definition_install(root, with_kb=True, project_root=project)
    text = (project / "justfile").read_text(encoding="utf-8")
    assert text == "default:\n  @echo hi\n\nimport? '.claude/skills/kbase/kb-tools/runner-snippets/kb.just'\n"
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
    out = capsys.readouterr().out
    assert "no include line written" in out and "'claude'" in out


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
    assert "names the kb snippets on lines 1, 2" in capsys.readouterr().out


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
    [REPO_ROOT, REPO_ROOT / "kb-tools", REPO_ROOT / HARNESS_RESOURCES_SOURCE / "opencode"],
    ids=["repository", "kb-tools-source", "harness-resources-source"],
)
def test_install_refuses_the_repository_and_a_source_it_copies_from(root: Path) -> None:
    """Every tree a later install reads from is refused as a root: the repository itself, the kb
    toolchain's package, and a harness's resources — writes there would land inside this run's own
    input."""
    with pytest.raises(InputError, match="is this repository or inside a source it copies from"):
        install(root, _CLAUDE_RENDER, verbose=False)
    assert not (root / "agents" / "python-coder.md").exists() and not (root / "commands").exists()


def test_a_shipped_package_copies_stamped_executable_and_replaces_its_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`SHIPPED_PACKAGES` is empty while no package ships, and the machinery stays because one is
    expected to return. A restored row over a temporary source is the only thing that exercises it:
    the package copies with the `!INSTALLED!` banner below the shebang, keeps the executable bit,
    leaves its tests and project documents behind, replaces the destination whole — a stale file under
    it is gone — and a root inside its own source is refused with nothing written."""
    repo = tmp_path / "repo"
    package = repo / "probe_pkg"
    (package / "tests").mkdir(parents=True)
    tool = package / "tool.py"
    tool.write_text("#!/usr/bin/env python3\nprint('probe')\n", encoding="utf-8")
    tool.chmod(0o755)
    (package / "tests/test_tool.py").write_text("pass\n", encoding="utf-8")
    (package / "SPEC.md").write_text("# probe\n", encoding="utf-8")
    monkeypatch.setattr("adjagent.install.REPO_ROOT", repo)
    monkeypatch.setattr("adjagent.install.SHIPPED_PACKAGES", (("probe_pkg", "adj-tools/probe_pkg"),))
    project = tmp_path / "project"
    root = project / ".claude"
    stale = root / "adj-tools/probe_pkg/stale.py"
    stale.parent.mkdir(parents=True)
    stale.write_text("x = 1\n", encoding="utf-8")
    install(root, _CLAUDE_RENDER, verbose=False, project_root=project)
    copied = root / "adj-tools/probe_pkg/tool.py"
    lines = copied.read_text(encoding="utf-8").split("\n")
    assert lines[0] == "#!/usr/bin/env python3"
    assert lines[1].startswith("# !INSTALLED! from probe_pkg/tool.py — ")
    assert lines[2:] == ["print('probe')", ""]
    assert os.access(copied, os.X_OK)
    assert not (root / "adj-tools/probe_pkg/tests").exists()
    assert not (root / "adj-tools/probe_pkg/SPEC.md").exists()
    assert not stale.exists()
    before = _files(tmp_path)
    with pytest.raises(InputError, match="is this repository or inside a source it copies from"):
        install(package, _CLAUDE_RENDER, verbose=False)
    assert _files(tmp_path) == before


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A consumer root installed with kb included: the whole product plus the kb-tools package."""
    project = tmp_path_factory.mktemp("consumer")
    root = project / ".claude"
    root.mkdir()
    install(root, _CLAUDE_RENDER, verbose=False, with_kb=True, project_root=project)
    return root


def test_install_writes_every_render_and_stamps_the_packages_once(installed: Path) -> None:
    assert all((installed / path).is_file() for path, _ in render_all(_CLAUDE_RENDER))
    kb_mk = (installed / "skills/kbase/kb-tools/runner-snippets/kb.mk").read_text(encoding="utf-8").split("\n")
    source_mk = (REPO_ROOT / "kb-tools/runner-snippets/kb.mk").read_text(encoding="utf-8").split("\n")
    assert kb_mk[0].startswith("# !INSTALLED! from kb-tools/runner-snippets/kb.mk — ")
    assert kb_mk[1:] == source_mk


def test_reinstall_prunes_only_our_stale_definitions(tmp_path: Path, capsys) -> None:
    install(tmp_path, _CLAUDE_RENDER, verbose=False)
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
    install(tmp_path, _CLAUDE_RENDER, verbose=False)
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
    mine = root / "agents/python-coder.md"
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
    target = root / "agents/python-coder.md"
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
    edited = ("agents/python-coder.md", "skills/kbase/references/reading.md")
    for relative in edited:
        with (root / relative).open("a", encoding="utf-8") as handle:
            handle.write("a local edit\n")
    _definition_install(root, with_kb=True, project_root=tmp_path)
    for relative in edited:
        assert (root / relative).read_text(encoding="utf-8") == _rendered(_CLAUDE_RENDER, relative)


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
    source = (REPO_ROOT / HARNESS_RESOURCES_SOURCE / "opencode" / _PLUGIN).read_bytes()
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
    assert plugin.read_bytes() == (REPO_ROOT / HARNESS_RESOURCES_SOURCE / "opencode" / _PLUGIN).read_bytes()


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
    root.mkdir()
    (tmp_path / ".mcp.json").write_bytes(settings)
    before = _files(tmp_path)
    with pytest.raises(InputError, match=re.escape(message)):
        _definition_install(root, with_kb=True, project_root=tmp_path)
    assert _files(tmp_path) == before


# The claude guardrail hook: shipped and registered in the project's `.claude/settings.json` when one
# run of the script on this machine succeeds, every byte of that file outside our entry kept.

# A hook the project registered itself, which no install may touch.
_SED_HOOK = '{"matcher": "Bash", "hooks": [{"type": "command", "command": "./block-sed.sh"}]}'
_BY_HAND = "left untouched; merge this entry by hand:"


def _claude_root(project: Path, settings: str | bytes | None = None) -> Path:
    """`project/.claude`, created, with `settings` planted as its settings file where given."""
    root = project / ".claude"
    root.mkdir()
    if settings is not None:
        data = settings if isinstance(settings, bytes) else settings.encode("utf-8")
        (project / _SETTINGS).write_bytes(data)
    return root


def test_an_existing_settings_file_gains_the_entry_beside_the_projects_own_hook(tmp_path: Path) -> None:
    """Our entry is appended after the project's `sed` hook at its indent and line ending; every other
    byte — other keys, the project's hook, CRLF endings — is kept."""
    head = f'{{\r\n  "permissions": {{"allow": ["Bash"]}},\r\n  "hooks": {{\r\n    "PreToolUse": [\r\n      {_SED_HOOK}'
    tail = '\r\n    ]\r\n  },\r\n  "model": "opus"\r\n}\r\n'
    root = _claude_root(tmp_path, head + tail)
    _definition_install(root, project_root=tmp_path)
    raw = (tmp_path / _SETTINGS).read_bytes()
    assert raw.startswith(head.encode()) and raw.endswith(tail.encode())
    assert b"\n" not in raw.replace(b"\r\n", b"")
    assert json.loads(raw) == {
        "permissions": {"allow": ["Bash"]},
        "hooks": {"PreToolUse": [json.loads(_SED_HOOK), _hook_entry(".claude")]},
        "model": "opus",
    }


def test_a_reinstall_replaces_our_entry_in_place_and_a_second_changes_no_byte(tmp_path: Path, capsys) -> None:
    """The entry a `--subdir=a` install wrote is ours, though it names another harness directory: one
    guardrail per project, so this install's entry replaces it where it stands, ahead of the project's
    hook, and the next install finds nothing to change."""
    head = '{\n  "hooks": {\n    "PreToolUse": [\n      '
    tail = f",\n      {_SED_HOOK}\n    ]\n  }}\n}}\n"
    root = _claude_root(tmp_path, head + json.dumps(_hook_entry("a")) + tail)
    _definition_install(root, project_root=tmp_path)
    settings = tmp_path / _SETTINGS
    first = settings.read_text(encoding="utf-8")
    assert first.startswith(head) and first.endswith(tail)
    assert json.loads(first)["hooks"]["PreToolUse"] == [_hook_entry(".claude"), json.loads(_SED_HOOK)]
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    assert settings.read_text(encoding="utf-8") == first
    assert f"{settings} already registers the guardrail hook" in capsys.readouterr().out


@pytest.mark.parametrize(
    "pre_tool_use",
    [
        [_hook_entry("a"), _hook_entry(".claude")],
        [{"matcher": "Bash", "hooks": [*_hook_entry(".claude")["hooks"], *json.loads(_SED_HOOK)["hooks"]]}],
    ],
    ids=["two-entries", "beside-the-projects-own"],
)
def test_settings_naming_our_command_ambiguously_are_reported_and_left_untouched(
    tmp_path: Path, capsys, pre_tool_use: list
) -> None:
    """Replacing either of two entries leaves the other, and replacing an entry that also runs the
    project's hook deletes it, so the operator merges by hand."""
    seed = json.dumps({"hooks": {"PreToolUse": pre_tool_use}}, indent=2) + "\n"
    root = _claude_root(tmp_path, seed)
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    assert (tmp_path / _SETTINGS).read_text(encoding="utf-8") == seed
    out = capsys.readouterr().out
    assert _BY_HAND in out and json.dumps(_hook_entry(".claude")) in out


def test_jsonc_settings_are_reported_and_left_untouched(tmp_path: Path, capsys) -> None:
    seed = '{\n  // mine\n  "hooks": {}\n}\n'
    root = _claude_root(tmp_path, seed)
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    assert (tmp_path / _SETTINGS).read_text(encoding="utf-8") == seed
    assert f"{tmp_path / _SETTINGS} is not a plain JSON object — {_BY_HAND}" in capsys.readouterr().out


@pytest.mark.parametrize(
    "settings, message",
    [
        (b"\xff\xfe{}\n", "is not readable UTF-8 text"),
        (b'{"hooks": []}\n', "holds a 'hooks' that is not an object"),
        (b'{"hooks": {"PreToolUse": {}}}\n', "holds a 'hooks.PreToolUse' that is not an array"),
    ],
    ids=["non-utf8", "non-object-hooks", "non-array-pre-tool-use"],
)
def test_guardrail_settings_the_merge_cannot_use_are_refused_before_the_first_write(
    tmp_path: Path, settings: bytes, message: str
) -> None:
    root = _claude_root(tmp_path, settings)
    before = _files(tmp_path)
    with pytest.raises(InputError, match=re.escape(message)):
        _definition_install(root, project_root=tmp_path)
    assert _files(tmp_path) == before


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
    assert (root / "agents/python-coder.md").is_file()
    assert not (root / _GUARDRAIL).exists()
    assert not (tmp_path / _SETTINGS).exists()
    [skipped] = [line for line in capsys.readouterr().out.splitlines() if line.startswith("guardrail hook skipped")]
    assert reason in skipped and "left in place" not in skipped


def test_a_failed_probe_after_an_install_leaves_its_script_and_entry_and_names_them(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _claude_root(tmp_path)
    _definition_install(root, project_root=tmp_path)
    before = _files(tmp_path)
    monkeypatch.setattr("adjagent.install.GUARDRAIL_INTERPRETER", "adjagent-no-such-perl")
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    after = _files(tmp_path)
    for relative in (f".claude/{_GUARDRAIL}", _SETTINGS):
        assert after[relative] == before[relative]
    assert (
        f"left in place from an earlier install: {root / _GUARDRAIL}, {tmp_path / _SETTINGS}" in capsys.readouterr().out
    )


def test_an_opencode_install_writes_no_claude_settings_file(tmp_path: Path) -> None:
    root = tmp_path / ".opencode"
    root.mkdir()
    _definition_install(root, _OPENCODE_RENDER, project_root=tmp_path)
    assert not (tmp_path / ".claude").exists()
    assert not (root / _GUARDRAIL).exists()


@pytest.mark.parametrize("subdir", ["tools/agents", "."], ids=["subdir", "project-root"])
def test_the_registered_command_runs_the_script_the_install_wrote(tmp_path: Path, subdir: str) -> None:
    """The settings file stays `.claude/settings.json` wherever ROOT sits, and the command it registers,
    run as Claude Code runs it, reaches the script under ROOT: it blocks an in-place edit and allows a
    plain command."""
    root = tmp_path / subdir
    root.mkdir(parents=True, exist_ok=True)
    _definition_install(root, project_root=tmp_path)
    assert (root / _GUARDRAIL).is_file()
    assert _run_registered_hook(tmp_path, "sed -i x f").returncode == 2
    assert _run_registered_hook(tmp_path, "echo hi").returncode == 0


def test_a_missing_script_does_not_block_and_names_the_path(tmp_path: Path) -> None:
    """Perl exits 2 on a script it cannot open, which Claude Code reads as a block, so a settings file
    committed without the hooks directory would block every Bash call. The registered command instead
    exits with another status and names the missing script."""
    root = _claude_root(tmp_path)
    _definition_install(root, project_root=tmp_path)
    (root / _GUARDRAIL).unlink()
    result = _run_registered_hook(tmp_path, "sed -i x f")
    assert result.returncode not in (0, 2)
    assert result.stderr.count("\n") == 1 and str(root / _GUARDRAIL) in result.stderr


def _run_registered_hook(project: Path, command: str) -> subprocess.CompletedProcess:
    """The one command `project`'s settings file registers, run under `sh -c` with
    `CLAUDE_PROJECT_DIR` set and a Bash payload for `command` on stdin."""
    settings = json.loads((project / _SETTINGS).read_text(encoding="utf-8"))
    [[hook]] = [element["hooks"] for element in settings["hooks"]["PreToolUse"]]
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(project)}
    return subprocess.run(
        ["sh", "-c", hook["command"]],
        input=json.dumps(payload),
        capture_output=True,
        encoding="utf-8",
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)},
        check=False,
    )


# A project's own hook running a script of the same name, spelled as the project would write it.
_PROJECT_GUARDRAIL = {
    "matcher": "Bash",
    "hooks": [{"type": "command", "command": 'perl "$CLAUDE_PROJECT_DIR/tools/hooks/guardrail.pl"'}],
}


def test_a_projects_own_hook_running_a_guardrail_pl_is_kept_and_ours_appended(tmp_path: Path) -> None:
    """Only the command an install writes is ours: a project hook naming a `hooks/guardrail.pl` of its
    own is the project's, and replacing it would delete it."""
    root = _claude_root(tmp_path, json.dumps({"hooks": {"PreToolUse": [_PROJECT_GUARDRAIL]}}, indent=2) + "\n")
    _definition_install(root, project_root=tmp_path)
    settings = json.loads((tmp_path / _SETTINGS).read_text(encoding="utf-8"))
    assert settings["hooks"]["PreToolUse"] == [_PROJECT_GUARDRAIL, _hook_entry(".claude")]


def test_a_failed_probe_names_neither_a_script_nor_an_entry_an_install_did_not_write(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _claude_root(tmp_path, json.dumps({"hooks": {"PreToolUse": [_PROJECT_GUARDRAIL]}}) + "\n")
    (root / "hooks").mkdir()
    (root / _GUARDRAIL).write_text("print 'mine';\n", encoding="utf-8")
    monkeypatch.setattr("adjagent.install.GUARDRAIL_INTERPRETER", "adjagent-no-such-perl")
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    [skipped] = [line for line in capsys.readouterr().out.splitlines() if line.startswith("guardrail hook skipped")]
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
    [skipped] = [line for line in capsys.readouterr().out.splitlines() if line.startswith("guardrail hook skipped")]
    assert "did not exit within 0.5 seconds" in skipped


def test_a_harness_directory_the_hook_command_cannot_quote_is_refused_with_nothing_written(tmp_path: Path) -> None:
    root = tmp_path / 'a"b'
    root.mkdir()
    before = _files(tmp_path)
    with pytest.raises(InputError, match="cannot quote"):
        _definition_install(root, project_root=tmp_path)
    assert _files(tmp_path) == before


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
    path.symlink_to(outside, target_is_directory=True)


def _standing(path: Path) -> object:
    """What stands at `path`, compared without following it: a link's target text, a directory's files,
    a file's bytes."""
    if path.is_symlink():
        return str(path.readlink())
    return _files(path) if path.is_dir() else path.read_bytes()


@pytest.mark.parametrize(
    "planted, plant",
    [(".claude/agents", _plant_file), (".claude/hooks", _plant_directory_link)],
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
        (_CLAUDE_RENDER, False, ".claude", _SETTINGS, _plant_directory, "is not a regular file"),
        (_CLAUDE_RENDER, False, "tools", ".claude", _plant_file, "is not a directory"),
        (_CLAUDE_RENDER, False, ".claude", _SETTINGS, _plant_link, "is a symlink"),
        (_CLAUDE_RENDER, False, ".claude", _SETTINGS, _plant_dangling_link, "is a symlink"),
        (_CLAUDE_RENDER, True, ".claude", ".mcp.json", _plant_directory, "is not a regular file"),
        (_CLAUDE_RENDER, True, ".claude", ".mcp.json", _plant_link, "is a symlink"),
        (_CLAUDE_RENDER, True, ".claude", ".mcp.json", _plant_dangling_link, "is a symlink"),
        (_OPENCODE_RENDER, True, "tools", ".opencode", _plant_file, "is not a directory"),
    ],
    ids=[
        "guardrail-directory",
        "guardrail-parent-file",
        "guardrail-symlink",
        "guardrail-dangling-symlink",
        "mcp-directory",
        "mcp-symlink",
        "mcp-dangling-symlink",
        "mcp-parent-file",
    ],
)
def test_a_settings_path_a_merge_cannot_write_in_place_is_reported_and_left_standing(
    tmp_path: Path, capsys, ctx: Render, kb: bool, subdir: str, planted: str, plant, reason: str
) -> None:
    """The install completes; the merge writes nothing there or through it — a symlink's target, dangling
    or not, outside the project included — and names the path with the entry to merge by hand."""
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
    out = capsys.readouterr().out
    assert any(f"{project / planted} {reason}" in line and _BY_HAND in line for line in out.splitlines())
