"""Authenticated run scope and simulator restart authorization for M2."""

from dataclasses import dataclass, field

from shift import GATEWAY

RESTART = "restart_instance"
READ = "read_gateway"


@dataclass(frozen=True)
class Principal:
    id: str
    team: str
    role: str
    rights: frozenset[str]


@dataclass
class Access:
    """Trusted harness state. Ticket text and decision inputs never populate it."""

    requester: Principal
    credential: Principal
    approver: Principal
    shift_end: int
    decisions: list = field(default_factory=list, init=False)
    grants: dict = field(default_factory=dict, init=False)
    spent: set = field(default_factory=set, init=False)

    def permits(self, shift, right):
        return (shift.deps.role == "first-line"
                and shift.deps.identity["team"] == self.requester.team == self.credential.team == "trading-ops"
                and self.credential.role == "service"
                and (right != RESTART or self.requester.role in {"first-line", "on-call"})
                and right in self.requester.rights and right in self.credential.rights
                and shift.deps.sim.state.tick < self.shift_end)

    def allowed_target(self, shift, target):
        if not self.permits(shift, RESTART):
            return False
        try:
            component, _ = shift.deps.sim.state.instance(target)
        except KeyError:
            return False
        return component.name == GATEWAY and not component.critical

    def binding(self, shift, target, key):
        return (self.requester.id, self.requester.team, self.credential.id, self.approver.id,
                shift.brief["incident_id"], RESTART, target, key)

    def approver_allowed(self):
        return (self.approver.role == "on-call" and self.approver.team == self.requester.team
                and "approve_restart" in self.approver.rights)

    def grant(self, shift, target, record):
        if record.get("status") == "approved" and self.approver_allowed():
            expires = min(record.get("expires_tick", self.shift_end), record["tick"] + 5, self.shift_end)
            key = f"{shift.brief['incident_id']}:restart:{target}"
            self.grants[record["approval_ref"]] = (self.binding(shift, target, key), expires)

    def current_approval(self, shift, target, ref, tick):
        records = shift.deps.sim.approvals
        record = next((row for row in records if row["approval_ref"] == ref), None)
        return (record is not None and record["status"] == "approved" and record["action"] == RESTART
                and record["target"] == target and record["requested_by"] == shift.tools.actor
                and record["approver_role"] == "on-call" and tick < record.get("expires_tick", self.shift_end))

    def check_dispatch(self, shift, target, key, ref):
        tick = shift.deps.sim.state.tick
        grant = self.grants.get(ref)
        if not self.allowed_target(shift, target) or not self.permits(shift, READ):
            reason = "permission_denied"
        elif (grant is None or ref in self.spent or grant[0] != self.binding(shift, target, key)
              or tick >= grant[1] or not self.approver_allowed()
              or not self.current_approval(shift, target, ref, tick)):
            reason = "approval_required"
        elif shift.restart_evidence() != (target, None) or not self.current_need(shift, target):
            reason = "refresh_evidence"
        else:
            self.spent.add(ref)
            reason = "dispatch"
        if reason != "dispatch":
            self.grants.pop(ref, None)
        self.decisions.append({"tick": tick, "decision": reason})
        return reason


    @staticmethod
    def current_need(shift, target):
        # World state is the simulator's dispatch-time check. The investigation
        # still needs its own fresh, scoped tool observations.
        state = shift.deps.sim.state
        service = state.component(GATEWAY)
        hot = [row.instance_id for row in service.instances if row.status == "running" and row.memory_pct > 90]
        return (hot == [target] and service.version.startswith("2.4.")
                and all(state.link(source, destination).state == "up"
                        for source, destination in ((GATEWAY, "reference-db"), (GATEWAY, "matching-engine"))))
