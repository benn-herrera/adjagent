# LUA_CODER_AND_TECH_WRITER_REVIEW_PLAN.md — ROADMAP items 8 and 9

**Status: ready to execute; two independent parts, each one commit.** Part B first. The second
commit deletes this plan.

Both parts change what a seat reads, so each ends the same way: `just render` then
`just render-diff` shows exactly the files the part names and nothing else; the owner reads them;
`just retake-reference` makes the accepted render the baseline; consumers pick the change up on
their next `just install`, where a pruned file disappears and a new one arrives.

Both parts produce model-facing prose, and the prompt-engineer authors it: in B the prose that
moves into the writer is edited as it moves, and in A the Lua seat's own text is new. A python-coder
at `sonnet` does the mechanical assembly of a definition module around that prose, since every
edit it makes is enumerated. The prompt-engineer's review of the finished definition is a separate
dispatch from its authoring.

## Part B — fold tech-writer-reviewer into tech-writer (item 9)

**The pattern to match.** The coders carry a `## When Reviewing` section immediately before
`{clauses.PE_LEAD}`; it holds the test-review lens, `clauses.WHEN_REVIEWING_SECTION`, and nothing
about modifying. The architect carries its review dimensions, process and output in its own body.
The prompt-engineer runs a review mode inside one definition and fences it in one sentence of its
intro and one of its output section. The tech-writer follows the prompt-engineer: one definition,
one fence, a review section of its own.

**The change, in `adjagent/definitions/tech_writer.py`.**

1. The intro gains the fence, bold, before any writing instruction: "**Dispatched to review rather
   than write, you report findings and modify nothing** — a fix you can see is an Avoidance
   requirement in your findings, not an edit."
2. `## Before Writing` is retitled `## Before Starting`, since it applies in both modes.
3. A `## When Reviewing` section goes after `## Working in a Review Loop` and immediately before
   `{clauses.PE_LEAD}`, with `###` subheadings `Review Scope`, `Severity Calibration`,
   `Without a Spec`, `Review Output`. Its text comes from `tech_writer_reviewer.py`, edited as it
   moves:
   - Review Scope opens "Check the doc against Writing Standards, Audience Modes and the README and
     USER_README conventions above, then:" and keeps only what those do not already state:
     variance against the code, mixed-audience documents, examples running on a clean environment,
     reference completeness, guarantees the document puts on its reader, discoverability. The
     bullets that restate Writing Standards (minimal complete verified examples, link don't repeat,
     version applicability) and the Audience Fit bullets that invert Audience Modes are dropped.
   - Severity Calibration moves unchanged.
   - Without a Spec replaces Projects Without Specs: "Reviewing with no SPEC or ARCHITECTURE
     document, mark the review 'draft, pending spec' and list the assumptions you reviewed
     against." The sentence sending the reader to the architect goes: the architect's own
     description refuses contract documents.
   - Review Output is the reviewer's Output Format under that heading, so it cannot be read as the
     writer's format when writing. Its Review Summary gains one required field in place of the
     reviewer's Pre-output Reasoning steps 2 and 4: "the audience mode you reviewed against, and
     the first point where that reader, walking the document from its first sentence, cannot
     proceed — or that they reach its promise." Steps 1 and 3 are already Before Starting.
   - Invocation Context reduces to two sentences inside Review Output: "Findings go to a writer
     for one fix pass: precise enough to act on without follow-up. Prose rhythm and style are
     `prose-architect`'s, not yours." The two protocols the reviewer named exist nowhere in the
     repository and are not carried.
   - The reviewer's "If asked to fix or rewrite content, decline" is not carried: a brief asking
     for a fix is a writing dispatch.
4. `## Working in a Review Loop` becomes three bullets with no reviewer named: "Given review
   findings on your draft: address each explicitly; disagree with reasoning rather than ignore;
   never reintroduce a finding a prior cycle closed." The bullet that had the writer hand off for
   review goes, since a writer with all tools would start the second dispatch itself.
5. The description loses "Designed to work in a writer/reviewer loop with tech-writer-reviewer"
   and gains "Also the reviewer seat for technical documentation — audits docs against the code
   for accuracy and audience fit; dispatched to review, reports findings and modifies nothing."
6. The reviewer's "guarantees the doc puts on its reader" item paraphrases
   `clauses.MACHINE_GUARANTEES`, which the shared-text rule forbids; one document-specific sentence
   of it goes into Writing Standards, where it governs both modes, and Review Scope cites it.
7. `adjagent/definitions/tech_writer_reviewer.py` is deleted.
8. Mentions, edited by the tech-writer: `README.md`'s Specialists list and its line citing the
   reviewer as an example of a review seat, which also gains `c-coder` and `cpp-coder` in the
   Coding Agent Set where they are missing; `ARCHITECTURE.md`'s Subsystem Map line;
   `kb_tools/ARCHITECTURE.md`'s sentence on which seats stay, which also carries the dangling
   "protocols" referent and loses it; `ACTIVE_PLAN.md`'s mention. `ROADMAP.md` item 9 is deleted.
9. Prompt-engineer review of the merged definition before the retake.

**Proof.** `render-diff` shows `agents/tech-writer.md` differing and
`agents/tech-writer-reviewer.md` only in the reference; nothing else. In the rendered writer,
`## Audience Modes` occurs once and no Writing Standards bullet reappears under When Reviewing.
The behavioural probe, before the retake: dispatch the merged writer to review a scratch README
seeded with a wrong example and a wrong section order; pass is zero file writes and a finding on
the structure. Then dispatch it to write and check that no review-format output appears.

## Part A — a Lua coder (item 8)

**The pattern to copy.** `adjagent/definitions/rust_coder.py`: the shared clauses in the coders'
order with the language's own prose between them, including the three clauses the thinner coders
omit, `ISSUE_TRACKER_HEALTH`, `new_project_runner_recipes` and `LOGS_NOT_STDOUT`.

**The change.**

1. The prompt-engineer writes the Lua seat's text against the lua.org manuals for 5.1 through 5.5
   and luajit.org's extensions page: the intro, the description, Core Expertise and Critical
   Gotchas. Its first subject is which runtime and which host, since the host (Neovim, OpenResty,
   Redis, a game engine, standalone) decides the library subset, the logger, the module path and
   whether blocking I/O is allowed. Core Expertise covers at least: the version differences that
   change code — `setfenv` against `_ENV`, `unpack` against `table.unpack`, `//` and bitwise
   operators against the `bit` library, `goto`, `<const>` and `<close>`, 5.5's `global`
   declarations, and `tostring(3.0)` giving `"3"` or `"3.0"`; LuaJIT as 5.1 plus selected 5.2
   extensions, the `bit` library and FFI, with no integer subtype outside FFI cdata; metatables
   and metamethods; coroutines; the module and `require` path; the C API and embedding; the
   garbage collector's parameters. Critical Gotchas covers at least: 1-based indexing, `#` on a
   table with holes, `nil` in a sequence, global by default, Lua patterns are not regular
   expressions, `:` against `.` method calls, concatenation in loops against `table.concat`,
   `nil` in varargs and `select('#', ...)` or `table.pack(...).n`, `local function` against
   `local f = function` for recursion, assigning new keys during `pairs`, and writing 5.3 syntax
   for a LuaJIT target. Luau is out of scope. The description: "Lua implementation specialist.
   Writes Lua for the runtime the project targets — PUC Lua 5.1 through 5.5 or LuaJIT, standalone
   or embedded. Covers metatables, coroutines, modules, the C API and LuaJIT FFI, testing, and
   LuaRocks. Parallel-execution safe. Prefer over generalist-coder for any Lua or LuaJIT work."
2. A python-coder at `sonnet` assembles `adjagent/definitions/lua_coder.py`, output
   `agents/lua-coder.md`, tier `high`, color `#000080`, from the rust-coder's clause order and
   that prose, with these slot values: unit tests `busted` (the `lunarmodules` fork; `luaunit`
   where a project has it), `luacheck` with a `.luacheckrc` naming the runtime's `std` and the
   host's globals (`selene` as the alternative), StyLua as the formatter, `luarocks` and a
   Makefile or justfile wrapping them as the build system; `boundary_check_coder_body(
   expectation="state/coroutine/context")`; `dependency_vetting(registry="the luarocks.org
   download count")`; the logging baseline "the host's logger where embedded (`vim.notify`,
   `ngx.log`, `redis.log`), otherwise a thin module over `io.stderr`".
3. `adjagent/definitions/generalist_coder.py`'s description, which today names only `go-coder`
   and `python-coder`, names all seven language coders including `lua-coder`.
4. `README.md`'s Coding Agent Set lists the new seat; `ROADMAP.md` item 8 is deleted.
5. Prompt-engineer review of the finished definition before the retake.

**Proof.** `render-diff` shows `agents/lua-coder.md` only in the new render and
`agents/generalist-coder.md` differing in its description; nothing else. The behavioural probe,
before the retake: three fixed tasks for a LuaJIT target where `//` or `table.unpack` would be
wrong, a parsing task where regular-expression syntax would be wrong, and a task over a sparse
array with `#`.

## Out of scope

Neither part changes a shared clause. If writing either shows a clause that should change, that
is its own item.
