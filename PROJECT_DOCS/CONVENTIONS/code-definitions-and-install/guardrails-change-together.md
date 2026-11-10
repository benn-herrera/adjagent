### Guardrails change together

`guardrail.ts` (opencode, installed inside the plugin beside the entry
`index.ts`, which imports it) and `guardrail.pl` (claude) are to block the same calls, except the one
spelling only claude's reads ([SPEC.md, Deployed Surfaces,
Shipped files](../../SPEC/deployed-surfaces/shipped-files.md)), and nothing at runtime
compares them. A behaviour change edits both scripts and `tests/guardrail_cases.json` in one
change; a change to the claude-only spelling edits `guardrail.pl` alone. `tests/test_guardrail.py`
is what holds them to it. No further variable
expansion is added. A detection change earns its place by the common form it catches, not by
closing an evasion: the guardrails are no boundary against a command built to evade them.
