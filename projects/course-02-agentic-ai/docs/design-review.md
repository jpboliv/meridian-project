# Meridian: does yesterday’s fix still apply?

Specification review · 19 November 2026

## The short version for Luís

### Para apresentar à turma (cerca de um minuto)

> Vou usar a Meridian para aprofundar dois temas das aulas: caching e avaliação. Quero perceber se consigo reduzir o custo de investigar um incidente sem piorar a decisão do agente.
>
> A ideia veio de um artigo da Helloform. A cada passo, o agente volta a enviar as mesmas instruções. Se o início do pedido se mantiver igual, o fornecedor do modelo pode reaproveitar esse trabalho. Vou testar duas versões: numa, a hora muda logo no início do pedido; na outra, vai no fim. O conteúdo é o mesmo.
>
> A Meridian dá-me uma forma de avaliar isto: consigo repetir o mesmo alerta, «as ordens estão lentas», mas mudar a causa. Ontem era o gateway; hoje é a ligação à base de dados. Vou medir quanto custou investigar cada incidente e ver que decisão o agente tomou. Se gastar menos mas reiniciar um gateway saudável, a versão mais barata falhou.

### Se o Luís perguntar como vou medir

Vou repetir cada incidente com o mesmo modelo, as mesmas ferramentas e o mesmo estado inicial. Só muda a posição da hora no pedido. Para cada versão, vou registar quantos tokens de entrada o fornecedor indica ter reutilizado, o custo do incidente inteiro e as leituras que justificaram a decisão. O que se reutiliza é o início do pedido. O agente continua a consultar os dados do turno atual; não recebe o diagnóstico de ontem como resposta.

Se os pedidos forem demasiado curtos e o fornecedor registar zero tokens em cache, isso também é um resultado. Se não fornecer essa métrica, fica como desconhecida. Para já, testei cinco casos com decisões programadas. Num deles, o monitor responde às dez, mas a leitura é das nove. A comparação com o modelo ainda está por fazer.

## One decision from start to finish

In the separate handover experiment, a shift credits a 10:05 restart for a drop in latency that began at 10:02. The times rule out one claim: the restart did not start the recovery. They do not tell us what caused it or whether the restart helped later.

Two gateway instances answer orders. On the first shift, the agent compares their memory use. One exceeds the limit in the current runbook, the service's operating procedure. The agent checks the links that the gateway depends on. With healthy links and approval for that instance, it requests one restart.

The action record tells the operator that the restart ran. It does not tell the operator that orders are fast again. For gateway version 2.4, the [runbook](../../../meridian/data/runbooks/order-gateway-latency-v2.md) calls for three consecutive readings after the action. Latency must fall below 20 milliseconds and the error rate below 1%. A restart can restore service without fixing the underlying memory leak.

The next shift inherits the question “Which instance has high memory use?” It does not inherit a target or permission to restart. On the third shift, memory is normal and the database link is slow. A good agent changes direction. If an upgrade leaves only an average across all instances, the agent cannot declare every instance healthy.

## What is settled and what is ready for review

Agreed means the owner reviewed the decision. This covers the shift inputs, the evidence for a lesson, corrections, source deletion, shortened handovers, and the main comparison measures. The [handover decision](https://github.com/jpboliv/meridian-agents/issues/5#issuecomment-6976560131) and [deletion decision](https://github.com/jpboliv/meridian-agents/issues/6#issuecomment-7008518875) record two examples.

Draft means that the owner delegated the choice and can review it here. The draft sets defaults for all eleven design issues. These include who can share a lesson, how many calls a shift gets, and when a worker can retry. Implemented means working project behavior with evidence. No project milestone has that status.

The submission deadline is 30 November 2026 at 23:59 Lisbon time (`Europe/Lisbon`).

## What the early trials showed

One fresh agent read a shortened handover. It found the [10:02 drop in latency](cases/restart/latency.md) and the [10:05 restart](cases/restart/actions.md). Recovery began before the restart. The readings ended at 10:03, so they did not establish whether the restart helped later. The prompt explicitly asked the agent to verify the sources.

Four other read-only shifts crossed two choices: with or without a lesson, and individual memory readings or a fleet average. All four read the same three sources and recommended investigating the slow database link. Both agents with only an average left individual memory use unknown.

These five trials used synthetic files. None used a simulator action. They did not establish a benefit from recall, caching, specialist work, or automatic shortening. The [experiment log](experiments.md) records the conditions. The [evaluation specification](specs/evaluation.md) defines the comparisons that still need results.

The [five M1 simulator traces](experiments.md#case-e-the-healthy-but-stale-monitor) use scripted decisions. Two cases restart different targets. Three hand over: missing readings, a changed cause, and a healthy sample from before the alert. They test the software around the model. Live model behavior and the value of reuse still need measurements.

## What we took from Helloform

Fred Oliveira’s [“Lessons in harness design: context, compaction and memory”](https://helloform.com/blog/harness-design-part-1/) suggests ordering sections of a request by how often they change. The timestamp experiment above tests that idea. The table also records follow-up ideas: prompt fingerprints, caching tool results, and comparing summary costs are optional.

Context is the material the model sees in one call. A token is a unit of model text. A cache stores work for reuse. A fingerprint identifies the exact contents of a section.

| Article idea | Meridian decision | How we will tell whether it works |
|---|---|---|
| Budget the whole request | The harness counts rules, tools, lessons, history, and current notes. Specialists share the shift budget. | Report token counts by section and whether the deciding agent saw the unusual log line. |
| Name the pieces and order them by how often they change | Put common rules and sorted tool definitions first. Put time and request IDs last. Use the same rules across roles. | Compare section fingerprints between calls. Report the first changed section separately from provider-reported reuse. |
| Preserve a stable start to the request | Append ordinary updates with an explicit replacement. Fold them into the next summary. Remove withdrawn, deleted, or forbidden material before the next call. | After deletion or a permission change, inspect the actual model input. No stale copy can survive to save a cache hit. |
| Shorten early and write for a successor | Reserve room for a summary. Keep the latest relevant words, exact action labels, timestamps, uncertainty, and receipt IDs. | Give a fresh shift the restart summary. It must distinguish the start of recovery from a possible later effect. |
| Let the reader return to the source | Index the retained, permitted history by source and range. Refresh the current lesson at each summary. | The next shift can reopen both original timing records while they exist. Deletion removes the reference and copied material. |
| Choose when and what to remember | Save evidence during the shift. Save supported clues at handover. Send a small, ranked selection and allow scoped search for the rest. | Compare the same clue through lookup and automatic handover. Count the cost of recording and correcting it. |
| Keep origin separate from authority | Attribute reports, tool readings, and agent inferences. A lesson never grants permission. | Copied ticket text cannot authorize a restart or turn itself into a procedure. |
| Count the cost of reuse | Start with the same model for summaries. Record provider cache reads and writes when available. Cached tokens still take up space. | Compare total input, output, and cost over the shift. Test another summary model only if the first comparison justifies it. |

## Sources and later presentation

The course brief is [*Projeto Agentic AI*](../references/Projeto%20Agentic%20AI.pdf), by Luís Noronha. Pages 4–7 define the milestones and minimum capabilities. Pages 9–10 describe assessment and delivery. The [simulator guide](../../../meridian/README.md), [session guide](../../../sessions/course-02-agentic-ai/README.md), and [project roadmap](../../../ROADMAP.md) distinguish supplied features from project work.

The [Hugging Face animation](https://huggingface.co/blog/harness-hub/harness-adapters) is a visual reference only. For a later illustration, show the agent, evidence sources, and executor in separate lanes. Move one observation at a time. At 10:05, the caption can show that the executor recorded the restart.
