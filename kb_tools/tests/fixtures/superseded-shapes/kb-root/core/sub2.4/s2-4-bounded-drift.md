[↑ §2.4 Bounded Drift](index.md)

<!-- kb-frontmatter
kind: leaf
claims: [clm-drf024, clm-drf025]
-->

# §2.4 Bounded Drift and Its Rate

[§1](../s1-scope.md) fixes what the ledger records. We now bound its drift.

<!-- claim-quality: clm-drf024 -->
**Proposition 2.4 (Bounded Drift).** For every admissible schedule the drift $d_n$ satisfies
$|d_n| \le D$.

<!-- claim-quality: clm-drf025 -->
Inside the band the drift decays geometrically: $|d_{n+1}| \le (1-r)|d_n|$.
