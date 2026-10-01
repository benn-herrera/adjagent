"""Ask a seat to do a thing, and get back what it said.

A **seat** is one of this agent set's definitions — ``kb-maintainer``,
``architect``, ``prompt-engineer`` — named by the stem of the ``.md`` file that
declares it. That is the whole of what this layer knows, and it is the whole of
the difference between it and :mod:`.claude` below it. It knows nothing about
claims, trees, registers or any other KB vocabulary; anything a seat is asked
about travels in ``prompt``, composed by whoever is asking.

**This function is the seam, not an abstraction over one.** A sibling that
dispatched to a differently-shaped harness would be a second function beside
this one, taking that harness's own arguments; the Claude-specific adaptation
of a seat — that a seat name is spelled as ``--agent <name>`` — stays inside
here rather than in a translation table nobody has two consumers for yet.

**It interprets nothing that comes back.** The response text is returned as it
arrived: envelope extraction, verdict parsing, JSON decoding and every other
reading of it belong to the caller that knows what it asked for.

**Two ways to seat a call.** :func:`ask_seat` invokes the seat as an agent
(``--agent <name>``), with whatever tools its definition grants — the shape for
a seat doing work. :func:`ask_reader` puts a question to a seat that is to
answer from the prompt alone: the definition's body becomes the system prompt,
replacing the CLI's default, with the caller's addendum after it, and every
built-in tool is disabled, no MCP server is loaded, and no memory is read. It
passes no ``--agent``, so no definition granting tools
reaches a model that cannot use them. The body is the definition with
its frontmatter dropped, which root SPEC.md's Guest-Extraction Contract
guarantees is the body entire.

**No ``--model`` of this layer's choosing, and not by discipline.** A seat's
model pin lives in its own frontmatter. Under ``--agent`` the CLI reads it, and
an explicit ``--model`` would override it, so none is passed. Without
``--agent`` nothing reads it but this module, so :func:`ask_reader` passes the
pin as ``--model`` — the same value, by the only route left. There is no
parameter here through which a caller could name a model, this layer spelling
no command at all.

Stdlib only.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from .. import install_location
from . import claude
from .claude import Outcome

_log = logging.getLogger(__name__)


def seat_directory() -> Path:
    """Where a project's seat definitions sit, relative to the directory the call runs in.

    The installed harness's ``agents/`` — the directory this toolchain is
    installed in. A seat may also be defined for the user rather than the
    project, under the same relative path below ``~``.
    """
    return Path(install_location.current().agents_relpath)


def _check_seat_name(seat: str) -> None:
    """A seat is named, never pathed. The definition's stem is the name.

    Catches the three spellings that reach the CLI as an unknown agent and come
    back as an opaque rejection: a path, a filename, and a flag.
    """
    complaint = ""
    if not seat.strip():
        complaint = "a seat name is empty"
    elif seat.endswith(".md") or "/" in seat:
        complaint = f"a seat is named by its definition's stem, not by its path: {seat!r}"
    elif seat.startswith("-"):
        complaint = f"a seat name cannot open with a dash: {seat!r}"
    if complaint:
        _refuse(complaint)


def _definition_path(seat: str, *, cwd: Path) -> Path | None:
    """The seat's definition file: the project's first, then the user's."""
    return next(
        (path for base in (cwd, Path.home()) if (path := base / seat_directory() / f"{seat}.md").is_file()),
        None,
    )


def _warn_if_undefined(seat: str, *, cwd: Path) -> None:
    """Non-gating: say so when no definition for this seat is where one would be.

    A seat may legitimately be defined somewhere this cannot see, so an absence
    is a warning and never a refusal — but it is by far the likeliest cause of
    a call the CLI rejects, and the rejection says nothing about which name was
    wrong.
    """
    if _definition_path(seat, cwd=cwd) is not None:
        return
    _log.warning("no definition for seat %r under %s in %s or the home directory", seat, seat_directory(), cwd)


#: The frontmatter's ``model:`` line, quoted or bare — the spelling
#: ``gen_defs.rendering``'s ``FRONTMATTER_PIN`` reads a rendered pin by. Stated
#: independently because the generator does not ship with this package.
_MODEL_PIN = re.compile(r"""^model:[ \t]*["']?([^"'\s#]+)["']?[ \t]*$""", re.MULTILINE)


#: Layered over the settings the CLI reads, so a reader call loads no memory —
#: no CLAUDE.md file, user, project or local, and no auto-memory — which would
#: put the operator's or the repository's instructions beside the definition.
#: Unlike ``--bare`` it leaves keychain authentication alone.
READER_SETTINGS = json.dumps({"claudeMdExcludes": ["**/CLAUDE.md", "**/CLAUDE.local.md"], "autoMemoryEnabled": False})


@dataclass(frozen=True)
class _Definition:
    """What a reader call takes from a seat's definition: its body and its pin."""

    body: str
    model: str | None


def _refuse(complaint: str) -> NoReturn:
    _log.error("seat ask refused: %s", complaint)
    raise ValueError(complaint)


def _read_definition(seat: str, *, cwd: Path) -> _Definition:
    """The definition split as the Guest-Extraction Contract states it.

    Every line through the one closing the frontmatter block is dropped, and
    what remains is the body entire. The file is read from wherever the seat is
    installed, which this toolchain did not write, so a definition carrying no
    frontmatter or no body is refused by name rather than sent as an empty or
    truncated system prompt.
    """
    path = _definition_path(seat, cwd=cwd)
    if path is None:
        _refuse(f"no definition for seat {seat!r} under {seat_directory()} in {cwd} or the home directory")
    lines = path.read_text(encoding="utf-8").split("\n")
    closing = next((number for number in range(1, len(lines)) if lines[number] == "---"), None)
    if lines[0] != "---" or closing is None:
        _refuse(f"{path} opens with no frontmatter block, so it is not a seat definition")
    body = "\n".join(lines[closing + 1 :]).strip()
    if not body:
        _refuse(f"{path} has no body to serve as a system prompt")
    pin = _MODEL_PIN.search("\n".join(lines[1:closing]))
    return _Definition(body=body, model=pin.group(1) if pin else None)


def ask_seat(
    *,
    seat: str,
    prompt: str,
    cwd: Path | None = None,
    silence_seconds: float = claude.DEFAULT_SILENCE_SECONDS,
    total_seconds: float = claude.DEFAULT_TOTAL_SECONDS,
    capture_path: Path | None = None,
    invoker: claude.Invoker | None = None,
) -> tuple[str, Outcome]:
    """Pose ``prompt`` to ``seat`` and return what it said and how the call ended.

    Synchronous, and **not a single completion**: a seat's own definition may
    have it dispatch further, so this returns when the call stops speaking or a
    bound expires. Budget against ``total_seconds``.

    ``cwd`` defaults to the process's working directory and decides which
    project's :func:`seat_directory` the seat resolves against. ``invoker``
    replaces the subprocess seam, which is how a caller tests this against no
    model at all.

    Raises :class:`ValueError` for an unusable seat name or prompt; every way a
    call can end, a command that could not be spawned included, is a returned
    :class:`~.claude.Outcome`.
    """
    _check_seat_name(seat)
    directory = Path.cwd() if cwd is None else cwd
    _warn_if_undefined(seat, cwd=directory)
    _log.info("asking seat %s in %s", seat, directory)

    return claude.call_claude(
        prompt=prompt,
        cwd=directory,
        agent=seat,
        silence_seconds=silence_seconds,
        total_seconds=total_seconds,
        capture_path=capture_path,
        invoker=invoker,
    )


def ask_reader(
    *,
    seat: str,
    prompt: str,
    system_addendum: str,
    cwd: Path | None = None,
    bare: bool = False,
    silence_seconds: float = claude.DEFAULT_SILENCE_SECONDS,
    total_seconds: float = claude.DEFAULT_TOTAL_SECONDS,
    capture_path: Path | None = None,
    invoker: claude.Invoker | None = None,
) -> tuple[str, Outcome]:
    """Pose ``prompt`` to ``seat`` with no tools, and return what it said and how the call ended.

    The system prompt is the seat definition's body, a blank line, and
    ``system_addendum`` — the caller's statement to the seat about the call it
    is in. Every built-in tool is disabled, no MCP server is loaded, no
    memory is read (:data:`READER_SETTINGS`) and no ``--agent`` is passed;
    the definition's model pin, where it has one, is passed as ``--model``.

    ``bare`` is the CLI's minimal mode, off unless asked for: it skips
    CLAUDE.md auto-discovery and hooks, and it never reads the keychain, so a
    call authenticated by a login held there fails under it.

    Raises :class:`ValueError` for an unusable seat name or prompt, and for a
    seat whose definition cannot be found or carries no body; every way a call
    can end is a returned :class:`~.claude.Outcome`.
    """
    _check_seat_name(seat)
    if not system_addendum.strip():
        _refuse("the system addendum is empty")
    directory = Path.cwd() if cwd is None else cwd
    definition = _read_definition(seat, cwd=directory)
    _log.info("asking seat %s as a reader in %s", seat, directory)

    return claude.call_claude(
        prompt=prompt,
        cwd=directory,
        model=definition.model,
        system_prompt=f"{definition.body}\n\n{system_addendum.strip()}",
        no_tools=True,
        strict_mcp_config=True,
        settings=READER_SETTINGS,
        bare=bare,
        silence_seconds=silence_seconds,
        total_seconds=total_seconds,
        capture_path=capture_path,
        invoker=invoker,
    )
