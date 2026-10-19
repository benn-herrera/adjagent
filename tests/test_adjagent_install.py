"""The agents-file render and installer, and the definition install, each case checked against values
the code under test did not compute: the marker span, the bytes kept outside it, the refusals that
write nothing, the redirects, the kb-tools package and its banner, the kb install path, the MCP
settings merge, the runner include line, and the prune.

The package is imported from the repository root, which `just test` puts on PYTHONPATH.
"""

import dataclasses
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from adjagent.agents_file import install_agents_file, marker_span, scope_name
from adjagent.cli import main
from adjagent.context import Render, build_render
from adjagent.definition import Definition
from adjagent.errors import InputError
from adjagent.families.claude import FAMILY as CLAUDE_FAMILY
from adjagent.harness import Harness
from adjagent.harnesses.claude import HARNESS as CLAUDE
from adjagent.harnesses.opencode import HARNESS as OPENCODE
from adjagent.install import (
    _LFS_UNKNOWN,
    _LFS_UNTRACKED,
    REPO_ROOT,
    _lfs_advisory,
    _named_harnesses,
    excluded,
    install,
    install_kb_include_line,
)
from adjagent.render import definitions, filled_body, render_agents_file, render_all, render_definition
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


# The definition install. A consumer project receives the product under its harness directory, and —
# when the install includes kb — the kb-tools package beside the `kbase` MCP entry and the runner
# include line.

_CLAUDE_RENDER = Render(harness=CLAUDE, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
_OPENCODE_RENDER = build_render(harness="opencode", family="claude", tier_spec="all=inherit", alias_spec=None)
_NEW_BANNER = "---\n# !GENERATED! from adjagent/definitions/gone.py — x\n# !TUNING! y\n---\n\nbody\n"
_OLD_BANNER = "---\n#\n# !GENERATED! from templates/agents/gone.tmpl.md\n# !TUNING! y\n#\n---\n\nbody\n"
# A skill's supporting file: no frontmatter, so its banner rides on two HTML comment lines.
_COMMENT_BANNER = "<!-- !GENERATED! from adjagent/definitions/kbase.py — x -->\n<!-- !TUNING! y -->"
_KBASE_BYTES = b"KBASE-STUB-v1\n"
_KB_DEFINITIONS = (
    "agents/kb-claim-scorer.md",
    "agents/kb-maintainer.md",
)
# The kbase skill's files: one definition owning a directory, so a run keeps or drops all three.
_KB_SKILL_FILES = (
    "skills/kbase/SKILL.md",
    "skills/kbase/references/reading.md",
    "skills/kbase/references/build.md",
)


def _kbase_exe(tmp_path: Path, *, name: str = "kbase") -> Path:
    """A stand-in `kbase` executable: known bytes with the executable bit set."""
    path = tmp_path / name
    path.write_bytes(_KBASE_BYTES)
    path.chmod(0o755)
    return path


def _unexecutable(tmp_path: Path) -> Path:
    """A stand-in `kbase` file with the executable bit clear."""
    path = tmp_path / "kbase"
    path.write_bytes(_KBASE_BYTES)
    path.chmod(0o644)
    return path


def _definition_install(
    root: Path,
    ctx: Render = _CLAUDE_RENDER,
    *,
    with_kb: bool = False,
    kbase_dist: Path | None = None,
    project_root: Path | None = None,
) -> None:
    install(root, ctx, verbose=False, with_kb=with_kb, kbase_dist=kbase_dist, project_root=project_root)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("kb-claim-scorer", True),
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
    assert "adj-tools/liaison_tools/msg-util.py" in files
    for relative in (
        *_KB_DEFINITIONS,
        *_KB_SKILL_FILES,
        "adj-tools/kb-tools/runner-snippets/kb.just",
        "adj-tools/kb-tools/kbase",
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
    dist = _kbase_exe(tmp_path)
    _definition_install(root, with_kb=True, kbase_dist=dist, project_root=project)
    for relative in (*_KB_DEFINITIONS, *_KB_SKILL_FILES):
        assert (root / relative).is_file()
    kb_just = (root / "adj-tools/kb-tools/runner-snippets/kb.just").read_text(encoding="utf-8").split("\n")
    source_just = (REPO_ROOT / "kb-tools/runner-snippets/kb.just").read_text(encoding="utf-8").split("\n")
    kb_mk = (root / "adj-tools/kb-tools/runner-snippets/kb.mk").read_text(encoding="utf-8").split("\n")
    assert kb_just[0].startswith("# !INSTALLED! from kb-tools/runner-snippets/kb.just — ")
    assert kb_just[1:] == source_just
    assert kb_mk[0].startswith("# !INSTALLED! from kb-tools/runner-snippets/kb.mk — ")
    kbase = root / "adj-tools/kb-tools/kbase"
    assert kbase.read_bytes() == dist.read_bytes() == _KBASE_BYTES
    assert os.access(kbase, os.X_OK)
    assert json.loads((project / ".mcp.json").read_text(encoding="utf-8")) == {
        "mcpServers": {
            "kbase": {
                "command": ".claude/adj-tools/kb-tools/kbase",
                "args": ["mcp", "--kb-root", str(project.resolve())],
            }
        }
    }
    assert (project / "justfile").read_text(encoding="utf-8") == (
        "# mine\n\nimport? '.claude/adj-tools/kb-tools/runner-snippets/kb.just'\n"
    )
    captured = capsys.readouterr()
    assert f"wrote {project / '.mcp.json'} with the kbase MCP entry" in captured.out
    assert "appended the KB include line" in captured.out
    assert "Git LFS" in captured.err


@pytest.mark.parametrize(
    "dist",
    [lambda tmp: tmp / "gone", lambda tmp: _unexecutable(tmp), lambda tmp: _kbase_exe(tmp, name="kbase.bin")],
    ids=["missing", "not-executable", "wrong-name"],
)
def test_a_kbase_dist_that_cannot_be_installed_is_refused_with_nothing_written(tmp_path: Path, dist) -> None:
    """A `--kbase-dist` the install cannot use is a refusal, never a silent fall-through to the
    installed binary — the caller asked for that file."""
    root = tmp_path / ".claude"
    root.mkdir()
    source = dist(tmp_path)
    before = _files(tmp_path)
    with pytest.raises(InputError, match="--kbase-dist"):
        _definition_install(root, with_kb=True, kbase_dist=source, project_root=tmp_path)
    assert _files(tmp_path) == before


def test_a_kbase_dist_inside_the_destination_it_replaces_is_refused_and_the_tree_survives(
    tmp_path: Path,
) -> None:
    """The source is read before the first write: a dist inside a destination this run deletes would
    otherwise be gone before it could be copied, leaving nothing installed."""
    project = tmp_path
    root = project / ".claude"
    installed = root / "adj-tools/kb-tools/kbase"
    installed.parent.mkdir(parents=True)
    installed.write_bytes(_KBASE_BYTES)
    installed.chmod(0o755)
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    before = _files(tmp_path)
    with pytest.raises(InputError, match="is inside"):
        _definition_install(root, with_kb=True, kbase_dist=installed, project_root=project)
    assert _files(tmp_path) == before


def test_the_current_kb_tools_destination_makes_a_plain_install_sticky(tmp_path: Path) -> None:
    """A plain install into a root already carrying the kb-tools destination is a kb install: the kb
    definitions and the installed executable stay."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    _definition_install(root, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=project)
    _definition_install(root, project_root=project)
    after = _files(root)
    for relative in (*_KB_DEFINITIONS, *_KB_SKILL_FILES):
        assert relative in after
    assert after["adj-tools/kb-tools/kbase"] == _KBASE_BYTES


def test_a_kb_tools_tree_without_the_executable_is_not_sticky(tmp_path: Path) -> None:
    """The executable is the signal, not the directory: a tracked tree whose binary has not been
    pulled from Git LFS is not a kb install's evidence, so a plain install stays plain — no kb
    definitions, no MCP entry, no runner include line, and the tree left as it was found."""
    project = tmp_path
    root = project / ".claude"
    snippets = root / "adj-tools/kb-tools/runner-snippets"
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


def test_a_non_executable_installed_kbase_is_refused_with_nothing_written(tmp_path: Path) -> None:
    """The sticky rule keys on the file existing, so a copy whose executable bit was never set still
    selects kb — but it is no source, no legacy tree holds one and no --kbase-dist was passed, so the
    refusal names the file's state rather than claiming it absent, and writes nothing."""
    project = tmp_path
    root = project / ".claude"
    installed = root / "adj-tools/kb-tools/kbase"
    installed.parent.mkdir(parents=True)
    installed.write_bytes(_KBASE_BYTES)
    installed.chmod(0o644)
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    before = _files(tmp_path)
    with pytest.raises(InputError, match="exists but is not an executable file"):
        _definition_install(root, project_root=project)
    assert _files(tmp_path) == before
    assert not (project / ".mcp.json").exists()
    assert (project / "justfile").read_text(encoding="utf-8") == "# mine\n"


@pytest.mark.parametrize(
    "rev_parse, check_attr, expected",
    [
        (1, None, _LFS_UNKNOWN),
        (0, "kbase: filter: lfs\n", None),
        (0, "kbase: filter: unspecified\n", _LFS_UNTRACKED),
    ],
    ids=["no-work-tree", "lfs", "untracked"],
)
def test_the_lfs_advisory_reads_gits_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rev_parse: int, check_attr: str | None, expected: str | None
) -> None:
    """No git: a fake answers `rev-parse` and `check-attr`, and the advisory is the verdict for that answer."""

    def fake_git(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
        if args[0] == "rev-parse":
            return subprocess.CompletedProcess(args, rev_parse, stdout="")
        return subprocess.CompletedProcess(args, 0, stdout=check_attr)

    monkeypatch.setattr("adjagent.install._git", fake_git)
    assert _lfs_advisory(tmp_path / "kbase") is expected


def test_the_cli_with_kb_flag_installs_the_kb_definitions_and_the_adj_tools_kb_tools_destination(
    tmp_path: Path,
) -> None:
    """`--with-kb` reaches `install()`: driven through the CLI entry point, the flag's own effect —
    the kb definitions, the runner snippets and the copied `kbase` — is what appears under ROOT."""
    root = tmp_path / ".claude"
    root.mkdir()
    dist = _kbase_exe(tmp_path)
    main(["install", str(root), "--harness=claude", "--with-kb", f"--kbase-dist={dist}"])
    assert all((root / relative).is_file() for relative in _KB_DEFINITIONS)
    snippets = root / "adj-tools/kb-tools/runner-snippets"
    assert (snippets / "kb.just").is_file() and (snippets / "kb.mk").is_file()
    kbase = root / "adj-tools/kb-tools/kbase"
    assert kbase.read_bytes() == _KBASE_BYTES
    assert os.access(kbase, os.X_OK)


def test_the_legacy_agents_kb_tools_destination_makes_a_plain_install_sticky(tmp_path: Path, capsys) -> None:
    """A tree an earlier version installed is a kb install's evidence and its source: the binary is
    copied to the new destination before the old tree is removed, and the snippets are refreshed."""
    project = tmp_path
    root = project / ".claude"
    legacy = root / "agents/kb-tools"
    snippets = legacy / "runner-snippets"
    snippets.mkdir(parents=True)
    (snippets / "kb.just").write_text("# stale snippet\n", encoding="utf-8")
    (snippets / "gone.just").write_text("# stale\n", encoding="utf-8")
    legacy_kbase = legacy / "kbase"
    legacy_kbase.write_bytes(_KBASE_BYTES)
    legacy_kbase.chmod(0o755)
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, project_root=project)
    for relative in ("agents/kb-claim-scorer.md", "skills/kbase/SKILL.md"):
        assert (root / relative).is_file()
    installed_kbase = root / "adj-tools/kb-tools/kbase"
    assert installed_kbase.read_bytes() == _KBASE_BYTES and os.access(installed_kbase, os.X_OK)
    assert not legacy.exists()
    out = capsys.readouterr().out
    assert f"removed legacy tree {legacy}" in out
    new_snippets = root / "adj-tools/kb-tools/runner-snippets"
    assert not (new_snippets / "gone.just").exists()
    kb_just = (new_snippets / "kb.just").read_text(encoding="utf-8")
    assert kb_just.startswith("# !INSTALLED! from kb-tools/runner-snippets/kb.just — ")
    assert "# stale snippet" not in kb_just and "kb-verify" in kb_just
    assert not any(line.startswith("pruned ") and "kb-" in line for line in out.splitlines())


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
    _definition_install(root, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=tmp_path)
    assert not stale.exists()
    assert mine.read_text(encoding="utf-8") == "---\nmine\n---\n"
    assert all((root / relative).is_file() for relative in _KB_SKILL_FILES)
    assert f"pruned {stale}" in capsys.readouterr().out


def test_a_plain_install_prunes_every_file_a_kb_install_wrote_for_the_skill(tmp_path: Path, capsys) -> None:
    """A skill is one keep/drop decision: no run leaves the router standing beside its references gone."""
    root = tmp_path / ".claude"
    (root / "skills/kbase/references").mkdir(parents=True)
    (root / "skills/kbase/SKILL.md").write_text(_NEW_BANNER, encoding="utf-8")
    for name in ("reading.md", "build.md"):
        (root / "skills/kbase/references" / name).write_text(f"{_COMMENT_BANNER}\n\nbody\n", encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, project_root=tmp_path)
    assert not (root / "skills/kbase").exists()
    pruned = {line for line in capsys.readouterr().out.splitlines() if line.startswith("pruned ")}
    assert pruned == {f"pruned {root / relative}" for relative in _KB_SKILL_FILES}


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
    planted = ("agents/kb_tools/kb_util.py", "agents/liaison_tools/stale.py")
    for relative in planted:
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text("# legacy\n", encoding="utf-8")
    capsys.readouterr()
    if kb:
        _definition_install(root, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=project)
    else:
        _definition_install(root, project_root=project)
    assert not (root / "agents/kb_tools").exists()
    assert not (root / "agents/liaison_tools").exists()
    out = capsys.readouterr().out
    for relative in ("agents/kb_tools", "agents/liaison_tools"):
        assert f"removed legacy tree {root / relative}" in out
    message = "legacy kb_tools removed. if you are using kb functionality install using `install-with-kb`"
    assert (message in out) == (not kb)


@pytest.mark.parametrize(
    "command, expected",
    [
        (lambda project: project / ".claude/adj-tools/kb-tools/kbase", ".claude/adj-tools/kb-tools/kbase"),
        (lambda project: project / "adj-tools/kb-tools/kbase", "adj-tools/kb-tools/kbase"),
        (lambda project: project.parent / "elsewhere/kbase", None),
    ],
    ids=["inside", "project-is-root", "outside"],
)
def test_the_claude_mcp_command_is_relative_to_the_project_when_it_sits_inside(
    tmp_path: Path, command, expected: str | None
) -> None:
    """Claude Code reads an absolute command inside the project as a shared file outside it, so one
    there is named relative to the project root with POSIX separators. An executable outside the
    project — an install root there is refused before the entry is built, so this is the builder's
    own contract — keeps its absolute path, `None` standing for it: there is no relative name."""
    project = tmp_path / "project"
    project.mkdir()
    executable = command(project).resolve()
    entry, container = CLAUDE.mcp.entry(command=str(executable), kb_root=str(project), project_root=project)
    assert entry["command"] == (str(executable) if expected is None else expected)
    assert container == ("mcpServers", "kbase")


def test_the_mcp_merge_keeps_every_unrelated_key(tmp_path: Path) -> None:
    """The entry is replaced where it stands — the absolute command an earlier version wrote does not
    survive, so an upgraded project needs no hand edit — and every key beside it is kept."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    (project / ".mcp.json").write_text(
        json.dumps(
            {
                "permissions": {"allow": ["Bash"]},
                "mcpServers": {
                    "other": {"command": "x"},
                    "kbase": {"command": f"{project.resolve()}/.claude/adj-tools/kb-tools/kbase", "args": []},
                },
            }
        ),
        encoding="utf-8",
    )
    _definition_install(root, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=project)
    data = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
    assert data["permissions"] == {"allow": ["Bash"]}
    assert data["mcpServers"]["other"] == {"command": "x"}
    assert data["mcpServers"]["kbase"] == {
        "command": ".claude/adj-tools/kb-tools/kbase",
        "args": ["mcp", "--kb-root", str(project.resolve())],
    }


def test_the_opencode_mcp_entry_lands_in_the_discovered_file_in_the_v2_shape(tmp_path: Path) -> None:
    project = tmp_path
    root = project / ".opencode"
    root.mkdir()
    discovered = root / "opencode.json"
    discovered.write_text(
        json.dumps({"theme": "omlx", "mcp": {"servers": {"other": {"type": "local"}}}}), encoding="utf-8"
    )
    _definition_install(root, _OPENCODE_RENDER, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=project)
    text = discovered.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["theme"] == "omlx"
    assert data["mcp"]["servers"]["other"] == {"type": "local"}
    assert data["mcp"]["servers"]["kbase"] == {
        "type": "local",
        "command": [str(root.resolve() / "adj-tools/kb-tools/kbase"), "mcp", "--kb-root", str(project.resolve())],
    }
    assert "enabled" not in text
    assert not (root / "opencode.jsonc").exists()


@pytest.mark.parametrize(
    "harness_dir, ctx, canonical",
    [(".claude", _CLAUDE_RENDER, ".mcp.json"), (".opencode", _OPENCODE_RENDER, ".opencode/opencode.jsonc")],
    ids=["claude", "opencode"],
)
def test_the_mcp_settings_file_is_created_when_absent(
    tmp_path: Path, harness_dir: str, ctx: Render, canonical: str
) -> None:
    root = tmp_path / harness_dir
    root.mkdir()
    _definition_install(root, ctx, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=tmp_path)
    text = (tmp_path / canonical).read_text(encoding="utf-8")
    assert json.loads(text)
    assert '"kbase"' in text and "enabled" not in text


def test_an_mcp_file_carrying_jsonc_comments_is_reported_and_left_untouched(tmp_path: Path, capsys) -> None:
    root = tmp_path / ".opencode"
    root.mkdir()
    discovered = root / "opencode.json"
    prior = '{\n  // my own server\n  "mcp": {"servers": {}}\n}\n'
    discovered.write_text(prior, encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, _OPENCODE_RENDER, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=tmp_path)
    assert discovered.read_text(encoding="utf-8") == prior
    assert f"{discovered} carries JSONC comments — left untouched; merge this entry by hand:" in capsys.readouterr().out


def _built_entry(harness: Harness, project: Path, root: Path) -> dict:
    """The `kbase` entry `harness`'s builder makes for `root` installed under `project` — the value the
    splice is expected to have placed, read from the builder rather than restated."""
    entry, _ = harness.mcp.entry(
        command=str(root.resolve() / "adj-tools/kb-tools/kbase"), kb_root=str(project.resolve()), project_root=project
    )
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
    _definition_install(root, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=project)
    text = (project / ".mcp.json").read_text(encoding="utf-8")
    head, other, tail = seed.partition('"other": {"command": "x", "args": [1, 2.50, true]}')
    assert other and text.startswith(head) and text.endswith(tail)
    before = json.loads(seed)
    before["mcpServers"]["kbase"] = _built_entry(CLAUDE, project, root)
    assert json.loads(text) == before


def test_a_compact_one_line_mcp_file_gains_the_entry_inline(tmp_path: Path) -> None:
    """The file states no indent, so none is invented: the entry goes in on the line it finds."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    (project / ".mcp.json").write_text('{"mcpServers": {}}', encoding="utf-8")
    _definition_install(root, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=project)
    text = (project / ".mcp.json").read_text(encoding="utf-8")
    assert "\n" not in text
    assert json.loads(text) == {"mcpServers": {"kbase": _built_entry(CLAUDE, project, root)}}


def test_a_settings_file_without_the_container_gains_it_whole(tmp_path: Path) -> None:
    """`mcpServers` absent is not a reason to reserialize: the container goes in as one member, on a
    line indented like the sibling it lands beside."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    seed = '{\n  "permissions": {"allow": ["Bash"]}\n}\n'
    (project / ".mcp.json").write_text(seed, encoding="utf-8")
    _definition_install(root, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=project)
    text = (project / ".mcp.json").read_text(encoding="utf-8")
    assert text.startswith('{\n  "permissions": {"allow": ["Bash"]},\n  "mcpServers": ')
    assert text.endswith("\n}\n")
    assert json.loads(text) == {
        "permissions": {"allow": ["Bash"]},
        "mcpServers": {"kbase": _built_entry(CLAUDE, project, root)},
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
    _definition_install(root, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=project)
    text = (project / ".mcp.json").read_text(encoding="utf-8")
    head, found, tail = seed.partition(prior)
    assert found and text.startswith(head) and text.endswith(tail)
    assert json.loads(text)["mcpServers"] == {"kbase": _built_entry(CLAUDE, project, root), "other": {"command": "x"}}


def test_a_crlf_mcp_file_keeps_its_line_endings(tmp_path: Path) -> None:
    """Byte reading and writing with no newline translation, and the entry's own lines take the file's
    ending: a CRLF file stays CRLF through the merge."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    seed = '{\r\n  "mcpServers": {\r\n  }\r\n}\r\n'
    (project / ".mcp.json").write_bytes(seed.encode("utf-8"))
    _definition_install(root, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=project)
    raw = (project / ".mcp.json").read_bytes()
    assert b"\n" not in raw.replace(b"\r\n", b"")
    assert json.loads(raw.decode("utf-8")) == {"mcpServers": {"kbase": _built_entry(CLAUDE, project, root)}}


def test_a_duplicate_container_key_is_reported_and_left_byte_identical(tmp_path: Path, capsys) -> None:
    """The file names `mcpServers` twice, so the splice cannot say which one is meant: it reports and
    writes nothing — the install still succeeded — rather than picking one."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    seed = '{"mcpServers": {"other": {"command": "x"}}, "mcpServers": {}}\n'
    (project / ".mcp.json").write_text(seed, encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=project)
    assert (project / ".mcp.json").read_text(encoding="utf-8") == seed
    out = capsys.readouterr().out
    entry = _built_entry(CLAUDE, project, root)
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
    _definition_install(root, _OPENCODE_RENDER, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=project)
    text = discovered.read_text(encoding="utf-8")
    head, other, tail = seed.partition('"other": {"type": "local"}')
    assert other and text.startswith(head) and text.endswith(tail)
    assert json.loads(text)["mcp"]["servers"]["kbase"] == _built_entry(OPENCODE, project, root)


def test_the_include_line_is_appended_to_an_existing_justfile(tmp_path: Path) -> None:
    root = tmp_path / ".claude"
    root.mkdir()
    (tmp_path / "justfile").write_text("default:\n  @echo hi\n", encoding="utf-8")
    _definition_install(root, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=tmp_path)
    assert (tmp_path / "justfile").read_text(encoding="utf-8") == (
        "default:\n  @echo hi\n\nimport? '.claude/adj-tools/kb-tools/runner-snippets/kb.just'\n"
    )


def test_a_makefile_is_created_when_the_project_has_neither_runner_file(tmp_path: Path) -> None:
    root = tmp_path / ".opencode"
    root.mkdir()
    _definition_install(root, _OPENCODE_RENDER, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=tmp_path)
    text = (tmp_path / "Makefile").read_text(encoding="utf-8")
    assert text.startswith("# Makefile — created by the adjagent installer.\n")
    assert "-include .opencode/adj-tools/kb-tools/runner-snippets/kb.mk\n" in text
    assert not (tmp_path / "justfile").exists()


def test_a_second_harness_writes_no_include_line_and_reports_the_first(tmp_path: Path, capsys) -> None:
    project = tmp_path
    first = project / ".claude"
    first.mkdir()
    (project / "justfile").write_text("# mine\n", encoding="utf-8")
    _definition_install(first, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=project)
    before = (project / "justfile").read_bytes()
    second = project / ".opencode"
    second.mkdir()
    capsys.readouterr()
    _definition_install(second, _OPENCODE_RENDER, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=project)
    assert (project / "justfile").read_bytes() == before
    out = capsys.readouterr().out
    assert "no include line written" in out and "'claude'" in out


@pytest.mark.parametrize(
    "legacy_path",
    ["agents/kb-tools/runner-snippets", "agents/kb_tools/runner-snippets"],
    ids=["hyphen", "underscore"],
)
def test_a_legacy_include_line_for_this_harness_is_rewritten_in_place(tmp_path: Path, capsys, legacy_path: str) -> None:
    """A line an earlier version wrote is the same harness's line: it is replaced where it stands, so
    the file keeps one include line rather than gaining a second beside a dead one."""
    project = tmp_path
    root = project / ".claude"
    root.mkdir()
    (project / "justfile").write_text(f"default:\n  @echo hi\n\nimport? '.claude/{legacy_path}/kb.just'\n")
    capsys.readouterr()
    _definition_install(root, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=project)
    text = (project / "justfile").read_text(encoding="utf-8")
    assert text == "default:\n  @echo hi\n\nimport? '.claude/adj-tools/kb-tools/runner-snippets/kb.just'\n"
    assert text.count("runner-snippets") == 1
    assert "rewrote the KB include line" in capsys.readouterr().out


def test_a_legacy_include_line_for_another_harness_is_reported_and_left(tmp_path: Path, capsys) -> None:
    project = tmp_path
    root = project / ".opencode"
    root.mkdir()
    line = "import? '.claude/agents/kb-tools/runner-snippets/kb.just'"
    (project / "justfile").write_text(f"{line}\n", encoding="utf-8")
    capsys.readouterr()
    _definition_install(root, _OPENCODE_RENDER, with_kb=True, kbase_dist=_kbase_exe(tmp_path), project_root=project)
    assert (project / "justfile").read_text(encoding="utf-8") == f"{line}\n"
    out = capsys.readouterr().out
    assert "no include line written" in out and "'claude'" in out


@pytest.mark.parametrize(
    "prior, expected",
    [
        (
            "# import? '.claude/agents/kb-tools/runner-snippets/kb.just'\n",
            "# import? '.claude/agents/kb-tools/runner-snippets/kb.just'\n"
            "\nimport? '.claude/adj-tools/kb-tools/runner-snippets/kb.just'\n",
        ),
        (
            "import? '.claude/agents/kb-tools/runner-snippets/kb.just'  # mine\n",
            "import? '.claude/adj-tools/kb-tools/runner-snippets/kb.just'  # mine\n",
        ),
        (
            "default:\r\n  @echo hi\r\n\r\nimport? '.claude/agents/kb-tools/runner-snippets/kb.just'\r\n",
            "default:\r\n  @echo hi\r\n\r\nimport? '.claude/adj-tools/kb-tools/runner-snippets/kb.just'\r\n",
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


def test_two_include_lines_are_reported_and_left(tmp_path: Path, capsys) -> None:
    """Rewriting one of two would leave the other stale, so the operator merges them by hand."""
    prior = (
        "import? '.claude/agents/kb-tools/runner-snippets/kb.just'\n"
        "import? '.claude/adj-tools/kb-tools/runner-snippets/kb.just'\n"
    )
    (tmp_path / "justfile").write_text(prior, encoding="utf-8")
    install_kb_include_line(tmp_path, harness_relpath=".claude")
    assert (tmp_path / "justfile").read_text(encoding="utf-8") == prior
    assert "names the kb snippets on lines 1, 2" in capsys.readouterr().out


def test_an_include_line_naming_no_harness_reports_its_raw_prefix() -> None:
    [match] = _named_harnesses("default:\n  @echo hi\nimport? 'tools/adj-tools/kb-tools/runner-snippets/kb.just'\n")
    assert (match.name, match.index) == ("tools", 2)


def test_a_non_utf8_runner_file_is_refused_before_the_first_write(tmp_path: Path) -> None:
    """The runner file is decoded with every other check: the refusal writes nothing, where a decode
    after the writes would leave a half-updated install and refuse the retry too."""
    root = tmp_path / ".claude"
    root.mkdir()
    (tmp_path / "justfile").write_bytes(b"\xff\xfe default:\n")
    dist = _kbase_exe(tmp_path)
    before = _files(tmp_path)
    with pytest.raises(InputError, match="justfile"):
        _definition_install(root, with_kb=True, kbase_dist=dist, project_root=tmp_path)
    assert _files(tmp_path) == before


def test_the_repositorys_own_project_root_gets_no_include_line() -> None:
    before = (REPO_ROOT / "justfile").read_bytes()
    install_kb_include_line(REPO_ROOT, harness_relpath=".claude")
    assert (REPO_ROOT / "justfile").read_bytes() == before
    assert not (REPO_ROOT / "Makefile").exists()


def test_kb_included_with_no_kbase_source_is_refused_with_nothing_written(tmp_path: Path) -> None:
    root = tmp_path / ".claude"
    root.mkdir()
    before = _files(tmp_path)
    with pytest.raises(InputError, match="no kbase executable"):
        _definition_install(root, with_kb=True, project_root=tmp_path)
    assert _files(tmp_path) == before


@pytest.mark.parametrize("root", [REPO_ROOT, REPO_ROOT / "kb-tools"], ids=["repository", "kb-tools-source"])
def test_install_refuses_the_repository_and_a_package_source(root: Path) -> None:
    with pytest.raises(InputError, match="is this repository or inside a package source"):
        install(root, _CLAUDE_RENDER, verbose=False)
    assert not (root / "agents" / "python-coder.md").exists() and not (root / "commands").exists()


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A consumer root installed with kb included: the whole product plus the kb-tools package."""
    project = tmp_path_factory.mktemp("consumer")
    root = project / ".claude"
    root.mkdir()
    install(root, _CLAUDE_RENDER, verbose=False, with_kb=True, kbase_dist=_kbase_exe(project), project_root=project)
    return root


def test_install_writes_every_render_and_stamps_the_packages_once(installed: Path) -> None:
    assert all((installed / path).is_file() for path, _ in render_all(_CLAUDE_RENDER))
    kb_mk = (installed / "adj-tools/kb-tools/runner-snippets/kb.mk").read_text(encoding="utf-8").split("\n")
    source_mk = (REPO_ROOT / "kb-tools/runner-snippets/kb.mk").read_text(encoding="utf-8").split("\n")
    assert kb_mk[0].startswith("# !INSTALLED! from kb-tools/runner-snippets/kb.mk — ")
    assert kb_mk[1:] == source_mk
    liaison = (installed / "adj-tools/liaison_tools/msg-util.py").read_text(encoding="utf-8").split("\n")
    source_liaison = (REPO_ROOT / "liaison_tools/msg-util.py").read_text(encoding="utf-8").split("\n")
    assert liaison[0] == source_liaison[0] == "#!/usr/bin/env python3"
    assert liaison[1].startswith("# !INSTALLED! from liaison_tools/msg-util.py — ")
    assert liaison[2:] == source_liaison[1:]


def test_install_keeps_the_executable_bit_and_ships_no_tests_or_project_documents(installed: Path) -> None:
    assert os.access(REPO_ROOT / "liaison_tools/msg-util.py", os.X_OK)
    assert os.access(installed / "adj-tools/liaison_tools/msg-util.py", os.X_OK)
    assert (installed / "adj-tools/kb-tools/kbase").read_bytes() == _KBASE_BYTES
    assert os.access(installed / "adj-tools/kb-tools/kbase", os.X_OK)
    shipped = {path.name for path in (installed / "adj-tools").rglob("*")}
    assert not shipped & {"tests", "SPEC.md", "CONVENTIONS.md", "__pycache__"}
    assert not (installed / "agents/liaison_tools").exists() and not (installed / "agents/kb-tools").exists()


def test_reinstall_replaces_packages_whole_and_prunes_only_our_stale_definitions(tmp_path: Path, capsys) -> None:
    install(tmp_path, _CLAUDE_RENDER, verbose=False)
    planted = {
        "adj-tools/liaison_tools/stale.py": "x = 1\n",
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
    assert not (tmp_path / "adj-tools/liaison_tools/stale.py").exists()
    pruned = {line for line in capsys.readouterr().out.splitlines() if line.startswith("pruned ")}
    assert pruned == {
        f"pruned {tmp_path / 'agents/gone-too/deeper/old.md'}",
        f"pruned {tmp_path / 'agents/gone/old.md'}",
        f"pruned {tmp_path / 'agents/kb-maintainer.md'}",
    }
