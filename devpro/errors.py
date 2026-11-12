"""The one error the package raises."""


class InputError(Exception):
    """A refusal the CLI reports as `error: <message>` and exit status 2."""
