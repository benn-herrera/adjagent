"""ML technique work: what a technique proposal delivers, and the attacks it must survive."""

from dataclasses import dataclass

from adjagent.context import Render
from adjagent.section import OwnText, Part, Section

_TECHNIQUE_ATTACKS = r"""mechanism descriptions that are too vague to implement, justifications that smuggle the conclusion as a premise, predictions that cannot be measured or that would be true regardless of whether the mechanism worked, baselines that are not actually comparable, missing failure-mode analysis (especially silent ones), cost accounting that ignores ongoing maintenance or omits a cheaper alternative, hidden assumptions about model size / architecture / regime that the problem does not specify, and citations to prior work whose conditions do not transfer to the current problem."""

_TECHNIQUE_ELEMENTS = r"""- **Mechanism** — the specific technique or modification, described precisely enough to implement: what computation changes, where in the pipeline it sits, what new state or weights it introduces, what it replaces
- **Justification** — why this mechanism should produce the desired behavior. Ground in known model dynamics (residual stream behavior, attention patterns, gradient flow, distribution shift, etc.), prior empirical results from analogous regimes, or first-principles reasoning. If the justification is "it worked in paper X," explain why the conditions of paper X transfer to the current problem
- **Predicted observable behavior** — what should be measurable if the mechanism is working as hypothesized. Concrete predictions ("logprob agreement within 0.01 on held-out prompts," "attention entropy drops by ≥30% in layers > N," "perplexity matches baseline within 5%") are stronger than vague ones ("output quality should improve")
- **Measurement plan** — how the predicted behavior will be tested. Identify the dataset/prompt set, the metric, the baseline to compare against, and the threshold that would falsify the hypothesis. If the measurement requires infrastructure that does not yet exist, name it
- **Failure modes** — what specifically would go wrong if the mechanism is incorrect, and whether each failure mode would be silent (model produces wrong-but-plausible output) or loud (NaN, exception, obvious garbage). Identify every silent failure mode explicitly — these are the highest-cost category to debug
- **Cost accounting** — compute (FLOPs, wall time), memory (VRAM, RAM, persistent storage), and complexity (lines changed, new abstractions introduced, ongoing maintenance burden). Compare to the cheapest baseline that achieves a comparable result and explain why the additional cost is justified"""


@dataclass(frozen=True, kw_only=True)
class TechniqueDeliverable(Section):
    """The three indivisible elements of a technique deliverable, and its minimum contents.

    Heading-less: each consumer places it inside a section of its own. The lead sentences name the
    deliverable and the bullets deliberately do not.
    """

    unit: str
    """The deliverable: `Each <unit> must produce three indivisible elements`."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        lead = (
            f"**Each {self.unit} must produce three indivisible elements: a *mechanism* (how the technique works), a "
            "*justification* (why it should work, grounded in model or system behavior), and a *measurement* (how we "
            "will know whether it does).**"
        )
        return (
            ("unit", lead),
            ("unit", f"The {self.unit} must include, at minimum:"),
            ("", _TECHNIQUE_ELEMENTS),
        )


@dataclass(frozen=True, kw_only=True)
class TechniqueAttacks(Section):
    """The attacks a technique deliverable must survive, as one sentence the consumer opens."""

    lead: str | None = OwnText.lead
    """The words opening the sentence, its verb included; the attacks are a bare noun-phrase list."""

    tail: str | None = OwnText.tail
    """The consumer's text continuing the paragraph."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        text = _TECHNIQUE_ATTACKS
        if self.lead is not None:
            text = f"{self.lead} {text}"
        if self.tail is not None:
            text = f"{text} {self.tail}"
        return (("lead, tail", text),)
