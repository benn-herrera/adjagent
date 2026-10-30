"""The two guardrail implementations — opencode's `guardrail.ts` and claude's `guardrail.pl` — held to
one case table, `tests/guardrail_cases.json`: every case runs through each implementation that has its
tool, each in a fresh root holding the case's files and a copy of the script staged in the harness
directory, and each implementation's reason must equal the table's.

A case is a shell command (`command`) or a file-tool call (`tool`, named as Claude names it or, for a
tool only opencode has, as opencode does, with `input` in that tool's argument names). In a case,
`@scratch@` stands for the harness's scratch directory, `@harness@` for its harness directory and
`@root@` for the case's root, substituted in the command, the input, the files, the links, the working
directory and the expected reason. `files` are created; `links` maps a path to a symlink target. A
case's optional `cwd` is the session's working directory, relative to the root and defaulting to it;
claude receives it as the input `cwd` beside `CLAUDE_PROJECT_DIR` set to the root, as Claude Code
sends both, and opencode's shell receives it as `workdir`. The TypeScript side runs under `bun`; a
missing `bun` fails rather than skips, because a skip would hide drift between the two.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from adjagent.harness import Harness
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
_CASE_FIELDS = {"command", "tool", "input", "reason", "files", "links", "cwd"}
_INDEX_REASON_HEAD = "kb-root/.index/ holds kbase's records"

# Each Claude tool's opencode name, None where opencode has no counterpart; the Claude argument
# names opencode spells otherwise, None where it has none; and the tools only opencode has.
_OPENCODE_TOOLS = {
    "Bash": "bash",
    "Read": "read",
    "Write": "write",
    "Edit": "edit",
    "Grep": "grep",
    "Glob": "glob",
    "NotebookEdit": None,
}
_OPENCODE_ARGS = {"file_path": "path", "glob": "include", "type": None}
_OPENCODE_ONLY_TOOLS = {"patch"}


def _tool(case: dict) -> str:
    return case.get("tool", "Bash")


def _tool_input(case: dict) -> dict:
    return case["input"] if "tool" in case else {"command": case["command"]}


def _opencode_tool(tool: str) -> str | None:
    return tool if tool in _OPENCODE_ONLY_TOOLS else _OPENCODE_TOOLS[tool]


_PL_INDEXES = [i for i, case in enumerate(_CASES) if _tool(case) in _OPENCODE_TOOLS]
_TS_INDEXES = [i for i, case in enumerate(_CASES) if _opencode_tool(_tool(case)) is not None]


def _reason(message: str) -> str:
    """The reason a block message carries: the text after the fixed `Blocked: ` prefix, and for a
    mutation, before the last `. Use the `, where both implementations' fixed suffix starts. A target
    can itself hold `. `, so the strip is on the fixed text, never a split on `.`. A `.index/`
    refusal carries no suffix."""
    assert message.startswith("Blocked: "), message
    rest = message[len("Blocked: ") :]
    return rest if rest.startswith(_INDEX_REASON_HEAD) else rest[: rest.rindex(". Use the ")]


def _fill(text: str | None, harness: Harness, root: Path) -> str | None:
    if text is None:
        return None
    return (
        text.replace("@scratch@", harness.project_temp_dir)
        .replace("@harness@", harness.project_harness_dir)
        .replace("@root@", str(root))
    )


def _case_root(root: Path, case: dict, harness: Harness, script: Path) -> tuple[Path, Path, Path, dict]:
    """The case's root, holding its files, its links and a copy of `script` at the path it takes in
    the harness directory; its working directory, created inside it; the staged script; and the
    case's tool input, filled."""
    root.mkdir()
    for rel in case.get("files", []):
        path = root / _fill(rel, harness, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n", encoding="utf-8")
    for rel, target in case.get("links", {}).items():
        path = root / _fill(rel, harness, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(_fill(target, harness, root))
    staged = root / harness.project_harness_dir / script.relative_to(script.parents[1])
    staged.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(script, staged)
    cwd = root / _fill(case.get("cwd", "."), harness, root)
    cwd.mkdir(parents=True, exist_ok=True)
    tool_input = {arg: _fill(value, harness, root) for arg, value in _tool_input(case).items()}
    return root, cwd, staged, tool_input


def _run_perl(
    stdin: str, *perl_args: str, project_dir: Path | None = None, script: Path = _PERL_HOOK
) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return subprocess.run(
        ["perl", *perl_args, str(script)],
        input=stdin,
        capture_output=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


def _hook_input(tool: str, tool_input: dict, cwd: Path | None) -> str:
    payload: dict = {"tool_name": tool, "tool_input": tool_input}
    if cwd is not None:
        payload["cwd"] = str(cwd)
    return json.dumps(payload)


def _opencode_call(tool: str, tool_input: dict, root: Path, cwd: Path) -> dict:
    """A case's call as opencode makes it: its tool, its arguments renamed, and a shell's working
    directory as `workdir`, sent only where it is not the root, as opencode sends none when the call
    sets none."""
    args = {
        renamed: value
        for arg, value in tool_input.items()
        if (renamed := _OPENCODE_ARGS.get(arg, arg)) is not None
    }
    name = _opencode_tool(tool)
    if name == "bash" and cwd != root:
        args["workdir"] = str(cwd)
    return {"tool": name, "input": args}


@pytest.fixture(scope="module")
def ts_results(tmp_path_factory: pytest.TempPathFactory) -> dict[int, tuple[Path, str | None]]:
    """Each opencode case's root and its reason under `guardrail.ts`, by table index, from one `bun`
    run over the table."""
    if shutil.which("bun") is None:
        pytest.fail("bun is not on PATH: the guardrail.ts side of the case table cannot run without it")
    base = tmp_path_factory.mktemp("ts")
    runs = []
    for i in _TS_INDEXES:
        case = _CASES[i]
        root, cwd, staged, tool_input = _case_root(base / str(i), case, OPENCODE, _TS_PLUGIN)
        runs.append({"root": str(root), "script": str(staged), **_opencode_call(_tool(case), tool_input, root, cwd)})
    done = subprocess.run(
        ["bun", str(_TESTS / "guardrail_ts_runner.ts")],
        input=json.dumps(runs),
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == 0, done.stderr
    messages = json.loads(done.stdout)
    assert len(messages) == len(runs)
    return {
        i: (Path(run["root"]), None if m is None else _reason(m))
        for i, run, m in zip(_TS_INDEXES, runs, messages)
    }


def _id(index: int) -> str:
    case = _CASES[index]
    label = case["command"].splitlines()[0] if "command" in case else f"{case['tool']} {json.dumps(case['input'])}"
    return f"{index}-{label}"


def test_guardrail_cases_carry_only_known_fields() -> None:
    """A misspelt field or tool would be ignored and its case run as something else, so the table is
    held to the fields the harness reads, and each case to one shell command or one known tool."""
    for i, case in enumerate(_CASES):
        assert set(case) <= _CASE_FIELDS, (i, set(case) - _CASE_FIELDS)
        assert ("command" in case) != ("tool" in case), i
        assert ("tool" in case) == ("input" in case), i
        assert _tool(case) in _OPENCODE_TOOLS.keys() | _OPENCODE_ONLY_TOOLS, (i, _tool(case))


def test_guardrail_matcher_names_exactly_the_claude_tools_the_case_table_covers() -> None:
    """A tool the matcher sends to the hook with no case is untested, and a case for a tool the
    matcher omits tests a call the hook never sees."""
    matcher = set(CLAUDE.guardrail.entry(CLAUDE.project_harness_dir)["matcher"].split("|"))
    assert matcher == {_tool(case) for case in _CASES if _tool(case) in _OPENCODE_TOOLS}


@pytest.mark.parametrize(
    ("script", "harness_scratch", "scratch_list"),
    [
        (_PERL_HOOK, _PERL_SCRATCH, r"^my @scratch = \((.*)\);$"),
        (_TS_PLUGIN, _TS_SCRATCH, r"^const scratch = \[(.*)\]$"),
    ],
    ids=["pl", "ts"],
)
def test_guardrail_scratch_list_holds_its_harness_temp_dir(
    script: Path, harness_scratch: str, scratch_list: str
) -> None:
    """Each script spells its scratch trees itself; the harness's temp directory, which the case table
    exempts as `@scratch@`, must be among them."""
    found = re.search(scratch_list, script.read_text(encoding="utf-8"), re.MULTILINE)
    assert found is not None, scratch_list
    assert re.findall(r"""["']([^"']*)["']""", found.group(1)).count(harness_scratch) == 1


@pytest.mark.parametrize("index", _TS_INDEXES, ids=[_id(i) for i in _TS_INDEXES])
def test_guardrail_ts_gives_the_case_tables_reason(index: int, ts_results: dict[int, tuple[Path, str | None]]) -> None:
    root, reason = ts_results[index]
    assert reason == _fill(_CASES[index]["reason"], OPENCODE, root)


@pytest.mark.parametrize("index", _PL_INDEXES, ids=[_id(i) for i in _PL_INDEXES])
def test_guardrail_pl_gives_the_case_tables_reason(index: int, tmp_path: Path) -> None:
    case = _CASES[index]
    root, cwd, staged, tool_input = _case_root(tmp_path / "root", case, CLAUDE, _PERL_HOOK)
    done = _run_perl(_hook_input(_tool(case), tool_input, cwd), project_dir=root, script=staged)
    expected = _fill(case["reason"], CLAUDE, root)
    if expected is None:
        assert (done.returncode, done.stderr) == (0, "")
    else:
        assert done.returncode == 2, done.stderr
        assert _reason(done.stderr.rstrip("\n")) == expected


def test_guardrail_pl_passes_a_tool_other_than_bash(tmp_path: Path) -> None:
    """The mutation check judges only Bash: the same command under another tool's name is let
    through."""
    done = _run_perl(_hook_input("Edit", {"command": "sed -i 's/a/b/' x.txt"}, tmp_path), project_dir=tmp_path)
    assert (done.returncode, done.stderr) == (0, "")


def test_guardrail_pl_takes_the_input_cwd_as_root_without_claude_project_dir(tmp_path: Path) -> None:
    """With no `CLAUDE_PROJECT_DIR`, the input `cwd` is the root: an absolute target inside that
    directory's scratch is let through, which it is only when scratch resolves against `cwd`."""
    target = tmp_path / _PERL_SCRATCH / "out.txt"
    done = _run_perl(_hook_input("Bash", {"command": f"echo hi > {target}"}, tmp_path))
    assert (done.returncode, done.stderr) == (0, "")


def test_guardrail_pl_fails_as_a_hook_error_never_as_a_block(tmp_path: Path) -> None:
    """Undecodable input, a JSON::PP that cannot load, and a Bash call with no project root each exit
    1, which Claude Code reports without blocking; perl's own exit for any could be 2, which would
    block every Bash call."""
    sed = {"command": "sed -i 's/a/b/' x.txt"}
    garbage = _run_perl("not json")
    broken = tmp_path / "lib/JSON"
    broken.mkdir(parents=True)
    (broken / "PP.pm").write_text("die 'unloadable';\n", encoding="utf-8")
    unloadable = _run_perl(_hook_input("Bash", sed, tmp_path), f"-I{tmp_path / 'lib'}")
    rootless = _run_perl(_hook_input("Bash", sed, None))
    assert garbage.returncode == 1 and garbage.stderr.startswith("guardrail: ")
    assert unloadable.returncode == 1 and "unloadable" in unloadable.stderr
    assert rootless.returncode == 1 and rootless.stderr.startswith("guardrail: no project root")
