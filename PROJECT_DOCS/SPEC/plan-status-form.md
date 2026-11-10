## Plan Status Form

Both plugins' `development` skill gives plans one form for package headings, status and release, and
one place for the plan and design under way and for those set aside, so that a tool reading plans
finds every plan in the same place and reads it the same way. The form is conditional: where a plan
states package headings, status or a release, it states them as follows. Nothing here makes a plan
state anything it would not otherwise state.

Where they are, all at the repository root: the plan under way at `ACTIVE_PLAN.md`, its post-plan
review's findings at `ACTIVE_PLAN_REVIEW.md`, the design under way at `ACTIVE_DESIGN.md`, and plans
and designs set aside in `ROADMAP_PLANS/`.

Terms:

- **plan** — a tracked document, written under the plugins' `development` skill, that lays out
  work as work packages and records their progress.
- **design** — a tracked document a plan is written from. It holds no work packages, sequencing or
  status.
- **work package** — one unit of a plan's work, with its own row in the plan's status table, named
  there by its ID.
- **state** — a work package's progress as its plan's status table records it: drafted,
  `dispatchable`, `in progress` or `landed`.
- **rating** — a work package's rating as its plan's status table records it: `mechanical`,
  `expert`, or unrated.

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
- Treats headings and tables inside fenced code as not part of the form.
