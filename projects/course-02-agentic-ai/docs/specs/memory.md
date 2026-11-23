# Memory lifecycle

Implementation state: partial and offline, merged in PR #36 at `34ab7b8`. Scoped retrieval, condition fit, ranking, clues and notes at close run in the offline shift flow. So does the in-shift check of restart claims: a sourced earlier fall withdraws a precise temporal claim and only flags a broad causal one. Deletion is shown in traces between shifts. Procedure approval, published editions, clue review and reader changes are tested only as library functions. Persistence and the operator handoff for a blocking conflict are outstanding; neither is reachable in the M2 trials ([#17 audit](../experiments.md#14-and-15-audit)). See [what is integrated](../experiments.md#what-is-integrated-what-is-library-only-and-what-is-outstanding). The [#17 handover study](../experiments.md#2026-11-23-m2-handover-comparison-prepared-offline) records reminder exposure per decision and scores a stored correction separately from the next shift.

State: **Agreed** for M2 · [Owner sign-off, 23 November](https://github.com/jpboliv/meridian-project/issues/6#issuecomment-7105048143).

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

## Agreed: who can receive a lesson

A lesson is team-only by default. Apply the same rule to search, direct reads by ID, automatic handover, and cached notes. Do not expose the existence of another team's private lesson.

For example, a database operator cannot receive a gateway lesson that cites a private gateway log. To share it, the owning operator approves a separate edition for the named team. That edition needs evidence the recipient can read and no private excerpts. If its evidence disappears, apply the same deletion rule.

## Agreed: what a diagnostic clue must contain

At shift close, save a proposed clue only if it names its source, the observation time, the affected component or instance, and a condition the next shift can check. For example, a clue to compare gateway instances must cite the original timed observation and say that the comparison requires a reading for each instance. If the observation time is missing, do not save the clue.

## Agreed: when a diagnostic clue expires

After seven simulated days without review, stop suggesting the clue to new shifts, even if its source still exists. Keep the incident as history under the existing access and deletion rules. Suggest the clue again only after someone reviews its evidence and confirms that its condition still applies.

## Agreed: when a shift note expires

A shift note expires after the next handover or 24 simulated hours from creation, whichever comes first. For example, pass “read instance 2 next” to the incoming shift once. If the note is already 24 hours old, omit it. If the work is still open at a later handover, write a fresh note.

## Agreed: when an agent can propose a team procedure

At least two independent incidents must support the proposed procedure. A ticket and a handover about the same outage count as one incident: they may support a diagnostic clue, but they do not show recurrence. Once the threshold is met, the agent may submit a proposal. An operator must approve it before the team uses it as a procedure.

## Agreed: what procedure approval covers

The operator approves the exact text, scope, version, and review date together. If any of these changes, obtain fresh approval before using the changed procedure. For example, adding the database team to a gateway-only procedure changes its scope even if the steps stay the same.

## Agreed: when to stop using a procedure

Stop using a procedure if it expires, an operator revokes it, or a change makes it incompatible. After an upgrade, check what the procedure requires. If only a fleet average remains, stop using a procedure that compares individual gateway instances. If the individual readings remain available, the version change alone does not disqualify it.

## Agreed: how to rank eligible lessons

Among eligible lessons the requester can read, rank first by component match, then by fit to current conditions. If both match equally well, prefer the more recent supporting observation. For example, when two gateway clues fit the component, an older clue that better matches today's symptoms comes first.

## Agreed: who can save and retrieve a lesson

Filter by the actual requester and source access before ranking results.

Save observations during the incident. At shift close, the lead agent proposes an incident record and any diagnostic clue. Apply the [agreed clue requirements](#agreed-what-a-diagnostic-clue-must-contain). A worker checkpoint resumes unfinished work in that incident; it is not a lesson, an action receipt, or evidence for a later incident. Correct a directly contradicted claim as soon as the evidence arrives. Do not wait for shift close to remove bad advice.

| Record | What can support it | When to stop using it |
|---|---|---|
| Incident record | A dated observation or action receipt with its origin | Use it only as history. Remove content when its source is deleted. |
| Shift note | Open work, missing evidence, and the next read | Follow the [agreed shift-note expiry rule](#agreed-when-a-shift-note-expires). |
| Diagnostic clue | At least one documented incident, an author, a team, and a testable condition | Follow the [agreed expiry rule](#agreed-when-a-diagnostic-clue-expires). A new deployment triggers a condition review. |
| Approved procedure | Apply the [proposal threshold](#agreed-when-an-agent-can-propose-a-team-procedure) and obtain [operator approval](#agreed-what-procedure-approval-covers). | Follow the [agreed stop conditions](#agreed-when-to-stop-using-a-procedure). A procedure never grants permission for a particular action. |

Record whether the source was a person, tool, document, or agent inference. Label a reported symptom as reported. An executor receipt supports an action. A reading supports an observation. A high confidence score cannot turn copied ticket text into a procedure.

Apply the [agreed ranking](#agreed-how-to-rank-eligible-lessons) after filtering. Allow a scoped search beyond the two handover clues. Display source, age, condition, and uncertainty. Skip expired, superseded, or withdrawn advice.

Classify evidence against a specific claim. A direct contradiction permits a factual correction. A possible conflict stays flagged until an independent source settles it. An unsupported concern does not withdraw advice. Record `withdrawn_at`, reason, and source references together when withdrawing advice. Deletion takes precedence over historical references.

When access changes or a source is deleted, stop serving affected copies before the next read or model call. Rebuild summaries from retained sources or withhold them. Apply this to saved handovers, the searchable history, cache entries, and restored work. Keep only a restricted deletion record with ID, time, actor, and reason. It contains no deleted text and cannot serve as evidence.
