# Cache policy

![Proposed flow](../flows/caching.svg)

A runbook gives instructions for a service. Before reusing a saved copy, make sure that it covers the current version and the reader can access it.

Draft for owner review · [Issue 7](https://github.com/jpboliv/meridian-agents/issues/7).

The class deep dive compares provider prompt caching with a changing timestamp at the start or end of each request. Use fresh readings in both versions. Application caches for tool results and summaries are optional and stay off for this experiment and the separate memory comparison.

A cache is a temporary copy of an earlier result. A hit means that the system used the copy instead of reading its source again.

| Reuse | Decision and expiry |
|---|---|
| Start of a model request | Keep common instructions and permitted tools in a stable order. Let the provider control expiry. Cached input still uses space. Correctness cannot depend on a hit. |
| Source result | Cache only a specific runbook revision for the shift. Match its applicability to the current component version on every use. Fetch again on any revision, access change, or shift end. |
| Evidence summary | Reuse within one incident and shift only. Require the same ordered source IDs and revisions, reader scope, summary rules, and model revision. Invalidate on correction, deletion, or access change. |
| Completed answer | Do not reuse diagnoses, action recommendations, approvals, or recovery reports. The same words can refer to a different incident or reader. |

For each application entry, use the trial, environment, team, reader permissions, policy revision, operation, and normalized arguments as its key. Include the source and component revisions for runbooks. For summaries, include the incident, source list, and summary recipe. If a required version or access decision is unavailable, do not serve the copy.

Read live metrics, link state, action status, and approval status from their owners. After a change, read new evidence before another decision. A ticket with the same wording does not make the previous answer current.

Count one logical simulator read the same way on a hit and a miss. Advance both by the case's `ticks_per_action` exactly once. A hit saves a source read. It does not freeze the exchange or turn an old sample into a new one. Provider prompt reuse has no effect on simulated time.

Record hit or miss, age, versions, invalidation reason, source calls, and elapsed time. Record provider cache reads and writes only if the provider reports them. In the Session 9 comparison, change one fact or one reader role while keeping the question identical. Neither case can reuse an old answer.
