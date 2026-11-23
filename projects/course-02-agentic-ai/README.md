# Course 2 — Agentic AI: project

The evolving project for Course 2: an incident-response system for the
Meridian Exchange, a fictional stock exchange simulated locally.

It grows in three milestones:

1. First-Line Incident Agent (sessions 1–3)
2. Production On-Call Agent (sessions 4–6)
3. 24/7 Incident Response Center (sessions 7–9)

Start with the [project goals](docs/project.md) and [reference incident](docs/reference-incident.md). Follow the [roadmap](../../ROADMAP.md) for milestone outcomes.

For the class presentation, use [the short report in Portuguese](docs/relatorio.md): the context-reuse question, course versus project work, the architecture, one evidence table with the `gateway-m1.7` scripted traces and the [15-run public live baseline](docs/experiments.md#2026-11-22-public-m1-baseline-gateway-m16) (9/15 passed), and what remains unmeasured. The current harness is `gateway-m1.7`, an [offline follow-up](docs/experiments.md#2026-11-23-offline-follow-up-to-the-baseline-failures-gateway-m17) to those failures with no live result yet. Its scripted outcomes match m1.6. The report ends with a [verification route](docs/relatorio.md#verificar-no-seu-computador) that needs no `.env` or API key: run the lab, regenerate the scripted traces and compare them byte for byte, and analyse the saved live baseline.

## Run the first-line cases

From the repository root:

```sh
uv run --locked python projects/course-02-agentic-ai/first_line/demo.py
```

This starts a fresh simulator for each case. The offline driver follows a fixed read order and chooses a target from the readings. MCP services, approvals, actions, recovery readings, and the course evaluator run locally. Each output line is a JSON trace. The command exits with a failure if any case fails. The [experiment log](docs/experiments.md#m1-grader-controls) shows what the graders accept and reject. Add `--case B` (A–E) to run one case.

### One bounded live case

`--live` asks the model named by `OPENAI_MODEL` for each decision in **one** case. It is a paid run: the owner decides the model, limits, and spending in [#8](https://github.com/jpboliv/meridian-project/issues/8) before anyone runs it. The command has no default limits, and it never runs all cases:

```sh
uv run --locked python projects/course-02-agentic-ai/first_line/demo.py --live --case A \
  --max-requests "$MAX_REQUESTS" --max-output-tokens "$MAX_OUTPUT_TOKENS"
```

The case and both limits are checked first. Then `OPENAI_API_KEY` and `OPENAI_MODEL` are read from the local `.env` or the environment. A missing or blank `OPENAI_MODEL` stops the run before any client is built; there is no fallback to the course default. `--max-requests` caps HTTP requests to the provider for the case. Decisions, output repairs, and SDK retries all count. SDK retries are off. When the cap is reached, the next request is refused before it is sent. The agent then hands over with “Provider request cap reached”, without any effect or recovery claim. `--max-output-tokens` is sent as `max_output_tokens` with **each** request, so the case produces at most `MAX_REQUESTS × MAX_OUTPUT_TOKENS` output tokens. Input tokens are measured, not capped. The trace's `pilot` field records the limits, the configured model, and each request's HTTP status. It also records the model and token usage the provider reported. Usage that was not reported stays `null`, also in `completed_model_calls`. It is never counted as zero, and no cost is calculated. The client is closed when the run ends, including after an error. The [offline pilot tests](first_line/test_pilot.py) use a mock HTTP transport.

If a decision cannot be obtained for another reason, the report's `model_failure` gives one code: `output_limit` (the decision's last response stopped at `max_output_tokens`, even after an invalid first answer), `validation_exhausted` (still invalid after the one repair), `provider_error` (HTTP, service or transport failure) or `unknown`. Each attempt records `response_status` and `incomplete_reason` as known codes only, never provider text. A response that merely used all its output tokens is not counted as truncated, and a truncated first reply followed by an ambiguous invalid one stays `unknown`. Since `gateway-m1.7`, a link handover target must exactly match an observed down or degraded link (otherwise the one repair is used). The [follow-up tests](first_line/test_followup.py) cover these paths.

The trace's `pilot` field also records, for each HTTP attempt, the provider-reported `usage.input_tokens_details.cached_tokens` (cache reads) and `cache_write_tokens`. The case totals `reported_cached_tokens` and `reported_cache_write_tokens` are computed independently. A reported 0 stays 0. A missing, invalid, or failed report is `null`, which makes that case total `null`. The OpenAI guide (linked below) describes reads and writes as disjoint subsets of `reported_input_tokens`, so they are never added to it. A pair whose sum exceeds the attempt's input tokens is recorded as `null` for both. There is no price, cost, or hit field. `started_at_utc` records when the run started, which gives the trial order. Source: [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching).

### Context-reuse arms for #21 (opt-in)

Add `--reuse-arm` to a bounded live command to run one [#21](https://github.com/jpboliv/meridian-project/issues/21) arm. Without it, the live request is the unchanged baseline.

| `--reuse-arm` | User JSON for each decision | Cache mode configured by Meridian |
|---|---|---|
| (omitted) | Baseline, with no `current_time` | None |
| `time-first` | `current_time` first | None (provider default, implicit) |
| `time-last` (shared control) | `current_time` last | None (provider default, implicit) |
| `time-last-no-cache` | Same as `time-last` | `{"mode": "explicit"}`, with no `prompt_cache_breakpoint` |

On an output repair, the SDK can add a diagnostic `comparison_response_id` to `prompt_cache_options` in any arm. It is not a breakpoint and does not change the cache policy. With fixed decisions, `time-last` and `time-last-no-cache` send the same substantive model-visible inputs; independent live runs can diverge.

`current_time` is the simulated clock (`HH:MM`), read once when each decision starts. An output repair resends the same value. The incident's own `time`, the observations, the instructions, the tools, the clock, and the limits are unchanged. According to the [OpenAI guide](https://developers.openai.com/api/docs/guides/prompt-caching#choose-a-caching-mode), explicit mode with no breakpoints turns off cache reads and writes. The arm is accepted only when `OPENAI_MODEL` is exactly `gpt-6-luna` (Responses API). Any other name, including a dated or lookalike one, stops the run before a client is built, with no fallback to default caching. If the provider rejects the setting, the attempt records its status and `null` cache usage. The agent hands over (“Model unavailable”), and the request is not resent without the setting. No cache key, retention, TTL, prewarm, or tool-result cache is used.

The [experiment log](docs/experiments.md#context-reuse-arms-prepared-offline) is the run protocol. It covers cost accounting, arm order and cache warmth, and the mocked-wire evidence.

The model chooses reads and proposes an action. Code controls the approval, dispatch, and recovery report. Code also ends the reads when a refresh of stale samples brings nothing new. It then uses link evidence from after that refresh (the model's own link read if the stalled step was `links`, otherwise one new link-monitor read that replaces any earlier one) and writes the sourced handover or names the unresolved evidence, marked `stale_evidence` in the report. A failed new link read cites no link. Only the evaluator reads `first_line/checks/`. Cases A, C, and D form the three-shift story. B has missing readings; in [E the monitor answers with old readings](docs/experiments.md#case-e-the-healthy-but-stale-monitor). Each starts without memory. A live run records provider-reported cache usage, but one run is not a reuse comparison. These runs do not measure cross-shift recall or worker replacement.

## Run the M2 handover comparison (#17)

[#17](https://github.com/jpboliv/meridian-project/issues/17) compares the full v2 runbook alone with the same runbook plus a sourced reminder, on public C and D. Both arms use the M2 scoped shift with the same identity, prompt, limits and a fresh simulator. Only memory differs. The reminder arm first replays a fixed scripted A shift, with no model, whose close saves the reminder. The agreed applicability rule then decides at each decision whether the reminder is shown. Each record says whether it was stored, shown or filtered, and why. From the repository root:

```sh
uv run --locked python projects/course-02-agentic-ai/first_line/handover_study.py
```

With no options, the command runs the 12-slot plan with scripted decisions, the acceptance controls and a summary. The output matches [`offline-study-m2.jsonl`](first_line/offline-study-m2.jsonl). Use `--plan` to print the slot plan and `--slot N` to run one slot. `--live --slot N --max-requests R --max-output-tokens T` runs exactly one planned slot with the model named by `OPENAI_MODEL`. It is a paid run under the same bounds as the single-case pilot, and the owner must authorize its settings and spending first. `--summarize FILE...` grades saved slot records against the plan. It lists unrun slots, failures, cap stops, cache counts and memory costs, and it never replaces a recorded slot. The [experiment log](docs/experiments.md#2026-11-23-m2-handover-comparison-prepared-offline) has the design, the offline results and the limits.

## Run one case in the lab

From the repository root, with no API key:

```sh
uv run --locked streamlit run projects/course-02-agentic-ai/first_line/lab.py
```

Choose one public case, A–E, and press **Executar caso**. The page runs that case through the same `run_case` path as the command above and shows the decision, a Portuguese summary of the next step, key observations, applied effects, the evaluator's checks, and the JSON trace record. Tool identifiers and the original report text stay in English as evidence. Opening the page or changing the selection runs nothing. The lab never calls a model. The page names the [report](docs/relatorio.md) it accompanies.

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
