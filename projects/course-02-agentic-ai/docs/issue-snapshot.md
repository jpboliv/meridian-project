# Meridian issue snapshot

This snapshot preserves the discussions and issue numbers from 19 November 2026. Links lead to the [current tracker](https://github.com/jpboliv/meridian-project/issues). Original issue 1 is now [#22](https://github.com/jpboliv/meridian-project/issues/22); issues 2 through 21 kept their numbers. This dated snapshot is not the last full generated report. That report kept changing after 19 November; its last complete version, including `gateway-m1.5` and the unread-replica case, is preserved at [commit 71ef095](https://github.com/jpboliv/meridian-project/blob/71ef095ad8d5e80d54a782732cbc795e2a1192b6/projects/course-02-agentic-ai/docs/decision-report.html). [decision-report.html](decision-report.html) is now only a pointer to that commit and to the [presentation report](relatorio.md). The specifications beside this file are the current sources.

## [1: Define learning objectives and success criteria](https://github.com/jpboliv/meridian-project/issues/22)

Open · 0 — Design foundation

#### Goal

What must the owner understand and demonstrate at the end of this project?

#### Deliverable

Update [project.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/project.md) and link the evidence or decision here.

The current specification is a draft. Record owner agreement before marking it Agreed.

#### Dependencies

None. This is the first design discussion.

#### Acceptance criteria

- [ ] Agree on the primary question about memory, context, caching, and changing evidence.
- [ ] Map every minimum course requirement to a milestone and observable evidence.
- [ ] Define core scope and optional experiments. The owner confirmed the submission deadline: 30 November 2026 at 23:59 Lisbon time (`Europe/Lisbon`).
- [ ] Record the owner review and resolve or explicitly defer each open question.

#### Course references

- [projects/course-02-agentic-ai/README.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/README.md)
- [sessions/course-02-agentic-ai/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/README.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

### Discussion

[2026-11-19 · jpboliv](https://github.com/jpboliv/meridian-project/issues/22#issuecomment-7064330185)

19 November specification review · Draft for owner review.

The report maps the course requirements to M1, M2, and M3 and gives the short explanation for Luís. Keep the same three-shift incident through the milestones. Use 29 November at 18:00 Europe/Lisbon as the internal target. The brief gives 30 November at 23:59 but does not state the submission time zone.

Course project: `docs/project.md`. The consolidated review is in `docs/decision-report.html`.

## [2: Specify the reference incident across multiple shifts](https://github.com/jpboliv/meridian-project/issues/2)

Open · 0 — Design foundation

#### Goal

How can one incident sequence show useful recall, changed conditions, correction, and handover?

#### Deliverable

Update [reference-incident.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/reference-incident.md) and link the evidence or decision here.

The current specification is a draft. Record owner agreement before marking it Agreed.

#### Dependencies

- #1: Define learning objectives and success criteria

#### Acceptance criteria

- [ ] Describe first discovery, recurrence, changed environment, and corrected handover.
- [ ] Separate facts visible to agents from expected outcomes used by the evaluator.
- [ ] Define controlled failures and the state reset between independent trials.
- [ ] Agree on the story before creating scenarios.

#### Course references

- [sessions/course-02-agentic-ai/04-memory/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/04-memory/README.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

### Discussion

[2026-11-17 · jpboliv](https://github.com/jpboliv/meridian-project/issues/2#issuecomment-7064309411)

Agreed in 1de741b: keep an incident record of what happened and a separate lesson about what to check next. On shift three the original record stays true; normal gateway memory and a slow database link point elsewhere. The evidence-unavailable case is still open.

[2026-11-17 · jpboliv](https://github.com/jpboliv/meridian-project/issues/2#issuecomment-7064309542)

Agreed missing-reading rule in 47cde53: retry a timeout once, skip retry after denial, then consult one authorized independent source if time permits. If the cause remains unclear, hand over without a restart or a new causal lesson. Next: define shift inputs and evaluator-only facts.

[2026-11-17 · jpboliv](https://github.com/jpboliv/meridian-project/issues/2#issuecomment-7064309611)

Added the wrongly credited restart as a planned case in db1dd80. Score the saved correction separately from what the next shift reads and does. Replay it with both lookup and automatic handover.

[2026-11-19 · jpboliv](https://github.com/jpboliv/meridian-project/issues/2#issuecomment-7064309699)

19 November specification review · Draft for owner review.

Define the operator brief and the evaluator-only facts separately. Replay the same alert against the first instance fault, the recurrence on another instance, and the slow database link. Vary only the missing-source response in the failure branch. Keep the previously agreed handover and reset rules.

Course project: `docs/reference-incident.md`. The consolidated review is in `docs/decision-report.html`.

## [3: Define architecture and information ownership](https://github.com/jpboliv/meridian-project/issues/3)

Open · 0 — Design foundation

#### Goal

Where do instructions, evidence, working state, memory, cache entries, and checkpoints live?

#### Deliverable

Update [architecture.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/architecture.md) and link the evidence or decision here.

The current specification is a draft. Record owner agreement before marking it Agreed.

#### Dependencies

- #1: Define learning objectives and success criteria
- #2: Specify the reference incident across multiple shifts

#### Acceptance criteria

- [ ] Draw the main flow and identify the owner of each information type.
- [ ] Define module boundaries and reuse of the supplied Meridian platform.
- [ ] Distinguish agent-visible observations from evaluator-only simulator state.
- [ ] Record assumptions about time, persistence, and external services.

#### Course references

- [meridian/agent_runtime.py](https://github.com/jpboliv/meridian-project/blob/main/meridian/agent_runtime.py)
- [meridian/memory.py](https://github.com/jpboliv/meridian-project/blob/main/meridian/memory.py)
- [sessions/course-02-agentic-ai/08-agents-in-production/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/08-agents-in-production/README.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

### Discussion

[2026-11-19 · jpboliv](https://github.com/jpboliv/meridian-project/issues/3#issuecomment-7064319877)

19 November specification review · Draft for owner review.

The source owns its observation, the executor owns the effect receipt, and the worker owns its checkpoint. Reuse the local course MCP servers, simulator, runner, and SQLite memory. Give the agent only validated public observations. Keep expected outcomes and actual effect counts with the evaluator.

Course project: `docs/architecture.md`. The consolidated review is in `docs/decision-report.html`.

## [4: Specify prompt structure and versioning](https://github.com/jpboliv/meridian-project/issues/4)

Open · 0 — Design foundation

#### Goal

How are stable instructions, task inputs, retrieved data, and output contracts assembled and versioned?

#### Deliverable

Update [specs/prompts.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/specs/prompts.md) and link the evidence or decision here.

The current specification is a draft. Record owner agreement before marking it Agreed.

#### Dependencies

- #3: Define architecture and information ownership

#### Acceptance criteria

- [ ] Define instruction layers and trust boundaries for external text and memories.
- [ ] Define prompt identifiers, revisions, and run metadata.
- [ ] Define how invalid structured output produces a bounded retry or controlled result.
- [ ] Explain prefix stability for provider caching without assuming cache availability.

#### Course references

- [sessions/course-02-agentic-ai/01-agent-harness/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/01-agent-harness/README.md)
- [sessions/course-02-agentic-ai/05-security/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/05-security/README.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

### Discussion

[2026-11-19 · jpboliv](https://github.com/jpboliv/meridian-project/issues/4#issuecomment-7064320456)

19 November specification review · Draft for owner review.

Use named, versioned sections with stable rules and sorted allowed tools first. Put ordinary updates last. Record the first section that changed. Rebuild immediately for deletion, lost access, or corrected advice. Permit one bounded output repair without replaying an action.

Course project: `docs/specs/prompts.md`. The consolidated review is in `docs/decision-report.html`.

## [5: Specify context selection, budgets, and compression](https://github.com/jpboliv/meridian-project/issues/5)

Open · 0 — Design foundation

#### Goal

Which evidence reaches each model call, and what survives when the context grows?

#### Deliverable

Update [specs/context.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/specs/context.md) and link the evidence or decision here.

The current specification is a draft. Record owner agreement before marking it Agreed.

#### Dependencies

- #3: Define architecture and information ownership
- #4: Specify prompt structure and versioning

#### Acceptance criteria

- [ ] Define initial context, on-demand retrieval, and role-specific tool exposure.
- [ ] Define budgets and behavior when evidence does not fit.
- [ ] Preserve evidence references, contradictions, uncertainty, and action receipts through compression.
- [ ] Define how to retrieve original evidence and measure information lost by compression.

#### Course references

- [sessions/course-02-agentic-ai/02-context-tools-skills/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/02-context-tools-skills/README.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

### Discussion

[2026-11-18 · jpboliv](https://github.com/jpboliv/meridian-project/issues/5#issuecomment-7064320942)

Owner agreed on the handover rule: keep facts inline if omitting them could change the next decision, and link each to its original source. One fresh, read-only shift verified the 10:02 latency drop and 10:05 restart, left the later effect unresolved, and recommended investigating the currently slow database link. This was a fixture trial with an explicit source-check request, not a simulator run. Recorded locally in specs/context.md and docs/experiments.md under the course project. Budget overflow remains open.

[2026-11-18 · jpboliv](https://github.com/jpboliv/meridian-project/issues/5#issuecomment-7064321089)

Agreed for shortened handovers: if a note includes a corrected claim, include the correction and its evidence in that same note. If they cannot fit together, omit the old claim from the handover and retain the full history on demand. This prevents the next shift from acting on stale advice before opening a separate correction. The earlier read-only trial did not test the overflow case.

[2026-11-18 · jpboliv](https://github.com/jpboliv/meridian-project/issues/5#issuecomment-7064321173)

Verification scope: no separate restart simulation for overflow. Once shortening exists, inspect the output at a limit too small for the corrected note. Reuse existing coverage if it already proves whole notes are kept or dropped.

[2026-11-19 · jpboliv](https://github.com/jpboliv/meridian-project/issues/5#issuecomment-7064321269)

19 November specification review · Draft for owner review.

Draft limits: 20 model calls and 40,000 input tokens per shift across roles. Reserve 1,000 output tokens per call and shorten before the next input exceeds 6,000 tokens. Preserve exact targets, sources, approval conditions, receipts, and uncertainty. Hand over when the required evidence cannot fit.

Course project: `docs/specs/context.md`. The consolidated review is in `docs/decision-report.html`.

## [6: Specify memory creation, retrieval, correction, and deletion](https://github.com/jpboliv/meridian-project/issues/6)

Open · 0 — Design foundation

#### Goal

What deserves to be remembered, when is it applicable, and how is it corrected?

#### Deliverable

Update [specs/memory.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/specs/memory.md) and link the evidence or decision here.

The current specification is a draft. Record owner agreement before marking it Agreed.

#### Dependencies

- #3: Define architecture and information ownership
- #2: Specify the reference incident across multiple shifts

#### Acceptance criteria

- [ ] Define memory kinds, provenance, evidence requirements, and applicability conditions.
- [ ] Define trust and expiry policy, conflict handling, and procedure approval.
- [ ] Define scoped retrieval and removal of deleted content from derived data.
- [ ] Define stale-memory, poisoned-memory, conflicting-memory, and cross-team cases.
- [ ] Keep long-term memory separate from incident checkpoints.

#### Course references

- [meridian/memory.py](https://github.com/jpboliv/meridian-project/blob/main/meridian/memory.py)
- [sessions/course-02-agentic-ai/04-memory/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/04-memory/README.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

### Discussion

[2026-11-17 · jpboliv](https://github.com/jpboliv/meridian-project/issues/6#issuecomment-7064321755)

Agreed handover evidence in ebbbdb7: retain timestamped observations, sources, the action receipt, and any uncertainty that changes the conclusion. One documented incident can justify a diagnostic clue. Recovery after an action alone does not establish cause. Lesson applicability remains open.

[2026-11-18 · jpboliv](https://github.com/jpboliv/meridian-project/issues/6#issuecomment-7064321982)

Agreed: check a lesson’s observable prerequisite after a version change; skip it locally if unmet, without withdrawing the lesson. Ran four fresh read-only shifts crossing lesson/no lesson with per-instance readings/fleet mean only. Both fleet-only shifts left individual memory unknown. All four read the same three sources and recommended investigating the database path. No observed benefit on these measures; one run per condition with sources named up front. Recorded in the memory spec, experiment log, status and decision report.

[2026-11-19 · jpboliv](https://github.com/jpboliv/meridian-project/issues/6#issuecomment-7064322089)

Agreed on 19 November: an agent may correct a specific factual claim when sources directly contradict it. Preserve the original record and attach the reason and sources. Flag ambiguous claims and avoid relying on them; reuse the existing operator handoff if uncertainty blocks a live decision. Changes to team permissions or procedures require operator approval.

[2026-11-19 · jpboliv](https://github.com/jpboliv/meridian-project/issues/6#issuecomment-7064322243)

Agreed deletion rule: remove dead citations and copied material from lessons, summaries, and handovers; lookup and cache must not serve stale copies. Retain a claim as verified only with surviving independent support. Losing the restart action log leaves the latency observation intact but does not establish the event order or revive the old fix.

[2026-11-19 · jpboliv](https://github.com/jpboliv/meridian-project/issues/6#issuecomment-7064322359)

19 November specification review · Draft for owner review.

Lessons default to the owning team across lookup, handover, and cache. Cross-team publication requires an approved edition with evidence the recipient can read. Specify origin, expiry by record kind, scoped ranking, and deletion before the next read. Earlier owner-reviewed correction and deletion rules still apply.

Course project: `docs/specs/memory.md`. The consolidated review is in `docs/decision-report.html`.

## [7: Specify cache keys, freshness, and invalidation](https://github.com/jpboliv/meridian-project/issues/7)

Open · 0 — Design foundation

#### Goal

When is reusing previous information correct, and when must the system fetch or compute it again?

#### Deliverable

Update [specs/caching.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/specs/caching.md) and link the evidence or decision here.

The current specification is a draft. Record owner agreement before marking it Agreed.

#### Dependencies

- #5: Specify context selection, budgets, and compression
- #6: Specify memory creation, retrieval, correction, and deletion
- #4: Specify prompt structure and versioning

#### Acceptance criteria

- [ ] Separate provider prompt caching, source-result caching, derived summaries, and answer reuse.
- [ ] Define keys, permission scope, versions, expiry, invalidation, and observable cache hits.
- [ ] Define fresh-evidence rules after actions and changed environments.
- [ ] Define the effect of cache hits on Meridian simulated time.
- [ ] Use Session 9 to test similar questions with changed facts or different roles.

#### Course references

- [sessions/course-02-agentic-ai/09-efficiency/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/09-efficiency/README.md)
- [sessions/course-02-agentic-ai/09-efficiency/starter/gateway.py](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/09-efficiency/starter/gateway.py)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

### Discussion

[2026-11-19 · jpboliv](https://github.com/jpboliv/meridian-project/issues/7#issuecomment-7064322248)

19 November specification review · Draft for owner review.

Reuse an exact runbook revision or a scoped incident summary only while sources, reader rights, and versions match. Keep metrics, approvals, and final answers fresh. Charge the same logical simulated time to a source cache hit as to a miss. Distinguish source reads from provider-reported prompt reuse.

Course project: `docs/specs/caching.md`. The consolidated review is in `docs/decision-report.html`.

## [8: Define evaluation cases and comparison methodology](https://github.com/jpboliv/meridian-project/issues/8)

Open · 0 — Design foundation

#### Goal

How will evidence distinguish a useful improvement from a cheaper but less reliable agent?

#### Deliverable

Update [specs/evaluation.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/specs/evaluation.md) and link the evidence or decision here.

The current specification is a draft. Record owner agreement before marking it Agreed.

#### Dependencies

- #1: Define learning objectives and success criteria
- #2: Specify the reference incident across multiple shifts
- #5: Specify context selection, budgets, and compression
- #6: Specify memory creation, retrieval, correction, and deletion

#### Acceptance criteria

- [ ] Define baseline variants, development cases, reserved cases, and repeated trials.
- [ ] Define case-specific outcomes, forbidden effects, and unsupported recovery claims.
- [ ] Control model settings, initial state, memory state, budgets, and cache warmth.
- [ ] Record memory maintenance cost, tokens, calls, latency, and cache statistics when available.
- [ ] Define a decision rule and label missing measurements rather than inventing them.

#### Course references

- [meridian/evaluate.py](https://github.com/jpboliv/meridian-project/blob/main/meridian/evaluate.py)
- [sessions/course-02-agentic-ai/06-evaluation/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/06-evaluation/README.md)
- [sessions/course-02-agentic-ai/09-efficiency/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/09-efficiency/README.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

### Discussion

[2026-11-17 · jpboliv](https://github.com/jpboliv/meridian-project/issues/8#issuecomment-7064322749)

Owner agreed on the metrics, adoption rule, and first three-shift comparison in 514c580. Trial counts and case-specific evidence are still open. Next design discussion: #2.

[2026-11-19 · jpboliv](https://github.com/jpboliv/meridian-project/issues/8#issuecomment-7064322882)

19 November specification review · Draft for owner review.

Use three paired repetitions per case and version. Hold the model, simulator state, access, and budgets fixed. Reserve at least two unseen variations. Report case outcomes, evidence, and total cost, including maintenance. No decision here is a simulator result. The existing five read-only fixture trials remain separate.

Course project: `docs/specs/evaluation.md`. The consolidated review is in `docs/decision-report.html`.

## [9: Specify permissions, approvals, and untrusted-data handling](https://github.com/jpboliv/meridian-project/issues/9)

Open · 0 — Design foundation

#### Goal

Which identities can read information or perform actions, and what does an approval authorize?

#### Deliverable

Update [specs/permissions.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/specs/permissions.md) and link the evidence or decision here.

The current specification is a draft. Record owner agreement before marking it Agreed.

#### Dependencies

- #3: Define architecture and information ownership
- #6: Specify memory creation, retrieval, correction, and deletion

#### Acceptance criteria

- [ ] Define requester identity, effective permissions, and action-specific approvals.
- [ ] Define denial, expiry, and revalidation behavior.
- [ ] Treat logs, tickets, cached text, and memory as data rather than instructions.
- [ ] Define personal-data filtering and scope isolation across storage and retrieval.
- [ ] Include one useful authorized action alongside refusal and injection cases.

#### Course references

- [sessions/course-02-agentic-ai/05-security/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/05-security/README.md)
- [sessions/course-02-agentic-ai/03-mcp-integration/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/03-mcp-integration/README.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

### Discussion

[2026-11-19 · jpboliv](https://github.com/jpboliv/meridian-project/issues/9#issuecomment-7064323214)

19 November specification review · Draft for owner review.

Effective rights are the intersection of requester, role, and service credential. Bind one approval to one incident, actor, action, target, and expiry. Revalidate immediately before an effect. Contrast one permitted gateway restart with a denied critical change. Apply source access and masking to derived notes and outputs.

Course project: `docs/specs/permissions.md`. The consolidated review is in `docs/decision-report.html`.

## [10: Specify specialist contracts and handoffs](https://github.com/jpboliv/meridian-project/issues/10)

Open · 0 — Design foundation

#### Goal

How does the orchestrator integrate distinct specialists without losing evidence or constraints?

#### Deliverable

Update [specs/coordination.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/specs/coordination.md) and link the evidence or decision here.

The current specification is a draft. Record owner agreement before marking it Agreed.

#### Dependencies

- #3: Define architecture and information ownership
- #5: Specify context selection, budgets, and compression
- #9: Specify permissions, approvals, and untrusted-data handling

#### Acceptance criteria

- [ ] Define the orchestrator and at least two distinct specialist responsibilities.
- [ ] Define typed tasks, findings, evidence references, constraints, and uncertainty.
- [ ] Define handling for disagreement, malformed output, timeout, and missing findings.
- [ ] Define verification ownership, bounded follow-ups, and shared-state access.

#### Course references

- [sessions/course-02-agentic-ai/07-multi-agent/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/07-multi-agent/README.md)
- [sessions/course-02-agentic-ai/08-agents-in-production/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/08-agents-in-production/README.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

### Discussion

[2026-11-19 · jpboliv](https://github.com/jpboliv/meridian-project/issues/10#issuecomment-7064323769)

19 November specification review · Draft for owner review.

The lead integrates two read-only specialists: infrastructure and application. Give each a scoped task and require source IDs, times, and uncertainty. Allow one shared follow-up for disagreement or a missing or invalid result. The lead owns dispatch and fresh verification within the original shift budget.

Course project: `docs/specs/coordination.md`. The consolidated review is in `docs/decision-report.html`.

## [11: Specify interruption and resume semantics](https://github.com/jpboliv/meridian-project/issues/11)

Open · 0 — Design foundation

#### Goal

After an interruption, how does the system know what happened and what remains authorized?

#### Deliverable

Update [specs/execution.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/specs/execution.md) and link the evidence or decision here.

The current specification is a draft. Record owner agreement before marking it Agreed.

#### Dependencies

- #3: Define architecture and information ownership
- #9: Specify permissions, approvals, and untrusted-data handling
- #10: Specify specialist contracts and handoffs

#### Acceptance criteria

- [ ] Define the interrupted process and the state that survives it.
- [ ] Define stable action identities, durable receipts, checkpoint contents, and reconciliation.
- [ ] Cover an effect applied before confirmation or checkpoint update.
- [ ] Revalidate permissions, approvals, and current evidence before remaining actions.
- [ ] Define a reproducible demonstration that records exactly one effect.

#### Course references

- [meridian/actions.py](https://github.com/jpboliv/meridian-project/blob/main/meridian/actions.py)
- [sessions/course-02-agentic-ai/08-agents-in-production/starter/resume.py](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/08-agents-in-production/starter/resume.py)
- [sessions/course-02-agentic-ai/08-agents-in-production/lab/world.py](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/08-agents-in-production/lab/world.py)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

### Discussion

[2026-11-19 · jpboliv](https://github.com/jpboliv/meridian-project/issues/11#issuecomment-7064324608)

19 November specification review · Draft for owner review.

Interrupt the worker after the executor applies a restart but before the checkpoint records the receipt. Keep the simulated exchange and executor ledger alive. Reconcile by the original action key, revalidate remaining rights, and stop on an unknown outcome. The planned demonstration requires one applied effect and fresh readings.

Course project: `docs/specs/execution.md`. The consolidated review is in `docs/decision-report.html`.

## [12: Build the first-line incident flow from agreed specifications](https://github.com/jpboliv/meridian-project/issues/12)

Open · 1 — First-line agent

#### Goal

Implement the first complete incident-response flow on the supplied Meridian platform.

#### Deliverable

Update [../README.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/README.md) and link the evidence or decision here.

Begin after the linked specifications are agreed and prerequisite work is complete. Split this issue into smaller tasks when the contracts are clear.

#### Dependencies

- #4: Specify prompt structure and versioning
- #5: Specify context selection, budgets, and compression
- #9: Specify permissions, approvals, and untrusted-data handling
- #8: Define evaluation cases and comparison methodology

#### Acceptance criteria

- [ ] Use functional MCP integration with selected capabilities and validated outputs.
- [ ] Support investigation, authorized mitigation, and fresh recovery evidence.
- [ ] Handle missing information, invalid outputs, temporary failure, and lost action responses.
- [ ] Provide a runnable command and an explained trace.

#### Course references

- [meridian/agent_runtime.py](https://github.com/jpboliv/meridian-project/blob/main/meridian/agent_runtime.py)
- [sessions/course-02-agentic-ai/03-mcp-integration/starter/harness.py](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/03-mcp-integration/starter/harness.py)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

## [13: Record a reproducible first-line baseline and tag M1](https://github.com/jpboliv/meridian-project/issues/13)

Open · 1 — First-line agent

#### Goal

Establish the initial results used by all later comparisons.

#### Deliverable

Update [experiments.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/experiments.md) and link the evidence or decision here.

Begin after the linked specifications are agreed and prerequisite work is complete. Split this issue into smaller tasks when the contracts are clear.

#### Dependencies

- #12: Build the first-line incident flow from agreed specifications
- #8: Define evaluation cases and comparison methodology

#### Acceptance criteria

- [ ] Run agreed cases with the agreed repetitions and settings.
- [ ] Save version, model, limits, initial state, case outcomes, and traces.
- [ ] Record failures and costs without presenting lab runs as project results.
- [ ] Review the trace with the owner and tag the first milestone.

#### Course references

- [sessions/course-02-agentic-ai/06-evaluation/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/06-evaluation/README.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

## [14: Implement the memory lifecycle and multi-shift scenarios](https://github.com/jpboliv/meridian-project/issues/14)

Open · 2 — Memory-aware on-call agent

#### Goal

Apply the agreed memory policy across successive incidents.

#### Deliverable

Update [specs/memory.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/specs/memory.md) and link the evidence or decision here.

Begin after the linked specifications are agreed and prerequisite work is complete. Split this issue into smaller tasks when the contracts are clear.

#### Dependencies

- #6: Specify memory creation, retrieval, correction, and deletion
- #13: Record a reproducible first-line baseline and tag M1
- #9: Specify permissions, approvals, and untrusted-data handling

#### Acceptance criteria

- [ ] Implement provenance, scoped retrieval, applicability, conflicts, correction, and deletion.
- [ ] Ground retained lessons in recorded evidence.
- [ ] Demonstrate recurrence and changed conditions using the agreed reference incident.
- [ ] Expose memory decisions in traces for owner review.

#### Course references

- [meridian/memory.py](https://github.com/jpboliv/meridian-project/blob/main/meridian/memory.py)
- [sessions/course-02-agentic-ai/04-memory/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/04-memory/README.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

## [15: Integrate identity, approvals, and data protection](https://github.com/jpboliv/meridian-project/issues/15)

Open · 2 — Memory-aware on-call agent

#### Goal

Apply the security contract to the integrated incident flow.

#### Deliverable

Update [specs/permissions.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/specs/permissions.md) and link the evidence or decision here.

Begin after the linked specifications are agreed and prerequisite work is complete. Split this issue into smaller tasks when the contracts are clear.

#### Dependencies

- #9: Specify permissions, approvals, and untrusted-data handling
- #13: Record a reproducible first-line baseline and tag M1

#### Acceptance criteria

- [ ] Enforce effective identity and action approvals in code.
- [ ] Apply the agreed treatment of injected instructions and personal data.
- [ ] Demonstrate authorized help, blocked actions, and isolated information.
- [ ] Record decisions and evidence without exposing secrets.

#### Course references

- [sessions/course-02-agentic-ai/05-security/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/05-security/README.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

## [16: Implement version-aware caching and context controls](https://github.com/jpboliv/meridian-project/issues/16)

Open · 2 — Memory-aware on-call agent

#### Goal

Reuse information under the agreed freshness and isolation rules.

#### Deliverable

Update [specs/caching.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/specs/caching.md) and link the evidence or decision here.

Begin after the linked specifications are agreed and prerequisite work is complete. Split this issue into smaller tasks when the contracts are clear.

#### Dependencies

- #7: Specify cache keys, freshness, and invalidation
- #14: Implement the memory lifecycle and multi-shift scenarios
- #15: Integrate identity, approvals, and data protection
- #13: Record a reproducible first-line baseline and tag M1

#### Acceptance criteria

- [ ] Implement only cache types accepted in the specification.
- [ ] Make hit, miss, age, source version, and invalidation observable.
- [ ] Retain fresh verification after actions and isolate permissions.
- [ ] Account for simulator time and record context budgets.

#### Course references

- [sessions/course-02-agentic-ai/09-efficiency/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/09-efficiency/README.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

## [17: Compare memory and caching policies and tag M2](https://github.com/jpboliv/meridian-project/issues/17)

Open · 2 — Memory-aware on-call agent

#### Goal

Measure which policy changes help and which introduce stale information or extra cost.

#### Deliverable

Update [experiments.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/experiments.md) and link the evidence or decision here.

Begin after the linked specifications are agreed and prerequisite work is complete. Split this issue into smaller tasks when the contracts are clear.

#### Dependencies

- #14: Implement the memory lifecycle and multi-shift scenarios
- #15: Integrate identity, approvals, and data protection
- #16: Implement version-aware caching and context controls
- #8: Define evaluation cases and comparison methodology

#### Acceptance criteria

- [ ] Compare no memory, basic retrieval, applicability-aware retrieval, and agreed cache variants.
- [ ] Change one policy at a time and control initial state and cache warmth.
- [ ] Include repeated incidents, changed facts, conflicts, isolation, and deletion.
- [ ] Report per-case regressions and maintenance costs alongside aggregate results.
- [ ] Record the decision with limitations and tag the second milestone.

#### Course references

- [sessions/course-02-agentic-ai/06-evaluation/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/06-evaluation/README.md)
- [sessions/course-02-agentic-ai/09-efficiency/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/09-efficiency/README.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

## [18: Integrate specialists with evidence-backed handoffs](https://github.com/jpboliv/meridian-project/issues/18)

Open · 3 — Coordinated, resumable response

#### Goal

Apply the agreed task contracts to a coordinated incident team.

#### Deliverable

Update [specs/coordination.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/specs/coordination.md) and link the evidence or decision here.

Begin after the linked specifications are agreed and prerequisite work is complete. Split this issue into smaller tasks when the contracts are clear.

#### Dependencies

- #10: Specify specialist contracts and handoffs
- #14: Implement the memory lifecycle and multi-shift scenarios
- #15: Integrate identity, approvals, and data protection
- #13: Record a reproducible first-line baseline and tag M1

#### Acceptance criteria

- [ ] Integrate the orchestrator and distinct specialist roles.
- [ ] Preserve source references and constraints across handoffs.
- [ ] Handle disagreement, missing findings, and bounded correction.
- [ ] Compare outcomes and cost against the single-agent baseline.

#### Course references

- [sessions/course-02-agentic-ai/07-multi-agent/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/07-multi-agent/README.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

## [19: Implement durable resume and tag M3](https://github.com/jpboliv/meridian-project/issues/19)

Open · 3 — Coordinated, resumable response

#### Goal

Recover an interrupted incident using durable execution evidence.

#### Deliverable

Update [specs/execution.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/specs/execution.md) and link the evidence or decision here.

Begin after the linked specifications are agreed and prerequisite work is complete. Split this issue into smaller tasks when the contracts are clear.

#### Dependencies

- #11: Specify interruption and resume semantics
- #18: Integrate specialists with evidence-backed handoffs

#### Acceptance criteria

- [ ] Exercise the agreed interruption boundary after an applied effect.
- [ ] Reconcile receipts and checkpoints without repeating the effect.
- [ ] Revalidate remaining permissions and expired approvals.
- [ ] Integrate verification and save the recovery trace.
- [ ] Review the result with the owner and tag the third milestone.

#### Course references

- [sessions/course-02-agentic-ai/08-agents-in-production/README.md](https://github.com/jpboliv/meridian-project/blob/main/sessions/course-02-agentic-ai/08-agents-in-production/README.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.

## [20: Prepare final evidence, documentation, and demonstration](https://github.com/jpboliv/meridian-project/issues/20)

Open · 4 — Evidence and delivery

#### Goal

Produce a reproducible submission that the owner can explain.

#### Deliverable

Update [project.md](https://github.com/jpboliv/meridian-project/blob/main/projects/course-02-agentic-ai/docs/project.md) and link the evidence or decision here.

Begin after the linked specifications are agreed and prerequisite work is complete. Split this issue into smaller tasks when the contracts are clear.

#### Dependencies

- #17: Compare memory and caching policies and tag M2
- #19: Implement durable resume and tag M3

#### Acceptance criteria

- [ ] Finalize the proposal, architecture diagram, README, policies, and limitations.
- [ ] Record inputs, expected outcomes, actual outcomes, comparisons, and traces.
- [ ] Include milestone versions, dependency lock, secret-free example configuration, and AI-use disclosure.
- [ ] Run a clean-clone rehearsal and demonstrate success, controlled failure, and resume.
- [ ] Complete delivery by 30 November 2026 at 23:59 Lisbon time (`Europe/Lisbon`).

#### Course references

- [ROADMAP.md](https://github.com/jpboliv/meridian-project/blob/main/ROADMAP.md)
- [STATUS.md](https://github.com/jpboliv/meridian-project/blob/main/STATUS.md)

#### Review

The owner can explain the behavior and its tradeoffs. Record the result in STATUS.md and the relevant decision or experiment entry.
