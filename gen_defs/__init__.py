"""
Generator for the generated definitions in this repository — agent definitions
and slash-command definitions alike.

Templates live in two sibling trees under templates/, and a template's surface
tree routes its output into the matching deployed surface beneath the output
root the invocation names (ROOT, `cli` module docstring; `generate` and
`install` each take it as their positional argument, and neither defaults —
this repository keeps no rendered tree of its own for a render to default
into):

    templates/agents/<name>.tmpl.md    + templates/shared-chunks.toml -> ROOT/agents/<name>.md
    templates/commands/<name>.tmpl.md  + templates/shared-chunks.toml -> ROOT/commands/<name>.md

Discovery is RECURSIVE within each surface tree, and a template's path is
MIRRORED into its surface — the relative subpath of the template is the
relative subpath of its output. The filesystem is the whole declaration;
there is no metadata key for placement:

    templates/agents/mad/participant-contract.tmpl.md -> ROOT/agents/mad/participant-contract.md

Every other mechanism — chunks, variants, markers, overlay anchors,
multi-output fences, banners, write safety, and numbered backups — applies
unchanged at a nested path. The surface directories under ROOT, and the
mirrored subdirectories beneath them, are created as needed.

templates/shared-chunks.toml is the single chunk source for both template
types. A template holds everything unique to its definition; every span of
text shared with other definitions is a marker referencing a chunk, so shared
text lives in exactly one place. templates/commands/ may be absent or empty
(git does not track an empty directory); that is not an error so long as at
least one template exists somewhere.

Enrollment is template existence, and nothing else. There is no enrollment
list and no exclusion list: the tool generates every definition its templates
declare and touches no other file. Every path printed and matched by the
package is derived from the package's location, one directory below the
repository root.

Usage — no default mode: a verb is required. `just render`, `just install`,
and `just install-agents-file` are the sanctioned entry points to this package's
verbs; ARCHITECTURE.md, Sanctioned Invocation, has the complete list of
recipes reaching this package. They wrap:

    python3 -m gen_defs generate R           # render templates into R
    python3 -m gen_defs install R            # full-product install into R
    python3 -m gen_defs install-agents-file H D  # install the harness agents file into D

The first two name their output root positionally, and neither defaults,
because there is no in-repository tree left to default to; the third names a
harness and the directory its agents file is installed into, and is described
in the `agents_file` module docstring. A fourth verb, `dev`, is internal and unsupported — absent from the
main help, listed by `dev help` — and serves this repository's own just
recipes: `just render` reaches the harness agents-file render (`agents_file`
module docstring) through it, by way of the private `render-agents-file`
recipe. Each verb declares only the flags it can act on: what a verb cannot
do is unrepresentable on its command line rather than refused after the fact.

There is no verification verb, and its absence is a decision. A render is the
only thing that knows what a template produces, so a verb that re-rendered a
tree and compared would be asking the producer whether it agrees with itself —
a rendering defect reaches both sides and the report reads clean. What a
render's output is worth comparing against is a SECOND, independently produced
tree, which is what `just render-diff` compares: `diff -rq` between two slots
under rendered/, each produced by its own `just render`. A stale definition in
an installed tree is retired by the install's own prune (`pruning` module
docstring) rather than reported by a checker, and the render's own properties
are asserted in tests/test_gen_defs.py against values the render did not
compute (ARCHITECTURE.md, Verification, and Why There Is No Verification Verb).

Generation is deterministic and idempotent: output depends only on the
template, the shared chunks, and the template's path.
"""

# Semver, bumped on mechanism changes; history: git log. Not embedded in
# rendered banners — that would churn every generated file on every bump.
__version__ = "7.0.0"
