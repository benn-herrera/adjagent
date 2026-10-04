"""Prompt composition, persistence, and the template lint.

The fixtures below stand in for the shipped bodies, so the machinery is tested
against templates whose defects are deliberate; the lint also runs over the
shipped ``prompt-templates/`` directory, which is the same guard aimed at the
prose a run actually dispatches.

Composition is strict in both directions on purpose: a template and the step
table that fills it are written by different hands, and every disagreement
between them is a driver defect (exit 15), never a pipeline outcome.

A slot is ``@!slot!@``, so a brace is only a brace: the fixtures carry raw JSON
and assert it survives composition, which under the ``str.format`` mechanism
this replaced was a render-time failure keyed on the body's own content.

The namespace is what routes a slot to its source, so the fixtures spell both
halves: ``@!dyn.charter!@`` for what the caller computes, and a bare name for
everything the composer fills. Each direction's refusal is checked for what it
*says* and not only that it fired — naming the miswiring is the whole of what
routing buys a caller over a flat namespace.
"""

from pathlib import Path

import pytest

from kb_tools import kb_util
from kb_tools.kb_driver import prompt_templates, runlog, steps

#: A caller's constant pool, stood in for the way the bodies below are. The
#: pool is the caller's mapping — ``kb_claimgraph.ask`` passes its marker
#: literals through it — so a fixture pool exercises the composer's half of the
#: contract without tying these cases to whatever a caller happens to publish.
#: ``values-flag`` is the one entry taken from a constant rather than invented:
#: the lint case at the bottom pins the same one, and two spellings of it here
#: would be the duplication the routing exists to prevent.
CONSTANTS = {
    "layout-paths": "scratch/kb-build/review/<stage>-<author>.md",
    "values-flag": kb_util.VALUES_FLAG,
    "pending-rule": "An unscored value is written as the literal `*pending*`, and only as that.",
}

# --- the fixture template set -----------------------------------------------
#
# Deliberately says nothing about sequencing: these are what a clean template
# set looks like, and the lint test below asserts exactly that.

FRAGMENT_FIXTURES = {
    # The one registered fragment slot, stood in for under its registered name
    # for the same reason as the alternatives below.
    "reader-system.tmpl.md": (
        "End with: VERDICT: critical=<n> warning=<n> note=<n>\n\n"
        "Return the counts as JSON where a tool asks for them:\n\n"
        '{"critical": 0, "warning": 0, "note": 0}\n\n'
        "Record the counts with @!values-flag!@ <your file>.\n"
    ),
    # The caller-selected alternatives, stood in for under their registered
    # names: which file an alternative slot resolves to is the registry's, so a
    # fixture that renamed them would be exercising a route nothing takes.
    "letter-correction.tmpl.md": "\n\n## A previous answer failed\n\n@!dyn.returned!@",
    "classify-options-three.tmpl.md": "Answer A, B or C for:\n\n- @!dyn.candidate!@",
    "classify-options-two.tmpl.md": "Answer A or C.",
}

SPLICING_FIXTURE = "fixture-review.single.tmpl.md"
CONSTANTS_FIXTURE = "fixture-design.single.tmpl.md"
ALTERNATIVE_FIXTURE = "fixture-ask.single.tmpl.md"

STEP_FIXTURES = {
    ALTERNATIVE_FIXTURE: "Read @!dyn.document!@.\n\n@!classify-options!@\n\nAnswer.@!correction!@",
    SPLICING_FIXTURE: (
        "Review the documents named below.\n\n"
        "Charter: @!dyn.charter!@\n\nDocuments:\n@!dyn.documents!@\n\n"
        "@!reader-system!@\n"
    ),
    CONSTANTS_FIXTURE: (
        "Design the taxonomy from the charter at @!dyn.charter!@.\n\n@!layout-paths!@\n\n@!pending-rule!@\n"
    ),
}


def _templates(
    tmp_path: Path, extra: dict[str, str] | None = None, fragments_extra: dict[str, str] | None = None
) -> Path:
    """A template set on the shipped layout: dispatchable bodies on top, fragments beneath.

    ``fragments_extra`` replaces a fragment body under its own registered name,
    which is the only way to put a defect inside one: which file a slot resolves
    to is the registry's, never a fixture's.
    """
    directory = tmp_path / "prompt-templates"
    fragments = directory / prompt_templates.FRAGMENTS_DIRNAME
    fragments.mkdir(parents=True)
    for name, body in (FRAGMENT_FIXTURES | (fragments_extra or {})).items():
        (fragments / name).write_text(body, encoding="utf-8")
    for name, body in (STEP_FIXTURES | (extra or {})).items():
        (directory / name).write_text(body, encoding="utf-8")
    return directory


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def test_render_fills_step_slots_fragments_and_constants(tmp_path: Path) -> None:
    directory = _templates(tmp_path)

    brief = prompt_templates.render(
        SPLICING_FIXTURE,
        slots={"charter": "scratch/build-charter.md", "documents": "- AcmeWidgets.md"},
        constants=CONSTANTS,
        directory=directory,
    )

    assert "scratch/build-charter.md" in brief
    assert "- AcmeWidgets.md" in brief
    # The fragment arrived, and its own slot was filled from the caller's pool
    # rather than restated in the template.
    assert "VERDICT: critical=<n>" in brief
    assert CONSTANTS["values-flag"] in brief
    assert "@!dyn.charter!@" not in brief


def test_a_fragment_example_survives_as_a_literal(tmp_path: Path) -> None:
    directory = _templates(tmp_path)

    brief = prompt_templates.render(
        SPLICING_FIXTURE,
        slots={"charter": "c.md", "documents": "- one"},
        constants=CONSTANTS,
        directory=directory,
    )

    assert '{"critical": 0, "warning": 0, "note": 0}' in brief


def test_constants_are_drawn_on_only_where_a_slot_names_them(tmp_path: Path) -> None:
    """One pool serves every template, and a template gets the entries it names and no others."""
    directory = _templates(tmp_path)

    brief = prompt_templates.render(
        CONSTANTS_FIXTURE,
        slots={"charter": "c.md"},
        constants=CONSTANTS,
        directory=directory,
    )

    assert CONSTANTS["pending-rule"] in brief
    assert CONSTANTS["values-flag"] not in brief


def test_an_unfilled_composer_slot_fails_composition(tmp_path: Path) -> None:
    """A bare slot no pool answers for. The caller is not asked about it and cannot fix it."""
    directory = _templates(tmp_path)

    with pytest.raises(runlog.BoundaryError, match="unfilled slot\\(s\\): layout-paths, pending-rule"):
        prompt_templates.render(CONSTANTS_FIXTURE, slots={"charter": "c.md"}, directory=directory)


def test_an_unsupplied_dynamic_slot_names_the_caller_s_omission(tmp_path: Path) -> None:
    """The failure a miswired caller gets, saying which of the two mistakes it made."""
    directory = _templates(tmp_path)

    with pytest.raises(runlog.BoundaryError, match=r"supplied no value for @!dyn\.…!@ slot\(s\): charter"):
        prompt_templates.render(CONSTANTS_FIXTURE, slots={}, constants=CONSTANTS, directory=directory)


def test_a_caller_supplying_a_composer_slot_is_told_which_half_it_belongs_to(tmp_path: Path) -> None:
    """The other half of the miswiring, and the one routing exists to catch.

    Under a single flat namespace this arrived as an unfilled slot and an unused
    value in two separate messages, and the reader inferred the rest.
    """
    directory = _templates(tmp_path)

    with pytest.raises(runlog.BoundaryError, match="the composer fills: pending-rule"):
        prompt_templates.render(
            CONSTANTS_FIXTURE,
            slots={"charter": "c.md", "pending-rule": "whatever I like"},
            constants=CONSTANTS,
            directory=directory,
        )


def test_a_caller_handing_prose_to_an_alternative_slot_reads_as_the_same_mistake(tmp_path: Path) -> None:
    """The shape the claim-graph asks had before routing: the chosen body's prose, in a slot dict."""
    directory = _templates(tmp_path)

    with pytest.raises(runlog.BoundaryError, match="the composer fills: correction"):
        prompt_templates.render(
            ALTERNATIVE_FIXTURE,
            slots={"document": "vol/one.md", "correction": "\n\n## A previous answer failed\n\nno such label"},
            alternatives={"classify-options": "classify-options-two", "correction": None},
            directory=directory,
        )


def test_an_unused_supplied_slot_fails_composition(tmp_path: Path) -> None:
    directory = _templates(tmp_path)

    with pytest.raises(runlog.BoundaryError, match="never uses"):
        prompt_templates.render(
            CONSTANTS_FIXTURE,
            slots={"charter": "c.md", "volume-list": "- one"},
            constants=CONSTANTS,
            directory=directory,
        )


# --- one expansion level, in every direction ---------------------------------
#
# The composer expands twice: the template, then each body it splices in. A
# spliced body naming another expandable slot would need a third pass, and the
# refusal has to cover the union of both vocabularies in both directions —
# nothing shipped nests today, which is exactly why an untested guard here would
# stop holding the first time someone added a slot to a fragment.


@pytest.mark.parametrize("inner", ["reader-system", "correction"])
def test_a_fragment_whose_body_names_an_expandable_slot_is_refused(tmp_path: Path, inner: str) -> None:
    directory = _templates(tmp_path, fragments_extra={"reader-system.tmpl.md": f"End with a verdict.\n\n@!{inner}!@\n"})

    complaint = rf"@!reader-system!@ resolves to .*whose body names @!{inner}!@"

    with pytest.raises(runlog.BoundaryError, match=complaint):
        prompt_templates.render(
            SPLICING_FIXTURE,
            slots={"charter": "c.md", "documents": "- one"},
            constants=CONSTANTS,
            directory=directory,
        )


@pytest.mark.parametrize("inner", ["reader-system", "classify-options"])
def test_an_alternative_whose_body_names_an_expandable_slot_is_refused(tmp_path: Path, inner: str) -> None:
    directory = _templates(tmp_path, fragments_extra={"letter-correction.tmpl.md": f"\n\nCorrection:\n\n@!{inner}!@"})

    with pytest.raises(runlog.BoundaryError, match=rf"@!correction!@ resolves to .*whose body names @!{inner}!@"):
        prompt_templates.render(
            ALTERNATIVE_FIXTURE,
            slots={"document": "vol/one.md"},
            alternatives={"classify-options": "classify-options-two", "correction": "letter-correction"},
            directory=directory,
        )


# --- the caller-selected alternatives ---------------------------------------


def test_a_caller_names_an_alternative_and_the_composer_resolves_it(tmp_path: Path) -> None:
    """The choice travels, never the prose: the caller names one and supplies its slot's value."""
    directory = _templates(tmp_path)

    brief = prompt_templates.render(
        ALTERNATIVE_FIXTURE,
        slots={"document": "vol/one.md", "candidate": "clm-bbbbbb"},
        alternatives={"classify-options": "classify-options-three", "correction": None},
        directory=directory,
    )

    assert brief == "Read vol/one.md.\n\nAnswer A, B or C for:\n\n- clm-bbbbbb\n\nAnswer."


def test_the_choice_that_is_no_choice_fills_the_slot_with_nothing(tmp_path: Path) -> None:
    """``None`` is a registered answer where the slot's absence is itself one."""
    directory = _templates(tmp_path)

    chosen, absent = (
        prompt_templates.render(
            ALTERNATIVE_FIXTURE,
            slots={"document": "vol/one.md", **extra},
            alternatives={"classify-options": "classify-options-two", "correction": correction},
            directory=directory,
        )
        for correction, extra in (("letter-correction", {"returned": "the locator names no label"}), (None, {}))
    )

    assert chosen == absent + "\n\n## A previous answer failed\n\nthe locator names no label"


@pytest.mark.parametrize(
    ("alternatives", "complaint"),
    [
        ({"classify-options": "classify-options-three"}, "no alternative chosen for slot"),
        (
            {"classify-options": "classify-options-three", "correction": None, "verdict": "letter-correction"},
            "does not declare",
        ),
        ({"classify-options": "letter-correction", "correction": None}, "takes one of"),
        ({"classify-options": "classify-options-two", "correction": "no-such-fragment"}, "takes one of"),
    ],
)
def test_a_choice_the_slot_does_not_register_is_refused(
    tmp_path: Path, alternatives: dict[str, str | None], complaint: str
) -> None:
    """Strict in both directions, like every other part of composition.

    An unanswered choice would fill a section of a dispatched prompt with
    nothing and say so nowhere, which is the one failure a composed prompt
    cannot report on its own.
    """
    directory = _templates(tmp_path)

    with pytest.raises(runlog.BoundaryError, match=complaint):
        prompt_templates.render(
            ALTERNATIVE_FIXTURE, slots={"document": "vol/one.md"}, alternatives=alternatives, directory=directory
        )


def test_a_named_but_absent_template_fails_composition(tmp_path: Path) -> None:
    directory = _templates(tmp_path)

    with pytest.raises(runlog.BoundaryError, match="not found"):
        prompt_templates.render("no-such.single.tmpl.md", slots={}, directory=directory)


def test_a_body_that_is_all_punctuation_composes_untouched(tmp_path: Path) -> None:
    """Nothing but a marker is syntax, so nothing but a marker needs escaping.

    The three shapes that used to raise at render time, keyed on the body's own
    content rather than on anything the author was writing as syntax: a JSON
    example, a shell expansion, and a LaTeX macro taking braced arguments.
    """
    body = 'Return {"step": "x"}, run ${VAR}, and typeset \\frac{a}{b}.\n'
    directory = _templates(tmp_path, extra={"raw.single.tmpl.md": body})

    assert prompt_templates.render("raw.single.tmpl.md", slots={}, directory=directory) == body


def test_an_unclosed_marker_is_refused_by_line(tmp_path: Path) -> None:
    """The property a polar delimiter buys: an opener with no closer names its own line."""
    directory = _templates(tmp_path, extra={"stray.single.tmpl.md": "Fill @!charter and stop.\n"})

    with pytest.raises(runlog.BoundaryError, match="stray slot delimiter on line\\(s\\) 1"):
        prompt_templates.render("stray.single.tmpl.md", slots={}, directory=directory)


@pytest.mark.parametrize("body", ["Fill @!Charter Path!@.\n", "Fill @!charter_path!@.\n", "Fill @!2nd-charter!@.\n"])
def test_a_marker_whose_name_is_not_a_slot_name_is_refused(tmp_path: Path, body: str) -> None:
    """A well-formed-looking pair the grammar does not admit is a defect, not a literal.

    The name class is kebab — the generator's own (``SLOT_NAME``) — so an
    underscore and a leading digit are as much a defect as a space is.
    """
    directory = _templates(tmp_path, extra={"odd.single.tmpl.md": body})

    with pytest.raises(runlog.BoundaryError, match="stray slot delimiter"):
        prompt_templates.render("odd.single.tmpl.md", slots={}, directory=directory)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_the_composed_brief_is_on_disk_before_anything_is_spawned(tmp_path: Path) -> None:
    briefs_dir = tmp_path / "briefs"
    briefs_dir.mkdir()

    path = prompt_templates.persist(briefs_dir, seq=7, step_id="p1a.review", text="brief body — ünicode")

    assert path == briefs_dir / "007-p1a.review.md"
    assert path.read_text(encoding="utf-8") == "brief body — ünicode\n"


def test_persisting_into_a_missing_directory_is_a_boundary_failure(tmp_path: Path) -> None:
    with pytest.raises(runlog.BoundaryError, match="brief directory"):
        prompt_templates.persist(tmp_path / "absent", seq=1, step_id="p0.survey", text="body")


# ---------------------------------------------------------------------------
# The template lint
# ---------------------------------------------------------------------------


def test_the_fixture_set_lints_clean(tmp_path: Path) -> None:
    directory = _templates(tmp_path)

    assert (
        prompt_templates.lint(prompt_templates.template_paths(directory), prohibited=steps.TEMPLATE_PROHIBITIONS) == []
    )


def test_the_shipped_template_directory_lints_clean() -> None:
    """The same guard aimed at ``prompt-templates/`` — the bodies a run dispatches."""
    assert prompt_templates.lint(prompt_templates.template_paths(), prohibited=steps.TEMPLATE_PROHIBITIONS) == []


def test_every_shipped_fragment_is_registered_exactly_once_and_every_registration_ships() -> None:
    """``fragments/`` and the two registries are one set, checked in both directions.

    A fragment's filename is derived from its name, so a registration and its
    file cannot disagree about spelling — but a fragment listed and not shipped,
    or shipped and listed nowhere, still can, and most fragments are named by no
    template today, so nothing else would meet the discrepancy. *Exactly once* is
    the half that keeps the two kinds apart: a composer-resolved slot and a
    caller-selected alternative reach a template by different routes, and a file
    claimed by both is a file whose route nobody can name.
    """
    directory = prompt_templates.PROMPT_TEMPLATES_DIR / prompt_templates.FRAGMENTS_DIRNAME
    shipped = {
        f"{prompt_templates.FRAGMENTS_DIRNAME}/{path.name}" for path in prompt_templates.template_paths(directory)
    }
    resolved = set(prompt_templates.FRAGMENTS.values())
    selected = set(prompt_templates.ALTERNATIVES.values())

    assert resolved | selected == shipped
    assert resolved & selected == set()


@pytest.mark.parametrize("name", prompt_templates.ALTERNATIVE_NAMES)
def test_every_shipped_alternative_ends_without_a_newline(name: str) -> None:
    """An alternative fills a slot inside a line; the template around it supplies every line break."""
    assert not prompt_templates.load(prompt_templates.ALTERNATIVES[name]).endswith("\n")


def test_no_dispatchable_template_sits_in_the_fragments_directory_or_the_other_way_round() -> None:
    """The layout is the declaration, so the step table's own names have to honour it."""
    named = {step.template for step in steps.STEPS if step.template}
    fragments = set(prompt_templates.FRAGMENTS.values()) | set(prompt_templates.ALTERNATIVES.values())

    assert named & fragments == set()
    assert all("/" not in name for name in named), "a row dispatches a template from the top level"


@pytest.mark.parametrize(
    ("body", "named"),
    [
        ("Record phase-3a once the review is clean.\n", "phase-3a"),
        ("Then depends-attributed writes the edges.\n", "depends-attributed"),
        ("Run advance-step when you are done.\n", "advance-step"),
        ("Then start-build opens the ledger.\n", "start-build"),
        ("Record OVERVIEW-DRAFTED before moving on.\n", "overview-drafted"),
        # A template that spells the write ops' flag has hand-written a token
        # `kb_util` publishes, and a rename would leave it stale. The fixture is
        # built from that constant for the same reason — a literal here would be
        # one more site a rename leaves behind.
        (f"Call the op with {kb_util.VALUES_FLAG} <your file>.\n", kb_util.VALUES_FLAG),
    ],
)
def test_a_template_naming_the_drivers_own_business_is_flagged(tmp_path: Path, body: str, named: str) -> None:
    directory = _templates(tmp_path, extra={"leak.single.tmpl.md": body})

    findings = prompt_templates.lint(prompt_templates.template_paths(directory), prohibited=steps.TEMPLATE_PROHIBITIONS)

    assert [finding for finding in findings if named in finding and finding.startswith("leak.single.tmpl.md:1:")]


def test_start_reads_as_prose_but_not_as_a_stage_argument(tmp_path: Path) -> None:
    prose = _templates(tmp_path / "a", extra={"ok.single.tmpl.md": "Start with the charter, then start the survey.\n"})
    naming = _templates(tmp_path / "b", extra={"bad.single.tmpl.md": "Then --stage start is recorded.\n"})

    assert prompt_templates.lint(prompt_templates.template_paths(prose), prohibited=steps.TEMPLATE_PROHIBITIONS) == []
    assert prompt_templates.lint(prompt_templates.template_paths(naming), prohibited=steps.TEMPLATE_PROHIBITIONS)


def test_the_lint_reports_a_stray_delimiter_rather_than_raising(tmp_path: Path) -> None:
    """A template defect the lint has to survive: it reports every file, not the first bad one."""
    directory = _templates(tmp_path, extra={"stray.single.tmpl.md": "Review @!documents and stop.\n"})

    findings = prompt_templates.lint(prompt_templates.template_paths(directory), prohibited=steps.TEMPLATE_PROHIBITIONS)

    assert any("stray slot delimiter" in finding for finding in findings)


def test_template_paths_tolerates_an_absent_directory(tmp_path: Path) -> None:
    assert prompt_templates.template_paths(tmp_path / "absent") == ()
