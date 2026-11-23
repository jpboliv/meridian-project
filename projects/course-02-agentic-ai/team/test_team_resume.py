"""#19 durable resume: atomic checkpoints, the executor ledger, the stop boundary and reconciliation."""

import asyncio
import os
from dataclasses import replace

import pytest

from handoff import SHIFT_CALLS, Budget
from m3_demo import CASES, access, passed
from resume_demo import interrupted, replacement, resume_runs
from m2_demo import APPROVER, IDENTITY, READERS
from resume import (CHECKPOINT_FIELDS, CheckpointStore, CheckpointUnreadable, DurableLead, ExecutorLedger,
                    ReplacementLead, WorkerStopped)
from scoped_access import READ, RESTART
from scoped_memory import ScopedMemory
from workbench import start_exchange


def run(coroutine):
    return asyncio.run(coroutine)


def test_checkpoint_write_is_all_or_nothing(tmp_path, monkeypatch):
    store = CheckpointStore(tmp_path / "checkpoint.json")
    first = dict.fromkeys(CHECKPOINT_FIELDS, None) | {"state": "intent_saved"}
    store.save(first)

    def crash(*args):
        raise OSError("power lost before the rename")

    monkeypatch.setattr(os, "replace", crash)
    with pytest.raises(OSError):
        store.save({**first, "state": "receipt_saved"})
    assert store.load() == first


def test_partial_or_foreign_checkpoint_is_unreadable(tmp_path):
    path = tmp_path / "checkpoint.json"
    path.write_text('{"state": "intent_sa')
    with pytest.raises(CheckpointUnreadable):
        CheckpointStore(path).load()
    path.write_text('{"state": "intent_saved"}')
    with pytest.raises(CheckpointUnreadable):
        CheckpointStore(path).load()
    assert CheckpointStore(tmp_path / "none.json").load() is None


def test_worker_stop_is_not_caught_by_ordinary_handlers():
    assert issubclass(WorkerStopped, BaseException) and not issubclass(WorkerStopped, Exception)


def ledger_for(case="A"):
    sim = start_exchange(CASES[case])
    return sim, ExecutorLedger(sim, "test/ledger-1")


def test_ledger_states_and_bound_keys():
    sim, ledger = ledger_for()
    assert ledger.lookup("k")["state"] == "absent"
    first = sim.executor.execute(RESTART, "order-gateway-2", idempotency_key="k", actor="a", confirmation_ref="r")
    assert ledger.lookup("k")["state"] == "completed" and ledger.lookup("k")["receipt"]["action_id"] == first["action_id"]
    again = sim.executor.execute(RESTART, "order-gateway-2", idempotency_key="k", actor="a", confirmation_ref="r")
    assert again["status"] == "already_applied" and ledger.lookup("k")["receipt"] == first
    other = sim.executor.execute(RESTART, "order-gateway-1", idempotency_key="k", actor="a", confirmation_ref="r")
    assert other["status"] == "conflict" and len(sim.executor.effects()) == 1
    ledger.hold = 1
    with pytest.raises(Exception):
        sim.executor.execute(RESTART, "order-gateway-1", idempotency_key="held", actor="a", confirmation_ref="r")
    assert ledger.lookup("held")["state"] == "in_flight" and len(sim.executor.effects()) == 1
    ledger.refuse = 1
    refused = sim.executor.execute(RESTART, "order-gateway-1", idempotency_key="no", actor="a", confirmation_ref="r")
    assert refused["status"] == "rejected" and ledger.lookup("no")["state"] == "rejected"


def test_intent_is_durable_before_the_executor_can_act(tmp_path):
    sim, ledger, store, memory, stopped = run(interrupted("A", tmp_path, "after_intent_before_dispatch"))
    record = store.load()
    assert record["state"] == "intent_saved" and ledger.entries == {} and sim.executor.audit == []
    assert {key: record[key] for key in ("incident", "step", "target", "action", "parameters", "key", "approval")} == {
        "incident": "INC-4100", "step": "restart_dispatch", "target": "order-gateway-2", "action": RESTART,
        "parameters": {"target": "order-gateway-2"}, "key": "INC-4100:restart:order-gateway-2",
        "approval": "APR-001"}
    assert record["caller"] == {"requester": "requester-1", "credential": "gateway-tool-1", "approver": APPROVER.id}
    assert record["evidence"] == ["metrics/order-gateway/24", "check_link/reference-db/25",
                                  "check_link/matching-engine/26"]
    assert record["remaining_budget"] == SHIFT_CALLS - 12
    assert record["ledger_id"] == ledger.instance_id and record["ledger_label"] == ledger.label


def test_stopped_worker_leaves_no_receipt_and_the_replacement_starts_cold(tmp_path):
    sim, ledger, store, memory, stopped = run(interrupted("A", tmp_path, "after_dispatch_before_receipt"))
    assert stopped["effects_at_stop"] == 1 and store.load()["receipt"] is None
    worker, report = run(replacement(sim, store, memory))
    assert worker.tools.trace[0].tool == "executor.lookup"  # its own trace, no inherited observations
    assert report["action"]["receipt"] == "ACT-001" and report["action"]["reconciled_by"] == "worker-2"
    assert store.load()["receipt"]["action_id"] == "ACT-001" and len(sim.executor.effects()) == 1
    assert report["team"]["budget"]["limit"] == SHIFT_CALLS - 12 - 1  # remaining at intent, dispatch reserved


def test_same_label_empty_ledger_cannot_authorize_resend(tmp_path):
    sim, original, store, _, stopped = run(interrupted("A", tmp_path, "after_dispatch_before_receipt"))
    intent = store.load()
    assert stopped["effects_at_stop"] == 1 and intent["receipt"] is None
    restarted = start_exchange(CASES["A"])
    fresh = ExecutorLedger(restarted, original.label)
    assert fresh.lookup(intent["key"])["state"] == "absent"
    worker, report = run(replacement(restarted, store, ScopedMemory()))
    assert report["resume"]["outcome"] == "unknown"
    assert [call.tool for call in worker.tools.trace] == ["executor.lookup"]
    assert restarted.executor.audit == [] and len(sim.executor.effects()) == 1 and store.load() == intent


def test_replacement_never_sends_another_key_or_target(tmp_path):
    sim, ledger, store, memory, stopped = run(interrupted("A", tmp_path, "after_intent_before_dispatch"))
    worker = ReplacementLead(sim, dict(IDENTITY), access(), memory, READERS, store, "worker-2")
    worker.resume_record = store.load()
    assert worker.tools.restart_instance("order-gateway-1", "INC-4100:restart:order-gateway-1", "APR-001") == {
        "error": "Not the recorded intent"}
    assert worker.tools.restart_instance("order-gateway-2", "new-key", "APR-001") == {"error": "Not the recorded intent"}
    report = worker.restart("order-gateway-1")
    assert "different target requires a new decision" in report["next_step"] and sim.executor.audit == []


def test_absent_intent_needs_current_restart_rights(tmp_path):
    sim, ledger, store, memory, stopped = run(interrupted("A", tmp_path, "after_intent_before_dispatch"))
    no_restart = replace(access().credential, rights=frozenset({READ}))
    worker, report = run(replacement(sim, store, memory, no_restart))
    assert report["resume"]["outcome"] == "reassessed_after_absence"
    assert sim.executor.audit == [] and report["status"] in ("denied", "needs_operator")


def test_absent_intent_needs_a_current_on_call_grant(tmp_path):
    sim, ledger, store, memory, stopped = run(interrupted("A", tmp_path, "after_intent_before_dispatch"))
    sim.scenario.approver = {"mode": "deny_all"}  # the on-call now declines
    worker, report = run(replacement(sim, store, memory))
    assert report["status"] == "denied" and sim.executor.audit == []


def test_replacement_budget_bounds_the_reassessment(tmp_path):
    sim, ledger, store, memory, stopped = run(interrupted("A", tmp_path, "after_intent_before_dispatch"))
    store.save({**store.load(), "remaining_budget": 6})
    worker, report = run(replacement(sim, store, memory))
    assert report["team"]["budget"]["used"] == 5 and sim.executor.audit == []
    assert "budget spent" in report["next_step"]


def test_unknown_stop_point_is_rejected(tmp_path):
    sim = start_exchange(CASES["A"])
    with pytest.raises(ValueError):
        DurableLead(sim, dict(IDENTITY), access(), ScopedMemory(), READERS, Budget(1), CheckpointStore(tmp_path / "c"),
                    "w", "somewhere")


def test_public_resume_records_pass_their_checks():
    records = run(resume_runs())
    assert [record["run"] for record in records if not passed(record)] == []
    naive = [record for record in records if record.get("control") == "naive"]
    assert naive and all(not all(record["checks"].values()) for record in naive)
