# Volume Alpha — Claim Quality Register

Alpha registers one claim, clm-alp011, which rests on the core text's band.

---

## Lemma: Ledger Monotonicity (Alpha §1)
<!-- id: clm-alp011 -->

> **Leaf references:** [a1-monotonicity](./a1-monotonicity.md).

### Quality
- confidence: 0.80
- depends-on:
  - clm-drf024 — Proposition 2.4, Bounded Drift (solidity 0.90) [monotonicity needs the drift kept inside the band]
- solidity: 0.80 (ok to build on, see caveats) [= min(0.80, 0.90)]
- rationale: Short and complete given the band; the settled-round premise is stated, not derived.
- strengthen-by:
  - Derive the settled-round premise from the schedule rules.
