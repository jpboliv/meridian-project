"""M2 entry point for a scoped first-line shift."""

import re
from datetime import datetime, timedelta

from meridian.agent_runtime import IncidentDeps
from meridian.tools import MeridianTools

from scoped_access import LINKS, READ, RESTART
from scoped_memory import Evidence, Lesson
from shift import Decision, GATEWAY, Shift

DROP = 0.9  # a latency sample at or below 90% of the one before it starts a recovery


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
        self.shift_id = memory.open_shift(self.brief["incident_id"])
        self.deployment = None  # this shift's traced deployment record
        self.memory_trace = []
        self.closed = False

    def now(self):
        return self.time_at(self.deps.sim.state.tick)

    def time_at(self, tick):
        return datetime.fromisoformat(self.deps.sim.clock.timestamp(tick))

    async def read(self, server, tool, args, schema):
        result = await super().read(server, tool, args, schema)
        if (server, tool) == ("deployments", "get_service"):
            self.deployment = {"critical": result.critical, "version": result.version, "replicas": result.replicas,
                               "source": f"deployments.get_service/{self.tools.trace[-1].tick}"}
        return result

    def dispatch_evidence(self, target):
        """Fresh traced readings for the restart need, taken after the grant: every replica in one metrics
        read, then both dependency links. Returns the sources and the first unmet condition, if any."""
        metrics = self.tools.read_metrics(GATEWAY, window_ticks=1, per_instance=True)
        read_tick = self.tools.trace[-1].tick
        rows = metrics.get("readings") if metrics.get("component") == GATEWAY else None
        row = rows[-1] if rows else {}
        sources = [metrics["source_ref"]] if rows else []
        hot = sorted(name for name, sample in row.get("instances", {}).items()
                     if sample["status"] == "running" and sample["memory_pct"] > 90)
        links = {}
        for name in LINKS:
            link = self.tools.check_link(GATEWAY, name)
            if link.get("source") == GATEWAY and link.get("target") == name and "state" in link:
                links[name] = link["state"]
                sources.append(f"check_link/{name}/{link['observed_tick']}")
        if not rows:
            problem = "no_instance_reading"
        elif row["tick"] != read_tick:
            problem = "stale_instance_reading"
        elif not str(row.get("version", "")).startswith("2.4."):
            problem = "no_applicable_procedure"
        elif hot != [target]:
            problem = "target_not_sole_hot_instance"
        elif links != dict.fromkeys(LINKS, "up"):
            problem = "dependency_link_not_up"
        else:
            problem = None
        return {"problem": problem, "sources": sources, "hot_running": hot, "links": links}

    def restart(self, target):
        if not self.access.allowed_target(self, target):
            self.access.decisions.append({"tick": self.deps.sim.state.tick, "target": target,
                                          "decision": "permission_denied", "reason": "rights_or_scope"})
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

    def check_claims(self):
        """Correct a team claim about this incident as soon as traced evidence contradicts it, before the next
        decision. The latency history comes from one metrics read; the restart time from a recorded receipt."""
        principal, incident = self.access.requester, self.brief["incident_id"]
        claims = self.memory.claims(principal, incident)
        if not claims:
            return
        metrics = self.tools.read_metrics(GATEWAY, window_ticks=30)
        rows = metrics.get("readings", []) if metrics.get("component") == GATEWAY else []
        refs = self.memory.incident_sources(principal, incident, "restart")
        drop = next((row for before, row in zip(rows, rows[1:])
                     if row["latency_ms"] <= DROP * before["latency_ms"]), None)
        if drop:
            ref = f"{self.shift_id}/{metrics['source_ref']}/latency_drop"
            self.memory.record(Evidence(ref, incident, GATEWAY, self.time_at(drop["tick"]), "tool",
                                        self.readers, "latency_drop", drop["latency_ms"], principal.team))
            refs.append(ref)
        for claim in claims:
            result = self.memory.assess_restart_claim(principal, claim, tuple(refs), self.now())
            self.memory_trace.append({"tick": self.tools.trace[-1].tick, "checked_claim": claim,
                                      "assessment": result, "sources": refs})

    async def run(self, decide):
        if not self.access.permits(self, READ):
            return self.report("denied", "Ask the gateway team for a permitted health reading.")

        principal = self.access.requester
        self.check_claims()
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
            corrections = {key: view for key in self.memory.withdrawn
                           if (view := self.memory.correction(self.access.requester, key)) is not None}
            self.memory_trace.append({"tick": self.deps.sim.state.tick, "conditions": conditions,
                                      "shown": [row["id"] for row in handover], "corrections": sorted(corrections)})
            decision = await decide({**context, "handover": handover, "corrections": list(corrections.values())})
            return decision if self.access.permits(self, READ) else Decision(step="handover")

        report = await super().run(decide_with_memory)
        if not self.access.permits(self, READ):
            report = self.report("denied", "Ask the gateway team for a permitted health reading.")
            report["observations"] = {}
            return report
        try:
            self.close(report)
        except (ValueError, PermissionError) as error:
            # The report and any receipt stand even if the shift record cannot be saved.
            self.memory_trace.append({"close_failed": str(error)})
            report["memory_error"] = "Shift record not saved. The report and any action receipt stand."
        return report

    def close(self, report):
        """Save this shift's evidence and proposals once. IDs are scoped to the shift, so another shift of the
        same incident never collides with or replaces them; closing again is a no-op."""
        if self.closed:
            return
        principal, incident, shift_id = self.access.requester, self.brief["incident_id"], self.shift_id
        evidence, lessons, current = [], [], []
        samples = self.observations.get("instances", {})
        for instance, sample in samples.items():
            ref = f"{shift_id}/{sample['source']}"
            read_at = self.time_at(int(ref.rsplit("/", 1)[1]))
            observed = read_at.replace(hour=int(sample["time"][:2]), minute=int(sample["time"][3:5]))
            if observed > read_at:
                observed -= timedelta(days=1)
            evidence.append(Evidence(ref, incident, GATEWAY, observed, "tool",
                                     self.readers, instance, sample["memory_pct"], principal.team))
            if sample["freshness"] == "current":
                current.append(ref)
        links = self.observations.get("links", {})
        link_refs = {}
        for target, link in links.items():
            link_refs[target] = f"{shift_id}/check_link/{target}/{link['tick']}"
            evidence.append(Evidence(link_refs[target], incident, GATEWAY, self.time_at(link["tick"]),
                                     "tool", self.readers, target, link["state"], principal.team))
        if self.action:
            receipt = self.action
            evidence.append(Evidence(f"{shift_id}/{receipt['receipt']}", incident, GATEWAY,
                                     self.time_at(receipt["tick"]), "tool", self.readers, "restart",
                                     receipt["target"], principal.team))
        follow = report.get("follow_up", {}).get("target")
        if follow in link_refs and principal.id in self.readers:
            link = links[follow]
            lessons.append(Lesson(f"{shift_id}/open-link", principal.team, principal.id, GATEWAY, "link_read",
                                  f"Read the {follow} link again: check_link reported {link['state']} "
                                  f"at tick {link['tick']}.", (link_refs[follow],), self.now(), kind="note"))
        hot = [name for name, sample in samples.items() if sample["memory_pct"] > 90]
        if (current and len(current) == len(samples) and "missing" not in self.observations and len(hot) == 1
                and len(link_refs) == len(LINKS) and principal.id in self.readers):
            states = ", ".join(f"{target} {links[target]['state']}" for target in LINKS)
            lessons.append(Lesson(f"{shift_id}/compare", principal.team, principal.id, GATEWAY, "hot_instance",
                                  f"Compare current per-instance readings and read both dependency links before "
                                  f"a restart decision. Cited: {hot[0]} above 90% memory; links {states}.",
                                  tuple(current + [link_refs[target] for target in LINKS]), self.now()))
        for source in evidence:
            self.memory.record(source)
        for lesson in lessons:
            self.memory.save(principal, lesson)
            self.memory_trace.append({"saved": lesson.id, "text": lesson.text, "sources": list(lesson.sources)})
        self.closed = True
