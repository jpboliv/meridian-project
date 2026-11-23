import asyncio
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

import scoped_access
from m2_demo import (CREDENTIAL, OPERATOR, OUTSIDER, READERS, REQUESTER, TEAM, build_shift,
                     critical_request, investigate, run_sequence)
from scoped_access import READ
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


def run(shift, decide=investigate):
    return asyncio.run(shift.run(decide))


def by_case():
    return {row["case"]: row for row in asyncio.run(run_sequence())}


def test_public_sequence():
    rows = by_case()
    initial, recurrence, control = rows["initial"], rows["recurrence"], rows["recurrence without memory"]
    assert initial["steps"] == control["steps"] == ["instances", "tickets", "links", "restart"]
    assert recurrence["steps"] == ["instances", "links", "tickets", "restart"]
    assert rows["C with and without memory"]["same_outcome"] is True
    assert recurrence["action"] == control["action"] and recurrence["effects"] == control["effects"] == 1
    assert initial["action"]["target"] != recurrence["action"]["target"]
    clue = next(row for row in initial["memory"] if "saved" in row)
    assert any("/check_link/" in ref for ref in clue["sources"]) and "links reference-db up" in clue["text"]

    changed, second = rows["changed conditions"], rows["next shift, same incident"]
    assert changed["effects"] == second["effects"] == 0
    assert not any(row.get("shown") for row in changed["memory"])
    assert second["shift"] == "INC-4300/shift-2" and second["steps"][0] == "links"
    assert {"INC-4300/shift-1/open-link"} == {key for row in second["memory"] for key in row.get("shown", [])}
    notes = rows["shift notes after the second handover"]
    assert notes["first_note"] is None and notes["fresh_note_pending"] is True

    denied, revoked, linked = rows["critical change denied"], rows["credential revoked after grant"], rows["link degraded after grant"]
    assert denied["effects"] == revoked["effects"] == linked["effects"] == 0
    assert denied["access"][-1]["decision"] == revoked["access"][-1]["decision"] == "permission_denied"


def test_correction_arrives_before_the_next_decision_and_survives_deletion():
    rows = by_case()
    first, second = rows["restart after the link cleared"], rows["next shift corrects the claim"]
    assert first["effects"] == 1 and second["effects"] == 0 and "restart" not in second["steps"]
    check = next(row for row in second["memory"] if "checked_claim" in row)
    decisions = [row for row in second["memory"] if "shown" in row]
    assert check["assessment"] == "contradiction" and check["tick"] < decisions[0]["tick"]
    assert all(row["corrections"] == ["INC-4400/outgoing-claim"] for row in decisions)
    assert second["reads"][0] == "read_metrics" and second["old_claim_lookup"] is None
    times = {row["fact"]: row["time"] for row in second["correction"]["sources"]}
    assert times["latency_drop"] < times["restart"] and second["correction"]["withdrawn_claim"]
    deleted = rows["restart receipt deleted"]
    assert [row["fact"] for row in deleted["correction"]["sources"]] == ["latency_drop"]
    assert "no longer establish" in deleted["correction"]["conclusion"]
    assert deleted["old_claim_lookup"] is deleted["other_team_correction"] is None
    assert deleted["other_team_lessons"] == []


def test_first_context_carries_the_correction():
    memory = ScopedMemory()
    first = build_shift("R", memory)
    run(first)
    ref = f"{first.shift_id}/handover"
    memory.record(Evidence(ref, "INC-4400", GATEWAY, first.now(), "reported", READERS, "claimed_cause", "restart", TEAM))
    memory.save(REQUESTER, Lesson("claim", TEAM, REQUESTER.id, GATEWAY, "restart_started_recovery",
                                  "Restarting the gateway fixed the delay.", (ref,), first.now()))
    contexts = []

    async def decide(context):
        contexts.append(context)
        return await investigate(context)

    run(build_shift("R", memory, sim=first.deps.sim), decide)
    assert contexts[0]["corrections"][0]["withdrawn_claim"] == "Restarting the gateway fixed the delay."
    assert all(item["id"] != "claim" for context in contexts for item in context["handover"])


def test_reference_documents_contradict_the_claim():
    """Library-level check on the agreed reference values: 10:02 latency drop, 10:05 restart."""
    memory = ScopedMemory()
    when = datetime(2026, 11, 3, 10, 5)
    memory.record(Evidence("report", "INC-4000", GATEWAY, when, "reported", READERS, "claimed_cause", "restart", TEAM))
    memory.save(REQUESTER, Lesson("old", TEAM, REQUESTER.id, GATEWAY, "restart_started_recovery",
                                  "Restarting the gateway fixed the delay.", ("report",), when))
    memory.record(Evidence("latency", "INC-4000", GATEWAY, when.replace(minute=2), "document", READERS,
                           "latency_drop", 740, TEAM))
    memory.record(Evidence("actions", "INC-4000", GATEWAY, when, "document", READERS, "restart", GATEWAY, TEAM))
    assert memory.assess_restart_claim(REQUESTER, "old", ("latency",), when) == "possible_conflict"
    assert memory.assess_restart_claim(REQUESTER, "old", ("latency", "actions"), when) == "contradiction"
    assert memory.lookup(REQUESTER, "old", when, {"restart_started_recovery": 1}) is None


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


def test_record_and_save_never_replace_history():
    memory, source, lesson = seed()
    memory.record(source)  # identical: no-op
    with pytest.raises(ValueError):
        memory.record(replace(source, value=12))
    memory.save(REQUESTER, lesson)
    memory.save(REQUESTER, lesson)
    with pytest.raises(ValueError):
        memory.save(REQUESTER, replace(lesson, text="Other text."))
    assert memory.sources[source.id] == source and memory.lessons[lesson.id] == lesson


def test_two_shifts_of_one_incident_keep_separate_records():
    memory = ScopedMemory()
    first = build_shift("A", memory)
    assert run(first)["status"] == "recovered"
    saved = dict(memory.sources), dict(memory.lessons)
    second = build_shift("A", memory)  # same incident and the same ticks in a fresh simulator
    report = run(second)
    assert report["status"] == "recovered" and "memory_error" not in report
    assert (first.shift_id, second.shift_id) == ("INC-4100/shift-1", "INC-4100/shift-2")
    assert all(memory.sources[key] == value for key, value in saved[0].items())
    assert all(memory.lessons[key] == value for key, value in saved[1].items())
    assert {"INC-4100/shift-1/compare", "INC-4100/shift-2/compare"} <= set(memory.lessons)
    assert f"{second.shift_id}/{second.action['receipt']}" in memory.sources


def test_close_is_idempotent():
    memory = ScopedMemory()
    shift = build_shift("D", memory)
    report = run(shift)
    before = dict(memory.sources), dict(memory.lessons), list(shift.memory_trace)
    shift.close(report)
    assert (dict(memory.sources), dict(memory.lessons), shift.memory_trace) == before


def test_close_failure_keeps_the_report_and_unrelated_history():
    memory = ScopedMemory()
    unrelated = Evidence("INC-4100/shift-1/check_link/reference-db/20", "INC-4100", GATEWAY, NOW, "tool",
                         READERS, "reference-db", "unrelated", TEAM)
    memory.record(unrelated)
    shift = build_shift("A", memory)
    report = run(shift)
    assert report["status"] == "recovered" and report["action"] and report["memory_error"]
    assert memory.sources[unrelated.id] == unrelated
    assert len(shift.deps.sim.executor.effects()) == 1


def test_dispatch_uses_fresh_traced_reads_after_the_grant():
    shift = build_shift("A", ScopedMemory())
    assert run(shift)["status"] == "recovered"
    grant = next(call for call in shift.tools.trace if call.tool == "request_approval")
    dispatch = next(call for call in shift.tools.trace if call.tool == "restart_instance")
    between = [call for call in shift.tools.trace if grant.step < call.step < dispatch.step]
    assert [call.tool for call in between] == ["read_metrics", "check_link", "check_link"]
    record = shift.access.decisions[-1]
    assert record["decision"] == "dispatch" and record["dispatch_tick"] == dispatch.tick
    assert record["evidence"]["sources"] == [f"metrics/{GATEWAY}/{between[0].tick}",
                                             f"check_link/reference-db/{between[1].tick}",
                                             f"check_link/matching-engine/{between[2].tick}"]
    assert record["evidence"]["hot_running"] == ["order-gateway-2"]
    assert dispatch.tick < grant.tick + scoped_access.GRANT_TICKS


def test_changed_link_after_grant_blocks_dispatch():
    shift = build_shift("L", ScopedMemory())
    assert run(shift)["status"] == "needs_operator"
    record = shift.access.decisions[-1]
    assert (record["decision"], record["reason"]) == ("refresh_evidence", "dependency_link_not_up")
    assert record["evidence"]["links"]["reference-db"] == "degraded"
    assert not shift.deps.sim.executor.effects()


def test_dispatch_follows_the_tool_result_not_world_state():
    shift = build_shift("A", ScopedMemory())
    check_link = shift.tools.check_link

    def reported_degraded(source, target):
        result = check_link(source, target)
        if shift.access.grants and target == "reference-db":
            return {**result, "state": "degraded"}
        return result

    shift.tools.check_link = reported_degraded
    run(shift)
    assert shift.deps.sim.state.link(GATEWAY, "reference-db").state == "up"
    assert shift.access.decisions[-1]["reason"] == "dependency_link_not_up"
    assert not shift.deps.sim.executor.effects()


def interrupt_reads(shift, action):
    read_metrics = shift.tools.read_metrics

    def interrupted(*args, **kwargs):
        result = read_metrics(*args, **kwargs)
        if shift.access.grants:
            action()
        return result

    shift.tools.read_metrics = interrupted


def test_rights_revoked_during_dispatch_reads():
    shift = build_shift("A", ScopedMemory())
    interrupt_reads(shift, lambda: setattr(shift.access, "credential", replace(CREDENTIAL, rights=frozenset({READ}))))
    run(shift)
    record = shift.access.decisions[-1]
    assert (record["decision"], record["reason"]) == ("permission_denied", "rights_changed_during_reads")
    assert record["evidence"]["sources"] and not shift.deps.sim.executor.effects()


def test_grant_expiring_while_reading_blocks_dispatch():
    shift = build_shift("A", ScopedMemory())
    request = shift.tools.request_approval

    def short_grant(*args, **kwargs):
        approval = request(*args, **kwargs)
        shift.deps.sim.approvals[-1]["expires_tick"] = approval["tick"] + 2  # valid at the gate, not after reads
        return approval

    shift.tools.request_approval = short_grant
    run(shift)
    record = shift.access.decisions[-1]
    assert record["tick"] < shift.deps.sim.approvals[-1]["expires_tick"] <= record["dispatch_tick"]
    assert (record["decision"], record["reason"]) == ("approval_required", "grant_expired_during_reads")
    assert not shift.deps.sim.executor.effects()


def test_grant_is_single_use_without_expiry_or_cooling(monkeypatch):
    monkeypatch.setattr(scoped_access, "GRANT_TICKS", 100)
    shift = build_shift("A", ScopedMemory())
    monkeypatch.setattr(shift.deps.sim.executor, "_restart", lambda instance: None)  # target stays hot
    run(shift)
    first = shift.access.decisions[-1]
    assert first["decision"] == "dispatch"
    key, ref = f"INC-4100:restart:{first['target']}", first["approval"]
    expiry = shift.access.grants[ref][1]
    audit, reads = len(shift.deps.sim.executor.audit), len(shift.tools.trace)
    assert "error" in shift.tools.restart_instance(first["target"], key, ref)
    replay = shift.access.decisions[-1]
    assert (replay["decision"], replay["reason"]) == ("approval_required", "grant_spent")
    assert len(shift.deps.sim.executor.audit) == audit and len(shift.tools.trace) == reads  # no reads, no executor call
    # Controls: the grant had not expired and fresh evidence still supports the same restart.
    assert replay["tick"] < expiry and shift.access.current_approval(shift, first["target"], ref, replay["tick"])
    assert shift.dispatch_evidence(first["target"])["problem"] is None


def test_unsupported_actions_never_dispatch():
    shift = build_shift("A", ScopedMemory())
    run(shift)
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

    assert run(shift, decide)["status"] == "denied"
    assert marker not in repr(shift.tools.trace)
    assert not shift.deps.sim.approvals


@pytest.mark.parametrize("change,reason", [("grant", "no_grant"), ("target", "grant_mismatch"),
                                          ("expiry", "grant_expired")])
def test_dispatch_checks_exact_grant(change, reason):
    shift = build_shift("A", ScopedMemory())
    request = shift.tools.request_approval

    def interrupt(*args, **kwargs):
        approval = request(*args, **kwargs)
        if change == "grant":
            shift.access.grants.clear()
        elif change == "expiry":
            shift.deps.sim.approvals[-1]["expires_tick"] = shift.deps.sim.state.tick
        else:
            binding, expiry = shift.access.grants[approval["approval_ref"]]
            shift.access.grants[approval["approval_ref"]] = (binding[:-2] + ("order-gateway-1", binding[-1]), expiry)
        return approval

    shift.tools.request_approval = interrupt
    assert run(shift)["status"] == "needs_operator"
    assert (shift.access.decisions[-1]["decision"], shift.access.decisions[-1]["reason"]) == ("approval_required", reason)
    assert "evidence" not in shift.access.decisions[-1]
    assert not shift.deps.sim.executor.effects()
