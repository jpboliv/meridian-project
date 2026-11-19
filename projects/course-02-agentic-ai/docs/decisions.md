# Decision log

| Decision | Reason |
|---|---|
| Use the supplied Meridian simulator. | Spend project time on agent behavior. |
| Study memory, context, and caching together. | The owner wants to explain how earlier information affects current decisions. |
| Track work in personal GitHub Issues. | Keep discussions and delivery evidence with the project. |
| Agreed, 18 Nov 2026 ([#5](https://github.com/jpboliv/meridian-agents/issues/5)): keep a corrected claim and its correction in the same handover note, or omit the old claim. | A shift could act on stale advice before opening a separate correction. The original record remains available. |

For each future decision, record the issue, alternatives considered, reason, owner review, and condition for revisiting it.

Agreed, 18 Nov 2026 ([#6](https://github.com/jpboliv/meridian-agents/issues/6)): check a lesson’s [observable prerequisites](specs/memory.md#agreed-when-a-lesson-applies) after an upgrade rather than rejecting it by version alone. A different version can still supply the same readings. Revisit the check if the system cannot tell which readings a source supplies.

Agreed, 19 Nov 2026 ([#6](https://github.com/jpboliv/meridian-agents/issues/6)): [agents can correct a directly contradicted factual claim](specs/memory.md#agreed-who-can-correct-a-shared-lesson). This keeps later shifts from inheriting a known error without giving agents authority to change procedures. Use existing incident triage if uncertainty blocks a live decision.

Agreed, 19 Nov 2026 ([#6](https://github.com/jpboliv/meridian-agents/issues/6)): [remove deleted evidence from derived records](specs/memory.md#agreed-when-a-source-is-deleted). A copied claim can outlive its evidence if the system removes only the link.

## Delegated choices for owner review

State: Draft, 19 November 2026. The owner delegated the remaining choices and requested one review. These are design decisions, not project results. The [review introduction](design-review.md) gives the short explanation for Luís and the reasons for using the Helloform ideas.

| Issue and decision | Reason or condition for review |
|---|---|
| [1: Scope and milestones](project.md) | Compare the same incident system at M1, M2, and M3. Defer model routing and report animation until the main comparisons are complete. |
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
