"""The two guardrail implementations — opencode's `guardrail.ts` and claude's `guardrail.pl` — held to
one case table, `tests/guardrail_cases.json`: every case runs through both, each in a fresh root
holding the case's files, and each implementation's reason must equal the table's.

In a case, `@scratch@` stands for the harness's scratch directory and `@root@` for the case's root,
substituted in the command, the files, the working directory and the expected reason. A case's
optional `cwd` is the session's working directory, relative to the root and defaulting to it; claude
receives it as the input `cwd` beside `CLAUDE_PROJECT_DIR` set to the root, as Claude Code sends
both, and opencode's runner receives it in each run. The TypeScript side runs under `bun`; a missing
`bun` fails rather than skips, because a skip would hide drift between the two.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from adjagent.harnesses.claude import HARNESS as CLAUDE
from adjagent.harnesses.opencode import HARNESS as OPENCODE
from adjagent.install import HARNESS_RESOURCES_SOURCE, REPO_ROOT

_RESOURCES = REPO_ROOT / HARNESS_RESOURCES_SOURCE
_PERL_HOOK = _RESOURCES / "claude/hooks/guardrail.pl"
_TS_PLUGIN = _RESOURCES / "opencode/plugins/guardrail.ts"
_TESTS = Path(__file__).parent
_CASES = json.loads((_TESTS / "guardrail_cases.json").read_text(encoding="utf-8"))
_PERL_SCRATCH = CLAUDE.project_temp_dir
_TS_SCRATCH = OPENCODE.project_temp_dir
_CASE_FIELDS = {"command", "reason", "files", "cwd"}


def _reason(message: str) -> str:
    """The reason a block message carries: the text between the fixed `Blocked: ` prefix and the last
    `. Use the `, where both implementations' fixed suffix starts. A target can itself hold `. `, so
    the strip is on the fixed text, never a split on `.`."""
    assert message.startswith("Blocked: "), message
    return message[len("Blocked: ") : message.rindex(". Use the ")]


def _fill(text: str | None, scratch: str, root: Path) -> str | None:
    return None if text is None else text.replace("@scratch@", scratch).replace("@root@", str(root))


def _case_root(root: Path, case: dict, scratch: str) -> tuple[Path, Path]:
    """The case's root, holding its files, and its working directory, created inside it."""
    root.mkdir()
    for rel in case.get("files", []):
        path = root / _fill(rel, scratch, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n", encoding="utf-8")
    cwd = root / _fill(case.get("cwd", "."), scratch, root)
    cwd.mkdir(parents=True, exist_ok=True)
    return root, cwd


def _run_perl(stdin: str, *perl_args: str, project_dir: Path | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return subprocess.run(
        ["perl", *perl_args, str(_PERL_HOOK)],
        input=stdin,
        capture_output=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


def _bash_input(command: str, cwd: Path | None, tool: str = "Bash") -> str:
    payload: dict = {"tool_name": tool, "tool_input": {"command": command}}
    if cwd is not None:
        payload["cwd"] = str(cwd)
    return json.dumps(payload)


@pytest.fixture(scope="module")
def ts_results(tmp_path_factory: pytest.TempPathFactory) -> dict[int, tuple[Path, str | None]]:
    """Each opencode case's root and its reason under `guardrail.ts`, by table index, from one `bun`
    run over the table."""
    if shutil.which("bun") is None:
        pytest.fail("bun is not on PATH: the guardrail.ts side of the case table cannot run without it")
    base = tmp_path_factory.mktemp("ts")
    dirs = [_case_root(base / str(i), case, _TS_SCRATCH) for i, case in enumerate(_CASES)]
    runs = [
        {"root": str(root), "cwd": str(cwd), "command": _fill(case["command"], _TS_SCRATCH, root)}
        for case, (root, cwd) in zip(_CASES, dirs)
    ]
    done = subprocess.run(
        ["bun", str(_TESTS / "guardrail_ts_runner.ts"), str(_TS_PLUGIN)],
        input=json.dumps(runs),
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == 0, done.stderr
    messages = json.loads(done.stdout)
    assert len(messages) == len(runs)
    return {i: (root, None if m is None else _reason(m)) for i, ((root, _), m) in enumerate(zip(dirs, messages))}


_IDS = [f"{i}-{case['command'].splitlines()[0]}" for i, case in enumerate(_CASES)]


def test_guardrail_cases_carry_only_known_fields() -> None:
    """A misspelt field would be ignored and its case run as something else, so the table is held to
    the fields the harness reads."""
    for i, case in enumerate(_CASES):
        assert set(case) <= _CASE_FIELDS, (i, set(case) - _CASE_FIELDS)


@pytest.mark.parametrize(
    ("script", "harness_scratch", "scratch_list"),
    [
        (_PERL_HOOK, _PERL_SCRATCH, r"^my @scratch = \((.*)\);$"),
        (_TS_PLUGIN, _TS_SCRATCH, r"^const scratch = \[(.*)\]$"),
    ],
    ids=["pl", "ts"],
)
def test_guardrail_scratch_list_holds_its_harness_temp_dir(script: Path, harness_scratch: str, scratch_list: str) -> None:
    """Each script spells its scratch trees itself; the harness's temp directory, which the case table
    exempts as `@scratch@`, must be among them."""
    found = re.search(scratch_list, script.read_text(encoding="utf-8"), re.MULTILINE)
    assert found is not None, scratch_list
    assert re.findall(r"""["']([^"']*)["']""", found.group(1)).count(harness_scratch) == 1


@pytest.mark.parametrize("index", range(len(_CASES)), ids=_IDS)
def test_guardrail_ts_gives_the_case_tables_reason(
    index: int, ts_results: dict[int, tuple[Path, str | None]]
) -> None:
    root, reason = ts_results[index]
    assert reason == _fill(_CASES[index]["reason"], _TS_SCRATCH, root)


@pytest.mark.parametrize("index", range(len(_CASES)), ids=_IDS)
def test_guardrail_pl_gives_the_case_tables_reason(index: int, tmp_path: Path) -> None:
    case = _CASES[index]
    root, cwd = _case_root(tmp_path / "root", case, _PERL_SCRATCH)
    done = _run_perl(_bash_input(_fill(case["command"], _PERL_SCRATCH, root), cwd), project_dir=root)
    expected = _fill(case["reason"], _PERL_SCRATCH, root)
    if expected is None:
        assert (done.returncode, done.stderr) == (0, "")
    else:
        assert done.returncode == 2, done.stderr
        assert _reason(done.stderr.rstrip("\n")) == expected


def test_guardrail_pl_passes_a_tool_other_than_bash(tmp_path: Path) -> None:
    """Only a Bash call is judged: the same command under another tool's name is let through."""
    done = _run_perl(_bash_input("sed -i 's/a/b/' x.txt", tmp_path, tool="Edit"), project_dir=tmp_path)
    assert (done.returncode, done.stderr) == (0, "")


def test_guardrail_pl_takes_the_input_cwd_as_root_without_claude_project_dir(tmp_path: Path) -> None:
    """With no `CLAUDE_PROJECT_DIR`, the input `cwd` is the root: an absolute target inside that
    directory's scratch is let through, which it is only when scratch resolves against `cwd`."""
    target = tmp_path / _PERL_SCRATCH / "out.txt"
    done = _run_perl(_bash_input(f"echo hi > {target}", tmp_path))
    assert (done.returncode, done.stderr) == (0, "")


def test_guardrail_pl_fails_as_a_hook_error_never_as_a_block(tmp_path: Path) -> None:
    """Undecodable input, a JSON::PP that cannot load, and a Bash call with no project root each exit
    1, which Claude Code reports without blocking; perl's own exit for any could be 2, which would
    block every Bash call."""
    garbage = _run_perl("not json")
    broken = tmp_path / "lib/JSON"
    broken.mkdir(parents=True)
    (broken / "PP.pm").write_text("die 'unloadable';\n", encoding="utf-8")
    unloadable = _run_perl(_bash_input("sed -i 's/a/b/' x.txt", tmp_path), f"-I{tmp_path / 'lib'}")
    rootless = _run_perl(_bash_input("sed -i 's/a/b/' x.txt", None))
    assert garbage.returncode == 1 and garbage.stderr.startswith("guardrail: ")
    assert unloadable.returncode == 1 and "unloadable" in unloadable.stderr
    assert rootless.returncode == 1 and rootless.stderr.startswith("guardrail: no project root")
