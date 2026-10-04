"""The harness agents-file install: block replacement into a directory the
operator names.

Every test installs into a directory under `tmp_path` with an injected
revision, so no outcome depends on this repository's git state, and nothing
here reads or writes a harness's live configuration directory.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from gen_defs import agents_file
from gen_defs.agents_file import TemplatesRevision
from gen_defs.errors import InputError

_REPO_ROOT = Path(__file__).resolve().parent.parent
CLEAN = TemplatesRevision(sha="abc1234", dirty=())
LATER = TemplatesRevision(sha="def5678", dirty=())

BEGIN = "<!-- vvv-adjagent do not edit. version[0000000] adjagent-vvv -->"
END = "<!-- ^^^-adjagent do not edit. version[0000000] adjagent-^^^ -->"

#: Every key the real template reads, with the user-global directory left to
#: the caller.
HARNESS = """
[harness.project-temp-dir]
text = ".x-temp"

[harness.project-harness-dir]
text = ".x"

[harness.user-harness-dir]
text = "{user_harness_dir}"

[harness.agents-file]
text = "X.md"
"""

#: A minimal valid agents-file body.
BODY = (
    "# @!dyn.agents-file-scope-name!@\n\n@!dyn.existing-user-content-before-rendered-minus-h1!@\n\n"
    "<!-- vvv-adjagent version[@!dyn.gen-short-sha!@] adjagent-vvv -->\nblock\n"
    "<!-- ^^^-adjagent version[@!dyn.gen-short-sha!@] adjagent-^^^ -->\n\n"
    "@!dyn.existing-user-content-after-rendered!@\n"
)


@pytest.fixture
def target(tmp_path) -> Path:
    directory = tmp_path / "d"
    directory.mkdir()
    return directory


def _install(directory: Path, revision: TemplatesRevision = CLEAN, **kwargs) -> Path:
    """Install the claude agents file into `directory`, which is not the
    harness's user-global directory, so the directives land in AGENTS.md."""
    agents_file.install_agents_file("claude", directory, revision, **kwargs)
    return directory / "AGENTS.md"


def _empty_render(directory: Path) -> str:
    return agents_file.render_agents_file_text("claude", directory, CLEAN)


def _with_user_content(empty: str, *, h1: str, before: str, after: str) -> str:
    """The empty-span render with the user's spans placed where the template
    lays them out: below the H1's blank line, and below the end line's."""
    head, rest = empty.split(f"{h1}\n\n\n\n", 1)
    assert head == "" and rest.endswith("adjagent-^^^ -->\n\n\n")
    return f"{h1}\n\n{before}\n\n{rest[:-1]}{after}\n"


def _marker_lines(text: str) -> list[str]:
    return [line for line in text.split("\n") if "-adjagent" in line]


def _listing(directory: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in directory.iterdir()}


# --- the four existing-file cases ------------------------------------------


def test_no_existing_file_writes_the_empty_render_and_no_backup(target):  # I1
    written = _install(target)
    assert written.read_text(encoding="utf-8") == _empty_render(target)
    assert sorted(_listing(target)) == ["AGENTS.md", "CLAUDE.md"]


def test_a_file_without_markers_is_kept_whole_above_the_block(target):  # I2
    original = "intro\n# Mine\n\nmy rule\n"
    (target / "AGENTS.md").write_text(original, encoding="utf-8")
    written = _install(target)
    text = written.read_text(encoding="utf-8")
    assert text == _with_user_content(
        _empty_render(target), h1="# d info and directives", before="intro\n\nmy rule", after=""
    )
    assert (target / "backup.AGENTS.md").read_text(encoding="utf-8") == original


def test_a_stale_block_is_replaced_and_the_user_content_kept_exactly(target):  # I3
    prior = f"# Old title\n\nmine above\n  indented\n\n{BEGIN}\nstale block\n{END}\n\nmine below\n\ttabbed  \n"
    (target / "AGENTS.md").write_text(prior, encoding="utf-8")
    text = _install(target).read_text(encoding="utf-8")
    assert text == _with_user_content(
        _empty_render(target),
        h1="# d info and directives",
        before="mine above\n  indented",
        after="mine below\n\ttabbed  ",
    )
    assert (target / "backup.AGENTS.md").read_text(encoding="utf-8") == prior


@pytest.mark.parametrize(
    "prior",
    [None, "my own rules\n", f"# T\nabove\n{BEGIN}\nold\n{END}\nbelow\n"],
    ids=["none", "no-markers", "valid-pair"],
)
def test_installing_twice_changes_nothing(target, prior):  # I4
    if prior is not None:
        (target / "AGENTS.md").write_text(prior, encoding="utf-8")
    written = _install(target)
    first = _listing(target)
    mtimes = {path.name: path.stat().st_mtime_ns for path in target.iterdir()}
    _install(target)
    assert _listing(target) == first
    assert {path.name: path.stat().st_mtime_ns for path in target.iterdir()} == mtimes
    assert written.read_text(encoding="utf-8").count("vvv-adjagent") == 1


@pytest.mark.parametrize(
    "existing",
    [
        f"a\n{BEGIN}\nb\n",
        f"a\n{END}\nb\n",
        f"a\n{END}\nb\n{BEGIN}\nc\n",
        f"{BEGIN}\nx\n{END}\n{BEGIN}\ny\n{END}\n",
        f"{BEGIN}\n{BEGIN}\nx\n{END}\n",
    ],
    ids=["begin-only", "end-only", "end-before-begin", "two-pairs", "two-begins-one-end"],
)
def test_malformed_markers_are_refused_and_nothing_written(target, existing):  # I5
    (target / "AGENTS.md").write_text(existing, encoding="utf-8")
    before = _listing(target)
    with pytest.raises(InputError, match="malformed adjagent markers"):
        _install(target)
    assert _listing(target) == before


@pytest.mark.parametrize(
    "begin, end",
    [
        (
            "<!-- vvv-adjagent something else entirely revision[ffffff] adjagent-vvv -->",
            "<!-- ^^^-adjagent and more adjagent-^^^ -->",
        ),
        (f"  \t{BEGIN}   ", f"\t{END} \t"),
    ],
    ids=["other-sha-and-middle", "surrounding-whitespace"],
)
def test_markers_are_recognised_by_their_ends(target, begin, end):  # I6
    (target / "AGENTS.md").write_text(f"mine above\n{begin}\nold\n{end}\nmine below\n", encoding="utf-8")
    text = _install(target).read_text(encoding="utf-8")
    assert text == _with_user_content(
        _empty_render(target), h1="# d info and directives", before="mine above", after="mine below"
    )


def test_user_text_is_never_rendered_or_searched(target):  # I7
    tricky = "uses @!dyn.tier-low!@ and a lone !@ and a whole chunk marker @!full-warning-set!@"
    (target / "AGENTS.md").write_text(f"{tricky}\n{BEGIN}\nold\n{END}\n{tricky}\n", encoding="utf-8")
    text = _install(target).read_text(encoding="utf-8")
    assert text == _with_user_content(_empty_render(target), h1="# d info and directives", before=tricky, after=tricky)


def test_trim_drops_edge_blank_lines_and_keeps_the_interior():  # I8
    assert agents_file.trim_user_content("  \n\n a\n\n \t\nb  \n\n  \n") == " a\n\n \t\nb  "


# --- the scope name ----------------------------------------------------------


def _plant_harness(tmp_path: Path, user_harness_dir: str) -> Path:
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir()
    (harness_dir / "x.toml").write_text(HARNESS.format(user_harness_dir=user_harness_dir), encoding="utf-8")
    return harness_dir


@pytest.mark.parametrize(
    "case, scope",
    [
        ("global-absolute", "Global"),
        ("global-home", "Global"),
        ("unreadable-git-directory", "proj"),
        ("unreadable-git-file", "proj"),
        ("plain", "proj"),
    ],
)
def test_the_scope_name(tmp_path, monkeypatch, case, scope):  # I9
    directory = tmp_path / ("home/.x" if case.startswith("global") else "proj")
    directory.mkdir(parents=True)
    user_harness_dir = str(tmp_path / "home/.x") if case == "global-absolute" else "~/.x"
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    if case == "unreadable-git-directory":
        (directory / ".git").mkdir()
    elif case == "unreadable-git-file":
        (directory / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    harness_dir = _plant_harness(tmp_path, user_harness_dir)
    agents_file.install_agents_file("x", directory, CLEAN, harness_dir=harness_dir)
    directives = "X.md" if scope == "Global" else "AGENTS.md"
    assert (directory / directives).read_text(encoding="utf-8").startswith(f"# {scope} info and directives\n")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _repo(path: Path, *remotes: tuple[str, str]) -> Path:
    """A fresh repository at `path` with one empty commit and `remotes`."""
    path.mkdir(parents=True)
    _git(path, "init", "--quiet")
    _git(path, "commit", "--quiet", "--allow-empty", "-m", "c")
    for name, url in remotes:
        _git(path, "remote", "add", name, url)
    return path


@pytest.mark.parametrize(
    "url, name",
    [
        ("git@github.com:owner/name.git", "name"),
        ("git@host:name.git", "name"),
        ("https://github.com/owner/name.git", "name"),
        ("https://github.com/owner/name/", "name"),
        ("ssh://git@host:22/owner/name.git", "name"),
        ("/srv/repos/name.git/", "name"),
        ("../name", "name"),
    ],
)
def test_repository_name_from_url(url, name):
    assert agents_file.repository_name_from_url(url) == name


def test_project_scope_is_the_origin_repository_name(tmp_path):
    # Cloned into a differently-named directory: origin wins over the directory.
    repo = _repo(tmp_path / "checkout", ("origin", "git@github.com:owner/scp-name.git"))
    assert agents_file.agents_file_scope_name("~/.x", repo) == "scp-name"
    _git(repo, "remote", "set-url", "origin", "https://github.com/owner/https-name.git")
    assert agents_file.agents_file_scope_name("~/.x", repo) == "https-name"


def test_a_clone_takes_its_origin_name_not_its_directory(tmp_path):
    source = _repo(tmp_path / "upstream")
    _git(tmp_path, "clone", "--quiet", str(source), "elsewhere")
    assert agents_file.agents_file_scope_name("~/.x", tmp_path / "elsewhere") == "upstream"


@pytest.mark.parametrize("remotes", [(), (("upstream", "https://host/owner/other.git"),)], ids=["none", "not-origin"])
def test_project_scope_without_origin_is_the_directory_name(tmp_path, remotes):
    repo = _repo(tmp_path / "local-name", *remotes)
    assert agents_file.agents_file_scope_name("~/.x", repo) == "local-name"


def test_a_linked_worktree_without_origin_takes_the_main_checkout_name(tmp_path):
    main = _repo(tmp_path / "main-checkout")
    _git(main, "worktree", "add", "--quiet", "--detach", str(tmp_path / "linked"))
    assert (tmp_path / "linked" / ".git").is_file()
    assert agents_file.agents_file_scope_name("~/.x", tmp_path / "linked") == "main-checkout"


def test_a_submodule_without_origin_takes_its_own_directory_name(tmp_path):
    library = _repo(tmp_path / "library")
    superproject = _repo(tmp_path / "super")
    _git(superproject, "-c", "protocol.file.allow=always", "submodule", "add", "--quiet", str(library), "sub-dir")
    submodule = superproject / "sub-dir"
    _git(submodule, "remote", "remove", "origin")
    assert (submodule / ".git").is_file()
    assert agents_file.agents_file_scope_name("~/.x", submodule) == "sub-dir"


# --- refusals ----------------------------------------------------------------


def test_a_dirty_revision_is_refused_before_anything_is_written(target):  # I10
    (target / "CLAUDE.md").write_text("mine\n", encoding="utf-8")
    before = _listing(target)
    with pytest.raises(InputError, match="uncommitted changes"):
        _install(target, TemplatesRevision(sha="abc1234", dirty=(" M templates/x",)))
    assert _listing(target) == before


@pytest.mark.parametrize("link_name", ["AGENTS.md", "backup.AGENTS.md", "CLAUDE.md"])
def test_a_symlink_at_the_output_its_backup_or_the_native_file_is_refused(tmp_path, target, link_name):  # I11
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    if link_name == "backup.AGENTS.md":
        (target / "AGENTS.md").write_text("mine\n", encoding="utf-8")
    (target / link_name).symlink_to(outside)
    before = _listing_with_links(target)
    with pytest.raises(InputError, match="symlink"):
        _install(target)
    assert outside.read_text(encoding="utf-8") == "outside\n"
    assert _listing_with_links(target) == before


def _plant_template(path: Path, body: str, *resolve_texts: str) -> Path:
    entries = "".join(f'[[outputs._resolve]]\ntext = "{text}"\n' for text in resolve_texts)
    path.write_text(f"+++\n{entries}+++\n{body}", encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "body",
    [
        BODY.replace("<!-- ^^^-adjagent version[@!dyn.gen-short-sha!@] adjagent-^^^ -->\n", ""),
        BODY.replace("@!dyn.existing-user-content-after-rendered!@", "after"),
        BODY.replace(
            "@!dyn.existing-user-content-after-rendered!@",
            "@!dyn.existing-user-content-after-rendered!@\n@!dyn.existing-user-content-after-rendered!@",
        ),
    ],
    ids=["no-end-marker", "no-after-placeholder", "after-twice"],
)
def test_a_template_failing_the_structure_check_is_refused(tmp_path, target, body):  # I12
    template = _plant_template(tmp_path / "t.tmpl.md", body, "@!dyn.agents-file-install-dir-arg!@/X.md")
    harness_dir = _plant_harness(tmp_path, "~/.x")
    with pytest.raises(InputError, match=r"t\.tmpl\.md"):
        agents_file.install_agents_file("x", target, CLEAN, template=template, harness_dir=harness_dir)
    assert list(target.iterdir()) == []


def test_the_cli_with_one_positional_exits_2(tmp_path):  # I13
    result = subprocess.run(
        [sys.executable, "-m", "gen_defs", "install-agents-file", "claude"],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(_REPO_ROOT)},
    )
    assert result.returncode == 2
    assert "DIR" in result.stderr


@pytest.mark.parametrize("redirected", [False, True], ids=["agents-md", "agents-md-redirected"])
def test_a_malformed_output_leaves_every_other_output_unwritten(tmp_path, target, redirected):  # I14
    # Every output is planned before any is written, a redirect's target
    # included, so one refusal writes nothing.
    template = _plant_template(
        tmp_path / "t.tmpl.md",
        BODY,
        "@!dyn.agents-file-install-dir-arg!@/X.md",
        "@!dyn.agents-file-install-dir-arg!@/ALSO.md",
    )
    if redirected:
        (target / "AGENTS.md").write_text("@TARGET.md\n", encoding="utf-8")
    (target / "ALSO.md").write_text(f"{BEGIN}\nunclosed\n", encoding="utf-8")
    before = _listing(target)
    with pytest.raises(InputError, match="malformed adjagent markers"):
        agents_file.install_agents_file(
            "x", target, CLEAN, template=template, harness_dir=_plant_harness(tmp_path, "~/.x")
        )
    assert _listing(target) == before


def test_the_backup_rolls_to_the_previous_install(target):  # I15
    (target / "AGENTS.md").write_text("mine\n", encoding="utf-8")
    first = _install(target).read_text(encoding="utf-8")
    second = _install(target, LATER).read_text(encoding="utf-8")
    assert second != first
    assert (target / "backup.AGENTS.md").read_text(encoding="utf-8") == first
    assert _marker_lines(second) and all("version[def5678]" in line for line in _marker_lines(second))


# --- where the directives land ----------------------------------------------------


@pytest.fixture
def global_dir(tmp_path, monkeypatch) -> Path:
    """claude's user-global directory, under a HOME planted in `tmp_path`."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    directory = tmp_path / "home" / ".claude"
    directory.mkdir(parents=True)
    return directory


def test_a_global_install_writes_the_native_file_and_no_redirect(global_dir):
    agents_file.install_agents_file("claude", global_dir, CLEAN)
    assert sorted(_listing(global_dir)) == ["CLAUDE.md"]
    text = (global_dir / "CLAUDE.md").read_text(encoding="utf-8")
    assert text.startswith("# Global info and directives\n")


def test_a_global_native_redirect_is_still_followed(global_dir):
    (global_dir / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    agents_file.install_agents_file("claude", global_dir, CLEAN)
    assert (global_dir / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"
    assert (global_dir / "AGENTS.md").read_text(encoding="utf-8").startswith("# Global info and directives\n")


def test_a_project_install_writes_agents_md_and_creates_the_claude_md_redirect(target):
    (target / ".git").mkdir()
    _install(target)
    assert (target / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"
    assert (target / "AGENTS.md").read_text(encoding="utf-8").startswith("# d info and directives\n")


NATIVE_REDIRECT = "\n  @AGENTS.md  \n\n"


@pytest.mark.parametrize("native", [NATIVE_REDIRECT, "@./AGENTS.md"], ids=["padded", "dot-slash"])
def test_an_existing_native_redirect_is_left_alone(target, native):
    (target / "CLAUDE.md").write_text(native, encoding="utf-8")
    (target / "AGENTS.md").write_text("my rule\n", encoding="utf-8")
    written = _install(target)
    assert (target / "CLAUDE.md").read_text(encoding="utf-8") == native
    assert not (target / "backup.CLAUDE.md").exists()
    assert written.read_text(encoding="utf-8") == _with_user_content(
        _empty_render(target), h1="# d info and directives", before="my rule", after=""
    )


@pytest.mark.parametrize(
    "native",
    ["my own rules\n", "@OTHER.md\n", "@AGENTS.md\nmy rule\n", f"# T\n{BEGIN}\nold\n{END}\n"],
    ids=["plain-text", "redirect-elsewhere", "import-and-text", "marked-block"],
)
def test_a_native_file_with_content_is_refused_and_nothing_written(target, native):
    (target / "CLAUDE.md").write_text(native, encoding="utf-8")
    before = _listing(target)
    with pytest.raises(
        InputError, match=r"move its content into .*AGENTS\.md and replace it with '@AGENTS\.md' by hand"
    ):
        _install(target)
    assert _listing(target) == before


def test_an_opencode_project_install_writes_agents_md_and_no_redirect(target):
    (target / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    agents_file.install_agents_file("opencode", target, CLEAN)
    assert sorted(_listing(target)) == [".git", "AGENTS.md"]
    assert (target / "AGENTS.md").read_text(encoding="utf-8").startswith("# d info and directives\n")


def test_agents_md_redirecting_back_to_an_absent_native_file_is_refused(target):
    (target / "AGENTS.md").write_text("@CLAUDE.md\n", encoding="utf-8")
    before = _listing(target)
    with pytest.raises(InputError, match="one file twice"):
        _install(target)
    assert _listing(target) == before


# --- redirects -----------------------------------------------------------------

REDIRECT = "\n  @RULES.md  \n\n"


@pytest.mark.parametrize(
    "prior, before, after",
    [
        (f"mine above\n{BEGIN}\nold\n{END}\nmine below\n", "mine above", "mine below"),
        ("# Theirs\nmy rule\n", "my rule", ""),
        (None, "", ""),
    ],
    ids=["target-with-markers", "target-without-markers", "target-missing"],
)
def test_a_redirect_installs_into_its_target_and_is_never_written(target, prior, before, after):
    redirect = target / "AGENTS.md"
    redirect.write_text(REDIRECT, encoding="utf-8")
    if prior is not None:
        (target / "RULES.md").write_text(prior, encoding="utf-8")
    _install(target)
    assert redirect.read_text(encoding="utf-8") == REDIRECT
    assert not (target / "backup.AGENTS.md").exists()
    assert (target / "RULES.md").read_text(encoding="utf-8") == _with_user_content(
        _empty_render(target), h1="# d info and directives", before=before, after=after
    )
    assert ((target / "backup.RULES.md").exists()) is (prior is not None)


def test_reinstalling_through_a_redirect_changes_nothing(target):
    (target / "AGENTS.md").write_text(REDIRECT, encoding="utf-8")
    (target / "RULES.md").write_text("my rule\n", encoding="utf-8")
    _install(target)
    first = _listing(target)
    mtimes = {path.name: path.stat().st_mtime_ns for path in target.iterdir()}
    _install(target)
    assert _listing(target) == first
    assert {path.name: path.stat().st_mtime_ns for path in target.iterdir()} == mtimes


@pytest.mark.parametrize(
    "files, message",
    [
        ({"AGENTS.md": "@RULES.md\n", "RULES.md": "@OTHER.md\n"}, "more than one hop"),
        ({"AGENTS.md": "@AGENTS.md\n"}, "more than one hop"),
        ({"CLAUDE.md": "@AGENTS.md\n", "AGENTS.md": "@CLAUDE.md\n"}, "more than one hop"),
        ({"AGENTS.md": "@../outside.md\n"}, "outside"),
        ({"AGENTS.md": "@linked/AGENTS.md\n"}, "outside"),
        ({"AGENTS.md": "@absent/AGENTS.md\n"}, "directory does not exist"),
    ],
    ids=[
        "two-hops",
        "self",
        "back-to-the-native-redirect",
        "dotdot-outside",
        "symlinked-dir-outside",
        "missing-directory",
    ],
)
def test_a_redirect_that_cannot_be_followed_is_refused(tmp_path, target, files, message):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (target / "linked").symlink_to(elsewhere)
    for name, text in files.items():
        (target / name).write_text(text, encoding="utf-8")
    before = _listing_with_links(target)
    with pytest.raises(InputError, match=message):
        _install(target)
    assert _listing_with_links(target) == before
    assert list(elsewhere.iterdir()) == []
    assert not (tmp_path / "outside.md").exists()


@pytest.mark.parametrize("link_name", ["RULES.md", "backup.RULES.md"])
def test_a_symlink_at_the_redirect_target_or_its_backup_is_refused(target, link_name):
    (target / "AGENTS.md").write_text(REDIRECT, encoding="utf-8")
    (target / "REAL.md").write_text("real\n", encoding="utf-8")
    if link_name != "RULES.md":
        (target / "RULES.md").write_text("mine\n", encoding="utf-8")
    (target / link_name).symlink_to(target / "REAL.md")
    with pytest.raises(InputError, match="symlink"):
        _install(target)
    assert (target / "REAL.md").read_text(encoding="utf-8") == "real\n"
    assert not (target / "CLAUDE.md").exists()


@pytest.mark.parametrize(
    "text", ["@RULES.md\n@OTHER.md\n", "@RULES.md\nmy rule\n"], ids=["two-imports", "import-and-text"]
)
def test_more_than_a_lone_import_is_an_ordinary_file(target, text):
    (target / "AGENTS.md").write_text(text, encoding="utf-8")
    written = _install(target)
    assert written.read_text(encoding="utf-8") == _with_user_content(
        _empty_render(target), h1="# d info and directives", before=text.rstrip("\n"), after=""
    )
    assert not (target / "RULES.md").exists()


def _listing_with_links(directory: Path) -> dict[str, bytes | str]:
    return {
        path.name: f"-> {path.readlink()}" if path.is_symlink() else path.read_bytes() for path in directory.iterdir()
    }
