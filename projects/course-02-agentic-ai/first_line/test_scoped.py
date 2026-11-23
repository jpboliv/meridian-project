import asyncio
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

import scoped_access
from m2_demo import (CREDENTIAL, OPERATOR, OUTSIDER, READERS, REQUESTER, TEAM, build_shift,
                     critical_request, investigate, run_sequence, save_claims)
from scoped_access import READ
from scoped_memory import Claim, Evidence, Lesson, ScopedMemory
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


def test_one_read_withdraws_the_temporal_claim_and_only_flags_the_causal_one():
    rows = by_case()
    first, second = rows["restart after the link cleared"], rows["next shift checks both claims"]
    assert first["effects"] == 1 and second["effects"] == 0 and "restart" not in second["steps"]
    checks = {row["meaning"]: row for row in second["memory"] if "checked_claim" in row}
    decisions = [row for row in second["memory"] if "shown" in row]
    assert checks["first_fall_after_restart"]["assessment"] == "contradiction"
    assert checks["restart_fixed_delay"]["assessment"] == "possible_conflict"
    assert all(row["tick"] < decisions[0]["tick"] for row in checks.values()) and second["reads"][0] == "read_metrics"
    temporal, causal = second["claims"]["first_fall_after_restart"], second["claims"]["restart_fixed_delay"]
    assert all(row["corrections"] == [checks["first_fall_after_restart"]["checked_claim"]]
               and row["disputed"] == [checks["restart_fixed_delay"]["checked_claim"]] for row in decisions)
    assert temporal["withdrawn"] and not temporal["flagged"] and temporal["flag"] is None
    assert causal["flagged"] and not causal["withdrawn"] and causal["correction"] is None
    assert temporal["lookup"] is causal["lookup"] is None  # neither is relied on for a decision
    # Both views cite the same observed readings: the fall before the 10:16 restart and the one after it.
    for view in (temporal["correction"], causal["flag"]):
        readings = {row["time"][11:16]: row["latency_ms"] for row in view["readings"]}
        assert readings["10:06"] == 365 and readings["10:07"] == 181
        assert readings["10:16"] == 190 and readings["10:17"] == 6.5
        assert view["restart"]["time"].endswith("10:16:00") and view["restart"]["target"] == "order-gateway-2"
        assert "from 365 ms at 10:06 to 181 ms at 10:07" in view["conclusion"]
        assert "from 190 ms at 10:16 to 6.5 ms at 10:17" in view["conclusion"]
    assert "neither establish nor rule out" in causal["flag"]["conclusion"]
    assert "stays withdrawn" in temporal["correction"]["conclusion"]


def test_deletion_keeps_readings_status_and_uncertainty():
    deleted = by_case()["restart receipt deleted"]
    temporal, causal = deleted["claims"]["first_fall_after_restart"], deleted["claims"]["restart_fixed_delay"]
    assert temporal["withdrawn"] and causal["flagged"] and temporal["lookup"] is causal["lookup"] is None
    for view in (temporal["correction"], causal["flag"]):
        assert view["restart"] is None and len(view["readings"]) == 5
        assert "order of events is not established" in view["conclusion"]
        assert "from 365 ms at 10:06 to 181 ms at 10:07" in view["conclusion"]
    assert temporal["other_team"] == causal["other_team"] == [None, None]
    assert deleted["other_team_lessons"] == []


def test_first_context_carries_the_correction_and_the_flag():
    memory = ScopedMemory()
    first = build_shift("R", memory)
    run(first)
    claims = save_claims(first, memory)
    contexts = []

    async def decide(context):
        contexts.append(context)
        return await investigate(context)

    run(build_shift("R", memory, sim=first.deps.sim), decide)
    assert [row["claim"] for row in contexts[0]["corrections"]] == [claims["first_fall_after_restart"]]
    assert [row["claim"] for row in contexts[0]["disputed"]] == [claims["restart_fixed_delay"]]
    assert contexts[0]["disputed"][0]["claim_text"] == "Restarting order-gateway-2 fixed the delay."
    assert all(item["id"] not in claims.values() for context in contexts for item in context["handover"])


REFERENCE = datetime(2026, 11, 3, 10, 0)


def reference_memory(meaning, target=GATEWAY, incident="INC-4000"):
    """The agreed reference documents: latency 880, 880, 740, 620 ms from 10:00, and a restart at 10:05."""
    memory = ScopedMemory()
    report = REFERENCE.replace(minute=6)
    memory.record(Evidence("report", "INC-4000", GATEWAY, report, "reported", READERS, "claimed_cause", target, TEAM))
    memory.save(REQUESTER, Lesson("old", TEAM, REQUESTER.id, GATEWAY, "hot_instance", "Restart claim.", ("report",),
                                  report, claim=Claim(meaning, "INC-4000", target, REFERENCE)))
    for minute, value in enumerate((880, 880, 740, 620)):
        memory.record(Evidence(f"latency-{minute}", incident, GATEWAY, REFERENCE.replace(minute=minute), "document",
                               READERS, "latency_ms", value, TEAM))
    memory.record(Evidence("actions", incident, GATEWAY, REFERENCE.replace(minute=5), "document", READERS,
                           "restart", GATEWAY, TEAM))
    return memory


LATENCY = tuple(f"latency-{minute}" for minute in range(4))


def test_reference_documents_contradict_only_the_temporal_claim():
    """Library-level check on the agreed reference values: latency fell at 10:02, the restart was at 10:05."""
    memory = reference_memory("first_fall_after_restart")
    assert memory.assess_restart_claim(REQUESTER, "old", LATENCY, REFERENCE) == "possible_conflict"  # order unknown
    assert memory.assess_restart_claim(REQUESTER, "old", LATENCY + ("actions",), REFERENCE) == "contradiction"
    correction = memory.correction(REQUESTER, "old")
    assert "from 880 ms at 10:01 to 740 ms at 10:02" in correction["conclusion"]
    assert memory.lookup(REQUESTER, "old", REFERENCE, {"hot_instance": 1}) is None

    memory = reference_memory("restart_fixed_delay")
    assert memory.assess_restart_claim(REQUESTER, "old", LATENCY, REFERENCE) == "unsupported"
    assert memory.assess_restart_claim(REQUESTER, "old", LATENCY + ("actions",), REFERENCE) == "possible_conflict"
    assert "old" not in memory.withdrawn and memory.correction(REQUESTER, "old") is None
    assert "neither establish nor rule out" in memory.flag(REQUESTER, "old")["conclusion"]


@pytest.mark.parametrize("change", ["other_target", "other_incident", "before_report", "falls_after_restart",
                                    "two_restarts"])
def test_temporal_claim_needs_a_matching_incident_target_and_time(change):
    memory = reference_memory("first_fall_after_restart", target="order-gateway-2" if change == "other_target"
                              else GATEWAY, incident="INC-4001" if change == "other_incident" else "INC-4000")
    refs = LATENCY + ("actions",)
    if change == "before_report":  # the only fall predates the reported delay
        memory.lessons["old"] = replace(memory.lessons["old"], claim=replace(memory.lessons["old"].claim,
                                                                             since=REFERENCE.replace(minute=3)))
    if change == "falls_after_restart":
        memory.record(Evidence("actions-early", "INC-4000", GATEWAY, REFERENCE.replace(minute=1), "document",
                               READERS, "restart", GATEWAY, TEAM))
        memory.delete(OPERATOR, "actions", REFERENCE)
        refs = LATENCY + ("actions-early",)
    if change == "two_restarts":
        memory.record(Evidence("actions-again", "INC-4000", GATEWAY, REFERENCE.replace(minute=8), "document",
                               READERS, "restart", GATEWAY, TEAM))
        refs += ("actions-again",)
    result = memory.assess_restart_claim(REQUESTER, "old", refs, REFERENCE)
    assert "old" not in memory.withdrawn
    expected = {"other_target": "possible_conflict", "other_incident": "unsupported", "before_report": "unsupported",
                "falls_after_restart": "unsupported", "two_restarts": "possible_conflict"}
    assert result == expected[change]


def test_a_fall_only_after_the_restart_changes_neither_claim():
    for meaning in ("first_fall_after_restart", "restart_fixed_delay"):
        memory = reference_memory(meaning)
        memory.record(Evidence("actions-early", "INC-4000", GATEWAY, REFERENCE.replace(minute=1), "document",
                               READERS, "restart", GATEWAY, TEAM))
        memory.delete(OPERATOR, "actions", REFERENCE)
        assert memory.assess_restart_claim(REQUESTER, "old", LATENCY + ("actions-early",), REFERENCE) == "unsupported"
        assert "old" not in memory.withdrawn and "old" not in memory.conflicts


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
    unrelated = Evidence("INC-4100/shift-1/check_link/reference-db/24", "INC-4100", GATEWAY, NOW, "tool",
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


def cited(memory):
    return {ref for lesson in memory.lessons.values() for ref in lesson.sources}


def test_changed_link_after_grant_blocks_dispatch_and_reaches_the_next_handover():
    rows = by_case()
    refused, later = rows["link degraded after grant"], rows["next shift after the refused dispatch"]
    record = refused["access"][-1]
    assert (record["decision"], record["reason"]) == ("refresh_evidence", "dependency_link_not_up")
    assert record["evidence"]["links"]["reference-db"] == "degraded"
    assert refused["effects"] == later["effects"] == 0
    assert refused["follow_up"] == {"operation": "investigate_link", "source": GATEWAY, "target": "reference-db",
                                    "observed_tick": 24}
    assert "degraded link" in refused["next_step"] and "tick 24" in refused["next_step"]
    saved = {row["saved"]: row for row in refused["memory"] if "saved" in row}
    assert saved["INC-4500/shift-1/open-link"]["sources"] == ["INC-4500/shift-1/check_link/reference-db/24"]
    prefix = "INC-4500/shift-1/"
    assert saved[prefix + "compare"]["sources"] == [  # newest dispatch reads only, each once
        prefix + "read_metrics/order-gateway-1/23", prefix + "read_metrics/order-gateway-2/23",
        prefix + "check_link/reference-db/24", prefix + "check_link/matching-engine/25"]
    assert "links reference-db degraded, matching-engine up" in saved[prefix + "compare"]["text"]
    assert all("reference-db up" not in row["text"] for row in saved.values())
    received = later["handover_received"]
    assert set(received) == set(saved) and all(ref.startswith("INC-4500/shift-1/") for row in received.values()
                                               for ref in row["sources"])
    assert all("reference-db up" not in row["text"] for row in received.values())
    assert later["steps"][0] == "links" and later["follow_up"]["target"] == "reference-db"


def broken_after_grant(shift, tool, broken):
    original = getattr(shift.tools, tool)

    def call(*args, **kwargs):
        if shift.access.grants:
            return broken(*args, **kwargs)
        return original(*args, **kwargs)

    setattr(shift.tools, tool, call)


def test_failed_dispatch_link_read_leaves_the_link_unknown():
    memory = ScopedMemory()
    shift = build_shift("A", memory)
    check_link = shift.tools.check_link
    broken_after_grant(shift, "check_link", lambda source, target: {"error": "timeout"} if target == "reference-db"
                       else check_link(source, target))
    report = run(shift)
    assert shift.access.decisions[-1]["reason"] == "dependency_link_not_up" and not shift.deps.sim.executor.effects()
    assert "reference-db" not in report["observations"]["links"]
    assert report["next_step"].startswith("Missing link state for reference-db.")
    assert not memory.lessons  # no clue or note from the healthy link read before the grant
    assert not any("/check_link/reference-db/" in ref for ref in memory.sources)


def test_failed_dispatch_metrics_read_saves_no_clue():
    memory = ScopedMemory()
    shift = build_shift("A", memory)
    broken_after_grant(shift, "read_metrics", lambda *args, **kwargs: {"error": "timeout"})
    report = run(shift)
    assert shift.access.decisions[-1]["reason"] == "no_instance_reading" and not shift.deps.sim.executor.effects()
    assert report["next_step"].startswith("read_metrics returned no current per-instance reading.")
    assert not memory.lessons


def test_failed_dispatch_metrics_and_one_faulty_link_are_reported_together():
    """#15 follow-up: the handover names the degraded link and the missing replica evidence, and the earlier
    samples are no longer labelled current."""
    memory = ScopedMemory()
    shift = build_shift("A", memory)
    check_link = shift.tools.check_link
    broken_after_grant(shift, "read_metrics", lambda *args, **kwargs: {"error": "timeout"})
    broken_after_grant(shift, "check_link", lambda source, target: {**check_link(source, target), "state": "degraded"}
                       if target == "reference-db" else check_link(source, target))
    report = run(shift)
    record = shift.access.decisions[-1]
    assert record["reason"] == "no_instance_reading" and not shift.deps.sim.executor.effects()
    assert record["evidence"]["links"] == {"reference-db": "degraded", "matching-engine": "up"}
    tick = report["observations"]["links"]["reference-db"]["tick"]
    grant = next(call for call in shift.tools.trace if call.tool == "request_approval")
    assert report["follow_up"] == {"operation": "investigate_link", "source": GATEWAY, "target": "reference-db",
                                   "observed_tick": tick} and tick > grant.tick  # the dispatch-time read
    step = report["next_step"]
    assert step.startswith("read_metrics returned no current per-instance reading.")
    assert "predate that read and do not establish current health" in step
    assert f"Investigate the degraded link from {GATEWAY} to reference-db. Source: check_link at tick {tick}." in step
    samples = report["observations"]["instances"]
    assert samples and {row["freshness"] for row in samples.values()} == {"superseded"}
    assert not any(key.endswith("/compare") for key in memory.lessons)  # no clue without current readings
    note, = memory.lessons.values()
    assert note.kind == "note" and note.sources == (f"{shift.shift_id}/check_link/reference-db/{tick}",)


def test_personal_identifiers_in_ticket_text_never_reach_context_trace_memory_or_report():
    memory = ScopedMemory()
    shift = build_shift("A", memory)
    markers = ("jane.doe@example.invalid", "+351 900 000 001")
    shift.deps.sim.tickets.get("MRX-4100").summary = f"INC-4100: slow acks, call {markers[0]} or {markers[1]}"
    seen = []

    async def decide(context):
        seen.append(repr(context))
        return await investigate(context)

    report = run(shift, decide)
    assert report["status"] == "recovered" and seen
    for text in (*seen, repr(shift.tools.trace), repr(memory.sources), repr(memory.lessons), repr(report)):
        assert not any(marker in text for marker in markers)


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
