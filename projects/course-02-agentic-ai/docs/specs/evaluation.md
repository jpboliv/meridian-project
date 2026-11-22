# Evaluation contract

![Agreed comparison](../flows/evaluation.svg)

Run the same three shifts with memory off and on. For each incident, count how often each version makes the right decision and can show why. Then compare costs.

Draft protocol for owner review · [Issue 8](https://github.com/jpboliv/meridian-project/issues/8). The metrics and adoption blockers below are Agreed.

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

## Draft: M1 baseline

**Owner decisions pending.** Approve the settings and batch below under [#8](https://github.com/jpboliv/meridian-project/issues/8) and separately authorize spending. The two one-off pilot authorizations are consumed. The public A–E batch establishes a baseline for later comparisons. The [#21 reuse experiment](../experiments.md#context-reuse-arms-prepared-offline) has its own protocol and approval.

**Why this setup.** The [m1.5 B pilot](../experiments.md#2026-11-21-live-pilot-case-b) exhausted three requests without the required monitor and independent link evidence. The [m1.6 B pilot](../experiments.md#2026-11-21-live-pilot-case-b-gateway-m16) used two requests, chose tickets and then instance readings, and passed with the harness's missing-reading handover. Both had zero effects. Use the current progress cue as the baseline. One run per revision cannot establish its effect. In the [m1.6 offline trace](../first_line/offline-traces-m1.6.jsonl), B used two scripted decisions and A, C, D and E each used four before any model repairs could count. These are scripted paths. Six HTTP requests leave room for two extra requests beyond the four-decision paths, including repairs.

**Freeze before running.** Use runnable tree `510c59434dda128c8fe400b5fbff4ef04ac337b9` from this checkout. Its runtime, fixtures, checks and lockfile are unchanged from the m1.6 pilot source `6c66b6427f9d67c54024ef77eaf52b6bd3f74b60`. Run with the locked environment and verify these SHA-256 hashes.

| File | SHA-256 |
|---|---|
| `first_line/shift.py` (gateway-m1.6) | `50684b26cba260d14423905c586dd47fb182470fa0584ba5314d976de7eb9f32` |
| `first_line/offline-traces-m1.6.jsonl` | `953ac92a8b53fb68dd817afbbd58b691e2663f56e7509bbfb0987674b2dad41a` |
| Root `uv.lock` | `843f89c39f7fcea0fb070693078c46d70b248fce2d858980bbf63abf4a25ba8d` |

Use `OPENAI_MODEL=gpt-6-luna` on Responses with the [single-case command](../../README.md#one-bounded-live-case) and omit `--reuse-arm`. Keep the shipped prompt, runbook and eight-decision ceiling. Temperature is unset. The pilots configured and received the ID `gpt-6-luna`. This proposal uses that alias without a pinned provider revision. Record the configured and returned IDs for each run, and any revision the provider independently identifies. Report an unavailable revision as unknown. An unchanged alias cannot establish that the backend revision stayed fixed.

Run A–E in order for three rounds, one fresh process and simulator per case, for 15 planned runs. Exclude both pilots. Use the committed public fixtures and checks, seed 11, and each fixture's fixed clock, identity, approvals and starting state. Start without carried memory, work records or local cache. Leave provider caching at its default, with no deliberate priming. Record order and reported cache usage because fresh local runs do not control provider cache warmth. Use `--max-requests 6 --max-output-tokens 512`. Each repair counts against the HTTP ceiling and SDK retries are off.

| Scope | HTTP requests at most | Output tokens at most |
|---|---:|---:|
| One run | 6 | 3,072 |
| Full batch | 90 | 46,080 |

**Separate spending proposal.** Ask the owner for a **USD 0.10 allowance** for this public batch. The harness limits requests and output tokens. Input tokens and dollar spend have no harness cap. Before starting, verify applicable rates and billing visibility, and estimate conservatively using uncached input and maximum output, allowing for cases longer than B. The historical B estimates in the pilot records are observations from two runs. Start only with both owner approvals, verified inputs and settings, and an estimate that fits the allowance. Review billed or conservatively estimated cumulative spend and the next run's projection before each invocation. Stop launching runs if the next run could reach the allowance, if missing usage or billing visibility prevents that check, or if source, settings or returned model identity drift. Estimates and checks between invocations leave exposure within a run. If the owner requires a hard dollar ceiling, start only with a verified external enforcement mechanism.

**Evidence and disposition.** Retain each public run's trace and grader outcomes, including source reads and their order, report citations or supporting tool evidence, receipts and actual effects. Use the existing pass criteria below and report per-case passes out of attempts with the planned denominator (three), failures and unrun slots visible. Check each run before continuing and stop on any agreed adoption blocker. Keep case failures in their original slots, with no replacement runs. Count a cap stop, invalid output after repair or service error as an attempted run and apply the case grader to the evidence available. If grading cannot complete, record an execution failure with no verified pass. Record HTTP requests and statuses, completed calls, input/output tokens, elapsed time, simulator ticks and cache counts. Zero requires evidence. Leave missing measurements and costs that depend on them unknown. Report rate-based estimates separately from billed costs.

## Draft: fair comparisons

For future paired comparisons choose one model and pin a provider revision where available. Record configured and returned IDs, settings, tool catalog and simulator seed. Fixed settings do not guarantee identical responses.

Use three paired repetitions per case and version. In each pair, use the same start time, identity, approvals, simulator state, and limits. Reset the simulator, memory, cache, and work records between independent trials. Within a three-shift trial, preserve only the allowed lessons across the prescribed sequence. Charge all memory writes and corrections to their trial.

| Comparison | Change only this | Evidence of a difference |
|---|---|---|
| Recall | No prior lesson, a scoped lookup, or the same lesson at handover | First decisive reading, number and order of reads, correct target, and next action. |
| Lesson selection | Compare basic team lookup with selection by applicable conditions. Both enforce access and use current evidence before actions. | After an upgrade, does the agent avoid treating a fleet average as an individual reading? |
| Shortening | Full authorized history or a bounded summary of the same history | Did the decisive fact and source reach the decision call? Can the next shift reopen the observation? |
| Caching | Source cache off or on. Record cold and warm starts separately. | Count source reads, stale results, access errors, logical reads, and simulated time. Charge priming separately. |
| Coordination | One agent or the lead plus two specialists with the same total budget | Can the team resolve conflicting evidence or hand over? Count missing facts, calls, and effects. |

Use the public course cases while developing. Two unpublished inputs, `m1-r1` and `m1-r2`, are reserved before further tuning. Freeze the versions before opening the reserved cases for evaluation. Keep expected outcomes and hidden state out of all agent prompts, search indexes and specialist inputs.

The reservation is on this machine in the ignored `projects/course-02-agentic-ai/private/m1-reservation/` directory. It contains one scenario and one scorer YAML per ID, with private grading instructions. Directory permissions are `0700` and file permissions are `0600`. The SHA-256 of the exact bytes of `SHA256SUMS` is `1221ed2c3acb9e6a49f3ab351b20a73f19c2255f3b309b58a7235a5d2926ab3b`. The manifest commits to the exact bytes of all four files, including the scorers.

From the reservation directory, run `sha256sum SHA256SUMS` and compare it to the published digest first. Then run `sha256sum --strict --check --status SHA256SUMS` and confirm that the manifest lists both scenario and both scorer files exactly once. Use only the committed inputs. A fresh clone does not contain them. If a file is missing or a digest differs, stop the reserved evaluation without substituting or recreating the reservation. The files passed offline load and compatibility checks. They are reserved inputs with no candidate results and are outside the 15-run public batch.

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
