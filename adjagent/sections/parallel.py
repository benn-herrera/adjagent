"""Parallel execution: the rules for a seat that may share its tree with other agents."""

from typing import Literal

PE_PREAMBLE = r"""You may be dispatched as one of several agents working on the same codebase simultaneously."""

PE_READ_BULLET = r"""- **Read before touching**: read every file you will edit before making any changes."""


def pe_declare_bullet(*, act: str = "modify") -> str:
    return rf"""- **Declare scope**: state which files you will {act} before starting. Do not touch files outside this set without explicit instruction."""


PE_STOP_BULLET = r"""- **Stop on conflict**: if mid-task you discover you need to modify a file another agent may be editing, stop and report rather than proceeding."""

PE_EXPANSION_BULLET = r"""- **Scope expansion**: if you discover the task is significantly larger than described — requires touching additional systems, reveals a fundamental design gap, or would affect other agents' work — stop immediately and report to the coordinator. Do not make unilateral expansion decisions."""


def pe_scope_creep_bullet(*, examples: str = "improve adjacent code, add comments to unchanged files") -> str:
    return rf"""- **No scope creep**: complete the assigned task and stop. Don't {examples}, or expand the task boundary."""


PE_SHARED_INFRA_BULLET = r"""- **Additive over invasive in shared infrastructure**: build files, shared configs, shared types and interfaces are read by work in flight you cannot see. Where the task can be done by adding alongside rather than restructuring, add — restructuring one of these is its own assignment, never a step inside another."""

PE_GLOBAL_STATE_BULLET = r"""- **No global-state commands**: package installs, dependency upgrades, config changes and migrations land outside your declared files and reach every agent in the tree. Run none of them unless your instructions say to."""

PE_SCOPED_GATE_BULLET = r"""- **Read a gate against your own scope**: run the narrowest runner target that covers your files. Where only a whole-tree gate exists, a failure it reports outside your declared scope is someone else's work in flight — report it and leave it. Never fix it, and never read it as evidence that your own change must grow."""


def parallel_execution(*, variant: Literal["general"]) -> str:
    bullets = {
        "general": (
            PE_READ_BULLET,
            pe_declare_bullet(),
            PE_STOP_BULLET,
            PE_SHARED_INFRA_BULLET,
            PE_GLOBAL_STATE_BULLET,
            PE_SCOPED_GATE_BULLET,
            PE_EXPANSION_BULLET,
            pe_scope_creep_bullet(),
        ),
    }
    return f"## Parallel Execution\n\n{PE_PREAMBLE}\n\n" + "\n".join(bullets[variant])
