"""The claim-graph builder's command line: run it from inside the consuming repo.

Nothing is discovered but the root: the repository root is walked up to from the
working directory, and the KB is the directory beside it — the same rule every
other tool in this toolchain resolves a root by, and the reason none of them
takes an override.

**``graph-init`` runs before this**, and this build does not seed. That verb
creates the derived-index directory and installs the runner include line, which
is the mechanism the last stage's refresh and verify targets exist through. A
run finding no spine says so and names the command that installs one, rather
than creating half of it itself.
"""

import argparse
import sys
from functools import partial

from .. import __version__, inference, kb_load, kb_pipeline, kb_util
from . import ask, conform, depends, discover, equations, unmarked
from .build import build

#: The scope vocabulary, read from the stage table rather than declared twice.
#: What the values distinguish is which *stage* an invocation of a pass is,
#: and that pairing is ``kb_pipeline.ClaimgraphInvocation``'s — so this module
#: parses the flags and asks what stage they name instead of branching on
#: numbers whose meaning is stated nowhere.
SCOPES: tuple[str, ...] = tuple(
    dict.fromkeys(
        stage.claimgraph_invocation.scope
        for stage in kb_pipeline.STAGES
        if stage.claimgraph_invocation and stage.claimgraph_invocation.scope
    )
)

EXIT_OK = 0
EXIT_GATE_FAILED = 1
EXIT_USAGE = 2
EXIT_NO_SPINE = 3

#: Where the write passes' values files land, under the project's scratch
#: space — the only place an uncommitted file may sit without failing a
#: clean-worktree gate.
SCRATCH_SUBDIR = "claimgraph"

#: Where the inference-spending passes record their asks — each group's ask
#: record and each call's captured stream — beside the write passes' values files.
ASKS_SUBDIR = "asks"

#: Every pass number the stage table declares an invocation for, in order.
#: Derived rather than typed, so a pass this tool accepts is a pass some stage
#: of the build actually is.
PASSES: tuple[int, ...] = tuple(
    dict.fromkeys(stage.claimgraph_invocation.which_pass for stage in kb_pipeline.STAGES if stage.claimgraph_invocation)
)


#: The stage ids this module branches on, read off the table so a rename
#: reaches here. The declared pass is the else.
_CLAIMS_DISCOVERED = kb_pipeline.claimgraph_stage(
    which_pass=1, scope=kb_pipeline.CLAIMGRAPH_SCOPE_FULL
).id  # type: ignore[union-attr]
_EQUATIONS_MINTED = kb_pipeline.claimgraph_stage(
    which_pass=1, scope=kb_pipeline.CLAIMGRAPH_SCOPE_EQUATIONS
).id  # type: ignore[union-attr]
_REFERENCES_FOUND = kb_pipeline.claimgraph_stage(
    which_pass=2, scope=kb_pipeline.CLAIMGRAPH_SCOPE_UNMARKED
).id  # type: ignore[union-attr]
_DEPENDS_ATTRIBUTED = kb_pipeline.claimgraph_stage(which_pass=2, scope=None).id  # type: ignore[union-attr]

#: The stages whose whole work is a reading a model performs: no part of them asks nobody.
_READING_ONLY = (_CLAIMS_DISCOVERED, _REFERENCES_FOUND)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kb_tools.kb_claimgraph", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s (kb_tools {__version__})")
    parser.add_argument(
        "--pass",
        dest="which_pass",
        type=int,
        choices=PASSES,
        default=PASSES[0],
        help=(
            "which pass to run: 1 authors the declared graph — the claims the author marked — over a fresh "
            "tree, and is mechanical end to end; 2 finds and classifies the discovered graph's edges over "
            "pass 1's output, and spends inference"
        ),
    )
    parser.add_argument(
        "--scope",
        choices=SCOPES,
        default=None,
        help=(
            "which stage of the pass to run. Pass 1, which nodes to mint (default 'block-hosted'): "
            "'block-hosted' authors the claims the author marked over a fresh tree and is mechanical end to end; "
            "'full' runs the node pass over every leaf the block-hosted run recorded unread, spending one letter "
            "ask per paragraph it reads; 'equations' mints the referenced equations nothing else holds, "
            "mechanically, once the node pass has judged the prose. Pass 2: 'unmarked' asks of each shortlisted "
            "pair of claims whether the source's text points at the target with no cross-reference; with no "
            "scope, pass 2 classifies every edge candidate and writes the edges"
        ),
    )
    parser.add_argument(
        kb_util.NO_INFERENCE_FLAG,
        dest="no_inference",
        action="store_true",
        help=(
            "spend no model call: run only the part of this invocation that asks nobody anything. Pass 2 "
            "records the edges containment settles and leaves the pairs it did not as open and unrecorded; "
            "the declared pass is mechanical already and is unchanged by it; claim discovery and the "
            "unmarked-reference asks have no such part and are refused"
        ),
    )
    arguments = parser.parse_args(argv)

    try:
        repo_root = kb_util.find_repo_root()
    except kb_util.RepoRootError as error:
        print(str(error), file=sys.stderr)
        return EXIT_USAGE

    kb_root = kb_util.kb_root(repo_root)
    if not kb_util.document_tree_present(repo_root):
        print(f"{kb_root} holds no document tree, so there is nothing to build a claim graph over", file=sys.stderr)
        return EXIT_USAGE

    absent = conform.spine_seeded(kb_root)
    if absent is not None:
        print(
            f"the claim-graph spine is not installed: {absent}. Seed it first:\n"
            f"    {kb_util.invocation()} {kb_util.OP_GRAPH_INIT}",
            file=sys.stderr,
        )
        return EXIT_NO_SPINE

    # After the spine check, so an unseeded tree is sent to graph-init, whose
    # refresh stamps it, rather than to a refresh of its own.
    try:
        kb_load.require_current(kb_root)
    except kb_load.FormatRefusal as refusal:
        print(str(refusal), file=sys.stderr)
        return EXIT_USAGE

    # Which stage this invocation is, resolved in the table the build's driver
    # composed the same flags from. A pass number branches nothing here: the
    # stage decides, and a combination no stage declares is a usage error rather
    # than a silent fall-through to the mechanical pass.
    scope = arguments.scope
    if scope is None and arguments.which_pass == PASSES[0]:
        scope = kb_pipeline.CLAIMGRAPH_SCOPE_BLOCK_HOSTED
    stage = kb_pipeline.claimgraph_stage(which_pass=arguments.which_pass, scope=scope)
    if stage is None:
        print(
            f"--pass {arguments.which_pass} with --scope {scope} is no stage of the build; "
            f"the invocations this tool runs are "
            f"{', '.join(' '.join(s.claimgraph_invocation.flags) for s in kb_pipeline.STAGES if s.claimgraph_invocation)}",
            file=sys.stderr,
        )
        return EXIT_USAGE

    precondition = kb_pipeline.precondition_of(stage)
    print(
        f"[claimgraph] FACT stage {stage.id} ({stage.display})"
        + (f"; runs over what {precondition.id} left" if precondition else "")
    )

    # Refused rather than run empty: everything these stages record comes out of
    # a reading a model performs, so there is no half of either that asks
    # nobody. A run of one under the flag would record nothing and then fail its
    # own exit condition, reporting a corpus fault for a wiring one.
    if stage.id in _READING_ONLY and arguments.no_inference:
        print(
            f"{kb_util.NO_INFERENCE_FLAG} names no run of {stage.display}: everything it records comes "
            f"from a reading a model performs, so it has no part that asks nobody. A build spending "
            f"none omits this stage rather than running it.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    scratch = repo_root / kb_util.scratch_dirname() / SCRATCH_SUBDIR
    asks = scratch / ASKS_SUBDIR
    reader = partial(ask.ask_without_tools, captures=asks)
    if stage.id in (_DEPENDS_ATTRIBUTED, *_READING_ONLY) and not arguments.no_inference:
        try:
            inference.check_environment()
        except ValueError as refusal:
            print(f"{stage.display} spends inference, and the environment names no server: {refusal}", file=sys.stderr)
            return EXIT_USAGE

    if stage.id == _DEPENDS_ATTRIBUTED:
        report = depends.build(
            kb_root=kb_root,
            repo_root=repo_root,
            scratch=scratch,
            reader=None if arguments.no_inference else reader,
            asks=asks,
        )
    elif stage.id == _REFERENCES_FOUND:
        report = unmarked.build(kb_root=kb_root, repo_root=repo_root, reader=reader, record_dir=asks)
    elif stage.id == _CLAIMS_DISCOVERED:
        report = discover.build(kb_root=kb_root, repo_root=repo_root, scratch=scratch, reader=reader, record_dir=asks)
    elif stage.id == _EQUATIONS_MINTED:
        report = equations.build(kb_root=kb_root, repo_root=repo_root, scratch=scratch)
    else:
        report = build(kb_root=kb_root, repo_root=repo_root, scratch=scratch)
    print("\n".join(report.lines()))
    return EXIT_GATE_FAILED if report.failed else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
