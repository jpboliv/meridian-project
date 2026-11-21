# Meridian: o agente de primeira linha

Projeto Agentic AI · M1 testado offline (`gateway-m1.6`) · um piloto real em `gateway-m1.5` (caso B, falhou), sem linha de base

## Pergunta

O alerta diz «o gateway de ordens está lento». Em modo real, o agente reenvia ao modelo as mesmas instruções a cada passo. **Quando é que reutilizar contexto reduz o custo de investigar um incidente, e que evidência tem o agente de recolher de novo antes de agir?** Um reinício errado mais barato conta como falha.

- **Cache do fornecedor ([#21](https://github.com/jpboliv/meridian-project/issues/21)).** Primeiro, a hora simulada no início ou no fim da mensagem do utilizador; um texto comum pode não acabar num ponto elegível da cache, e só o fornecedor reporta leituras. Depois, hora no fim com cache automática contra desligada. Escrever na cache custa mais do que a entrada normal; só compensa se o incidente ficar mais barato com o mesmo resultado.
- **Lembrete com fonte.** Runbook completo contra runbook com lembrete, em C (novo alvo: instância 1) e D (nova causa: ligação à base de dados); o lembrete não dispensa leituras atuais.
- **Correção (teste proposto).** A latência começou a descer às 10:02 e o reinício foi às 10:05. Isto exclui que o reinício tenha iniciado a recuperação, não que tenha ajudado depois.

## Arquitetura

```mermaid
flowchart LR
  alerta["Alerta, runbook e ticket"]
  subgraph M1["M1: implementado e testado offline"]
    decisor["Decisor: guião fixo ou modelo com --live"]
    codigo["Código: valida leituras, pede aprovação, executa uma vez, verifica a recuperação"]
    sim["Simulador do curso: serviços MCP, aprovador e executor"]
    relatorio["Relatório: recuperado ou passagem ao operador"]
  end
  subgraph AVAL["Avaliador: respostas inacessíveis ao agente"]
    esperado["Resultado esperado"]
    veredito["Passou ou falhou"]
  end
  subgraph R21["#21: ligado, ainda sem medição"]
    cache["Hora no início ou no fim; cache automática ou desligada"]
  end
  subgraph FUT["Futuro, ainda não implementado"]
    m2["M2: memória entre turnos"]
    m3["M3: líder, especialistas e retoma"]
  end
  alerta --> decisor
  decisor -- "próxima leitura ou ação proposta" --> codigo
  codigo -- "pedidos" --> sim
  sim -- "observações e recibos" --> codigo
  codigo -- "observações validadas" --> decisor
  codigo --> relatorio
  relatorio --> veredito
  sim -- "chamadas e efeitos registados" --> veredito
  esperado --> veredito
  cache -.-> decisor
  m2 -.-> decisor
  m3 -.-> codigo
```

O modelo só propõe; a aprovação, o reinício único e a verificação ficam no código.

```mermaid
flowchart TD
  inicio["Ticket, memória de cada instância e duas ligações"]
  inicio -- "A e C: só uma instância acima de 90 %, leituras atuais, ligações ativas" --> reinicio["Aprovação on-call, um reinício, três leituras saudáveis"]
  inicio -- "B: monitor sem resposta duas vezes na instância 1" --> faltas["Passagem: pedir leituras das instâncias 1 e 2"]
  inicio -- "D e E: ligação à base de dados degradada" --> ligacao["Passagem: investigar a ligação"]
```

## Evidência

Os cinco casos passaram com decisões programadas em `gateway-m1.6`, com os mesmos resultados de `gateway-m1.5` ([registos](../first_line/offline-traces-m1.6.jsonl)). Com modelo real houve apenas um piloto, no caso B, ainda em `gateway-m1.5` (ver abaixo).

**Reinício, caso A.** A instância 2 estava a 93,9 % de memória e as ligações ativas. Após o reinício aprovado (tick 23): 6,5, 5,0 e 5,0 ms. [Registo A](../first_line/offline-traces-m1.6.jsonl#L1).

**Falha controlada, caso B (programado).** O monitor falhou duas vezes na instância 1; a 2 nunca foi lida. Sem reinício, o agente pediu leituras das duas. [Registo B](../first_line/offline-traces-m1.6.jsonl#L2).

**Piloto real, caso B (21 nov. 2026, `gateway-m1.5`), distinto do B programado.** Numa única execução com `gpt-6-luna`, o modelo pesquisou os tickets três vezes, mesmo com o MRX-4100 já encontrado. Nunca leu o monitor nem a ligação, e o avaliador deu falha nessas verificações. Passou ao operador sem efeitos. Não é linha de base nem resultado do #21; a causa está por apurar. [Registo do piloto](../first_line/live-pilot-b-2026-11-21.jsonl#L1). Numa reconstrução offline, o segundo e o terceiro pedidos saíram idênticos e mantinham a instrução de começar pelo ticket; a revisão `gateway-m1.6` torna essa correlação condicional, mas ainda não foi testada com o modelo real ([registo offline](experiments.md#2026-11-21-the-completed-ticket-read-offline-gateway-m16)).

**Prefixo, offline.** Em 13 pares de decisões seguidas, o JSON do utilizador partilha 22 bytes iniciais (mediana) com a hora no início e 920 com ela no fim. São bytes, não tokens: não mostram leituras da cache nem se o prefixo chega aos 1024 tokens exigidos ([notas](experiments.md#context-reuse-arms-prepared-offline)).

## Experimentar

Na raiz do repositório:

```sh
uv run --locked streamlit run projects/course-02-agentic-ai/first_line/lab.py
```

Escolha um caso de A a E e carregue em **Executar caso**.

## Utilização de IA

Escrito com assistentes de IA, incluindo o Claude Code; os resultados programados acima não usam nenhum modelo; só o piloto real do caso B usou o `gpt-6-luna`.
