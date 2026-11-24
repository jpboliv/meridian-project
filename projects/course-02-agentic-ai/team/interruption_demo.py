"""Two worker stops on the public simulator. Emit source records, without grading the run."""
import asyncio
import json
import tempfile
from pathlib import Path

from handoff import SHIFT_CALLS
from m2_demo import IDENTITY, READERS
from m3_demo import access, reads
from resume import ReplacementLead, WorkerStopped
from resume_demo import interrupted
from scoped_memory import ScopedMemory


class StopBeforeVerification(ReplacementLead):
    def verify(self, receipt):
        raise WorkerStopped("after_reconciled_receipt")


async def trial(case, folder):
    sim, ledger, store, _, stopped = await interrupted(case, folder, "after_dispatch_before_receipt")

    def start(cls, name):
        return cls(sim, dict(IDENTITY), access(), ScopedMemory(), READERS, store, name)

    first = start(StopBeforeVerification, "worker-2")
    try:
        await first.run()
    except WorkerStopped as stop:
        point = stop.point
    else:
        raise AssertionError("replacement did not stop")
    checkpoint = store.load()
    middle = reads(first)
    del first
    last = start(ReplacementLead, "worker-3")
    report = await last.run()
    audit = [{"action_id": row.action_id, "key": row.idempotency_key, "effect": row.effect_applied,
              "tick": row.tick, "target": row.target, "outcome": row.outcome} for row in ledger.audit]
    return {"input": case, "stopped": stopped, "second_stop": {"point": point, "reads": middle,
            "state": checkpoint["state"], "receipt": checkpoint["receipt"], "remaining": checkpoint["remaining_budget"]},
            "replacement": {"reads": reads(last), "status": report["status"], "action": report["action"],
                            "budget": report["team"]["budget"], "resume": last.reconciliation},
            "metrics": [{"tick": c.tick, "result": c.result} for c in last.tools.trace if c.tool == "read_metrics"],
            "executor_audit": audit, "limit": SHIFT_CALLS}


if __name__ == "__main__":
    for case in ("A", "N"):
        with tempfile.TemporaryDirectory() as folder:
            print(json.dumps(asyncio.run(trial(case, Path(folder))), sort_keys=True))
