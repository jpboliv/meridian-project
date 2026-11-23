"""#18 specialist handoffs: scope, validation, one follow-up, shared budget, order, and the M2 gates."""

import asyncio
from dataclasses import replace

import pytest
import yaml

from handoff import (READS, SHIFT_CALLS, WRITES, Budget, BudgetExhausted, Reader, ScopeError, Task, TeamLead,
                     application, check, inject, infrastructure)
from m3_demo import CASES, access, handoff_runs, passed, team
from m2_demo import IDENTITY, READERS
from scoped_access import READ
from scoped_memory import ScopedMemory
from workbench import start_exchange


def run(coroutine):
    return asyncio.run(coroutine)


def lead_for(case="A", budget=SHIFT_CALLS, faults=None, credential=None):
    sim = start_exchange(CASES[case])
    chosen = access() if credential is None else access(credential)
    return TeamLead(sim, dict(IDENTITY), chosen, ScopedMemory(), READERS, Budget(budget), faults)


def task_for(lead, specialty, **changes):
    tick = lead.deps.sim.state.tick
    task = Task("INC-4100/shift-1/task-1", lead.brief["incident_id"], {"principal": "requester-1"}, specialty,
                "order-gateway", "q", READS[specialty], tick, tick + 6, lead.budget.remaining())
    return replace(task, **changes)


def test_specialists_are_read_only_and_distinct():
    assert set(READS["application"]).isdisjoint(READS["infrastructure"])
    assert not WRITES & {tool for reads in READS.values() for tool in reads}
    assert not {name for name in dir(Reader) if not name.startswith("_")} - {"call"}


@pytest.mark.parametrize("tool", ["request_approval", "restart_instance", "rollback_change", "read_logs"])
def test_out_of_scope_call_is_refused_before_any_trace_or_tick(tool):
    lead = lead_for()
    reader = Reader(lead, task_for(lead, "infrastructure"))
    tick = lead.deps.sim.state.tick
    with pytest.raises(ScopeError):
        run(reader.call(tool, component="order-gateway"))
    assert lead.tools.trace == [] and lead.deps.sim.state.tick == tick and lead.budget.used == 0


def test_specialist_reads_only_within_the_caller_scope():
    lead = lead_for(credential=replace(access().credential, rights=frozenset()))
    reader = Reader(lead, task_for(lead, "application"))
    with pytest.raises(ScopeError, match="caller's scope"):
        run(reader.call("deployments.get_service", service="order-gateway"))
    assert lead.tools.trace == []


def test_a_blocked_reply_is_a_named_gap_not_evidence():
    lead = lead_for()
    revoke = lead.access

    async def application_blocked(reader, task):
        revoke.credential = replace(revoke.credential, rights=frozenset())  # scope lost mid-task
        try:
            return await application(reader, task)
        finally:
            revoke.credential = replace(revoke.credential, rights=frozenset({READ, "restart_instance"}))

    import handoff
    original = handoff.SPECIALISTS["application"]
    handoff.SPECIALISTS["application"] = application_blocked
    try:
        report = run(lead.run())
    finally:
        handoff.SPECIALISTS["application"] = original
    first = report["team"]["exchanges"][0]
    assert first["verdict"] == "accepted" and first["reply"]["status"] == "blocked"
    assert report["team"]["follow_up"] is None  # blocked is a valid answer, not a missing or invalid one
    assert report["team"]["summary"]["lacking"] == {"application": "blocked"}
    assert report["status"] == "needs_operator" and lead.deps.sim.executor.effects() == []


def test_denied_caller_gets_no_team_round():
    lead = lead_for(credential=replace(access().credential, rights=frozenset()))
    report = run(lead.run())
    assert report["status"] == "denied" and lead.tools.trace == []


def validated(fault, specialty="infrastructure"):
    lead = lead_for()
    task = task_for(lead, specialty)
    reader = Reader(lead, task)
    result = run((infrastructure if specialty == "infrastructure" else application)(reader, task))
    return check(lead, task, inject(result, fault, task), reader.steps)


@pytest.mark.parametrize("fault, verdict, reason", [
    (None, "accepted", None),
    ("drop", "missing", "no reply"),
    ("wrong_task", "invalid", "wrong task ID"),
    ("no_target", "invalid", "missing or wrong target"),
    ("late", "timed_out", None),
    ("unknown_source", "invalid", "unknown source check_link/reference-db/0"),
])
def test_reply_validation(fault, verdict, reason):
    got = validated(fault)
    assert got[0] == verdict
    if reason:
        assert got[1] == reason


def test_a_reply_cannot_cite_another_task_call_or_an_unlisted_source():
    lead = lead_for()
    first = task_for(lead, "infrastructure")
    first_reader = Reader(lead, first)
    first_result = run(infrastructure(first_reader, first))
    second = task_for(lead, "infrastructure", task_id="INC-4100/shift-1/task-2")
    second_reader = Reader(lead, second)
    second_result = run(infrastructure(second_reader, second))
    borrowed = replace(second_result, sources=second_result.sources + first_result.sources[:1])
    assert check(lead, second, borrowed, second_reader.steps)[0] == "invalid"
    unlisted = replace(second_result, sources=second_result.sources[1:])
    assert check(lead, second, unlisted, second_reader.steps) == ("invalid", "finding cites an unknown source")


def test_reads_are_sequential_in_a_fixed_order():
    lead, report, sim = run(team("A"))
    roles = lead.tools.call_roles
    ticks = [call.tick for call in lead.tools.trace]
    assert ticks == sorted(set(ticks))
    first_infra = roles.index("infrastructure")
    assert set(roles[1:first_infra]) == {"application"} and set(roles[first_infra:first_infra + 3]) == {"infrastructure"}
    assert report["team"]["sequential"] is True and report["team"]["order"] == ["application", "infrastructure"]


def test_only_one_follow_up_across_both_specialists():
    lead, report, sim = run(team("D", {"application": ["drop", "drop"], "infrastructure": ["drop"]}))
    assert len(report["team"]["exchanges"]) == 3 and report["team"]["follow_up"]["specialty"] == "application"
    assert report["team"]["summary"]["lacking"] == {"application": "missing", "infrastructure": "missing"}
    assert report["status"] == "needs_operator" and sim.executor.effects() == []
    assert "missing reply is not evidence of health" in report["next_step"]


def test_missing_application_blocks_a_restart_even_when_measurements_support_it():
    lead, report, sim = run(team("A", {"application": ["drop", "drop"]}))
    assert lead.restart_evidence()[1] == "unsupported"  # no accepted ticket
    assert report["status"] == "needs_operator" and sim.executor.effects() == []
    assert all(call.tool != "request_approval" for call in lead.tools.trace)


def test_budget_refusal_is_not_traced_and_does_not_advance_time():
    lead = lead_for(budget=1)
    lead.tools.read_runbook("order-gateway-latency", 2)
    tick = lead.deps.sim.state.tick
    with pytest.raises(BudgetExhausted):
        lead.tools.check_link("order-gateway", "reference-db")
    assert len(lead.tools.trace) == 1 and lead.deps.sim.state.tick == tick


def test_follow_up_must_fit_the_remaining_budget():
    lead, report, sim = run(team("D", {"application": ["drop", "drop"]}, budget=9))
    assert report["team"]["budget"] == {"limit": 9, "used": 9, "by_role": {"lead": 1, "application": 5,
                                                                           "infrastructure": 3}}
    assert report["status"] == "needs_operator" and "budget spent" in report["next_step"]
    assert sim.executor.effects() == []


def test_conflict_settled_by_an_up_read_lets_the_lead_proceed(tmp_path):
    spec = yaml.safe_load(CASES["M"].read_text())
    spec["faults"] = spec["faults"][:2]  # the link stays up after tick 20
    path = tmp_path / "shift-m-up.yaml"
    path.write_text(yaml.safe_dump(spec))
    sim = start_exchange(path)
    lead = TeamLead(sim, dict(IDENTITY), access(), ScopedMemory(), READERS, Budget(SHIFT_CALLS))
    report = run(lead.run())
    assert report["team"]["follow_up"]["separating_read"]["state"] == "up"
    assert report["status"] == "recovered" and len(sim.executor.effects()) == 1


def test_lead_keeps_the_m2_limits_on_effects():
    lead = lead_for("D")
    assert lead.tools.rollback_change("CHG-5100", "k", "APR-001") == {"error": "M2 dispatch denied"}
    assert lead.tools.restart_service("order-gateway") == {"error": "M2 dispatch denied"}
    assert lead.tools.restart_instance("order-gateway-2", "k", "APR-001") == {"error": "M2 dispatch denied"}
    assert lead.deps.sim.executor.effects() == []


def test_lead_only_dispatches_the_restart_and_specialists_make_no_writes():
    lead, report, sim = run(team("A"))
    writes = [(call.tool, role) for call, role in zip(lead.tools.trace, lead.tools.call_roles)
              if call.tool in WRITES]
    assert writes == [("request_approval", "lead"), ("restart_instance", "lead")]
    assert lead.access.permits(lead, READ)


def test_public_handoff_records_pass_their_checks():
    records = run(handoff_runs())
    assert [record["run"] for record in records if not passed(record)] == []
