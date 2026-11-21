# Experiment log

Proposed first simulator comparison: run the recurrence with and without a prior shift record. Does recall reduce investigation effort without a wrong-target restart?

For each experiment, record the hypothesis, harness revision, case, model, initial state, budget, repetitions, expected outcome, observed outcome, trace, and decision. Include the cost of writing memory. For cache comparisons, record whether the cache started empty.

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
