---
kind: leaf
claims: [clm-sb5555]
support-nodes:
  - sup-id: sup-coh001
    supports:
      - clm-sb5555: 1.0
---
[↑ Mini-KB Common](index.md)


## Co-Hosted Claim And Its Analytical Support

A single container that originates BOTH a claim node (clm-sb5555, via `claims:`)
AND a support node (sup-coh001, via `sup-id:` + `supports:`) — orthogonal
node-bodies in one container (INVARIANT-S10), exactly as a leaf may co-host a
`claims:` and an `exp-id:`. The support strengthens this leaf's own co-located
claim's DERIVATION branch (a node→node supports edge between two distinct
node-bodies, not a self-loop). `kind` stays `leaf`.
