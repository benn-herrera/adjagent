### Group membership

A group is the set of definitions whose own `Definition(...)` call names the group's anchor clause
(`CODE_PRINCIPLES_CODER` for coders, `CODE_PRINCIPLES_PLATFORM` for platform experts). The check is in
[Structural rules](../../ARCHITECTURE/composition-model/structural-rules.md). To add a coder or
platform expert, in `tests/test_clause_groups.py`:

1. Name the anchor in the definition's own `Definition(...)` call, called or read. A clause reached
   only inside another constant is not carried.
2. Add the definition's name to the group's `members`.
3. Carry every `plain` entry and exactly one clause of each `alternatives` pair, or add an
   `EXEMPTIONS` entry `(definition, clause): reason` for a plain entry. An exemption names only a
   plain entry, never the anchor or an alternative.
4. Add a clause every member should carry to the group's `plain`.

`just test` fails until each step holds. The exemption is written in `EXEMPTIONS` and nowhere else:
not in the definition, not in a comment beside the omission. The reason names a fact about the seat.
