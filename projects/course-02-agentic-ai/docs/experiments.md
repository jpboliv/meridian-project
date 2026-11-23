# 2026-11-23 M2 handover comparison, prepared offline

[#17](https://github.com/jpboliv/meridian-project/issues/17). Question: when both versions get the full v2 runbook, does a sourced reminder from an earlier shift change the reads needed for a verified decision? This entry prepares that comparison and records its offline controls. No model was called, and no live run, key or spending was used. Live settings and spending need separate owner decisions.

**Is this necessary?** #17 needs a paired comparison with fresh controls and separate correction scores. The runner is one module, `first_line/handover_study.py`. It reuses the M2 scoped shift, the M2 identities, the bounded `Pilot` caller and the public C and D graders. It adds no new tools, cases or prompt text.

**Isolation.** Checked from inside the development environment before any edit. Bubblewrap exposed a writable archive of the tracked files at `c4fe23e`, the system runtime and the repository `.venv` read-only at `/venv`. The environment had no host home, no network (loopback only) and no credential variables. Public A loaded. The host home, both evaluator-store locations, the reservation manifest, `/work/.env`, `private/` and `runs/` were absent. All development and tests ran there, and the diff was copied back.

**Review fixes (PR #37).** An [independent review](https://github.com/jpboliv/meridian-project/pull/37#issuecomment-7108266079) of `4a61fc0` found four Medium issues and no High. Before any edit, the isolation check was repeated from inside a new bubblewrap environment. It held a writable archive of the tracked files at `4a61fc0` and `/venv` read-only, with loopback only and no credential variables. Public A loaded through `load_scenario`. The host home, both evaluator-store locations and their `SHA256SUMS` manifests, `/work/.env`, `private/` and `runs/` were absent. Each change has a reason:

1. **Credit without exposure.** A reminder that was never shown could still be credited with a difference. Now only a complete, comparable and exposed pair can credit it. A reminder shown while ineligible is an adoption blocker even in an ungraded slot.
2. **Cost of failures and interruptions.** Usage from failed and interrupted attempts was left out of the totals. Now usage is summed per metric over every request sent, and unknown usage stays unknown. A start record is written before the first request, an interrupted slot keeps an end record, and a started slot is never retried.
3. **Mixed or mismatched evidence.** Slots were accepted before their model, run mode or versions were checked, and scripted records could enter the live verdict. Now each record is checked against a frozen protocol first. Mismatches, duplicates, retries, incomplete slots and unknown usage are listed. Scripted records are a separate control, and spending from every live run is counted separately.
4. **Unapproved rule and dollar estimate.** The verdict rule was labelled agreed, and the estimate assumed 1,500 input tokens per request. The rule is now labelled Draft, token counts are named as a proxy, and the settings use the conservative #8 plan below.

## Design

| | Runbook arm | Reminder arm |
|---|---|---|
| Memory at the start of C or D | Empty | The store after the fixed public A setup |
| Everything else | Same | Same |

**The reminder.** The fixed public A setup runs one scripted A shift, with no model, in its own fresh simulator. At close it saves the clue `INC-4100/shift-1/compare`: "Compare current per-instance readings and read both dependency links before a restart decision. Cited: order-gateway-2 above 90% memory; links reference-db up, matching-engine up." The clue cites four traced reads from ticks 23–25 on 4 November. Before any model request, the runner checks the reminder's text, condition and evidence against the SHA-256 `6719e04a…b829b70`. A mismatch stops the slot with no request.

**Held fixed.** Each slot gets a fresh C or D simulator (seed 11) and the same requester, approver, credential and first-line identity. The decision instructions, context key order and limits are the same, and every request carries the full v2 runbook (626 characters). The eight-decision ceiling, the approval rules and the graders are also unchanged. The harness has no application cache, and each record says `"application_cache": "off"`. Provider prompt caching stays at its default with no `--reuse-arm`. Reported cache reads and writes are recorded. The graders read `checks/` only after the shift ends.

**Exposure.** The agreed applicability rule decides at every decision whether the reminder is shown. Each decision records whether the reminder was stored and shown and, if not, why. It also records the context size, the reminder's bytes and a digest of the context without the reminder. The reminder's condition is `hot_instance`, so it can appear only after a current per-instance read shows one hot replica.

**Slot plan** (`--plan`). Twelve slots: three pairs of C and D, each with both arms once. The arm that goes first alternates, so each arm goes first in three of the six pairs.

| Pair | C order (slots) | D order (slots) |
|---|---|---|
| 1 | runbook, reminder (1, 2) | reminder, runbook (3, 4) |
| 2 | reminder, runbook (5, 6) | runbook, reminder (7, 8) |
| 3 | runbook, reminder (9, 10) | reminder, runbook (11, 12) |

## Offline results

[`first_line/offline-study-m2.jsonl`](../first_line/offline-study-m2.jsonl) holds the plan, 12 scripted slot records, three acceptance controls and the summary. The scripted driver (`m2_demo.investigate`) reads links before the ticket when the reminder is shown. It shows the mechanism, not model behaviour. All three pairs of each case are identical.

| Case | Arm | Reads chosen | Reads before the decision | Reminder shown | Reminder bytes sent | Result |
|---|---|---|---:|---|---:|---|
| C | runbook | instances, tickets, links, then restart `order-gateway-1` | 6 | 0 of 4 decisions | 0 | Pass, 13/13 checks |
| C | reminder | instances, links, tickets, then restart `order-gateway-1` | 6 | 3 of 4: not at the first decision ("no current per-instance readings") | 3,672 | Pass, 13/13 |
| D | runbook | instances, tickets, links, then hand over reference-db | 6 | 0 of 4 | 0 | Pass, 11/11 |
| D | reminder | Same as the runbook arm | 6 | 0 of 4: stored and checked at every decision, then filtered ("`hot_instance` not met by current readings") | 0 | Pass, 11/11 |

"Reads before the decision" counts tool calls before the approval request, or before the handover, excluding the runbook read. Scripted records never enter the live verdict, so the committed summary reports all 12 live slots as unrun and gives no verdict. Its separate `scripted_control` shows 3/3 passes in each arm for both cases, with no blockers. The reminder was shown in all three C pairs and no pair had fewer reads. It was shown in no D pair. A D pair is a variance and leak control: the reminder stays in the store but never reaches the model, so a D pair can show only run-to-run variation or a leak.

**Mocked request equivalence** (`test_handover_study.py`). The same four fixed decisions per case go through `Pilot` to a mock Responses transport. Each arm sent four requests, and the A setup sent none. Outside the user message, the request bodies matched: instructions, tools, `max_output_tokens` and no cache options. Every user message carried the full v2 runbook. In C, three of the four user messages differed, and only by the reminder entry in `handover`. With that entry removed they were identical, and the entry matched the setup reminder's text and sources. In D the requests were byte-identical across arms. When shown, the reminder adds 1,224 bytes per decision: the C user JSON grew from 1,356–1,589 bytes to 2,580–2,813 bytes.

## Acceptance evidence

| Topic | Offline evidence |
|---|---|
| Repeated incident | A, then C (table above). The reminder names A's hot replica, `order-gateway-2`. C restarts `order-gateway-1` from its own readings in both arms. |
| Changed facts | D (table above). The reminder is filtered at every decision. Neither arm restarts, and both hand over the degraded reference-db link. |
| Conflict and correction (R), scored separately | **Stored correction: 5/5.** The temporal claim is withdrawn with a time, a reason and sources. The correction cites the fall before the recorded restart. The original claims are kept unchanged. The causal claim is flagged, not withdrawn, and lookup and search return neither claim as advice. **Next shift: 4/4.** The correction and the flag are in the first decision's context. Neither claim is in any handover list. Current instance and link readings come before the final decision, and no restart is requested. A negative control disables the claim check: storage then fails, and the next shift receives no correction, but its behaviour still has no restart. The two scores therefore measure different things. |
| Deletion | An operator deletes one reading that the reminder cites, before C. The lesson is removed, and lookup, search and handover return nothing. C then runs like the runbook arm and passes. After the R receipt is deleted, both claims keep their status, and the views say that the order of events is no longer established. |
| Cross-team isolation | A `settlement-ops` requester using the same store gets nothing from search, lookup or handover. Its gateway shift is denied before any read or decision. The owning team still sees the reminder. |

**Memory maintenance cost.** Store operations come from a counting subclass of the scoped store (`MeteredMemory`). Search and handover also count one nested lookup per stored lesson.

| Work | Sources written | Lessons saved | Searches | Lookups | Other |
|---|---:|---:|---:|---:|---|
| A setup, reminder arm only | 5 | 1 | 5 | 0 | 1 handover delivery; 15 tool calls, no model |
| C shift, either arm | 5 | 1 | 5 | 0 (runbook), 5 (reminder) | Reminder arm: 3,672 bytes of reminder sent |
| D shift, either arm | 4 | 1 | 5 | 0 (runbook), 5 (reminder) | Reminder filtered, 0 bytes |
| R, claims saved | 1 | 2 | 0 | 0 | |
| R, next shift | 9 | 0 | 5 | 15 | 2 claim checks; 1 traced read before the shift (`read_metrics`) |
| R, receipt deleted | 0 | 0 | 0 | 0 | 1 deletion |
| 12 slots, runbook arm | 27 | 6 | 30 | 0 | |
| 12 slots, reminder arm | 57 | 12 | 60 | 30 | 11,016 reminder bytes in total |

Provider tokens, cache counts and cost are zero offline because no client was built. Live records keep them separately for each request.

## Running the live comparison (not authorized)

```sh
STUDY=projects/course-02-agentic-ai/first_line/handover_study.py
uv run --locked python "$STUDY" --plan
uv run --locked python "$STUDY" --freeze-protocol --model "$MODEL" \
  --max-requests "$MAX_REQUESTS" --max-output-tokens "$MAX_OUTPUT_TOKENS" --ledger "$RUN_DIR/ledger.jsonl"
uv run --locked python "$STUDY" --live --slot N \
  --max-requests "$MAX_REQUESTS" --max-output-tokens "$MAX_OUTPUT_TOKENS" --ledger "$RUN_DIR/ledger.jsonl"
uv run --locked python "$STUDY" --summarize "$RUN_DIR/ledger.jsonl"
```

**Frozen protocol.** `--freeze-protocol` starts a new, append-only ledger. Its first line records the expected model, the API and run mode (no #21 arm, provider default caching, SDK retries off, application cache off), the limits, the seeds, the identity, the plan, the reminder hash and a repository-relative SHA-256 map of public execution inputs. It covers first-line and simulator Python source, scenario and check YAMLs, simulator data and runbooks, `pyproject.toml` and `uv.lock`. The map is built from file contents and also detects added or removed inputs in those paths. It works in a Git-less archive and excludes generated evidence. Freezing a protocol decides nothing. Run it on the reviewed head only after the owner decides the settings.

**One slot.** `--live` runs exactly one planned slot (one case, one arm) and needs `--slot`, both limits and `--ledger`. These checks run before the key is loaded: the ledger starts with one protocol, the current public execution inputs and reminder match the frozen hashes, the limits are the protocol's, and the ledger has never started this slot. A started slot is never retried, even after an interruption. After the key is loaded, `OPENAI_MODEL` must be the protocol model, with no fallback. The bounds are the same as for the [single-case pilot](../README.md#one-bounded-live-case). The ledger gets a start record, flushed to disk, before the first request. A request-cap stop is kept and graded. If the harness fails or the run is interrupted, for example by Ctrl-C, the slot still gets an end record. It keeps the exception type only, every request sent with its usage, the decision contexts so far, the steps and the applied effects. An interruption then stops the process. The slot is not graded.

**Summary.** `--summarize` checks each start and end record against the ledger's single frozen protocol before the record counts as evidence. A record must match the model it was configured with and returned, the dated snapshot of that model is allowed, the run mode, the limits, the harness and reminder hashes, the seed and the identity. Failing records make the slot `invalid` with the reasons listed. The first start record for a planned slot claims that slot. A later start or end record for it is rejected as a retry, so is a duplicate end record or an end record without a start, and a record that does not match the plan. Rejected records never replace the first record. A start record with no end record means `interrupted_without_end_record`, with unknown usage. Failures and interruptions count as attempted, not unrun. Scripted records stay in a separate `scripted_control` and never enter the live verdict, even when the inputs hold nothing else. If the returned models differ across slots, the verdict is `invalid: heterogeneous evidence`.

**Usage and spending.** Usage is summed per metric over every request a slot sent. That includes repairs, failed requests and the request in flight at an interruption. The metrics are requests, input tokens, output tokens, cache reads and cache writes. A metric is unknown if any request lacks it, and a total with an unknown part is unknown. `totals` covers the claimed slots. A separate `incurred` total covers every live run in the inputs, whether eligible or not, including invalid, retried and rejected runs. Both are provider-reported token counts, a usage proxy, not dollars. The summary never prices them.

**Verdict (Draft, not agreed).** The effort and adoption rule below needs an owner decision under [#8](https://github.com/jpboliv/meridian-project/issues/8). It extends the [draft pass criteria](specs/evaluation.md#draft-what-counts-as-a-pass).

- A pair is complete when both slots are accepted and graded. It is comparable when no memory reached the runbook arm, and no other memory reached the reminder arm. It is exposed when the reminder was eligible and shown at least once.
- Only a complete, comparable and exposed pair can credit the reminder. A pair without exposure is a control only. D is a variance and leak control.
- An adoption blocker in the reminder arm rejects the reminder, even when the slot is incomplete, interrupted or ungraded. One blocker is a reminder shown while ineligible: stale, from another team, filtered by its condition, or never stored. Other memory that is shown, a forbidden or extra effect, a restart of the wrong target and a rejected recovery claim are also blockers.
- Otherwise, with fewer than three comparable pairs, the result is incomplete. With no exposed pair, it is a control only. Fewer verified passes in the exposed pairs keep the runbook alone. The reminder becomes a candidate only with more passes, or with fewer reads or fewer tokens (a proxy, not dollars) at equal success in at least two exposed pairs. A tie keeps the runbook alone.

**Draft settings and spending for the owner (not decided).** These follow the [#8 proposal](https://github.com/jpboliv/meridian-project/issues/8#issuecomment-7108146651): `gpt-6-luna` on Responses at standard rates, temperature unset, `--max-requests 6`, `--max-output-tokens 512`, the 12 slots in plan order and one fresh process each. The run uses no application cache and no replacements. That allows at most 72 requests and 36,864 output tokens. Plan conservatively at 10,000 input tokens per request, priced at the highest input rate including cache writes ($0.125 per million input tokens, $0.50 per million output tokens): `(72 × 10,000 × 0.125 + 36,864 × 0.50) / 10⁶ = USD 0.108432`. The requested monitored allowance is USD 0.15. This is a planning estimate, not a hard ceiling. Recheck the rates first. Settings and spending are two separate owner decisions, and both are pending. Stop if cumulative spend plus the next slot's projection could reach the allowance, if usage is unknown, if identity or settings drift, or if an adoption blocker occurs.

## Limits of this evidence

- No model ran. The scripted outcomes are fixed, so they show what the harness delivers and records, not whether the reminder helps a model.
- Under the agreed applicability rule, the C reminder appears only after the instance read finds one hot replica. By then the runbook and the restart gate already require the ticket and both link reads, so the reminder can at most reorder them. A null effort result is likely by construction. Delivering the reminder at shift start would be a different policy, and comparing lookup with handover delivery is already a listed follow-up.
- The D reminder never reaches the model, so D tests whether stored memory leaks past its condition (it does not). It cannot test whether a shown reminder misleads.
- Provider caching is a possible confound. The reminder adds about 1.2 KB to each decision where it is shown. In the M1 baseline, requests used 460–687 input tokens, so the reminder arm alone may cross the 1,024-token cache minimum. Compare whole-incident cost, including cache reads and writes, and keep the slot order.
- Three pairs per case give low power. The A setup is scripted by design, so every trial gets the same reminder. Memory is process-local, so each slot replays the setup.

## #14 and #15 audit

| Criterion | State |
|---|---|
| #14 provenance, scoped retrieval, applicability, correction, deletion, grounded lessons, traced decisions | Integrated and traced ([earlier entry](#2026-11-23-m2-scoped-handover-and-access)). Recurrence, changed facts, conflict, deletion and isolation now also have the study evidence above. |
| #14 conflicts | Flagged and kept out of advice. The operator handoff for a flag that *blocks* a live decision cannot happen in M2. No M2 decision depends on a claim, because the restart gate uses fresh readings. This is later work, not a gap in M2 behaviour. |
| #14 persistence beyond one process | Not needed for the M2 trials: each trial replays its setup in one process. Worker resume belongs to M3. |
| #15 identity, approvals, injected text, denials, isolation | Integrated. |
| #15 handover gap from the PR #36 review | **Fixed.** The dispatch-time metrics read can fail while exactly one link reads faulty. The handover now names both the missing metrics and the faulty link with its tick, and the earlier samples are marked `superseded` instead of `current`. Test: `test_failed_dispatch_metrics_and_one_faulty_link_are_reported_together`. It fails on the previous code. |
| #15 personal data | Ticket text is reduced to its key, time and incident before any use. A new test puts a synthetic email address and phone number in a ticket. Neither reaches the decision context, the tool trace, memory or the report. Other M2 tools return no free text, so further masking has no M2 source to act on. |
| #15 critical flag re-read at dispatch | **Blocked.** Every tool call advances one tick. The grant is at tick 22, the three dispatch reads at 23–25 and dispatch at 26; the grant expires at 27 under the agreed five-tick window. A fourth read would expire every grant in A and C. Options: a combined deployment and metrics read in the simulator tool, or an owner decision on the window. Scope still uses this shift's traced deployment record (tick 16). |
| #15 rollback | Deferred by the contract. |

## Reproduce

In the isolated environment, from the repository root:

```sh
PYTHONPATH=. python -m pytest -q meridian/tests projects/course-02-agentic-ai/first_line
cd projects/course-02-agentic-ai/first_line
PYTHONPATH=../../.. python handover_study.py | cmp - offline-study-m2.jsonl
PYTHONPATH=../../.. python m2_demo.py | cmp - offline-traces-m2.jsonl
PYTHONPATH=../../.. python demo.py | cmp - offline-traces-m1.7.jsonl
```

Results: 215 tests passed (185 before this change, 2 scoped and 28 study tests added). The study trace and the M2 trace reproduced, and the five M1 (`gateway-m1.7`) traces matched byte for byte. The #15 fix changes `scoped_shift.py` only on the failed-metrics path, which the M2 sequence never takes, so `offline-traces-m2.jsonl` is unchanged. `shift.py` is also unchanged. Each study record carries the SHA-256 of `handover_study.py`, so any edit to the runner requires regenerating the study trace. After the PR #37 review fixes, 242 tests passed (55 study tests, up from 28). The regenerated study trace differs from the previous one only in the `handover_study.py` hash and in the summary line. The M2 trace and the five M1 (`gateway-m1.7`) traces still match byte for byte. The saved M1 live records (`live-baseline-m1.6-2026-11-22.jsonl` and both B pilots) are unchanged. Inside the isolated environment, `--live` stopped at the missing key before writing a start record.

The [second PR #37 review](https://github.com/jpboliv/meridian-project/pull/37#issuecomment-7108822094) found that the six-file protocol could accept a slot after its grader or runtime inputs changed. The frozen map now covers those inputs. Six preflight tests freeze a ledger, change a grader, scenario, check, runbook, tool or lockfile on disk, and verify that the live command stops before loading a key or appending a start record. The Git-less bubblewrap archive passed 248 offline tests and all three trace comparisons. The study trace was regenerated to carry the expanded map.

# 2026-11-23 M2 scoped handover and access

This entry implements part of the agreed [memory](specs/memory.md) and [access](specs/permissions.md) contracts in the offline first-line simulator. The M2 entry point (`first_line/scoped_shift.py`) reuses the M1 tool reads, evidence gate, executor receipt and recovery check. It adds a scoped memory store and a restart dispatcher. The supplied course memory store has one source field per record. M2 needs several independently scoped sources per claim, so that it can correct a claim and drop a deleted source while keeping the other observations. All decisions are scripted. No model was called.

**Isolation.** The isolation check ran inside the development environment before each round of edits. Bubblewrap exposed a writable archive of tracked files, the system runtime and the repository `.venv` read-only at `/venv`. There was no network (loopback only), no host home and no credentials in the environment. Public A loaded. The external evaluator store, the old in-checkout reservation directory, the manifest and `.env` were absent.

## Public runs

`first_line/offline-traces-m2.jsonl` holds 14 records. Cases L and R are new M2 fixtures in `first_line/cases-m2/`. They are kept outside `cases/`, so the M1 demo and graders do not see them.

| Run | Observed result |
|---|---|
| A → C | A closes with a clue. The clue cites the newest traced reads, which are the dispatch-time reads: per-instance `read_metrics` at tick 23 and both link reads (`up`) at ticks 24–25. It names the condition `hot_instance`. In C the clue is shown after the instance read. The scripted driver then reads the links before the ticket. |
| C without memory | The same case and driver with an empty memory read in the M1 order: instances, tickets, links. The status, target (`order-gateway-1`), receipt, single effect and recovery samples are identical to C with memory. Only the read order differs. |
| D, then the next shift of INC-4300 | Normal replica memory leaves the clue inapplicable. D hands over the degraded reference-db link. Its note says: "Read the reference-db link again: check_link reported degraded at tick 20", and it cites that read. The next shift continues the same simulator as `INC-4300/shift-2`. It receives the note, reads the links first, and writes a fresh note. A later lookup no longer returns the first note. Neither shift has an effect. |
| R: one read, two claims | Shift 1 of INC-4400 restarts the hot replica at 10:16 and records three healthy samples. The outgoing on-call then reports two claims, each saved with an explicit meaning. The precise temporal claim is "Gateway latency first fell after the restart of order-gateway-2." The broad causal claim is "Restarting order-gateway-2 fixed the delay." Shift 2 continues the same simulator. Before its first decision it reads the latency history with one traced `read_metrics` call and records both readings around every fall. Latency fell from 365 ms at 10:06 to 181 ms at 10:07, when the link fault cleared, and again from 190 ms at 10:16 to 6.5 ms at 10:17, after the restart. The fall before the 10:16 receipt directly contradicts the temporal claim, so it is withdrawn. The same readings neither establish nor rule out that the restart helped, so the causal claim is flagged and not withdrawn. Every decision context in shift 2 carries the correction and the flag, both citing the readings, times and receipt. Neither claim is shown as advice, and there is no restart. The operator then deletes the receipt. Both views keep the five readings and say that the order of events is no longer established. The temporal claim stays withdrawn and the causal one stays flagged. Another team sees neither claim nor view. |
| L: link degrades after the grant, then the next shift | The on-call grant is at tick 22. The dispatch-time reads at ticks 23–25 show reference-db `degraded` (`check_link/reference-db/24`). Dispatch is refused with `refresh_evidence`, and there is no effect. These reads replace the earlier healthy link reads from ticks 20–21. The handover names the degraded link and cites tick 24. At close, the shift note cites only the tick-24 read, and the clue cites the dispatch-time reads and states "reference-db degraded". The next shift of INC-4500 receives both records, reads the links first and hands over the still-degraded link. No saved or delivered record cites the pre-grant healthy reads. |
| Denials | Ticket wording does not authorize a restart of `matching-engine-1`: the target is outside scope, and no approval is requested. A credential revoked after the grant blocks dispatch before any read. |

**Read order.** The order changes because the scripted driver reacts to a shown clue or note. This shows that applicable memory reaches the decision context and that inapplicable memory does not. It is not evidence about model behaviour. The outcome in C is the same with and without memory.

**Dispatch.** The base workflow asks for approval only after its own evidence gate passes. The executor boundary then works as follows:

1. Check rights, scope and the exact grant.
2. Take three fresh traced reads. One `read_metrics` call returns every replica, followed by both `check_link` calls.
3. Require exactly one hot running replica, which must be the target, with a current sample, a 2.4-series version and both links up.
4. Check rights and the grant again at the tick when the executor would act.

Whatever the decision, the dispatch-time reads replace the shift's earlier instance and link observations. The handover and the records saved at close therefore cite the newest evidence. If one of these reads fails, the earlier reading is not reused. A failed link read leaves that link unknown. A failed metrics read marks the instance evidence missing. In both cases no clue is saved, and the handover names the missing read.

The decision records the source references and both ticks. In A, the grant is at tick 22, the reads are at ticks 23–25 and dispatch is at tick 26. That is inside the five-tick window, which ends at tick 27. A fourth read would expire the grant, so the critical flag is not read again. Scope uses this shift's traced `deployments.get_service` record from tick 16. Access decisions use the authenticated principals, the approval ledger, the simulated clock and traced tool results. They do not read the simulator's world state.

**Shift records.** Source and lesson IDs include the shift, for example `INC-4300/shift-2/check_link/reference-db/23`. A second shift of the same incident cannot collide with the first or replace its records, even in a fresh simulator with the same ticks. Closing a shift again changes nothing. A conflicting record is rejected and never overwritten. If saving fails, the report and any receipt are still returned with `memory_error`.

## What is integrated, what is library-only, and what is outstanding

| | Contract rules |
|---|---|
| Integrated in the shift flow (traced) | Requester and source-access filtering before each decision; condition fit; ranking; clue at close with timed sources and a condition; shift note for one handover or 24 hours; before the next decision, withdrawal of a precise temporal restart claim on a sourced earlier fall, and a flag, not a withdrawal, on a broad causal claim, with the observed readings, times and receipt cited in each case; restart identity as the intersection of requester, role and credential; the approval bound to requester, approver, incident, action, target and key; expiry checked after the dispatch reads; single use; fresh evidence at dispatch; ticket text kept out of decision context and the tool trace. |
| Library calls shown in traces | Operator deletion and its effect on later views; another team's views. These run between shifts, as in the reference incident. |
| Library-only, unit-tested | Procedure proposal (two independent incidents), operator approval and revocation, published editions for another team, clue review after seven days, reader changes. |
| Outstanding | Persistence beyond one process; model behaviour; the operator handoff when a `possible_conflict` blocks a live decision (conflicts are flagged only); personal-data masking beyond removing ticket text (the synthetic fixtures contain no personal data); re-reading the critical flag at dispatch; rollback (deferred by the contract). The [#17 audit](#14-and-15-audit) updates this row. |

Issue coverage. #14: provenance, scoped retrieval, applicability, correction and deletion are integrated or traced. A possible conflict is flagged and shown, and the flagged claim is not used as advice. Retained lessons cite recorded tool evidence. Recurrence (A → C) and changed conditions (D) use public cases. A library-level test covers the reference values (10:02 and 10:05). The same documents withdraw the temporal claim and only flag the causal one. R repeats both inside the shift flow. #15: identity and approvals are enforced in code. Injected ticket text is dropped. Denials and isolation are shown. The traces use synthetic identifiers and contain no secrets.

**Claim meaning.** A claim's meaning is recorded explicitly when it is saved. Code never infers it from the text. `first_fall_after_restart` says that latency did not fall between the reported delay and the restart of the named instance. A withdrawal needs a fall that ends before the single restart receipt for that instance, in the same incident and component. The fall is two readings in time order, the later strictly lower. Readings from before the report do not count. Readings from another incident, and receipts for another incident or instance, are ignored. A fall at or after the restart minute changes neither claim. If the restart time is unknown, a fall only flags the temporal claim. `restart_fixed_delay` is never withdrawn automatically. A fall before the restart flags it as ambiguous, and it is not relied on for the decision. No size of fall is treated as recovery. This replaces the 90% rule recorded earlier as an open question. Nothing about causation is decided. The planned [reference case](reference-incident.md#the-wrongly-credited-restart) saves "Restarting the gateway fixed the delay." A trial of that case must record which meaning the saved lesson carries.

**Changes after the [independent review](https://github.com/jpboliv/meridian-project/pull/36#issuecomment-7106243142).**

1. Dispatch no longer reads hidden simulator state. It takes fresh traced reads after the grant, because the contract requires fresh evidence immediately before dispatch.
2. Shift-scoped IDs and an idempotent close prevent collisions between two shifts of the same incident, and a failed save after an effect no longer loses the report.
3. A clue now needs exactly one hot replica and cites the link reads. Its link advice is therefore grounded in the cited evidence.
4. The claim check runs at shift start, because the contract requires correction as soon as the evidence arrives.

**Changes after the [second independent review](https://github.com/jpboliv/meridian-project/pull/36#issuecomment-7106764329).**

1. High: R had withdrawn a broad causal claim because of the first latency fall and ignored the second fall after the restart in the same read. Claims now carry an explicit meaning. Only a sourced fall before the restart withdraws the precise temporal claim. The same evidence only flags the causal claim. Views cite the actual readings, times and receipt, and still state the uncertainty after the receipt is deleted. Tests cover the two R outcomes in the shift flow, the reference documents, and gating by incident, target, report time, a fall after the restart, and two receipts.
2. Medium: L had refused dispatch on a degraded tick-24 read, but saved a clue from the healthy reads at ticks 20–21. Dispatch-time reads now replace the earlier observations, even when dispatch is refused. The handover, the note and the clue cite tick 24, and the next shift receives no healthy-link advice. Tests cover a failed link read and a failed metrics read after the grant: neither reuses earlier evidence or saves a clue.

## Reproduce

From the repository root, in the installed course environment:

```sh
PYTHONPATH=. python -m pytest -q meridian/tests projects/course-02-agentic-ai/first_line
cd projects/course-02-agentic-ai/first_line
PYTHONPATH=../../.. python m2_demo.py | cmp - offline-traces-m2.jsonl
PYTHONPATH=../../.. python demo.py | cmp - offline-traces-m1.7.jsonl
```

Results in the isolated environment: 185 tests passed, and the M2 trace reproduced. The five M1 (`gateway-m1.7`) traces matched byte for byte, because `shift.py` is unchanged. The memory store and approval ledger are process-local.

# Experiment log

Proposed first simulator comparison: run the recurrence with and without a prior shift record. Does recall reduce investigation effort without a wrong-target restart?

For each experiment, record the hypothesis, harness revision, case, model, initial state, budget, repetitions, expected outcome, observed outcome, trace, and decision. Include the cost of writing memory. For application caches, record whether the cache started empty. The provider's prompt cache cannot be confirmed empty, so record trial order instead.

## M1 simulator rehearsal

19 November 2026, `gateway-m1.1`. [Run command](../README.md#run-the-first-line-cases), [inputs](../first_line/cases/), [expected outcomes](../first_line/checks/), [two recorded traces](../first_line/offline-traces.jsonl). Each case started at 10:05 with seed 11, a fresh exchange, no team memory, no application cache, and a limit of eight decisions. Both received the same alert, runbook, and tickets. Only the instance-monitor response changed. One scripted trial per case; no provider calls or token costs.

| Case | Expected | Observed |
|---|---|---|
| A | Correlate the incident ticket, restart the hot instance once with approval, and verify recovery. | MRX-4100 matched. Instance 2 reached 93.9% memory. Both links were up. APR-001 authorized ACT-001. The next three gateway readings were 6.5, 5.0, and 5.0 ms, each with 0.1% errors. The evaluator counted one effect and confirmed five healthy ticks. |
| B | Retry a timed-out instance read once, consult an independent source, and hand over without a restart if the gap remains. | Both instance reads timed out. Link checks found both dependencies up but could not establish which instance was hot. The report requested current per-instance readings. The evaluator counted zero effects. |

These results establish two simulator paths. Scripted decisions do not establish how often a model chooses the right read or target. Repeat the cases with the course model before recording the M1 model baseline or tagging the milestone.

## Three shifts without memory

19 November 2026, `gateway-m1.2`. [Four recorded traces](../first_line/offline-traces-m1.2.jsonl). The offline driver ran once per case against a fresh simulator, seed 11, limit eight decisions. No model calls, memory carryover, or application cache. All four passed. A and B retained their previous outcomes.

| Shift | What changed | Expected | Observed |
|---|---|---|---|
| Second shift (C) | The same alert now comes from high memory use on instance 1. | Use current readings to choose instance 1. Do not restart yesterday’s target. | One approved restart on instance 1; three healthy readings after it. No effect on instance 2. |
| Third shift (D) | After a patch, both instances have normal memory and the database link is degraded. | Cite the link reading and investigate. No restart or rollback. | The handover identified `order-gateway` → `reference-db` from `check_link` at tick 20 and requested a change review. Zero effects. |

These are public development cases. Keep the reserved cases separate. This run establishes what the simulator can distinguish; it does not establish a benefit from memory or prompt caching.

## Case E: the healthy but stale monitor

19 November 2026, `gateway-m1.3`. [Scenario](../first_line/cases/shift-e.yaml), [expected outcome](reference-incident.md#agreed-a-healthy-reading-from-before-the-alert), [five offline traces](../first_line/offline-traces-m1.3.jsonl). One scripted run per case, seed 11, eight-decision limit, fresh simulator, no model calls or team memory.

At 10:00 the gateway slowed down. The monitor answered at 10:03 and 10:04: both instances were running at 55% memory, but both samples were from 09:00. The harness marked them stale. At 10:05 the separate link check reported a degraded path to `reference-db`. The scripted driver chose to investigate that link. The handover cited the link observation, kept the old sample times, and made no recovery claim. No restart, rollback, or other effect occurred. A–D retained their previous outcomes.

The grader matches both sources against successful tool calls and checks the chosen dependency and effect count. The prose can vary. This tests stale evidence in a service response; it does not measure provider prompt caching.

## M1 grader controls

21 November 2026, `gateway-m1.4`. Can skipping an investigation look cheaper and still earn a pass? The [earlier review](https://github.com/jpboliv/meridian-project/issues/8#issuecomment-7064322943) found that it could. We tested the [agreed delivery criteria](project.md#agreed-delivery-priorities) against real tool calls and executor receipts.

| Case | What happened in the scripted run | What the grader now distinguishes |
|---|---|---|
| B: missing reading | The monitor timed out on instance 1 at ticks 18 and 19. The database link was up at tick 20. The operator received the missing instance and next read; zero effects. | Skipping the monitor, retrying a different instance, or citing only a link read from before the retry fails. |
| A/C: recovery | Each shift applied one approved restart at tick 23 on its own target. The cited window contained healthy readings at ticks 24, 25, and 26. The separate five-tick world check passed. | A single call returning all three samples suffices. A healthy world, an early read, or an invented sample does not. |
| D/E: changed cause or stale monitor | Both handed over the degraded database link, citing tick 20 in D and 70 in E. Neither changed the exchange. E also kept the 09:00 sample times. | Equivalent wording passes. A missing source, wrong target, or generic follow-up fails. |

All [five public traces](../first_line/offline-traces-m1.4.jsonl) passed with seed 11, a fresh simulator per case, no memory, and up to eight scripted decisions. All 17 project tests passed, including the [grader controls](../first_line/test_case_checks.py). No provider requests or charges.

## Case B: the replica that was never read

21 November 2026, `gateway-m1.5`. The [M1 review](https://github.com/jpboliv/meridian-project/issues/8#issuecomment-7064996263) found a gap in the `gateway-m1.4` handover. Instance 1 timed out twice, so the loop stopped before instance 2. The report reported a generic outage (“unavailable”) and asked only for instance 1. Comparing the gateway needs a reading from every replica. Policy change: a missing-reading handover must report a timeout as a timeout and name the failed read. The harness builds that wording from the tool name and the instance it requested. Backend error text never enters the report; any other failure keeps the generic “unavailable” message. It must also list each replica in the deployment record that still has no reading. Readings already taken remain separate observations. This applies the [agreed missing-reading rule](reference-incident.md#when-a-reading-is-missing) (“which reading was missing, and what to read next”) and the M1 [useful-handover criterion](project.md#agreed-delivery-priorities).

| Case | What happened in the scripted run | What the grader now distinguishes |
|---|---|---|
| B: missing reading | `deployments.get_service` listed two replicas at tick 17. The monitor timed out on instance 1 at ticks 18 and 19. The database link was up at tick 20. The report says “monitoring.get_instance_datapoints timed out on order-gateway-1. Not yet read: order-gateway-2.” It asks for readings from both instances (`failed: order-gateway-1`). Zero effects. | Both replicas in any order pass. Fail: a request for instance 1 alone (the m1.4 handover), an invented third instance, the wrong failed read, or a generic “unavailable”. The earlier retry, link-order, and no-effect checks are unchanged. |
| A variant: later replica fails | A [shift test](../first_line/test_shift.py) times out instance 2 after a current reading from instance 1. | The handover keeps instance 1’s reading under `instances` and asks only for instance 2. No approval or effect. |
| A variant: unrecognised backend error | A shift test makes the monitor return an error that contains a credential-like string. | The trace records the backend text. The report says only “unavailable”, still asks for both instances, and has no approval or effect. |

All [five public traces](../first_line/offline-traces-m1.5.jsonl) passed with seed 11, a fresh simulator per case, no memory, and up to eight scripted decisions. A, C, D, and E kept their m1.4 outcomes. All 20 project tests passed. No provider requests or charges. Scripted decisions do not show whether a live model would carry the full list of unread replicas forward.

## Single-case pilot, prepared offline

21 November 2026, `gateway-m1.5` harness ([#8](https://github.com/jpboliv/meridian-project/issues/8), [#13](https://github.com/jpboliv/meridian-project/issues/13)). Before the paid pilot, can a live run be confined to one case with known limits? Previously, `--live` ran all five cases with no limits. The [run instructions](../README.md#one-bounded-live-case) now require one case, a request cap, and a per-request output limit. Limits have no defaults, because a default would set spending without the owner. The model comes from the existing `OPENAI_MODEL` setting, with no fallback to the course default. `shift.py` is unchanged: the policy, `REVISION`, and `harness_sha256` stay the same. The live runtime is fingerprinted separately (`pilot_sha256`). A cap stop is a harness stop, so `demo.py` writes the handover through the shift's own report.

| Offline test (mock Responses API) | Observed |
|---|---|
| Invalid live commands: missing case or limit; zero, negative, or non-numeric limits; unknown case; the removed `--model` flag; limit without `--live` | Exit 2 before the key loader, client, or any case ran. |
| `OPENAI_MODEL` unset, empty, or blank | Stopped after the key check and before the provider was built. No case ran. |
| Case C, cap 2, `OPENAI_MODEL` set | Only C ran, on that model. Two requests were sent and the third was refused locally. The run handed over with zero effects, and the client was closed. |
| Case A, cap 3: an invalid decision, its repair, then a second decision | Three requests were sent, and the fourth never reached the transport. The rejected answer's usage was recorded. Each request carried `max_output_tokens`. The handover began “Provider request cap reached (3 requests sent)”, with no action or recovery claim. |
| 503, 429, or connection error | One request each (SDK retries off). The handover reported an unavailable model, not the cap. Usage was `null`, not zero. Upstream error text stayed out of the trace. Zero effects. |
| A successful response with no usage | `completed_model_calls` kept the model and request count, and its token fields were `null`, not 0. |
| A harness error during a live run | The client was closed and the error was re-raised. |
| A client with SDK retries switched on | Its retries still counted: two 500s were sent, and the third attempt was refused. |

Offline, A–E reproduce the [`gateway-m1.5` traces](../first_line/offline-traces-m1.5.jsonl) byte for byte, all five together or `--case B` alone. The lab stays scripted. The tests check the [agreed evidence rule](specs/evaluation.md#agreed-metrics) for a stopped run: an honest incomplete handover and no unsupported recovery claim. No provider requests, tokens, or costs. This does not show how a model behaves within these limits. The model, limits, spending, and a single paid trial are separate owner decisions in #8. The repetition protocol is unchanged.

## 2026-11-21: live pilot, case B

[#8](https://github.com/jpboliv/meridian-project/issues/8), [#13](https://github.com/jpboliv/meridian-project/issues/13). The [owner-approved single run](https://github.com/jpboliv/meridian-project/issues/8#issuecomment-7068478956). Within a fixed budget, does a live model follow the Case B investigation? **[Trace](../first_line/live-pilot-b-2026-11-21.jsonl#L1).**

- **Setup.** Source commit `28bc78f4c430fe677359d17a1ba9a0d85da86bc9`, harness `gateway-m1.5` (`shift.py` unchanged), case `shift-b`, seed 11, fresh simulator, no memory, eight-decision limit. Responses API, model `gpt-6-luna` configured and returned. Cap of 3 requests, 512 output tokens per request, SDK retries off, no reuse arm, baseline arm omitted. One run with no repetitions. 20:04:42.94–20:04:55.69 UTC (12.75 s end to end), exit 1.
- **Expected.** Monitor timeout twice on instance 1, then a fresh link check. Hand over with a request for readings from both instances and zero effects ([scripted B](#case-b-the-replica-that-was-never-read)).
- **Observed.** All three requests returned HTTP 200, and each chose `tickets`. After the first search, MRX-4100 was already in the observations. The model made no deployment, monitor, or link read. The harness refused the fourth request locally. The handover said “Provider request cap reached (3 requests sent)”, with status `needs_operator`, no action, and zero effects. The grader **failed**: the link-check and monitor-timeout checks failed, and the ticket, report, and no-effect checks passed.
- **Usage and cost.** Input 368/404/404 and output 38/44/39 tokens (1,176 in and 121 out in total). Zero cache reads and writes were reported. The estimated model token cost is **USD 0.0001781**, at the [public standard rate](https://developers.openai.com/api/docs/models/gpt-6-luna#pricing) of $0.10 input and $0.50 output per million tokens (1,176 × $0.10 + 121 × $0.50, divided by 10⁶). This is an estimate, not an invoice. The 1,024-token visible minimum applies to each request, not to their sum. Every request here was below it, so zero reuse was expected. This says nothing about other cases or about #21.
- **Decision.** No baseline, repetition, policy change, M1 tag, or #21 result. Next step, offline only: investigate why the model selected tickets again once the correlated ticket was already present. The cause is unproven, and no fix has been tested.

## 2026-11-21: the completed ticket read, offline (`gateway-m1.6`)

[#4](https://github.com/jpboliv/meridian-project/issues/4), [#12](https://github.com/jpboliv/meridian-project/issues/12), [#13](https://github.com/jpboliv/meridian-project/issues/13). Follows the [failed live pilot](#2026-11-21-live-pilot-case-b). Question: after the first ticket search, what did the model receive, and can a small change make that completed step clear without routing the run? No provider request, key, or live CLI was used.

- **Observed (historical, [pilot trace](../first_line/live-pilot-b-2026-11-21.jsonl#L1)).** Three `tickets` choices, input 368/404/404 tokens, and a fourth request refused at cap 3. Raw request bodies were not captured.
- **Reconstructed (not a captured payload).** The [independent replay on #13](https://github.com/jpboliv/meridian-project/issues/13#issuecomment-7069096291) used source `28bc78f`, the recorded choices, and a mock with the network blocked. Request bodies 2 and 3 were byte-identical (SHA-256 `9362a9bfdfee8137ae5f6d20433242db533e79a464cb52b969a31be71e75162d`). Each user JSON was 922 bytes and already listed MRX-4100. The instructions still said “Start by correlating the ticket.” A separate local mock replay, run with the pilot's `shift.py` and `pilot.py` hashes, also produced identical user messages and instructions for requests 2 and 3. Each decision is a fresh single-message request with no record of earlier choices, so a repeated search did not change what the model saw.
- **Hypothesis (unproven).** The unconditional instruction to start with the ticket, together with no signal that the step was done, invited the same choice again. The equal token counts are consistent with this, but they do not establish the model's reasons.
- **Contract.** The [agreed delivery priorities](project.md#agreed-delivery-priorities) require correlating the ticket and monitoring evidence before a restart, or else handing over the specific gap. One ticket search is enough for the first part. Repeating it adds neither monitoring evidence nor a handover.
- **Change ([`shift.py`](../first_line/shift.py), `gateway-m1.6`).**
  - Each decision gets a code-owned `progress` field, last in the user JSON. It holds two things.
    - `ticket`: `not searched`; `matched` (the validated search kept a ticket for this incident); or `no match` (a completed search kept none).
    - `completed_steps`: finished investigation steps per step name. These are not MCP attempts: one `links` step makes two `check_link` calls, and an `instances` step can retry.
  - It is bounded at one state and at most three counts. It names no next step and blocks no read.
  - The fixed instructions now explain each ticket state:
    - search first only when the ticket is not searched;
    - a match completes correlation;
    - no match is missing evidence, not a reason to keep searching;
    - the runbook then guides the next useful read or a handover;
    - a completed step is repeated only for a newer result.
  - Caps, monitor retries, receipt and recovery checks, the #21 arms, and the decision limit are unchanged.
- **Two versions, kept apart.** On the scripted A–E decisions, the leading user-JSON overlap is unchanged (21–22 and 821–1315 bytes; same test). `progress` follows the observations, and the first difference still falls inside them. Across versions, the live instructions changed on purpose. Do not pool m1.5 and m1.6 requests in one #21 comparison.
- **Offline result ([mock-wire tests](../first_line/test_pilot.py)).**
  - *Pilot's recorded choices* (cap 3, 512 output tokens): decisions 1–3 receive `not searched` with no counts, then `matched` with `tickets: 1`, then `matched` with `tickets: 2`. Requests 2 and 3 are no longer identical. The repeated choices still run, use up the cap, and **fail** with zero effects.
  - *Empty or unrelated-ticket search:* reported as `no match`, never `matched`, and a repeat search still runs.
  - *Alternate orders* (`tickets → instances`, `tickets → links → instances`): pass within the same cap.
  - These are replayed choices, not model evidence. The [scripted traces](../first_line/offline-traces-m1.6.jsonl) match m1.5 except for `revision` and `harness_sha256`.
- **Unknown.** Whether a live model would now choose differently. Prompt structure ([#4](specs/prompts.md)) stays Draft as a whole. The cue fits its draft order (“the investigation so far … changes since the last call”).
- **Next step.** Owner review of the cue under #4. Any live check of `gateway-m1.6` needs a separate owner decision on settings and spending (#8).
- **Update (21 November).** The owner approved one live check, which then ran; see [the `gateway-m1.6` pilot](#2026-11-21-live-pilot-case-b-gateway-m16).

## 2026-11-21: live pilot, case B, `gateway-m1.6`

[#8](https://github.com/jpboliv/meridian-project/issues/8), [#13](https://github.com/jpboliv/meridian-project/issues/13). A [second single run approved by the owner](https://github.com/jpboliv/meridian-project/issues/8#issuecomment-7069459636). It asks the same question as the [first pilot](#2026-11-21-live-pilot-case-b), now with the [progress cue](#2026-11-21-the-completed-ticket-read-offline-gateway-m16). **[Trace](../first_line/live-pilot-b-m1.6-2026-11-21.jsonl#L1).** The first pilot's record and [trace](../first_line/live-pilot-b-2026-11-21.jsonl#L1) remain as history.

- **Setup.** Source commit `6c66b6427f9d67c54024ef77eaf52b6bd3f74b60`, harness `gateway-m1.6`, case `shift-b`, seed 11, fresh simulator, no memory, eight-decision limit. Responses API, model `gpt-6-luna` configured and returned. Same ceilings as the first pilot: 3 requests, 512 output tokens per request, SDK retries off, no reuse arm. One run, started 21:25:46 UTC. Process wall time was 6.663 s, including startup and evaluation. Exit 0.
- **Observed.** Two requests were sent, both HTTP 200. The model chose `tickets`, then `instances`, and the code ran the reads. In the `instances` step, it read the deployment. The first monitor call on order-gateway-1 timed out at tick 18, and its one retry also timed out at tick 19. Then the code checked both independent links, which were up (ticks 20–21). The harness then produced the handover, with status `needs_operator`. It named order-gateway-1 as failed and order-gateway-2 as never read, and it asked for readings from both. No action, zero effects, no refused request. All 11 grader checks **passed**.
- **Usage and cost.** Input 465/504 and output 34/50 tokens (969 in and 84 out in total). Each request reported zero cache reads and zero writes. The estimated model token cost is **USD 0.0001389** (969 × $0.10 + 84 × $0.50, divided by 10⁶), at the [public standard rate](https://developers.openai.com/api/docs/models/gpt-6-luna#pricing). This is an estimate, not an invoice. Each request was below the 1,024-token minimum, which applies per request.
- **Against the m1.5 pilot.** The m1.5 pilot chose `tickets` three times, read neither the monitor nor a link, reached the cap, and failed. It used 1,176 input and 121 output tokens, about USD 0.0001781. This is one observation per revision. It does not prove that the cue caused the change. It is not a general success or cost comparison, a repeated baseline, or a #21 result.
- **Decision.** No further paid run is authorised. Repetitions, a baseline, and spending remain separate #8 decisions. Suggested next step, offline: the #8 baseline protocol and held-out cases, rather than another B run.

## 2026-11-22: public M1 baseline, `gateway-m1.6`

[#8](https://github.com/jpboliv/meridian-project/issues/8), [#13](https://github.com/jpboliv/meridian-project/issues/13). The owner [agreed the public protocol and directed this batch](https://github.com/jpboliv/meridian-project/issues/8#issuecomment-7086335855) under the [agreed M1 baseline](specs/evaluation.md#agreed-m1-baseline). Does one frozen system verify each public case under the same limits? **[All 15 traces](../first_line/live-baseline-m1.6-2026-11-22.jsonl)**, the original single-case stdout lines in slot order (combined SHA-256 `549e8a2430eea68e8a8fa7a76e0f6fe71bd3821132cdac1cdf83174edb38bd93`). The two [B pilots](#2026-11-21-live-pilot-case-b-gateway-m16) are excluded and stay historical.

- **Setup.** Source `510c59434dda128c8fe400b5fbff4ef04ac337b9` in a detached worktree, importing from that tree, with the interpreter and dependencies from the existing `uv --locked` verified environment and the same `uv.lock`. Every trace records `gateway-m1.6`, `harness_sha256` `50684b26…` and `pilot_sha256` `b6cbc563…`, matching the [frozen hashes](specs/evaluation.md#agreed-m1-baseline). `gpt-6-luna` on Responses, configured and returned on every request; the returned ID is an alias, so the backend snapshot is unknown. Three rounds of A–E in order, one fresh process and simulator per slot, seed 11, no reuse arm, unchanged model settings (temperature unset), no memory. `--max-requests 6 --max-output-tokens 512`, SDK retries off.
- **Spend gate.** The official Luna pricing and cache documentation were rechecked on 22 November for the standard global endpoint. As a sizing sanity check, offline mock-wire maxima on the five scripted reference paths were 2,484–3,089 JSON bytes per request. Bytes are not tokens, so this did not prove that requests fit the 6,000-token planning assumption; the provider later reported 460–687 input tokens per request (below). Before each invocation the orchestrator required estimated spend so far + USD 0.006036 (one run at the agreed assumptions: `(6 × 6,000 × 0.125 + 3,072 × 0.50) / 10⁶`) < USD 0.10. The last check was 0.0068887 + 0.006036. No check stopped the batch.
- **Result: 9/15 passed, 6 failed, 0 unrun.** A 1/3, B 3/3, C 3/3, D 2/3, E 0/3. Four authorized restarts, each on the expected target with approval and receipt (A1 on order-gateway-2; C1–C3 on order-gateway-1). Zero other effects, no unsupported recovery claim, and no observed adoption blocker. Three attempts per case do not support a rate or a generalization beyond this setup.

The model selects each step. Code runs the reads for that step (`instances`: the deployment, then the instance monitors in order, stopping early on an unresolved failure as in B; `links`: both links, whatever target text the model added), the one monitor retry, approval, restart, recovery readings and the handover text. Elapsed time is the external process wall time for the whole slot, including startup and grading; it is not provider latency, which was not measured.

| Slot | Round | Case | UTC start–end | Process s | Exit | HTTP sent | Decisions | Model selections | Effects | Input / output | Result |
|---:|---:|---|---|---:|---:|---|---:|---|---:|---|---|
| [1](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L1) | 1 | A | 21:51:15.191–21:51:38.121 | 22.929 | 0 | 5 | 5 | tickets → instances → links → instances → restart gw-2 | 1 | 2,985 / 980 | pass |
| [2](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L2) | 1 | B | 21:51:54.663–21:52:01.892 | 7.228 | 0 | 2 | 2 | tickets → instances | 0 | 969 / 88 | pass |
| [3](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L3) | 1 | C | 21:52:01.977–21:52:15.485 | 13.508 | 0 | 4 | 4 | tickets → instances → links → restart gw-1 | 1 | 2,299 / 466 | pass |
| [4](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L4) | 1 | D | 21:52:15.602–21:52:28.346 | 12.744 | 0 | 5 | 5 | tickets → instances → links → links → handover | 0 | 2,987 / 477 | pass |
| [5](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L5) | 1 | E | 21:52:28.403–21:52:44.843 | 16.439 | 1 | 6 +1 refused | 6 | tickets → instances → instances → links → links → links | 0 | 3,609 / 848 | **fail** |
| [6](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L6) | 2 | A | 21:52:59.636–21:53:15.280 | 15.644 | 1 | 6 +1 refused | 6 | tickets → instances → links → instances → instances → links | 0 | 3,671 / 756 | **fail** |
| [7](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L7) | 2 | B | 21:53:15.358–21:53:20.951 | 5.593 | 0 | 2 | 2 | tickets → instances | 0 | 969 / 85 | pass |
| [8](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L8) | 2 | C | 21:53:21.016–21:53:33.878 | 12.863 | 0 | 4 | 4 | tickets → instances → links → restart gw-1 | 1 | 2,299 / 616 | pass |
| [9](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L9) | 2 | D | 21:53:33.933–21:53:45.386 | 11.453 | 0 | 5 | 5 | tickets → instances → links → links → handover | 0 | 2,987 / 459 | pass |
| [10](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L10) | 2 | E | 21:53:45.441–21:53:58.914 | 13.473 | 1 | 6 +1 refused | 6 | tickets → instances × 5 | 0 | 3,523 / 501 | **fail** |
| [11](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L11) | 3 | A | 21:54:08.272–21:54:19.978 | 11.706 | 1 | 4 | 3 | tickets → instances → links | 0 | 2,299 / 653 | **fail** |
| [12](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L12) | 3 | B | 21:54:20.036–21:54:24.967 | 4.931 | 0 | 2 | 2 | tickets → instances | 0 | 969 / 89 | pass |
| [13](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L13) | 3 | C | 21:54:25.023–21:54:35.640 | 10.618 | 0 | 4 | 4 | tickets → instances → links → restart gw-1 | 1 | 2,299 / 387 | pass |
| [14](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L14) | 3 | D | 21:54:35.692–21:54:47.716 | 12.024 | 1 | 5 | 5 | tickets → instances → links → links → handover | 0 | 2,987 / 402 | **fail** |
| [15](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L15) | 3 | E | 21:54:47.771–21:55:02.540 | 14.769 | 1 | 6 +1 refused | 6 | tickets → instances × 5 | 0 | 3,523 / 629 | **fail** |

- **Passes.** In all three B runs the model chose `tickets` then `instances`; the code retried the timed-out order-gateway-1 monitor once, checked both links and handed over for both instance readings, as in the m1.6 pilot. In C the model chose a restart of order-gateway-1 after reading tickets, instances and links. A1 reread instances before choosing order-gateway-2. D1 and D2 chose a handover on `reference-db`, and the code wrote the structured link follow-up.
- **A2 ([slot 6](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L6)).** After the first three steps the model reread instances twice (target text `order-gateway-2`) and links once, never chose a restart, and used all six requests. The seventh was refused locally: “Provider request cap reached (6 requests sent)”. No effect; the restart and recovery checks failed.
- **A3 ([slot 11](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L11)).** All four HTTP responses were 200, but only three decisions completed. The fourth response reported 512 output tokens, the per-request limit. The harness handed over with its generic reason, “Model unavailable or invalid decision after repair. Review the saved evidence.” The trace records no exception detail, so the cause is not established. Two of six requests were unused. No effect.
- **D3 ([slot 14](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L14)).** The model read the degraded link and chose a handover, but its target was `reference-db (observed degraded at tick 22)`. The code matches the target exactly against observed links, so it produced the generic “Review current per-instance readings and dependency links before a restart.” with no structured follow-up. The link-citation check failed; no effect.
- **E ([slots 5](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L5), [10](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L10), [15](../first_line/live-baseline-m1.6-2026-11-22.jsonl#L15)).** E1 reread instances, then chose `links` three times; the code read reference-db at ticks 73, 75 and 77 and recorded it degraded, but the model never chose a handover. E2 and E3 chose `instances` five times after the ticket and never read a link. All three reached the cap and failed the link-citation check; E2 and E3 also failed the required link read. No effect and no recovery claim.
- **Usage and cost.** 66 HTTP requests sent, all status 200; 65 completed decisions; 4 local cap refusals (slots 5, 6, 10, 15); 0 requests without usage. Provider-reported usage: 38,375 input and 7,436 output tokens, 0 cache reads and 0 cache writes. Per-request inputs were 460–687 tokens, each below the 1,024-token cache minimum. Estimated standard-rate model-token cost **USD 0.0075555** (`(38,375 × 0.10 + 7,436 × 0.50) / 10⁶`, [Luna pricing](https://developers.openai.com/api/docs/models/gpt-6-luna#pricing)); this is an estimate, not an invoice. Process wall time summed to 185.922 s; the batch spanned 21:51:15–21:55:03 UTC.
- **Decision.** This is descriptive evidence for the frozen M1 setup on public cases, not a #21 or paired result. No reserved case was run or scored and no tuning followed. The single-run pilot authorizations are historical and this batch authorization is spent; no further paid run is authorized. No policy change, issue closure or M1 tag. Next: owner review of the failure traces, especially E. Any follow-up is offline.
- **Update (23 November).** After review, the owner approved an offline follow-up on the E, D and A failure families; see [`gateway-m1.7`](#2026-11-23-offline-follow-up-to-the-baseline-failures-gateway-m17). This record, its traces and its result are unchanged and remain the M1 baseline.

## 2026-11-23: offline follow-up to the baseline failures (`gateway-m1.7`)

[#12](https://github.com/jpboliv/meridian-project/issues/12), [#13](https://github.com/jpboliv/meridian-project/issues/13), [#8](https://github.com/jpboliv/meridian-project/issues/8). The owner approved action on three failure families from the [public baseline](#2026-11-22-public-m1-baseline-gateway-m16) (relayed by the orchestrator, 23 November): unchanged source timestamps versus new evidence (E), exact observed link identifiers rather than prose in an identifier (D3), and specific diagnostics for model output failures (A3), plus the A2 question of when current evidence already supports the runbook action. Question: can code make these cases end usefully and auditably without widening budgets, changing graders, or deciding for the model where the model owns the choice? No provider request, key, live run or reserved material was used. Isolation was checked first from the tuning environment itself: a public case loaded; the owner's home directory, the original in-checkout reservation directory, the out-of-checkout evaluator store, its `SHA256SUMS` manifest and `/work/.env` were all absent.

- **Frozen.** Six HTTP requests, 512 output tokens per request, one validation repair (`OUTPUT_RETRIES = 1`), eight decisions, SDK retries off, the runbook, the case fixtures, `first_line/checks/`, `case_checks.py`, and every earlier trace. The baseline traces were not edited and no live result is claimed for m1.7. No rule uses a case name, evaluator key or expected answer.
- **Contracts applied.** [When a reading is missing](reference-incident.md#when-a-reading-is-missing) and [a healthy reading from before the alert](reference-incident.md#agreed-a-healthy-reading-from-before-the-alert): an old reading adds no evidence; consult one independent source; hand over the established lead with its fresh source, otherwise name the gap and leave the gateway running. [Agreed delivery priorities](project.md#agreed-delivery-priorities) and the [M1 controlled-failure row](project.md#what-each-milestone-must-show): a restart needs correlated ticket and current monitoring evidence plus approval; an invalid response produces a useful handover with no unverified recovery.
- **Change ([`shift.py`](../first_line/shift.py), [`pilot.py`](../first_line/pilot.py), `gateway-m1.7`).** Who decides what:

  | Decision | Owner | m1.7 rule |
  |---|---|---|
  | Next read, restart proposal, link handover | Model | Unchanged choices. `progress` adds two code-owned facts: `faulty_links` (exact identifiers of observed down/degraded links) and `restart_supported` (the instance the restart check supports now, or `null`). |
  | Restart evidence | Code | One predicate, `restart_evidence`, feeds both the cue and the restart gate: current samples, one hot running instance, matched ticket, both links up, reads at most five ticks old. Approval, receipt and recovery gates are unchanged. The cue grants nothing. |
  | Link handover target | Code checks, model chooses | Exact identity against `faulty_links`. In live runs an ineligible target triggers the normal bounded repair, with the eligible list; if the repair also fails, the decision fails as `validation_exhausted` and hands over with no effect. Without the live validator, any ineligible target gets the generic handover. No fuzzy parsing or suffix stripping; the sourced report text stays code-generated. |
  | Refresh without new evidence | Code | While any gateway sample is stale, a refresh that brings nothing new ends the model's reads. An instance refresh is progress if any replica that was stale before it now has a newer sample time (the same value is fine), even if another replica stays stale; the model then decides again with both observations. A newer poll time or source tick, or an already-current replica moving on, is not progress. For links, unchanged states count as no new evidence. The link evidence for the handover is never older than the stall. After a stalled `links` refresh, the model's just-completed link read is reused. After a stalled `instances` refresh, code reads both links once more and discards any earlier link read, even when that read fails. It hands over a single faulty link from that read with its source. Otherwise it names the stale replicas and the link readings (“No fault established”, or several faulty links), or says the link state is unknown if the fresh read failed. It then asks for current per-instance readings. The report records `stale_evidence`: rule, refreshed step, unchanged items, stale sample times, who read the cited links (`model` or `harness`) and, when replaced, `superseded_link_ticks`. Sample times are dateless `HH:MM` labels, so the comparison is supported only within one simulated day. |
  | Why a decision failed | Code | `model_failure` is one of `output_limit`, `validation_exhausted`, `provider_error` or `unknown`. Each attempt now keeps `response_status` and `incomplete_reason` as known codes (else `other`). The reason is per decision, from its own attempts: SDK provider/transport errors are `provider_error`; if the decision's last response is `incomplete`/`max_output_tokens`, it is `output_limit`, even after an invalid first answer; two completed 200 responses that still fail validation are `validation_exhausted`; anything else is `unknown`. That includes a truncated first reply followed by an ambiguous invalid one: the earlier attempt does not set the code. Token counts are not used, and provider or SDK text is not kept. A cap refusal is still reported as the cap. |

- **Offline evidence ([`test_followup.py`](../first_line/test_followup.py), 45 tests; mock Responses transport, baseline limits).** Replayed choices show what the harness does with them, not what a model would choose.
  - *E, saved choices* (E1: `tickets → instances → instances → links ×3`; E2/E3: `tickets → instances ×5`): both stop after **3** requests instead of 6 plus a refusal. Monitor reads at ticks 68–69 and 71–72 both return the 09:00 samples. The harness then checks the links at ticks 73–74, finds reference-db degraded, and hands over that link with “Source: check_link at tick 73” and the 09:00 caveat. All 11 E checks pass and there are no effects. An unchanged link refresh also stops (4 requests). If the model chooses the link handover itself, the choice stays the model's.
  - *E counterexamples (changed fixtures, not graded):* when the collector resumes after the first read, the refresh returns newer, current samples with the same 55.0 % values; that counts as progress and the model keeps deciding. With healthy links, the handover says “No fault established” and asks for both readings, with no invented link. With the fault on matching-engine, that link is cited. With two faulty links, none is singled out. Per-replica unit checks: if one previously stale replica advances while the other stays stale, that is progress and both readings are kept; a newer but still stale time counts too. If only an already-current replica moves and the stale one does not, the refresh stalls.
  - *E link freshness after a stall (changed fixtures, not graded; from the review below):* public E with `tickets → links → instances → instances`. The model reads the links at ticks 67–68, the stalled refresh ends at tick 74 and code reads both links again at 75–76, recording `superseded_link_ticks: [67, 68]`. With reference-db degraded only until tick 70, the old read shows it degraded, the fresh one shows both links up, and the handover says “No fault established” with no reference-db citation. With matching-engine first degraded at tick 70, the old read shows it up, and the handover cites matching-engine at tick 76. With the unchanged fixture, reference-db is cited at its fresh tick 75. If either fresh `check_link` row fails, no link is kept or cited. The handover says the link state is unknown and claims neither a fault nor healthy links. The restart check stays unsupported. Every variant ends after 4 requests with no approval or effect.
  - *D3, saved decorated identifier then a valid one:* six requests. The sixth is the repair of the fifth: same user JSON plus a `function_call_output` naming `["reference-db"]`. The report cites reference-db at tick 22; 11/11 checks pass; no effect. Negative controls, each sent twice: the decorated string, `matching-engine` (healthy), `payments-db` (unseen), `order-gateway-2`, `Reference-DB`, ` reference-db` and `reference-db.`. Each ends in `validation_exhausted` with no follow-up and no effect, and so does `reference-db` before any link was read. A generic handover after a rejected target remains available. B timeout handling and restart refusals are unchanged (existing tests).
  - *A2, saved choices:* the cue shows `order-gateway-2` at decisions 4 and 5 and is withdrawn at 6. By then the two refreshes had aged the link reads past five ticks, so the saved final `links` read was a legitimate refresh. The refreshes still run, the replay still reaches the cap and fails overall (7 of 12 checks passed), and nothing is approved. A restart at the cue passes 12/12 with approval, receipt and three post-action readings. A1's refresh-then-restart path still passes. Stale samples (collector stopped at tick 14) and expired reads show no cue, and the gate refuses accordingly.
  - *A3 diagnostics after three reads:* a reasoning-only `incomplete`/`max_output_tokens` reply at 512 tokens fails after one request with no repair (the same shape as slot 11: 4 HTTP, 3 decisions) and is reported as `output_limit`. Truncated tool calls twice → `output_limit`. Completed invalid answers at 512 tokens twice → `validation_exhausted`. Completed answers with no call → `validation_exhausted`. An invalid completed answer, then an explicit limit on the repair → `output_limit` (the final signal is definitive). No `status` field, `content_filter`, or a truncated reply then an invalid completed one → `unknown`. 500 or 503 → `provider_error`. A valid completed answer at exactly 512 tokens is a normal decision. After a successful repair, the next decision's failure gets its own reason. A refused repair is still the cap. No SDK message, provider error text or raw model output appears in any record.
  - *Mutation check (scratch, not committed):* disabling the refresh rule, the exact-link validator, the classifier, or the cue's age check each made 2–16 of these tests fail.
- **Scripted traces.** [`offline-traces-m1.7.jsonl`](../first_line/offline-traces-m1.7.jsonl) (SHA-256 `a7335605…`, regenerated after the review fix below; it embeds the `shift.py` hash) matches m1.6 and m1.5 except for `revision` and `harness_sha256`. The scripted order never reaches the new paths. The [m1.6 traces](../first_line/offline-traces-m1.6.jsonl) still hash to the frozen `953ac92a…`. The #21 byte-overlap test still reproduces 21–22 and 821–1315 bytes. That is a byte measure of user JSON, not a token, cache or cost result. m1.7 requests differ from m1.6 in instructions and `progress`, so do not pool them in a #21 comparison.
- **What this does not show.** Whether `gpt-6-luna` would now pass E, D or A; whether the cue changes A2-like choices; whether slot 11 really stopped at the output limit (its trace kept no response status, so the cause stays unknown). Code now ends the E loop and writes the handover, so a future E pass would show the harness policy working, not that the model chose the link. The `stale_evidence` record keeps that distinction. The refresh rule applies only while gateway samples are stale, so repeated reads with current samples are still bounded only by the cap and decision limit. Sample-time order is tested only within one simulated day; a case whose samples cross midnight is unsupported. Prompt structure (#4) and the other specifications stay Draft.
- **Review fix (23 November).** A fresh Opus 5.5 review found one Medium. The stall handover reused any earlier link read, even one taken before the stalled refresh, after which the link state could have changed. In `tickets → links → instances → instances`, a link that recovered at tick 70 was cited as degraded, and a link that first degraded at 70 was missed. Reason for the change: the agreed rule requires a fresh independent source. The fix is the read-order rule in the table above, with no extra model decision. The same change stops a refresh from being labelled a stall when a previously stale replica advanced but another did not. The tests above failed on the reviewed code and pass now. Classifier behavior is unchanged; only its description was made exact, and the invalid-then-limit case is now tested.
- **Decision at the time.** The code-owned E handover was ready for owner review; the [closeout below](#2026-11-23-m1-closeout) records the decision. Any live check of `gateway-m1.7` needs separate owner decisions on settings and spending under #8.

## 2026-11-23 M1 closeout

The owner accepted M1, including the code-owned Case E handover, and asked for the tag. Issues [#12](https://github.com/jpboliv/meridian-project/issues/12) and [#13](https://github.com/jpboliv/meridian-project/issues/13) are closed. The [owner sign-off](https://github.com/jpboliv/meridian-project/issues/13#issuecomment-7102990460) is recorded on #13. The [annotated M1 tag](https://github.com/jpboliv/meridian-project/tree/M1) points to `f07fb1ef84b34287d5992ccec4d484f1f10490bc`, which has the same tree as the packaged and reviewed commit `781f290`. The local ZIP is the original tested handoff from before the tag.

Released `gateway-m1.7` passed 119 offline tests and 5/5 scripted cases. In the Case E replay, the harness ends the stalled reads, checks the links again, and writes the handover. If the stalled refresh itself reads the links, the harness uses that fresh evidence. The archived [`gateway-m1.6` live baseline](#2026-11-22-public-m1-baseline-gateway-m16) passed 9/15. Live performance for `gateway-m1.7` remains untested.

## Context-reuse arms, prepared offline

21 November 2026, `gateway-m1.5` harness ([#21](https://github.com/jpboliv/meridian-project/issues/21), [#20](https://github.com/jpboliv/meridian-project/issues/20)). Project question: when does reusing context lower the cost of investigating an incident, and what evidence must the agent gather again before acting? Timestamp position is one hypothesis, not the whole project. This section is the run protocol for #21. It implements the request side of the [agreed prompt-caching comparison](specs/evaluation.md#agreed-metrics). `shift.py`, the scripted traces, the lab, model selection, and the limits are unchanged. The baseline live request is also unchanged. The versioned runbook and source cache stays optional under [#16](https://github.com/jpboliv/meridian-project/issues/16).

**Offline prefix overlap ([#21](https://github.com/jpboliv/meridian-project/issues/21), at `b8cf8ba`).** At each scripted A–E decision, the current simulated time (`sim.clock.label(sim.state.tick)`) was added first or last to the same context, then serialized with `json.dumps`. The check compared consecutive UTF-8 user JSON messages within each incident. Across 18 decisions there were 13 adjacent pairs. Identical leading bytes: time first, 21–22 (median **22**); time last, 821–1315 (median **920**). `test_offline_prefix_overlap_matches_the_issue_21_measurement` reproduces all six numbers through the arm's layout function. These are **bytes** of the user message only. They exclude instructions, tool schemas, and provider serialization. They do not measure tokens, cache hits, latency, or savings. Eligibility depends on two things. On Luna, the prefix must reach 1,024 visible tokens, and it must end at an eligible message ending or breakpoint ([OpenAI guide](https://developers.openai.com/api/docs/guides/prompt-caching#choose-a-caching-mode)). Here the time changes inside a single user JSON message, so a shared byte prefix within that message is not enough on its own.

**Arms.** Each live run takes one `--reuse-arm` choice ([operator notes](../README.md#context-reuse-arms-for-21-opt-in)): `time-first`, `time-last` (the shared control), or `time-last-no-cache`. The extra comparison asks whether cache writes are worthwhile. `time-last-no-cache` sends the control's request with `prompt_cache_options={"mode": "explicit"}` and no breakpoints. According to the [OpenAI guide](https://developers.openai.com/api/docs/guides/prompt-caching#choose-a-caching-mode), this disables cache reads and writes on GPT-6 Luna (Responses API). The arm is accepted only for the exact model name `gpt-6-luna`. No other factorial arms exist: the CLI rejects any other choice.

**Cost accounting, from the [OpenAI guide](https://developers.openai.com/api/docs/guides/prompt-caching#monitor-cache-performance).** On GPT-6 Luna with the Responses API, `cached_tokens` counts billed cache reads and excludes writes. Reads and `cache_write_tokens` are disjoint subsets of `input_tokens`, so ordinary input = `input_tokens` − `cached_tokens` − `cache_write_tokens`. At the standard default 30-minute rates, a write is billed at 1.25× the ordinary input rate and a read at 0.1×. These are the full rates for those tokens, not surcharges; check them again at run time. Illustration for one prefix only: written once and fully reused once, it costs 1.35 input-rate units, against 2 with no cache. That is not an incident result. The harness records counts only, with no billing engine. If both counts are valid but their sum exceeds `input_tokens`, both are recorded as unknown, so ordinary input never goes negative.

| Mocked-wire test (Responses API, mock transport) | Observed |
|---|---|
| Case A, four fixed decisions, baseline and each arm | Every arm had the same decisions, reads, effect, end tick, and verified recovery. Each arm's user JSON matched the baseline byte for byte, apart from one added `"current_time"` key, placed first or last. The value was 10:06 at the first decision and rose at each later one. The incident kept `time: 10:05`, and the report had no `current_time`. |
| `time-last` vs `time-last-no-cache`, four fixed decisions and an output repair | With the mode and the SDK's diagnostic response reference removed, each pair of bodies was identical. That covered the instructions, messages, tools, `max_output_tokens`, and time. Every no-cache request, including the repair, carried `mode: explicit`. No `prompt_cache_breakpoint`, key, retention, or TTL appeared. The repair resent the same time. |
| `time-last-no-cache` with `OPENAI_MODEL` set to a placeholder, `gpt-4.1-mini`, `gpt-5.6`, `gpt-6-lunar`, `gpt-6-luna-2026-11-01`, or `GPT-6-LUNA` | The run stopped after the key check, before any client or request. Nothing was printed. |
| Provider answers 400 to the no-cache setting | One request was sent and was not resent without the setting. The attempt kept status 400 and `null` cache usage. The handover reported an unavailable model. Zero effects. |
| Usage across three attempts: 0/0 of 101 input tokens, then a read of 64 of 102 with no write field, then 64/32 of 103 | Per attempt: `(0, 0)`, `(64, null)`, `(64, 32)`. The read total stayed known at 128, and the write total was `null`. Input tokens stayed 306 with no cache count added. There was no cost, price, or hit field. |
| Reads and writes of 60/41 and 61/41, each of 101 input tokens | 60/41 equals the input and was kept. 61/41 exceeds it, so both counts were recorded as `null` at attempt and case level, while the input tokens stayed recorded. |
| `input_tokens_details` missing, null, or a string; `cached_tokens` null, string, negative, boolean, fractional, or above `input_tokens` | The read count was `null` at both attempt and case level. Input tokens were still recorded. |

All 69 project tests passed offline. No provider requests, credentials, tokens, or costs. Complete requests match only in a fixed-decision replay. In a live run each arm's model can choose differently, so later requests can diverge; that divergence is part of the outcome.

**Plan for the paid comparison (not authorized).** For every attempt, including failures, repairs, and retries, count cache reads, cache writes, ordinary input, and output separately. Whole-incident cost sums all of them at the rates published on the run date. If usage or a price is missing, the cost is unknown. Writes pay off only if `time-last` costs less than `time-last-no-cache` for the whole incident, with the same verified passes, targets, and effects. A cheaper wrong restart fails. The provider cache cannot be flushed, and an auto arm can start warm from an earlier run with the same prefix. Counterbalance the arm order within each pair, and keep `started_at_utc`. Repetitions, spending, and actual results remain open with [#8](https://github.com/jpboliv/meridian-project/issues/8).

Evidence levels: the M1 scripted traces are recorded results. Prefix overlap is an offline byte measure. The wire tests show what would be sent and how usage would be recorded. Provider results for these arms are pending.

One optional follow-up, only if the results show that writes often go unread: place an explicit breakpoint at the end of stable, authorized content. Do not add an application cache now: the runbook is read once per shift.

## 2026-11-18: shortened restart handover

One read-only trial with `claude-opus-5-5`, a fresh conversation, and only the four [case files](cases/restart/) in its working directory. No simulator or action tools. Prompt: “The order gateway is slow. Read handover.md, verify it against its sources, inspect current.md, and recommend the next action. Cite the observations behind your decision.”

Expected: recover both times from the originals, bound the causal claim, and use the current readings. Observed:

- Cited the fall from 880 to 740 ms at 10:02 in `latency.md` and the 10:05 restart in `actions.md`. Noted the samples stop at 10:03, so they cannot establish a later restart effect.
- Cited normal gateway memory and elevated gateway-to-database latency in `current.md`. Recommended checking database and network timings rather than restarting or declaring a cause.

Keep the compact handover for this case. The trial tested a requested source check, not whether an agent checks spontaneously or whether compression outperforms the full history.

## 2026-11-18: does the memory lesson change the investigation?

Four fresh read-only shifts, one per combination (Claude Code 2.1.327, `claude-opus-5-5`). Every shift received the same post-upgrade alert, the same three filenames, and a request to investigate and recommend a next step. Half also received “when the gateway slows down, compare memory use across instances.” There was no expected answer in the prompt.

| Memory source | Without lesson | With lesson |
|---|---|---|
| Two instance readings, each 55% | Reported both within range | Compared both readings. Neither stood out. |
| Fleet mean 55% only | Left individual memory unresolved | Said the comparison was unavailable. Left individual memory unresolved. |

All four traces listed the same reads: `memory.txt`, `link.txt`, `health.txt`. The independent monitor had no per-instance readings. All agents recommended investigating the database path. Latency was 210 ms against a normal range of 15–25 ms. No agent had an action tool.

The readings determined which conclusion the evidence supported. Adding the lesson did not change source use or the primary recommendation in this small comparison. Each condition had one run, and the prompt named every source. These results do not establish whether recall helps in a broader investigation.
