"""Na raiz do repositório: uv run --locked streamlit run projects/course-02-agentic-ai/first_line/lab.py

Corre um caso público de cada vez com o simulador e o avaliador locais. Não chama nenhum modelo.
Relatório para a apresentação: projects/course-02-agentic-ai/docs/relatorio.md
"""

import asyncio

import streamlit as st

import demo

RELATORIO = "projects/course-02-agentic-ai/docs/relatorio.md"
RELATORIO_URL = f"https://github.com/jpboliv/meridian-project/blob/main/{RELATORIO}"  # só um link; nada é pedido ao abrir
CASOS = {
    "A": "Primeiro turno: o gateway de ordens está lento",
    "B": "O mesmo alerta, mas o monitor de instâncias não responde",
    "C": "Segundo turno: o alerta repete-se",
    "D": "Terceiro turno: o alerta repete-se depois de um patch",
    "E": "O monitor responde, mas com leituras antigas",
}
ESTADOS = {"recovered": "recuperado", "needs_operator": "passagem ao operador", "denied": "recusado"}
PASSOS = {"tickets": "ticket", "instances": "memória das instâncias", "links": "ligações",
          "restart": "reiniciar", "handover": "passar ao operador"}
FRESCURA = {"current": "atual", "stale": "antiga"}
LIGACAO = {"up": "ativa", "degraded": "degradada", "down": "em baixo"}


def proximo_passo(relatorio):
    """Resumo em português, construído só a partir dos campos estruturados do relatório."""
    seguinte = relatorio.get("follow_up") or {}
    if seguinte.get("operation") == "obtain_instance_readings":
        falha = f"O monitor de instâncias falhou em {seguinte['failed']}. " if seguinte.get("failed") else ""
        return (f"{falha}Obter leituras atuais de {' e '.join(seguinte['targets'])} "
                "antes de comparar instâncias ou reiniciar.")
    if seguinte.get("operation") == "investigate_link":
        antigas = sorted({v["time"] for v in relatorio["observations"].get("instances", {}).values()
                          if v["freshness"] == "stale"})
        aviso = f"As leituras das {', '.join(antigas)} não mostram o estado atual. " if antigas else ""
        return (f"{aviso}Investigar a ligação de {seguinte['source']} a {seguinte['target']} "
                f"(observada no tick {seguinte['observed_tick']}) e rever alterações recentes antes de propor uma correção.")
    if relatorio["status"] == "recovered":
        return "Vigiar se volta a acontecer: a recuperação não prova uma correção permanente."
    return None


st.set_page_config(page_title="Meridian · primeira linha", layout="wide")
st.title("Laboratório: o agente de primeira linha da Meridian")
st.write("Escolha um caso e carregue em **Executar caso**. O simulador arranca do zero e o agente segue decisões "
         "programadas: não há chamadas a modelos nem chave de API. No fim, o avaliador lê o resultado esperado "
         "e verifica o que o simulador registou.")
st.caption(f"[Relatório com a arquitetura e os resultados]({RELATORIO_URL}) · sem rede: `{RELATORIO}`")

with st.container(border=True):
    letra = st.selectbox("Caso", list(CASOS), format_func=lambda x: f"{x} · {CASOS[x]}", key="caso")
    if st.button("Executar caso", type="primary", key="executar"):
        with st.spinner(f"A executar o caso {letra}..."):
            st.session_state.resultado = asyncio.run(demo.run_case(demo.HERE / "cases" / f"shift-{letra.lower()}.yaml"))
    st.caption("Abrir a página ou mudar de caso não executa nada.")

registo = st.session_state.get("resultado")
if registo is None:
    st.stop()

corrido = registo["case"].removeprefix("shift-").upper()
if corrido != letra:
    st.info(f"Resultado do caso {corrido}. Carregue em **Executar caso** para correr o caso {letra}.")

relatorio = registo["report"]
obs = relatorio["observations"]
total, certas = len(registo["checks"]), sum(c["pass"] for c in registo["checks"])
(st.success if registo["passed"] else st.error)(
    f"**Caso {corrido}: {'passou' if registo['passed'] else 'falhou'}** ({certas} de {total} verificações do avaliador)")
st.caption(f"Revisão {registo['revision']} · semente {registo['seed']} · {registo['model']}")

a, b, c = st.columns(3)
a.metric("Decisão final", ESTADOS.get(relatorio["status"], relatorio["status"]))
b.metric("Efeitos aplicados", registo["applied_effects"])
c.metric("Último tick do agente", registo["end_tick"])

st.subheader("O que o agente decidiu")
st.write(" → ".join(f"{PASSOS.get(d['step'], d['step'])} {d['target']}".strip() for d in registo["decisions"]))
if acao := relatorio["action"]:
    st.write(f"Reiniciou **{acao['target']}** no tick {acao['tick']} (aprovação {acao['approval']}, recibo {acao['receipt']}).")
if resumo := proximo_passo(relatorio):
    st.write(f"Próximo passo: **{resumo}**")
st.caption(f"Texto original do relatório: {relatorio['next_step']}")

st.subheader("Observações principais")
if "instances" in obs:
    st.markdown("**Memória das instâncias** (frescura: a amostra é da hora a que foi pedida?)")
    st.table([{"instância": nome, "memória (%)": v["memory_pct"], "hora da amostra": v["time"],
               "pedida às": v["read_at"], "frescura": FRESCURA.get(v["freshness"], v["freshness"])}
              for nome, v in obs["instances"].items()])
if "missing" in obs:
    st.warning(f"Leitura em falta (texto original): {obs['missing']}")
if "links" in obs:
    st.markdown("**Ligações do gateway**")
    st.table([{"destino": nome, "estado": LIGACAO.get(v["state"], v["state"]), "tick": v["tick"]}
              for nome, v in obs["links"].items()])
if "recovery" in obs:
    st.markdown(f"**Leituras depois do reinício** ({obs['recovery']['source']})")
    st.table([{"tick": s["tick"], "hora": s["time"], "latência (ms)": s["latency_ms"], "erros (%)": s["error_rate"] * 100}
              for s in obs["recovery"]["samples"]])

with st.expander("Leituras e ações, por ordem (identificadores originais)"):
    st.table(registo["reads_and_actions"])
with st.expander("Verificações do avaliador (texto original)"):
    st.table(registo["checks"])
with st.expander("Registo completo (o mesmo JSON que a linha de comandos escreve)"):
    st.json(registo)
