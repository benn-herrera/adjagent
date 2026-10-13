"""The agents-file render and installer, and the definition install, each case checked against values
the code under test did not compute: the marker span, the bytes kept outside it, the refusals that
write nothing, the redirects, the package copy and its banner, and the prune.

The package is imported from the repository root, which `just test` puts on PYTHONPATH.
"""

import dataclasses
import os
import re
from pathlib import Path

import pytest

from adjagent.agents_file import install_agents_file, marker_span, scope_name
from adjagent.context import Render
from adjagent.definition import Definition
from adjagent.errors import InputError
from adjagent.families.claude import FAMILY as CLAUDE_FAMILY
from adjagent.harness import Harness
from adjagent.harnesses.claude import HARNESS as CLAUDE
from adjagent.harnesses.opencode import HARNESS as OPENCODE
from adjagent.install import REPO_ROOT, install
from adjagent.render import filled_body, render_agents_file, render_all
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
def test_the_fresh_render_holds_one_block_citing_the_default_family_medium_member(harness: Harness) -> None:
    user_dir = Path(harness.user_harness_dir).expanduser()
    text = render_agents_file(harness, scope=scope_name(harness, user_dir))
    lines, begin, end = marker_span(text, where="render")
    assert (lines[0], lines[begin], lines[end]) == ("# Global info and directives", _BEGIN, _END)
    assert "`model: sonnet`" in text
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


# The definition install.

_CLAUDE_RENDER = Render(harness=CLAUDE, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
_NEW_BANNER = "---\n# !GENERATED! from adjagent/definitions/gone.py — x\n# !TUNING! y\n---\n\nbody\n"
_OLD_BANNER = "---\n#\n# !GENERATED! from templates/agents/gone.tmpl.md\n# !TUNING! y\n#\n---\n\nbody\n"


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("consumer")
    install(root, _CLAUDE_RENDER, verbose=False)
    return root


def test_install_writes_every_render_and_stamps_package_code_once(installed: Path) -> None:
    assert all((installed / path).is_file() for path, _ in render_all(_CLAUDE_RENDER))
    shebang = (installed / "agents/kb_tools/verify_md_links.py").read_text(encoding="utf-8").split("\n")
    source = (REPO_ROOT / "kb_tools/verify_md_links.py").read_text(encoding="utf-8").split("\n")
    assert shebang[0] == source[0] == "#!/usr/bin/env python3"
    assert shebang[1].startswith("# !INSTALLED! from kb_tools/verify_md_links.py — ")
    assert shebang[2:] == source[1:]
    plain = (installed / "agents/kb_tools/kb_util.py").read_text(encoding="utf-8")
    assert plain.count("!INSTALLED!") == 1 and plain.startswith("# !INSTALLED! from kb_tools/kb_util.py — ")
    template = "agents/kb_tools/installed/AGENTS.tmpl.md"
    assert (installed / template).read_bytes() == (REPO_ROOT / "kb_tools/installed/AGENTS.tmpl.md").read_bytes()


def test_install_keeps_the_executable_bit_and_ships_no_tests_or_project_documents(installed: Path) -> None:
    assert os.access(REPO_ROOT / "liaison_tools/msg-util.py", os.X_OK)
    assert os.access(installed / "agents/liaison_tools/msg-util.py", os.X_OK)
    assert not os.access(installed / "agents/kb_tools/verify_md_links.py", os.X_OK)
    shipped = {path.name for path in (installed / "agents").rglob("*")}
    assert not shipped & {"tests", "SPEC.md", "CONVENTIONS.md", "__pycache__"}


def test_reinstall_replaces_packages_whole_and_prunes_only_our_stale_definitions(tmp_path: Path, capsys) -> None:
    install(tmp_path, _CLAUDE_RENDER, verbose=False)
    planted = {
        "agents/kb_tools/stale.py": "x = 1\n",
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
    assert pruned == {f"pruned {tmp_path / 'agents/gone-too/deeper/old.md'}", f"pruned {tmp_path / 'agents/gone/old.md'}"}


@pytest.mark.parametrize("root", [REPO_ROOT, REPO_ROOT / "kb_tools"], ids=["repository", "package-source"])
def test_install_refuses_the_repository_and_a_package_source(root: Path) -> None:
    with pytest.raises(InputError, match="is this repository or inside a package source"):
        install(root, _CLAUDE_RENDER, verbose=False)
    assert not (root / "agents" / "python-coder.md").exists() and not (root / "commands").exists()
