# Current focus

Design foundation. The [specification report](projects/course-02-agentic-ai/docs/decision-report.html) is ready for owner review. It covers design issues 1–11 and starts with the explanation for Luís. The owner delegated the remaining choices on 19 November. They are Draft until reviewed. The course platform is available through upstream revision `363abf1`. The project has no implementation baseline yet.

The owner agreed on the [shift inputs and trial reset](projects/course-02-agentic-ai/docs/reference-incident.md#agreed-handover), the [evidence needed to save a clue](projects/course-02-agentic-ai/docs/specs/memory.md#agreed-handover-evidence), and [when a lesson applies](projects/course-02-agentic-ai/docs/specs/memory.md#agreed-when-a-lesson-applies). Check the prerequisite against current evidence, not the version number alone.

Use the [roadmap](ROADMAP.md) for milestone outcomes and [GitHub Issues](https://github.com/jpboliv/meridian-agents/issues) for live task status. Update this page when the next discussion changes.

The owner confirmed the submission deadline: 30 November 2026 at 23:59 Lisbon time (`Europe/Lisbon`).

Planned memory correction case: [the wrongly credited restart](projects/course-02-agentic-ai/docs/reference-incident.md#the-wrongly-credited-restart). No run results yet.

Session handoff: use rules to classify evidence against a specific claim as a direct contradiction, possible conflict, or unsupported concern. A separate policy decides whether to withdraw a team lesson, seek human review, or leave it alone. Skipping a lesson for a version mismatch does not withdraw it. Record `withdrawn_at`, the reason, and sources together when withdrawing advice.

Owner agreed: [keep decision-changing facts inline with their sources](projects/course-02-agentic-ai/docs/specs/context.md#agreed-shortening-a-shift-handover). In the [fresh-shift fixture trial](projects/course-02-agentic-ai/docs/experiments.md#2026-11-18-shortened-restart-handover), the agent verified both times and used current readings to recommend investigating the database link. No simulator actions were tested. Owner also agreed: keep a corrected claim and its correction together in the same note. If they cannot fit, omit the old claim; keep the original record available. Verify this at the shortening step once implemented. Reuse whole-note coverage if available; no extra shift simulation is planned. The remaining budget choices now have draft limits in #5.

[Four read-only shifts](projects/course-02-agentic-ai/docs/experiments.md#2026-11-18-does-the-memory-lesson-change-the-investigation) distinguished individual readings from a fleet average. No observed lesson effect on source use or primary recommendation.

Owner agreed on [authority to correct a shared lesson](projects/course-02-agentic-ai/docs/specs/memory.md#agreed-who-can-correct-a-shared-lesson): agents can correct directly contradicted facts; operators approve procedure and permission changes. Use existing triage when uncertainty blocks a live decision.

Owner agreed on [source deletion](projects/course-02-agentic-ai/docs/specs/memory.md#agreed-when-a-source-is-deleted): neither lookup nor handover may return a deleted source’s links or copied material. Retain independently supported observations.
