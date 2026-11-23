# Interruption and resume

![Proposed flow](../flows/execution.svg)

If the agent loses the reply to a restart request, it reads the action record. The restart can succeed even when the reply never arrives.

State: **Agreed** for M3 · [Owner sign-off, 23 November](https://github.com/jpboliv/meridian-project/issues/11#issuecomment-7116373196).

A checkpoint records unfinished work. A receipt records the executor's result. Before dispatch, save the incident, step, caller, target, action, parameters, stable action key, approval reference, evidence references, and remaining budget. Save the intent before the executor can act. Write each checkpoint as one complete update.

One intended effect gets one key across retries and workers. Tie the key to the incident and recorded intent. Bind the action and parameters to it. A different target requires a new decision and approval. Do not let a model invent a new key after a timeout.

The demonstration stops the incident worker. The simulated exchange keeps running. The supplied executor keeps receipts in memory. It stays in the surviving simulation process. A new worker can then compare its saved step with the executor's record. Restarting the entire simulator erases that evidence.

| What the executor can establish | What the replacement worker does |
|---|---|
| The matching action completed | Record its receipt. Do not send it again. Read fresh service measurements to assess recovery. |
| The executor rejected the action or reports a key conflict | Stop the write. Record the reason and request a decision if further action is necessary. |
| The authoritative executor confirms no effect and no request still in flight | Reassess current need, permission, and approval. If all still hold, allow one dispatch using the original key. |
| The ledger is missing, unavailable, or cannot distinguish an absent request from a pending one | Leave the outcome unknown. Hand over without a second dispatch. |

Rebuild the working context using current access and retained sources. Do not restore expired approvals or deleted material from the checkpoint. If access no longer permits verification, record the gap and hand over. Do not infer recovery from an old receipt.

For the demonstration, interrupt the worker after the executor applies a restart but before the worker saves the receipt. Start a new worker on the same incident and ledger. Count applied effects rather than calls. Success requires one restart, the original receipt, and a recovery statement consistent with the new readings.
