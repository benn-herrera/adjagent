<!-- kb-frontmatter
kind: entry-point
subtree-claims: [clm-alp011, clm-bet021, clm-drf024, clm-drf025]
subtree-experiments: []
-->

# Drift Ledger Knowledge Base

A synthetic KB in the superseded metadata format.

---

## Key Results

**Bounded drift (Proposition 2.4).** The ledger's drift stays inside a fixed band for every
admissible schedule.

**Settlement closure (Beta §2).** Every settlement round closes once the ledger is monotone.

---

## Domains

- [Core Text](core/index.md) — the bounded-drift results (clm-drf024, clm-drf025), registered at the
  KB root
- [Volume Alpha: Drift of $\phi(t)$](alpha/index.md) — ledger monotonicity (clm-alp011)
- [Volume Beta](beta/index.md) — settlement closure (clm-bet021); cites downward to Alpha and the core
- [Volume Gamma](gamma/index.md) — an appendix that states no result
