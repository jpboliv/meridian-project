# Prompt structure

![Proposed flow](../flows/prompts.svg)

A prompt tells the agent what to do. A ticket describes what someone saw. If a ticket says to restart a service, those words do not give the agent permission.

Draft for owner review · [Issue 4](https://github.com/jpboliv/meridian-agents/issues/4).

Build each request from named sections in this order:

1. Common rules, role, and required report fields.
2. Allowed tools in a fixed order, with their inputs and outputs.
3. The incident brief, team scope, and any eligible lessons for this trial.
4. The investigation so far, with a source and time on each observation.
5. Current time, remaining budget, and changes since the last call.

The first two sections come from reviewed project files. A quote in a ticket stays in the evidence section with the ticket ID. Text from tickets, logs, tools, or lessons cannot change the rules. The lead agent and specialists share the common rules. Each role receives only the tools it needs.

Record the prompt ID, revision, role, model, tool catalog revision, and token count for each section. A token is a unit of model input or output. Record a fingerprint of each section and the name of the first section that changed. A matching fingerprint shows identical text. Only the provider can report a cache hit.

Keep unchanged sections byte-for-byte stable. Sort tool definitions and field names. Put clocks and request IDs at the end. For an ordinary update, append the new value and name the value it replaces. At the next summary, keep only the current value. If a source disappears, access changes, or advice needs a correction, rebuild before the next call.

The final report names the incident, status, affected target, observations with sources, actions with receipt IDs, uncertainty, and next step. Use `recovered`, `mitigated`, `needs_operator`, or `denied`. A completed restart alone cannot support `recovered`. `mitigated` requires observed improvement and states what remains unresolved.

Code validates the report fields and evidence references. For an invalid model response, allow one repair within the shift budget. Give the model the field error and the available evidence. If repair fails, return a handover from the known facts. A repair cannot replay an action. Compare revisions on the same cases before adopting a change.
