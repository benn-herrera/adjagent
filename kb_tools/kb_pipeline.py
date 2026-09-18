"""The KB build pipeline's state machine: stage table, ledger, checklist.

**The stage table lives here and only here.** The ordered stage vocabulary is
the in-code constant :data:`STAGES`; agent definitions read it out of
``kb_util show-status`` rather than enumerating stages of their own, so there
is exactly one source and no definition can drift from it.

**The ledger is the git commit trail.** There is no pipeline metadata file:
the KB and the repository's history are the only durable state. A stage
boundary is recorded by making a commit whose subject carries the stage id,
and status is read back with ``git log --grep``.

Subject format — stable, greppable, and machine-readable::

    kb-build: <stage-id> | <display name>

``<stage-id>`` is the first whitespace-free token after the ``kb-build: ``
prefix and is always one of :data:`STAGE_IDS`. An optional body paragraph
follows the subject: the charter path on ``start``, the ``--note`` text
``advance-step`` carries on any stage.

**Stage-addressed and declarative.** Recording is idempotent per stage — a
re-record reports and exits 0 — and out-of-order recording is refused with
the checklist, so a caller with a wrong world-model is corrected rather than
obeyed.

Stdlib only.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from kb_tools import kb_index_lib, kb_util

# Exit codes. 0/2 keep kb_util's meanings (success; environment unfit, which
# includes an unresolvable root and a failed git invocation) and 3 stays
# reserved for kb_util's already-populated KB, so a caller can read one ladder
# across the whole CLI.
EXIT_OK = 0
EXIT_GIT_FAILURE = 2
EXIT_OUT_OF_ORDER = 4
EXIT_ALREADY_STARTED = 5
EXIT_POSTCONDITION_FAILED = 6

# The one greppable marker. `git log --grep` finds candidate commits; the
# subject regex is what actually decides, so a note quoting the prefix in a
# commit body cannot forge a ledger entry.
LEDGER_PREFIX = "kb-build:"
_SUBJECT_RE = re.compile(rf"^{re.escape(LEDGER_PREFIX)} ([^\s|]+) \| ")

# Line prefixes. The checklist is the only block matching `^\[[x* ]\] `;
# everything else carries a word in the brackets so the two cannot be
# confused by a parser or by a reader.
_TAG = f"[{LEDGER_PREFIX[:-1]}]"

# The build's scratch layout, repo-root-relative. One definition per path, read
# by the coverage checks that look there and by `kb_driver.steps`, which imports
# these rather than restating them: a second spelling could send an artifact
# somewhere the tool never looks.
SCRATCH_RELROOT = f"{kb_util.SCRATCH_DIRNAME}/{kb_util.SCRATCH_BUILD_DIRNAME}"

# Where the build charter lands, repo-root-relative and tracked. Not under the
# scratch tree with the rest of the build's working artifacts: the start
# commit's body names this path permanently, and scratch is wiped between
# sessions — a ledger entry pointing into a wiped tree names nothing. Not under
# kb-root/ either, which holds the distillation and is walked as authored KB
# content by refresh and both verifiers.
CHARTER_RELPATH = "kb-build-charter.md"

#: The ``start`` boundary's body, in its two forms. A charter is optional
#: (SPEC.md, The Driver's Contract), so the field below names a path on one
#: build and the absence is the whole body on another — but the absence is
#: *stated*, never left as an empty body, because an empty body is equally what
#: a caller that dropped the argument leaves behind and the ledger is the only
#: durable record either way. A charter written where the build never looked is
#: found by reading the boundary, not by inferring from silence.
CHARTER_BODY_FIELD = "charter:"
NO_CHARTER_BODY = "charter: none — this build was given none and runs on its sources"


class PipelineError(RuntimeError):
    """A git invocation the pipeline depends on failed."""


# --- coverage ---------------------------------------------------------------
#
# A stage's coverage is the units it must cover, each carrying where it is
# satisfied from and whether it is; a stage whose coverage is incomplete cannot
# be recorded.
#
# Coverage checks EXISTENCE, per unit, and existence is not quality.
# `_check_verify_gates` is the one exception: it runs the three verifiers, and
# judging the work is theirs alone. Every path checked is one the established layout contract
# already names, and where a stage's units are enumerated from an artifact the
# toolchain wrote, that artifact also names them — nothing here invents a
# location or a count.


@dataclass(frozen=True)
class CheckContext:
    """What a coverage check may look at: the repo, and the record's own arguments."""

    repo_root: Path
    note: str | None = None
    charter: str | None = None
    #: This build spent no model call. A property of the *build*, stated by the
    #: record, and the only thing a caller says here: which coverage units it
    #: makes vacuous is decided below and is not a caller's to name. A record
    #: cannot waive a check; it can only say what the build was.
    no_inference: bool = False


@dataclass(frozen=True, kw_only=True)
class CoverageUnit:
    """One unit a stage must cover.

    ``source`` is where the unit is satisfied *from* — an artifact path, a path
    prefix, or the command whose outcome decides it. ``detail`` states the
    condition an unsatisfied unit fails, and is what a refusal carries beside
    the id.

    ``vacuous`` separates the two ways a unit is satisfied: an artifact was
    found, or there was nothing to look for. Both are ``satisfied``, so without
    the flag nothing distinguishes them, and a build that covered nothing reads
    exactly like one that covered everything. It is reported and never gates.

    ``from_argument`` marks a unit satisfied from the record's own arguments
    rather than from the tree. A read has no record arguments, so such a unit
    is unsatisfiable there for a reason that is not a fact about the KB, and
    :func:`stage_status` says which rather than reporting a tree it never
    looked at.

    **``asserts_own_work`` is the two kinds of coverage check, and it has no
    default.** A unit either asserts *this stage did its work* — pointless to
    demand of a build that excluded the work, so it goes vacuous there
    (:func:`_excused`) — or it asserts *the state handed to the next stage is
    valid for it*, which no path to the boundary excuses, however the state
    got there. Declared on the unit rather than on the stage because a check
    can be attached to more than one stage: ``_check_verify_gates`` is
    ``depends-attributed``'s and ``phase-3a``'s alike, and a per-stage
    classification would let the two disagree about one check — which is
    exactly how a validity gate goes missing from the stage that needed it.
    """

    id: str
    source: str
    satisfied: bool
    asserts_own_work: bool
    detail: str = ""
    vacuous: bool = False
    from_argument: bool = False

    def __post_init__(self) -> None:
        if self.vacuous and not self.satisfied:
            raise ValueError("a unit with nothing to check is satisfied; there is nothing left to fail")


@dataclass(frozen=True)
class CoverageReport:
    """A stage's declared units.

    One constructor: :meth:`declared` refuses an empty unit tuple — which is
    what keeps ``all(unit.satisfied for unit in ())`` out of reach. A check
    that cannot read its declaring artifact reports that as one unsatisfied
    unit carrying the reason as its ``detail``, the same as any other missing
    unit; there is no separate shape for it.

    Units are ordered by id, so two asks of an unchanged tree render alike.

    ``unit_class`` is what the units are, said once and in the negative — what
    a report with nothing satisfied is missing, stated as a class rather than
    as its instances. A decomposed report carries it and a degenerate one does
    not, its single unit being its own class.
    """

    units: tuple[CoverageUnit, ...]
    degenerate: bool = False
    unit_class: str = ""

    def __post_init__(self) -> None:
        if not self.units:
            raise ValueError("a coverage report must declare at least one unit")
        if self.degenerate and len(self.units) != 1:
            raise ValueError("a degenerate report is the one unit standing for a stage with no decomposition")
        if bool(self.unit_class) == self.degenerate:
            raise ValueError(
                "a decomposed report states what its units are as a class; "
                "a degenerate report's one unit is that class already"
            )
        object.__setattr__(self, "units", tuple(sorted(self.units, key=lambda unit: unit.id)))

    @classmethod
    def declared(
        cls, units: Sequence[CoverageUnit], *, degenerate: bool = False, unit_class: str = ""
    ) -> "CoverageReport":
        """The units a stage declares, and what they are as a class. Refuses an empty tuple."""
        return cls(units=tuple(units), degenerate=degenerate, unit_class=unit_class)


def _file_unit(
    *, unit_id: str, path: Path, detail: str, asserts_own_work: bool, from_argument: bool = False
) -> CoverageUnit:
    return CoverageUnit(
        id=unit_id,
        source=str(path),
        satisfied=path.is_file(),
        asserts_own_work=asserts_own_work,
        detail=detail,
        from_argument=from_argument,
    )


def _check_charter_written(ctx: CheckContext) -> CoverageReport:
    """The charter the record names is on disk, where the record names one.

    Argument-derived, over three conditions the unit tells apart. ``None`` is a
    *read*, which holds no record argument to check and so cannot be satisfied
    from the tree. The empty string is a record that named no charter, which is
    a build carrying none: there is nothing to look for, so the unit is vacuous
    rather than failed — a charter is what a build was told, and a build told
    nothing but its sources is an ordinary build. A path is checked on disk.
    """
    if ctx.charter is None:
        unit = CoverageUnit(
            id="charter",
            source="the record's charter argument",
            satisfied=False,
            asserts_own_work=True,
            detail="the record names no charter",
            from_argument=True,
        )
    elif not ctx.charter:
        unit = CoverageUnit(
            id="charter",
            source="the record's charter argument",
            satisfied=True,
            asserts_own_work=True,
            detail="this build carries no charter, so there is none to find",
            vacuous=True,
            from_argument=True,
        )
    else:
        unit = _file_unit(
            unit_id="charter",
            path=ctx.repo_root / ctx.charter,
            detail="no charter stands where the record names one",
            asserts_own_work=True,
            from_argument=True,
        )
    return CoverageReport.declared((unit,), degenerate=True)


def _check_document_tree(ctx: CheckContext) -> CoverageReport:
    """The tree the document graph writes: an entry point with a volume beside it.

    ``kb_util.document_tree_present`` is the same precondition ``graph-init``
    already refuses on, asked here as this stage's coverage — one predicate,
    two callers, and no second reading of what "a tree is there" means.
    """
    return CoverageReport.declared(
        (
            CoverageUnit(
                id="document-tree",
                source=str(kb_util.kb_root(ctx.repo_root) / kb_index_lib.ENTRY_POINT_FILENAME),
                satisfied=kb_util.document_tree_present(ctx.repo_root),
                asserts_own_work=True,
                detail=f"{kb_util.KB_DIRNAME}/ holds no entry point with a volume directory beside it",
            ),
        ),
        degenerate=True,
    )


def _check_spine_seeded(ctx: CheckContext) -> CoverageReport:
    """``graph-init``'s two writes: the derived-index directory, and the runner include line.

    Two units and not one, because they fail for different reasons and are
    restored by the same call for different halves of it — a seed that created
    the directory and could not find a runner file to install into is a
    different state from one that never ran.
    """
    kb = kb_util.kb_root(ctx.repo_root)
    return CoverageReport.declared(
        (
            CoverageUnit(
                id="derived-index",
                source=str(kb / kb_util.INDEX_DIRNAME),
                satisfied=(kb / kb_util.INDEX_DIRNAME).is_dir(),
                asserts_own_work=True,
                detail="the derived-index directory was never created",
            ),
            CoverageUnit(
                id="runner-targets",
                source=kb_util.verify_cmd(ctx.repo_root),
                satisfied=kb_util.targets_installed(ctx.repo_root),
                asserts_own_work=True,
                detail="this repository's runner file carries no KB include line",
            ),
        ),
        unit_class="the claim-graph spine was never seeded",
    )


def _tree_documents(repo_root: Path) -> dict[str, str]:
    """Every document of the tree by kb-root-relative path, with its text.

    ``kb_index_lib``'s walk, which is the one the verifiers and the claim-graph
    stages are both checked against. **Read from there and never from
    ``kb_claimgraph``**: that package reads this stage table, so an import in
    this direction would close a cycle — and this module holding no import of
    it at all is what makes the cycle impossible rather than a thing held apart
    by where a line sits.
    """
    return kb_index_lib.document_texts(kb_util.kb_root(repo_root))


def _check_claims_declared(ctx: CheckContext) -> CoverageReport:
    """The declared pass's universal product: a metadata block on every document.

    Which claims a document declares is the corpus's answer and may be none;
    that it carries the block saying so is this stage's, for every document
    without exception. An empty tree fails rather than passing vacuously — a
    walk that found nothing to stamp has not stamped everything.
    """
    from kb_tools.kb_write.render import FRONTMATTER_OPENER

    documents = _tree_documents(ctx.repo_root)
    missing = sorted(path for path, text in documents.items() if FRONTMATTER_OPENER not in text)
    detail = (
        f"{kb_util.KB_DIRNAME}/ holds no document to stamp"
        if not documents
        else f"{len(missing)} of {len(documents)} document(s) carry no metadata block: {', '.join(missing[:5])}"
    )
    return CoverageReport.declared(
        (
            CoverageUnit(
                id="frontmatter",
                source=str(kb_util.kb_root(ctx.repo_root)),
                satisfied=bool(documents) and not missing,
                asserts_own_work=True,
                detail=detail,
            ),
        ),
        degenerate=True,
    )


def _check_claims_discovered(ctx: CheckContext) -> CoverageReport:
    """Claim discovery's exit condition: no document is still awaiting a reading.

    The declared pass writes one reason — ``kb_index_lib.UNSCANNED_REASON``, its
    own statement that no claim has been looked for in this document's prose —
    and discovery's whole job is to replace every instance of it. A document
    still carrying it is a document this stage did not reach.
    """
    documents = _tree_documents(ctx.repo_root)
    awaiting = sorted(path for path, text in documents.items() if kb_index_lib.UNSCANNED_REASON in text)
    detail = (
        f"{kb_util.KB_DIRNAME}/ holds no document to read"
        if not documents
        else f"{len(awaiting)} document(s) still await a reading: {', '.join(awaiting[:5])}"
    )
    return CoverageReport.declared(
        (
            CoverageUnit(
                id="determinations",
                source=str(kb_util.kb_root(ctx.repo_root)),
                satisfied=bool(documents) and not awaiting,
                asserts_own_work=True,
                detail=detail,
            ),
        ),
        degenerate=True,
    )


def _check_verify_gates(ctx: CheckContext) -> CoverageReport:
    """The three verifiers, green. Two stages share it, for two different reasons.

    ``phase-3a`` is the tail's entry gate. ``depends-attributed`` is the head's
    exit, and it is this rather than an artifact check because dependency
    attribution is the one stage whose product cannot be found by looking: it
    writes ``- depends-on:`` bullets, how many is the corpus's answer, and an
    author who cross-referenced nothing leaves a tree indistinguishable from a
    pass that never ran. What can be asked of it is what the whole head has
    just built — every edge resolving, the graph acyclic, the derived index
    matching what is authored — which is the same question its own tool exits
    on, asked here by the ledger rather than taken on the tool's word.
    """
    # Local import: these modules import kb_util, which imports this one only
    # from its CLI dispatch. Kept local for the same reason kb_util does.
    from kb_tools import verify_citations, verify_kb_metadata, verify_md_links

    kb = str(kb_util.kb_root(ctx.repo_root))
    links_rc = verify_md_links.main(["--root", str(ctx.repo_root)])
    metadata_rc = verify_kb_metadata.main(["--kb-root", kb])
    citations_rc = verify_citations.main(["--kb-root", kb])
    # One unit and not three: a partial verify is not partial progress.
    return CoverageReport.declared(
        (
            CoverageUnit(
                id="verify-gates",
                source=kb_util.verify_cmd(ctx.repo_root),
                satisfied=not (links_rc or metadata_rc or citations_rc),
                asserts_own_work=False,
                detail=f"links rc={links_rc}, metadata rc={metadata_rc}, citations rc={citations_rc}",
            ),
        ),
        degenerate=True,
    )


#: The KB's overview document — what the tree holds, how it is organized, how a
#: reader navigates it. The stage assembles it from
#: :mod:`kb_tools.kb_readme`'s packaged template; the name is declared here
#: because this stage's coverage unit and postcondition look for that file.
OVERVIEW_DOC = "README.md"

#: The KB's operating contract, seeded from its packaged template at the
#: readiness stamp below — :data:`READINESS_DOCS`' document, and no later
#: stage's. ``phase-5``'s reviewer is still handed its path and may fault what
#: it says; what no boundary after ``phase-3a`` asks is whether it exists,
#: because the stamp has already written it and a check there is satisfied
#: before the stage it guards has run.
CONVENTIONS_DOC = "CONVENTIONS.md"

#: What the meta-documentation stages must produce, declared here so the
#: stages' units and anything else naming them read one definition. One
#: document, and it is the one carrying a slot no read of the KB fills: the
#: overview's opening passage is a seat's answer, where every word of
#: :data:`CONVENTIONS_DOC` is canned text an earlier stage stamped.
META_DOCS = (OVERVIEW_DOC,)


def _check_meta_docs(ctx: CheckContext) -> CoverageReport:
    """The meta-document is on disk. Two boundaries share it, for two halves of one job.

    ``overview-drafted`` writes the overview document and ``phase-5`` reviews
    what it wrote, so the question at both boundaries is the same question — the
    document is there — and the answer is the same computation. Existence is
    not quality here any more than anywhere else: whether the review improved it
    is the reviewer's ruling, which reaches the run as severities and never as a
    unit.
    """
    kb = kb_util.kb_root(ctx.repo_root)
    return CoverageReport.declared(
        tuple(
            _file_unit(unit_id=name, path=kb / name, detail="this document was never written", asserts_own_work=True)
            for name in META_DOCS
        ),
        # One unit, so it is its own class: :func:`_named_missing` names a sole
        # unit either way, which leaves a ``unit_class`` beside it a sentence
        # nothing can render.
        degenerate=True,
    )


# --- pre-commit stamps ------------------------------------------------------
#
# A stamp WRITES, where a coverage check only reads. It runs on the success
# path after coverage passes and before the boundary commit, so what
# it writes is swept into that commit rather than left dangling for the next
# stage to pick up.

#: The KB's orientation document, and the home of its scope pin — charter prose
#: the build run writes there (`kb_tools/SPEC.md`, Project Scoping). Named
#: rather than spelled twice: it is also the name `stamp_readiness_docs` seeds
#: through :data:`READINESS_DOCS`, pin and orientation text together, and only
#: where no file already stands there.
SCOPE_PIN_DOC = "CLAUDE.md"

READINESS_DOCS = (SCOPE_PIN_DOC, CONVENTIONS_DOC)
PROJECT_NAME_FIELD = "{project-name}"

#: The scope pin's slot in :data:`SCOPE_PIN_DOC`'s template. The stamp fills it
#: with what the build's charter states, so the document that says it carries
#: the pin carries one.
SCOPE_PIN_FIELD = "{scope-pin}"

#: What fills :data:`SCOPE_PIN_FIELD` on a build that was given no charter. A
#: charter is optional (SPEC.md, The Driver's Contract), so this is a legitimate
#: build and not a failure — but the pin is the charter's text, and a build with
#: no charter has none to write. The absence is stated in the document rather
#: than left as a blank section, for the reason a dropped step is named at its
#: boundary: a document nobody pinned and one whose pin went missing are not the
#: same fact, and only the build can tell them apart.
NO_CHARTER_PIN = (
    "This build was given no charter, so nothing was recorded about which corpus it "
    "distills beyond the sources it was run on. Nothing here is waiting on a tool: a "
    "reader who knows the scope should write it into this section."
)

#: Every slot an installed template declares. The spelling is kebab-case in
#: braces (root CONVENTIONS.md, the identifier class). The stamp matches this
#: against the fields it can fill and refuses a template carrying one it cannot
#: — so a slot renamed on one side of the substitution and not the other is a
#: refusal rather than a literal ``{scope-pin}`` shipped into a consumer's KB,
#: which is a corrupted document that reads as a written one.
TEMPLATE_SLOT_RE = re.compile(r"\{[a-z][a-z0-9]*(?:-[a-z0-9]+)*\}")

# kb_tools/installed/ holds the artifacts this toolchain writes into a
# consuming KB rather than anything rendered here. The directory name is the
# statement: nothing in it is a source for a file of the same name beside it.
INSTALLED_DIR = "installed"


def installed_template(name: str) -> Path:
    """The packaged source for the KB document ``name``, under ``kb_tools/installed/``.

    ``__file__`` is the right anchor here and only here: these are package
    resources, so they live wherever kb_tools was installed. Repo and KB paths
    stay cwd-anchored.
    """
    return Path(__file__).resolve().parent / INSTALLED_DIR / f"{name}.tmpl"


def scope_pin_text(repo_root: Path) -> str:
    """What this KB distills, as the build's own charter states it.

    The charter is the only place a build is told what it is for, so the pin is
    that text and nothing composed around it: no inference writes this document
    and there is nothing here for one to write — the words are the project's own
    (SPEC.md, Project Scoping).

    A recorded charter that is no longer on disk raises rather than degrading to
    :data:`NO_CHARTER_PIN`. The two are different facts, and writing the absence
    over a charter the ledger names would put a false statement in the one
    document a reader trusts for scope.
    """
    relpath = recorded_charter(repo_root)
    if relpath is None:
        return NO_CHARTER_PIN
    charter = repo_root / relpath
    if not charter.is_file():
        raise PipelineError(
            f"the {FIRST_STAGE_ID} boundary records a charter at {relpath}, and no file "
            f"stands there — {SCOPE_PIN_DOC} cannot be stamped with a scope pin this "
            f"build cannot read. Restore that file and record this stage again."
        )
    return charter.read_text(encoding="utf-8").strip() or NO_CHARTER_PIN


def stamp_readiness_docs(ctx: CheckContext) -> list[str]:
    """Write the KB's readiness docs from their packaged templates.

    Only-if-absent: a project that has authored its own CLAUDE.md or CONVENTIONS.md
    keeps it. ``{project-name}`` is substituted from the repo directory name, and
    ``{scope-pin}`` from the build's charter — the per-project facts these
    otherwise canned documents carry.

    **Why the pin lands here and not when the build opens.** ``kb-root/`` holds
    nothing outside ``.index/`` until the document graph writes the tree, so a
    write into it at build-open would carry the pin at the cost of turning
    ``kb_util.kb_root_state`` from ``spine-only`` into ``populated`` — the exact
    reading ``pre.kb-root`` refuses a fresh build on. By this stage the tree is
    populated already and the stamp cannot change that answer.

    Neither file is the corpus-invariant channel: those live in
    ``invariants.md``, which is what the toolchain parses for framework nodes.
    """
    kb = kb_util.kb_root(ctx.repo_root)
    reports = []
    for name in READINESS_DOCS:
        target = kb / name
        if target.exists():
            reports.append(f"{name}: present, left as authored")
            continue
        source = installed_template(name)
        if not source.is_file():
            raise PipelineError(
                f"the packaged readiness template {source} is missing; this "
                f"kb_tools install is incomplete — re-install the agent definitions."
            )
        text = source.read_text(encoding="utf-8")
        # Per template, and the pin read only for a template that takes one: a
        # stamp that writes nothing must not fail over a charter it never needs.
        fields = {PROJECT_NAME_FIELD: ctx.repo_root.name}
        if SCOPE_PIN_FIELD in text:
            fields[SCOPE_PIN_FIELD] = scope_pin_text(ctx.repo_root)
        # Checked on the template, never on the result: a charter is arbitrary
        # prose and may legitimately carry braces of its own.
        unfilled = [slot for slot in TEMPLATE_SLOT_RE.findall(text) if slot not in fields]
        if unfilled:
            raise PipelineError(
                f"{source.name} carries the slot(s) {', '.join(sorted(set(unfilled)))}, which "
                f"nothing here fills; the fields this stamp substitutes are {', '.join(fields)}. "
                f"Writing it would put the slot's own text into {name} as though it were prose."
            )
        for field, value in fields.items():
            text = text.replace(field, value)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        reports.append(f"{name}: written from {source.name}")
    return reports


@dataclass(frozen=True)
class ClaimgraphInvocation:
    """Which ``kb_claimgraph`` invocation a stage is, as its own command line spells it.

    **The table that used to exist nowhere.** ``--pass 1 --scope block-hosted``,
    ``--pass 1 --scope full`` and ``--pass 2`` are three stages of this
    pipeline, and until this declaration the pairing lived in two places that
    could not see each other: the driver composed the flags from pass numbers
    of its own, and the tool parsed them back into a branch of its own. Both
    read this now, in opposite directions — :attr:`flags` composes and
    :func:`claimgraph_stage` resolves — so a build cannot invoke a pass the
    tool would run as a different stage.

    The numbering is the tool's shipped surface and is not touched here; what
    this fixes is that nothing said what the numbers meant.
    """

    which_pass: int
    scope: str | None = None

    @property
    def flags(self) -> tuple[str, ...]:
        return ("--pass", str(self.which_pass), *(() if self.scope is None else ("--scope", self.scope)))


#: The scope vocabulary ``kb_claimgraph``'s command line declares. Named here
#: because the stages below are what the two values distinguish.
CLAIMGRAPH_SCOPE_BLOCK_HOSTED = "block-hosted"
CLAIMGRAPH_SCOPE_FULL = "full"

# The three claim-graph invocations, named before the table so the stage that
# declares one and the flags composed from it are one value.
_DECLARED_INVOCATION = ClaimgraphInvocation(which_pass=1, scope=CLAIMGRAPH_SCOPE_BLOCK_HOSTED)
_DISCOVERED_INVOCATION = ClaimgraphInvocation(which_pass=1, scope=CLAIMGRAPH_SCOPE_FULL)
_ATTRIBUTED_INVOCATION = ClaimgraphInvocation(which_pass=2)


@dataclass(frozen=True)
class Stage:
    """One pipeline stage: contract id, human label, coverage.

    ``display`` is what the stage is *for*, in the reader's words, and it is the
    whole of what this table says about purpose. It reaches a reader three ways
    and no other: the checklist line, :func:`stage_status`' ``FACT`` line, and
    the boundary commit's subject.

    ``coverage`` reports the units the stage must cover and which of them are
    satisfied. Every stage has one: a stage with no enumerable decomposition
    returns a degenerate report of one unit rather than no report at all, which
    is how a stage that gates on nothing says so instead of being silent.

    ``work_is_inference`` marks a stage whose work is a model call — the stages
    a build spending none does without. It is the *other* half of what excuses
    a coverage unit, and both halves are needed: a build that spent no
    inference still derived its tree and seeded its spine for real, so those
    stages' own-work units stand. Only where this stage's work was the
    inference and the unit asserts that work is there nothing left to assert
    (:func:`_excused`).

    ``claimgraph_invocation`` is set on the three stages ``kb_claimgraph`` runs
    and on no other — the mapping between this vocabulary and that tool's
    command line, read from both ends.
    """

    id: str
    display: str
    coverage: Callable[["CheckContext"], CoverageReport]
    # Runs after coverage passes and before the boundary commit, so whatever it
    # writes is swept into that commit. Returns report lines.
    pre_commit: Callable[["CheckContext"], list[str]] | None = None
    work_is_inference: bool = False
    claimgraph_invocation: ClaimgraphInvocation | None = None


# The frozen vocabulary. Ids are a cross-team contract — templates elsewhere
# are written against these exact strings — so an id is never renamed in
# place; a change means a new id and a migration.
#
# **A stage is as small as the most expensive thing in it that must not be
# repeated** (SPEC.md, The Driver's Contract). A boundary is a stage, so a stage
# holding two steps that spend inference would leave the first one's result
# behind a step that can fail, and a resume re-spends what had already been
# earned. That is what decides where the tail's boundaries fall:
# `overview-drafted` is the overview document written, and `phase-5` is the
# review of it — one stage each, because the draft and the review are two
# model calls and neither may pay for the other's failure. Splitting them is also
# what retired the alternative, which was to trust the draft's scratch file on
# re-entry: an output no boundary accounts for is discarded, and a boundary
# immediately behind the draft means there is nothing left to trust.
#
# The rule is enforced over the step table rather than restated here
# (`kb_driver.steps`, and `test_kb_driver_steps.py`'s assertion that no failable
# row stands between an inference-spending row and its boundary). A stage that
# grows a second such row fails that assertion; it is not a judgement call made
# again at each insertion.
STAGES: tuple[Stage, ...] = (
    Stage(
        "start",
        "build started",
        coverage=_check_charter_written,
    ),
    Stage(
        "document-graph",
        "document tree derived",
        coverage=_check_document_tree,
    ),
    Stage(
        "spine-seed",
        "claim-graph spine seeded",
        coverage=_check_spine_seeded,
    ),
    Stage(
        "claims-declared",
        "declared claim graph",
        coverage=_check_claims_declared,
        claimgraph_invocation=_DECLARED_INVOCATION,
    ),
    Stage(
        "claims-discovered",
        "claim discovery",
        coverage=_check_claims_discovered,
        work_is_inference=True,
        claimgraph_invocation=_DISCOVERED_INVOCATION,
    ),
    Stage(
        "depends-attributed",
        "dependency attribution",
        coverage=_check_verify_gates,
        claimgraph_invocation=_ATTRIBUTED_INVOCATION,
    ),
    Stage(
        "phase-3a",
        "validation gate",
        coverage=_check_verify_gates,
        # Seeded at the gate rather than at the finish: these are the KB's
        # orientation docs, and every stage after this one runs against a KB
        # that should already carry them. Only-if-absent, so a later stage
        # authoring its own keeps it.
        pre_commit=stamp_readiness_docs,
    ),
    Stage(
        "overview-drafted",
        "overview drafted",
        coverage=_check_meta_docs,
        work_is_inference=True,
    ),
    Stage(
        "phase-5",
        "meta-documentation",
        coverage=_check_meta_docs,
        work_is_inference=True,
    ),
)

STAGE_IDS: tuple[str, ...] = tuple(stage.id for stage in STAGES)
_STAGE_BY_ID = {stage.id: stage for stage in STAGES}
_ID_WIDTH = max(len(stage_id) for stage_id in STAGE_IDS)
FIRST_STAGE_ID = STAGES[0].id


def resolve_stage(name: str) -> Stage | None:
    """The stage ``name`` names — by id or by display name — or ``None``.

    Both spellings are admitted because the ids are a machine contract and half
    of them are not readable as anything else: an operator bounding a run after
    the validation gate should not have to know that it is ``phase-3a``.
    Whitespace is normalized and case is ignored, so ``"Validation Gate"``
    and ``phase-3a`` name one stage.
    """
    wanted = " ".join(name.split()).casefold()
    return next((stage for stage in STAGES if wanted in (stage.id.casefold(), stage.display.casefold())), None)


def stage_by_id(stage_id: str) -> Stage:
    """The stage one id names. Raises ``KeyError`` for an id outside the vocabulary."""
    return _STAGE_BY_ID[stage_id]


def claimgraph_stage(*, which_pass: int, scope: str | None) -> Stage | None:
    """The stage one ``kb_claimgraph`` invocation is, or ``None`` for no such pass.

    The resolving direction of :class:`ClaimgraphInvocation`. The tool parses
    its own flags and asks this what stage it is running, so what a pass number
    means is answered in the table both sides read rather than in a branch on
    either side of the subprocess.
    """
    wanted = ClaimgraphInvocation(which_pass=which_pass, scope=scope)
    return next((stage for stage in STAGES if stage.claimgraph_invocation == wanted), None)


def precondition_of(stage: Stage) -> Stage | None:
    """The stage whose own work must already stand for ``stage``'s to run.

    The pipeline is a line, so a stage's precondition is the stage before it and
    there is nothing further to declare: what "already stands" means is that
    stage's own-work coverage units (``CoverageUnit.asserts_own_work``), which
    are declared once beside the check that produces them. The first stage has
    none.

    Read by the claim-graph tool as well as by this module, which is the point:
    each of its three invocations refuses a tree the pass before it has not run
    over, and until this the two statements of that order — the tool's entry
    conditions and this table — could not see each other.
    """
    index = STAGE_IDS.index(stage.id)
    return None if index == 0 else STAGES[index - 1]


def stage_vocabulary() -> str:
    """Every name :func:`resolve_stage` admits, in walk order — a refusal's whole guidance."""
    return ", ".join(f"{stage.id} ({stage.display})" for stage in STAGES)


def recorded_stages(repo_root: Path) -> set[str]:
    """The stage ids the commit trail records, read from subjects alone."""
    result = kb_util.run_git(repo_root, "log", f"--grep=^{LEDGER_PREFIX}", "--format=%s")
    # A repo whose branch is unborn (no commits yet) makes `git log` exit
    # nonzero. That is an empty ledger, not a fault.
    if result is None or result.returncode != 0:
        return set()
    found = (_SUBJECT_RE.match(subject) for subject in result.stdout.splitlines())
    return {match.group(1) for match in found if match is not None and match.group(1) in _STAGE_BY_ID}


def recorded_charter(repo_root: Path) -> str | None:
    """The charter path the ``start`` boundary recorded, or ``None`` where it recorded none.

    The ledger is the durable answer and the only one: the charter reaches
    ``start-build`` as an argument and is written into that boundary's body
    (:data:`CHARTER_BODY_FIELD`), so a later stage asks the commit trail rather
    than guessing a path or re-reading a command line it never saw. A build
    given none recorded :data:`NO_CHARTER_BODY`, which is a stated absence and
    comes back as ``None`` — distinct from a boundary nobody has recorded yet,
    which is also ``None`` because neither has a charter to name.
    """
    result = kb_util.run_git(repo_root, "log", "-1", f"--grep=^{LEDGER_PREFIX} {FIRST_STAGE_ID} |", "--format=%b")
    if result is None or result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        # The absence is spelled with the same field name, so it is matched
        # first: `NO_CHARTER_BODY` is a whole statement and not a path.
        if line.strip() == NO_CHARTER_BODY:
            return None
        if line.startswith(CHARTER_BODY_FIELD):
            return line[len(CHARTER_BODY_FIELD) :].strip() or None
    return None


def current_stage(recorded: set[str]) -> Stage | None:
    """The stage to act on — the first unrecorded one — or None when complete.

    One definition serves the checklist's ``[*]`` marker and the zero-argument
    coverage read alike, so the two can never point at different stages.
    """
    return next((stage for stage in STAGES if stage.id not in recorded), None)


def checklist_lines(recorded: set[str]) -> list[str]:
    """The checklist: ``[x]`` recorded, ``[*]`` in progress, ``[ ]`` undone.

    ``[*]`` marks the first unrecorded stage, and only once the build has
    started — before that nothing is in progress.
    """
    started = FIRST_STAGE_ID in recorded
    in_progress = current_stage(recorded)
    lines = []
    for stage in STAGES:
        if stage.id in recorded:
            marker = "x"
        elif started and in_progress is not None and stage.id == in_progress.id:
            marker = "*"
        else:
            marker = " "
        lines.append(f"[{marker}] {stage.id:<{_ID_WIDTH}}  {stage.display}")
    return lines


def status_line(recorded: set[str]) -> str:
    """The one-line verdict naming which of the three world-states holds."""
    count = len(recorded)
    if FIRST_STAGE_ID not in recorded:
        state = "not started"
    elif count == len(STAGES):
        state = "complete"
    else:
        state = "in progress"
    return f"{_TAG} status: {state} ({count} of {len(STAGES)} stages recorded)"


def _print_report(
    recorded: set[str],
    *,
    advisory: str | None = None,
    stage_status: Sequence[str] = (),
) -> None:
    """The full render: status, checklist, and a refusal's unsatisfied units.

    The checklist block stays contiguous and is the only thing matching
    ``^\\[[x* ]\\] ``; every other line carries a word-prefix instead, so a
    parser can lift the checklist without knowing about the rest.

    ``stage_status`` is a refusal's unsatisfied units, rendered under the
    checklist — what is not covered, beside where the build stands.
    """
    print(status_line(recorded))
    if advisory is not None:
        print(advisory)
    for line in checklist_lines(recorded):
        print(line)
    for line in stage_status:
        print(line)


def _record(repo_root: Path, stage: Stage, body: str | None = None) -> None:
    """Sweep the worktree into a boundary commit for ``stage``.

    ``git add -A`` is the sweep: gitignore rules keep scratch out, and on the
    first stage it deliberately picks up the uncommitted spine seed, which
    belongs to the build's first commit. A stage that changed no tracked file
    still records, via ``--allow-empty`` — the boundary is the point, not the
    diff.
    """
    added = kb_util.run_git(repo_root, "add", "-A")
    if added is None or added.returncode != 0:
        raise PipelineError(f"git add -A failed at {repo_root}: {'' if added is None else added.stderr.strip()}")
    status = kb_util.run_git(repo_root, "status", "--porcelain")
    if status is None or status.returncode != 0:
        raise PipelineError(f"git status failed at {repo_root}")
    args = ["commit", "-m", f"{LEDGER_PREFIX} {stage.id} | {stage.display}"]
    if body:
        args += ["-m", body]
    if not status.stdout.strip():
        args.append("--allow-empty")
    committed = kb_util.run_git(repo_root, *args)
    if committed is None or committed.returncode != 0:
        detail = "git is not runnable" if committed is None else committed.stderr.strip()
        raise PipelineError(f"git commit failed at {repo_root}: {detail}")


def _unseeded_advisory(repo_root: Path) -> str | None:
    """The note a checklist carries while ``kb-root/`` does not exist yet, if it does not.

    One statement, read by the status render, which is where an unseeded repo
    is met.
    """
    if kb_util.kb_root(repo_root).is_dir():
        return None
    return f"{_TAG} note: {kb_util.KB_DIRNAME}/ is not seeded yet — the seed runs before the first stage is recorded."


def show_status(repo_root: Path) -> int:
    """Render the checklist for ``repo_root``. Read-only; always exit 0.

    This is also the resume detector: a present-but-incomplete ledger is what
    says an invocation is continuing a build rather than opening one.

    ``repo_root`` is a git root, not necessarily a seeded one: the ledger
    lives in the commit trail, so a KB that does not exist yet is *status*
    — a fresh build reads this before the spine is seeded — and it is named
    in the render rather than left implied.
    """
    _print_report(recorded_stages(repo_root), advisory=_unseeded_advisory(repo_root))
    return EXIT_OK


def _unit_phrase(unit: CoverageUnit) -> str:
    return f"{unit.id} ({unit.source})" + (f" — {unit.detail}" if unit.detail else "")


def _named_missing(report: CoverageReport) -> tuple[CoverageUnit, ...]:
    """The unsatisfied units a refusal names one by one.

    Empty where a decomposed report has nothing satisfied — the stage did not
    happen, and naming a hundred instances of that obscures the one fact.
    ``show-stage-status`` is where the paths are obtained in that state.

    Anything else names every unsatisfied unit and never a subset: those are
    exactly the gap between what happened and what should have, and a caller
    told only how many remain cannot dispatch against them. A stage declaring
    one unit names it either way, there being no instances for a class
    statement to stand above.
    """
    missing = tuple(unit for unit in report.units if not unit.satisfied)
    if len(missing) == len(report.units) and len(report.units) > 1:
        return ()
    return missing


def _coverage_refusal(report: CoverageReport) -> str | None:
    """The report's refusal reason, or None when the stage may be recorded.

    One decision, and the whole of it: no refusal iff every unit in the report
    is satisfied.

    The verdict is binary; the message says which shape of failure produced it,
    over the units :func:`_named_missing` decides are worth naming.

    Takes a report rather than a stage because the record path reads one
    production of it twice — for this verdict and for
    :func:`_report_vacuous_units` — and building a report can run the verify
    gates.
    """
    if all(unit.satisfied for unit in report.units):
        return None
    named = _named_missing(report)
    if not named:
        return f"not one of {len(report.units)} coverage units is satisfied: {report.unit_class}"
    phrases = "; ".join(_unit_phrase(unit) for unit in named)
    return f"{len(named)} of {len(report.units)} coverage unit(s) unsatisfied: {phrases}"


#: What a unit's detail becomes once this build's exclusion has excused it.
#: Written where the excusing happens rather than in each check, because the
#: reason is the same reason every time and none of the checks knows it.
WORK_EXCLUDED_DETAIL = "this build spent no model call, so this stage's work did not run and there is none to find"


def _excused(report: CoverageReport, stage: Stage, ctx: CheckContext) -> CoverageReport:
    """The report with the units this build's exclusion excuses turned vacuous.

    **Two conditions, and both are the tool's own.** The build says one thing —
    that it spent no inference — and everything else is decided here: whether
    this stage's work was the inference (:attr:`Stage.work_is_inference`), and
    which of its units assert that work (:attr:`CoverageUnit.asserts_own_work`).
    A record cannot name a unit and cannot waive a check; the classification is
    not reachable from a command line.

    **A validity unit is never excused, whatever the build did.** Whatever path
    reached this boundary, the state handed across it must satisfy the next
    stage's contract — which is why ``_check_verify_gates`` runs at
    ``depends-attributed`` under this flag exactly as it does without it, over a
    KB that stage left unchanged. Refresh is idempotent absent claim-value
    changes and verify is cheap, so the cost of asking twice is nothing beside
    a validity gate silently skipped.
    """
    if not (ctx.no_inference and stage.work_is_inference):
        return report
    return replace(
        report,
        units=tuple(
            replace(unit, satisfied=True, vacuous=True, detail=WORK_EXCLUDED_DETAIL) if unit.asserts_own_work else unit
            for unit in report.units
        ),
    )


def _report_vacuous_units(report: CoverageReport) -> None:
    """Name every unit that was satisfied because there was nothing to check.

    Never a gate — the stage records either way. Zero support nodes has two
    causes the tool cannot tell apart, a corpus that derives nothing and a wave
    that noticed nothing, which is why it passes; this line is what leaves a
    reader able to tell, and it claims nothing about which cause holds.
    """
    for unit in report.units:
        if unit.vacuous:
            print(f"{_TAG} note: nothing to check for {unit.id} — {unit.detail}")


# --- the stage-coverage read ------------------------------------------------
#
# One stage's coverage, rendered for a caller who asked rather than for one who
# was refused. Three statuses and no verdict: reading a stage decides nothing,
# so nothing here gates and nothing here writes.
#
# The MISSING line is built in one place and both consumers call it — the
# refusal below renders the units it names as exactly these lines — so the two
# outputs are one computation rather than two renderings that agree today.

STAGE_STATUS_TAG = "[stage-status]"
COVERED = "COVERED"
MISSING = "MISSING"
FACT = "FACT"

#: What an argument-derived unit reports on a read. ``start``'s charter rides
#: the record, so a read holds no value to check — which is a fact about the
#: question asked, never about the tree.
ARGUMENT_ON_A_READ = "this argument rides the record and is not available on a read"


def _missing_line(unit: CoverageUnit) -> str:
    return f"{STAGE_STATUS_TAG} {MISSING} {_unit_phrase(unit)}"


def _covered_line(unit: CoverageUnit) -> str:
    # A satisfied unit's `detail` states the condition it did not fail, which
    # beside COVERED reads as a defect; a vacuous unit's says why there was
    # nothing to look for, which is the whole of what it has to report.
    return f"{STAGE_STATUS_TAG} {COVERED} {unit.id} ({unit.source})" + (f" — {unit.detail}" if unit.vacuous else "")


def _stage_fact(stage: Stage, detail: str) -> str:
    return f"{STAGE_STATUS_TAG} {FACT} {stage.id} ({stage.display}) — {detail}"


def stage_status(repo_root: Path, stage: Stage) -> list[str]:
    """One stage's coverage, read with no record arguments to hand.

    The context is built here, and empty of them: a read is not a record, so
    an argument-derived unit reports :data:`ARGUMENT_ON_A_READ` rather than a
    claim about the tree.
    """
    report = stage.coverage(CheckContext(repo_root))
    lines = [_stage_fact(stage, f"{len(report.units)} coverage unit(s) declared")]
    for unit in report.units:
        if unit.satisfied:
            lines.append(_covered_line(unit))
        else:
            lines.append(_missing_line(replace(unit, detail=ARGUMENT_ON_A_READ) if unit.from_argument else unit))
    return lines


def show_stage_status(repo_root: Path, stage_id: str | None) -> int:
    """Print one stage's coverage. Read-only; always exit 0.

    Zero-argument resolves through :func:`current_stage` — the same decision
    the checklist's ``[*]`` marker makes — so asking what remains where the
    build actually stands takes no stage id. A complete build has no such stage
    and says so rather than falling back to the last one.

    ``stage_id`` names any stage, recorded or unreached: a recorded stage's
    report is how a resumed build reads what actually landed, and an unreached
    stage's ``MISSING`` lines are as true an answer to a read as a recorded
    stage's ``COVERED`` ones.

    No checklist is rendered: this read is as long as the corpus has units,
    where ``show-status``' render is the fixed-length one.
    """
    if stage_id is not None:
        stage = _STAGE_BY_ID[stage_id]
    else:
        in_flight = current_stage(recorded_stages(repo_root))
        if in_flight is None:
            print(
                f"{STAGE_STATUS_TAG} {FACT} complete — all {len(STAGES)} stages are recorded; "
                f"--stage names one to inspect"
            )
            return EXIT_OK
        stage = in_flight
    for line in stage_status(repo_root, stage):
        print(line)
    return EXIT_OK


def _refuse(recorded: set[str], stage: Stage, report: CoverageReport, refusal: str) -> int:
    """Report incomplete coverage, naming the units that are not covered.

    The units the refusal names are rendered as the same ``MISSING`` lines
    ``show-stage-status`` prints, so a caller who was refused and a reader who
    asked are looking at one computation.
    """
    kb_util.to_stderr(f"{_TAG} cannot record '{stage.id}' — {refusal}. Nothing committed.")
    _print_report(recorded, stage_status=[_missing_line(unit) for unit in _named_missing(report)])
    return EXIT_POSTCONDITION_FAILED


def start_build(repo_root: Path, charter: str) -> int:
    """Record the ``start`` boundary, sweeping the seed into it.

    Refuses without committing when ``start`` is already recorded: this
    commit is by definition the build's first, so a second one would be a
    contradiction rather than a repetition.

    ``charter`` empty is a build carrying none, and the boundary says so in
    words rather than carrying an empty body. A charter is optional (SPEC.md,
    The Driver's Contract) so an absence is a legitimate state — but an empty
    body is also what a caller that silently dropped the argument leaves, and
    the ledger is the only durable place the two can be told apart. A reader
    who wrote a charter the build never picked up learns it here.
    """
    recorded = recorded_stages(repo_root)
    if FIRST_STAGE_ID in recorded:
        kb_util.to_stderr(
            f"{_TAG} this build is already started — nothing committed. "
            f"Use '{kb_util.OP_ADVANCE_STEP}' to record the next stage."
        )
        _print_report(recorded)
        return EXIT_ALREADY_STARTED
    stage = _STAGE_BY_ID[FIRST_STAGE_ID]
    report = stage.coverage(CheckContext(repo_root, charter=charter))
    refusal = _coverage_refusal(report)
    if refusal is not None:
        return _refuse(recorded, stage, report, refusal)
    _report_vacuous_units(report)
    _record(repo_root, stage, body=f"{CHARTER_BODY_FIELD} {charter}" if charter else NO_CHARTER_BODY)
    _print_report(recorded_stages(repo_root))
    return EXIT_OK


def advance_step(repo_root: Path, stage_id: str, note: str | None = None, no_inference: bool = False) -> int:
    """Record the ``stage_id`` boundary commit.

    Stage-addressed and declarative: an already-recorded stage reports and
    exits 0, and a stage whose predecessors are unrecorded is refused with the
    checklist so the caller's world-model is corrected rather than obeyed.

    ``no_inference`` states one fact about the build — that it spent no model
    call. It names no check and excuses none by itself; :func:`_excused` is
    where that fact meets this table's own classification of what each coverage
    unit asserts.
    """
    stage = _STAGE_BY_ID[stage_id]
    recorded = recorded_stages(repo_root)

    if stage.id in recorded:
        banner = (
            "process already complete" if len(recorded) == len(STAGES) else f"stage '{stage.id}' is already recorded"
        )
        print(f"{_TAG} {banner} — nothing committed.")
        _print_report(recorded)
        return EXIT_OK

    unrecorded = [s.id for s in STAGES[: STAGE_IDS.index(stage.id)] if s.id not in recorded]
    if unrecorded:
        kb_util.to_stderr(
            f"{_TAG} cannot record '{stage.id}' — these predecessors are "
            f"unrecorded: {', '.join(unrecorded)}. Record them in order, or re-read the "
            f"checklist below for where this build actually stands."
        )
        _print_report(recorded)
        return EXIT_OUT_OF_ORDER

    ctx = CheckContext(repo_root, note=note, no_inference=no_inference)
    report = _excused(stage.coverage(ctx), stage, ctx)
    refusal = _coverage_refusal(report)
    if refusal is not None:
        return _refuse(recorded, stage, report, refusal)
    _report_vacuous_units(report)

    if stage.pre_commit is not None:
        for line in stage.pre_commit(ctx):
            print(f"{_TAG} {line}")

    _record(repo_root, stage, body=note)
    _print_report(recorded_stages(repo_root))
    return EXIT_OK


def run_op(
    repo_root: Path,
    *,
    op: str,
    stage: str | None,
    charter: str | None,
    note: str | None,
    no_inference: bool = False,
) -> int:
    """Dispatch one ledger op.

    Each op's subparser declares only the arguments that op takes, so this
    trusts the combination it is handed.
    """
    try:
        if op == kb_util.OP_SHOW_STATUS:
            return show_status(repo_root)
        if op == kb_util.OP_SHOW_STAGE_STATUS:
            # The one op whose --stage is optional: without it the read
            # resolves the stage in flight.
            return show_stage_status(repo_root, stage)
        if op == kb_util.OP_START_BUILD:
            return start_build(repo_root, charter=charter or "")
        return advance_step(repo_root, stage_id=stage or "", note=note, no_inference=no_inference)
    except PipelineError as exc:
        kb_util.to_stderr(f"error: {exc}")
        return EXIT_GIT_FAILURE
