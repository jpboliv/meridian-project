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
| M2: Permissions and evaluation | Code enforces access. Repeated runs compare changes against a baseline. | Show one permitted effect, one refusal with no effect, and per-case results for recall and caching. Include failures and costs. |
| M3: Response team | A lead agent combines results from two specialists. Technical changes require evidence and approval. | Show two findings, one failed handoff, and a decision to act or stop. Compare the team with the single agent. |
| M3: Resume | The system saves unfinished work and reconciles it with the executor after an interruption. | Stop the worker after the restart takes effect. A new worker finds the receipt and verifies the result. The evaluator counts one effect. |

Use the supplied Python simulator, local synthetic data, the course tools, and the existing evaluator. The core experiment covers three shifts, one changed cause, and one correction. Keep model routing, communication with another team's agent, and an animated report optional. None answers the primary question.

For delivery, tag the three milestone versions. Provide a proposal, flow diagram, dependency lock, and secret-free `.env.example`. Use the README to explain setup, policies, limitations, and AI assistance. Include each case, its expected and actual result, the model version, limits, and a trace. Rehearse a verified fix, a controlled failure, and a resume from a clean clone.

The submission deadline is 30 November 2026 at 23:59 Lisbon time (`Europe/Lisbon`). The internal finish target is 29 November at 18:00 in the same time zone.
