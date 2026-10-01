"""gen_defs — the exit-2 error."""


class InputError(Exception):
    """The run cannot proceed at all: an invocation or an input it reads is
    unusable. The CLI reports it and exits 2 — the absence of a verdict, never
    a verdict about the tree."""
