# Follow-ups from the 0.13.0 post-sprint review

Findings that the 0.13.0 review raised and the release left for later. None is scheduled. A later
plan picks each one up or drops it.

## Open

- Nothing makes the own-paragraph rule for module text beside a clause hold: `just test` does not fail on a new join site — `devtools/clause_join_sites.py`, `tests/`
- A shared sentence written out inside a longer paragraph is not checked for double delivery — `tests/test_adjagent.py` (`_double_paragraphs`)
- The double-delivery paragraph check fills only the claude family under the claude harness, so family overlay text and other harnesses' text go unchecked — `tests/test_adjagent.py` (`_prompts`, `_CLAUDE_RENDER`)
- The installed agents file is never part of a prompt, though it sits in context beside every command and skill — `tests/test_adjagent.py` (`_prompts`, `_loaded`); `PROJECT_DOCS/SPEC/generation-system.md`
- `@` lines are followed one level deep only — `tests/test_adjagent.py` (`_loaded`)
- A coder or platform expert that never carries its group's anchor is outside every group, so nothing checks it — `tests/test_clause_groups.py` (`check_clause_groups`)
- Exemption reasons quote definition text that nothing checks — `tests/test_clause_groups.py` (`EXEMPTIONS`)
