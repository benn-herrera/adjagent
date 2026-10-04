"""Config validation and the barrier-decision vocabulary.

Every refusal here is exit 13 at load, before anything runs: a typo must not
become a mid-build stop three hours in. The tests are a table of the ways a
config or a ``--decide`` value can be wrong, plus the typed values a good one
yields.
"""

from pathlib import Path

import pytest

from kb_tools import kb_pipeline
from kb_tools.kb_driver import config, steps

MINIMAL = """
[run]
sources = ["AcmeWidgets.tex"]
"""

# A stand-in registry, injected so answer-set validation is testable without
# importing `barriers`. The pair is synthetic and registered nowhere — config
# checks a decision's form and takes its vocabulary from whatever registry the
# caller hands it, so nothing here asserts anything about a real barrier.
ADMISSIBLE = {
    "example-stage.example-kind": frozenset({"approve", "revise", "cancel"}),
}


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "driver-run.toml"
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Accepted configs
# ---------------------------------------------------------------------------


def test_minimal_config_applies_every_default(tmp_path: Path) -> None:
    cfg = config.load(_write(tmp_path, MINIMAL))

    assert cfg.run.sources == ("AcmeWidgets.tex",)
    assert cfg.run.charter_file == Path(kb_pipeline.CHARTER_RELPATH)
    assert cfg.run.runner is None
    assert cfg.timeouts.silence_seconds == config.DEFAULT_SILENCE_SECONDS
    assert cfg.retry.backoff_seconds == config.DEFAULT_BACKOFF_SECONDS
    assert cfg.log.level == "INFO"
    assert cfg.log.run_dir == Path(config.default_run_dir())
    assert cfg.decisions == {}


def test_full_config_is_typed_through(tmp_path: Path) -> None:
    body = """
[run]
sources = ["a.tex", "b.tex"]
charter_file = "scratch/charter.md"
runner = "make"

[timeouts]
silence_seconds = 30

[retry]
transport_attempts = 2
backoff_seconds = [1, 2, 3]

[log]
level = "DEBUG"
run_dir = "/var/tmp/kb-driver"

[barriers.example-stage.example-kind]
decision = "approve"
note = "Approve."
"""
    cfg = config.load(_write(tmp_path, body), admissible=ADMISSIBLE)

    assert cfg.run.sources == ("a.tex", "b.tex")
    assert cfg.run.charter_file == Path("scratch/charter.md")
    assert cfg.run.runner == "make"
    assert cfg.timeouts.silence_seconds == 30
    assert cfg.retry.transport_attempts == 2
    assert cfg.retry.backoff_seconds == (1, 2, 3)
    assert cfg.log.run_dir == Path("/var/tmp/kb-driver")

    decision = cfg.decisions["example-stage.example-kind"]
    assert (decision.stage, decision.kind, decision.answer) == ("example-stage", "example-kind", "approve")
    assert decision.note == "Approve."
    assert decision.source == "config"
    assert decision.spec == "example-stage.example-kind=approve"


# ---------------------------------------------------------------------------
# No file at all, and the two doors together
# ---------------------------------------------------------------------------


def test_flags_alone_specify_a_run_and_every_other_field_defaults() -> None:
    """The launch that composes nothing: one field given, the rest as they ship."""
    cfg = config.load(None, run_overrides={"sources": ("a.tex", "b.tex")})

    assert cfg.path is None
    assert cfg.run.sources == ("a.tex", "b.tex")
    assert cfg.run.charter_file == Path(kb_pipeline.CHARTER_RELPATH)
    assert cfg.run.runner is None
    assert cfg.log.run_dir == Path(config.default_run_dir())
    assert cfg.decisions == {}


def test_a_flag_wins_over_the_file_for_the_field_it_names(tmp_path: Path) -> None:
    """Precedence, and its bound: an override replaces its own field and no other."""
    body = MINIMAL + 'runner = "make"\n[barriers.example-stage.example-kind]\ndecision = "approve"\n'

    cfg = config.load(
        _write(tmp_path, body),
        run_overrides={"sources": ("flagged.tex",)},
        admissible=ADMISSIBLE,
    )

    assert cfg.run.sources == ("flagged.tex",), "a repeated --source replaces the list rather than extending it"
    assert cfg.run.runner == "make", "a field no flag names keeps the file's value"
    assert cfg.decisions["example-stage.example-kind"].answer == "approve"


def test_the_field_with_no_default_is_refused_naming_both_doors() -> None:
    with pytest.raises(config.ConfigError) as excinfo:
        config.load(None, run_overrides={"no_inference": True})

    message = str(excinfo.value)
    assert "[run] sources" in message
    assert config.SOURCE_FLAG in message


def test_a_flag_value_is_refused_in_the_same_words_its_config_key_would_be() -> None:
    """One vocabulary for both doors: the flags carry no validation of their own."""
    with pytest.raises(config.ConfigError, match=r"\[run\] through"):
        config.load(None, run_overrides={"sources": ("a.tex",), "through": "no-such-stage"})


@pytest.mark.parametrize(
    ("path", "overrides", "expected"),
    [
        (Path("driver-run.toml"), {}, "--config driver-run.toml"),
        (None, {"sources": ("a.tex", "b c.tex")}, "--source a.tex --source 'b c.tex'"),
        (Path("driver-run.toml"), {"no_inference": True}, f"--config driver-run.toml {config.NO_INFERENCE_FLAG}"),
        (None, {}, ""),
    ],
)
def test_the_resume_line_reproduces_what_the_run_was_given(
    path: Path | None, overrides: dict[str, object], expected: str
) -> None:
    """The relay card hands back an invocation the operator made, never one they did not.

    Both doors together is the case that matters: a resume naming only the
    config would drop the flag that overrode it and resume a different run.
    """
    assert config.invocation(path, overrides) == expected


@pytest.mark.parametrize(
    ("run_dir", "expected"),
    [
        (None, "--source a.tex"),
        (config.default_run_dir(), "--source a.tex"),
        (Path("/outside/runs"), f"--source a.tex {config.RUN_DIR_FLAG} /outside/runs"),
    ],
)
def test_the_resume_line_names_the_run_directory_wherever_it_is_not_the_default(
    run_dir: Path | str | None, expected: str
) -> None:
    """A resumed run's evidence lands where the first run's did, or the line is wrong.

    ``--run-dir`` is what a run launched outside the default parent is launched
    with, and a resume line that dropped it would file the resumed run's
    evidence under the default and strand the first run's. The default itself
    stays unspelled: a bare invocation already finds it.
    """
    assert config.invocation(None, {"sources": ("a.tex",)}, run_dir=run_dir) == expected


def test_the_run_directory_flag_wins_over_the_file_and_reaches_the_resume_line(tmp_path: Path) -> None:
    """One rule for both doors, and one effective value for both readers.

    ``--run-dir`` names a ``[log]`` key rather than a ``[run]`` one, and takes
    the same precedence. ``log.run_dir`` is where the run directory is laid out
    and ``invocation`` is what the card hands back, so the two reading one value
    is what keeps a card from naming a directory the run did not use.
    """
    body = MINIMAL + '[log]\nrun_dir = "/var/tmp/configured"\n'

    configured = config.load(_write(tmp_path, body))
    flagged = config.load(_write(tmp_path, body), run_dir=Path("/outside/runs"))

    assert configured.log.run_dir == Path("/var/tmp/configured")
    assert f"{config.RUN_DIR_FLAG} /var/tmp/configured" in configured.invocation
    assert flagged.log.run_dir == Path("/outside/runs")
    assert f"{config.RUN_DIR_FLAG} /outside/runs" in flagged.invocation


# ---------------------------------------------------------------------------
# Refused configs — the validation table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "body", "expected"),
    [
        ("missing sources", '[run]\nrunner = "just"\n', "sources"),
        ("empty sources", "[run]\nsources = []\n", "sources"),
        ("sources not strings", "[run]\nsources = [1]\n", "sources"),
        ("missing [run]", '[log]\nlevel = "INFO"\n', "sources"),
        ("unknown runner", MINIMAL + 'runner = "cmake"\n', "runner"),
        ("timeout not an integer", MINIMAL + '[timeouts]\nsilence_seconds = "fast"\n', "silence_seconds"),
        ("timeout not positive", MINIMAL + "[timeouts]\nsilence_seconds = 0\n", "silence_seconds"),
        ("backoff not integers", MINIMAL + '[retry]\nbackoff_seconds = ["5s"]\n', "backoff_seconds"),
        ("unknown log level", MINIMAL + '[log]\nlevel = "CHATTY"\n', "level"),
        (
            "barrier table has no decision",
            MINIMAL + '[barriers.example-stage.example-kind]\nnote = "hi"\n',
            "decision",
        ),
        (
            "barrier stage is not a table",
            MINIMAL + '[barriers]\nexample-stage = "approve"\n',
            "barriers.example-stage",
        ),
    ],
)
def test_invalid_config_is_refused_naming_the_key(tmp_path: Path, case: str, body: str, expected: str) -> None:
    with pytest.raises(config.ConfigError) as excinfo:
        config.load(_write(tmp_path, body))
    assert expected in str(excinfo.value), case


@pytest.mark.parametrize(
    ("body", "named"),
    [
        pytest.param('[claude]\ncommand = ["claude"]\n', "[claude]", id="the-cli-section"),
        pytest.param('permission_mode = "bypassPermissions"\n', "permission_mode", id="the-permission-mode"),
        pytest.param("[timeouts]\nsingle_seconds = 60\n", "single_seconds", id="the-total-bound"),
        pytest.param('[timeouts.by_step]\n"ov.docs" = 14400\n', "by_step", id="the-per-step-total-bound"),
    ],
)
def test_a_key_of_the_retired_cli_transport_is_refused_as_unknown_naming_it(
    tmp_path: Path, body: str, named: str
) -> None:
    """Nothing reads them: every call is one request to the server the environment names.

    A file still carrying one means something by it — a model, a mode, a bound —
    and a build that ignored it would not be the build the file asks for.
    """
    with pytest.raises(config.ConfigError, match="unknown") as excinfo:
        config.load(_write(tmp_path, MINIMAL + body))

    assert named in str(excinfo.value)


@pytest.mark.parametrize("door", ["file", "flag"])
def test_an_unknown_run_key_is_refused_naming_it(tmp_path: Path, door: str) -> None:
    """[run] has no enumerated vocabulary to check against — a key config.load
    never reads is refused all the same, both doors alike, because a flag is
    refused in the same words its config key would be.
    """
    with pytest.raises(config.ConfigError) as excinfo:
        if door == "file":
            config.load(_write(tmp_path, MINIMAL + 'no_inferrence = "true"\n'))
        else:
            config.load(None, run_overrides={"sources": ("a.tex",), "no_inferrence": "true"})

    message = str(excinfo.value)
    assert "[run]" in message
    assert "no_inferrence" in message


def test_build_mode_is_refused_by_the_general_unknown_key_rule(tmp_path: Path) -> None:
    """The retired per-key allowlist is gone; the general rule subsumes it.

    ``build_mode`` once selected which rows a build walked and was refused by
    name. It reads nothing now, so it is caught the same way any other typo
    in ``[run]`` is: named as an unrecognized key.
    """
    with pytest.raises(config.ConfigError) as excinfo:
        config.load(_write(tmp_path, MINIMAL + 'build_mode = "fresh"\n'))

    message = str(excinfo.value)
    assert "[run]" in message
    assert "build_mode" in message


def test_multiple_unknown_run_keys_are_all_reported_in_one_refusal(tmp_path: Path) -> None:
    body = MINIMAL + 'no_inferrence = true\nbuild_mode = "fresh"\n'

    with pytest.raises(config.ConfigError) as excinfo:
        config.load(_write(tmp_path, body))

    message = str(excinfo.value)
    assert "no_inferrence" in message
    assert "build_mode" in message


def test_every_recognized_run_key_still_loads(tmp_path: Path) -> None:
    """The refusal reads what config.load actually consults — every field it
    is documented to accept must still load clean."""
    body = """
[run]
sources = ["a.tex"]
bibliography = "refs.bib"
charter_file = "scratch/charter.md"
runner = "make"
no_inference = true
through = "start"
"""
    cfg = config.load(_write(tmp_path, body))

    assert cfg.run.sources == ("a.tex",)
    assert cfg.run.bibliography == "refs.bib"
    assert cfg.run.charter_file == Path("scratch/charter.md")
    assert cfg.run.runner == "make"
    assert cfg.run.no_inference is True
    assert cfg.run.through == "start"


# One row per section the unknown-key refusal covers, carrying that section's
# complete valid key set. ``[barriers]`` is absent because it is the one
# section with a vocabulary of its own to be checked against — the registry's
# registered pairs.
SECTION_VALID_KEYS = [
    ("timeouts", "[timeouts]\nsilence_seconds = 30\n"),
    ("retry", "[retry]\ntransport_attempts = 2\nbackoff_seconds = [1, 2]\n"),
    ("log", '[log]\nlevel = "DEBUG"\nrun_dir = "/var/tmp/kb-driver"\n'),
]
_SECTIONS = [section for section, _ in SECTION_VALID_KEYS]


@pytest.mark.parametrize("section", _SECTIONS)
def test_an_unknown_key_in_any_section_is_refused_naming_it(tmp_path: Path, section: str) -> None:
    """What ``[run]`` already refused, every other section refuses too.

    A key nothing consults is not partial: the default stays in force and the
    run reports itself configured, so a typo buys an inert setting and no
    complaint.
    """
    with pytest.raises(config.ConfigError) as excinfo:
        config.load(_write(tmp_path, MINIMAL + f'[{section}]\nno_such_key = "x"\n'))

    message = str(excinfo.value)
    assert f"[{section}]" in message
    assert "no_such_key" in message


@pytest.mark.parametrize(("section", "body"), SECTION_VALID_KEYS, ids=_SECTIONS)
def test_every_recognized_key_of_a_section_still_loads(tmp_path: Path, section: str, body: str) -> None:
    """The refusal reads what config.load actually consults, so a key it does
    consult by some route other than ``.get`` would be refused as unknown.
    Each section's whole valid vocabulary, given alone, must load clean."""
    config.load(_write(tmp_path, MINIMAL + body))


def test_missing_config_file_is_a_config_error(tmp_path: Path) -> None:
    with pytest.raises(config.ConfigError, match="not found"):
        config.load(tmp_path / "absent.toml")


def test_malformed_toml_is_a_config_error(tmp_path: Path) -> None:
    with pytest.raises(config.ConfigError, match="not valid TOML"):
        config.load(_write(tmp_path, "[run\nsources = "))


def test_out_of_set_barrier_decision_is_refused_at_load(tmp_path: Path) -> None:
    body = MINIMAL + '[barriers.example-stage.example-kind]\ndecision = "approve-ish"\n'
    with pytest.raises(config.ConfigError, match="not admissible"):
        config.load(_write(tmp_path, body), admissible=ADMISSIBLE)


def test_unregistered_barrier_pair_is_refused_at_load(tmp_path: Path) -> None:
    body = MINIMAL + '[barriers.phase-9.made-up]\ndecision = "proceed"\n'
    with pytest.raises(config.ConfigError, match="unknown barrier"):
        config.load(_write(tmp_path, body), admissible=ADMISSIBLE)


def test_barrier_answers_are_unchecked_without_a_registry(tmp_path: Path) -> None:
    # Form only: the registry lives above config in the dependency direction,
    # so a caller that has not loaded it gets structural validation alone.
    body = MINIMAL + '[barriers.example-stage.example-kind]\ndecision = "approve-ish"\n'
    assert config.load(_write(tmp_path, body)).decisions["example-stage.example-kind"].answer == "approve-ish"


# ---------------------------------------------------------------------------
# --decide
# ---------------------------------------------------------------------------


def test_decide_parses_pair_answer_and_note() -> None:
    decision = config.parse_decision("example-stage.example-kind=revise:tighten the domain split")
    assert (decision.stage, decision.kind, decision.answer) == ("example-stage", "example-kind", "revise")
    assert decision.note == "tighten the domain split"
    assert decision.source == "cli"


def test_decide_splits_a_dotted_stage_id_on_its_last_dot() -> None:
    decision = config.parse_decision("example-stage.2.example-kind=stop")
    assert (decision.stage, decision.kind) == ("example-stage.2", "example-kind")


@pytest.mark.parametrize(
    "spec",
    [
        "example-stage.example-kind",  # no answer
        "example-kind=approve",  # no stage
        "=approve",  # no pair
        "example-stage.example-kind=",  # empty answer
        "example-stage.example-kind=Approve",  # answers are lowercase tokens
        "example-stage.example-kind=approve now",  # free text belongs after the colon
        ".example-kind=approve",  # empty stage
    ],
)
def test_malformed_decide_is_refused(spec: str) -> None:
    with pytest.raises(config.ConfigError, match="malformed"):
        config.parse_decision(spec)


def test_decide_answer_is_checked_against_the_registry() -> None:
    with pytest.raises(config.ConfigError, match="not admissible"):
        config.parse_decision("example-stage.example-kind=maybe", admissible=ADMISSIBLE)


def test_decide_pair_is_checked_against_the_registry() -> None:
    with pytest.raises(config.ConfigError, match="unknown barrier"):
        config.parse_decision("phase-9.made-up=proceed", admissible=ADMISSIBLE)


# ---------------------------------------------------------------------------
# The mode flag, and the one bound
# ---------------------------------------------------------------------------


def test_the_mode_flag_defaults_off_and_is_carried_through(tmp_path: Path) -> None:
    assert config.load(_write(tmp_path, MINIMAL)).run.no_inference is False
    assert config.load(_write(tmp_path, MINIMAL), run_overrides={"no_inference": True}).run.no_inference is True
    assert config.load(_write(tmp_path, MINIMAL + "no_inference = true\n")).run.no_inference is True


def test_the_retired_audit_key_is_refused_at_load(tmp_path: Path) -> None:
    """``doc_audit`` named a stage the pipeline no longer has, so a file carrying it means nothing runnable."""
    with pytest.raises(config.ConfigError, match="doc_audit"):
        config.load(_write(tmp_path, MINIMAL + "doc_audit = true\n"))


def test_the_mode_flag_is_rendered_into_the_resume_line_and_the_bound_is_not() -> None:
    """What a resume must keep, and what it must drop.

    A resume dropping the mode flag would change the build half way through,
    spending the calls it was told to do without. A resume keeping the bound
    would stop in the same place forever, which is what resuming is for.
    """
    line = config.invocation(None, {"sources": ("a.tex",), "no_inference": True, "through": "start"})

    assert line == f"--source a.tex {config.NO_INFERENCE_FLAG}"
    assert config.THROUGH_FLAG not in line


def test_a_run_spending_no_inference_may_still_be_bounded_anywhere(tmp_path: Path) -> None:
    """The refusal that went with the old meaning is gone, and this is why.

    ``no_inference`` bounded the walk once, so a ``through`` past where it
    stopped was unreachable and refused at load. It bounds nothing now — every
    stage is walked — so every stage is a reachable bound and the two compose
    without a rule pairing them.
    """
    for stage in kb_pipeline.STAGE_IDS:
        cfg = config.load(_write(tmp_path, MINIMAL + "no_inference = true\n"), run_overrides={"through": stage})
        assert cfg.run.through == stage and cfg.run.no_inference


def test_the_rows_a_no_inference_run_drops_are_the_step_tables_answer() -> None:
    """Config carries the flag and classifies nothing — the table owns which rows go."""
    dropped = [step.id for step in steps.STEPS if step.spends_inference]

    assert dropped
    assert all(not steps.applies(step, spend_inference=False) for step in steps.STEPS if step.id in dropped)
