"""M3 specialist handoffs (#18) on the M2 scoped lead path. Offline and scripted: no model is called.

The lead owns the incident. It asks two read-only specialists in one round, in a fixed order, validates each
reply against its task and the shared trace, allows one follow-up across both, and then either acts within the
M2 restart authority or hands over. Specialists read only their allowlisted tools, within the caller's scope.
They cannot approve, dispatch or save lessons. Every traced call, by the lead or a specialist, draws from one
shift budget, which the single agent gets too.
"""

import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "first_line"))  # reuse the M1/M2 modules unchanged

from fastmcp import Client  # noqa: E402
from fastmcp.exceptions import ToolError  # noqa: E402
from pydantic import BaseModel, ValidationError  # noqa: E402

from meridian.agent_runtime import IncidentDeps  # noqa: E402
from meridian.mcp_servers import build_servers  # noqa: E402
from scoped_access import LINKS, READ  # noqa: E402
from scoped_shift import ScopedShift, ScopedTools  # noqa: E402
from shift import FAULTY, GATEWAY, Service, TicketList  # noqa: E402

SHIFT_CALLS = 32  # traced simulator calls per shift, shared by the lead and both specialists
TASK_TICKS = 6  # a task's deadline, in ticks after it is issued
LOG_LOOKBACK = 5  # service logs from this many ticks before the incident brief
ORDER = ("application", "infrastructure")  # measurements are read last, nearest the decision
STATUSES = ("found", "no_evidence", "blocked")
READS = {
    "application": ("deployments.get_service", "deployments.list_deployments", "tickets.search_issues", "read_logs"),
    "infrastructure": ("read_metrics", "check_link"),
}
NATIVE = {"read_metrics", "check_link", "read_logs"}
WRITES = {"request_approval", "restart_instance", "restart_service", "rollback_change", "comment_ticket",
          "send_message", "deployments.rollback_deployment", "deployments.restart_workload"}
assert not WRITES & {tool for reads in READS.values() for tool in reads}  # specialists stay read-only
QUESTIONS = {
    "application": "Which change records, open incident tickets and gateway service logs bear on this incident?",
    "infrastructure": "What are the current per-instance gateway readings and both dependency link states?",
}
# Delivery faults for controls, applied by the harness after a specialist has done its reads.
FAULTS = ("drop", "wrong_task", "unknown_source", "no_target", "late")


class BudgetExhausted(Exception):
    """A traced call was refused before it ran: the shift budget is spent. No time passes."""


class ScopeError(Exception):
    """A specialist asked for a tool outside its task, or the caller's scope no longer permits reads."""


@dataclass
class Budget:
    limit: int
    used: int = 0
    by_role: dict = field(default_factory=dict)

    def remaining(self):
        return self.limit - self.used


class TeamTools(ScopedTools):
    """The M2 scoped tools with one shared budget. A refused call is not traced and does not advance time."""

    budget = None
    role = "lead"
    exhausted = None  # the first refused tool; an MCP server wraps the exception, so it is also recorded here

    def _run(self, tool, args, fn):
        if self.budget.remaining() <= 0:
            self.exhausted = self.exhausted or tool
            raise BudgetExhausted(tool)
        self.budget.used += 1
        self.budget.by_role[self.role] = self.budget.by_role.get(self.role, 0) + 1
        self.call_roles.append(self.role)
        return super()._run(tool, args, fn)


def install_tools(shift, budget, tools_class=TeamTools):
    """Replace the M2 shift's tools with budgeted ones before any call. Access, approval and dispatch gates are the
    inherited M2 ones."""
    tools = tools_class(shift.deps.sim, actor=shift.tools.actor)
    tools.budget = budget
    tools.call_roles = []  # the role behind each traced call, in trace order
    tools.shift = shift
    shift.deps = IncidentDeps(tools, identity=shift.deps.identity)
    shift.tools = tools
    shift.servers = build_servers(tools, ["tickets", "deployments", "monitoring"])


class BudgetedShift(ScopedShift):
    """The M2 single agent under the same shift budget as the team."""

    def __init__(self, sim, identity, access, memory, readers, budget):
        super().__init__(sim, identity, access, memory, readers)
        install_tools(self, budget)

    async def run(self, decide):
        try:
            report = await super().run(decide)
        except BudgetExhausted as stop:
            return budget_report(self, stop)
        return budget_report(self, self.tools.exhausted) if self.tools.exhausted else report


def budget_report(shift, stop):
    if shift.action:
        return shift.handover(f"Shift budget spent before {stop}. Restart {shift.action['receipt']} recorded; "
                              f"obtain three healthy post-action readings.")
    return shift.handover(f"Shift budget spent before {stop}. This shift recorded no restart receipt. Review the "
                          f"saved evidence and the executor's action record.")


@dataclass
class Task:
    task_id: str
    incident_id: str
    caller_scope: dict
    specialty: str
    target: str
    question: str
    allowed_reads: tuple
    issued_tick: int
    deadline_tick: int
    remaining_budget: int
    focus: str | None = None  # a narrowed follow-up: one link to read again


@dataclass
class Result:
    task_id: str
    status: str
    target: str
    finding: dict
    sources: list
    limitations: list
    suggested_next_read: str | None
    returned_tick: int


class Reader:
    """The only tool surface a specialist gets. The harness, not the specialist, records which traced calls belong
    to the task, so a reply cannot cite a call it did not make."""

    def __init__(self, lead, task):
        self.lead, self.task, self.steps = lead, task, []

    async def call(self, tool, **args):
        lead, task = self.lead, self.task
        if tool not in task.allowed_reads or tool in WRITES:
            raise ScopeError(f"{tool} is outside the {task.specialty} task")
        if not lead.access.permits(lead, READ):
            raise ScopeError("the caller's scope no longer permits reads")
        if lead.deps.sim.state.tick >= task.deadline_tick:
            raise ScopeError("task deadline reached")
        if lead.budget.remaining() <= 0:
            lead.tools.exhausted = lead.tools.exhausted or tool
            raise BudgetExhausted(tool)
        lead.tools.role = task.specialty
        try:
            if tool in NATIVE:
                data = getattr(lead.tools, tool)(**args)
            else:
                server, name = tool.split(".")
                async with Client(lead.servers[server]) as client:
                    data = (await client.call_tool(name, args)).data
        finally:
            lead.tools.role = "lead"
        call = lead.tools.trace[-1]
        self.steps.append(call.step)
        label = args.get("target") or args.get("component") or args.get("service") or args.get("project")
        return data, {"id": f"{tool}/{label}/{call.tick}", "tool": tool, "step": call.step,
                      "tick": call.tick, "time": call.time}


class Deployment(BaseModel):
    deployment_id: str
    service: str
    kind: str
    deployed_at: str
    version_before: str | None = None
    version_after: str | None = None
    state: str


class DeploymentList(BaseModel):
    items: list[Deployment]


async def infrastructure(reader, task):
    """Scripted infrastructure specialist: one per-instance metrics read, then the dependency links in order."""
    finding, sources, limitations = {}, [], []
    links = (task.focus,) if task.focus else LINKS
    if not task.focus:
        metrics, source = await reader.call("read_metrics", component=GATEWAY, window_ticks=1, per_instance=True)
        rows = metrics.get("readings") if isinstance(metrics, dict) and metrics.get("component") == GATEWAY else None
        if not rows or not rows[-1].get("instances"):
            return blocked(task, reader, sources, "read_metrics returned no per-instance reading")
        sources.append(source)
        row = rows[-1]
        current = row["tick"] == source["tick"]
        if not current:
            limitations.append(f"Per-instance sample from {row['time']} predates the read at {source['time']}.")
        finding["instances"] = {name: {"memory_pct": sample["memory_pct"], "status": sample["status"],
                                       "time": row["time"], "read_at": source["time"],
                                       "freshness": "current" if current else "stale", "source": source["id"]}
                                for name, sample in sorted(row["instances"].items())}
        finding["version"] = row.get("version")
    finding["links"] = {}
    for name in links:
        link, source = await reader.call("check_link", source=GATEWAY, target=name)
        if (not isinstance(link, dict) or link.get("source") != GATEWAY or link.get("target") != name
                or link.get("state") not in {"up", "down", "degraded"}):
            return blocked(task, reader, sources, f"check_link returned no state for {name}")
        sources.append(source)
        finding["links"][name] = {"state": link["state"], "tick": link["observed_tick"], "source": source["id"]}
    faulty = [name for name, row in finding["links"].items() if row["state"] in FAULTY]
    return Result(task.task_id, "found", task.target, finding, sources, limitations,
                  f"check_link {faulty[0]}" if faulty else None, reader.lead.deps.sim.state.tick)


async def application(reader, task):
    """Scripted application specialist: service record, change records, open incident tickets, service logs.
    Only identifiers, times and counts leave it; backend text is never copied into a finding."""
    lead, sources, limitations = reader.lead, [], []
    try:
        data, source = await reader.call("deployments.get_service", service=GATEWAY)
        service = Service.model_validate(data)
        sources.append(source)
        data, changes_source = await reader.call("deployments.list_deployments", service=GATEWAY, limit=5)
        changes = DeploymentList.model_validate(data).items
        sources.append(changes_source)
        data, tickets_source = await reader.call("tickets.search_issues", project="MRX", component=GATEWAY,
                                                 issue_type="Incident", status="Open")
        tickets = TicketList.model_validate(data).issues
        sources.append(tickets_source)
    except (ValidationError, ToolError):
        return blocked(task, reader, sources, "a change, service or ticket read returned no usable record")
    since = lead.brief["tick"] - LOG_LOOKBACK
    logs, logs_source = await reader.call("read_logs", component=GATEWAY, since_tick=since, limit=200)
    if not isinstance(logs, dict) or not isinstance(logs.get("lines"), list):
        return blocked(task, reader, sources, "read_logs returned no lines")
    sources.append(logs_source)
    slow, change_errors = {}, {}
    ids = [change.deployment_id for change in changes]
    for line in logs["lines"]:
        for name in LINKS:
            if re.search(rf"slow response from {re.escape(name)} ", line["message"]):
                ticks = slow.setdefault(name, [])
                ticks.append(line["tick"])
        if line["level"] == "ERROR":
            for change_id in ids:
                if re.search(rf"\b{re.escape(change_id)}\b", line["message"]):
                    change_errors[change_id] = change_errors.get(change_id, 0) + 1
    finding = {
        "service": {"version": service.version, "critical": service.critical, "replicas": service.replicas,
                    "source": source["id"]},
        "change_records": {"count": len(changes), "source": changes_source["id"]},
        "changes": [{"id": change.deployment_id, "kind": change.kind, "deployed_at": change.deployed_at,
                     "version_before": change.version_before, "version_after": change.version_after,
                     "state": change.state, "source": changes_source["id"]} for change in changes],
        "tickets": [{"key": ticket.key, "created": ticket.created, "component": ticket.component,
                     "source": tickets_source["id"]}
                    for ticket in tickets if ticket.summary.partition(":")[0] == lead.brief["incident_id"]],
        "service_logs": {"since_tick": since, "read_tick": logs_source["tick"], "source": logs_source["id"],
                         "slow_dependency": {name: {"lines": len(ticks), "first_tick": min(ticks),
                                                    "last_tick": max(ticks)} for name, ticks in slow.items()},
                         "change_errors": change_errors},
    }
    for change in finding["changes"]:
        if change["state"] == "active" and not change_errors.get(change["id"]):
            limitations.append(f"No service-log error names {change['id']}: no evidence that it caused the delay.")
    return Result(task.task_id, "found", task.target, finding, sources, limitations, None, lead.deps.sim.state.tick)


def blocked(task, reader, sources, reason):
    return Result(task.task_id, "blocked", task.target, {}, sources, [reason], None,
                  reader.lead.deps.sim.state.tick)


SPECIALISTS = {"application": application, "infrastructure": infrastructure}


def cited(value):
    """Every `source` named anywhere inside a finding."""
    if isinstance(value, dict):
        return [ref for key, item in value.items()
                for ref in ([item] if key == "source" else cited(item))]
    if isinstance(value, list):
        return [ref for item in value for ref in cited(item)]
    return []


def check(lead, task, result, steps):
    """Accept a reply only if it answers this task, for this target, in time, from calls this task made.
    Returns (verdict, reason); the verdict is `accepted`, `missing`, `timed_out` or `invalid`."""
    if result is None:
        return "missing", "no reply"
    if result.task_id != task.task_id:
        return "invalid", "wrong task ID"
    if result.status not in STATUSES:
        return "invalid", "unknown status"
    if result.target != task.target:
        return "invalid", "missing or wrong target"
    if result.returned_tick > task.deadline_tick:
        return "timed_out", f"returned at tick {result.returned_tick}, after the deadline {task.deadline_tick}"
    trace = {call.step: call for call in lead.tools.trace}
    ids = set()
    for source in result.sources:
        call = trace.get(source.get("step"))
        if (call is None or call.step not in steps or call.tool != source.get("tool") or call.tick != source.get("tick")
                or call.time != source.get("time") or source.get("tool") not in task.allowed_reads
                or not task.issued_tick <= call.tick <= result.returned_tick):
            return "invalid", f"unknown source {source.get('id')}"
        ids.add(source["id"])
    if any(ref not in ids for ref in cited(result.finding)):
        return "invalid", "finding cites an unknown source"
    if result.status == "found" and not ids:
        return "invalid", "a finding without sources"
    return "accepted", None


class TeamLead(ScopedShift):
    """The M2 scoped shift as an incident lead with two specialists. Decisions are code-owned and scripted."""

    TOOLS = TeamTools

    def __init__(self, sim, identity, access, memory, readers, budget, faults=None):
        super().__init__(sim, identity, access, memory, readers)
        install_tools(self, budget, self.TOOLS)
        self.budget = budget
        self.faults = {specialty: list(items) for specialty, items in (faults or {}).items()}
        self.exchanges = []  # every task, its reply and the verdict, in order
        self.follow_up = None
        self.counterfactual = None
        self.summary = None  # which findings the lead accepted, which it lacked, and why it acted or handed over

    async def ask(self, specialty, focus=None, reason=None):
        number = len(self.exchanges) + 1
        tick = self.deps.sim.state.tick
        task = Task(f"{self.shift_id}/task-{number}", self.brief["incident_id"],
                    {"principal": self.access.requester.id, "team": self.access.requester.team, "rights": [READ]},
                    specialty, GATEWAY,
                    f"Read the {focus} link again." if focus else QUESTIONS[specialty],
                    ("check_link",) if focus else READS[specialty], tick, tick + TASK_TICKS,
                    self.budget.remaining(), focus)
        reader = Reader(self, task)
        try:
            result = await SPECIALISTS[specialty](reader, task)
        except ScopeError as error:
            result = blocked(task, reader, [], str(error))
        fault = self.faults.get(specialty, []).pop(0) if self.faults.get(specialty) else None
        result = inject(result, fault, task)
        verdict, reason_text = check(self, task, result, reader.steps)
        self.exchanges.append({"task": asdict(task), "follow_up_reason": reason, "injected": fault,
                               "calls": [{"step": step, "tick": call.tick, "tool": call.tool}
                                         for step in reader.steps for call in [self.tools.trace[step - 1]]],
                               "reply": asdict(result) if result else None,
                               "verdict": verdict, "verdict_reason": reason_text})
        return result, verdict

    def conflict(self, app, infra):
        """Service logs naming slow responses from a link that the link monitor reports up. The readings are
        sequential: the record keeps both read ticks."""
        logs = app.finding["service_logs"]
        for name, row in infra.finding["links"].items():
            slow = logs["slow_dependency"].get(name)
            if row["state"] == "up" and slow:
                return {"link": name, "service_logs": {**slow, "read_tick": logs["read_tick"], "source": logs["source"]},
                        "check_link": {"state": "up", "tick": row["tick"], "source": row["source"]}}
        return None

    async def lead(self):
        runbook = self.tools.read_runbook("order-gateway-latency", 2)
        if runbook.get("version") != 2:
            return self.handover("Read the applicable gateway runbook.")
        replies = {}
        for specialty in ORDER:
            replies[specialty] = await self.ask(specialty)
        accepted = lambda name: replies[name][1] == "accepted"  # noqa: E731
        conflict = None
        if all(accepted(name) and replies[name][0].status == "found" for name in ORDER):
            conflict = self.conflict(replies["application"][0], replies["infrastructure"][0])
        problem = next(((name, replies[name][1]) for name in ORDER if not accepted(name)), None)
        if problem is None and conflict:
            problem = ("infrastructure", "conflicting")
        if problem:
            specialty, verdict = problem
            focus = conflict["link"] if verdict == "conflicting" else None
            self.follow_up = {"specialty": specialty, "reason": verdict, "focus": focus}
            if focus:
                # What the observations would support if the newest reading simply won, before the follow-up.
                self.integrate(*(replies[name][0] for name in ORDER))
                candidate, gap = self.restart_evidence()
                self.counterfactual = {"restart_supported_without_follow_up": None if gap else candidate}
            result, verdict = await self.ask(specialty, focus, verdict)
            if focus:
                self.follow_up["separating_read"] = result.finding.get("links", {}).get(focus) if result else None
                if verdict == "accepted" and result.status == "found":
                    infra = replies["infrastructure"][0]
                    infra.finding["links"][focus] = result.finding["links"][focus]
                    infra.sources += result.sources
                    conflict["resolved_by"] = result.finding["links"][focus]
                replies["infrastructure"] = (replies["infrastructure"][0], verdict)
            else:
                replies[specialty] = (result, verdict)
        return self.decide(replies, conflict)

    def integrate(self, app, infra):
        """Accepted findings enter the same observation shape the M1/M2 gates read."""
        if infra is not None:
            self.observations["instances"] = {name: {key: row[key] for key in
                                                     ("memory_pct", "time", "status", "read_at", "freshness", "source")}
                                              for name, row in infra.finding["instances"].items()}
            self.observations["links"] = {name: {"state": row["state"], "tick": row["tick"]}
                                          for name, row in infra.finding["links"].items()}
            self.last_read_tick["instances"] = min(int(row["source"].rsplit("/", 1)[1])
                                                   for row in infra.finding["instances"].values())
            self.last_read_tick["links"] = max(row["tick"] for row in infra.finding["links"].values())
        if app is not None:
            self.observations["tickets"] = [{key: row[key] for key in ("key", "created", "component")}
                                            for row in app.finding["tickets"]]
            service = app.finding["service"]
            self.deployment = {"critical": service["critical"], "version": service["version"],
                               "replicas": service["replicas"], "source": service["source"]}
            self.observations["changes"] = app.finding["changes"]
            self.observations["service_logs"] = app.finding["service_logs"]

    def decide(self, replies, conflict):
        # Only an accepted `found` reply supplies evidence. `blocked` and `no_evidence` are valid answers that
        # still leave the gap; they are named, never read as healthy.
        lacking = {name: verdict if verdict != "accepted" else result.status
                   for name, (result, verdict) in replies.items()
                   if verdict != "accepted" or result.status != "found"}
        app, infra = (None if name in lacking else replies[name][0] for name in ORDER)
        self.observations.pop("instances", None)
        self.observations.pop("links", None)
        self.integrate(app, infra)
        self.summary = {"accepted": [name for name in ORDER if name not in lacking], "lacking": lacking,
                        "conflict": conflict}
        if conflict and "resolved_by" not in conflict:
            self.summary["why"] = "conflict not settled by the one follow-up"
            return self.handover(f"Service logs read at tick {conflict['service_logs']['read_tick']} report slow "
                                 f"{conflict['link']} responses at ticks {conflict['service_logs']['first_tick']}–"
                                 f"{conflict['service_logs']['last_tick']}; check_link at tick "
                                 f"{conflict['check_link']['tick']} reports up. The follow-up did not settle it. "
                                 f"Read the {conflict['link']} link and gateway latency again before any restart.")
        after = " after the one follow-up" if self.follow_up else ""
        if infra is None:
            self.summary["why"] = "no accepted measurements"
            return self.handover(f"Infrastructure finding {lacking['infrastructure']}{after}. A "
                                 f"{lacking['infrastructure']} reply is not evidence of health. Obtain current "
                                 f"per-instance readings and both dependency links before any restart.")
        faulty = self.faulty_links()
        if faulty:
            report = self.link_handover(faulty[0]) if len(faulty) == 1 else self.handover(
                f"Investigate the faulty links: {', '.join(faulty)}. Inspect recent changes before proposing a fix.")
            report["next_step"] += " " + self.application_context(app, lacking.get("application"))
            if conflict:
                logs, first = conflict["service_logs"], conflict["check_link"]
                report["next_step"] += (f" Readings were sequential: service logs read at tick {logs['read_tick']} "
                                        f"report slow {conflict['link']} responses at ticks {logs['first_tick']}–"
                                        f"{logs['last_tick']}; check_link at tick {first['tick']} reported up; "
                                        f"the follow-up read at tick {conflict['resolved_by']['tick']} reports "
                                        f"{conflict['resolved_by']['state']}.")
            self.summary["why"] = "faulty dependency link: outside the restart authority"
            return report
        if app is None:
            self.summary["why"] = "no accepted ticket or deployment record: no restart in scope"
            return self.handover(f"Application finding {lacking['application']}{after}: no ticket or deployment "
                                 f"record was accepted, so no restart is in scope. "
                                 f"{self.application_context(None, lacking['application'])}")
        candidate, problem = self.restart_evidence()
        if problem is None:
            self.summary["why"] = f"accepted findings support the runbook restart of {candidate}"
            return self.restart(candidate)
        self.summary["why"] = f"restart evidence {problem}"
        return self.handover("No supported restart. Review current per-instance readings, ticket, and dependency links.")

    def application_context(self, app, verdict):
        if app is None:
            return (f"Application finding {verdict}: change records, tickets and service logs were not accepted. "
                    f"The link reading alone cannot identify a change to roll back, and a {verdict} reply does not "
                    f"mean nothing changed.")
        changes = [row for row in app.finding["changes"] if row["state"] == "active"]
        if not changes:
            return f"Application: no active change record for {GATEWAY} ({app.finding['change_records']['source']})."
        named = "; ".join(f"{row['id']} {row['kind']} {row['version_before']}→{row['version_after']} at "
                          f"{row['deployed_at']} ({row['source']})" for row in changes)
        unproven = [row["id"] for row in changes if not app.finding["service_logs"]["change_errors"].get(row["id"])]
        caveat = (f" No service-log error names {', '.join(unproven)}: no evidence that "
                  f"{'it' if len(unproven) == 1 else 'any of them'} caused the delay. No rollback proposed."
                  if unproven else "")
        return f"Application: {named}.{caveat}"

    def team_record(self):
        return {"order": list(ORDER), "sequential": True, "summary": self.summary, "exchanges": self.exchanges,
                "follow_up": self.follow_up,
                "counterfactual": self.counterfactual,
                "budget": {"limit": self.budget.limit, "used": self.budget.used, "by_role": dict(self.budget.by_role)}}

    async def run(self, decide=None):
        """`decide` is unused: the lead's choices are scripted code."""
        if not self.access.permits(self, READ):
            return self.report("denied", "Ask the gateway team for a permitted health reading.")
        try:
            report = await self.lead()
        except BudgetExhausted as stop:
            report = budget_report(self, stop)
        if self.tools.exhausted and "budget spent" not in report["next_step"]:
            report = budget_report(self, self.tools.exhausted)
        report["team"] = self.team_record()
        try:
            self.close(report)
        except (ValueError, PermissionError) as error:
            self.memory_trace.append({"close_failed": str(error)})
            report["memory_error"] = "Shift record not saved. The report and any action receipt stand."
        return report


def inject(result, fault, task):
    """Apply one delivery fault to a reply, for controls. The specialist's reads have already happened."""
    if fault is None or result is None:
        return result
    if fault == "drop":
        return None
    changed = Result(**{**asdict(result)})
    if fault == "wrong_task":
        changed.task_id = task.task_id + "-other"
    elif fault == "unknown_source":
        changed.sources = [*changed.sources, {"id": "check_link/reference-db/0", "tool": "check_link", "step": 10**6,
                                              "tick": 0, "time": "00:00"}]
    elif fault == "no_target":
        changed.target = ""
    elif fault == "late":
        changed.returned_tick = task.deadline_tick + 1
    else:
        raise ValueError(f"unknown fault {fault!r}")
    return changed
