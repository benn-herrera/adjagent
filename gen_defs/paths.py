"""gen_defs — repo anchoring, path display."""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"
SHARED_CHUNKS = TEMPLATES_DIR / "shared-chunks.toml"
FAMILY_DIR = TEMPLATES_DIR / "family"
TEMPLATE_SUFFIX = ".tmpl.md"
FAMILY_SUFFIX = ".toml"
HARNESS_DIR = TEMPLATES_DIR / "harness"
AGENTS_FILE_TEMPLATE = HARNESS_DIR / f"AGENTS{TEMPLATE_SUFFIX}"


def rel(path: Path) -> str:
    """A path as printed and matched everywhere: relative to the repo root
    when it lies inside it, resolved-absolute otherwise (ROOT and --family may
    point anywhere)."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        try:
            return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
        except ValueError:
            return path.resolve().as_posix()
