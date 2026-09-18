# Driver burndown: what the step table stopped needing

Two independent architect surveys of `kb_driver/` and `kb_pipeline.py` — one asking *does this serve
the end the thesis describes*, one asking *where has a narrow concern been elaborated past its
weight*. They converged on seven findings and each found more the other did not. This is the union.

**The shape of it.** The driver is roughly six thousand lines sequencing nine stages. Seven invoke a
tool and read an exit code; two dispatch a seat to write and review one document. Around those two
stands an apparatus built for a dispatch model that no longer exists — a coordinator agent driving
the ledger by hand, and a seat fanning out to member sub-seats. Both are gone from the step table.
Neither is gone from the code, the templates, or the contract documents.

**The suite has been documenting the vacancy rather than catching anything.**
`tests/test_kb_driver_steps.py` asserts `envelope_rows == waves` (both empty), `scope_rows ==
set()`, and the worker-writer set `== set()`. Those are tests of emptiness.

## What is established, and how

```
$ grep -n "WAVE\|ENVELOPE\|WORKER" kb_tools/kb_driver/steps.py
39,45,46,54,55,62:   enum definitions only — no Step(...) in STEPS sets any of them

$ grep -rn "_wave(\|_refresh(" kb_tools/kb_driver/
run.py:1068, run.py:1152:   definitions; no _HANDLERS entry, no call site

$ grep -rn "undeclared(" kb_tools/ | grep -v "def undeclared"
(no output)

$ grep -n "kb_driver run" .claude/commands/kb-build.md
21:  ...kb_driver run --source <path> [--source <path> ...]      — no --decide start.proceed=yes

$ grep -rn "watch" kb-testing/justfile
(no output)                     — cli.py:170 says watch is "Required in the kb-testing recipes"
```

## Rules

1. **A row states what its deleted thing caught and where that coverage now comes from** — or that
   it is accepted as lost, stated rather than omitted.
2. A row deletes the tests asserting the behaviour it removes, and says so. **Several here assert
   only that a set is empty**; those go with their subject and are not coverage.
3. **The contract moves with the row.** Several of these are recorded in `SPEC.md` or
   `ARCHITECTURE.md`; a row that leaves a document describing what it removed is not done. State
   the design, carry no magnitude.
4. Where a thing carries recorded evidence — a scar naming an observed failure — **say so in the
   commit**, even when the row does not touch it. A reader meeting a diff near `PHASE_5_FIX_CAP`
   must not read it as cap erosion.
5. Code citations by symbol, never by line. Do not commit.
6. **Green at handoff means no failure this row introduced that this row could have fixed.** These
   rows run concurrently over one package, and a deletion's last consumer often sits in a file
   another row owns — so a row can be correct and the tree still red. Where that happens, name the
   failure and hand over the patch that fixes it; a row is not entitled to reach into another's
   file, and is not excused from saying exactly what needs to happen there.

## Rows

| Row | What | Who | Blocked on | Done when |
|---|---|---|---|---|
| **D1** | **The wave and scope apparatus.** `Unit.WAVE`/`WAVE_STAR`/`REFRESH`, `Writer.WAVE_SESSION`/`WORKER`, `Parse.ENVELOPE`/`SCOPE`; `run._wave`, `Member`, `pending_members`, `_refresh`, and `_call`'s deviation-append; `call`'s `is_wave` and the `WORKER` branches; `envelope`'s envelope and scope halves — `Envelope`, `Deviation`, `parse_envelope`, `envelope_block`, `append_deviations`, `Scope`, `parse_scope`, `SCOPE_LINE_CONTRACT`; `prompt_templates.WAVE_INFIX` and `RESERVED_WAVE_SLOTS`; `replay.envelope`; four fragments no template names. **`run.py`'s own docstring states the position: "No row in the current table is a wave."** `DECIDE:` what survives in `envelope.py` — `kb_claimgraph.ask` calls `parse_record` and `check_exhausted`, so the record parser and a minimal `ProseBlocks` stay; establish which of `prose_field`, `prose_array` and `ProseBlocks.take` have a caller outside `parse_envelope` before cutting. `ROADMAP.md` item 6 ("the envelope contract is one definition, not two") **retires rather than being done** | PC | — | The surviving `envelope.py` surface named by symbol with its caller. The four fragments named in the commit, since deleting reviewed prose is recoverable only from git. `ARCHITECTURE.md`'s envelope rows corrected |
| **D2** | **The self-graded-work guard.** `Step.writes_register`; `run`'s `_authored_ids`, `_registers_on_disk`, `_register_path`, `_minted_grades`, `_check_minted_grades`, `_mint_remedy` and the two-branch dispatch in `_run_step`. No row declares the field, and `ARCHITECTURE.md` already calls it "dormant, not removed". **This is a recorded decision to keep, not a scar** — nothing was learned from a failed build; a stage set was deleted and the guard was left standing. Say which in the commit. **`SPEC.md`'s driver contract carries the sentence this implements** — *"a seat that grades its own minted work stops the stage"* — and it goes or is re-attributed to `kb_claimgraph`, whose minting is mechanical and undispatched | PC, then **TW** for SPEC | — | `_run_step` collapsed to the handler dispatch. The SPEC sentence disposed of, not left describing a guard that is gone |
| **D3** | **`CoverageReport.undeclared`** — the `reason` field, its two `__post_init__` invariants, the constructor, and the five branches reading it (`_named_missing`, `_coverage_refusal`, `_excused`, `stage_status`, the `UNDECLARED` status word). Nothing constructs one, not even a test; its docstring says "three shapes reach here" and none does. **The exact case `kb_tools/AGENTS.md` rules on** — name the producer before you write the refusal. A future check that cannot read its declaring artifact is one unsatisfied unit with a `detail`, which the existing machinery renders | PC | — | `CoverageReport` reduced to `units` + `degenerate` + `unit_class`. Where the state would now surface instead, stated |
| **D4** | **`start.proceed`.** The row, `barriers.START_PROCEED` and its spec, `run._pre_proceed`. It asks whether to proceed with a build the operator launched by typing the command, and `/kb-build` prints that command **without** the flag that answers it — so the documented human path is run, get stopped, re-run. **It fires before `pre.kb-root`**, so the one fact that would change the answer — a populated `kb-root/` that refuses the build — is not read until after the confirmation. `DECIDE:` remove it, or move `pre.kb-root` ahead of it. The step table's TOCTOU reasoning for placing `pre.kb-root` last does not conflict: a barrier is an exit, and the next process re-reads everything | PC | — | The decision with its reason. If removed, `kb-testing`'s note that it "fires unconditionally on every live run" goes with it |
| **D5** | **Watch mode.** `watch.py`, `cli`'s `p_watch` parser, `baton.MODE_WATCH`, `_MODE_BATONS`, `WATCH_MODE_EXIT_CODES`, `EXIT_WATCH_*`. Its premise is in its own first paragraph — that `/kb-build` backgrounds the driver and holds no pipe — and `/kb-build` does neither. `SPEC.md`'s Project Scoping settles it: *"Agent-assisted launch and management of a run is later work."* **`cli.py` claims watch is required in the kb-testing recipes and it is not.** `watch.recorded_stages` has a live caller in `run._recorded_stages` and moves rather than dies. `DECIDE:` delete, or keep and fix the two false statements — if agent-assisted run management is returning, that belongs in `ROADMAP.md` and the module says so. Deleting also retires `no_writes`, which replaces `builtins.open` process-wide to guard a read loop | PC | — | The decision with its reason. `recorded_stages` relocated with its caller. `ARCHITECTURE.md`'s module-table and CLI rows corrected |
| **D6** | **The action-card apparatus.** `kb_pipeline`'s `RecordStep`, `StageStatusStep`, `GateStep`, `CappedLine`, `CardItem`, `_kb_util_command`, `_front_end_command`, `_cap_values`, `card_lines`, `CARD_PREFIX`, `CONTRACT_LINE`, the `card=` tuples in `STAGES`, and `show_confirmation` with its five helpers and `Stage.user_gate`. Every card instructs a reader to run a command the driver runs itself; `StageStatusStep` tells that reader to *"dispatch against those and compose no path of your own"*. **`SPEC.md` abolished the reader**: *"there is no coordinator seat… no artifact this toolchain produces admits a second controller."* The surveys split on whether a descriptive line per stage must survive, one of them holding that the card is the only place a stopped build says what the stage it stopped in was *for*. **That is false and the row is a deletion.** `Stage` carries `display` beside `card`, and its values are the purpose labels — "document tree derived", "claim-graph spine seeded", "dependency attribution", "validation gate". It reaches the reader in three places already: the checklist line (`[marker] id  display`), the stage-status `FACT` line (`id (display) — detail`), and the ledger commit subject (`id | display`). What the card adds beyond that is the instruction half, and its reader does not exist. `show-confirmation` goes with it — the second door `ARCHITECTURE.md`'s own opening-gate section says must not exist, which the driver never invokes | PC + **TW** | D1-D5 | A stopped build demonstrated still naming its stage and what that stage does, from `display` alone. `ARCHITECTURE.md`'s opening-gate and card paragraphs disposed of with it |
| **D7** | **`ledger`'s latent ops and their retry apparatus** — `write_op`, `validate_build`, `_VALIDATE_EXITS`, `_WRITE_OP_EXITS`, `WRITE_OP_RETRY_LIMIT`, `_outcome`'s `retry_rc` loop and contended-write warning, `Outcome.barrier`, `RunPaths.values`. Both docstrings say no row calls them. **Removing the driver-side adapter does not touch the recorded keep-decision for `kb_survey.validate`** — `kb_util validate-build` remains, and a three-line adapter is re-derivable. Say so in the commit; `ARCHITECTURE.md` cites that decision | PC | — | `_outcome` reduced to one `_run` and the rc map. The `kb_survey.validate` decision explicitly untouched |
| **D8** | **The brief-constants pool.** `steps.WRITE_OP_SLOTS`, `VALUES_FLAG_SLOT`, `CONSTANT_SLOTS`, `SCRATCH_LAYOUT`, `_layout_paths` — a pool of slots no dispatched template names. **Keep the mechanism**: `prompt_templates.render`'s `constants` parameter is live, filled by `kb_claimgraph.ask`'s own marker slots. **Keep `TEMPLATE_PROHIBITIONS`** — a lint is meant to guard templates that do not exist yet. *Its other half — `replay.py`'s assignment-table reader — is subsumed by D11, which deletes the module.* | PC | D1 | The `constants` mechanism demonstrated still reached |
| **D9** | **The small-dead sweep**, one commit. `config.brief_transport` / `BRIEF_TRANSPORTS` / `DEFAULT_BRIEF_TRANSPORT` — validated, stored, read by nothing, so an operator setting it gets no change and no complaint. `BarrierSpec.payload`. `steps.SERIES_GATE` and `run.revisions_spent`'s gate branch — one series exists, and with one series the body is `round_number - 1`. `prompt_templates.SEAT_SLOT` and `RowSlots.seat`. `TimeoutSection.wave_seconds`. Plus three stale references: `run._only_series`'s docstring names a row that does not exist, `baton._ARTIFACT_NOTE` cites a rule the current `kb-build.md` does not contain, and `replay.write_assigned`'s docstring references a function that is not in the module | PC | D1 | Each named with what read it. Nothing reported as removed that a caller still reaches |
| **D10** | **`SPEC.md`'s entry-point size budget** — an eight-line contract paragraph about word counts and a runaway threshold. `ARCHITECTURE.md` already reports the mechanism gone and says SPEC *"names a document nothing in the toolchain sizes."* Both paragraphs go. If the budget returns when a seat writes that document again, it is a `ROADMAP.md` item and not a standing clause with no mechanism | **TW** | — | Both paragraphs gone. No magnitude introduced anywhere |

| **D11** | **`--dry-run` and its fake-model invoker leave the deliverable.** `kb_driver/replay.py`, the flag through `cli.py` and `config.py`, `test_kb_driver_dryrun.py`, `test_kb_driver_replay.py`, `kb-testing`'s rung-1 recipe, the `SPEC.md` sentence, and `ARCHITECTURE.md`'s 387-396/406/424/648. **The consumer named in its own docstring does not exist** — `.claude/commands/kb-build.md` never offers the flag and the only caller anywhere is the dev harness, so this is test functionality in shipped surface. The `ask.SeatAsk` fact carried by the ARCHITECTURE paragraph is true for `--no-inference` and survives the flag's removal. `--no-inference` is untouched; the `Invoker` protocol and its `invoker=None` default stay, being ordinary injection | PC | — | Flag gone from code and contract. `just test` green. `Step.spends_own_inference`'s comment stating what is true without the flag |
| **D12** | **The driver's end-to-end integration test, built from scratch in the test tree.** D11 deletes the only walk that exercised the real ledger subprocess, the consuming repo's `kb-refresh`/`kb-verify`, the postconditions and the barriers together. It is rebuilt as a test that injects a fake `Invoker` at the `inference.invoke` seam — no production flag, no shipped scenario module, no step-table knowledge outside the suite. **Not a transplant**: the deleted files are not a starting point | PC | D11 | One test walking the stage table against a real fixture repo with the model injected from the suite |
| **D13** | **`phase-5` collapses to a fixed sequence: one review round, one fix round, no failure.** No re-review after the fix, no counting, and review findings never fail the stage. That is a structure rather than a bounded loop, so the loop machinery goes: `ReviewCycle`, `REVIEW_CYCLES`, `RoundsSpent`, `LoopSeries`, `_review_loop`, `_review_round`, `_spend_or_escalate`, `_only_series`, the two-letter series vocabulary and the `review/{stage}-{series}{round}-{author}.md` grammar it feeds, the cap barrier, `kb_pipeline.PHASE_5_FIX_CAP` and its `phase_5_fix_cap` slot, and the exit-17 no-op-fix detector (`CappedLine` names that cap but is card machinery — **D6 owns it**) — **about a third of `run.py`**. `_report_round` survives in whatever form records the two calls. **`PHASE_5_FIX_CAP` is not eroded, it is made structural**: `CONVENTIONS.md` records a pipeline that looped until a reviewer stopped finding problems, against instructions that made problems inexhaustible. A fixed two-call sequence cannot reintroduce that, because nothing loops on a model's opinion. The document under review is `README.md`, composed from the index except for one drafted passage. **Minimum viable collapse** — this stage is up for redesign, so nothing here is re-architected on the way out | PC | `run.py` ownership — D2 and D6 also edit it | The two calls run in sequence and the stage records both. No counter, no cap, no series. `just test` green |


## Not buildup — established as proportionate, do not touch

`steps.PATH_SLOTS` and `call._path_complaints` (a precondition standing in for an instruction to a
model, with the live failure recorded — a review that read a different repository's KB);
`runlog`'s lock; `baton`'s card table, every row reachable; `ledger._failure_detail` (recorded: a
sweep of builds relaying `exited 1` and nothing else); `run.RUNNER_ATTRIBUTES` (fixes a named
defect, and `ROADMAP.md` names it as a landed prerequisite); `envelope`'s prose-block transport (a
corpus of mathematics makes `\sigma` inside JSON the ordinary case);
`prompt_templates`' two-direction fill and the `dyn.` namespace; `run._assemble_overview`'s byte
comparison; `CoverageUnit.asserts_own_work`; `ov.docent-check`, whose docstring gives the wrong
reason for the right check — a resume skips `pre.preflight`, so on a resume this is the only one.

## Order

**D1 first.** Largest, and D8's and D9's last entries fall out of it.

**D2, D3, D4, D5, D7, D10 in any order** — independent of each other. D3 is the smallest and the
doctrine case is exact. D10 is TW-only.

**D6 after the rest**, because it is the largest surface and touches two contract sections — not
because it is unsettled. Its reader question is closed: `Stage.display` already carries what the
card was thought to be the only source of.

**D11 has landed.** **D12 follows it** and is the only row here that adds code rather than removing it.

**D2, D6 and D13 all edit `run.py`** and cannot run concurrently. D13 is the largest of the three.
