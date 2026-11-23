"""Authenticated run scope and simulator restart authorization for M2.

Access decisions use the authenticated principals, the approval ledger, the simulated clock and traced tool
results from this shift. At the effect boundary, the course security adapter provides current
target classification as authorization metadata, separate from diagnostic evidence.
"""

import re
from dataclasses import dataclass, field

from meridian.security import describe_action
from shift import GATEWAY

RESTART = "restart_instance"
READ = "read_gateway"
LINKS = ("reference-db", "matching-engine")
GRANT_TICKS = 5


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
        """One noncritical gateway instance, by name and by this shift's traced deployment record."""
        match = re.fullmatch(rf"{GATEWAY}-([1-9][0-9]*)", target)
        deployment = shift.deployment
        return (self.permits(shift, RESTART) and match is not None and deployment is not None
                and deployment["critical"] is False and int(match[1]) <= deployment["replicas"])

    def binding(self, shift, target, key):
        return (self.requester.id, self.requester.team, self.credential.id, self.approver.id,
                shift.brief["incident_id"], RESTART, target, key)

    def approver_allowed(self):
        return (self.approver.role == "on-call" and self.approver.team == self.requester.team
                and "approve_restart" in self.approver.rights)

    def grant(self, shift, target, record):
        if record.get("status") == "approved" and self.approver_allowed():
            expires = min(record.get("expires_tick", self.shift_end), record["tick"] + GRANT_TICKS, self.shift_end)
            key = f"{shift.brief['incident_id']}:restart:{target}"
            self.grants[record["approval_ref"]] = (self.binding(shift, target, key), expires)

    def current_approval(self, shift, target, ref, tick):
        """The approval ledger entry is still approved, exact and unexpired at `tick`."""
        record = next((row for row in shift.deps.sim.approvals if row["approval_ref"] == ref), None)
        return (record is not None and record["status"] == "approved" and record["action"] == RESTART
                and record["target"] == target and record["requested_by"] == shift.tools.actor
                and record["approver_role"] == "on-call" and tick < record.get("expires_tick", self.shift_end))

    def grant_problem(self, shift, target, key, ref):
        tick = shift.deps.sim.state.tick
        grant = self.grants.get(ref)
        if ref in self.spent:
            return "grant_spent"
        if grant is None:
            return "no_grant"
        if grant[0] != self.binding(shift, target, key):
            return "grant_mismatch"
        if tick >= grant[1] or not self.current_approval(shift, target, ref, tick):
            return "grant_expired"
        if not self.approver_allowed():
            return "approver_not_allowed"
        return None

    def classification_problem(self, shift, target, record):
        """The target must still exist, be the exact gateway instance and be noncritical now. Asks the course
        security adapter, which does not advance the clock; anything it cannot confirm fails closed."""
        classification = {"source": "security.describe_action", "component": None, "critical": None}
        record["classification"] = classification
        try:
            request = describe_action(shift.deps, RESTART, target)
            action, resolved_target = request.action, request.target
            component, critical = request.component, request.critical
        except Exception:
            # A failed lookup cannot authorize an effect.
            return "target_unverified"
        if (action, resolved_target) != (RESTART, target) or component is None or type(critical) is not bool:
            return "target_unverified"
        classification["critical"] = critical
        if component != GATEWAY:
            return "target_mismatch"
        classification["component"] = GATEWAY
        if critical:
            return "target_critical"
        return None

    def check_dispatch(self, shift, target, key, ref):
        """The effect boundary. Rights and the grant are checked, then fresh traced readings and links are taken,
        then the target's current classification, rights and the grant are checked again at the tick the executor
        would act. Spends the grant only on dispatch."""
        record = {"tick": shift.deps.sim.state.tick, "target": target, "approval": ref}
        if not self.allowed_target(shift, target) or not self.permits(shift, READ):
            decision, reason = "permission_denied", "rights_or_scope"
        elif problem := self.grant_problem(shift, target, key, ref):
            decision, reason = "approval_required", problem
        else:
            evidence = shift.dispatch_evidence(target)
            problem = evidence.pop("problem")
            record["evidence"] = evidence
            if classified := self.classification_problem(shift, target, record):
                decision, reason = "permission_denied", classified
            elif problem:
                decision, reason = "refresh_evidence", problem
            elif not self.allowed_target(shift, target) or not self.permits(shift, READ):
                decision, reason = "permission_denied", "rights_changed_during_reads"
            elif problem := self.grant_problem(shift, target, key, ref):
                decision, reason = "approval_required", f"{problem}_during_reads"
            else:
                decision, reason = "dispatch", "fresh_evidence_and_grant"
        if decision == "dispatch":
            self.spent.add(ref)
        else:
            self.grants.pop(ref, None)
        record.update(decision=decision, reason=reason, dispatch_tick=shift.deps.sim.state.tick)
        self.decisions.append(record)
        return decision
