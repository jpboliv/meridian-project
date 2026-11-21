# Information ownership

Draft for owner review · [Issue 3](https://github.com/jpboliv/meridian-project/issues/3).

Alert → select evidence → investigate → authorize a specific action → execute once → measure again → report.

The harness is the software that runs the agent. It builds the model input, decides which tools to expose, and stops the run. The model can request a read or propose a change. Code controls what reaches the model and what the executor can do.

| Record | Who owns it | What it answers |
|---|---|---|
| Instructions and tool definitions | The project maintainer versions them. The harness selects them by role. | What task and tools can this agent use? |
| Observations | Monitoring, tickets, and deployments own their records. The harness gives authorized readers a source ID, target, time, and unit where relevant. | What did this source report, and when? |
| Context and working state | The harness builds each model input. The lead agent proposes updates to the open incident. | What does this shift know? What evidence is missing? |
| Memory | The team owns its incident records and lessons. The memory policy controls writes, reads, corrections, and deletion. | What can a later shift use as a clue? |
| Cache | The harness owns temporary copies. It can discard them at any time. | Can this reader reuse this exact result now? |
| Checkpoint and receipt | The worker saves unfinished steps. The executor records each action and its outcome. | Where did work stop? Did the action already happen? |
| Evaluation | The evaluator reads the hidden case and actual simulator effects after a run. | Did the decision, the evidence, and the effects meet the case? |

The course runner makes model calls. Local MCP servers provide service readings. The supplied executor applies actions. Use SQLite for team memory and durable work records. Keep work records separate from lessons.

If a checkpoint says “pending” and the executor records a completed restart, the receipt establishes that the restart happened. Only new readings can establish recovery.

One simulator tick is one simulated minute. Tools advance the clock according to the case. Model response time does not advance it. Local services and synthetic failure cases allow repeatable reads without live exchange access. If the model service fails, save the available evidence and hand over. Do not invent a model result.

## Tool boundary

The course simulator is the starting point. Add project tools to expose observations an operator could obtain. Change the simulator itself when a case needs behavior it cannot represent. Keep the injected cause and expected decision with the evaluator. For the timestamp comparison, run both layouts against the same simulator revision and tool catalog so that only the layout changes.

Use the Session 3 MCP integration against the same simulator as the executor. Pin the allowed server, publisher, tool revision, input fields, and reader scope. The investigator can use `tickets.search_issues`, `monitoring.get_instance_datapoints`, and `deployments.list_deployments`. A changed or unknown tool definition stays out until review.

Code accepts a reading only if its fields match the contract. Preserve the distinction between an instance value and a fleet average. Add the observation time and source reference from the call record when the source omits them. Reject a payload that names another target or cannot support the requested reading. Treat it as missing evidence.

Correlate the alert and ticket using the component, overlapping time, and matching symptom or an explicit incident reference. A nearby ticket about another component stays separate. Use ticket text as a lead. It cannot authorize a write.
