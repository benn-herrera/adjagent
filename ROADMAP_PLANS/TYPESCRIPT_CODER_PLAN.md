# TYPESCRIPT_CODER_PLAN.md — a TypeScript coder

**Status: steps 1–5 landed; reference retaken. Open: routing.** The descriptions of
typescript-coder, web-app-expert and generalist-coder still state the browser boundary three ways,
and the owner has not ruled on two cases: isomorphic libraries, and framework apps (Next.js) with
server and browser code. Once ruled, all three descriptions state one test, typescript-coder's drops
"Covers the type system, runtime validation" (the body no longer has those sections), the reference
is retaken, and the commit deletes this plan. Serial dispatch — one agent at a time.

The change gives a seat new text to read, so it ends like every such change: `just render`, then
`just render-diff` shows exactly the files named under Proof and nothing else; the owner reads them;
`just retake-reference` makes the accepted render the baseline.

## Scope of the seat

TypeScript and modern JavaScript outside the browser: Node, Deno and Bun services, CLIs and
libraries. Code whose target is a browser belongs to web-app-expert, and each seat's description
says so.

## The pattern to copy

`adjagent/definitions/rust_coder.py` and `adjagent/definitions/lua_coder.py`: the shared clauses in
the coders' order, with the language's own prose between them, including `ISSUE_TRACKER_HEALTH`,
`new_project_runner_recipes` and `LOGS_NOT_STDOUT`. The dependency lead is
`clauses.DEPENDENCIES_LEAD_PACKAGES`.

## Steps

1. **prompt-engineer authors the seat's prose:** the description, the intro, Core Expertise,
   Critical Gotchas, and the language-specific sentences that sit beside the shared clauses (build
   system, logging, data formats, dependencies). Its first subject is which runtime and which module
   system the project targets (Node / Deno / Bun; ESM / CJS; the `tsconfig` `module` and
   `moduleResolution` settings), since that decides imports, the test runner and what the build
   emits. The prose is written to a file under `.claude-temp/typescript-coder/`.
2. **python-coder at `sonnet` assembles `adjagent/definitions/typescript_coder.py`**, output
   `agents/typescript-coder.md`, tier `high`, color `#3178C6`, in rust-coder's clause order around
   that prose. Slot values: unit tests vitest (`node:test` where the project uses it); type check
   `tsc --noEmit`; lint eslint with typescript-eslint; formatter prettier (biome where the project
   uses it); package manager the one the lockfile names; `dependency_vetting(registry="npm weekly
   downloads")`; `manual_over_large_dependency(unit="package")`.
3. **Descriptions.** `adjagent/definitions/generalist_coder.py` names `typescript-coder for
   TypeScript and JavaScript outside the browser` among the language coders.
   `adjagent/definitions/web_app_expert.py` names `typescript-coder` for TypeScript and JavaScript
   whose target is not a browser.
4. **Docs.** `README.md`'s Coding Agent Set lists `typescript-coder.md`. `ARCHITECTURE.md`'s
   Subsystem Map line `language coders (c, cpp, go, python, rust)` becomes
   `(c, cpp, go, lua, python, rust, typescript)`.
5. **prompt-engineer reviews the finished definition**, as its own dispatch, separate from the one
   in step 1.

The seat's description is not shortened here beyond what the step-5 review requires;
DESCRIPTION_TRIM_PLAN.md, which follows, shortens every description including this one.

## Proof

`just test adjagent` passes. `render-diff` shows `agents/typescript-coder.md` only in the new render,
and `agents/generalist-coder.md` and `agents/web-app-expert.md` differing in their descriptions;
nothing else.

## Out of scope

No shared clause changes. If writing the seat shows a clause that should change, that is its own
item.
