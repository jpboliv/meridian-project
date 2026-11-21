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

    at.selectbox(key="caso").select("A").run()
    assert len(ran) == 1
    assert at.info[0].value.startswith("Resultado do caso B.")
