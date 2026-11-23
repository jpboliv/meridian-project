# Meridian roadmap · November 2026

Start with [STATUS.md](STATUS.md). M1 is complete and tagged. The [M1 closeout](projects/course-02-agentic-ai/docs/experiments.md#2026-11-23-m1-closeout) records owner acceptance and the evidence for `gateway-m1.7`.

## Delivery order

Dates through 28 November are planning targets. The rehearsal target is **29 November at 18:00**; submission is due **30 November at 23:59**, Lisbon time.

| Target | Work and issues | Evidence needed to finish |
|---|---|---|
| 19–20 Nov · Baseline decisions | Owner reviews [#8][8] (model revision, repetitions, run limits). Finish the first-line flow [#12][12] and configure the course model locally. | Record the agreed settings and reserve unseen cases before tuning. While the run settings await approval, prepare the arms and usage recording for [#21][21]. |
| 22 Nov · M1 live baseline (completed) | The archived [`gateway-m1.6` baseline](projects/course-02-agentic-ai/docs/experiments.md#2026-11-22-public-m1-baseline-gateway-m16) under [#13][13] passed 9/15, with four authorized restarts and no other effects. | On 23 November, the owner accepted M1. The tagged `gateway-m1.7` passed 119 offline tests and 5/5 scripted cases. |
| 23–25 Nov · Course deep dive | Compare **timestamp first vs. last**, and the time-last control with caching off, for [#21][21] after freezing M1. Use the same cases, model, tools, memory setting, and limits ([protocol](projects/course-02-agentic-ai/docs/experiments.md#context-reuse-arms-prepared-offline)). | Show provider-reported cached tokens and whole-incident cost beside verified outcomes. A cheaper wrong restart fails. Report zero reuse or unavailable measurements honestly. |
| 23–25 Nov · M2: handover and access | Implement scoped memory [#14][14] and permissions [#15][15]. Then compare runbook alone vs. runbook plus a sourced reminder [#17][17]. This can run alongside #21; keep the prompt layout fixed here. | Show the corrected lesson reaching the next shift, one authorized action, one refusal, and per-case regressions or a tie. Review and tag M2. |
| 26–28 Nov · M3: team and resume | Integrate two specialists [#18][18], then interrupt and replace the incident worker [#19][19]. Rehearse the interruption boundary earlier, as soon as the single-agent restart works. | Detect a failed handoff. After an applied restart, recover the original receipt, verify health with fresh readings, and count exactly one effect. Review and tag M3. |
| 29–30 Nov · Rehearse and submit | Follow the README from a clean clone [#20][20]. Use 30 November for fixes and submission. | Demonstrate a verified fix, a controlled failure, and resume. Deliver the three tagged versions, comparisons, traces, limitations, and AI-use disclosure. |

## How to use the backlog

[Design foundation][design] holds the eleven specification issues. Review memory and access before M2, and specialist handoff and resume before M3. Agreement on an individual rule does not make the full specification Agreed.

Open a pull request in `jpboliv/meridian-project` when work starts on each milestone. Assign it to the same milestone as its issues and link the evidence. The orchestrator merges it after a clean independent review, as set out in [AGENTS.md](AGENTS.md); tagging still waits for owner review.

If time gets tight, defer [#16][16] (caching tool results), prompt fingerprints, and summary-cost comparisons. **Keep #21:** it is the presentation’s prompt-caching experiment, and the simulator gives it a correctness check.

[Live milestones][milestones] track the work; [STATUS.md](STATUS.md) records the latest evidence and next decision.

[8]: https://github.com/jpboliv/meridian-project/issues/8
[12]: https://github.com/jpboliv/meridian-project/issues/12
[13]: https://github.com/jpboliv/meridian-project/issues/13
[14]: https://github.com/jpboliv/meridian-project/issues/14
[15]: https://github.com/jpboliv/meridian-project/issues/15
[16]: https://github.com/jpboliv/meridian-project/issues/16
[17]: https://github.com/jpboliv/meridian-project/issues/17
[18]: https://github.com/jpboliv/meridian-project/issues/18
[19]: https://github.com/jpboliv/meridian-project/issues/19
[20]: https://github.com/jpboliv/meridian-project/issues/20
[21]: https://github.com/jpboliv/meridian-project/issues/21
[design]: https://github.com/jpboliv/meridian-project/milestone/2
[milestones]: https://github.com/jpboliv/meridian-project/milestones
