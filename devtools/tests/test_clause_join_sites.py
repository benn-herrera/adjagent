from types import SimpleNamespace

import pytest

from devtools.clause_join_sites import join_sites

_CLAUSES = SimpleNamespace(
    A="Clause a.",
    B="Clause b.",
    TEMP_DIR="@!hrn-temp-dir!@",
    framed=lambda *, frame: f"Lead. {frame} Tells.",
)
_NAMESPACE = {"clauses": _CLAUSES, "_FRAME": "Own frame."}


def _sites(body: str) -> list[str]:
    source = f'DEFINITIONS = (Definition(\n    body=f"""{body}"""),)\n'
    return join_sites(source, namespace=dict(_NAMESPACE), path="d.py")


@pytest.mark.parametrize(
    "body, expected",
    [
        ("{clauses.A} Own text.", ["d.py:2: clauses.A"]),
        ("Own text.\n\n{clauses.A}\n\nMore own text.", []),
        ("Write to {clauses.TEMP_DIR} only.", []),
        ("- {clauses.A} Own text.\n- Own item.", ["d.py:2: clauses.A"]),
        ("- {clauses.A}\n- Own item.", []),
        ("Own lead.\n{clauses.B} {clauses.A}", ["d.py:3: clauses.B + clauses.A"]),
        ('{clauses.framed(frame="Literal frame.")}', []),
        ("{clauses.framed(frame=_FRAME)}", ["d.py:2: clauses.framed"]),
    ],
    ids=[
        "clause-joined-to-module-text",
        "clause-alone-in-its-paragraph",
        "harness-string-is-module-text",
        "list-item-joins-clause-and-module-text",
        "list-item-holding-only-a-clause",
        "two-clauses-in-source-order",
        "literal-argument-is-clause-text",
        "module-constant-argument-is-module-text",
    ],
)
def test_join_sites(body: str, expected: list[str]) -> None:
    assert _sites(body) == expected
