#!/usr/bin/env python3
"""Extract the KB inferential-quality eval instrument's prompt body, or one
of its header fields.

Used by `kb-headless-eval` (kb-testing/justfile). A standalone script rather
than an inline heredoc: `just` requires every line of a recipe body —
including a heredoc's terminator — to carry the recipe's own leading-
whitespace prefix, which a bash heredoc's own terminator rules cannot
satisfy. Keeping this logic in a real file also makes it runnable and
testable on its own, outside any recipe.

Two independent modes, each with its own stdout contract, so a shell caller
captures each with its own `$(...)` and neither can corrupt the other:

  Body mode  — argv: <brief_path> <kb_root_path> <report_path> <corpus_note>
               Stdout: the substituted prompt body.
  Field mode — argv: --field model <brief_path>
               Stdout: the dispatch contract's model name (e.g. "sonnet"),
               newline-terminated.

Stderr + exit 1: any refusal below, in either mode.
"""

import re
import sys

START_MARKER = "---- PROMPT BODY BELOW"
END_MARKER = "---- PROMPT BODY ABOVE"
DISPATCH_PREFIX = "Dispatch contract:"
MODEL_TOKEN = re.compile(r"`model:\s*([^`\s]+)`")

# The header's "<run-tag>" (angle brackets, in its output-filename naming
# convention prose) is documentation only, never a fourth placeholder —
# this list is exhaustive and deliberately does not include it.
PLACEHOLDERS = ("{kb-root-path}", "{output-report-path}", "{corpus-note}")


def fail(message: str) -> None:
    sys.stderr.write(f"error: {message}\n")
    sys.exit(1)


def find_start(lines: list[str], brief_path: str) -> int:
    start_idx = next((i for i, line in enumerate(lines) if line.startswith(START_MARKER)), None)
    if start_idx is None:
        fail(f"no line matching '^{START_MARKER}' in {brief_path} — the fixture's shape is a contract; refusing.")
    return start_idx


def extract_model(lines: list[str], start_idx: int, brief_path: str) -> str:
    # The dispatch contract lives in the header, above the prompt body —
    # bounded by start_idx so a stray "Dispatch contract:"-shaped string
    # inside the body itself is never mistaken for it.
    header = lines[:start_idx]
    dispatch_idx = next((i for i, line in enumerate(header) if line.lstrip().startswith(DISPATCH_PREFIX)), None)
    if dispatch_idx is None:
        fail(f"no line starting with '{DISPATCH_PREFIX}' before the prompt body in {brief_path} — refusing.")

    # The sentence may wrap before its terminating colon; join a small
    # forward window rather than assume the model token fits on one line.
    window = "".join(header[dispatch_idx : dispatch_idx + 3])
    match = MODEL_TOKEN.search(window)
    if match is None:
        fail(
            f"dispatch contract has no backtick-quoted `model: ...` token in {brief_path} — "
            f"refusing. Line: {header[dispatch_idx]!r}"
        )
    return match.group(1)


def extract_body(lines: list[str], start_idx: int, kb_root: str, report_path: str, corpus_note: str) -> str:
    # The end boundary is optional today and forward-compatible: a future
    # fixture revision may add a closing marker so content appended after
    # it (changelog, version table) stays out of the prompt. Until then,
    # extraction runs to EOF. Searched only after start_idx so header prose
    # above the start marker can never be mistaken for it.
    end_idx = next((i for i, line in enumerate(lines) if i > start_idx and line.startswith(END_MARKER)), None)

    body = "".join(lines[start_idx + 1 : end_idx]).lstrip("\n")

    # Substitution is single-pass and values are never rescanned: a value
    # that itself contains a placeholder-shaped string would sit there
    # unexpanded, or — depending on substitution order — swallow another
    # placeholder's slot, rather than error. A stray "{" or "}" in any
    # value refuses instead of risking a silently corrupted prompt.
    for name, value in (("kb-root-path", kb_root), ("output-report-path", report_path), ("corpus-note", corpus_note)):
        if "{" in value or "}" in value:
            brace = "{" if "{" in value else "}"
            fail(f"{name} value contains a stray '{brace}' — refusing. Value: {value!r}")

    missing = [p for p in PLACEHOLDERS if p not in body]
    if missing:
        fail(f"prompt body missing placeholder(s): {', '.join(missing)} — refusing rather than launch a malformed eval.")

    body = body.replace("{kb-root-path}", kb_root)
    body = body.replace("{output-report-path}", report_path)
    body = body.replace("{corpus-note}", corpus_note)
    return body


def main(argv: list[str]) -> int:
    if argv[:1] == ["--field"]:
        if len(argv) != 3 or argv[1] != "model":
            fail(f"--field takes exactly one field name ('model') and a brief_path, got {argv[1:]!r}")
        brief_path = argv[2]
        lines = open(brief_path, encoding="utf-8").readlines()
        start_idx = find_start(lines, brief_path)
        sys.stdout.write(extract_model(lines, start_idx, brief_path) + "\n")
        return 0

    if len(argv) != 4:
        fail(f"expected 4 arguments (brief_path kb_root_path report_path corpus_note), got {len(argv)}")
    brief_path, kb_root, report_path, corpus_note = argv
    lines = open(brief_path, encoding="utf-8").readlines()
    start_idx = find_start(lines, brief_path)
    sys.stdout.write(extract_body(lines, start_idx, kb_root, report_path, corpus_note))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
