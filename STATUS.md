# Current focus

The [tracker and milestones](https://github.com/jpboliv/meridian-project/milestones) now live beside the code in the private repository. [PR #1](https://github.com/jpboliv/meridian-project/pull/1) holds the M1 implementation under review.

First-line implementation. All five [public development cases](projects/course-02-agentic-ai/docs/experiments.md#m1-grader-controls) pass with scripted decisions under `gateway-m1.4`. The A/C reports match three healthy readings after the applied restart. B hands over after two timeouts on the same instance and a fresh link check. D and E cite the degraded link and have no effects. No live-model baseline yet.

Resume here (21 November): review the [M1 milestone pull request](https://github.com/jpboliv/meridian-project/pull/1) against the [grader controls](projects/course-02-agentic-ai/first_line/test_case_checks.py) and [five offline traces](projects/course-02-agentic-ai/first_line/offline-traces-m1.4.jsonl). All 18 project tests pass (`uv run --locked --offline python -m pytest projects/course-02-agentic-ai/first_line -q`). Next, add and test a single-case pilot with request and output limits. The current `--live` command runs all five cases.

The [budget proposal](https://github.com/jpboliv/meridian-project/issues/8#issuecomment-7064323088) uses `gpt-6-luna` on the Responses API. Review the run settings and offline evidence before spending on the pilot. A separate Decisions API trial could test specialist routing after M1.

Owner clarified the [reuse scope](projects/course-02-agentic-ai/docs/architecture.md#tool-boundary): new tools and cases are in scope. Extend the simulator when an experiment needs behavior it cannot currently represent.

All eleven design topics have drafts. Agreement on individual rules does not approve the full contracts. The next owner review is the [baseline protocol](projects/course-02-agentic-ai/docs/specs/evaluation.md#draft-fair-comparisons): model revision, repetitions, and run limits. Then run the live baseline using the [project guide](projects/course-02-agentic-ai/README.md#run-the-first-line-cases). The timestamp-layout comparison also needs both layouts and provider cache-usage recording before it can measure reuse. Later specialist and resume contracts can be reviewed separately.

The owner agreed on the [shift inputs and trial reset](projects/course-02-agentic-ai/docs/reference-incident.md#agreed-handover), the [evidence needed to save a clue](projects/course-02-agentic-ai/docs/specs/memory.md#agreed-handover-evidence), and [when a lesson applies](projects/course-02-agentic-ai/docs/specs/memory.md#agreed-when-a-lesson-applies). Check the prerequisite against current evidence, not the version number alone.

Use the [dated roadmap](ROADMAP.md#delivery-order) for the delivery sequence. The next decision is [baseline review #8](https://github.com/jpboliv/meridian-project/issues/8). [Experiment #21](https://github.com/jpboliv/meridian-project/issues/21) tracks provider prompt caching and verified outcomes separately from the optional tool-result cache in #16.

The owner confirmed the submission deadline: 30 November 2026 at 23:59 Lisbon time (`Europe/Lisbon`).

Presentation slice of [#20](https://github.com/jpboliv/meridian-project/issues/20), 21 November, awaiting owner review: the [short Portuguese report](projects/course-02-agentic-ai/docs/relatorio.md) replaces the generated HTML report and its renderer; `docs/decision-report.html` is now a pointer to commit `83bd973`. It shows the architecture in Mermaid, case A (supported restart) and case B (controlled failure) with their m1.4 traces, what is unmeasured, the caching question, and the AI-use disclosure. The offline lab runs one chosen case only on request: `uv run --locked streamlit run projects/course-02-agentic-ai/first_line/lab.py`. It shares `run_case` with `demo.py`; the CLI output still matches `offline-traces-m1.4.jsonl` byte for byte. `first_line/test_lab.py` checks that loading or changing the selection runs nothing and that one click runs only the selected case. Mermaid was not rendered locally; check both diagrams on GitHub. The rest of #20 (proposal, milestone tags, `.env.example`, rehearsal) remains open.

[Class pitch for Luís](projects/course-02-agentic-ai/docs/design-review.md#para-apresentar-à-turma-cerca-de-um-minuto): prompt caching is the course deep dive. Compare two timestamp positions and evaluate provider-reported reuse, whole-incident cost, and verified decisions. No provider results yet. The separate memory trials keep the same full runbook. Protect correction, specialist handoff, worker resume, and the 29 November rehearsal. Caching tool results and comparing compaction policies remain optional.

Planned memory correction case: [the wrongly credited restart](projects/course-02-agentic-ai/docs/reference-incident.md#the-wrongly-credited-restart). No run results yet.

Session handoff: use rules to classify evidence against a specific claim as a direct contradiction, possible conflict, or unsupported concern. A separate policy decides whether to withdraw a team lesson, seek human review, or leave it alone. Skipping a lesson for a version mismatch does not withdraw it. Record `withdrawn_at`, the reason, and sources together when withdrawing advice.

Owner agreed: [keep decision-changing facts inline with their sources](projects/course-02-agentic-ai/docs/specs/context.md#agreed-shortening-a-shift-handover). In the [fresh-shift fixture trial](projects/course-02-agentic-ai/docs/experiments.md#2026-11-18-shortened-restart-handover), the agent verified both times and used current readings to recommend investigating the database link. No simulator actions were tested. Owner also agreed: keep a corrected claim and its correction together in the same note. If they cannot fit, omit the old claim; keep the original record available. Verify this at the shortening step once implemented. Reuse whole-note coverage if available; no extra shift simulation is planned. The remaining budget choices now have draft limits in #5.

[Four read-only shifts](projects/course-02-agentic-ai/docs/experiments.md#2026-11-18-does-the-memory-lesson-change-the-investigation) distinguished individual readings from a fleet average. No observed lesson effect on source use or primary recommendation.

Owner agreed on [authority to correct a shared lesson](projects/course-02-agentic-ai/docs/specs/memory.md#agreed-who-can-correct-a-shared-lesson): agents can correct directly contradicted facts; operators approve procedure and permission changes. Use existing triage when uncertainty blocks a live decision.

Owner agreed on [source deletion](projects/course-02-agentic-ai/docs/specs/memory.md#agreed-when-a-source-is-deleted): neither lookup nor handover may return a deleted source’s links or copied material. Retain independently supported observations.
