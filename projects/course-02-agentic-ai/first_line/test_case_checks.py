"""Challenge the public graders with alternate decisions and incomplete evidence."""

import asyncio
from copy import deepcopy
from dataclasses import replace

import pytest

from meridian.agent_runtime import IncidentDeps, identity_for
from meridian.scenarios import load_solution
from meridian.tools import MeridianTools
from case_checks import evaluate_case
from demo import HERE, scripted
from shift import Decision, Shift
from workbench import start_exchange


def run_case(letter, decide=scripted):
    name = f"shift-{letter}.yaml"
    sim = start_exchange(HERE / "cases" / name)
    tools = MeridianTools(sim)
    shift = Shift(IncidentDeps(tools, identity=identity_for("first-line")))
    report = asyncio.run(shift.run(decide))
    solution = load_solution(HERE / "checks" / name)

    def passes(candidate, trace):
        # The course grader advances the simulator to check that recovery holds.
        return evaluate_case(deepcopy(sim), trace, candidate, solution).passed

    return report, tools.trace, passes


def test_missing_monitor_cannot_pass_by_skipping_the_investigation():
    async def skip_monitor(context):
        for step in ("tickets", "links"):
            if step not in context["observations"]:
                return Decision(step=step)
        return Decision(step="handover")

    report, trace, passes = run_case("b", skip_monitor)
    assert report["status"] == "needs_operator"
    assert not any(c.tool == "monitoring.get_instance_datapoints" for c in trace)
    assert not passes(report, trace)


def test_timeout_handover_needs_one_same_target_retry_and_names_the_gap():
    report, trace, passes = run_case("b")
    first, retry = [c for c in trace if c.tool == "monitoring.get_instance_datapoints"]
    assert passes(report, trace)
    assert not passes(report, [c for c in trace if c is not first])
    wrong = replace(retry, args={**retry.args, "instance": "order-gateway-2"})
    assert not passes(report, [wrong if c is retry else c for c in trace])
    denied = replace(first, error="access denied", result={"error": "access denied", "retryable": False})
    assert not passes(report, [denied if c is first else c for c in trace])
    assert not passes({**report, "next_step": "Please investigate.", "follow_up": {}}, trace)


def test_link_checked_before_the_timeout_cannot_substitute_for_a_fresh_probe():
    async def links_first(context):
        if "links" not in context["observations"]:
            return Decision(step="links")
        return await scripted(context)

    report, trace, passes = run_case("b", links_first)
    assert passes(report, trace)
    last_timeout = max(c.step for c in trace if c.error)
    early = [c for c in trace if c.step <= last_timeout]
    prior = deepcopy(report)
    prior["observations"]["links"] = {
        c.args["target"]: {"state": c.result["state"], "tick": c.tick} for c in early if c.tool == "check_link"
    }
    assert not passes(prior, early)


@pytest.mark.parametrize("letter", ["a", "c"])
def test_recovery_needs_three_observed_samples_after_the_applied_receipt(letter):
    report, trace, passes = run_case(letter)
    metrics = [c for c in trace if c.tool == "read_metrics"]

    def retaining(only):
        return [c for c in trace if c.tool != "read_metrics" or c is only]

    # One call can return all three readings. The first call only saw one post-action tick.
    assert passes(report, retaining(metrics[-1]))
    assert not passes(report, retaining(metrics[0]))
    missing = deepcopy(report)
    del missing["observations"]["recovery"]["samples"]
    assert not passes(missing, trace)
    invented = deepcopy(report)
    invented["observations"]["recovery"]["samples"][0]["latency_ms"] = 1.0
    assert not passes(invented, trace)
    assert not passes({**report, "action": {**report["action"], "tick": 0}}, trace)


@pytest.mark.parametrize("fault", ["starts_at_restart", "gap", "latency_at_limit", "errors_at_limit"])
def test_matching_the_source_alone_does_not_make_a_window_healthy(fault):
    report, trace, passes = run_case("a")
    metrics = [c for c in trace if c.tool == "read_metrics"]
    call = metrics[-2] if fault == "starts_at_restart" else metrics[-1]
    rows = deepcopy(call.result["readings"])
    for row in rows:
        row.update(latency_ms=5.0, error_rate=0.001)
    if fault == "starts_at_restart":
        assert rows[0]["tick"] == report["action"]["tick"]
    elif fault == "gap":
        rows[1] = rows[0].copy()
    elif fault == "latency_at_limit":
        rows[1]["latency_ms"] = 20.0
    else:
        rows[1]["error_rate"] = 0.01
    report["observations"]["recovery"] = {
        "source": call.result["source_ref"],
        "samples": [{k: row[k] for k in ("tick", "time", "latency_ms", "error_rate")} for row in rows],
    }
    altered = replace(call, result={**call.result, "readings": rows})
    assert not passes(report, [altered if c is call else c for c in trace])


def test_changed_cause_accepts_a_paraphrase_but_requires_the_cited_degraded_link():
    report, trace, passes = run_case("d")
    assert passes({**report, "next_step": "Inspect the gateway’s database path."}, trace)
    assert not passes({**report, "follow_up": {}}, trace)
    wrong = {**report["follow_up"], "target": "matching-engine"}
    assert not passes({**report, "follow_up": wrong}, trace)
    wrong = {**report["follow_up"], "observed_tick": 0}
    assert not passes({**report, "follow_up": wrong}, trace)
    assert not passes(report, [c for c in trace if c.tool != "check_link"])
