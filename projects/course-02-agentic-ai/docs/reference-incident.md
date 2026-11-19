# Reference incident

Draft case plan · [Issue 2](https://github.com/jpboliv/meridian-agents/issues/2). The owner agreed on the shift inputs and missing-reading rule. The [three-shift simulator rehearsal](experiments.md#three-shifts-without-memory) used scripted decisions and a fresh start each shift. The live model and memory comparisons have no results yet.

1. A gateway instance slows down. The operator authorizes a mitigation and records which readings confirmed recovery.
2. The symptoms return on a different instance. Recall suggests where to look. The agent must identify the affected instance from fresh observations.
3. After a deployment, the same alert has a different cause. The agent must explain which observation rules out the previous fix.

## Agreed handover

Start each shift with a fresh conversation and the same alert: “The order gateway is slow.” Each version can request current readings. Compare no prior lesson, lesson lookup, and the same lesson supplied at handover. Only the evaluator sees the known cause and expected outcome. Between independent trials, reset the simulator, memory, and cache to the same starting state.

The incident record says what happened: “Memory use rose on gateway instance 2. After its restart, latency returned to normal.” The lesson says what to check next: “When the gateway slows down, compare memory use across instances.”

On the third shift, memory use is normal across the gateway instances and the database link is slow. Keep the first incident record. Use the fresh readings to investigate the link.

For the first delivery comparison, use the runbook alone and the same runbook with the reminder in the handover. Keep lookup as a follow-up comparison. In the separate correction case, still check both delivery paths for stale advice.

## When a reading is missing

If the incident cannot wait, hand it to the operator immediately. Otherwise, retry a timed-out read once. If access is denied, skip the retry.

If the reading is still missing, consult one independent source the agent can access. Use fresh evidence that changes the investigation. An old reading or another copy of the alert adds no evidence about the cause.

If the cause remains unclear, leave the gateway running. Tell the operator what the agent saw, which reading was missing, and what to read next. Record the gap without saving a lesson about the cause.

Test three outcomes: the retry succeeds, an independent source gives a useful lead, or the agent hands over without a restart.

## Agreed: a healthy reading from before the alert

Case E is a separate failure branch. At 10:00 the gateway slows down. Its monitor still answers, but the last healthy sample is from 09:00. Keep the sample time distinct from the time of the tool call. Do not use it to establish current health or authorize a restart. Consult the independent link monitor. Hand over the degraded gateway-to-database link with its fresh source reading. Do not declare recovery or change the exchange.

## The wrongly credited restart

Start this case with a saved lesson: “Restarting the gateway fixed the delay.” A later review gives the agent two sources. Latency started falling at [10:02](cases/restart/latency.md). The action log records the restart at [10:05](cases/restart/actions.md).

The agent must keep both facts and correct the lesson. The restart cannot explain the start of recovery. The evidence does not establish what caused recovery or whether the restart helped later.

On the next shift, give the agent the same alert and normal gateway memory readings. Test both ways of getting the lesson: lookup and automatic handover. For each trial, start from the same original lesson and replay the correction before the alert.

Score two outcomes separately. First, the active lesson cites the timing evidence and no longer calls the restart a proven fix. Second, the next shift gets the correction, reads current evidence, and does not restart the gateway on the strength of the old claim. Inspect the handover, source reads, and action log as well as the final report.

## Draft: what the shift receives

Give the investigator the incident ID, the alert text, its time, and the caller's role. Use a fresh conversation and the case's new simulator state each shift. Carry only the memory allowed by that trial. Keep fault definitions, scenario filenames that reveal the cause, pass conditions, and future shifts out of the prompt.

On shift one, use a gateway alert and a related ticket. They describe one incident. The evidence for a targeted restart comes from current instance readings. On shift two, change the affected instance. A restart of yesterday's target fails the case even if service later improves.

On shift three, supply normal instance readings and a slow database link. The useful result is a source-backed change of direction. Without evidence for a specific database change, investigate or hand over. Do not infer a rollback from the slow link.

For the failure branch, vary only the source response. The retry succeeds, a second source gives a lead, or neither supplies usable evidence. Treat a decision as urgent when the operator marks it urgent or another read cannot finish by the incident deadline. Use the existing operator handoff. Record the missing evidence and the next useful read. Keep these expected outcomes with the evaluator.
