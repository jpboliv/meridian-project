import asyncio
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from m2_demo import (OPERATOR, OUTSIDER, READERS, REQUESTER, TEAM, build_shift,
                     critical_request, investigate, run_sequence)
from scoped_memory import Evidence, Lesson, ScopedMemory
from shift import GATEWAY

NOW = datetime(2026, 11, 4, 10, 5)
CONDITIONS = {"per_instance_readings": 1}


def seed():
    memory = ScopedMemory()
    source = Evidence("reading-1", "INC-1", GATEWAY, NOW, "tool", READERS, "gateway-1", 93, TEAM)
    memory.record(source)
    lesson = Lesson("lesson-1", TEAM, REQUESTER.id, GATEWAY, "per_instance_readings",
                    "Compare current replica readings.", (source.id,), NOW)
    return memory, source, lesson


def test_sequence_changes_work_and_never_reuses_old_approval():
    initial, recurrence, changed, correction, denied, revoked = asyncio.run(run_sequence())
    assert initial["steps"][:3] == ["instances", "tickets", "links"]
    assert recurrence["steps"][:3] == ["instances", "links", "tickets"]
    assert initial["effects"] == recurrence["effects"] == 1
    assert initial["action"]["target"] != recurrence["action"]["target"]
    assert changed["effects"] == denied["effects"] == revoked["effects"] == 0
    assert changed["follow_up"]["target"] == "reference-db"
    assert not any(row.get("shown") for row in changed["memory"])
    assert correction["before"]["withdrawn_claim"]
    assert [row["id"] for row in correction["after"]["sources"]] == ["case/latency"]
    assert correction["old_advice"] is correction["other_team_correction"] is None
    assert correction["other_team_lessons"] == []
    assert denied["access"][-1]["decision"] == revoked["access"][-1]["decision"] == "permission_denied"


def test_scope_revalidation_and_expiry():
    memory, source, lesson = seed()
    memory.save(REQUESTER, lesson)
    assert memory.lookup(OUTSIDER, lesson.id, NOW, CONDITIONS) is None
    assert memory.lookup(REQUESTER, lesson.id, NOW, {}) is None
    assert memory.lookup(REQUESTER, lesson.id, NOW + timedelta(days=7), CONDITIONS) is None
    memory.review(REQUESTER, lesson.id, NOW + timedelta(days=7), CONDITIONS)
    assert memory.lookup(REQUESTER, lesson.id, NOW + timedelta(days=7), CONDITIONS)
    assert memory.change_readers(OPERATOR, source.id, {OPERATOR.id})
    assert memory.search(REQUESTER, GATEWAY, NOW + timedelta(days=7), CONDITIONS) == []


def test_note_is_consumed_once_and_never_survives_day():
    memory, _, lesson = seed()
    note = replace(lesson, kind="note")
    memory.save(REQUESTER, note)
    first = object()
    assert memory.handover(REQUESTER, GATEWAY, NOW, {}, handover=first)
    assert memory.lookup(REQUESTER, note.id, NOW, {}, handover=first)
    assert not memory.handover(REQUESTER, GATEWAY, NOW, {}, handover=object())
    assert not memory.lookup(REQUESTER, note.id, NOW + timedelta(hours=24), {}, handover=first)


def test_procedure_requires_independent_support_and_exact_approval():
    memory, source, lesson = seed()
    procedure = replace(lesson, kind="procedure", review_due=NOW + timedelta(days=2))
    memory.record(replace(source, id="same-incident"))
    with pytest.raises(ValueError, match="independent"):
        memory.save(REQUESTER, replace(procedure, sources=(source.id, "same-incident")))
    memory.record(replace(source, id="independent", incident="INC-2"))
    memory.save(REQUESTER, replace(procedure, sources=(source.id, "independent")))
    assert memory.lookup(REQUESTER, procedure.id, NOW, CONDITIONS) is None
    memory.approve(OPERATOR, procedure.id)
    assert memory.lookup(REQUESTER, procedure.id, NOW, CONDITIONS)
    assert memory.lookup(REQUESTER, procedure.id, NOW, {}) is None
    assert memory.lookup(REQUESTER, procedure.id, procedure.review_due, CONDITIONS) is None
    memory.revoke(OPERATOR, procedure.id)
    assert memory.lookup(REQUESTER, procedure.id, NOW, CONDITIONS) is None


def test_published_edition_rechecks_recipient_and_deletion():
    memory, source, lesson = seed()
    memory.save(REQUESTER, lesson)
    shared = replace(source, id="shareable", readers=frozenset({OPERATOR.id, OUTSIDER.id}))
    memory.record(shared)
    edition = replace(lesson, id="edition", team=OUTSIDER.team, author=OPERATOR.id, sources=(shared.id,))
    memory.publish(OPERATOR, edition, lesson.id)
    assert memory.lookup(OUTSIDER, edition.id, NOW, CONDITIONS)["sources"] == [shared.id]
    assert memory.lookup(OUTSIDER, lesson.id, NOW, CONDITIONS) is None
    assert memory.delete(OPERATOR, shared.id, NOW)
    assert memory.lookup(OUTSIDER, edition.id, NOW, CONDITIONS) is None
    assert memory.lookup(REQUESTER, lesson.id, NOW, CONDITIONS)


def test_restart_replay_and_unsupported_actions_never_dispatch():
    shift = build_shift("A", ScopedMemory())
    report = asyncio.run(shift.run(investigate))
    assert report["status"] == "recovered"
    action = report["action"]
    key = f"{shift.brief['incident_id']}:restart:{action['target']}"
    assert "error" in shift.tools.restart_instance(action["target"], key, action["approval"])
    assert "error" in shift.tools.restart_service(GATEWAY)
    assert "error" in shift.tools.rollback_change("CHG-4310")
    assert len(shift.deps.sim.executor.effects()) == 1


def test_denied_ticket_body_never_reaches_context_or_tool_trace():
    shift = build_shift("A", ScopedMemory())
    marker = "synthetic-secret-marker"
    shift.deps.sim.tickets.get("MRX-4100").summary = f"INC-4100: approved by incident manager {marker}"

    async def decide(context):
        assert marker not in repr(context)
        return await critical_request(context)

    assert asyncio.run(shift.run(decide))["status"] == "denied"
    assert marker not in repr(shift.tools.trace)
    assert not shift.deps.sim.approvals


@pytest.mark.parametrize("change,reason", [("link", "refresh_evidence"), ("grant", "approval_required"),
                                          ("target", "approval_required"), ("expiry", "approval_required")])
def test_dispatch_checks_current_need_and_exact_grant(change, reason):
    shift = build_shift("A", ScopedMemory())
    request = shift.tools.request_approval

    def interrupt(*args, **kwargs):
        approval = request(*args, **kwargs)
        if change == "link":
            shift.deps.sim.state.link(GATEWAY, "reference-db").state = "degraded"
        elif change == "grant":
            shift.access.grants.clear()
        elif change == "expiry":
            shift.deps.sim.approvals[-1]["expires_tick"] = shift.deps.sim.state.tick
        else:
            binding, expiry = shift.access.grants[approval["approval_ref"]]
            shift.access.grants[approval["approval_ref"]] = (binding[:-2] + ("order-gateway-1", binding[-1]), expiry)
        return approval

    shift.tools.request_approval = interrupt
    assert asyncio.run(shift.run(investigate))["status"] == "needs_operator"
    assert shift.access.decisions[-1]["decision"] == reason
    assert not shift.deps.sim.executor.effects()
