"""Na raiz do repositório: uv run --locked streamlit run projects/course-02-agentic-ai/first_line/lab.py

Corre um caso público de cada vez com o simulador e o avaliador locais. Não chama nenhum modelo.
"""

import asyncio

import streamlit as st

import demo

CASOS = {
    "A": "Primeiro turno: o gateway de ordens está lento",
    "B": "O mesmo alerta, mas o monitor de instâncias não responde",
    "C": "Segundo turno: o alerta repete-se",
    "D": "Terceiro turno: o alerta repete-se depois de um patch",
    "E": "O monitor responde, mas com leituras antigas",
}
ESTADOS = {"recovered": "recuperado", "needs_operator": "passagem ao operador", "denied": "recusado"}

st.set_page_config(page_title="Meridian · primeira linha", layout="wide")
st.title("Laboratório: o agente de primeira linha da Meridian")
st.write("Escolha um caso e carregue em **Executar**. O simulador arranca do zero e o agente segue decisões "
         "programadas: não há chamadas a modelos nem chave de API. No fim, o avaliador lê o resultado esperado "
         "e verifica o que o simulador registou.")

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
    st.info(f"Resultado do caso {corrido}. Carregue em **Executar** para correr o caso {letra}.")

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
st.write(" → ".join(f"{d['step']} {d['target']}".strip() for d in registo["decisions"]))
if acao := relatorio["action"]:
    st.write(f"Reiniciou **{acao['target']}** no tick {acao['tick']} (aprovação {acao['approval']}, recibo {acao['receipt']}).")
st.write(f"Próximo passo indicado no relatório: *{relatorio['next_step']}*")

st.subheader("Observações principais")
if "instances" in obs:
    st.markdown("**Instâncias** (frescura: a leitura é da hora a que foi pedida?)")
    st.table([{"instância": nome, **{k: v[k] for k in ("memory_pct", "time", "read_at", "freshness")}}
              for nome, v in obs["instances"].items()])
if "missing" in obs:
    st.warning(f"Leitura em falta: {obs['missing']}")
if "links" in obs:
    st.markdown("**Ligações do gateway**")
    st.table([{"destino": nome, **v} for nome, v in obs["links"].items()])
if "recovery" in obs:
    st.markdown(f"**Leituras depois do reinício** ({obs['recovery']['source']})")
    st.table(obs["recovery"]["samples"])

with st.expander("Leituras e ações, por ordem"):
    st.table(registo["reads_and_actions"])
with st.expander("Verificações do avaliador"):
    st.table(registo["checks"])
with st.expander("Registo completo (o mesmo JSON que a linha de comandos escreve)"):
    st.json(registo)
