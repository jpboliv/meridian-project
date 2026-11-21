# Course 2 — Agentic AI: project

The evolving project for Course 2: an incident-response system for the
Meridian Exchange, a fictional stock exchange simulated locally.

It grows in three milestones:

1. First-Line Incident Agent (sessions 1–3)
2. Production On-Call Agent (sessions 4–6)
3. 24/7 Incident Response Center (sessions 7–9)

Start with the [project goals](docs/project.md) and [reference incident](docs/reference-incident.md). Follow the [roadmap](../../ROADMAP.md) for milestone outcomes.

For the class presentation, use [the one-minute pitch in Portuguese](docs/design-review.md#para-apresentar-à-turma-cerca-de-um-minuto).

## Run the first-line cases

From the repository root:

```sh
uv run --locked python projects/course-02-agentic-ai/first_line/demo.py
```

This starts a fresh simulator for each case. The offline driver follows a fixed read order and chooses a target from the readings. MCP services, approvals, actions, recovery readings, and the course evaluator run locally. Each output line is a JSON trace. The command exits with a failure if any case fails. The [experiment log](docs/experiments.md#m1-grader-controls) shows what the graders accept and reject.

The current `--live` switch runs **all five cases** using `OPENAI_API_KEY` from the local `.env`. Use the offline command above during development. Review the single-case pilot and its limits in [#8](https://github.com/jpboliv/meridian-agents/issues/8) before a paid run. The default model is `gpt-4.1-mini`; `OPENAI_MODEL` selects another. The model chooses reads and proposes an action. Code controls the approval, dispatch, and recovery report. Only the evaluator reads `first_line/checks/`. Cases A, C, and D form the three-shift story. B has missing readings; in [E the monitor answers with old readings](docs/experiments.md#case-e-the-healthy-but-stale-monitor). Each starts without memory. These runs do not measure provider cache reuse, cross-shift recall, or worker replacement.

## Design index

Read the [review introduction](docs/design-review.md) on GitHub, or open `docs/decision-report.html` in a browser after cloning the repository. The HTML file contains the complete report and its diagrams. Reading it needs no setup.

The introduction and the specifications below contain the editable text. To rebuild the HTML after an edit, run this from the repository root:

```sh
uv run --locked python projects/course-02-agentic-ai/docs/render_report.py
```

The [course references](references/) contain the project brief and the first session's slides. The [issue snapshot](docs/issue-snapshot.md) preserves the decisions and discussions from the [course fork's tracker](https://github.com/jpboliv/meridian-agents/issues).

- [Architecture and information ownership](docs/architecture.md)
- [Prompts](docs/specs/prompts.md) and [context](docs/specs/context.md)
- [Memory](docs/specs/memory.md) and [caching](docs/specs/caching.md)
- [Evaluation](docs/specs/evaluation.md) and [experiment log](docs/experiments.md)
- [Permissions](docs/specs/permissions.md), [coordination](docs/specs/coordination.md), and [resume](docs/specs/execution.md)
- [Decision log](docs/decisions.md) and [specification template](docs/specs/template.md)

Discuss one incident example before choosing a policy. The owner reviews the contract, then a coding agent implements it. Review both the outcome and the evidence used to reach it.
