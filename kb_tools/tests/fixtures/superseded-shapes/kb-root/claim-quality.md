# Drift Ledger KB — Claim Quality Register

Confidence and solidity are scored per entry. The core text registers its claims here, at the KB
root; clm-drf024 is the result every volume leans on.

## Build-status legend

| Solidity | Build status |
|---|---|
| 0.85 | ok to build on |
| 0.65 | ok to build on, see caveats |
| 0.45 | use as input only, don't build deeper |
| 0.20 | do not build on, rework needed |
| 0.00 | refuted, do not use |

---

## Proposition 2.4 — Bounded Drift
<!-- id: clm-drf024 -->

> **Leaf references:** [s2-4-bounded-drift](./core/sub2.4/s2-4-bounded-drift.md).

### Quality
- confidence: 0.90
- solidity: 0.90 (ok to build on)
- rationale: The band follows from a two-line contraction argument; every step is justified.
- strengthen-by:
  - None — the bound is locally complete; no open work item at the claim level.

---

## Corollary 2.5 — Drift Rate
<!-- id: clm-drf025 -->

> **Leaf references:** [s2-4-bounded-drift](./core/sub2.4/s2-4-bounded-drift.md).

### Quality
- confidence: 0.70
- depends-on:
  - clm-drf024 — Proposition 2.4, Bounded Drift (solidity 0.90) ["the rate is read off the band of Proposition 2.4"]
- solidity: 0.70 (ok to build on, see caveats) [= min(0.70, 0.90)]
- rationale: The rate is exact inside the band, but the constant is quoted rather than derived.
- strengthen-by:
  - Derive the rate constant rather than quoting it; shares the band argument of clm-drf024.
