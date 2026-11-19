# Project goals

Draft for owner review · [Issue 1](https://github.com/jpboliv/meridian-agents/issues/1).

The user is the on-call engineer at Meridian, a simulated stock exchange. The engineer needs to know what happened, whether to act, and whether the service recovered. The project asks when an earlier shift saves investigation time and when it points the next shift at the wrong fix.

By the demonstration, the owner can follow one alert through the system. They can show which evidence reached the model, why it used a lesson, and why it accepted or refused a saved result. They can point to the effect in the action log and the later readings that support the report.

## What each milestone must show

| Milestone | Course requirement | Evidence to show Luís |
|---|---|---|
| M1: First-line agent | One agent handles a request from alert to result. It selects context and uses the Model Context Protocol (MCP) to read from services. | A ticket and a monitoring reading refer to the same fault. The agent names the affected instance, obtains approval, and reads its condition after one restart. |
| M1: Controlled failure | Tools have explicit inputs and outputs. Code enforces their limits. | A missing reading, an invalid response, or an unavailable service produces a useful handover. No unverified recovery claim. |
| M2: On-call agent | Memory persists across shifts. Access, origin, correction, and deletion have rules. | The next shift finds a new target. A later shift drops the old diagnosis. Neither lookup nor handover returns deleted or private material. |
| M2: Permissions and evaluation | Code enforces access. Repeated runs compare changes against a baseline. | Show one permitted effect, one refusal with no effect, and results for recall on each case. Include failures and the cost of maintaining memory. |
| M3: Response team | A lead agent combines results from two specialists. Technical changes require evidence and approval. | Show two findings, one failed handoff, and a decision to act or stop. Compare the team with the single agent. |
| M3: Resume | The system saves unfinished work and reconciles it with the executor after an interruption. | Stop the worker after the restart takes effect. A new worker finds the receipt and verifies the result. The evaluator counts one effect. |

## Agreed delivery priorities

First deliver two runnable M1 cases. In one, correlate the ticket and monitoring evidence, approve one targeted restart, and show three consecutive healthy readings after it. In the other, the instance readings are missing. Consult an independent source and hand over the specific gap without a restart if it remains unresolved.

Our course deep dive is prompt caching, evaluated on verified incident outcomes. Compare a changing timestamp at the start of the request with the same timestamp at the end. Measure provider-reported reuse and cost per incident. A cheaper wrong restart fails the case.

In a separate handover experiment, compare a fresh agent with and without the same sourced reminder. Both get the full runbook, which already calls for per-instance checks. Count reads to a correct decision, wrong targets, and the cost of saving and retrieving the reminder. A tie counts as a result. The correction case asks a different question: once the restart story proves wrong, what advice reaches the next operator?

Protect the M3 demonstration: combine two specialist findings, detect a failed handoff, and resume after an applied action without repeating it. Use 29 November for a clean-clone rehearsal. Caching tool results, prompt fingerprints, summary-cost comparisons, model routing, and animation can follow if time permits. No delivery milestone depends on them.

For delivery, tag the three milestone versions. Provide a proposal, flow diagram, dependency lock, and secret-free `.env.example`. Use the README to explain setup, policies, limitations, and AI assistance. Include each case, its expected and actual result, the model version, limits, and a trace. Rehearse a verified fix, a controlled failure, and a resume from a clean clone.

The submission deadline is 30 November 2026 at 23:59 Lisbon time (`Europe/Lisbon`). The internal finish target is 29 November at 18:00 in the same time zone.
