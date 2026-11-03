### Normative pages outrank the plan

A plan may name a normative page outside the contract documents, and that page outranks the
plan. The contract documents are THESIS.md, SPEC.md, ARCHITECTURE.md and CONVENTIONS.md. A plan
may make a page of its own subject normative, and on that subject the page is the requirement
while the plan is the route. Where a plan row and the page disagree, the work implements the page
and the plan's line is reported as moved, in the commit that lands it; the page is not edited by
the landing, and the contract documents cite it rather than restate it. A plan that needs such a
page names it in the plan, so a reader knows which source settles a disagreement.
- Working drafts and half-formed notes are scratch (`.opencode-temp/`), not plans.
- Any plan that is activated, regardless of its location, gets a post-sprint review section at the
  end.
  - That section contains the review, revision, and burndown steps.
  - Unless otherwise specified the reviewers are an architect, a coder and a tech-writer reviewing
    with THESIS.md, SPEC.md, ARCHITECTURE.md, and CONVENTIONS.md as their pre-task reading list. The
    tech-writer reviews what the change ships as documentation — the contract documents, README, and
    any page a plan makes normative — for accuracy against the code and for whether a reader without
    the work thread can act on it.
  - They do NOT get the plan doc. Their job is to review the changes against standards and
    suitability for purpose, not rehash the implementation.
  - Their review brief includes reviewing the tests.
  - The burndown list is written to a separate `<plan>_REVIEW_BURNDOWN.md` and gets the same prompt
    engineer review and revision pass as any other document containing agent instructions.

