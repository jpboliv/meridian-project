# Specialist handoffs

![Proposed flow](../flows/coordination.svg)

Each specialist reports what they found and where they found it. If they disagree, the agent leading the investigation asks for more evidence before anyone changes the system.

State: **Agreed** for M3 · [Owner sign-off, 23 November](https://github.com/jpboliv/meridian-project/issues/10#issuecomment-7116373182).

Implementation state: offline and scripted, in draft [PR #41](https://github.com/jpboliv/meridian-project/pull/41) (`team/handoff.py`); not yet reviewed or merged. Two read-only specialists with disjoint allowlists, validated task replies, one shared follow-up and one shift budget run on the M2 scoped lead path. Public evidence: [M3 specialist handoffs](../experiments.md#2026-11-23-m3-specialist-handoffs-offline). Specialist judgement by a model, and its token cost, are untested.

The lead agent owns the incident, combines findings, and reports to the operator. The infrastructure specialist reads instance and link measurements. The application specialist reads change records, tickets, and service logs. Specialists can read within the caller's scope. Neither can approve actions, dispatch changes, or write shared lessons.

Each task carries a task ID, incident ID, caller scope, target, question, allowed reads, deadline, and remaining budget. Each result returns the task ID, finding, source IDs and times, limitations, and suggested next read. Accept statuses `found`, `no_evidence`, or `blocked`. A result with an unknown source, wrong task ID, or missing target cannot support an action.

The lead agent can request both specialties in one round. Keep source timestamps on the replies. If two tool calls advance the simulator, record their actual order. Do not describe sequential readings as simultaneous.

For example, infrastructure sees a slow database link. Application finds a recent deployment but no evidence that it caused the delay. The lead asks for one observation that separates those explanations. A majority vote or two copies of the same alert add no evidence.

For the demo, compare a complete handoff with one missing the application finding. The link reading alone cannot identify a change to roll back. Show which finding the lead accepted, which it lacked, and why it sought evidence or handed over.

Allow one follow-up across both specialists for a missing, conflicting, timed-out, or invalid finding. A format repair counts as that follow-up. If the remaining evidence supports a decision, the lead can proceed within its authority. Otherwise use the same operator handoff as the single agent. A missing reply never means “healthy.”

Only the lead sends an authorized intent to the executor. It obtains fresh readings after the effect and cites them in the final report. The comparison counts the specialists' calls and tokens against the same shift budget as the single agent.
