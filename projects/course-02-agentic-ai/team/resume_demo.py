"""#19 worker replacement runs for `m3_demo.py --part resume`. Offline, scripted, no model."""

import tempfile
from dataclasses import replace
from pathlib import Path

from handoff import SHIFT_CALLS, Budget
from m3_demo import CASES, access, effects, reads
from m2_demo import CREDENTIAL, IDENTITY, READERS
from meridian.tools import MeridianTools
from resume import CheckpointStore, DurableLead, ExecutorLedger, ReplacementLead, WorkerStopped
from scoped_memory import ScopedMemory
from workbench import start_exchange


def stopped_record(worker, stop, sim, ledger, store):
    record = store.load()
    return {"worker": worker.worker, "point": stop.point, "tick": sim.state.tick,
            "checkpoint_state": record["state"] if record else None,
            "checkpoint_has_receipt": bool(record and record["receipt"]),
            "effects_at_stop": effects(sim),
            "ledger": {key: {k: v for k, v in entry.items() if k != "receipt"} for key, entry in ledger.entries.items()},
            "checkpoints_saved": worker.checkpoints, "reads": reads(worker)}


async def interrupted(case, folder, stop_at, *, hold=0, refuse=0):
    """Run the integrated lead until it stops at `stop_at`; return what survives: the simulator, the ledger and
    the checkpoint file. The stopped worker object is dropped by the caller."""
    sim = start_exchange(CASES[case])
    ledger = ExecutorLedger(sim, f"{sim.scenario.scenario_id}/ledger-1")
    ledger.hold, ledger.refuse = hold, refuse
    store = CheckpointStore(Path(folder) / "checkpoint.json")
    memory = ScopedMemory()
    worker = DurableLead(sim, dict(IDENTITY), access(), memory, READERS, Budget(SHIFT_CALLS), store, "worker-1", stop_at)
    try:
        await worker.run()
    except WorkerStopped as stop:
        return sim, ledger, store, memory, stopped_record(worker, stop, sim, ledger, store)
    raise RuntimeError("the worker did not reach its stop point")


async def replacement(sim, store, memory, credential=CREDENTIAL):
    worker = ReplacementLead(sim, dict(IDENTITY), access(credential), memory, READERS, store, "worker-2")
    report = await worker.run()
    return worker, report


def resume_record(run, case, stopped, worker, report, sim, checks, **extra):
    return {"part": "resume", "run": run, "case": case, "stopped": stopped,
            "replacement": {"worker": worker.worker, "status": report["status"], "action": report["action"],
                            "next_step": report["next_step"], "resume": report["resume"],
                            "recovery": report["observations"].get("recovery"),
                            "post_restart": report["observations"].get("post_restart"),
                            "checkpoints_saved": worker.checkpoints, "access": worker.access.decisions,
                            "reads": reads(worker), "budget": report["team"]["budget"]},
            "effects": effects(sim),
            "executor_audit": [{"action_id": row.action_id, "tick": row.tick, "outcome": row.outcome,
                                "target": row.target, "key": row.idempotency_key, "approval": row.confirmation_ref,
                                "effect": row.effect_applied} for row in sim.executor.audit],
            **extra, "checks": checks}


async def resume_runs():
    records = []
    with tempfile.TemporaryDirectory() as folder:
        sim, ledger, store, memory, stopped = await interrupted("A", folder, "after_dispatch_before_receipt")
        original = next(iter(ledger.entries.values()))["receipt"]  # the receipt from the stopped worker's dispatch
        worker, report = await replacement(sim, store, memory)
        saved = store.load()
        records.append(resume_record("applied restart, receipt not saved", "A", stopped, worker, report, sim, {
            "stopped after the effect, before the receipt": stopped["effects_at_stop"] == 1
            and stopped["checkpoint_state"] == "intent_saved" and not stopped["checkpoint_has_receipt"],
            "original receipt reconciled": report["action"]["receipt"] == original["action_id"] == "ACT-001"
            and saved["receipt"]["action_id"] == "ACT-001" and saved["key"] == original["idempotency_key"],
            "no second dispatch": all(row["tool"] != "restart_instance" for row in reads(worker))
            and ledger.entries[saved["key"]]["requests"] == 1,
            "one applied restart": effects(sim) == 1,
            "recovery from fresh readings": report["status"] == "recovered"
            and report["observations"]["recovery"]["samples"][0]["tick"] > original["tick"]}))

    with tempfile.TemporaryDirectory() as folder:
        sim, ledger, store, memory, stopped = await interrupted("A", folder, "after_intent_before_dispatch")
        before = store.load()
        worker, report = await replacement(sim, store, memory)
        saved = store.load()
        records.append(resume_record("intent saved, never dispatched", "A", stopped, worker, report, sim, {
            "authoritative absence": report["resume"]["ledger"]["state"] == "absent"
            and report["resume"]["ledger"]["epoch"] == before["ledger_epoch"],
            "original grant not restored; a new on-call grant": report["resume"]["original_approval"]["restored"] is False
            and saved["approval"] != before["approval"] and saved["key"] == before["key"],
            "need re-read before dispatch": [row["decision"] for row in worker.access.decisions] == ["dispatch"],
            "one dispatch with the original key": [row.idempotency_key for row in sim.executor.audit]
            == [before["key"]] and effects(sim) == 1,
            "recovery from fresh readings": report["status"] == "recovered"}))

    controls = (("request still in flight", {"hold": 1}, "unknown"),
                ("executor rejected the request", {"refuse": 1}, "rejected"))
    for run, faults, outcome in controls:
        with tempfile.TemporaryDirectory() as folder:
            sim, ledger, store, memory, stopped = await interrupted("A", folder, "after_dispatch_before_receipt",
                                                                    **faults)
            worker, report = await replacement(sim, store, memory)
            records.append(resume_record(run, "A", stopped, worker, report, sim, {
                f"outcome {outcome}": report["resume"]["outcome"] == outcome,
                "no second dispatch": all(row["tool"] != "restart_instance" for row in reads(worker))
                and all(entry["requests"] == 1 for entry in ledger.entries.values()),
                "no effect, no recovery claim": effects(sim) == 0 and report["status"] == "needs_operator"}))

    with tempfile.TemporaryDirectory() as folder:
        sim, ledger, store, memory, stopped = await interrupted("A", folder, "after_dispatch_before_receipt")
        record = store.load()
        store.save({**record, "target": "order-gateway-1", "parameters": {"target": "order-gateway-1"}})
        worker, report = await replacement(sim, store, memory)
        records.append(resume_record("checkpoint and ledger disagree on the bound target", "A", stopped, worker,
                                     report, sim, {
                                         "key conflict stops the write": report["resume"]["outcome"] == "conflict",
                                         "no second dispatch, one effect": effects(sim) == 1
                                         and all(row["tool"] != "restart_instance" for row in reads(worker))}))

    with tempfile.TemporaryDirectory() as folder:
        sim, ledger, store, memory, stopped = await interrupted("A", folder, "after_dispatch_before_receipt")
        ledger.available = False
        worker, report = await replacement(sim, store, memory)
        records.append(resume_record("executor ledger unavailable", "A", stopped, worker, report, sim, {
            "outcome unknown": report["resume"]["outcome"] == "unknown",
            "no second dispatch, no recovery claim": effects(sim) == 1 and report["status"] == "needs_operator"
            and all(row["tool"] != "restart_instance" for row in reads(worker))}))

    with tempfile.TemporaryDirectory() as folder:
        sim, ledger, store, memory, stopped = await interrupted("A", folder, "after_dispatch_before_receipt")
        restarted = start_exchange(CASES["A"])  # the whole simulator restarted: executor, world and ledger are new
        ExecutorLedger(restarted, f"{restarted.scenario.scenario_id}/ledger-2")
        worker, report = await replacement(restarted, store, ScopedMemory())
        records.append(resume_record("whole simulator restarted", "A", stopped, worker, report, restarted, {
            "absence not trusted from another ledger": report["resume"]["ledger"]["state"] == "absent"
            and report["resume"]["outcome"] == "unknown",
            "no dispatch in the new simulator": effects(restarted) == 0
            and all(row["tool"] != "restart_instance" for row in reads(worker))},
            original_simulator_effects=effects(sim)))

    with tempfile.TemporaryDirectory() as folder:
        sim, ledger, store, memory, stopped = await interrupted("A", folder, "after_dispatch_before_receipt")
        worker, report = await replacement(sim, store, memory, replace(CREDENTIAL, rights=frozenset()))
        records.append(resume_record("read access revoked before resume", "A", stopped, worker, report, sim, {
            "gap recorded, handed over": report["resume"]["outcome"] == "access_gap"
            and report["status"] == "needs_operator",
            "no read, no recovery inferred": reads(worker) == [] and report["observations"].get("recovery") is None}))

    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / "checkpoint.json").write_text("{\"version\": 1, \"incid")  # a torn, non-atomic write
        sim = start_exchange(CASES["A"])
        ExecutorLedger(sim, "shift-a/ledger-1")
        worker, report = await replacement(sim, CheckpointStore(Path(folder) / "checkpoint.json"), ScopedMemory())
        records.append(resume_record("checkpoint unreadable", "A", None, worker, report, sim, {
            "outcome unknown, nothing read or sent": report["resume"]["outcome"] == "unknown"
            and reads(worker) == [] and effects(sim) == 0}))

    with tempfile.TemporaryDirectory() as folder:
        sim, ledger, store, memory, stopped = await interrupted("N", folder, "after_dispatch_before_receipt")
        worker, report = await replacement(sim, store, memory)
        records.append(resume_record("link degrades after the restart", "N", stopped, worker, report, sim, {
            "receipt reconciled": report["resume"]["outcome"] == "reconciled_receipt",
            "no recovery claimed from the old receipt": report["status"] == "needs_operator"
            and report["observations"].get("recovery") is None and report["observations"].get("post_restart"),
            "one effect": effects(sim) == 1},
            naive_claim="recovered, from the receipt alone"))

    with tempfile.TemporaryDirectory() as folder:
        sim, ledger, store, memory, stopped = await interrupted("A", folder, "after_dispatch_before_receipt")
        record = store.load()
        tools = MeridianTools(sim, actor="agent-first-line")  # a naive replacement: no lookup, a fresh key
        tools.restart_instance(record["target"], record["key"] + ":retry", record["approval"])
        records.append({"part": "resume", "run": "naive replacement re-sends with a new key", "case": "A",
                        "control": "naive", "stopped": stopped, "effects": effects(sim),
                        "executor_audit": [{"action_id": row.action_id, "outcome": row.outcome,
                                            "key": row.idempotency_key, "effect": row.effect_applied}
                                           for row in sim.executor.audit],
                        "checks": {"one applied restart (expected to fail)": effects(sim) == 1}})
    return records
