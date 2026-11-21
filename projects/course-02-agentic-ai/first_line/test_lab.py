"""The lab runs one selected case, only when asked, through the CLI's run path. Offline: no model or key."""

from streamlit.testing.v1 import AppTest

import demo


def test_lab_runs_only_the_selected_case_on_request(monkeypatch):
    ran = []
    real = demo.run_case

    async def counted(path, model=None):
        ran.append((path.name, model))
        return await real(path, model)

    monkeypatch.setattr(demo, "run_case", counted)
    at = AppTest.from_file(str(demo.HERE / "lab.py"), default_timeout=60).run()
    at.selectbox(key="caso").select("B").run()
    assert not at.exception
    assert ran == [] and "resultado" not in at.session_state

    at.button(key="executar").click().run()
    assert not at.exception
    assert ran == [("shift-b.yaml", None)]
    record = at.session_state["resultado"]
    assert record["passed"] and record["applied_effects"] == 0
    assert record["report"]["status"] == "needs_operator"
    assert at.success[0].value.startswith("**Caso B: passou**")
    shown = [m.value for m in at.markdown]
    assert ("Próximo passo: **O monitor de instâncias falhou em order-gateway-1. Obter leituras atuais de "
            "order-gateway-1 e order-gateway-2 antes de comparar instâncias ou reiniciar.**") in shown
    assert not any(m.startswith("Reiniciou") for m in shown)

    at.selectbox(key="caso").select("A").run()
    assert len(ran) == 1
    assert at.info[0].value.startswith("Resultado do caso B.")


def test_lab_shows_the_case_a_restart_and_recovery():
    at = AppTest.from_file(str(demo.HERE / "lab.py"), default_timeout=60).run()
    assert "resultado" not in at.session_state
    at.selectbox(key="caso").select("A").run()
    at.button(key="executar").click().run()
    assert not at.exception
    assert at.success[0].value.startswith("**Caso A: passou**")
    assert [(m.label, m.value) for m in at.metric] == [
        ("Decisão final", "recuperado"), ("Efeitos aplicados", "1"), ("Último tick do agente", "27")]
    shown = [m.value for m in at.markdown]
    assert "Reiniciou **order-gateway-2** no tick 23 (aprovação APR-001, recibo ACT-001)." in shown
    assert "**Leituras depois do reinício** (metrics/order-gateway/26)" in shown
    recovery = at.table[2].value  # instances, links, then the recovery readings
    assert recovery["tick"].tolist() == [24, 25, 26]
    assert recovery["latência (ms)"].tolist() == [6.5, 5.0, 5.0]
