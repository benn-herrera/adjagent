"""One report line, in the toolchain's uniform ``[tag] STATUS name detail`` shape.

``FACT`` describes state and never gates; ``FAIL`` is the whole verdict. Shared
by every stage so a run's output reads as one report rather than seven.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from .. import kb_util

TAG = "claimgraph"

# The three status tokens, imported rather than re-spelled, so they mean the
# same thing here as in every other report the toolchain emits.
PASS = kb_util.PASS
FAIL = kb_util.FAIL
FACT = kb_util.FACT


@dataclass(frozen=True)
class Finding:
    """One report line."""

    status: str
    check: str
    detail: str

    def line(self) -> str:
        return f"[{TAG}] {self.status} {self.check} {self.detail}"


def gating(findings: Sequence[Finding]) -> bool:
    return any(finding.status == FAIL for finding in findings)


@dataclass
class Report:
    """What one run produced and what the gates said about it.

    Shared by both passes, because a run's output has to read as one report
    whichever pass produced it — the verdict is the same comparison over the
    same findings, and a second Report class would be a second answer to
    "did this run fail".
    """

    findings: list[Finding] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return gating(self.findings)

    def lines(self) -> list[str]:
        return [finding.line() for finding in self.findings]


class ClaimGraphError(Exception):
    """A stage stopped. Carries the check it stopped in and why.

    Every stage in this package terminates on a comparison between two
    artifacts, so a stop is always attributable to a named check rather than to
    an opinion. :func:`finding` is how a stop becomes the report line the run
    exits on.
    """

    def __init__(self, check: str, detail: str) -> None:
        super().__init__(detail)
        self.check = check
        self.detail = detail

    def finding(self) -> Finding:
        return Finding(FAIL, self.check, self.detail)
