"""`devtools/scripts/mage-dist.sh`, driven through its command line with the stub `gpg` of
`tests/stubs/` on PATH: no key, no real keyring. Each build gets its own work directory.
"""

import functools
import json
import os
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
STUBS = Path(__file__).parent / "stubs"
SCRIPT = REPO / "devtools/scripts/mage-dist.sh"


@functools.cache
def _version() -> str:
    return subprocess.run(
        ["python3", "-m", "adjagent", "version"],
        cwd=REPO, env={**os.environ, "PYTHONPATH": str(REPO)}, capture_output=True, encoding="utf-8", check=True,
    ).stdout.strip()


def _names(out: Path) -> dict[str, Path]:
    v = _version()
    return {
        "tgz": out / f"adjagent-mage-v{v}.tgz",
        "tgz_asc": out / f"adjagent-mage-v{v}.tgz.asc",
    }


@dataclass
class Dist:
    root: Path
    build: subprocess.CompletedProcess

    @property
    def names(self) -> dict[str, Path]:
        return _names(self.root / "dist")


def _build(root: Path, extra_path: Path | None = None) -> Dist:
    path = f"{STUBS}{os.pathsep}{os.environ['PATH']}"
    if extra_path is not None:
        path = f"{extra_path}{os.pathsep}{path}"
    env = {
        **os.environ,
        "PATH": path,
        "PROJECT_ROOT": str(REPO),
        "GEN": "adjagent",
        "DIST_DIR": str(root / "dist"),
    }
    done = subprocess.run(
        [str(SCRIPT)], env=env, stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8", check=False
    )
    return Dist(root, done)


def test_build_layout(tmp_path_factory: pytest.TempPathFactory):
    built = _build(tmp_path_factory.mktemp("dist"))
    assert built.build.returncode == 0, built.build.stderr
    names = built.names
    assert all(p.is_file() for p in names.values())
    assert sorted(p.name for p in (built.root / "dist").iterdir()) == sorted(p.name for p in names.values())
    assert built.build.stdout.strip() == "mage-dist: " + " ".join(str(names[k]) for k in ("tgz", "tgz_asc"))
    extracted = built.root / "extracted"
    with tarfile.open(names["tgz"]) as tar:
        members = tar.getmembers()
        entries = [m.name for m in members]
        assert all(n == "adjagent" or n.startswith("adjagent/") for n in entries), entries
        assert not [m.name for m in members if any("xattr" in k for k in m.pax_headers)]
        tar.extractall(extracted, filter="data")
    tools = extracted / "adjagent/skills/kbase/kb-tools"
    assert [p.name for p in tools.iterdir()] == ["runner-snippets"]
    mcp = json.loads((extracted / "adjagent/.mcp.json").read_text(encoding="utf-8"))
    assert mcp["mcpServers"]["kbase"]["command"] == "kbase"
    assert (extracted / "adjagent/CLAUDE.md").is_file()
    assert f"file {names['tgz'].name}\n" in names["tgz_asc"].read_text(encoding="utf-8")


def test_rerun_replaces_the_two_files(tmp_path: Path):
    first = _build(tmp_path)
    assert first.build.returncode == 0, first.build.stderr
    for path in first.names.values():
        path.write_text("stale", encoding="utf-8")
    second = _build(tmp_path)
    assert second.build.returncode == 0, second.build.stderr
    assert all(p.is_file() and p.read_text(encoding="latin-1") != "stale" for p in second.names.values())
    assert not (tmp_path / "dist/stage").exists()


def test_failed_signing_leaves_neither_output_nor_stage(tmp_path: Path):
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "gpg").write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    (fake / "gpg").chmod(0o755)
    built = _build(tmp_path, extra_path=fake)
    assert built.build.returncode != 0
    assert list((tmp_path / "dist").iterdir()) == []


def test_bad_version_removes_and_writes_nothing(tmp_path: Path):
    out = tmp_path / "dist"
    (out / "stage").mkdir(parents=True)
    (out / "stage/keep.txt").write_text("keep", encoding="utf-8")
    for path in _names(out).values():
        path.write_text("keep", encoding="utf-8")
    before = {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "python3").write_text("#!/usr/bin/env bash\nprintf '1.2\\n'\n", encoding="utf-8")
    (fake / "python3").chmod(0o755)
    built = _build(tmp_path, extra_path=fake)
    assert built.build.returncode != 0
    assert "not <major>.<minor>.<patch>" in built.build.stderr
    assert {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()} == before
