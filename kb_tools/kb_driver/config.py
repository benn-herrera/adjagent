"""Driver configuration: TOML load, typed validation, defaults.

A run is specified by a config file, by command-line flags, or by both:
:func:`load` takes an optional path and a mapping of ``[run]`` overrides, and
either may be empty. Defaults live here, which is what lets a launch carry
nothing but ``--source``, the one field with no default. Every rejection raises
:class:`ConfigError`, which ``cli`` translates to exit 13 — validation happens
at load, before anything runs, so a typo cannot become a mid-build stop three
hours in, and a flag is refused in the same words its config key would be.

**A flag wins over the file for the field it names.** The command line is the
more specific statement of one run, and it is the precedence ``--decide``
already has over the ``[barriers.*]`` tables — one rule for both doors rather
than a rule per door. A repeated ``--source`` replaces the configured list
outright rather than extending it: a merge would leave no way to say "these
sources and not the file's".

``permission_mode`` defaults to ``bypassPermissions`` because the driver is
headless: a mode that gates a tool the build needs stops a spawned ``claude``
with nobody there to answer it, and ``bypassPermissions`` is the only mode a
run has been driven to completion under. What the build may do is bounded by
the environment it runs in, not by this field; ``--permission-mode`` narrows
it for a run that wants it narrowed.

No model key exists, by design: an explicit ``--model``
overrides a seat's frontmatter pin, so the driver never passes the flag, and a
``[claude]`` key attempting a per-step model is rejected at load rather than
silently ignored. Model routing survives through ``command``/``env``.

Barrier decisions arrive through two doors with one vocabulary — the
``[barriers.<stage>.<kind>]`` config tables and the repeatable
``--decide <stage>.<kind>=<answer>[:<free text>]`` — so an operator
answer and a config answer cannot diverge in form. Both are checked against
the barrier registry's admissible answers when one is supplied; the registry
lives in ``barriers.py`` and is injected rather than imported, since config
load sits below it in the dependency direction.

**There is no build-mode setting, and the key that carried one is refused.** A
build is either a launch or a resume, and a resume is not configured — it is
what a ledger with recorded stages already says, re-derived from the ledger on
every invocation. A setting whose vocabulary has one member is a question with
one answer, so ``[run] build_mode``, its vocabulary and its default are deleted
outright rather than kept as a single-valued vestige. It needs no key of its
own to be refused by, because **every key :func:`load` does not read is
refused, naming its section and the key** — in ``[run]``, ``[claude]``,
``[timeouts]``, ``[retry]`` and ``[log]`` alike. An unknown key is never inert:
a file that still carries one means something by it, and silently ignoring it
would walk a different build than the file asks for. ``[barriers]`` is checked
differently because it is the one section with a vocabulary to check
against — the registry's own registered pairs, below.

**One field says what a run is made of; one bounds how far it goes.**
``no_inference`` drops every row that would cost a model call, row by row, and
the walk carries on past them to a finished build. ``through`` names the last
stage to walk, by stage id or by the stage's own display name, resolved here to
an id so nothing downstream deals in two spellings. The first is rendered back
into the resume line and the second is not.

A stage id containing a dot must be quoted in TOML — e.g. ``[barriers."phase-1.5".some-kind]``
— because TOML reads an unquoted dot as another level of table nesting. No
stage id today has one, but the vocabulary does not promise that it never will.

Stdlib only.
"""

import re
import shlex
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .. import kb_pipeline, kb_util

# The step-id vocabulary `[timeouts.by_step]` is keyed by. Imported rather than
# injected the way the barrier registry above is: what made the registry a
# parameter is that `barriers` imports this module, and `steps` does not.
from . import steps

# --- vocabularies -----------------------------------------------------------

# The three flags that specify a run, named here rather than in ``cli`` because
# this module both validates what they carry and renders them back into the
# resume line every relay card prints. One spelling, two readers.
CONFIG_FLAG = "--config"
SOURCE_FLAG = "--source"
PERMISSION_MODE_FLAG = "--permission-mode"

# The mode flag. It specifies what the run is made of rather than how far it
# goes, so it is rendered back into the resume line (:func:`invocation`).
#
# `--no-inference` spends no model call: every row that would cost one is
# dropped and the walk continues past it, so the build closes out without them.
# Spelled once in `kb_util`, because the driver passes the same flag through to
# `advance-step`, where the stage table decides what it excuses.
NO_INFERENCE_FLAG = kb_util.NO_INFERENCE_FLAG

# The one flag that bounds an invocation rather than specifying the build, and
# so the one this module does not render back: see :func:`invocation`.
THROUGH_FLAG = "--through"

# Where this run's evidence goes: `[log] run_dir`'s flag, and the one flag that
# names a `[log]` key rather than a `[run]` one. This module resolves it against
# the file and renders it back into the resume line — a card that dropped it
# would hand back an invocation whose evidence lands somewhere else
# (:func:`invocation`). Spelled in `kb_util` for `NO_INFERENCE_FLAG`'s reason:
# the flag is published beside the invocation a consuming repo reaches these
# modules through, so one spelling serves whatever renders a command line.
RUN_DIR_FLAG = kb_util.RUN_DIR_FLAG

# The installed CLI's permission modes, probed at 2.1.220 (`--permission-mode`
# rejects anything else and names the set). Config load validates against this
# list and refuses an unknown mode at load rather than discovering it at the
# first call.
PERMISSION_MODES = ("acceptEdits", "auto", "bypassPermissions", "manual", "dontAsk", "plan")

RUNNERS = ("just", "make")
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

# --- defaults ---------------------------------------------------------------

DEFAULT_PERMISSION_MODE = "bypassPermissions"
DEFAULT_CLAUDE_COMMAND = ("claude",)
DEFAULT_SINGLE_SECONDS = 1800
DEFAULT_SILENCE_SECONDS = 600
DEFAULT_TRANSPORT_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = (5, 30)
DEFAULT_LOG_LEVEL = "INFO"
# The run directory's parent: LATEST lives here, one <run-id> directory per run
# beneath it. The run lock does NOT — it is anchored at the repo root, so that
# changing this value cannot buy a second concurrent run.
DEFAULT_RUN_DIR = ".claude-temp/kb-driver"


class ConfigError(ValueError):
    """A config file or ``--decide`` value the driver refuses. Exit 13."""


# --- typed sections ---------------------------------------------------------


@dataclass(frozen=True)
class Decision:
    """One barrier answer, from config or from ``--decide``."""

    stage: str
    kind: str
    answer: str
    note: str = ""
    source: str = "config"

    @property
    def pair(self) -> str:
        return f"{self.stage}.{self.kind}"

    @property
    def spec(self) -> str:
        """The ``--decide`` spelling of this decision, for batons and exit.json."""
        return f"{self.pair}={self.answer}"


@dataclass(frozen=True)
class RunSection:
    sources: tuple[str, ...]
    permission_mode: str
    #: Where this run looks for a charter, defaulted to ``kb_pipeline``'s own
    #: durable path rather than restated here. A charter is an input that must
    #: already stand when the build opens, and the ``start`` boundary's body
    #: names it permanently — so the default may never point into
    #: ``.claude-temp/``, which staging deletes wholesale: a ledger entry naming
    #: a wiped path names nothing. Configurable all the same, for a consumer
    #: that keeps its charter elsewhere in the tree.
    charter_file: Path
    runner: str | None
    #: The one bibliography this run resolves citations against, where a run
    #: needs the set narrowed to a single file. Defaulted rather than required,
    #: so that ``sources`` stays the one field with no default and the launch
    #: line stays the sources it already carries: given none, ``run.py`` passes
    #: every ``.bib`` sitting beside them, which the reader merges.
    bibliography: str = ""
    #: Spend no model call. Every row that would cost one is dropped
    #: (``steps.applies``) and the walk continues past it, so this specifies
    #: what the build is made of rather than bounding how far it goes.
    no_inference: bool = False
    #: The last stage this invocation walks, as a **resolved stage id** — the
    #: display name a caller may have written is resolved at load, so nothing
    #: downstream deals in anything but ids. Empty is the whole build.
    through: str = ""


@dataclass(frozen=True)
class ClaudeSection:
    command: tuple[str, ...]
    env: Mapping[str, str]


@dataclass(frozen=True)
class TimeoutSection:
    single_seconds: int
    silence_seconds: int
    #: Per-step total bounds, keyed by step id. The keys are checked against the
    #: step table at load and the values against the same positivity rule the
    #: three scalars above take, because a key naming no step leaves the default
    #: silently in force and a non-positive one is refused mid-build or nowhere.
    by_step: Mapping[str, int]


@dataclass(frozen=True)
class RetrySection:
    transport_attempts: int
    backoff_seconds: tuple[int, ...]


@dataclass(frozen=True)
class LogSection:
    level: str
    run_dir: Path


@dataclass(frozen=True)
class DriverConfig:
    path: Path | None  # None when the flags are the whole of the specification
    #: The flags that reproduce this run, for the resume line on every relay
    #: card. Rendered at load from what the run was actually given, so a card
    #: cannot hand back an invocation the operator never made.
    invocation: str
    run: RunSection
    claude: ClaudeSection
    timeouts: TimeoutSection
    retry: RetrySection
    log: LogSection
    decisions: Mapping[str, Decision]  # keyed by "<stage>.<kind>"


# --- typed field helpers ----------------------------------------------------


def _table(parent: Mapping[str, object], key: str, *, section: str) -> dict:
    value = parent.get(key, {})
    if not isinstance(value, dict):
        raise ConfigError(f"[{section}] must be a table, got {type(value).__name__}")
    return value


class _TrackedTable(dict):
    """A table that remembers every key read through :meth:`get`.

    No section has an enumerated key vocabulary to check an unknown key
    against — the recognized set is derived from the reads themselves, so it
    cannot drift from what :func:`load` actually consults. Every field helper
    below reads through ``.get``, so wrapping the table is enough to capture
    the whole set with no change to the helpers. :func:`_table` reads through
    ``.get`` too, which is what makes a nested table a read key of its parent
    rather than an unknown one: ``[timeouts.by_step]`` and ``[claude] env``
    reach their values through the helper that fetched the table, and the
    fetch is the read.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.read_keys: set[str] = set()

    def get(self, key: str, default: object = None) -> object:
        self.read_keys.add(key)
        return super().get(key, default)


def _refuse_unknown_keys(table: _TrackedTable, *, section: str) -> None:
    """Refuse every key of one section that :func:`load` did not read.

    Called once per section, after that section is built, so what counts as
    recognized is the set of reads that built it. The state refused is a
    hand-authored config file — an operator's ``--config`` or a consuming
    repo's committed one — where a key sits that nothing consults: the default
    stays in force and the run reports itself configured.
    """
    unknown = sorted(set(table) - table.read_keys)
    if unknown:
        plural = "s" if len(unknown) > 1 else ""
        raise ConfigError(f"[{section}] unknown key{plural}: {', '.join(unknown)}")


def _required(section: str, key: str, flag: str) -> str:
    """The refusal for a field with no default, naming both doors it can arrive through."""
    both = f", or pass {flag}" if flag else ""
    return f"[{section}] {key} is required and has no default{both}"


def _str_field(
    table: Mapping[str, object],
    key: str,
    *,
    section: str,
    default: str | None = None,
    choices: Sequence[str] | None = None,
    flag: str = "",
) -> str:
    value = table.get(key, default)
    if value is None:
        raise ConfigError(_required(section, key, flag))
    if not isinstance(value, str):
        raise ConfigError(f"[{section}] {key} must be a string, got {type(value).__name__}")
    if choices is not None and value not in choices:
        raise ConfigError(f"[{section}] {key} = {value!r} is not one of: {', '.join(choices)}")
    return value


def _str_list_field(
    table: Mapping[str, object],
    key: str,
    *,
    section: str,
    default: tuple[str, ...] | None = None,
    flag: str = "",
) -> tuple[str, ...]:
    value = table.get(key, default)
    if value is None:
        raise ConfigError(_required(section, key, flag))
    if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"[{section}] {key} must be a list of strings")
    if not value:
        raise ConfigError(f"[{section}] {key} must not be empty")
    return tuple(value)


def _bool_field(table: Mapping[str, object], key: str, *, section: str, default: bool) -> bool:
    value = table.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"[{section}] {key} must be true or false, got {type(value).__name__}")
    return value


def _stage_field(table: Mapping[str, object], key: str, *, section: str, flag: str) -> str:
    """A stage bound, resolved from either spelling to the id everything downstream uses.

    An unresolvable name is refused here rather than at the stage it would have
    stopped at, and the refusal carries the whole vocabulary in walk order:
    a bound is a thing an operator types from memory, so the correction has to
    be in the message that rejects it.
    """
    value = table.get(key, "")
    if not isinstance(value, str):
        raise ConfigError(f"[{section}] {key} must be a string, got {type(value).__name__}")
    if not value:
        return ""
    stage = kb_pipeline.resolve_stage(value)
    if stage is None:
        raise ConfigError(
            f"[{section}] {key} = {value!r} names no stage (also settable as {flag}). "
            f"The stages this build walks, in order: {kb_pipeline.stage_vocabulary()}"
        )
    return stage.id


def _int_field(table: Mapping[str, object], key: str, *, section: str, default: int) -> int:
    value = table.get(key, default)
    # bool is an int subclass; a `true` here is a typo, not a duration.
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(f"[{section}] {key} must be an integer, got {type(value).__name__}")
    if value <= 0:
        raise ConfigError(f"[{section}] {key} must be positive, got {value}")
    return value


def _int_list_field(
    table: Mapping[str, object], key: str, *, section: str, default: tuple[int, ...]
) -> tuple[int, ...]:
    value = table.get(key, default)
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        raise ConfigError(f"[{section}] {key} must be a list of integers")
    return tuple(value)


def _str_map(table: Mapping[str, object], key: str, *, section: str) -> dict[str, str]:
    mapping = _table(table, key, section=f"{section}.{key}")
    for name, value in mapping.items():
        if not isinstance(value, str):
            raise ConfigError(f"[{section}.{key}] {name} must be a string, got {type(value).__name__}")
    return dict(mapping)


def _int_map(table: Mapping[str, object], key: str, *, section: str, keys: Sequence[str]) -> dict[str, int]:
    """A table of positive durations, keyed by a closed vocabulary.

    Both refusals are the ones :func:`_int_field` already makes for a duration
    this module names itself, applied to one the caller names instead. A key
    outside the vocabulary is a misspelling, and left unrefused it does nothing
    at all — the default stays in force and the run reads as configured. A
    non-positive value reaches ``call.Caller``'s own spawn boundary instead, as a
    boundary error mid-build, where every other duration setting is refused at
    load. The refusal carries the whole vocabulary, because a step id is a thing
    an operator types from memory.
    """
    mapping = _table(table, key, section=f"{section}.{key}")
    for name, value in mapping.items():
        if name not in keys:
            raise ConfigError(
                f"[{section}.{key}] {name!r} names no step. The steps this build walks, " f"in order: {', '.join(keys)}"
            )
        if not isinstance(value, int) or isinstance(value, bool):
            raise ConfigError(f"[{section}.{key}] {name} must be an integer, got {type(value).__name__}")
        if value <= 0:
            raise ConfigError(f"[{section}.{key}] {name} must be positive, got {value}")
    return dict(mapping)


def _reject_model_keys(claude_raw: Mapping[str, object]) -> None:
    """Refuse any ``[claude]`` model key.

    An explicit ``--model`` overrides a seat's frontmatter pin, so the driver
    omits the flag unconditionally. An honored
    model key would therefore be a lie; the key is named and refused at load
    instead, so exit 13's baton has a key to report.

    It runs before the section is built, so a model key always meets this
    refusal and never the general unknown-key one: the two never report the
    same key, and the operator gets the message that says why no such key
    exists rather than the one that says this one is unrecognized.
    """
    for key in claude_raw:
        if key == "model" or key.startswith("model_"):
            raise ConfigError(
                f"[claude] {key} is rejected: no model key exists, by design. An explicit --model "
                "overrides a seat's frontmatter pin, so the driver never passes it. Route models "
                "through [claude] command/env instead."
            )


# --- barrier decisions ------------------------------------------------------

# <stage>.<kind>=<answer>[:<free text>]. The stage may itself contain dots
# (a hypothetical "phase-1.5", say), the kind never does, so the pair splits
# on its last dot.
_PAIR_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]*$")
_ANSWER_RE = re.compile(r"^[a-z][a-z\-]*$")


def _check_admissible(decision: Decision, admissible: Mapping[str, frozenset[str]] | None) -> None:
    if admissible is None:
        return
    answers = admissible.get(decision.pair)
    if answers is None:
        raise ConfigError(f"unknown barrier {decision.pair!r}: not a registered (stage, kind) pair")
    if decision.answer not in answers:
        raise ConfigError(
            f"barrier {decision.pair} decision {decision.answer!r} is not admissible; "
            f"expected one of: {', '.join(sorted(answers))}"
        )


def parse_decision(
    spec: str,
    *,
    source: str = "cli",
    admissible: Mapping[str, frozenset[str]] | None = None,
) -> Decision:
    """Parse one ``--decide`` value. Malformed input is a ConfigError."""
    pair, sep, value = spec.partition("=")
    if not sep:
        raise ConfigError(f"--decide {spec!r} is malformed: expected <stage>.<kind>=<answer>[:<note>]")
    stage, dot, kind = pair.rpartition(".")
    if not dot or not stage or not kind:
        raise ConfigError(f"--decide {spec!r} is malformed: {pair!r} is not <stage>.<kind>")
    if not _PAIR_RE.match(stage) or not _PAIR_RE.match(kind):
        raise ConfigError(f"--decide {spec!r} is malformed: {pair!r} is not a lowercase <stage>.<kind> pair")
    answer, _, note = value.partition(":")
    if not _ANSWER_RE.match(answer):
        raise ConfigError(f"--decide {spec!r} is malformed: {answer!r} is not an answer token")

    decision = Decision(stage=stage, kind=kind, answer=answer, note=note, source=source)
    _check_admissible(decision, admissible)
    return decision


def _decisions(raw: Mapping[str, object], *, admissible: Mapping[str, frozenset[str]] | None) -> dict[str, Decision]:
    barriers = _table(raw, "barriers", section="barriers")
    decisions: dict[str, Decision] = {}
    for stage, kinds in barriers.items():
        if not isinstance(kinds, dict):
            raise ConfigError(f"[barriers.{stage}] must be a table of <kind> tables")
        for kind, entry in kinds.items():
            section = f"barriers.{stage}.{kind}"
            if not isinstance(entry, dict):
                raise ConfigError(f"[{section}] must be a table")
            decision = Decision(
                stage=stage,
                kind=kind,
                answer=_str_field(entry, "decision", section=section),
                note=_str_field(entry, "note", section=section, default=""),
                source="config",
            )
            _check_admissible(decision, admissible)
            decisions[decision.pair] = decision
    return decisions


# --- load -------------------------------------------------------------------


def _read(path: Path) -> dict:
    """The config file's tables. Every failure to get at them is a ConfigError."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    except OSError as exc:
        raise ConfigError(f"config file unreadable: {path}: {exc}") from exc
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"config file is not valid TOML: {path}: {exc}") from exc


def run_dir_parent(parent: Path | str | None) -> str:
    """The run-directory parent a card must name, or empty where it need not.

    Read by the resume line rendered below. The default is what a bare
    invocation already finds, so naming it would put a flag on every card to
    say nothing; anything else is a directory the next invocation would
    otherwise not look in, and a resume that dropped it would file the resumed
    run's evidence under the default parent and strand the first run's.
    """
    if parent is None or str(parent) == DEFAULT_RUN_DIR:
        return ""
    return str(parent)


def invocation(
    path: Path | None,
    run_overrides: Mapping[str, object] | None = None,
    *,
    run_dir: Path | str | None = None,
) -> str:
    """The flags that reproduce this run, rendered from what it was given.

    Written out flag by flag rather than derived from the override keys: the
    two are spelled differently (``--source`` carries ``sources``), and a
    resume line is not the place for a mapping that could be wrong.

    **The run directory is rendered wherever it is not the default one**
    (:func:`run_dir_parent`). ``run_dir`` is the
    *effective* parent — the flag where one was given, the file's ``[log]
    run_dir`` otherwise — so a card built from this line hands back the
    directory this run's evidence is actually in. A resume line that dropped it
    would put the resumed run's evidence under the default parent and leave the
    first run's stranded, which is the one thing a resume must not do to a run's
    own account of itself.

    **The bound is not rendered, deliberately.** ``--through`` bounds one
    invocation rather than specifying the build, and this string is what every
    relay card's resume line is built from — so a card carrying it back would
    hand the operator an invocation that stops in the same place forever.
    Resuming past a bound is the point of resuming.

    **The mode flag is rendered, for the mirror-image reason.** It says what
    this build is made of, so a resume that dropped it would change the build
    half way through, running the very rows the build was told to do without.
    """
    overrides = run_overrides or {}
    parts: list[str] = []
    if path is not None:
        parts += [CONFIG_FLAG, str(path)]
    sources = overrides.get("sources") or ()
    parts += [part for source in sources for part in (SOURCE_FLAG, str(source))]
    mode = overrides.get("permission_mode")
    if mode is not None:
        parts += [PERMISSION_MODE_FLAG, str(mode)]
    named_parent = run_dir_parent(run_dir)
    if named_parent:
        parts += [RUN_DIR_FLAG, named_parent]
    if overrides.get("no_inference"):
        parts.append(NO_INFERENCE_FLAG)
    return shlex.join(parts)


def load(
    path: Path | None,
    *,
    run_overrides: Mapping[str, object] | None = None,
    admissible: Mapping[str, frozenset[str]] | None = None,
    run_dir: Path | None = None,
) -> DriverConfig:
    """Validate one run's specification. Any refusal is a ConfigError (exit 13).

    ``path`` is the config file, or ``None`` for a run the flags specify
    entirely. ``run_overrides`` are ``[run]`` keys from the command line, which
    win over the file's own for the keys they name.

    ``run_dir`` is ``--run-dir``, the one flag naming a ``[log]`` key rather
    than a ``[run]`` one, and it takes the same precedence for the same reason —
    one rule for both doors. Resolving it here rather than at the call site is
    what lets ``log.run_dir`` be the *effective* parent and the resume line
    render it: a flag the config never saw is a flag no card can hand back.

    ``admissible`` maps ``"<stage>.<kind>"`` to that barrier's admissible
    answers. Supply the registry to have decisions checked at load; omit it
    and only their form is checked.
    """
    overrides = dict(run_overrides or {})
    raw = _read(path) if path is not None else {}

    run_raw = _TrackedTable({**_table(raw, "run", section="run"), **overrides})
    runner = run_raw.get("runner")
    run = RunSection(
        sources=_str_list_field(run_raw, "sources", section="run", flag=SOURCE_FLAG),
        bibliography=_str_field(run_raw, "bibliography", section="run", default=""),
        permission_mode=_str_field(
            run_raw, "permission_mode", section="run", default=DEFAULT_PERMISSION_MODE, choices=PERMISSION_MODES
        ),
        charter_file=Path(_str_field(run_raw, "charter_file", section="run", default=kb_pipeline.CHARTER_RELPATH)),
        runner=None if runner is None else _str_field(run_raw, "runner", section="run", choices=RUNNERS),
        no_inference=_bool_field(run_raw, "no_inference", section="run", default=False),
        through=_stage_field(run_raw, "through", section="run", flag=THROUGH_FLAG),
    )
    _refuse_unknown_keys(run_raw, section="run")

    claude_raw = _TrackedTable(_table(raw, "claude", section="claude"))
    _reject_model_keys(claude_raw)
    claude = ClaudeSection(
        command=_str_list_field(claude_raw, "command", section="claude", default=DEFAULT_CLAUDE_COMMAND),
        env=_str_map(claude_raw, "env", section="claude"),
    )
    _refuse_unknown_keys(claude_raw, section="claude")

    timeouts_raw = _TrackedTable(_table(raw, "timeouts", section="timeouts"))
    timeouts = TimeoutSection(
        single_seconds=_int_field(timeouts_raw, "single_seconds", section="timeouts", default=DEFAULT_SINGLE_SECONDS),
        silence_seconds=_int_field(
            timeouts_raw, "silence_seconds", section="timeouts", default=DEFAULT_SILENCE_SECONDS
        ),
        by_step=_int_map(timeouts_raw, "by_step", section="timeouts", keys=tuple(steps.STEPS_BY_ID)),
    )
    _refuse_unknown_keys(timeouts_raw, section="timeouts")

    retry_raw = _TrackedTable(_table(raw, "retry", section="retry"))
    retry = RetrySection(
        transport_attempts=_int_field(
            retry_raw, "transport_attempts", section="retry", default=DEFAULT_TRANSPORT_ATTEMPTS
        ),
        backoff_seconds=_int_list_field(retry_raw, "backoff_seconds", section="retry", default=DEFAULT_BACKOFF_SECONDS),
    )
    _refuse_unknown_keys(retry_raw, section="retry")

    log_raw = _TrackedTable(_table(raw, "log", section="log"))
    configured_run_dir = _str_field(log_raw, "run_dir", section="log", default="")
    log = LogSection(
        level=_str_field(log_raw, "level", section="log", default=DEFAULT_LOG_LEVEL, choices=LOG_LEVELS),
        run_dir=run_dir if run_dir is not None else Path(configured_run_dir or DEFAULT_RUN_DIR),
    )
    _refuse_unknown_keys(log_raw, section="log")

    return DriverConfig(
        path=path,
        invocation=invocation(path, overrides, run_dir=log.run_dir),
        run=run,
        claude=claude,
        timeouts=timeouts,
        retry=retry,
        log=log,
        decisions=_decisions(raw, admissible=admissible),
    )
