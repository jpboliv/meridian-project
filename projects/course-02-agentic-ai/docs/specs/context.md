# Context selection

![Proposed flow](../flows/context.svg)

When many log lines repeat the same error, summarize them. Keep the unusual line and a link to the original log.

Draft limits for owner review · [Issue 5](https://github.com/jpboliv/meridian-agents/issues/5). The handover rule below is Agreed.

## Agreed: shortening a shift handover

If leaving out a fact can change the next shift's decision, keep it in the handover. Link each such fact to its source. State what the evidence leaves unknown. Keep repeated readings and the full action log available on demand while the reader has access.

In the [restart example](../cases/restart/handover.md), recovery began before the restart. Include both times so the next shift can establish the order and read either source. Use fresh readings to decide how to handle the new alert.

If the handover mentions a corrected claim, put the correction and its evidence in the same note. With a link alone, the next shift can act before it sees the correction. If the pair will not fit, omit the old claim. Keep the retained history available on request.

To test shortening, set a limit too small for the corrected note. The old claim must not appear alone. If an existing test already proves that whole notes stay together, use that test. No separate shift simulation is needed.

## Draft: how much the agent receives

Start with the incident ID, caller, alert, time, and the selected role's tools. Add at most two eligible clues in the automatic handover trial. Load original readings on request. Start with the affected service. Follow an unusual log line or a slow link to its dependency. A summary gives the exact source ID and the range of records to reopen.

Use these starting limits for each version. The harness owns the total. The first comparison will show whether these limits leave room for decisive evidence.

| Limit | Starting value | Reason |
|---|---|---|
| Per shift, including specialists, summaries, and retries | 20 model calls and 40,000 cumulative input tokens | Match the course runner's default call limit and the Session 2 input budget. |
| Per call | 7,000 input tokens and 1,000 output tokens, or less if the model requires it | Leave room for the answer. |
| Input allocation | 1,600 for rules and tools, 600 for the brief and lessons, 4,500 for evidence and history, 300 for current notes | Expose which section displaced a useful reading. |
| When to shorten | Before the next request passes 6,000 input tokens | Leave room for a summary request and its answer. |

Count tokens before sending a request. If a large result arrives, store the permitted source and pass a bounded excerpt. Keep up to 1,000 recent tokens verbatim within the history budget. Preserve exact option labels, targets, conditions, and approval references whenever the next reply can refer to them.

Address the summary to a successor who cannot see the previous messages. Keep the current decision, decisive observations, conflicting facts, gaps, action receipts, and the next useful read. Keep times and sources together. Group repeated log lines by signature and count. Keep the unusual line with its original wording and source.

Use the same model for the first summary comparison. A cheaper model can cost more if it must read the entire history again. Count summary input, output, and later reads. When the harness shortens a conversation, refresh the lessons and remove outdated copies. A permitted reader can search the retained history by source. Apply deletion and access rules each time.

If space is tight, drop duplicates, then optional history. Never truncate an approval condition or split a disputed claim from its correction. If the agent still lacks room for a supported decision, stop and hand over. If no model call remains, the harness reports the available readings, missing evidence, and next step itself.
