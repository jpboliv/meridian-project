# Decision log

| Decision | Reason |
|---|---|
| Agreed, 23 Nov 2026: [two read-only specialists, one shared follow-up, one lead with dispatch authority](https://github.com/jpboliv/meridian-project/issues/10#issuecomment-7116373182). | A second account of an alert is not independent evidence. Bound the extra investigation and compare it with the single agent under the same budget. |
| Agreed, 23 Nov 2026: [reconcile a replacement worker's saved intent with the surviving executor](https://github.com/jpboliv/meridian-project/issues/11#issuecomment-7116373196). | A missing reply does not mean the restart failed. Recover its receipt without repeating it; check current health before reporting recovery. |
| Agreed, 21 Nov 2026: keep code, issues, milestones and review PRs in the private `jpboliv/meridian-project` repository. | A PR and its issues can now share a GitHub milestone. The owner can review the implementation and its evidence in one place. |
| Agreed, 19 Nov 2026 ([#3](https://github.com/jpboliv/meridian-project/issues/3)): reuse the Meridian simulator as a starting point. We can add tools and cases, and change the simulator when an experiment warrants it. | The simulated exchange makes trials repeatable. Its existing tool catalog and fault models do not limit the questions we can test. |
| Study memory, context, and caching together. | The owner wants to explain how earlier information affects current decisions. |
| Track work in personal GitHub Issues. | Keep discussions and delivery evidence with the project. |
| Agreed, 18 Nov 2026 ([#5](https://github.com/jpboliv/meridian-project/issues/5)): keep a corrected claim and its correction in the same handover note, or omit the old claim. | A shift could act on stale advice before opening a separate correction. The original record remains available. |

For each future decision, record the issue, alternatives considered, reason, owner review, and condition for revisiting it.

Agreed, 18 Nov 2026 ([#6](https://github.com/jpboliv/meridian-project/issues/6)): check a lesson’s [observable prerequisites](specs/memory.md#agreed-when-a-lesson-applies) after an upgrade rather than rejecting it by version alone. A different version can still supply the same readings. Revisit the check if the system cannot tell which readings a source supplies.

Agreed, 19 Nov 2026 ([#6](https://github.com/jpboliv/meridian-project/issues/6)): [agents can correct a directly contradicted factual claim](specs/memory.md#agreed-who-can-correct-a-shared-lesson). This keeps later shifts from inheriting a known error without giving agents authority to change procedures. Use existing incident triage if uncertainty blocks a live decision.

Agreed, 19 Nov 2026 ([#6](https://github.com/jpboliv/meridian-project/issues/6)): [remove deleted evidence from derived records](specs/memory.md#agreed-when-a-source-is-deleted). A copied claim can outlive its evidence if the system removes only the link.

Agreed, 23 Nov 2026 ([#6 owner review](https://github.com/jpboliv/meridian-project/issues/6#issuecomment-7103963598)): allow a [separate edition for a named team](specs/memory.md#agreed-who-can-receive-a-lesson) rather than forwarding a private lesson or forbidding all sharing. The recipient can verify the clue without seeing the private log.

Agreed, 23 Nov 2026 ([#9 owner review](https://github.com/jpboliv/meridian-project/issues/9#issuecomment-7103963642)): bind [one gateway restart](specs/permissions.md#agreed-one-approval-for-one-gateway-restart) to one instance and a short-lived approval. A shift that resumes after the fault moves must not use the old grant on the newly affected instance.

Agreed, 23 Nov 2026 ([#6 owner review](https://github.com/jpboliv/meridian-project/issues/6#issuecomment-7104148998)): [stop suggesting an unreviewed clue after seven simulated days](specs/memory.md#agreed-when-a-diagnostic-clue-expires). A past incident can remain accurate while its advice becomes stale. Keep the incident as history; review the evidence and confirm the condition before suggesting the clue again.

Agreed, 23 Nov 2026 ([#6 owner review](https://github.com/jpboliv/meridian-project/issues/6#issuecomment-7104286574)): [expire a shift note after one handover or 24 simulated hours](specs/memory.md#agreed-when-a-shift-note-expires), whichever comes first. A fresh note tells the next shift that the task is still open; forwarding the old note cannot establish that.

Agreed, 23 Nov 2026 ([#6 owner review](https://github.com/jpboliv/meridian-project/issues/6#issuecomment-7104405732)): require [two independent incidents before an agent proposes a team procedure](specs/memory.md#agreed-when-an-agent-can-propose-a-team-procedure). Counting reports instead would let a single outage look like a recurring pattern. An operator still decides whether to approve the proposal.

Agreed, 23 Nov 2026 ([#6 owner review](https://github.com/jpboliv/meridian-project/issues/6#issuecomment-7104456047)): [stop using a procedure](specs/memory.md#agreed-when-to-stop-using-a-procedure) on expiry, operator revocation, or an incompatible change. Checking the required readings after an upgrade keeps a valid procedure available without asking a shift to act on evidence it no longer has.

Agreed, 23 Nov 2026 ([#6 owner review](https://github.com/jpboliv/meridian-project/issues/6#issuecomment-7104486966)): [bind procedure approval to its exact text, scope, version, and review date](specs/memory.md#agreed-what-procedure-approval-covers). Otherwise an edit could extend a gateway procedure to another team without the operator reviewing that use.

Agreed, 23 Nov 2026 ([#6 owner review](https://github.com/jpboliv/meridian-project/issues/6#issuecomment-7104566649)): [require a source, observation time, affected component or instance, and testable condition](specs/memory.md#agreed-what-a-diagnostic-clue-must-contain) before saving a clue at shift close. The next shift needs to verify what happened then and check whether the clue applies now.

## Delegated choices for owner review

Agreed, 23 Nov 2026: the owner signed off on the combined [memory contract](https://github.com/jpboliv/meridian-project/issues/6#issuecomment-7105048143) and [M2 access contract](https://github.com/jpboliv/meridian-project/issues/9#issuecomment-7105048144) for #14 and #15. The authorized restart and denied critical change cover the demonstration; rollback stays outside M2.

23 Nov 2026: the owner agreed to [rank eligible lessons by component, current conditions, then observation time](specs/memory.md#agreed-how-to-rank-eligible-lessons) and delegated routine M2 choices. Recency breaks a tie rather than displacing a better match. Review the remaining [memory](https://github.com/jpboliv/meridian-project/issues/6#issuecomment-7104800247) and [access](https://github.com/jpboliv/meridian-project/issues/9#issuecomment-7104800162) details together. The proposed access contract defers rollback: one permitted gateway restart and one denied critical change already demonstrate the M2 boundary.

19 November, after the course-fit review: deliver the verified restart and missing-evidence handover first. Keep correction, failed specialist handoff, and resume on the delivery path. For the class deep dive, keep one prompt-caching comparison: moving the timestamp tests the Helloform idea without changing the information available to the agent. Evaluate cost alongside verified outcomes. Defer application caches and compaction comparisons. For the separate memory comparison, keep the full runbook in both versions. See the [delivery priorities](project.md#agreed-delivery-priorities).

State: Draft, 19 November 2026. The owner delegated the remaining choices and requested one review. These are design decisions, not project results. The [review introduction](design-review.md) gives the short explanation for Luís and the reasons for using the Helloform ideas.

| Issue and decision | Reason or condition for review |
|---|---|
| [22: Scope and milestones](project.md) | Compare the same incident system at M1, M2, and M3. Defer model routing and report animation until the main comparisons are complete. |
| [2: Three shifts](reference-incident.md) | Change the affected instance, then the cause. This separates useful recall from repeating a fix. |
| [3: Record ownership](architecture.md) | A receipt establishes an effect. A reading establishes the service condition. A checkpoint cannot replace either. |
| [4: Prompt sections](specs/prompts.md) | Stable sections make costs measurable. Rebuild immediately if access or a correction changes the evidence. |
| [5: Context budget](specs/context.md) | Reserve space for a successor summary. Review the limits if they hide decisive evidence or drive needless summaries. |
| [6: Team memory](specs/memory.md) | Use private lessons within the team. Cross-team publication requires readable evidence and a separate edition. Review the expiry period against recall results. |
| [7: Cache](specs/caching.md) | Reuse versioned runbooks and scoped summaries. Do not reuse live diagnoses. Count logical tool time on hits and misses. |
| [8: Evaluation](specs/evaluation.md) | Paired repetitions and reserved cases expose regressions. A small comparison supports a project choice, not a general performance claim. |
| [9: Action authority](specs/permissions.md) | Bind a short-lived grant to one intent. Approval cannot turn a read-only role into a writer. |
| [10: Two specialists](specs/coordination.md) | Different sources make a disagreement useful. Limit follow-ups so the team cannot spend the shift in a loop. |
| [11: Resume](specs/execution.md) | Keep the executor alive across a worker restart. An unknown outcome cannot justify another effect. |
