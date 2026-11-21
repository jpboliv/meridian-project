# Course 2 — Agentic AI: project

The evolving project for Course 2: an incident-response system for the
Meridian Exchange, a fictional stock exchange simulated locally.

It grows in three milestones:

1. First-Line Incident Agent (sessions 1–3)
2. Production On-Call Agent (sessions 4–6)
3. 24/7 Incident Response Center (sessions 7–9)

Start with the [project goals](docs/project.md) and [reference incident](docs/reference-incident.md). Follow the [roadmap](../../ROADMAP.md) for milestone outcomes.

For the class presentation, use [the short report in Portuguese](docs/relatorio.md): architecture diagrams, one supported and one controlled-failure outcome with traces, and what remains unmeasured.

## Run the first-line cases

From the repository root:

```sh
uv run --locked python projects/course-02-agentic-ai/first_line/demo.py
```

This starts a fresh simulator for each case. The offline driver follows a fixed read order and chooses a target from the readings. MCP services, approvals, actions, recovery readings, and the course evaluator run locally. Each output line is a JSON trace. The command exits with a failure if any case fails. The [experiment log](docs/experiments.md#m1-grader-controls) shows what the graders accept and reject.

The current `--live` switch runs **all five cases** using `OPENAI_API_KEY` from the local `.env`. Use the offline command above during development. Review the single-case pilot and its limits in [#8](https://github.com/jpboliv/meridian-project/issues/8) before a paid run. The default model is `gpt-4.1-mini`; `OPENAI_MODEL` selects another. The model chooses reads and proposes an action. Code controls the approval, dispatch, and recovery report. Only the evaluator reads `first_line/checks/`. Cases A, C, and D form the three-shift story. B has missing readings; in [E the monitor answers with old readings](docs/experiments.md#case-e-the-healthy-but-stale-monitor). Each starts without memory. These runs do not measure provider cache reuse, cross-shift recall, or worker replacement.

## Run one case in the lab

From the repository root, with no API key:

```sh
uv run --locked streamlit run projects/course-02-agentic-ai/first_line/lab.py
```

Choose one public case, A–E, and press **Executar caso**. The page runs that case through the same `run_case` path as the command above and shows the decision, key observations, applied effects, the evaluator's checks, and the JSON trace record. Opening the page or changing the selection runs nothing. The lab never calls a model.

## Design index

The [presentation report](docs/relatorio.md) replaces the generated HTML report. The [review introduction](docs/design-review.md) keeps the 19 November pitch and the Helloform reasoning. The specifications below contain the detailed contracts.

The [course references](references/) contain the project brief and the first session's slides. The [19 November snapshot](docs/issue-snapshot.md) preserves the discussions from that date. Use this repository’s [issue tracker](https://github.com/jpboliv/meridian-project/issues) for current work.

- [Architecture and information ownership](docs/architecture.md)
- [Prompts](docs/specs/prompts.md) and [context](docs/specs/context.md)
- [Memory](docs/specs/memory.md) and [caching](docs/specs/caching.md)
- [Evaluation](docs/specs/evaluation.md) and [experiment log](docs/experiments.md)
- [Permissions](docs/specs/permissions.md), [coordination](docs/specs/coordination.md), and [resume](docs/specs/execution.md)
- [Decision log](docs/decisions.md) and [specification template](docs/specs/template.md)

Discuss one incident example before choosing a policy. The owner reviews the contract, then a coding agent implements it. Review both the outcome and the evidence used to reach it.
