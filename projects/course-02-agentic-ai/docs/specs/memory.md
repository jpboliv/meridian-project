# Memory lifecycle

![Proposed flow](../flows/memory.svg)

We agreed to keep two records. The incident record says what happened. The lesson tells the next shift what to check. Today’s readings determine whether the same fix fits.

## Agreed handover evidence

Name the affected component or instance. Give the readings and their times. Link each observation to its source and each action to its executor record. Describe what happened afterward. Include missing or conflicting evidence when it changes the conclusion.

One documented incident can support a clue about what to check next. Link the clue to its incident record and say when it applies. Recovery after an action, by itself, does not prove that the action caused recovery.

## Agreed: when a lesson applies

A version change prompts a check. It does not, on its own, disqualify a lesson. Name the condition the lesson needs and check it against current evidence.

“Compare memory across instances” requires a reading for each instance. If those readings are available, compare them. If only a fleet average is available, seek another source or leave individual memory use unknown. A normal average does not establish that every instance is healthy. If individual readings are unavailable, skip this comparison. Keep the lesson for future shifts.

Compare observable work: which sources the agent reads, in what order or batches, and which action it takes or recommends. A mention of the lesson in the final explanation does not, by itself, show a change in behavior.

## Agreed: who can correct a shared lesson

If sources directly contradict a specific factual claim, the agent can correct it without operator approval. Preserve the original record and attach the reason and sources to the correction. For example, the [10:02 latency drop](../cases/restart/latency.md) preceded the [10:05 restart](../cases/restart/actions.md). The restart did not start recovery. Its later effect remains unknown.

If the evidence is ambiguous, flag the uncertainty and do not rely on the disputed claim for the current decision. If that blocks a live decision, use the existing [operator handoff rule](../reference-incident.md#when-a-reading-is-missing). Changing what the team is authorized or instructed to do, including an approved procedure, requires operator approval.

## Agreed: when a source is deleted

Remove its links and copied material from saved lessons, summaries, and handovers. Do not serve stale copies from lookup or cache. If a retained source supports the claim, cite that source. Otherwise stop presenting the claim as verified. A summary of the deleted source is not independent evidence.

If the team deletes the action log, the latency record still shows the start of recovery at 10:02. Without another record of the restart time, the next shift cannot establish which event came first. Deletion does not reinstate the claim that the restart fixed the delay.

## Draft: who can save and retrieve a lesson

Draft for owner review · [Issue 6](https://github.com/jpboliv/meridian-agents/issues/6). A lesson is team-only by default. Apply the same rule to search, direct reads by ID, automatic handover, and cached notes. Filter by the actual requester and source access before ranking results. Do not expose the existence of another team's private lesson.

For example, a database operator cannot receive a gateway lesson that cites a private gateway log. To share it, the owning operator approves a separate edition for the named team. That edition needs evidence the recipient can read and no private excerpts. If its evidence disappears, apply the same deletion rule.

Save observations during the incident. At shift close, the lead agent proposes an incident record and any diagnostic clue. The harness admits a clue only if its source, time, subject, and condition are available. Correct a directly contradicted claim as soon as the evidence arrives. Do not wait for shift close to remove bad advice.

| Record | What can support it | When to stop using it |
|---|---|---|
| Incident record | A dated observation or action receipt with its origin | Use it only as history. Remove content when its source is deleted. |
| Shift note | Open work, missing evidence, and the next read | After the next handover or 24 simulated hours, whichever comes first. |
| Diagnostic clue | At least one documented incident, an author, a team, and a testable condition | After seven simulated days without review, remove it from active recall. A new deployment triggers a condition review. |
| Approved procedure | The agent can propose a procedure after two independent incidents. An operator approves its text, scope, version, and review date. | On expiry, revocation, or an incompatible change. A procedure never grants permission for a particular action. |

Record whether the source was a person, tool, document, or agent inference. Label a reported symptom as reported. An executor receipt supports an action. A reading supports an observation. A high confidence score cannot turn copied ticket text into a procedure.

Among eligible lessons, rank by component, agreement with current conditions, then the date of the supporting observation. Allow a scoped search beyond the two handover clues. Display source, age, condition, and uncertainty. Skip expired, superseded, or withdrawn advice.

Classify evidence against a specific claim. A direct contradiction permits a factual correction. A possible conflict stays flagged until an independent source settles it. An unsupported concern does not withdraw advice. Record `withdrawn_at`, reason, and source references together when withdrawing advice. Deletion takes precedence over historical references.

When access changes or a source is deleted, stop serving affected copies before the next read or model call. Rebuild summaries from retained sources or withhold them. Apply this to saved handovers, the searchable history, cache entries, and restored work. Keep only a restricted deletion record with ID, time, actor, and reason. It contains no deleted text and cannot serve as evidence.
