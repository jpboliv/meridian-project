"""M3 durable resume (#19) on the integrated lead path. Offline and scripted: no model is called.

Before the executor can act, the lead saves its restart intent as one complete checkpoint file: incident, step,
caller, target, action, parameters, the stable key, the approval reference, the dispatch evidence and the
remaining budget. The executor ledger lives beside the supplied executor in the surviving simulation process and
enters every keyed request as in flight before the executor runs it. A worker is stopped by `WorkerStopped`
at a named point and discarded. A replacement worker gets only the checkpoint path, the surviving simulator and
ledger, and current access. It reconciles the original key against the ledger and never invents a new key.
"""

import json
import os
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from meridian.actions import ActionTimeout
from meridian.tools import MeridianTools
from handoff import Budget, TeamLead, TeamTools
from scoped_access import GRANT_TICKS, READ, RESTART
from shift import GATEWAY, GatewayHealth

DISPATCH_RESERVED = 1  # the dispatch call is charged to the budget whether or not it was sent
STOP_POINTS = ("after_intent_before_dispatch", "after_dispatch_before_receipt")
CHECKPOINT_FIELDS = ("version", "incident", "shift", "step", "worker", "caller", "target", "action", "parameters",
                     "key", "approval", "evidence", "remaining_budget", "ledger_id", "ledger_label", "state", "receipt",
                     "saved_tick")


class WorkerStopped(BaseException):
    """The worker process stops here. Nothing after this point runs; no handler in the worker catches it."""

    def __init__(self, point):
        super().__init__(point)
        self.point = point


class CheckpointUnreadable(Exception):
    pass


class CheckpointStore:
    """One JSON file, replaced as a whole. A write goes to a temporary file in the same directory, is flushed to
    disk, then atomically renamed over the old one, so a reader sees the previous or the new version, never part."""

    def __init__(self, path):
        self.path = Path(path)

    def save(self, record):
        data = json.dumps(record, sort_keys=True).encode()
        temporary = self.path.with_name(self.path.name + ".tmp")
        with open(temporary, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
        directory = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def load(self):
        try:
            record = json.loads(self.path.read_bytes())
        except FileNotFoundError:
            return None
        except ValueError as error:
            raise CheckpointUnreadable(str(error)) from None
        if not isinstance(record, dict) or set(record) != set(CHECKPOINT_FIELDS):
            raise CheckpointUnreadable("unexpected checkpoint fields")
        return record


class ExecutorLedger:
    """The authoritative record of executor requests, kept in the surviving simulation process.

    Every keyed request is entered as `in_flight` before the supplied executor runs it, bound to its action and
    parameters, and then marked `completed`, `rejected` or `conflict`. `lookup` returns `absent` only when this
    ledger never received the key, which also means nothing with that key is in flight. `hold` and `refuse` are
    control faults: leave the next request in flight, or have the executor refuse it."""

    def __init__(self, sim, label):
        self.executor = sim.executor
        self.sim = sim
        self.label = label
        self.instance_id = uuid4().hex
        self.entries = {}
        self.available = True
        self.hold = 0
        self.refuse = 0
        sim.executor = self  # every tool call to the executor now passes through the ledger

    def __getattr__(self, name):
        return getattr(self.__dict__["executor"], name)

    def execute(self, action, target, *, idempotency_key=None, actor="agent", confirmation_ref=None):
        if idempotency_key is None:
            return self.executor.execute(action, target, actor=actor, confirmation_ref=confirmation_ref)
        binding = {"action": action, "parameters": {"target": target}}
        entry = self.entries.get(idempotency_key)
        if entry is not None and entry["binding"] != binding:
            return {"action": action, "target": target, "idempotency_key": idempotency_key, "status": "conflict",
                    "detail": "Key already bound to another action or target. No effect."}
        if entry is None:
            entry = self.entries[idempotency_key] = {"binding": binding, "state": "in_flight", "receipt": None,
                                                     "received_tick": self.sim.state.tick, "requests": 0}
        entry["requests"] += 1
        if self.hold:
            self.hold -= 1
            raise ActionTimeout(f"No response from the executor for {action} {target} (timeout). "
                                f"The action may or may not have been applied.")
        if self.refuse:
            self.refuse -= 1
            record = self.executor._record(action, target, "rejected", "Executor refused the request.", False,
                                           idempotency_key, actor, confirmation_ref)
            entry["state"] = "rejected"
            return {**record.public(), "status": "rejected"}
        try:
            result = self.executor.execute(action, target, idempotency_key=idempotency_key, actor=actor,
                                           confirmation_ref=confirmation_ref)
        except ActionTimeout:
            status = self.executor.status(idempotency_key)
            if status["status"] == "completed":
                entry.update(state="completed", receipt=status)
            raise
        if result["status"] == "completed":
            entry.update(state="completed", receipt=result)
        elif result["status"] in ("rejected", "conflict"):
            entry["state"] = result["status"]
        return result  # `already_applied` keeps the original receipt

    def lookup(self, key):
        entry = self.entries.get(key)
        if entry is None:
            return {"idempotency_key": key, "state": "absent"}
        return {"idempotency_key": key, "state": entry["state"], "binding": entry["binding"],
                "received_tick": entry["received_tick"], "requests": entry["requests"], "receipt": entry["receipt"]}


class DurableTools(TeamTools):
    def restart_instance(self, instance_id, idempotency_key=None, confirmation_ref=None):
        """The M2 effect boundary, with the intent saved before the executor can act and the receipt after it."""
        shift = self.shift
        recorded = shift.resume_record
        if recorded and (instance_id, idempotency_key) != (recorded["target"], recorded["key"]):
            # A different target needs a new decision; never a new key for the recorded intent.
            return {"error": "Not the recorded intent"}
        if shift.access.check_dispatch(shift, instance_id, idempotency_key, confirmation_ref) != "dispatch":
            return {"error": "M2 dispatch denied"}
        shift.save_intent(instance_id, idempotency_key, confirmation_ref)
        shift.stop_if("after_intent_before_dispatch")
        result = MeridianTools.restart_instance(self, instance_id, idempotency_key, confirmation_ref)
        shift.stop_if("after_dispatch_before_receipt")
        shift.save_outcome(result)
        return result

    def ledger_lookup(self, key, expected_id):
        def lookup():
            ledger = self.sim.executor
            if not isinstance(ledger, ExecutorLedger) or not ledger.available:
                return {"error": "executor ledger unavailable"}
            same_instance = ledger.instance_id == expected_id
            source = {"label": ledger.label, "same_instance": same_instance}
            return {**source, **ledger.lookup(key)} if same_instance else source

        return self._run("executor.lookup", {"idempotency_key": key}, lookup)


class DurableLead(TeamLead):
    """The integrated #18 lead whose restart intent and receipt are checkpointed."""

    TOOLS = DurableTools

    def __init__(self, sim, identity, access, memory, readers, budget, store, worker, stop_at=None, faults=None):
        if stop_at not in (None, *STOP_POINTS):
            raise ValueError(f"unknown stop point {stop_at!r}")
        super().__init__(sim, identity, access, memory, readers, budget, faults)
        self.store, self.worker, self.stop_at = store, worker, stop_at
        self.resume_record = None
        self.checkpoints = []  # (tick, state) of every checkpoint this worker saved

    def stop_if(self, point):
        if point == self.stop_at:
            raise WorkerStopped(point)

    def save(self, record):
        self.store.save(record)
        self.checkpoints.append({"tick": self.deps.sim.state.tick, "state": record["state"],
                                 "approval": record["approval"]})

    def save_intent(self, target, key, ref):
        decision = self.access.decisions[-1]
        self.save({
            "version": 2, "incident": self.brief["incident_id"], "shift": self.shift_id, "step": "restart_dispatch",
            "worker": self.worker,
            "caller": {"requester": self.access.requester.id, "credential": self.access.credential.id,
                       "approver": self.access.approver.id},
            "target": target, "action": RESTART, "parameters": {"target": target}, "key": key, "approval": ref,
            "evidence": decision["evidence"]["sources"], "remaining_budget": self.budget.remaining(),
            "ledger_id": self.deps.sim.executor.instance_id, "ledger_label": self.deps.sim.executor.label,
            "state": "intent_saved", "receipt": None,
            "saved_tick": self.deps.sim.state.tick})

    def save_outcome(self, result):
        record = self.store.load()
        if (result.get("status"), result.get("action"), result.get("target"), result.get("idempotency_key")) == (
                "completed", RESTART, record["target"], record["key"]):
            self.save_receipt(record, result)
        else:
            self.save({**record, "state": "dispatch_unconfirmed", "worker": self.worker,
                       "saved_tick": self.deps.sim.state.tick})

    def save_receipt(self, record, receipt):
        self.save({**record, "version": 3, "remaining_budget": self.budget.remaining(),
                   "state": "receipt_saved", "worker": self.worker, "saved_tick": self.deps.sim.state.tick,
                   "receipt": {key: receipt[key] for key in ("action_id", "tick", "time", "action", "target",
                                                             "idempotency_key", "confirmation_ref", "outcome")}})


def binding(record):
    return {"action": record["action"], "parameters": record["parameters"]}


class ReplacementLead(DurableLead):
    """A new worker for the same incident. It starts from the checkpoint file, the surviving simulator and ledger,
    and current access. Nothing from the stopped worker's memory is used."""

    def __init__(self, sim, identity, access, memory, readers, store, worker, faults=None):
        super().__init__(sim, identity, access, memory, readers, Budget(0), store, worker, None, faults)
        self.reconciliation = {"worker": worker}

    def unknown(self, why):
        self.reconciliation["outcome"] = "unknown"
        return self.handover(f"{why} The restart outcome is unknown. No second dispatch: read the executor's "
                             f"action record before any action.")

    async def resume(self):
        notes = self.reconciliation
        try:
            record = self.store.load()
        except CheckpointUnreadable:
            record = None
        if record is None:
            notes["checkpoint"] = "missing or unreadable"
            return self.unknown("No readable checkpoint.")
        notes["checkpoint"] = {key: record[key] for key in ("state", "worker", "target", "key", "approval",
                                                            "remaining_budget", "ledger_label", "saved_tick")}
        if (record["incident"], record["action"]) != (self.brief["incident_id"], RESTART):
            return self.unknown("The checkpoint names another incident or action.")
        self.resume_record = record
        balance = record["remaining_budget"]
        if record["state"] == "receipt_saved":
            if record["version"] != 3:
                return self.handover("Receipt saved, but remaining verification budget is unknown. Check current health.")
        else:
            balance -= DISPATCH_RESERVED  # intent was saved before the dispatch charge
        self.budget = self.tools.budget = Budget(balance)
        # Grants live only in the stopped worker's access state. The approval ledger survives; the grant is never
        # restored from the checkpoint, so any new dispatch needs a current on-call grant.
        granted = next((row for row in self.deps.sim.approvals if row["approval_ref"] == record["approval"]), None)
        notes["original_approval"] = {"ref": record["approval"], "restored": False,
                                      "status": granted["status"] if granted else "not in the approval ledger",
                                      "window_ends_tick": granted["tick"] + GRANT_TICKS if granted else None}
        if not self.access.permits(self, READ):
            notes["outcome"] = "access_gap"
            return self.handover(f"Access no longer permits verifying restart key {record['key']}. Ask the gateway "
                                 f"team to read the executor record and current gateway health. No recovery is "
                                 f"inferred from an earlier receipt.")
        found = self.tools.ledger_lookup(record["key"], record["ledger_id"])
        notes["ledger"] = {key: value for key, value in found.items() if key != "receipt"}
        if "error" in found:
            return self.unknown("The executor ledger is unavailable.")
        if not found["same_instance"]:
            return self.unknown("The ledger instance changed. The original request may still be pending or applied.")
        state = found["state"]
        if state != "absent" and found["binding"] != binding(record):
            notes["outcome"] = "conflict"
            bound = found["binding"]
            return self.handover(f"Key {record['key']} is bound to {bound['action']} {bound['parameters']['target']} "
                                 f"in the executor ledger, not to the recorded {record['action']} {record['target']}. "
                                 f"Stop: request a decision before any further action.")
        if state == "completed":
            receipt = found["receipt"]
            self.save_receipt(record, receipt)
            self.action = {"target": receipt["target"], "receipt": receipt["action_id"],
                           "approval": receipt["confirmation_ref"], "tick": receipt["tick"],
                           "reconciled_by": self.worker}
            notes["outcome"] = "reconciled_receipt"
            return self.verify(receipt)
        if state in ("rejected", "conflict"):
            notes["outcome"] = state
            return self.handover(f"The executor {'rejected' if state == 'rejected' else 'reports a key conflict for'} "
                                 f"{record['action']} {record['target']} (key {record['key']}). Stop the write: "
                                 f"request a decision if further action is necessary.")
        if state != "absent":
            return self.unknown(f"The executor ledger reports key {record['key']} as {state}.")
        notes["outcome"] = "reassessed_after_absence"
        return await self.lead()  # current need, rights and approval; dispatch at most once with the original key

    def restart(self, target):
        if target != self.resume_record["target"]:
            return self.handover(f"Current evidence supports {target}, not the recorded "
                                 f"{self.resume_record['target']}: a different target requires a new decision "
                                 f"and approval.")
        return super().restart(target)

    def verify(self, receipt):
        """Fresh health readings after the receipt, by the M1 recovery rule. An old receipt is never recovery."""
        for _ in range(6):
            try:
                metrics = GatewayHealth.model_validate(self.tools.read_metrics(GATEWAY, window_ticks=3))
            except ValidationError:
                break
            rows = metrics.readings
            last = self.tools.trace[-1].tick
            if (rows[0].tick > receipt["tick"] and [row.tick for row in rows] == [last - 2, last - 1, last]
                    and all(row.latency_ms < 20 and row.error_rate < .01 for row in rows)):
                self.observations["recovery"] = {"source": metrics.source_ref,
                                                 "samples": [row.model_dump() for row in rows]}
                return self.report("recovered", f"Restart {receipt['action_id']} reconciled from the executor "
                                                f"ledger. Monitor for recurrence. Recovery does not establish a "
                                                f"permanent fix.")
            self.observations["post_restart"] = {"source": metrics.source_ref,
                                                 "samples": [row.model_dump() for row in rows]}
        return self.handover(f"Restart {receipt['action_id']} recorded. Fresh readings after it do not show "
                             f"recovery; obtain three healthy post-action latency and error readings.")

    async def run(self, decide=None):
        from handoff import BudgetExhausted, budget_report
        try:
            report = await self.resume()
        except BudgetExhausted as stop:
            report = budget_report(self, stop)
        if self.tools.exhausted and "budget spent" not in report["next_step"]:
            report = budget_report(self, self.tools.exhausted)
        report["team"] = self.team_record()
        report["resume"] = self.reconciliation
        return report
