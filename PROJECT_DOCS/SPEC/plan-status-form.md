## Plan Status Form

Both plugins' `development` skill gives plans one form for package headings, status and release,
gives a design one final form and the roadmap's tickets one form, and gives one place for the
roadmap's tickets, for the plan and design under way and for those set aside, so that a tool
reading plans, designs and the roadmap finds each in the same place and reads it the same way.
The plan form is conditional: where a plan states package headings, status or a release, it
states them as follows. Nothing here makes a plan state anything it would not otherwise state.
Nothing inside fenced code is part of any form here, and no reader reads it.

Where they are, all at the repository root: the roadmap's tickets at `ROADMAP.md`, the plan under
way at `ACTIVE_PLAN.md` or, where the plan passed the plan size limit before approval and was diced,
the tree `ACTIVE_PLAN/`, its post-plan review's findings at `ACTIVE_PLAN_REVIEW.md`, the design
under way at `ACTIVE_DESIGN.md`, and plans and designs set aside in `ROADMAP_DESIGNS/`.
Setting work aside moves every `ACTIVE_*` file or diced tree at the root into `ROADMAP_DESIGNS/`,
its `ACTIVE_` prefix replaced by `<topic>_`, all under one topic no file already there uses
(`ACTIVE_DESIGN.md` becomes `<topic>_DESIGN.md`, a diced `ACTIVE_DESIGN/` becomes
`<topic>_DESIGN/`); the plan drops its `Release:` line. A plan cites its design by the name the
design has in the same place: `ACTIVE_DESIGN.md` at the root, `<topic>_DESIGN.md` set aside. A plan
cites a diced design through its `entry-point.md`. Returning restores the `ACTIVE_` names and the
citations; the plan names a release again once it is under way for one. Work set aside returns only
once no `ACTIVE_*` file or diced tree is at the root.

Terms:

- **plan** — a tracked document, or a tree of them where the plan was diced, written under the
  plugins' `development` skill, that lays out work as work packages and records their progress.
- **design** — a tracked document a plan is written from. It holds no work packages, sequencing or
  status.
- **roadmap** — intended work not yet taken up, at whatever stage of refinement: a ticket in
  `ROADMAP.md`, or a design or plan set aside in `ROADMAP_DESIGNS/`. Work leaves it when it becomes
  the active tasking, is accomplished by other work, or is abandoned (superseded work counts as
  abandoned).
- **work package** — one unit of a plan's work, with its own row in the plan's status table, named
  there by its ID.
- **state** — a work package's progress as its plan's status table records it: drafted,
  `dispatchable`, `in progress` or `landed`.
- **rating** — a work package's rating as its plan's status table records it: `mechanical`,
  `expert`, or unrated.
- **plan size limit** — the length past which the plugins' `development` skill dices a plan before
  it is approved.

The form:

A plan states:

- A work package is a row of the plan's status table. An ID names one row only and contains no
  spaces.
- A work package's heading, at any heading level, opens with its row's ID and then its title, with
  any separator.
- The status table sits under a `## Status` heading, and its headers include `Package`, `State` and
  `Rating`. Other columns are free.
- A state cell opens with one of three words: `dispatchable`, ready to hand to an agent as it
  stands; `in progress`, dispatched and not yet landed; `landed`, accepted and committed. Anything
  after the word is a note.
- A rating cell opens with one of two words: `mechanical`, every edit enumerated, no design choice
  and no debugging; `expert`, anything else. Anything after the word is a note.
- The post-plan review and the post-plan burndown are work packages, each with its own ID and row.
  The review's title opens with `Post-plan review` and the burndown's with `Post-plan burndown`; the
  rest of each title is free. A plan has a post-plan review row only with a post-plan burndown row,
  and a burndown row only with a review row.
- A plan carries `Release: <version>` as the first non-blank line after the plan's H1 heading once
  it is the plan under way for that release. A plan set aside for later names no release.
- A release's hardening plan is the plan whose H1 heading opens with `Release hardening`.

A reader of plans:

- Ignores a row whose `Package` cell is empty; it is not a work package.
- Matches a heading to a row by the row's ID, and takes only the title from the heading.
- Takes the first table under a `## Status` heading whose headers include `Package` and `State` as
  the status table.
- Reads a row with no state word, or opening with any other word, as drafted.
- Reads a work package as unrated where the table has no `Rating` column, or its rating cell opens
  with neither rating word.
- Reads a plan as done only when its post-plan review row and its post-plan burndown row, each
  where it has one, are `landed`.
- Reads only the `Release hardening` prefix of a hardening plan's H1 heading, nothing after it, and
  reads the release's version only from the `Release:` line.
- Reads a plan held as a tree at `ACTIVE_PLAN/` through its `entry-point.md`; a leaf there is part of
  that one plan.

A design:

- The design under way stays at `ACTIVE_DESIGN.md` from before its plan is written: it is removed
  when that plan is done, and is set aside with its plan, or alone before a plan exists. The plan
  cites the design's entries rather than restating them, a requirement found while the plan runs
  is entered in the design, and the plan's post-plan review reads the design.
- Work a design has not yet written as entries is held under one `## Drafts` heading, as tickets
  in the roadmap's form.
- A diced design is split at its `##` and `###` headings only, so each entry and each ticket is
  one file.
- A design is offered for acceptance only once a reader of designs finds no breach of its final
  form.

A design's final form:

- It opens with a level-1 heading naming the change, then a statement of its intent before any
  `##` heading, followed by this line, verbatim apart from where it wraps: "The preceding is a
  summary of the detailed design below. Summaries are unavoidably lossy. The summary text is not
  to be consistency checked. The design is authoritative." A diced design holds all three in its
  `entry-point.md`.
- Its only `##` headings are `## SPEC delta`, `## ARCHITECTURE delta` and `## Code delta`, spelled
  exactly so, in that order, each at most once, and at least one of them.
- Under each, nothing before its first `###` entry; an entry runs to the next `#`, `##` or `###`
  heading. An entry's heading names the leaf, or the section of an undiced document, it changes —
  or, under `## Code delta`, whose statements its code change must keep true: as a link where that
  leaf or section exists, as plain text where the change creates it.

A reader of designs:

- Reports any `##` heading other than the three as a breach of the final form.
- Does not check that an entry's linked leaf or section exists; a link check does.
- Reads the whole design in the roadmap's form, each delta a category and each entry a ticket, and
  reports what a reader of the roadmap reports, other than a missing category, as a breach of the
  final form.

The roadmap's form:

- A category is a `##` heading and the text after it, up to the next `#` or `##` heading. A ticket
  is a `###` heading inside a category and the text after it, up to the next `#`, `##` or `###`
  heading. A `####` heading inside a ticket is part of its text.
- Text inside a category before its first ticket is not a ticket.
- A ticket's heading names the ticket. A top-level list item opening with a bold lead appears only
  inside a ticket.

A reader of the roadmap:

- Reports a `ROADMAP.md` with no category, a `###` heading outside any category, a top-level list
  item opening with a bold lead outside any ticket, and a ticket heading that names nothing, as
  breaches of the form.
