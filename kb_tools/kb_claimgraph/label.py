"""The sentence-labelled render of one document, and the map from a label back to it.

**What the seat is shown, and how a paragraph is named.** Discovery's paragraph
ask shows a model one document rendered one sentence per line, each line opening
with its own label, and asks of one paragraph at a time whether it states a
result. A paragraph is named by its label range (:meth:`Render.span_of`), and the
same span is the slice a yes places (:attr:`Span.excerpt`). So the model answers
with a letter, and every byte written comes from the document.

**Three properties the render has, and each is load-bearing.**

* **One sentence per line, wraps collapsed.** Every line of the render is one
  line of the answer's vocabulary, so a range names a run of sentences rather
  than a run of the wrapping a converter happened to choose.
* **Paragraph breaks are kept, and they are the same breaks the write API sees.**
  ``ops.excerpt_lines`` joins each body line's collapsed text with single
  spaces, so a blank line puts two spaces into its haystack and **no slice can
  cross one**. A paragraph here is therefore exactly a run of lines a slice can
  span, and the rule that a locator lies within one paragraph is what keeps the
  slice findable rather than a matter of taste about locators.
* **Navigation carries no label.** The up-link and the frontmatter block are
  shown as they stand. What the render never offers, a locator cannot name, so
  the exclusion needs no check downstream.

**A display-maths fence is not special here, and measurement is why.** Over the
survey corpus, 74 fences carry 6 blank lines before them: pandoc emits a fence
flush against the prose it interrupts, and 59 of the 74 open mid-sentence. So a
fence sits inside its own paragraph by the ordinary rule, a span crossing one is
findable by the ordinary rule, and the one thing left to say about fences —
*a span may contain an equation and may not be one* — is a comparison against
the fence extents rather than a rule in this render. What the render does do is
leave a fence's lines unsegmented: a sentence splitter run over
``\\begin{align}`` is splitting on the wrong grammar.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from ..kb_write import render as compose
from ..kb_write import store
from .inventory import MathFence
from .tree import BLOCKQUOTE_PREFIX

#: The letter every label opens with. A label is this and a 1-based ordinal, and
#: a locator is one label or two joined by a hyphen.
LABEL_PREFIX = "S"

#: A line opening a heading or a list item, over blockquote-stripped text. Either
#: one starts a paragraph of its own, which is what stops a locator widening out
#: of a stated result and into the section or the list that holds it.
_HEADING_RE = re.compile(r"^#{1,6}\s")
_LIST_ITEM_RE = re.compile(r"^(?:[-*+]\s|\d+[.)]\s)")

#: A sentence terminator: the mark, whatever closes a quotation or an emphasis
#: run behind it, and the single space a collapsed line puts after it.
_TERMINATOR_RE = re.compile(r"[.!?][\"')\]*_`»”’]* ")

#: What may open the next sentence. A lowercase letter after a full stop is an
#: abbreviation this module's list did not carry, not a new sentence.
_OPENS_SENTENCE_RE = re.compile(r"[A-Z0-9$\\`*_(\[\"'#—-]")

#: One letter and a stop — an author's initial, never a sentence end.
_INITIAL_RE = re.compile(r"^[A-Za-z]\.$")

#: The abbreviations this corpus writes. Each is a token ending in a stop and
#: followed by a capital, which is every property the splitter reads — so
#: without the list, ``Fig. 3`` is two sentences and the second one is an
#: integer.
_ABBREVIATIONS = frozenset("""
    al. app. approx. cf. ch. cor. def. dr. e.g. ed. eds. eq. eqn. eqns. eqs. etc.
    fig. figs. i.e. incl. lem. max. min. mr. mrs. ms. no. p. pp. prof. prop. ref.
    refs. resp. sec. sect. secs. st. thm. trans. viz. vol. vols. vs.
    """.split())


@dataclass(frozen=True)
class Sentence:
    """One labelled line of the render, and where in the source it came from.

    ``text`` is the render's own line — blockquote prefix stripped, whitespace
    collapsed — which is the form ``ops.excerpt_lines`` matches a needle in, so
    a slice built by joining these is findable without a second normalization.
    ``start`` and ``end`` are byte offsets into the rendered source, carried so
    that a label resolves to a place in the document and not only to a string.
    """

    label: str
    text: str
    start: int
    end: int
    #: The 0-based source line the sentence begins on. Fence extents and claim
    #: blocks are stated in lines, and this is what they are compared against.
    line: int
    #: Which run of lines the sentence belongs to: a blank line ends one, and a
    #: heading or a list item opens one. A span may not leave its own.
    paragraph: int


@dataclass(frozen=True)
class Span:
    """A contiguous run of labelled sentences, and the slice of the document it names."""

    sentences: tuple[Sentence, ...]

    @property
    def locator(self) -> str:
        first, last = self.sentences[0], self.sentences[-1]
        return first.label if first is last else f"{first.label}-{last.label}"

    @property
    def excerpt(self) -> str:
        """The tool's own slice — the author's words, and nothing a seat composed."""
        return " ".join(sentence.text for sentence in self.sentences)

    @property
    def line(self) -> int:
        """The source line the span begins on, which is where its marker will land."""
        return self.sentences[0].line

    @property
    def paragraphs(self) -> frozenset[int]:
        return frozenset(sentence.paragraph for sentence in self.sentences)


@dataclass(frozen=True)
class Paragraph:
    """One paragraph of the render: the unit a slice cannot leave.

    ``start`` is the 0-based source line it begins on, which is what names it
    outside this module; ``index`` is :attr:`Sentence.paragraph`'s ordinal for
    it; ``lines`` is every source line it holds.
    """

    index: int
    start: int
    lines: frozenset[int]


@dataclass(frozen=True)
class Render:
    """One document as the ask shows it, with every label resolvable back to a span."""

    #: What the seat is shown: the unlabelled navigation, then one labelled line
    #: per sentence, with the paragraph breaks kept.
    text: str
    sentences: tuple[Sentence, ...]
    paragraphs: tuple[Paragraph, ...] = ()

    def paragraph_at(self, line: int) -> Paragraph | None:
        """The paragraph holding source line ``line``, or ``None`` for a line in none of them."""
        return next((paragraph for paragraph in self.paragraphs if line in paragraph.lines), None)

    def span_of(self, paragraph: Paragraph) -> Span:
        """Every sentence of ``paragraph``, as one span."""
        return Span(sentences=tuple(sentence for sentence in self.sentences if sentence.paragraph == paragraph.index))


def _body_start(text: str) -> int:
    """The first line a label may name.

    The write API's locator match begins beneath the frontmatter block, so a
    label above it could never be found again; and line 1 is the up-link, which
    is navigation rather than anything the document states. Excluding both here
    is what retires two downstream checks — what the render does not offer, a
    locator cannot name.
    """
    block = store.FRONTMATTER_BLOCK.search(text)
    return max(text.count("\n", 0, block.end()) + 1 if block else 0, 1)


def heading_lines(text: str) -> frozenset[int]:
    """Every line of the labelled region that is a heading, by the rule the render opens a paragraph on.

    Named here so a caller excluding headings asks this module's own reading of
    one rather than a second pattern: a heading is navigation, not a sentence.
    """
    return frozenset(
        number
        for number, line in enumerate(text.splitlines())
        if number >= _body_start(text) and _HEADING_RE.match(BLOCKQUOTE_PREFIX.sub("", line).strip())
    )


def _inside_run(text: str, at: int, delimiter: str) -> bool:
    """True where ``at`` sits inside an unclosed ``delimiter`` run — inline maths, or a code span."""
    opened = sum(1 for index in range(at) if text[index] == delimiter and text[index - 1 : index] != "\\")
    return bool(opened % 2)


def _sentence_bounds(text: str) -> list[tuple[int, int]]:
    """Where each sentence of one collapsed paragraph begins and ends.

    Heuristic, and it has to be: no closed grammar separates ``Fig. 3`` from the
    end of a sentence. Nothing downstream rests on the split being *right* — a
    label naming half a sentence still cuts the author's own bytes and still
    locates — so the guards here buy a readable render for the seat rather than
    correctness for the checks.
    """
    bounds: list[tuple[int, int]] = []
    start = 0
    for match in _TERMINATOR_RE.finditer(text):
        end = match.end() - 1
        if end <= start or not _OPENS_SENTENCE_RE.match(text[end + 1 : end + 2]):
            continue
        if _inside_run(text, match.start(), "$") or _inside_run(text, match.start(), "`"):
            continue
        token = text[:end].rsplit(" ", 1)[-1]
        if token.lower() in _ABBREVIATIONS or _INITIAL_RE.match(token):
            continue
        bounds.append((start, end))
        start = end + 1
    if start < len(text):
        bounds.append((start, len(text)))
    return bounds


@dataclass(frozen=True)
class _Group:
    """One run of source lines the render treats as a unit before segmenting it.

    ``opens`` is what makes a heading or a list item a paragraph of its own
    without a blank line around it, which is how a list — written with no blank
    line between its items — still refuses a locator that runs across two of
    them.
    """

    kind: str
    lines: tuple[int, ...] = ()
    opens: bool = False


def _group(lines: Sequence[str], *, first: int, fenced: frozenset[int], excluded: frozenset[int]) -> list[_Group]:
    """The labelled region as runs: a break, an excluded line, one fence line, a heading, or wrapped prose."""
    groups: list[_Group] = []
    prose: list[int] = []
    opens = False

    def flush() -> None:
        nonlocal opens
        if prose:
            groups.append(_Group("prose", tuple(prose), opens))
            prose.clear()
        opens = False

    for number in range(first, len(lines)):
        line = BLOCKQUOTE_PREFIX.sub("", lines[number]).strip()
        if number in excluded:
            flush()
            groups.append(_Group("excluded", (number,)))
        elif number in fenced:
            flush()
            groups.append(_Group("fence", (number,)))
        elif not line:
            flush()
            groups.append(_Group("break"))
        elif _HEADING_RE.match(line):
            flush()
            groups.append(_Group("heading", (number,), opens=True))
        elif _LIST_ITEM_RE.match(line):
            flush()
            opens = True
            prose.append(number)
        else:
            prose.append(number)
    flush()
    return groups


def _tokens(lines: Sequence[str], offsets: Sequence[int], numbers: Sequence[int]) -> list[tuple[str, int]]:
    """Every whitespace-separated token of a group, with its byte offset in the source.

    Tokenizing and rejoining with single spaces is what ``render.collapse_prose``
    does to each line and what ``ops.excerpt_lines`` does between them, so the
    text built from these tokens is the text that matcher searches — and the
    offsets are what carry a label back to a place in the document.
    """
    found: list[tuple[str, int]] = []
    for number in numbers:
        prefix = BLOCKQUOTE_PREFIX.match(lines[number])
        cut = prefix.end() if prefix else 0
        found += [
            (match.group(), offsets[number] + cut + match.start()) for match in re.finditer(r"\S+", lines[number][cut:])
        ]
    return found


def _pieces(lines: Sequence[str], offsets: Sequence[int], group: _Group) -> list[tuple[str, int, int]]:
    """One group's sentences, each as its collapsed text and its byte range in the source."""
    if group.kind in ("fence", "heading"):
        number = group.lines[0]
        body = compose.collapse_prose(BLOCKQUOTE_PREFIX.sub("", lines[number]))
        return [(body, offsets[number], offsets[number] + len(lines[number]))]

    tokens = _tokens(lines, offsets, group.lines)
    collapsed = " ".join(token for token, _ in tokens)
    starts: list[int] = []
    at = 0
    for token, _ in tokens:
        starts.append(at)
        at += len(token) + 1

    found: list[tuple[str, int, int]] = []
    for low, high in _sentence_bounds(collapsed):
        head = max(index for index, start in enumerate(starts) if start <= low)
        tail = max(index for index, start in enumerate(starts) if start < high)
        found.append((collapsed[low:high], tokens[head][1], tokens[tail][1] + len(tokens[tail][0])))
    return found


def render(text: str, *, fences: Sequence[MathFence] = (), excluded: frozenset[int] = frozenset()) -> Render:
    """``text`` as the ask shows it: navigation verbatim, then one labelled sentence per line.

    ``excluded`` lines are shown as they stand and carry no label, so no locator
    can name one, and each of them ends the paragraph it interrupts.
    """
    lines = text.splitlines()
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line) + 1

    first = _body_start(text)
    fenced = frozenset(number for fence in fences for number in range(fence.start, fence.end))

    # One blank line between the navigation shown as it stands and the labelled
    # render, so the seat can see where the part it may name begins.
    shown: list[str] = list(lines[:first]) + ([""] if first < len(lines) else [])
    sentences: list[Sentence] = []
    held: dict[int, list[int]] = {}
    paragraph = 0
    previous = "break"

    for group in _group(lines, first=first, fenced=fenced, excluded=excluded):
        if group.kind == "break":
            if previous != "break":
                shown.append("")
            previous = "break"
            continue
        if group.kind == "excluded":
            shown.append(lines[group.lines[0]])
            previous = "excluded"
            continue
        if previous in ("break", "heading", "excluded") or group.opens:
            paragraph += 1
        previous = group.kind
        held.setdefault(paragraph, []).extend(group.lines)

        for body, start, end in _pieces(lines, offsets, group):
            if not body:
                continue
            label = f"{LABEL_PREFIX}{len(sentences) + 1}"
            sentences.append(
                Sentence(
                    label=label,
                    text=body,
                    start=start,
                    end=end,
                    line=text.count("\n", 0, start),
                    paragraph=paragraph,
                )
            )
            shown.append(f"{label}: {body}")

    paragraphs = tuple(
        Paragraph(index=index, start=min(numbers), lines=frozenset(numbers)) for index, numbers in held.items()
    )
    return Render(text="\n".join(shown) + "\n", sentences=tuple(sentences), paragraphs=paragraphs)
