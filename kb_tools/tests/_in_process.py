"""A module's ``main(argv)`` run in this process and reported the way a subprocess run of it would be.

For tests whose subject is what a command does, not that it runs as a process
of its own: interpreter start and imports are most of what a ``python -m``
spawn costs here. A test whose subject *is* the process boundary — import-time
behaviour, root discovery from a child's cwd, an exit status out of a real
process — keeps its subprocess.

Two things a subprocess would show do not reach the result: text a module
sends through ``logging`` (pytest's log capture holds it), and anything written
to a stream bound before the redirect — a default argument holding
``sys.stderr``, or a child process given the inherited descriptors.
"""

import contextlib
import io
import subprocess
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path


def run_main(
    main: Callable[[list[str]], int], argv: Sequence[str], *, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """``main(argv)`` with stdout and stderr captured, from ``cwd`` when given.

    A ``SystemExit`` — argparse's usage error, ``--help`` — is the exit status
    it carries, as the interpreter would make it: ``None`` is 0, and a message
    is written to stderr and exits 1. An uncaught exception is what it is to a
    process: its traceback on stderr, and exit 1.
    """
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.ExitStack() as stack:
        if cwd is not None:
            stack.enter_context(contextlib.chdir(cwd))
        stack.enter_context(contextlib.redirect_stdout(stdout))
        stack.enter_context(contextlib.redirect_stderr(stderr))
        try:
            code = main(list(argv))
        except SystemExit as exc:
            if exc.code is None:
                code = 0
            elif isinstance(exc.code, int):
                code = exc.code
            else:
                print(exc.code, file=stderr)
                code = 1
        except Exception:
            traceback.print_exc(file=stderr)
            code = 1
    return subprocess.CompletedProcess(
        args=list(argv), returncode=code, stdout=stdout.getvalue(), stderr=stderr.getvalue()
    )
