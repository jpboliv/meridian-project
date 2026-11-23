"""Run the public M3 demonstrations offline with scripted decisions. No model is called and no key is read.

`--part handoff` runs the #18 specialist handoffs and the single-agent comparison under one shift budget.
`--part resume` runs the #19 worker replacement and its failure controls. With no option, both run. Each output
line is one JSON record with its own `checks`; the command exits 1 if any check fails. Controls marked
`"control": "naive"` show a worker that ignores the contract; for them the listed checks are expected to fail.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from handoff import SHIFT_CALLS, Budget, BudgetedShift, TeamLead
from m2_demo import APPROVER, CREDENTIAL, IDENTITY, M2_CASES, READERS, REQUESTER, investigate
from scoped_access import Access
from scoped_memory import ScopedMemory
from workbench import start_exchange

HERE = Path(__file__).resolve().parent
CASES = {**M2_CASES, **{path.stem.removeprefix("shift-").upper(): path
                        for path in sorted((HERE / "cases-m3").glob("shift-*.yaml"))}}
SHIFT_END = 250
COSTS = {"measured": "traced simulator calls by role, simulated ticks (one per call), approval requests and "
                     "applied effects, all read from the simulator trace and executor audit",
         "scripted": "every lead and specialist decision is code: 0 model requests and 0 tokens were sent. A live "
                     "run's token cost is not measured here."}


def access(credential=CREDENTIAL):
    return Access(REQUESTER, credential, APPROVER, SHIFT_END)


def reads(shift):
    return [{"tick": call.tick, "role": role, "tool": call.tool}
            for call, role in zip(shift.tools.trace, shift.tools.call_roles)]


def effects(sim):
    return len(sim.executor.effects())


def summary(shift, report, sim):
    return {"status": report["status"], "action": report["action"], "next_step": report["next_step"],
            "follow_up": report.get("follow_up"), "effects": effects(sim),
            "approval_requests": sum(call.tool == "request_approval" for call in shift.tools.trace),
            "tool_calls": len(shift.tools.trace), "by_role": dict(shift.budget.by_role)
            if hasattr(shift, "budget") else None, "ticks": sim.state.tick - shift.brief["tick"],
            "recovery": report["observations"].get("recovery"), "model_requests": 0}


async def single(case):
    sim = start_exchange(CASES[case])
    budget = Budget(SHIFT_CALLS)
    shift = BudgetedShift(sim, dict(IDENTITY), access(), ScopedMemory(), READERS, budget)
    shift.budget = budget
    report = await shift.run(investigate)
    return shift, report, sim


async def team(case, faults=None, budget=SHIFT_CALLS):
    sim = start_exchange(CASES[case])
    lead = TeamLead(sim, dict(IDENTITY), access(), ScopedMemory(), READERS, Budget(budget), faults)
    report = await lead.run()
    return lead, report, sim


def team_record(run, case, lead, report, sim, checks, **extra):
    return {"part": "handoff", "run": run, "case": case, "agent": "team", **summary(lead, report, sim),
            "summary": report["team"]["summary"], "follow_up_used": report["team"]["follow_up"],
            "counterfactual": report["team"]["counterfactual"], "budget": report["team"]["budget"],
            "exchanges": [{"task": row["task"], "injected": row["injected"], "verdict": row["verdict"],
                           "verdict_reason": row["verdict_reason"], "calls": row["calls"], "reply": row["reply"]}
                          for row in report["team"]["exchanges"]],
            "reads": reads(lead), **extra, "checks": checks}


async def handoff_runs():
    records, rows = [], []
    for case in ("A", "D", "M"):
        shift, report, sim = await single(case)
        rows.append({"case": case, "agent": "single", **{key: value for key, value in summary(shift, report, sim).items()
                                                          if key not in ("next_step", "recovery", "follow_up")}})
        if case == "M":
            single_m = (shift, report, sim)
    lead, report, sim = await team("A")
    records.append(team_record("complete, restart within authority", "A", lead, report, sim, {
        "both findings accepted": report["team"]["summary"]["accepted"] == ["application", "infrastructure"],
        "no follow-up needed": report["team"]["follow_up"] is None,
        "one restart by the lead": effects(sim) == 1 and report["action"]["target"] == "order-gateway-2",
        "recovery cites post-restart readings": bool(report["observations"].get("recovery"))
        and report["observations"]["recovery"]["samples"][0]["tick"] > report["action"]["tick"],
        "specialists made no writes": all(row["tool"] not in ("request_approval", "restart_instance")
                                          for row in reads(lead) if row["role"] != "lead")}))
    rows.append({"case": "A", "agent": "team", **{k: v for k, v in summary(lead, report, sim).items()
                                                   if k not in ("next_step", "recovery", "follow_up")}})

    lead, report, sim = await team("D")
    records.append(team_record("complete handoff", "D", lead, report, sim, {
        "both findings accepted": report["team"]["summary"]["accepted"] == ["application", "infrastructure"],
        "degraded link handed over with its source": report["follow_up"]["target"] == "reference-db",
        "change found and not called the cause": "CHG-5100" in report["next_step"]
        and "no evidence that" in report["next_step"],
        "no rollback or restart": effects(sim) == 0
        and all(row["tool"] != "request_approval" for row in reads(lead))}))
    rows.append({"case": "D", "agent": "team", **{k: v for k, v in summary(lead, report, sim).items()
                                                   if k not in ("next_step", "recovery", "follow_up")}})

    lead, report, sim = await team("D", {"application": ["drop", "drop"]})
    records.append(team_record("application finding missing", "D", lead, report, sim, {
        "infrastructure accepted, application lacking": report["team"]["summary"]["accepted"] == ["infrastructure"]
        and report["team"]["summary"]["lacking"] == {"application": "missing"},
        "one follow-up, to application": report["team"]["follow_up"]["specialty"] == "application"
        and len(report["team"]["exchanges"]) == 3,
        "missing reply not read as no change": "missing reply does not mean nothing changed" in report["next_step"]
        and "cannot identify a change to roll back" in report["next_step"],
        "same operator handoff as the single agent": report["status"] == "needs_operator"
        and report["follow_up"]["target"] == "reference-db" and effects(sim) == 0}))
    rows.append({"case": "D (application missing)", "agent": "team",
                 **{k: v for k, v in summary(lead, report, sim).items() if k not in ("next_step", "recovery", "follow_up")}})

    lead, report, sim = await team("D", {"application": ["drop"]})
    records.append(team_record("application reply lost once, follow-up answered", "D", lead, report, sim, {
        "follow-up filled the gap": report["team"]["summary"]["accepted"] == ["application", "infrastructure"],
        "change context reported": "CHG-5100" in report["next_step"], "no effect": effects(sim) == 0}))

    lead, report, sim = await team("M")
    shift_m, report_m, sim_m = single_m
    records.append(team_record("conflicting findings", "M", lead, report, sim, {
        "conflict detected on reference-db": report["team"]["summary"]["conflict"]["link"] == "reference-db",
        "newest-reading-wins would have restarted": report["team"]["counterfactual"]
        == {"restart_supported_without_follow_up": "order-gateway-2"},
        "one separating read, degraded": report["team"]["follow_up"]["separating_read"]["state"] == "degraded",
        "no approval requested, no effect": effects(sim) == 0
        and all(row["tool"] != "request_approval" for row in reads(lead)),
        "readings described as sequential": "Readings were sequential" in report["next_step"]},
        single_agent={"status": report_m["status"], "approval_requests": summary(shift_m, report_m, sim_m)[
            "approval_requests"], "dispatch": shift_m.access.decisions, "effects": effects(sim_m)}))
    rows.append({"case": "M", "agent": "team", **{k: v for k, v in summary(lead, report, sim).items()
                                                   if k not in ("next_step", "recovery", "follow_up")}})

    lead, report, sim = await team("D", {"application": ["wrong_task"], "infrastructure": ["drop"]})
    records.append(team_record("format repair spends the one follow-up", "D", lead, report, sim, {
        "repair went to application": report["team"]["follow_up"] == {"specialty": "application",
                                                                      "reason": "invalid", "focus": None},
        "no second follow-up for infrastructure": len(report["team"]["exchanges"]) == 3,
        "missing measurements are not health": "not evidence of health" in report["next_step"]
        and effects(sim) == 0}))

    lead, report, sim = await team("A", budget=10)
    records.append(team_record("shift budget spent before the restart", "A", lead, report, sim, {
        "stopped at the budget": report["team"]["budget"]["used"] == 10, "no effect": effects(sim) == 0,
        "honest handover": report["status"] == "needs_operator" and "budget spent" in report["next_step"]}))

    records.append({"part": "handoff", "run": "comparison under one shift budget", "budget_calls": SHIFT_CALLS,
                    "costs": COSTS, "rows": rows, "checks": {
                        "same outcome in A": [row["status"] for row in rows if row["case"] == "A"]
                        == ["recovered", "recovered"],
                        "same outcome in D": [row["status"] for row in rows if row["case"] == "D"]
                        == ["needs_operator", "needs_operator"],
                        "each run within the budget": all(row["tool_calls"] <= SHIFT_CALLS for row in rows),
                        "at most one effect per run": all(row["effects"] <= 1 for row in rows)}})
    return records


def passed(record):
    if record.get("control") == "naive":
        return not all(record["checks"].values())
    return all(record["checks"].values())


def brief(record):
    verdict = "PASS" if passed(record) else "FAIL"
    if record.get("control") == "naive":
        verdict += " (naive control: its checks fail as expected)"
    if "rows" in record:
        detail = "; ".join(f"{row['case']} {row['agent']}: {row['status']}, {row['tool_calls']} calls, "
                           f"{row['effects']} effect(s)" for row in record["rows"])
    elif record["part"] == "handoff":
        detail = (f"{record['status']}, {record['tool_calls']} calls {record['by_role']}, "
                  f"{record['effects']} effect(s), follow-up {'used' if record['follow_up_used'] else 'unused'}")
    elif "replacement" in record:
        replacement = record["replacement"]
        detail = (f"stopped {record['stopped']['point'] if record['stopped'] else '-'}; replacement "
                  f"{replacement['resume'].get('outcome')} -> {replacement['status']}, {record['effects']} effect(s)")
    else:
        detail = f"{record['effects']} effect(s)"
    return f"{verdict:4} {record['part']:7} {record.get('case', '-'):2} {record['run']}: {detail}"


async def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--part", choices=("handoff", "resume"), help="Run one part only.")
    parser.add_argument("--summary", action="store_true", help="Print one readable line per run instead of JSON.")
    args = parser.parse_args(argv)
    records = []
    if args.part in (None, "handoff"):
        records += await handoff_runs()
    if args.part in (None, "resume"):
        from resume_demo import resume_runs  # #19, which builds on this module
        records += await resume_runs()
    for record in records:
        print(brief(record) if args.summary else json.dumps(record, sort_keys=True, ensure_ascii=False))
    failed = [record["run"] for record in records if not passed(record)]
    if failed:
        print(f"FAILED: {failed}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
