# CONVENTIONS – kb_tools

House rules and traps only, for someone working *inside* `kb_tools/`. The contract and its mechanism
live in SPEC.md and ARCHITECTURE.md — this file never restates them, only points at them.
Unqualified, those names mean this directory's copies; the repository-root documents are named as
root.

- **Never run these tools ad-hoc.** Use the consuming project's runner target (`kb-verify` /
  `kb-refresh` / `kb-stats`, or the `kb_util` build ops through the runner include) — see SPEC.md,
  Runner Targets, for the sanctioned channels. The exception is a measurement script of your own
  over already-built kb-roots, and it runs through `measure-kb-roots` (`kb-testing/justfile`, whose
  `[doc]` states the argv it hands you). Reaching an op these tools already expose is running them,
  read-only or not. Write the script read-only; nothing checks that. The report a measurement lands
  in cites the script by path.
- **Never spell a harness path.** `.claude`, `.opencode`, their `-temp` scratch directories and the
  `<harness-dir>/agents` PYTHONPATH entry come from `install_location` through `kb_util`'s
  functions, called where the value is used and never at import: the package is imported from the
  source tree by tests and `kb-testing` recipes, where no harness directory exists, and a
  module-level spelling would fail every one of those imports. A test that spawns a kb_tools
  subprocess sets its PYTHONPATH to `install_location.current().agents_dir` — the installed layout
  `tests/conftest.py` stands up — never to the source tree, from which the child cannot locate
  itself.
- **`pandoc.py` and `dot.py` are the only modules that name their binaries.** Each is one of the two
  enumerated stdlib-only exceptions (SPEC.md, Corpus Invariants). What makes them enumerable is that
  nothing else in the package builds an argv for either or spells either name in a string it hands
  anywhere. A preflight item or a report line that names a binary takes the name and the message
  from the seam. This is enforced by `tests/test_binary_monopoly.py`. A second call site is a
  defect: it is a second place that knows how its binary is driven, and the seam exists so that
  replacing either binary is one module's work rather than a sweep.
- **Adding a third stdlib exception is a design decision, not an implementer's.** SPEC.md
  enumerates exactly two (the `pandoc` and `dot` binaries, reached through `pandoc.py` and
  `dot.py`); proposing another goes to the architect, not into a patch.
- **A `kb_claimgraph` stage never exits on a model's opinion.** Every stage exits on a comparison
  between two artifacts or a verifier's return code (`gate.py`, ARCHITECTURE.md's Claim Graph
  section) — a new stage does not get to add a third kind of exit. This is a scar, not a preference:
  an earlier pipeline ran two review loops until a reviewer stopped finding problems, against
  reviewer instructions that made problems inexhaustible — one resolving severity ambiguity toward
  the more severe, another demanding a tool be named wherever none existed — while the loop that
  actually finished a build exited on a subprocess return code. A stage that asks a model whether
  the work is good enough is reintroducing that failure, not a smaller version of it.
- **No prompt reaches a model from a heredoc or an in-code string.** Every prompt is a template
  under `kb_driver/prompt-templates/`, rendered with its slots filled — every ask, its system prompt
  and its re-ask included. A prompt assembled from string literals is a model-facing artifact that
  does not look like one: it never lands in a diff as prose, it is never read end to end, and it
  never goes to the prompt-engineer, because nothing about it says "document". This is a scar.
  `kb_claimgraph`'s claim-identification ask carried an answer format whose central rule — that a
  prose block's two markers carry one number — was stated nowhere in it and demonstrated only at
  block 1, where the two numbers are both `1` and the rule is invisible; the seat got it wrong on
  roughly one answer in ten, always at an interior block, and stopped a 176-document build twice.
  The same ask requested a `no-claim` reason as "one sentence saying so", which nothing checks
  beyond non-emptiness and which is written into a document's frontmatter permanently. Neither had
  been read as a prompt by anyone.
- **A model call is `inference.liaison_tools.call_chat` and nothing else; a system prompt is a
  fragment, never an agent definition.** A call that spawns a process, or one whose system prompt is
  an agent-set seat's definition, is the CLI path this package deleted: its bounds, its tool set and
  its model were the CLI's and the definition's, not anything the build states.
- **`prompt-templates/` holds what is dispatched; `prompt-templates/fragments/` holds what is
  spliced.** Which one a new file is, is settled by where it goes and by nothing else — no prefix,
  no suffix, no list to read. Every file under `fragments/` is registered in exactly one of
  `prompt_templates`' two vocabularies, `FRAGMENT_SLOTS` (the composer resolves it, because a
  template named its slot or a caller rendered it whole) or `ALTERNATIVE_NAMES` (a caller picked
  it), and `tests/test_kb_driver_prompt_templates.py` checks that correspondence both ways — so a
  fragment nobody registered fails rather than sitting unreachable.
- **A caller-selected alternative ends without a newline; the template it fills supplies every line
  break around it.** Every alternative a caller can pick — the set
  `prompt_templates.ALTERNATIVE_SLOTS` registers — is spliced into a slot sitting inside a line
  rather than appended as a block of lines. An editor that adds the customary final newline moves
  the prompt's bytes and nothing about the file says so.
  `tests/test_kb_driver_prompt_templates.py` checks every registered alternative for it.
- **Prompt generation is tested against in-test fixtures and goldens, never against the working
  templates.** A generation test writes its own small templates and fragments, points the composer
  at them (`tests/_fixture_templates.py`), composes real asks through them, and compares the result
  byte for byte with a golden held in the test. A test that renders a working template and compares
  it with a stored copy is a checksum of the wording: every prompt edit breaks it and it guards no
  behaviour. A test over the working templates checks structure only: every slot filled, the slot
  order, the shared prefix. No test asserts a prompt's prose; what a test may key on is the
  offered letters, the slot set, the system fragment and the closing line's letters.
- **A `dyn.` slot the caller supplies under one alternative lives in that alternative's fragment and
  nowhere else.** Composition refuses an unsupplied slot and an unused value alike.
- **A register holds four entry kinds, and `RegisterEntry.kind` is where you learn which.** `clm`,
  `sup`, `exp` and — since the off-graph endcap — `work`, whose id is `work-` plus a citation key
  rather than a hash body, so a pattern spelling `[a-z0-9]{6}` does not match one. Anything keying
  on that field, or on `locate_register_entries`, meets all four; a branch handling three silently
  drops the fourth, which is how a work entry becomes a lost entry the census reports and nobody
  expected. The one asymmetry to know: a `work-` entry carries no `- solidity:` line and no
  depends-on list, because the node is terminal and nothing derives a value for it.
- **YAML is `kb_yaml`'s.** Every YAML byte a KB holds is read and written through it. No module
  splits `---`, strips a `--- ` marker or parses an index line itself; test `bool` before `int` when
  typing a value.
- **A test KB is stamped.** A test that builds a KB inline builds it through
  `tests/_stamped_kb.py` (`write_stamped_kb`, `write_index`); an unstamped KB in a test is a
  migration's input — a copy of the `0.9.0` goldens or of `fixtures/superseded-shapes/`, or the
  document tree `graph-init` seeds — and nothing else. A KB copied for refresh sits in a directory
  named `kb-root`: the build records are read beside `kb-root/`, so a copy named otherwise finds no
  KB for them.
- **Only `kb_migrate` knows a superseded format.** Every other module reads the current one, from
  disk or converted through `kb_load`, and spells no superseded form — not the comment-block opener,
  not a `.jsonl` index or `.json` record name, not in a comment either.
  `tests/test_superseded_format_monopoly.py` enforces it. A test that needs a 0.9.0 document takes
  one from the `0.9.0` goldens or `fixtures/superseded-shapes/` rather than typing it.
- **A frontmatter writer after the declared pass carries forward every attribute it does not own.**
  `set-frontmatter` replaces the whole block, so a key left out of the values file is a key removed:
  a leaf's block-hosted `claims:` left out is caught only by verify, after the write, and a
  `path-stable:` left out is caught by nothing. Such a writer reads the block as it stands and
  restates what is not its own: `write.land_leaf` is the one that does, and a new writer goes
  through it rather than beside it. The `kb-format` stamp is the exception: `set-frontmatter`
  carries it over itself, as the block's last key, and `store`'s frontmatter splices keep it last —
  a new frontmatter writer goes through them rather than appending past it.
- **Keep no prose copy of an op's key vocabulary.** The vocabulary is closed, total, and per-op,
  stated once in `values.OP_FIELDS` (SPEC.md, The Write API's Contract). A second statement of it —
  in a doc, a docstring, or a comment — drifts; point at `values.OP_FIELDS` or the refusal message
  it produces instead of transcribing it.
- **Never spell the node-kind list.** It is `kb_schema.NODE_KINDS`, and the same rule applies to it
  in code as to `OP_FIELDS` in prose. A site that *iterates* — a census, a breakdown, a union, an
  ordering — reads the tuple and names no kind; a site that *branches* keeps naming kinds, because
  that is what a branch is, and wraps its table in `kb_schema.kind_table`, which refuses one that is
  not total over the vocabulary at the moment it is defined. A count derived from the list ("all
  four node types") is the same copy in a shorter form. This is a scar: `work` arrived as a fifth
  kind with no constant to arrive in, so every site spelled its own list and each drifted alone — a
  census whose total counted the works and whose breakdown never named them, and a union returning
  four of five that drew every `rests-on` target as a ghost id with the record sitting in
  `claims.jsonl` the whole time. Note which question you are asking: `kb_schema.ID_KINDS` is what
  gets *minted* and excludes `work` deliberately; this is what exists.
- **Never enumerate what you will accept in a field this package does not fill.** `OP_FIELDS` and
  `NODE_KINDS` above end at "point at the constant"; this inverts, because no constant is total over
  a vocabulary nobody here defines. Read such a field whole and branch only on the values you must
  act on — `tree.CLEVEREF_REFERENCE_TYPES` — handing everything else downstream under its own name,
  the way an unrecognised Div class falls back to itself in `authored_blocks.lua`. A table that must
  stay closed keeps its residue counted and reported instead (`Census.unclassified`, `build.py`'s
  `stage-B-unclassified` line); a pattern or a branch enumerating its accepted values leaves the
  unanticipated one no trace at all. This is a scar: `tree.ANCHOR_RE` spelled `data-reference-type`
  as `([a-z]+)`, which matches `ref` and `eqref` and neither spelling pandoc gives the cleveref
  family (`\cref`, `\Cref`, `\autoref`), so every cleveref reference in the corpus reached the trees
  and was read as none — one paper recorded all thirty of its claims as resting on nothing.
  SPEC.md's cross-reference join says only that the type is the referencing macro's own kind and
  enumerates no vocabulary: a character class enumerating one is a second contract, and a count of
  the spellings written down here would be a third. A model's answer to one of our own asks is not
  this case — that format is ours, and its parser stays strict.
- **A document template's links resolve only where a build stamps it into a KB**, so a `*.md` link
  crawl skips `*.tmpl.md` (`kb_links.DOCUMENT_TEMPLATE_SUFFIX`).

- **A test's placement is decided by what it drives, not by convenience.** A test that exercises a
  `kb_tools` function or module in isolation belongs in `kb_tools/tests/` and runs under `test`
  (`just test`). A test that drives a corpus through the pipeline — a `kb-driver` build over staged
  corpus material, a staged multi-document corpus, anything reaching a `kb-testing/` runner target —
  is an integration test and belongs in `kb-testing/`, never in `kb_tools/tests/`. A build over a
  tracked single-document fixture is not that: it drives the driver, not a corpus. Two written forms
  coexist there: the justfile recipes that already drive staged corpora end to end, and a pytest
  tree at `kb-testing/tests/` for integration tests better expressed that way — the choice between
  the two is only how the test is written, never what kind of test it is. Integration tests run from
  `integration-test` (`kb-testing/justfile`), not from root `test`, which stays the fast unit run.
  Integration test data is staged into gitignored `kb-testing/test-data/transient/` and never
  committed; a test finding no staged data skips, which is normal, not a failure. This is a scar:
  four integration tests had settled into `kb_tools/tests/` with nothing written down to say they
  were in the wrong place.
- **A test reaches a `kb_tools` entry point in-process, and shares a build only through a copy.**
  Call a CLI's `main` through `tests/_in_process.run_main`; spawn `python -m` only where the process
  boundary is what the test is about. A build shared across tests is handed out only through
  `tests/_shared_builds` (`copy_build`, `held_unchanged`), so no test can write into another's
  input.

## Tooling-Repo Targets

The agent-definition repo's own justfile; never installed into consumers:

- `test` — the `kb_tools/tests/` suite (auto-provisions `.venv` + `pytest`; a dev dependency, never
  imported at runtime).
- `format-python` — `black` (line-length 120) + `isort` over every python surface in the repo at
  once: `kb_tools`, `liaison_tools`, `tests`, and `gen_defs`. There is no `kb_tools`-only
  invocation, so a run after editing here also reformats anything left unformatted elsewhere; check
  the diff before committing.
