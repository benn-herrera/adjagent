"""House practice: the build system, new-project setup, project documents, data
formats, dependencies and logging."""

from typing import Literal

from adjagent.context import Render


# outputs= is a NOUN PHRASE, not the sentence around it: a whole-sentence
# argument at the call sites that override it would be more argument than text.
# go-coder, rust-coder and the C family are NOT on this chunk: each states the
# rule inverted (the operations go through the targets, rather than use the
# targets for the operations) inside a paragraph that runs on into
# language-specific material, and they share build-system-lead instead.
def build_system(
    *, direct: str, ops: str = "build, test, and integration", outputs: str = "a designated output directory"
) -> str:
    return rf"""**Build system**: if the project has a Makefile or justfile, use its targets/recipes (whichever runner the project has chosen) for all {ops} operations — never invoke {direct} directly when a target covers it. Build outputs belong in {outputs}, not scattered in the source tree."""


def new_project_setup(ctx: Render) -> str:
    temp = ctx.harness.project_temp_dir
    home = ctx.harness.project_harness_dir
    return rf"""**New project setup**: creating a project from scratch means creating its task-runner entry point WITH the first code, never retrofitting it later. A `justfile` by default; a `Makefile` only where the top-level utility commands genuinely need dependency management — file targets with staleness rules, generated content that must rebuild when its sources change, recursive sub-builds (`$(MAKE) -C`). Aliasing commands is never reason enough to choose Make over just. Standard targets: `build`/`rebuild`, `test`, an integration-test target, and `generate`/`regenerate` wherever generation is a distinct step the build does not own — CMake project generation in the C++/CMake family, `go generate` codegen in Go, code/data generation in Python (Rust and Zig typically need none: `build.rs`/`build.zig` own generation). Omit a target only where the task genuinely does not exist for the project — never because wiring it up is effort. No project may ever require the agent or the developer to execute a major project-iteration task from a naked command line with correctly-recalled values: the target is the memory. Also created at project birth: `{temp}/`, with a `{temp}/` entry in the root `.gitignore` — the project's scratch space (throwaway builds, probe harnesses, captured output), pre-made so the scratch-space rule never stalls on a missing directory. It lives beside `{home}/`, never inside it — writes under `{home}/` trip the permission system's own-settings protections."""


def new_project_runner_recipes(*, language: str, recipes: str = "`fmt`, `lint` and a sanitizer build") -> str:
    return rf"""A new {language} project's runner carries {recipes} alongside that standard set."""


PROJECT_DOCS_SETUP = r"""**Project documents**: a project with a maintained contract carries the full document set — `THESIS.md`, `SPEC.md`, `ARCHITECTURE.md`, `CONVENTIONS.md` — with `ARCHITECTURE.md` citing `SPEC.md` rather than restating it, and `CONVENTIONS.md` carrying house rules and project-specific traps rather than contract. A project AGENTS.md stays lean — only the project-specific rules that drift when the contract docs fall out of context. A vanilla project may have no AGENTS.md and no SPEC.md; that is an acceptable state, not a defect. A project intended to be maintained also carries `ROADMAP.md` — next steps and future intent, even if one sentence ("spec implemented; no further work intended"). Future-thinking routes there, never inline in the contract docs, and ROADMAP.md is not handed to coding dispatches."""

DATA_FORMATS_SCOPE = r"""project-owned configuration and structured data files"""

DATA_FORMATS = rf"""**Data formats**: the right tool for the job decides. Absent a reason that does, prefer TOML for {DATA_FORMATS_SCOPE}; YAML when the shape is genuinely a tree (deep nesting, nulls, top-level lists); JSON last. Cases that override that order: JSONL for flat records one per line, sorted or append-only — the line is the record, so `grep` returns whole records and `git diff` isolates the changed one; JSON for wire protocols and external API contracts someone else defines. Where the project's `CONVENTIONS.md` says more about formats, it governs."""

COMMERCIAL_APPROVAL_CLAUSE = r"""unless explicitly approved by the coordinator/user"""


def dependencies_lead(*, variant: Literal["packages"]) -> str:
    texts = {
        "packages": rf"""**Dependencies**: every dependency is a permanent maintenance obligation — justify it before adding. No paid or commercial packages {COMMERCIAL_APPROVAL_CLAUSE} — report as a Blocker if a task requires a commercial dependency.""",
    }
    return texts[variant]


# Not folded into dependencies-lead: shell-dsl-coder and the platform experts
# expand that chunk and state no size test. Not folded into dependency-vetting
# either: those five measured checks decide whether a candidate is sound, this
# decides whether to reach for one at all.
def manual_over_large_dependency(*, unit: str = "package") -> str:
    return rf"""A small manual implementation beats importing a large {unit} for a single feature."""


# Not one of dependency-vetting's items: that list is what a REGISTRY shows, and
# an issue tracker's state is the one signal none of them carries.
ISSUE_TRACKER_HEALTH = r"""Check issue tracker health before adopting."""


def dependency_vetting(
    *,
    artifact: str = "justification (task report or Blocker)",
    registry: str = 'pkg.go.dev "Imported by", PyPI downloads, crates.io recent downloads, or npm weekly downloads',
) -> str:
    return rf"""**Vet adoption and maintenance from the registry, not the README.** Before adding a dependency, record these in the {artifact} — measured, not asserted:

1. **Last release date** — a stale package is a bus-factor bet no benchmark score offsets.
2. **Adoption count** — {registry} — judged against the niche's scale, not absolute numbers.
3. **Deprecation/archival status** — registries and repo banners show it; READMEs often do not.
4. **Transitive dependency count** — the graph you adopt, not just the package.
5. **License** — compatible with the project's; a copyleft or source-available surprise is a Blocker, same as commercial.

**The port trap:** for a port or binding, verify the PORT's release activity, not its upstream's — a port's README typically describes the upstream project's cadence, which says nothing about whether the port has shipped in years.

**Default to the well-trodden option** unless the off-standard gain is genuinely substantial. Weight the cost of being wrong, not just the benchmark delta: a stale dependency's cost lands later, on whoever replaces it mid-feature."""


# rust-coder states this rule inline against a named ecosystem and a concrete
# threshold (the tracing ecosystem, for a tool that needs three log lines); no
# argument over this body reproduces it.
def heavy_logging_framework(*, baseline: str) -> str:
    return rf"""Do not reach for a heavy third-party logging framework unless {baseline} demonstrably cannot meet the requirement."""
