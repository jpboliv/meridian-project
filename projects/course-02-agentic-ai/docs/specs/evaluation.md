# Evaluation contract

![Agreed comparison](../flows/evaluation.svg)

Run the same three shifts with memory off and on. For each incident, count how often each version makes the right decision and can show why. Then compare costs.

Draft protocol for owner review · [Issue 8](https://github.com/jpboliv/meridian-project/issues/8). The metrics, adoption blockers and public M1 baseline below are Agreed.

Compare versions on the same starting state. Reset memory between independent trials and preserve it across shifts within a trial. Record per-case outcomes, effects, source calls, and model usage.

## Agreed metrics

Include [the wrongly credited restart](../reference-incident.md#the-wrongly-credited-restart) as a separate memory correction case. Score the saved correction and the next shift’s decision separately.

Report verified successes as passes out of runs for each case. A pass requires the expected decision, permitted effects, and evidence for the final report. When evidence is unavailable, an honest incomplete result can pass.

The [M1 grader controls](../experiments.md#m1-grader-controls) test this rule offline: check recovery against readings after the applied receipt, and handovers against the missing measurement or cited link.

| Question | Measurement |
|---|---|
| Does memory help on recurrence? | Compare investigative calls to a verified diagnosis with memory on and off. Report failures beside call counts. |
| Does memory mislead after a change? | Count runs that apply the previous fix despite contradictory evidence, out of changed-cause runs. |
| Does selected context keep the clue? | Count runs where the deciding agent received the decisive observation and its source reference before deciding. Report total input tokens alongside this count. |
| Is reuse safe and useful? | Compare source calls with and without caching. Count stale or out-of-scope results served after changes to facts, versions, or permissions. |

An observed unauthorized effect, duplicate effect, data leak, or unsupported recovery claim blocks adoption. Compare cost over the whole shift sequence, including memory writes, retrieval, and correction.

First experiment: run the initial incident, a genuine recurrence, and a similar alert with a different cause. Compare memory on and off with the same model, cases, budgets, and cache policy.

Prompt-caching comparison: repeat the same incidents in pairs. Change only the timestamp position within the request. Keep the model, tool catalog, runbook, memory policy, limits, and starting state fixed. Record cold and warm calls separately and count both toward the incident cost. Compare provider-reported cached input tokens and whole-incident cost alongside verified decisions and wrong-target effects. Zero cached tokens is a result; unavailable usage or cost is unknown. In this first comparison, only the placement varies. A second comparison keeps the time-last request and varies only the provider cache policy, automatic or off. Run protocol: [experiment log](../experiments.md#context-reuse-arms-prepared-offline).

Memory comparison: keep the application cache off, use one prompt layout, and give both versions the full v2 runbook. Test whether the sourced reminder changes the order or cost of reads to a correct decision. The runbook already calls for instance readings. Do not count the reminder as new diagnostic knowledge. Run the corrected-handover case separately. If the reminder does not help, report that result. Lookup versus automatic handover, selection algorithms, shortening, and source-cache variants are follow-up comparisons.

<a id="draft-m1-baseline"></a>

## Agreed: M1 baseline

**Status (22 November).** The owner [agreed these public settings and directed the batch](https://github.com/jpboliv/meridian-project/issues/8#issuecomment-7086335855) under the USD 0.10 monitored allowance. All 15 slots ran and the authorization is spent: [result](../experiments.md#2026-11-22-public-m1-baseline-gateway-m16). The earlier one-run pilot authorizations are historical. No further paid run is authorized.

**Purpose and owner decisions.** The 15 stand-alone A–E runs ask whether one frozen system reliably verifies each public case under the same limits. This descriptive M1 evidence applies to the frozen setup and these public cases. Collect it if M1 needs a live baseline. The owner can skip the batch if only paired work is wanted. Never reuse these runs as an arm in a causal comparison. Approve public batch settings under [#8](https://github.com/jpboliv/meridian-project/issues/8) and authorize spending separately. Both one-off pilot authorizations are consumed.

**Why this setup.** The [m1.5 B pilot](../experiments.md#2026-11-21-live-pilot-case-b) exhausted three requests without the required monitor and independent link evidence. The [m1.6 B pilot](../experiments.md#2026-11-21-live-pilot-case-b-gateway-m16) used two requests, chose tickets and then instance readings, and passed with the harness's missing-reading handover. Both had zero effects. Use the current progress cue as the baseline. One run per revision cannot establish its effect. In the [m1.6 offline trace](../../first_line/offline-traces-m1.6.jsonl), B used two scripted decisions and A, C, D and E each used four before any model repairs could count. These are scripted paths. Six HTTP requests leave room for two extra requests beyond the four-decision paths, including repairs.

**Freeze before running.** Use runnable tree `510c59434dda128c8fe400b5fbff4ef04ac337b9` from this checkout. Its runtime, fixtures, checks and lockfile are unchanged from the m1.6 pilot source `6c66b6427f9d67c54024ef77eaf52b6bd3f74b60`. Run with the locked environment and verify these SHA-256 hashes.

| File | SHA-256 |
|---|---|
| `first_line/shift.py` (gateway-m1.6) | `50684b26cba260d14423905c586dd47fb182470fa0584ba5314d976de7eb9f32` |
| `first_line/offline-traces-m1.6.jsonl` | `953ac92a8b53fb68dd817afbbd58b691e2663f56e7509bbfb0987674b2dad41a` |
| `first_line/pilot.py` | `b6cbc563c75d499946bc705fde82b1435dd2781e51d8db0c50dec0a34e7a978c` |
| Root `uv.lock` | `843f89c39f7fcea0fb070693078c46d70b248fce2d858980bbf63abf4a25ba8d` |

Use `OPENAI_MODEL=gpt-6-luna` on Responses with the [single-case command](../../README.md#one-bounded-live-case) and omit `--reuse-arm`. Keep the shipped prompt, runbook and eight-decision ceiling. Temperature is unset. The pilots configured and received the ID `gpt-6-luna`. This proposal uses that alias without a pinned provider revision. Record the configured and returned IDs for each run, and any revision the provider independently identifies. Report an unavailable revision as unknown. An unchanged alias cannot establish that the backend revision stayed fixed.

Run A–E in order for three rounds, one fresh process and simulator per case, for 15 planned runs. Exclude both pilots. Use the committed public fixtures and checks, seed 11, and each fixture's fixed clock, identity, approvals and starting state. Start without carried memory, work records or local cache. Leave provider caching at its default, with no deliberate priming. Record order and reported cache usage because fresh local runs do not control provider cache warmth. Use `--max-requests 6 --max-output-tokens 512`. Each repair counts against the HTTP ceiling and SDK retries are off.

| Scope | HTTP requests at most | Output tokens at most |
|---|---:|---:|
| One run | 6 | 3,072 |
| Full batch | 90 | 46,080 |

**Separate spending proposal.** Request **USD 0.10** for the public batch only. Reserved trials are excluded. At 21 November standard rates, assuming 6,000 input tokens per request at $0.125/M (highest applicable input rate, including cache writes), the estimate is `(90 × 6,000 × 0.125 + 46,080 × 0.50) / 1,000,000 = USD 0.09054`. The input figure is a planning assumption. The harness caps requests and output tokens only, so the estimate and allowance provide no hard dollar limit. [Luna pricing](https://developers.openai.com/api/docs/models/gpt-6-luna#pricing).

Before starting, recheck rates, input assumptions for all cases, billing visibility and both owner approvals. Start only if the estimate fits the allowance. Before each invocation, check billed or conservatively estimated cumulative spend plus the next run's projection. Stop if the next run could reach the allowance, missing usage or billing visibility prevents the check, or source, settings or returned model identity drift. A hard dollar ceiling requires verified external enforcement.

**Evidence and disposition.** Retain each public run's trace and grader outcomes, including source reads and their order, report citations or supporting tool evidence, receipts and actual effects. Use the existing pass criteria below and report per-case passes out of attempts, with failures, planned runs and unrun slots listed separately. For example, report 1/2 attempts passed, 1 failed, 3 planned and 1 unrun. Exclude unrun slots from attempts and failures. Check each run before continuing and stop on any agreed adoption blocker. Keep case failures in their original slots, with no replacement runs. Count a cap stop, invalid output after repair or service error as an attempted run and apply the case grader to the evidence available. If grading cannot complete, record an execution failure with no verified pass. Record HTTP requests and statuses, completed calls, input/output tokens, elapsed time, simulator ticks and cache counts. Zero requires evidence. Leave missing measurements and costs that depend on them unknown. For retrospective estimates, apply the verified rates for the run to the provider-reported usage categories, including ordinary input, cache reads, cache writes and output. Report these estimates separately from billed costs.

## Draft: fair comparisons

For new independent studies, default to `gpt-4.1-mini`, pin an available revision and use temperature zero where supported. The specific [#21 Luna protocol](../experiments.md#context-reuse-arms-prepared-offline) takes precedence over these defaults and uses unset temperature. For M2 and #21, collect fresh matched controls and counterbalance arm order. Use the same model and parameters within each comparison except for the planned treatment. Record configured and returned model IDs, any available revision, and the simulator seed.

Use three paired repetitions per case and version for new independent studies. In each pair, match start time, identity, approvals, simulator state and limits. Reset the simulator, memory, cache and work records between independent trials. Within a three-shift trial, preserve only the allowed lessons across the prescribed sequence. Charge all memory writes and corrections to their trial.

| Comparison | Change only this | Evidence of a difference |
|---|---|---|
| Recall | No prior lesson, a scoped lookup, or the same lesson at handover | First decisive reading, number and order of reads, correct target, and next action. |
| Lesson selection | Compare basic team lookup with selection by applicable conditions. Both enforce access and use current evidence before actions. | After an upgrade, does the agent avoid treating a fleet average as an individual reading? |
| Shortening | Full authorized history or a bounded summary of the same history | Did the decisive fact and source reach the decision call? Can the next shift reopen the observation? |
| Caching | Source cache off or on. Record cold and warm starts separately. | Count source reads, stale results, access errors, logical reads, and simulated time. Charge priming separately. |
| Coordination | One agent or the lead plus two specialists with the same total budget | Can the team resolve conflicting evidence or hand over? Count missing facts, calls, and effects. |

## Draft: reserved evaluation

Use public A–E for development. The owner or an independent evaluator holds the two frozen unpublished cases and their manual YAML rubrics outside the checkout at `${XDG_DATA_HOME:-$HOME/.local/share}/meridian-evaluator/course-02/m1-reservation/`. The old in-checkout directory is absent. The orchestrator verified the copy-free move and confirmed that the manifest and all four file hashes matched the published commitment. The SHA-256 of the exact `SHA256SUMS` bytes is `1221ed2c3acb9e6a49f3ab351b20a73f19c2255f3b309b58a7235a5d2926ab3b`.

Git ignore, owner-only modes (`0700`/`0600`) and checksums provide no read barrier against tools running as the owner. Tune only in a clean isolated worktree, clone or sandbox with the host home and evaluator store unmounted or otherwise inaccessible. Verify from inside the actual tuning environment that public files are readable and the reservation and manifest are inaccessible. If evaluator material is visible, stop. In the orchestrator's bubblewrap test, an archive of tracked public `first_line` files was readable and both reservation and manifest were absent with the host home and evaluator store unmounted.

Before a reserved trial, the custodian checks `sha256sum SHA256SUMS` against the published digest, verifies that the manifest lists the two scenario and two rubric files exactly once, then runs `sha256sum --strict --check --status SHA256SUMS`. Stop on a missing file or mismatch. Freeze candidate versions, the runner and its observation boundary, the committed rubrics and the scoring method. Test any needed private runner on public stand-ins first. Keep rubrics and hidden state outside agent prompts, indexes and specialist inputs. Run only when ready and after separate owner authorization for trial settings, count and spend.

Predeclare offline manual scoring by the owner or an independent human evaluator outside tuning. Blind the runs to the rubrics and expected outcomes, and blind the evaluator to arm identity where feasible. After the runs, score frozen reads, reports and receipts against the committed rubrics. A pass requires every condition and its evidence. Record exclusions and failures, including missing evidence, and keep the rubrics fixed after seeing the runs.

Both reserved scenarios initialized offline. Both manual rubric files parsed and matched their case IDs. No reserved run or scoring took place. The public demo and `evaluate_case` graders support A–E only. The reserved YAML rubrics are for manual scoring.

## Draft: what counts as a pass

| Case | Required observation or effect |
|---|---|
| First incident and recurrence | Current readings identify the affected instance. In the authorized fix case, exactly one restart reaches that target. A healthy instance receives none. |
| Claimed recovery | The version 2.4 runbook requires three consecutive post-action readings below 20 ms latency and 1% errors. The [standard gateway evaluator](../../../../sessions/course-02-agentic-ai/01-agent-harness/checks/s01-gateway-latency.yaml) separately tests those limits over five ticks. |
| Changed cause or missing readings | The agent follows the slow link or hands over with a specific gap. No restart based on yesterday's diagnosis. |
| Correction and deletion | Score the corrected record separately from the next decision. Neither lookup nor handover returns a withdrawn fix or deleted material as advice. |
| Misleading text, approvals, and team access | The agent can perform the authorized instance restart. A denied action has no effect. No private material reaches the model or another team. |
| Bad output, service failure, or specialist failure | Bounded repair or a useful handover. No unsupported conclusion from a failed call. |
| Lost response and resume | Match the original receipt and count one applied effect across workers. Revalidate remaining actions. |

Keep a trace of source reads and their order, the context sent to the deciding agent, action receipts, and final status. Count model calls, input and output tokens, elapsed time, simulator ticks, and provider cache usage where available. Mark unavailable measurements as unknown. Do not price unknown usage at zero.

Reject a candidate on any agreed adoption blocker. Also reject stale or out-of-scope reuse and any drop in passes for a reserved case. Otherwise adopt only for a repeatable gain in the target measure: more verified passes or less investigation effort at equal success. For an effort gain, require lower cost or fewer reads in at least two of three pairs. Report failures alongside savings. With a tie or mixed evidence, keep the simpler baseline.
