"""House practice: the build system and project setup, data formats, dependencies and logging."""

from dataclasses import dataclass

from adjagent.context import Render
from adjagent.profile import Profile
from adjagent.section import Section

_PROJECT_DOCS_SETUP = r"""**Project documents**: a project with a maintained contract carries the full document set — `THESIS.md`, `SPEC.md`, `ARCHITECTURE.md`, `CONVENTIONS.md` — with `ARCHITECTURE.md` citing `SPEC.md` rather than restating it, and `CONVENTIONS.md` carrying house rules and project-specific traps rather than contract. A project AGENTS.md stays lean — only the project-specific rules that drift when the contract docs fall out of context. A vanilla project may have no AGENTS.md and no SPEC.md; that is an acceptable state, not a defect. A project intended to be maintained also carries `ROADMAP.md` — next steps and future intent, even if one sentence ("spec implemented; no further work intended"). Future-thinking routes there, never inline in the contract docs, and ROADMAP.md is not handed to coding dispatches."""

_DATA_FORMATS = r"""**Data formats**: the right tool for the job decides. Absent a reason that does, prefer TOML for project-owned configuration and structured data files; YAML when the shape is genuinely a tree (deep nesting, nulls, top-level lists); JSON last. Cases that override that order: JSONL for flat records one per line, sorted or append-only — the line is the record, so `grep` returns whole records and `git diff` isolates the changed one; JSON for wire protocols and external API contracts someone else defines. Where the project's `CONVENTIONS.md` says more about formats, it governs."""

_DEPENDENCIES_LEAD = r"""**Dependencies**: every dependency is a permanent maintenance obligation — justify it before adding. No paid or commercial packages unless explicitly approved by the coordinator/user — report as a Blocker if a task requires a commercial dependency."""

_MANUAL_OVER_LARGE_DEPENDENCY = (
    r"""A small manual implementation beats importing a large package for a single feature."""
)

_ISSUE_TRACKER_HEALTH = r"""Check issue tracker health before adopting."""


def _build_system(profile: Profile) -> str:
    return rf"""**Build system**: if the project has a Makefile or justfile, use its targets/recipes (whichever runner the project has chosen) for all {profile.build_operations} operations — never invoke {profile.build_tools} directly when a target covers it. Build outputs belong in {profile.build_outputs}, not scattered in the source tree."""


def _new_project_setup(ctx: Render, profile: Profile) -> str:
    temp = ctx.harness.project_temp_dir
    home = ctx.harness.project_harness_dir
    return rf"""**New project setup**: creating a project from scratch means creating its task-runner entry point WITH the first code, never retrofitting it later. A `justfile` by default; a `Makefile` only where the top-level utility commands genuinely need dependency management — file targets with staleness rules, generated content that must rebuild when its sources change, recursive sub-builds (`$(MAKE) -C`). Aliasing commands is never reason enough to choose Make over just. Standard targets: `build`/`rebuild`, `test`, an integration-test target, and `generate`/`regenerate` wherever generation is a distinct step the build does not own — CMake project generation in the C++/CMake family, `go generate` codegen in Go, code/data generation in Python (Rust and Zig typically need none: `build.rs`/`build.zig` own generation). Omit a target only where the task genuinely does not exist for the project — never because wiring it up is effort. No project may ever require the agent or the developer to execute a major project-iteration task from a naked command line with correctly-recalled values: the target is the memory. Also created at project birth: `{temp}/`, with a `{temp}/` entry in the root `.gitignore` — the project's scratch space (throwaway builds, probe harnesses, captured output), pre-made so the scratch-space rule never stalls on a missing directory. It lives beside `{home}/`, never inside it — writes under `{home}/` trip the permission system's own-settings protections. A new {profile.language} project's runner carries {profile.runner_recipes} alongside that standard set."""


def _dependency_vetting(profile: Profile) -> str:
    return rf"""**Vet adoption and maintenance from the registry, not the README.** Before adding a dependency, record these in the justification (task report or Blocker) — measured, not asserted:

1. **Last release date** — a stale package is a bus-factor bet no benchmark score offsets.
2. **Adoption count** — {profile.registry} — judged against the niche's scale, not absolute numbers.
3. **Deprecation/archival status** — registries and repo banners show it; READMEs often do not.
4. **Transitive dependency count** — the graph you adopt, not just the package.
5. **License** — compatible with the project's; a copyleft or source-available surprise is a Blocker, same as commercial.

**The port trap:** for a port or binding, verify the PORT's release activity, not its upstream's — a port's README typically describes the upstream project's cadence, which says nothing about whether the port has shipped in years.

**Default to the well-trodden option** unless the off-standard gain is genuinely substantial. Weight the cost of being wrong, not just the benchmark delta: a stale dependency's cost lands later, on whoever replaces it mid-feature."""


@dataclass(frozen=True)
class BuildSystem(Section):
    """The build-system rule, new-project setup with the language's runner recipes, and the project
    document set."""

    profile: Profile

    def render(self, ctx: Render) -> str:
        return "\n\n".join((_build_system(self.profile), _new_project_setup(ctx, self.profile), _PROJECT_DOCS_SETUP))


@dataclass(frozen=True)
class DataFormats(Section):
    """The format preference order, continued by the language's format libraries."""

    profile: Profile

    def render(self, ctx: Render) -> str:
        return f"{_DATA_FORMATS} {self.profile.format_libraries}"


@dataclass(frozen=True)
class Dependencies(Section):
    """Justifying a dependency, then vetting it from the language's registry.

    The size test and the issue-tracker check stay out of the vetting list: the list is what a
    registry shows, and those decide whether to reach for a dependency at all.
    """

    profile: Profile

    def render(self, ctx: Render) -> str:
        lead = f"{_DEPENDENCIES_LEAD} {_MANUAL_OVER_LARGE_DEPENDENCY} {_ISSUE_TRACKER_HEALTH}"
        return f"{lead}\n\n{_dependency_vetting(self.profile)}"


@dataclass(frozen=True)
class Logging(Section):
    """The language's logging rule, closed by the no-heavy-framework sentence."""

    profile: Profile

    def render(self, ctx: Render) -> str:
        return (
            f"{self.profile.logging}\nDo not reach for a heavy third-party logging framework unless "
            f"{self.profile.logging_baseline} demonstrably cannot meet the requirement."
        )
