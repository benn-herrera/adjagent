"""Replay a finished build's recorded claim-graph asks against another model.

Invoked through `just replay-claimgraph-asks` (kb-testing/justfile), with
PYTHONPATH at the fixture's own installed agents directory: the seat, the
no-tools fragment and the asks directory are read from the toolchain copy the
build ran, not from this repository's working tree.

Each ask the build recorded under ``<fixture>/<ASKS_RELPATH>`` as
``NNN-<name>.prompt.md`` is put once to the model ``--env-file`` names, through liaison_tools: a
messages file made by ``msg-util.py init`` (system prompt, then the recorded
prompt verbatim as the user turn) and one ``post-openai.py`` call. The system
prompt is what ``inference.ask_reader`` composes for the build — the seat
definition's body, a blank line, the rendered ``no-tools`` fragment. The asks
record no seat; the build constructed both consumers without one, so the seat
is the toolchain's default, ``kb_claimgraph.ask.SEAT``.

Connection parameters, the model included, come from a liaison env file
(``--env-file``), parsed by relay-driver.py's own allowlisting loader; the
sampling settings are replaced by :data:`CALL_SETTINGS`.

Writes, under ``.claude-temp/ask-replay/<model>/`` at the repository root:
  system-prompt.md         the system prompt every replayed ask was sent
  NNN-<name>.capture.jsonl one JSON line per ask: the reply text and how the call ended
  messages/                the messages files post-openai.py was handed

Resumable: an ask whose capture records a completed call (post-openai.py exit
0, 3 or 4) is skipped; a timed-out or failed one is reissued on the next run.
Writes nothing else, and nothing into the fixture.
"""

import argparse
import importlib.util
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import liaison_tools
from kb_tools.inference import claude, seat
from kb_tools.kb_claimgraph import ask
from kb_tools.kb_claimgraph.__main__ import ASKS_RELPATH
from kb_tools.kb_driver import prompt_templates

OUT = Path(__file__).resolve().parents[2] / ".claude-temp" / "ask-replay"
LIAISON = Path(liaison_tools.__file__).resolve().parent
POST_OPENAI = LIAISON / "post-openai.py"
MSG_UTIL = LIAISON / "msg-util.py"

#: The build's call conditions as far as an OpenAI-compatible request can state
#: them: thinking on, temperature 1 (what an Anthropic-route call with thinking
#: runs at) and the CLI's 32000-token output cap the build's captures report.
CALL_SETTINGS = {"ENABLE_THINKING": "true", "TEMPERATURE": "1.0", "MAX_TOKENS": "32000"}

#: post-openai.py exits naming a call that completed — a reply, a truncated one
#: or an empty one. Reissuing any of them identically would not help.
COMPLETED_EXITS = frozenset({0, 3, 4})

PROMPT_SUFFIX = ".prompt.md"
CAPTURE_SUFFIX = ".capture.jsonl"

_log = logging.getLogger("replay-claimgraph-asks")


def load_relay_driver():
    """relay-driver.py, loaded by path: its name is not a legal module name."""
    spec = importlib.util.spec_from_file_location("relay_driver", LIAISON / "relay-driver.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def system_prompt(fixture: Path) -> str:
    """The system prompt ``ask_without_tools`` hands ``ask_reader`` for the build's seat, as ``ask_reader`` joins it."""
    definition = seat._read_definition(ask.SEAT, cwd=fixture)
    addendum = prompt_templates.render(prompt_templates.FRAGMENTS[ask.NO_TOOLS], slots={})
    return f"{definition.body}\n\n{addendum.strip()}"


def completed(capture: Path) -> bool:
    if not capture.is_file():
        return False
    try:
        record = json.loads(capture.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return record.get("exit") in COMPLETED_EXITS


def replay_one(
    *, prompt: Path, model_dir: Path, system_file: Path, env: dict[str, str], timeout: float
) -> dict[str, object]:
    stem = prompt.name[: -len(PROMPT_SUFFIX)]
    messages = model_dir / "messages" / f"{stem}.messages.json"
    subprocess.run(
        [
            sys.executable,
            str(MSG_UTIL),
            "init",
            f"--system-prompt={system_file}",
            f"--instructions={prompt}",
            str(messages),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    with tempfile.TemporaryDirectory(dir=model_dir) as scratch:
        usage_file = Path(scratch) / "usage.jsonl"
        started = time.monotonic()
        try:
            run = subprocess.run(
                [sys.executable, str(POST_OPENAI), str(messages)],
                env={**env, "USAGE_STATS_FILE": str(usage_file)},
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout,
            )
            exit_code: int | str = run.returncode
            text, stderr = run.stdout, run.stderr
        except subprocess.TimeoutExpired as expired:
            exit_code = "timeout"
            # Bytes whatever text= says, where anything was captured at all.
            partial = expired.stderr or b""
            text, stderr = "", partial.decode("utf-8", errors="replace") if isinstance(partial, bytes) else partial
        duration_ms = round((time.monotonic() - started) * 1000)
        usage_lines = usage_file.read_text(encoding="utf-8").splitlines() if usage_file.is_file() else []
    usage = json.loads(usage_lines[-1]) if usage_lines else {}
    record = {
        "type": "replay",
        "ask": stem,
        "model": env["MODEL"],
        "served_model": usage.get("model"),
        "exit": exit_code,
        "duration_ms": duration_ms,
        "usage": {key: usage.get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
        "settings": {key: env[key] for key in CALL_SETTINGS},
        # post-openai.py ends its stdout with one newline of its own.
        "text": text[:-1] if text.endswith("\n") else text,
        "stderr": stderr,
    }
    capture = model_dir / f"{stem}{CAPTURE_SUFFIX}"
    staged = capture.with_suffix(".partial")
    staged.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(staged, capture)
    return record


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--fixture", type=Path, required=True, help="repository root the build ran in")
    parser.add_argument(
        "--env-file", type=Path, required=True, help="liaison connection env file; its MODEL is replayed"
    )
    parser.add_argument("--concurrency", type=int, default=4, help="asks in flight at once (default 4)")
    parser.add_argument(
        "--timeout",
        type=float,
        default=claude.DEFAULT_TOTAL_SECONDS,
        help="per-ask bound in seconds (default: the build's)",
    )
    parser.add_argument("--ask", action="append", default=[], help="replay only this ask stem (repeatable)")
    arguments = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", stream=sys.stderr)

    fixture = arguments.fixture.resolve()
    asks_dir = fixture / ASKS_RELPATH
    prompts = sorted(asks_dir.glob(f"*{PROMPT_SUFFIX}"))
    if arguments.ask:
        wanted = set(arguments.ask)
        prompts = [p for p in prompts if p.name[: -len(PROMPT_SUFFIX)] in wanted]
        missing = wanted - {p.name[: -len(PROMPT_SUFFIX)] for p in prompts}
        if missing:
            parser.error(f"no recorded ask named {', '.join(sorted(missing))} under {asks_dir}")
    if not prompts:
        parser.error(f"no recorded asks under {asks_dir}")

    connection = load_relay_driver().load_connection_env(arguments.env_file)
    model = connection.get("MODEL", "")
    if not model or "/" in model:
        parser.error(f"{arguments.env_file} names no usable MODEL")
    overridden = sorted(key for key in CALL_SETTINGS if key in connection and connection[key] != CALL_SETTINGS[key])
    if overridden:
        _log.warning("env file's %s replaced by the build's call settings", ", ".join(overridden))
    env = {**os.environ, **connection, **CALL_SETTINGS}

    model_dir = OUT / model
    (model_dir / "messages").mkdir(parents=True, exist_ok=True)
    system_file = model_dir / "system-prompt.md"
    system_file.write_text(system_prompt(fixture), encoding="utf-8")

    pending = [p for p in prompts if not completed(model_dir / f"{p.name[: -len(PROMPT_SUFFIX)]}{CAPTURE_SUFFIX}")]
    _log.info(
        "seat %s; model %s; %d asks, %d already captured, %d to replay at concurrency %d -> %s",
        ask.SEAT,
        model,
        len(prompts),
        len(prompts) - len(pending),
        len(pending),
        arguments.concurrency,
        model_dir,
    )
    failures = 0
    with ThreadPoolExecutor(max_workers=arguments.concurrency) as pool:
        futures = {
            pool.submit(
                replay_one, prompt=p, model_dir=model_dir, system_file=system_file, env=env, timeout=arguments.timeout
            ): p
            for p in pending
        }
        for done, future in enumerate(as_completed(futures), start=1):
            record = future.result()
            if record["exit"] not in COMPLETED_EXITS:
                failures += 1
            if record["served_model"] not in (None, model):
                _log.warning("%s: served by %s, not %s", record["ask"], record["served_model"], model)
            _log.info(
                "[%d/%d] %s exit=%s %.1fs completion_tokens=%s",
                done,
                len(pending),
                record["ask"],
                record["exit"],
                record["duration_ms"] / 1000,
                record["usage"]["completion_tokens"],
            )
    _log.info("done: %d replayed, %d not completed (reissued on the next run)", len(pending), failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
