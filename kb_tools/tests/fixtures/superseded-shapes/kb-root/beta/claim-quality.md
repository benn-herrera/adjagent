# Volume Beta — Claim Quality Register

Beta registers one claim, clm-bet021.

---

## Theorem: Settlement Closure (Beta §2)
<!-- id: clm-bet021 -->

> **Leaf references:** [b2-closure](./b2-closure.md).

### Quality
- confidence: 0.60
- depends-on:
  - clm-alp011 — Ledger Monotonicity (solidity 0.80) ["once the ledger is monotone"]
  - clm-drf025 — Drift Rate (solidity 0.70) ["its drift decays"]
- solidity: 0.60 (use as input only, don't build deeper) [= min(0.60, 0.70)]
- rationale: The closure step is asserted from the two premises with no bound on the round count.
- strengthen-by:
  - Bound the number of rounds to closure using the rate of clm-drf025.
