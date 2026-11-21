"""Exercise decisions that the executor would otherwise accept for a noncritical service."""

import asyncio
from copy import deepcopy

from pydantic_ai.models.test import TestModel
from meridian.agent_runtime import IncidentDeps, identity_for
from meridian.scenarios import load_scenario, load_solution
from meridian.simulator import Simulator
from meridian.tools import MeridianTools

from demo import HERE, scripted
from case_checks import evaluate_case
from shift import Decision, Shift, live_decider
from workbench import start_exchange


def start(**changes):
    case = load_scenario(HERE / "cases/shift-a.yaml")
    for name, value in changes.items():
        setattr(case, name, value)
    sim = Simulator(case)
    return Shift(IncidentDeps(MeridianTools(sim), identity=identity_for("first-line")))


def test_provider_decision_cannot_restart_without_source_evidence():
    shift = start()
    calls = []
    model = TestModel(custom_output_args={"step": "restart", "target": "order-gateway-2"})
    report = asyncio.run(shift.run(live_decider(model, calls)))
    assert report["status"] == "needs_operator"
    assert calls[0]["requests"] == 1
    assert not shift.deps.sim.approvals and not shift.deps.sim.executor.effects()


def test_no_effect_when_operator_denies_after_valid_evidence():
    shift = start(approver={"mode": "deny_all"})
    report = asyncio.run(shift.run(scripted))
    assert report["status"] == "denied"
    assert shift.deps.sim.approvals[0]["target"] == "order-gateway-2"
    assert not shift.deps.sim.executor.effects()


def test_wrong_instance_refused_even_with_a_real_fault():
    async def wrong(context):
        decision = await scripted(context)
        return Decision(step="restart", target="order-gateway-1") if decision.step == "restart" else decision

    shift = start()
    assert asyncio.run(shift.run(wrong))["status"] == "needs_operator"
    assert not shift.deps.sim.executor.effects()


def test_lost_reply_reconciled_and_recovery_measured_after_effect():
    shift = start(executor={"drop_response": [{"action": "restart_instance", "call": 1}]})
    report = asyncio.run(shift.run(scripted))
    effect, = shift.deps.sim.executor.effects()
    assert any(c.tool == "action_status" for c in shift.tools.trace)
    assert report["action"]["receipt"] == effect.action_id
    assert report["status"] == "recovered"
    samples = report["observations"]["recovery"]["samples"]
    assert len(samples) == 3 and all(s["tick"] > effect.tick for s in samples)


def test_receipt_is_not_a_recovery_reading():
    shift = start(tools={"read_metrics": {"unavailable": True}})
    report = asyncio.run(shift.run(scripted))
    assert len(shift.deps.sim.executor.effects()) == 1
    assert report["status"] == "needs_operator" and report["action"]["receipt"]
    assert "recovery" not in report["observations"]


def test_stale_handover_needs_original_timestamp_and_independent_evidence():
    sim = start_exchange(HERE / "cases/shift-e.yaml")
    shift = Shift(IncidentDeps(MeridianTools(sim), identity=identity_for("first-line")))
    report = asyncio.run(shift.run(scripted))
    solution = load_solution(HERE / "checks/shift-e.yaml")

    def passed(candidate, trace):
        return evaluate_case(sim, trace, candidate, solution).passed

    trace = shift.tools.trace
    assert report["status"] == "needs_operator" and not sim.executor.effects()
    assert passed({**report, "next_step": "Inspect the database path."}, trace)
    assert not passed({**report, "status": "recovered"}, trace)
    assert not passed({**report, "follow_up": {}}, trace)
    assert not passed(report, [c for c in trace if c.tool != "check_link"])
    misdated = deepcopy(report)
    sample = next(iter(misdated["observations"]["instances"].values()))
    sample["time"] = sample["read_at"]
    assert not passed(misdated, trace)


def test_hot_historical_sample_cannot_authorize_a_restart():
    case = load_scenario(HERE / "cases/shift-a.yaml")
    case.tools["metric_collector"] = {"component": "order-gateway", "last_poll_tick": 14}
    sim = start_exchange(case)
    shift = Shift(IncidentDeps(MeridianTools(sim), identity=identity_for("first-line")))

    async def ignore_age(context):
        if "links" in context["observations"]:
            return Decision(step="restart", target="order-gateway-2")
        return await scripted(context)

    report = asyncio.run(shift.run(ignore_age))
    assert report["observations"]["instances"]["order-gateway-2"]["memory_pct"] > 90
    assert report["status"] == "needs_operator"
    assert not sim.approvals and not sim.executor.effects()
