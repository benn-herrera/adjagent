### Guardrails change together

`guardrail.ts` (opencode) and
`guardrail.pl` (claude) are meant to block exactly the same calls, but for `guardrail.pl`'s reading
of a shell path word that opens with `$CLAUDE_PROJECT_DIR`, which opencode has no counterpart for,
and nothing at runtime compares them. That covers the mutation check on shell commands and the
`.index/` read check on shell and file-tool calls alike. A behaviour change edits both and
`tests/guardrail_cases.json` in one change — a change to that expansion edits `guardrail.pl` alone —
and `tests/test_guardrail.py` is what holds them to it: it runs each case through each
implementation its `harness` field does not exclude, under `bun` and `perl`, and fails, not skips,
without `bun`. That `$CLAUDE_PROJECT_DIR` expansion is the only one either guardrail performs, and
no other is added. The guardrail catches the in-place edit and
redirect forms agents habitually use and points them to the edit tools; it is not a boundary
against a command built to evade it, and a detection change earns its place by the common form it
catches, not by closing an evasion.
