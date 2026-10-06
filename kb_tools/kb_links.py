"""Shared Markdown link-scanning primitives for the KB toolchain.

Single source for the low-level Markdown scanning the repo does in more than
one place: neutralizing code spans, the inline-link regex, target cleanup, and
the file crawl. Both the KB link checker (``verify_md_links.py``) and
the query CLI's on-demand reverse-find (``kb_cmd``) import these so there is
exactly one copy of each primitive.

Also the one rewrite of a link: ``rebase_inline_links``, for text copied from
one document into a document in another directory.

This is the *primitive* layer only. Link classification and gating (which
links are broken, which gate the exit code) stay in ``verify_md_links.py`` —
that logic is verifier-specific and not shared.

Stdlib only.
"""

import posixpath
import re
from pathlib import Path
from urllib.parse import unquote

from kb_tools import kb_schema

# Directories never crawled, matched as a single path segment at any depth.
#   - `.index` holds the generated index streams.
#   - `.agents` is gitignored ephemeral scratch — must never be linted.
#   - `_archive` (at any depth) is a frozen archive — content is intentionally
#     stale and must not gate or warn (e.g. research/_archive/,
#     _orchestration/_archive/).
SKIP_DIRS = {".venv", "venv", ".git", "build", "node_modules", kb_schema.INDEX_DIRNAME, ".agents", "_archive"}

# Consecutive path-segment sequences that exclude a file from the crawl,
# matched anywhere in the file's relative path.
#   - `tests/fixtures`: test fixtures (the checker's and the KB tooling's)
#     contain deliberately broken links and placeholder ids; scanning them as
#     real content would fail a repo-wide run on intentional test data.
#   - `.claude/worktrees`: nested git worktrees (gitignored) — scanning them
#     would double-count the repo against itself.
SKIP_SEGMENT_RUNS: tuple[tuple[str, ...], ...] = (
    ("tests", "fixtures"),
    (".claude", "worktrees"),
)

# A document template (kb_tools/installed/<NAME>.tmpl.md) is never crawled: its
# relative links are written for the KB a build stamps it into, so where it
# sits they resolve to nothing. The stamped document is crawled instead.
DOCUMENT_TEMPLATE_SUFFIX = ".tmpl.md"

# A link's text, allowing one level of nested brackets. `[^\]]*` — the obvious
# spelling — cannot match `["the rule [see note] applies"](target.md)`, and a
# link the regex cannot see is a link no gate checks: the citation becomes
# invisible to `verify_md_links` and `verify_citations` alike, so a `]` in an
# excerpt is enough to smuggle a broken target past both.
LINK_TEXT = r"(?:[^\[\]]|\[[^\[\]]*\])*"

# Markdown inline link: [text](target). Two destination spellings, ONE capture
# group (callers index group(1) and a second group would silently re-key them):
#
#   * `<...>` — CommonMark's angle-bracket destination, the only form that can
#     carry a space. Unmatched by the bare `[^)\s]+` alternative, so a link like
#     `[x](<a file.md>)` is not a link at all as far as this regex is
#     concerned: broken targets inside it are invisible to every gate, which
#     reads as a pass.
#   * bare — everything up to the first `)` or space.
#
# The angle form is tried first; otherwise `[^)\s]+` would match `<a` and stop.
# We deliberately do not handle titles `(url "title")`; targets here are file
# paths without titles.
_DESTINATION = r"\(\s*(<[^>]*>|[^)\s]+)\s*\)"
LINK_RE = re.compile(rf"\[{LINK_TEXT}\]{_DESTINATION}")

# A destination alone, wherever a link text closes. Not LINK_RE: a linked image
# `[![](a)](b)` is one LINK_RE match whose group names only `b`, and a rewrite
# that moves `b` and leaves `a` leaves the image itself broken.
_DESTINATION_RE = re.compile(rf"\]{_DESTINATION}")

# A destination naming no file relative to the document it sits in: a URL
# scheme, a scheme-relative or rooted path, a home-dir path, a same-page anchor.
_UNMOVED_TARGET_RE = re.compile(r"^(?:[a-z][a-z0-9+.\-]*:|[/~#])", re.IGNORECASE)

# A link reference DEFINITION: `[label]: destination "optional title"`, up to
# three leading spaces per CommonMark. Without this, a destination declared here
# and used as `[text][label]` elsewhere is exempt from every gate in the
# toolchain — reference-style links go unchecked entirely. Checking the DEFINITIONS
# rather than the uses is what makes that cheap and false-positive-free: a
# definition is unambiguously a declared link target, whereas `[a][b]` in prose
# is not reliably distinguishable from two adjacent bracketed spans.
#
# Two exclusions, both found by running this over the repo's own prose:
#
#   * `(?!\^)` — `[^1]: text` is a FOOTNOTE definition, not a link. Its body is
#     ordinary prose and its first word is not a destination.
#   * the trailing `(?:title)?[ \t]*$` anchor — CommonMark allows nothing after
#     the destination but an optional title, so `[architect]: which minimal
#     stage subset builds first.` is a paragraph, not a definition. Without the
#     anchor its first word `which` was reported as a broken link.
REF_DEF_RE = re.compile(
    r"^[ \t]{0,3}\[(?!\^)[^\[\]]+\]:[ \t]*(<[^>]*>|\S+)[ \t]*(?:\"[^\"]*\"|'[^']*'|\([^)]*\))?[ \t]*$",
    re.MULTILINE,
)

# A fenced-code-block delimiter line, matched against the line with its
# blockquote markers already off (_QUOTE_PREFIX). Group 1 is the delimiter run
# itself, so its character and its LENGTH are both available to the close test;
# group 2 is whatever follows on the line — an info string on an opener, and on
# a closer the one thing tolerated below. Leading whitespace is accepted at any
# depth rather than CommonMark's three-space limit — a fence nested in a list
# item is indented past three and the KB's registers rely on that shape.
_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})[ \t]*(.*?)[ \t]*$")

# A blockquote's own markers, one or more deep. A display-maths fence may sit
# inside a labelled blockquote and opens `> ``` math` there, which a scanner
# anchored after whitespace alone does not see at all: the LaTeX is then read as
# prose, and `[T_{P,Q}g](z)` — a subscript bracket beside a parenthesised
# argument — is an inline link to a file named `z` that every gate reports
# broken. Stripping the marker before the fence test is what makes one fence
# scanner answer for quoted and unquoted fences alike.
_QUOTE_PREFIX = re.compile(r"^[ \t]{0,3}(?:>[ \t]?)+")

# An inline maths span, in the one spelling the reader emits for it: a `$`
# either side of a code span, GitHub-flavoured Markdown's own form, paired with
# the ``` ``` math ``` fence display maths gets (SPEC.md point 9). Unlike the
# code-span rule below it is NOT line-bounded, because pandoc hard-wraps a long
# inline span mid-maths and the continuation is still maths — inside a labelled
# blockquote it arrives carrying that block's `> ` marker. A span left standing
# across that break is scanned as prose, and
# `\Pi_+\!\bigl[a_{k,-}^{-1}\widehat{f}\bigr](\xi)` is then an inline link to a
# file named `\xi` that every gate reports broken.
#
# The `$` at both ends is what makes the multi-line reach safe: an odd backtick
# in prose cannot open one, so no unpaired delimiter can blank a tract of
# document and take real broken links down with it.
INLINE_MATH_RE = re.compile(r"\$`[^`]*`\$")

# An inline code span, line-bounded on purpose — see above for what pays for
# the maths rule's licence to cross a newline and why this does not get it.
# CommonMark's pairing: a maximal run of n backticks opens, and only the next
# maximal run of exactly n closes; a run of any other length inside is content,
# and an opener with no closer on its line is literal text and blanks nothing.
_INLINE_CODE_RE = re.compile(r"(?<!`)(`+)(?!`)[^\n]*?(?<!`)\1(?!`)")

# What a closing delimiter may carry and still close. A quoted fence sitting
# inside an emphasised run has the emphasis' own delimiter written onto its
# closing line — `> ```*` — which under CommonMark is not a closer at all; a
# reader matching the delimiter exactly finds the fence unclosed and blanks the
# rest of the document, and a document nothing scans reads as a document with no
# broken links. Emphasis markers and nothing else: an info string still
# disqualifies a closer, so a ```` ```` ```` block quoting a ``` ```python ```
# line does not close on it.
_CLOSER_TAIL = re.compile(r"^[*_]*$")


def _contains_run(parts: tuple[str, ...], run: tuple[str, ...]) -> bool:
    """True if ``run`` appears as a consecutive subsequence of ``parts``."""
    return any(parts[i : i + len(run)] == run for i in range(len(parts) - len(run) + 1))


def iter_markdown_files(root: Path):
    """Yield every ``.md`` file under ``root`` that is not a document template,
    skipping SKIP_DIRS at any depth."""
    for path in sorted(root.rglob("*.md")):
        if path.name.endswith(DOCUMENT_TEMPLATE_SUFFIX):
            continue
        parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in parts):
            continue
        if any(_contains_run(parts, run) for run in SKIP_SEGMENT_RUNS):
            continue
        yield path


def blank_fenced_lines(text: str) -> list[str]:
    """Return ``text``'s lines with every fenced code block blanked to ``""``.

    The one fence scanner for the toolchain: the register parser, the link
    checker, the citation gate and the metadata verifier all reach this
    function, so a fence means the same thing to each of them. Divergent
    scanners are how ``refresh`` comes to corrupt an example that ``verify``
    reports missing.

    A fence opens on a run of three or more `` ` `` or ``~``, at any indentation
    and under any depth of blockquote marker. It closes on a run of the SAME
    character, at least as long, carrying nothing after it but emphasis markers.
    Every one of those conditions is a measured failure:

    * length — a ```` ```` ```` block quoting a ``` ``` ``` line closed on the
      inner run and re-opened on the outer, inverting inside-ness for the whole
      rest of the file;
    * indentation — a closing fence indented under a list item did not match a
      column-0-anchored opener at all, desyncing the toggle so that an entire
      claim register scrubbed to nothing and parsed as zero entries;
    * the blockquote prefix — a display-maths fence inside a labelled blockquote
      never opened, so its LaTeX was scanned as prose and its subscript brackets
      were reported as broken links;
    * the emphasis tail — that same fence, sitting inside an emphasised theorem
      statement, closes on ``` ```* ```, and a reader that refused it swallowed
      every line after it.

    **A fence opened inside a blockquote closes with the blockquote.** Fenced
    content takes no lazy continuation, so a line carrying no marker is outside
    the quote and outside the fence — which is the bound that keeps an unclosed
    quoted fence from blanking the rest of a file and reporting the silence as
    a clean scan.

    Line count is preserved so reported line numbers stay accurate.
    """
    out: list[str] = []
    opener: str | None = None  # the active delimiter run, e.g. "```" or "~~~~"
    quoted = False  # the active fence opened inside a blockquote
    for raw in text.splitlines():
        prefix = _QUOTE_PREFIX.match(raw)
        line = raw[prefix.end() :] if prefix else raw
        m = _FENCE_RE.match(line)
        if opener is None:
            if m:
                opener, quoted = m.group(1), prefix is not None
                out.append("")
            else:
                out.append(raw)
            continue
        if quoted and prefix is None:
            opener = None
            out.append(raw)
            continue
        out.append("")
        if m and m.group(1)[0] == opener[0] and len(m.group(1)) >= len(opener) and _CLOSER_TAIL.match(m.group(2)):
            opener = None
    return out


def _spaces(match: re.Match[str]) -> str:
    """The match with every character but its newlines replaced by a space."""
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_code(text: str) -> str:
    """Blank out fenced blocks, inline maths spans and inline code spans.

    Lines inside ``` / ~~~ fences become empty; an inline ``$`maths`$`` span
    and an inline ``code`` span are replaced by spaces. Newlines are preserved
    so reported line numbers stay accurate.

    Maths is blanked before code, and blanking it is what this function owes a
    link scan that must not read LaTeX as Markdown: a subscript bracket beside a
    parenthesised argument is an inline link to whatever the argument names.
    Display maths arrives fenced and ``blank_fenced_lines`` already answers for
    it; inline maths arrives as a code span and is neutralised by that rule
    alone only while it stays on one line, which a hard-wrapped span does not.
    """
    return _blank_inline_spans("\n".join(blank_fenced_lines(text)))


def _blank_inline_spans(text: str) -> str:
    """``text`` with its inline maths and code spans blanked, every offset kept."""
    return _INLINE_CODE_RE.sub(_spaces, INLINE_MATH_RE.sub(_spaces, text))


def rebase_inline_links(text: str, *, from_dir: str, to_dir: str) -> str:
    """``text`` moved from a file in ``from_dir`` to a file in ``to_dir``, each relative link still naming its file.

    Both directories are POSIX paths relative to one common root. Every inline
    link or image destination outside a code or maths span is rewritten; one
    :data:`_UNMOVED_TARGET_RE` matches is left as written, and an ``#anchor``
    rides along unchanged. ``text`` is inline text — a heading, a title — so a
    fenced block in it is not recognised as one.
    """
    if posixpath.normpath(from_dir or ".") == posixpath.normpath(to_dir or "."):
        return text
    pieces: list[str] = []
    last = 0
    for match in _DESTINATION_RE.finditer(_blank_inline_spans(text)):
        start, end = match.span(1)
        pieces += [text[last:start], _rebase_target(text[start:end], from_dir=from_dir, to_dir=to_dir)]
        last = end
    return "".join(pieces) + text[last:]


def _rebase_target(raw: str, *, from_dir: str, to_dir: str) -> str:
    angled = raw.startswith("<") and raw.endswith(">")
    target = raw[1:-1] if angled else raw
    if not target or _UNMOVED_TARGET_RE.match(target):
        return raw
    path, anchor_mark, anchor = target.partition("#")
    rebased = posixpath.relpath(posixpath.join(from_dir, path), to_dir or ".") + anchor_mark + anchor
    return f"<{rebased}>" if angled else rebased


def strip_target(target: str) -> str:
    """Normalize a raw link destination to a resolvable relative path.

    Three steps, in this order:

    1. **unwrap** a CommonMark ``<...>`` destination. Written literally, the
       angle brackets became part of the path and every such link resolved to
       nothing — reported broken while pointing at a file that was right there.
    2. **strip** a trailing ``#anchor`` and a trailing ``:linenum`` suffix (the
       codebase cites locations as ``path/file.md:42``).
    3. **percent-decode**. ``[x](sub/a%20file.md)`` is the correct encoding of a
       path with a space; resolving the literal ``a%20file.md`` reported it
       broken. Decoding LAST is what keeps an encoded ``%23`` from being split
       off as an anchor in step 2.
    """
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = target.split("#", 1)[0]
    target = re.sub(r":\d+$", "", target)
    return unquote(target)
