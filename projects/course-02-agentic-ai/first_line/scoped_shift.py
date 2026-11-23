"""M2 entry point for a scoped first-line shift."""

import re
from datetime import datetime, timedelta

from meridian.agent_runtime import IncidentDeps
from meridian.tools import MeridianTools

from scoped_access import READ, RESTART
from scoped_memory import Evidence, Lesson
from shift import Decision, GATEWAY, Shift


class ScopedTools(MeridianTools):
    def _run(self, tool, args, fn):
        if tool != "tickets.search_issues":
            return super()._run(tool, args, fn)

        def safe_tickets():
            incident = self.sim.scenario.incident["id"]
            result = fn()
            if "issues" not in result:
                return result
            return {"issues": [
                {"key": row["key"], "created": row["created"], "project": "MRX",
                 "component": GATEWAY, "summary": incident + ":"}
                for row in result["issues"]
                if row["summary"].partition(":")[0] == incident
                and re.fullmatch(r"MRX-[0-9]+", row["key"])
                and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}", row["created"])
            ]}

        return super()._run(tool, args, safe_tickets)


    def request_approval(self, action, target, reason, approver_role="on-call"):
        shift = self.shift
        if (action != RESTART or approver_role != "on-call" or not shift.access.allowed_target(shift, target)
                or not shift.access.approver_allowed()):
            return {"status": "denied"}
        record = super().request_approval(action, target, reason, approver_role)
        shift.access.grant(shift, target, record)
        return record

    def action_status(self, idempotency_key):
        if not self.shift.access.decisions or self.shift.access.decisions[-1]["decision"] != "dispatch":
            return {"error": "M2 dispatch denied"}
        return super().action_status(idempotency_key)

    def restart_service(self, component, idempotency_key=None, confirmation_ref=None):
        return {"error": "M2 dispatch denied"}

    def rollback_change(self, change_id, idempotency_key=None, confirmation_ref=None):
        return {"error": "M2 dispatch denied"}

    def restart_instance(self, instance_id, idempotency_key=None, confirmation_ref=None):
        shift = self.shift
        if shift.access.check_dispatch(shift, instance_id, idempotency_key, confirmation_ref) != "dispatch":
            return {"error": "M2 dispatch denied"}
        return super().restart_instance(instance_id, idempotency_key, confirmation_ref)


class ScopedShift(Shift):
    def __init__(self, sim, identity, access, memory, readers):
        if not re.fullmatch(r"INC-[0-9]+", sim.scenario.incident["id"]):
            raise ValueError("M2 requires a synthetic incident ID")
        super().__init__(IncidentDeps(ScopedTools(sim), identity=identity))
        self.brief.pop("summary")
        self.tools.shift = self
        self.access = access
        self.memory = memory
        self.readers = readers
        self.memory_trace = []

    def now(self):
        return self.time_at(self.deps.sim.state.tick)

    def time_at(self, tick):
        return datetime.fromisoformat(self.deps.sim.clock.timestamp(tick))

    def restart(self, target):
        if not self.access.allowed_target(self, target):
            self.access.decisions.append({"tick": self.deps.sim.state.tick, "decision": "permission_denied"})
            return self.report("denied", "Inspect current gateway instance readings and dependency links.")
        before = len(self.access.decisions)
        report = super().restart(target)
        if len(self.access.decisions) > before:
            decision = self.access.decisions[-1]["decision"]
            if decision == "permission_denied":
                return self.report("denied", "Inspect current gateway instance readings and dependency links.")
            if decision == "approval_required":
                return self.handover("Ask for a new on-call grant for the current target.")
            if decision == "refresh_evidence":
                return self.handover("Refresh gateway instance readings and dependency links.")
        return report

    def conditions(self):
        samples = self.observations.get("instances", {})
        if (not samples or "missing" in self.observations
                or self.deps.sim.state.tick - self.last_read_tick["instances"] > 5
                or any(row["freshness"] != "current" for row in samples.values())):
            return {}
        return {"per_instance_readings": 1,
                "hot_instance": int(any(row["memory_pct"] > 90 for row in samples.values()))}

    async def run(self, decide):
        if not self.access.permits(self, READ):
            return self.report("denied", "Ask the gateway team for a permitted health reading.")

        principal = self.access.requester
        handover_token = object()
        pending = self.memory.handover(principal, GATEWAY, self.now(), {}, handover=handover_token)
        note_ids = [row["id"] for row in pending if row["kind"] == "note"]

        async def decide_with_memory(context):
            if not self.access.permits(self, READ):
                return Decision(step="handover")
            now = self.now()
            conditions = self.conditions()
            views = self.memory.search(self.access.requester, GATEWAY, now, conditions)
            # Rebuild delivered notes for this shift from current source access.
            notes = [self.memory.lookup(self.access.requester, key, now, conditions, handover=handover_token)
                     for key in note_ids]
            handover = [row for row in notes if row is not None] + [row for row in views if row["kind"] != "note"][:2]
            self.memory_trace.append({"tick": self.deps.sim.state.tick,
                                      "conditions": conditions, "shown": [row["id"] for row in handover]})
            corrections = [view for key in self.memory.withdrawn
                           if (view := self.memory.correction(self.access.requester, key)) is not None]
            decision = await decide({**context, "handover": handover, "corrections": corrections})
            return decision if self.access.permits(self, READ) else Decision(step="handover")

        report = await super().run(decide_with_memory)
        if self.access.permits(self, READ):
            self.close(report)
        else:
            report = self.report("denied", "Ask the gateway team for a permitted health reading.")
            report["observations"] = {}
        return report

    def close(self, report):
        principal = self.access.requester
        incident = self.brief["incident_id"]
        refs = []
        for instance, sample in self.observations.get("instances", {}).items():
            ref = f"{incident}/{sample['source']}"
            read_at = self.time_at(int(ref.rsplit("/", 1)[1]))
            observed = read_at.replace(hour=int(sample["time"][:2]), minute=int(sample["time"][3:5]))
            if observed > read_at:
                observed -= timedelta(days=1)
            if ref in self.memory.sources:
                continue
            self.memory.record(Evidence(ref, incident, GATEWAY, observed, "tool",
                                        self.readers, instance, sample["memory_pct"], principal.team))
            if sample["freshness"] == "current":
                refs.append(ref)
        for target, link in self.observations.get("links", {}).items():
            ref = f"{incident}/check_link/{target}/{link['tick']}"
            self.memory.record(Evidence(ref, incident, GATEWAY, self.time_at(link["tick"]),
                                        "tool", self.readers, target, link["state"], principal.team))
            if (report.get("follow_up", {}).get("target") == target
                    and principal.id in self.readers):
                self.memory.save(principal, Lesson(f"{incident}/open-link", principal.team, principal.id,
                                                   GATEWAY, "link_read", "Check the dependency link again.",
                                                   (ref,), self.now(), kind="note"))
                self.memory_trace.append({"saved": f"{incident}/open-link", "sources": [ref]})
        if self.action:
            receipt = self.action
            self.memory.record(Evidence(f"{incident}/{receipt['receipt']}", incident, GATEWAY,
                                        self.time_at(receipt["tick"]),
                                        "tool", self.readers, "restart", receipt["target"], principal.team))
        if (refs and len(refs) == len(self.observations["instances"]) and "missing" not in self.observations
                and any(row["memory_pct"] > 90 for row in self.observations["instances"].values())
                and principal.id in self.readers):
            self.memory.save(principal, Lesson(f"{incident}/compare", principal.team, principal.id, GATEWAY,
                                               "hot_instance", "Compare current instance readings and check both links.",
                                               tuple(refs), self.now()))
            self.memory_trace.append({"saved": f"{incident}/compare", "sources": refs})
