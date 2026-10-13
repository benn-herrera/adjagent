"""kb-build: the command that launches a KB build in the background and relays it to the user.

Its first body line is what the harness lists the command by, so it reads as the description.
"""

from adjagent.definition import Definition
from adjagent.vocabulary import Kind

DEFINITIONS = (
    Definition(
        name="kb-build",
        kind=Kind.COMMAND,
        body="""Launch a KB build over the named LaTeX sources in the background, and relay its progress and its
stops to the user until it ends.

## Arguments

```
/kb-build <source>[,source...]
```

The first token is the LaTeX source root, or a comma-separated list of volume paths, each spelled
relative to the repository root and passed in the order given. Nothing else is an argument: the KB
root is always `kb-root/`, a name the tools hard-code and take no override for. Anything the user
typed after the source list is not an input — not a further source, and nothing this command
carries into the build; say so rather than folding it into the launch.

## Launch

From the repository root, through its runner — `just` if a justfile is there, else `make` if a
Makefile is; with neither, say so and stop:

```
just kb-build <source> [<source> ...]
make kb-build SOURCES="<source> [<source> ...]"
```

Relay the `launched pid` line to the user. A launch refused because a build is already running is
reported and ends the command; `kb-build-kill` runs only on the user's word.

## Await

Run `kb-build-await` through the same runner so that it does not hold your turn, and take up its
output when it arrives. Its `await-build:` line is the answer, whatever the exit code:

- `changed` — tell the user the `[kb-build] status:` line beneath it in one sentence; await again.
- `exited` — the relay card beneath it governs. Place what it says to place in your message body,
  verbatim. An ASK that is a question goes to the user, with any admissible answers, and your
  turn ends there; an ASK reading `none — …` is an instruction: do what follows the dash. Run
  the THEN RUN command, with the user's answer substituted where the card says so, only once
  nothing the card puts ahead of it is outstanding — an answer it asks for, a fix it says must
  come first. Running it is a launch: relay, then await as above.
- `nothing-to-await` — tell the user no build is running.

The await output is the only view of the build you relay. Never run the driver in the foreground,
read or tail its console log, restate the stages or exit codes the cards carry, or launch a second
build while one runs.""",
    ),
)
