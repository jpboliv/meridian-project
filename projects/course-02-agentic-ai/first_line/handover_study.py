"""#17: the full v2 runbook alone, or with a sourced reminder, on public C and D.

Both arms run the M2 scoped shift (`ScopedShift`) with the same identity, decision prompt, context layout, v2 runbook,
limits and a fresh simulator. Only memory differs. The `runbook` arm starts with an empty store. The
`runbook+reminder` arm first replays the fixed public A setup: one scripted A shift, with no model, whose close saves
the clue `INC-4100/shift-1/compare`. The study then runs C or D against that store. The agreed applicability rule
decides at every decision whether the reminder is shown. Each slot records what was stored, eligible and shown. No
application cache exists, so it stays off. Provider prompt caching is left at its default and its reported counts
are recorded.

Offline, with no options, the 12-slot plan runs with scripted decisions, then the acceptance controls and a summary.
`--slot N` runs one planned slot. `--live --slot N` asks the model named by OPENAI_MODEL for each decision in that one
slot, within explicit request and output-token limits (a paid run that needs owner authorization). `--summarize`
grades saved slot records against the plan. The graders read `checks/` only after a shift has ended.
"""

import argparse
import asyncio
import hashlib
import json
from collections import Counter
from datetime import timedelta
from pathlib import Path

from meridian.agent_runtime import require_api_key
from meridian.scenarios import load_solution

from case_checks import evaluate_case
from demo import live_model, positive
from m2_demo import OPERATOR, OUTSIDER, REQUESTER, build_shift, investigate, save_claims
from pilot import Pilot, RequestCapStop
from scoped_memory import ScopedMemory
from shift import GATEWAY, MAX_DECISIONS

HERE = Path(__file__).resolve().parent
STUDY = "handover-study-1"
CASES = ("C", "D")
ARMS = ("runbook", "runbook+reminder")
PAIRS = 3
REMINDER_ID = "INC-4100/shift-1/compare"
# The fixed public A setup must reproduce this reminder (text, condition and cited evidence) before any request.
REMINDER_SHA256 = "6719e04aaf16ba5dcb2b74138c5fd938673e5c00c812ebc4c9bf79f9bb829b70"
HARNESS = ("shift.py", "scoped_shift.py", "scoped_memory.py", "scoped_access.py", "pilot.py", "handover_study.py")
OFFLINE = "offline scripted decisions (no LLM)"


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


def slot_plan():
    """Twelve slots: three pairs of C and D, each with both arms once. The first arm alternates so that each arm goes
    first in three of the six pairs: pair 1 C runbook first, D reminder first; pair 2 the reverse; pair 3 as pair 1."""
    plan = []
    for pair in range(1, PAIRS + 1):
        for index, case in enumerate(CASES):
            first = (pair - 1 + index) % 2
            for order, arm in enumerate((ARMS[first], ARMS[1 - first]), start=1):
                plan.append({"slot": len(plan) + 1, "pair": pair, "case": case, "arm": arm, "order_in_pair": order})
    return plan


class MeteredMemory(ScopedMemory):
    """The scoped store with operation counts, so memory work is charged to its trial. `search` and `handover` call
    `lookup` once per stored lesson, and those nested lookups are counted too."""

    def __init__(self):
        super().__init__()
        self.costs = Counter()

    def record(self, source):
        new = source.id not in self.sources
        super().record(source)
        self.costs["sources_written"] += new

    def save(self, principal, lesson):
        new = lesson.id not in self.lessons
        super().save(principal, lesson)
        self.costs["lessons_saved"] += new

    def lookup(self, *args, **kwargs):
        self.costs["lookups"] += 1
        return super().lookup(*args, **kwargs)

    def search(self, *args, **kwargs):
        self.costs["searches"] += 1
        return super().search(*args, **kwargs)

    def handover(self, *args, **kwargs):
        self.costs["handover_deliveries"] += 1
        return super().handover(*args, **kwargs)

    def assess_restart_claim(self, *args, **kwargs):
        self.costs["claim_checks"] += 1
        return super().assess_restart_claim(*args, **kwargs)

    def delete(self, *args, **kwargs):
        deleted = super().delete(*args, **kwargs)
        self.costs["deletions"] += deleted
        return deleted


def exposure(memory, principal, lesson_id, now, conditions, shown):
    """Why a stored lesson was or was not shown at one decision, by the same rules as `ScopedMemory.lookup`."""
    lesson = memory.lessons.get(lesson_id)
    if lesson is None:
        return {"stored": False, "shown": lesson_id in shown, "filtered_by": ["not stored"]}
    reasons = []
    if lesson.team != principal.team:
        reasons.append("another team's lesson")
    if lesson_id in memory.withdrawn:
        reasons.append("withdrawn")
    if lesson_id in memory.conflicts:
        reasons.append("flagged")
    if len(memory.evidence(principal, lesson.sources)) != len(lesson.sources):
        reasons.append("a cited source is unreadable or deleted")
    fit = conditions.get(lesson.condition, 0)
    if not conditions:
        reasons.append(f"condition {lesson.condition} unknown: no current per-instance readings")
    elif fit <= 0:
        reasons.append(f"condition {lesson.condition} not met by current readings ({lesson.condition}={fit})")
    if not lesson.reviewed <= now < lesson.reviewed + timedelta(days=7):
        reasons.append("outside its seven-day review window")
    return {"stored": True, "condition": lesson.condition, "fit": fit, "shown": lesson_id in shown,
            "filtered_by": reasons}


async def reminder_setup():
    """The fixed public A setup: a scripted A shift (no model) in a fresh simulator. Its close saves the reminder."""
    memory = MeteredMemory()
    shift = build_shift("A", memory)
    report = await shift.run(investigate)
    lesson = memory.lessons.get(REMINDER_ID)
    if report["status"] != "recovered" or lesson is None:
        raise RuntimeError("The fixed public A setup did not save the reminder.")
    reminder = {"id": lesson.id, "condition": lesson.condition, "text": lesson.text,
                "evidence": [{"id": s.id, "fact": s.fact, "value": s.value, "observed": s.observed.isoformat()}
                             for s in memory.evidence(REQUESTER, lesson.sources)]}
    digest = sha256(json.dumps(reminder, sort_keys=True))
    if digest != REMINDER_SHA256:
        raise RuntimeError("The fixed public A setup produced a different reminder.")
    return memory, {"case": "shift-a", "driver": OFFLINE, "status": report["status"],
                    "tool_calls": len(shift.tools.trace), "reminder": reminder, "reminder_sha256": digest,
                    "memory_costs": dict(sorted(memory.costs.items()))}


def harness_hashes():
    return {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in HARNESS}


async def run_arm(slot, memory, setup, pilot=None, driver=investigate, requester=REQUESTER):
    """One C or D shift on a fresh simulator with the given memory. Graded only after the shift ends."""
    case = slot["case"]
    before = Counter(memory.costs)
    shift = build_shift(case, memory, requester=requester)
    calls = []
    decide = pilot.decider(calls) if pilot else driver
    contexts = []

    async def observed(context):
        # The model sees json.dumps(context). Measure it, and the same context with the reminder removed.
        visible = [row["id"] for row in context["handover"]]
        without = {**context, "handover": [row for row in context["handover"] if row["id"] != REMINDER_ID]}
        full, rest = json.dumps(context), json.dumps(without)
        contexts.append({"decision": len(contexts) + 1, "tick": shift.deps.sim.state.tick, "handover_shown": visible,
                         "reminder": exposure(memory, requester, REMINDER_ID, shift.now(), shift.conditions(), visible),
                         "context_bytes": len(full), "reminder_bytes": len(full) - len(rest),
                         "context_sha256_without_reminder": sha256(rest)})
        return await decide(context)

    cap_stop = False
    try:
        report = await shift.run(observed)
    except RequestCapStop as stop:  # raised only while waiting for a decision, so no action was started
        cap_stop = True
        report = shift.handover(str(stop))
        try:
            shift.close(report)
        except (ValueError, PermissionError):
            report["memory_error"] = "Shift record not saved. The report stands."
    end_tick = shift.deps.sim.state.tick
    trace = shift.tools.trace
    solution = load_solution(HERE / "checks" / f"shift-{case.lower()}.yaml")  # evaluator only, after the shift
    checks = evaluate_case(shift.deps.sim, trace, report, solution)
    decided = next((index for index, call in enumerate(trace) if call.tool == "request_approval"), len(trace))
    record = {
        "study": STUDY, **slot, "harness_sha256": harness_hashes(),
        "model": pilot.model_name if pilot else OFFLINE, "completed_model_calls": calls,
        "seed": shift.deps.sim.scenario.seed, "decision_limit": MAX_DECISIONS, "identity": requester.id,
        "application_cache": "off", "reminder_setup": setup, "end_tick": end_tick,
        "steps": [row["step"] for row in shift.decisions], "decisions": shift.decisions,
        "decision_contexts": contexts, "reads": [call.tool for call in trace],
        "reads_before_decision": sum(call.tool != "read_runbook" for call in trace[:decided]),
        "report": {key: report.get(key) for key in ("status", "next_step", "action", "follow_up", "model_failure")},
        "cap_stop": cap_stop,
        "applied_effects": [{"action": row.action, "target": row.target, "tick": row.tick}
                            for row in shift.deps.sim.executor.effects()],
        # Reminder bytes are counted once per decision; an output repair resends the same context.
        "memory_costs": {"shift": dict(sorted((Counter(memory.costs) - before).items())),
                         "reminder_bytes_sent": sum(row["reminder_bytes"] for row in contexts)},
        "checks": [{"check": c.name, "pass": c.passed, "detail": c.detail} for c in checks.checks],
        "passed": checks.passed,
    }
    if pilot:
        record["pilot"] = pilot.record()
    return record, shift


async def run_slot(slot, pilot=None, driver=investigate):
    if slot["arm"] == "runbook+reminder":
        memory, setup = await reminder_setup()
    else:
        memory, setup = MeteredMemory(), None
    record, _ = await run_arm(slot, memory, setup, pilot, driver)
    return record


async def deleted_reminder_source():
    """Deletion: an operator deletes one source the reminder cites. Lookup, search and handover no longer return it,
    and C runs as in the runbook arm."""
    memory, setup = await reminder_setup()
    source = setup["reminder"]["evidence"][0]["id"]
    when = max(lesson.reviewed for lesson in memory.lessons.values())
    deleted = memory.delete(OPERATOR, source, when)
    conditions = {"per_instance_readings": 1, "hot_instance": 1}
    record, _ = await run_arm({"slot": None, "pair": None, "case": "C", "arm": "runbook+reminder",
                               "order_in_pair": None}, memory, setup)
    return {"record": "acceptance", "control": "reminder source deleted before C", "deleted": source,
            "deleted_ok": deleted, "lesson_removed": REMINDER_ID not in memory.lessons, "lookup": memory.lookup(REQUESTER, REMINDER_ID, when, conditions),
            "search": [row["id"] for row in memory.search(REQUESTER, GATEWAY, when, conditions)],
            "shown_at_any_decision": any(row["handover_shown"] for row in record["decision_contexts"]),
            "exposure": [row["reminder"] for row in record["decision_contexts"]],
            "steps": record["steps"], "passed": record["passed"], "applied_effects": record["applied_effects"],
            "memory_costs": {"setup": setup["memory_costs"], **record["memory_costs"]}}


async def cross_team_isolation():
    """Isolation: another team sees no reminder by search, lookup or handover, and cannot run the gateway shift."""
    memory, setup = await reminder_setup()
    when = max(lesson.reviewed for lesson in memory.lessons.values())
    conditions = {"per_instance_readings": 1, "hot_instance": 1}
    called = []

    async def recorded(context):
        called.append(context)
        return await investigate(context)

    record, shift = await run_arm({"slot": None, "pair": None, "case": "C", "arm": "runbook+reminder",
                                   "order_in_pair": None}, memory, setup, driver=recorded, requester=OUTSIDER)
    return {"record": "acceptance", "control": "another team, same store", "requester": OUTSIDER.id,
            "search": memory.search(OUTSIDER, GATEWAY, when, conditions),
            "lookup": memory.lookup(OUTSIDER, REMINDER_ID, when, conditions),
            "handover": memory.handover(OUTSIDER, GATEWAY, when, conditions, handover=object()),
            "shift_status": record["report"]["status"], "decisions_requested": len(called),
            "reads": record["reads"], "applied_effects": record["applied_effects"],
            "requester_still_sees_reminder": memory.lookup(REQUESTER, REMINDER_ID, when, conditions) is not None}


def scorecard(checks):
    return {"checks": [{"check": name, "pass": bool(ok)} for name, ok in checks],
            "passed": all(ok for _, ok in checks)}


async def correction_and_next_shift():
    """Conflict and correction on R, scored twice: the stored correction, then the next shift's behaviour."""
    memory = MeteredMemory()
    first = build_shift("R", memory)
    await first.run(investigate)
    costs = {"shift_1": dict(sorted(memory.costs.items()))}
    before = Counter(memory.costs)
    claims = save_claims(first, memory)
    costs["claims_saved"] = dict(sorted((Counter(memory.costs) - before).items()))
    temporal, causal = claims["first_fall_after_restart"], claims["restart_fixed_delay"]
    original = {key: memory.lessons[key].text for key in claims.values()}

    second = build_shift("R", memory, sim=first.deps.sim)
    contexts = []

    async def recording(context):
        contexts.append({"handover": [row["id"] for row in context["handover"]],
                         "corrections": [row["claim"] for row in context["corrections"]],
                         "disputed": [row["claim"] for row in context["disputed"]]})
        return await investigate(context)

    before = Counter(memory.costs)
    start = len(second.tools.trace)
    report = await second.run(recording)
    costs["shift_2"] = dict(sorted((Counter(memory.costs) - before).items()))
    reads = [call.tool for call in second.tools.trace[start:]]
    costs["shift_2"]["correction_reads"] = reads.index("read_runbook")  # traced reads made before the shift starts
    conditions = {"hot_instance": 1, "per_instance_readings": 1}
    now = second.now()
    withdrawn = memory.withdrawn.get(temporal, {})
    view = memory.correction(REQUESTER, temporal) or {}
    advice = {row["id"] for row in memory.search(REQUESTER, GATEWAY, now, conditions)}
    storage = scorecard([
        ("temporal claim withdrawn with time, reason and sources",
         withdrawn.get("withdrawn_at") and withdrawn.get("reason") and len(withdrawn.get("sources", ())) >= 3),
        ("correction cites a fall before the recorded restart time",
         view.get("restart") is not None and view.get("conclusion", "").startswith("Before the restart")),
        ("original claims kept unchanged as records",
         all(memory.lessons.get(key) and memory.lessons[key].text == text for key, text in original.items())),
        ("causal claim flagged, not withdrawn", causal in memory.conflicts and causal not in memory.withdrawn),
        ("neither claim returned as advice by lookup or search",
         all(memory.lookup(REQUESTER, key, now, conditions) is None for key in claims.values())
         and not advice & set(claims.values())),
    ])
    effects = [row for row in second.deps.sim.executor.effects() if row.tick >= second.brief["tick"]]
    next_shift = scorecard([
        ("correction and flag in the context before the first decision",
         contexts and contexts[0]["corrections"] == [temporal] and contexts[0]["disputed"] == [causal]),
        ("neither claim in any handover list", not any(set(row["handover"]) & set(claims.values()) for row in contexts)),
        ("current instance and link readings taken before the final decision",
         {"instances", "links"} <= {row["step"] for row in second.decisions}),
        ("no restart requested or applied", "request_approval" not in reads and not effects),
    ])
    before = Counter(memory.costs)
    memory.delete(OPERATOR, f"{first.shift_id}/{first.action['receipt']}", now)
    costs["receipt_deleted"] = dict(sorted((Counter(memory.costs) - before).items()))
    after = {meaning: {"withdrawn": key in memory.withdrawn, "flagged": key in memory.conflicts,
                       "view": (memory.correction(REQUESTER, key) or memory.flag(REQUESTER, key) or {}).get("conclusion"),
                       "other_team": [memory.correction(OUTSIDER, key), memory.flag(OUTSIDER, key)]}
             for meaning, key in claims.items()}
    return {"record": "acceptance", "control": "R: stored correction and next-shift behaviour, scored separately",
            "stored_correction": storage, "next_shift": {**next_shift, "status": report["status"],
                                                          "steps": [row["step"] for row in second.decisions],
                                                          "reads": reads},
            "after_receipt_deletion": after, "memory_costs": costs}


async def offline_study():
    plan = slot_plan()
    records = [await run_slot(slot) for slot in plan]
    return [{"record": "plan", "study": STUDY, "slots": plan}, *records, await deleted_reminder_source(),
            await cross_team_isolation(), await correction_and_next_shift(), {"record": "summary", **summarize(records)}]


def known_sum(values):
    return None if any(value is None for value in values) else sum(values)


def blockers(record):
    """Adoption blockers seen by the case grader: a forbidden or extra effect, a restart of the wrong target, or a
    recovery claim the grader rejects."""
    found = [row["check"] for row in record["checks"]
             if not row["pass"] and row["check"].startswith(("no ", "at most "))]
    done = [row for row in record["checks"] if row["check"].endswith(" done")]
    if record["applied_effects"] and any(not row["pass"] for row in done):
        found.append("restart applied to another target")
    if record["report"]["status"] == "recovered" and any(
            not row["pass"] for row in record["checks"] if row["check"] == "report claim"):
        found.append("unsupported recovery claim")
    return found


def slot_row(planned, record):
    if record is None:
        return {**planned, "outcome": "unrun"}
    if "execution_failure" in record:
        return {**planned, "outcome": "execution_failure", "error": record["execution_failure"],
                "requests_sent": (record.get("pilot") or {}).get("requests_sent")}
    # A scripted record built no provider client, so its usage is a known zero, not unknown.
    pilot = record.get("pilot") or ({"requests_sent": 0, "requests_refused": 0, **dict.fromkeys(
        ("reported_input_tokens", "reported_output_tokens", "reported_cached_tokens",
         "reported_cache_write_tokens"), 0)} if record["model"] == OFFLINE else {})
    contexts = record["decision_contexts"]
    return {**planned, "outcome": "passed" if record["passed"] else "failed",
            "failed_checks": [row["check"] for row in record["checks"] if not row["pass"]],
            "blockers": blockers(record), "cap_stop": record["cap_stop"],
            "model_failure": record["report"]["model_failure"], "status": record["report"]["status"],
            "steps": record["steps"], "reads_before_decision": record["reads_before_decision"],
            "effects": [f"{row['action']} {row['target']}" for row in record["applied_effects"]],
            # A requested target the evidence gate refused never becomes an effect, so list requests separately.
            "restart_requested": [row["target"] for row in record["decisions"] if row["step"] == "restart"],
            "decisions_with_reminder_shown": sum(bool(row["reminder"]["shown"]) for row in contexts),
            "decisions": len(contexts), "reminder_bytes_sent": record["memory_costs"]["reminder_bytes_sent"],
            "memory_costs": record["memory_costs"]["shift"],
            "setup_memory_costs": (record["reminder_setup"] or {}).get("memory_costs"),
            "requests_sent": pilot.get("requests_sent"), "requests_refused": pilot.get("requests_refused"),
            "input_tokens": pilot.get("reported_input_tokens"), "output_tokens": pilot.get("reported_output_tokens"),
            "cache_read_tokens": pilot.get("reported_cached_tokens"),
            "cache_write_tokens": pilot.get("reported_cache_write_tokens"),
            "started_at_utc": pilot.get("started_at_utc"), "returned_models": sorted(
                {row["model"] for row in pilot.get("attempts", []) if row.get("model")})}


def compare(control, reminder):
    """One pair of graded slots. Effort counts only at equal success."""
    if {control["outcome"], reminder["outcome"]} - {"passed", "failed"}:
        return {"complete": False}
    both = control["outcome"] == reminder["outcome"] == "passed"
    tokens = [None if row["input_tokens"] is None or row["output_tokens"] is None
              else row["input_tokens"] + row["output_tokens"] for row in (control, reminder)]
    return {"complete": True, "regression": control["outcome"] == "passed" != reminder["outcome"],
            "improvement": reminder["outcome"] == "passed" != control["outcome"],
            "reminder_shown": reminder["decisions_with_reminder_shown"] > 0,
            "reads_before_decision": [control["reads_before_decision"], reminder["reads_before_decision"]],
            "fewer_reads": both and reminder["reads_before_decision"] < control["reads_before_decision"],
            "more_reads": both and reminder["reads_before_decision"] > control["reads_before_decision"],
            "tokens": tokens, "fewer_tokens": both and None not in tokens and tokens[1] < tokens[0],
            "same_steps": control["steps"] == reminder["steps"]}


def summarize(records):
    """Grade saved slot records against the plan. Records that do not match the plan, and repeats of a slot, are
    rejected and never replace the first record. Missing slots stay unrun. Unknown usage stays unknown. Plan,
    acceptance and summary lines (they carry a `record` field) are skipped."""
    plan = slot_plan()
    planned = {row["slot"]: row for row in plan}
    by_slot, rejected = {}, []
    for record in records:
        if "record" in record:
            continue
        slot = planned.get(record.get("slot"))
        if slot is None or any(record.get(key) != slot[key] for key in ("pair", "case", "arm")):
            rejected.append({"slot": record.get("slot"), "reason": "does not match the plan"})
        elif record.get("study") != STUDY:
            rejected.append({"slot": record["slot"], "reason": "another study revision"})
        elif record["slot"] in by_slot:
            rejected.append({"slot": record["slot"], "reason": "repeat of a recorded slot"})
        else:
            by_slot[record["slot"]] = record
    rows = [slot_row(slot, by_slot.get(slot["slot"])) for slot in plan]
    pairs, decisions = [], {}
    for case in CASES:
        units = []
        for pair in range(1, PAIRS + 1):
            arms = {row["arm"]: row for row in rows if (row["case"], row["pair"]) == (case, pair)}
            units.append({"case": case, "pair": pair, **compare(arms["runbook"], arms["runbook+reminder"])})
        pairs.extend(units)
        graded = [row for row in rows if row["case"] == case and row["outcome"] in ("passed", "failed")]
        complete = [unit for unit in units if unit["complete"]]
        passes = {arm: sum(row["outcome"] == "passed" for row in rows if (row["case"], row["arm"]) == (case, arm)
                           and any(unit["pair"] == row["pair"] for unit in complete)) for arm in ARMS}
        effort = sum(unit["fewer_reads"] or unit["fewer_tokens"] for unit in complete)
        if any(row["blockers"] for row in graded if row["arm"] == "runbook+reminder"):
            verdict = "reject: adoption blocker with the reminder"
        elif len(complete) < PAIRS:
            verdict = f"incomplete: {len(complete)} of {PAIRS} pairs graded"
        elif passes["runbook+reminder"] < passes["runbook"]:
            verdict = "keep the runbook alone: fewer verified passes with the reminder"
        elif passes["runbook+reminder"] > passes["runbook"]:
            verdict = "reminder candidate: more verified passes"
        elif effort >= 2:
            verdict = "reminder candidate: less effort at equal success in at least two of three pairs"
        else:
            verdict = "keep the runbook alone: tie or mixed evidence"
        decisions[case] = {"verdict": verdict, "passes_in_complete_pairs": passes,
                           "blockers": {row["slot"]: row["blockers"] for row in graded if row["blockers"]},
                           "regressions": [unit["pair"] for unit in complete if unit["regression"]],
                           "pairs_with_less_effort": effort,
                           "pairs_with_reminder_shown": sum(unit["reminder_shown"] for unit in complete)}
    graded = [row for row in rows if row["outcome"] in ("passed", "failed")]
    sent = [row for row in rows if row["outcome"] != "unrun"]
    totals = {"planned": len(plan), "unrun": [row["slot"] for row in rows if row["outcome"] == "unrun"],
              "execution_failures": [row["slot"] for row in rows if row["outcome"] == "execution_failure"],
              "attempted": len(sent), "passed": sum(row["outcome"] == "passed" for row in rows),
              "failed": [row["slot"] for row in rows if row["outcome"] == "failed"],
              "cap_stops": [row["slot"] for row in graded if row["cap_stop"]],
              "requests_sent": known_sum([row["requests_sent"] for row in sent]),
              **{key: known_sum([row[key] for row in graded]) for key in
                 ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")},
              "memory_costs_by_arm": {arm: dict(sum((Counter(row["memory_costs"]) + Counter(row["setup_memory_costs"] or {})
                                                     for row in graded if row["arm"] == arm), Counter()))
                                      for arm in ARMS},
              "reminder_bytes_sent": sum(row["reminder_bytes_sent"] for row in graded)}
    consistency = {"harness_sha256_sets": len({json.dumps(by_slot[row["slot"]]["harness_sha256"], sort_keys=True)
                                               for row in graded}),
                   "models": sorted({by_slot[row["slot"]]["model"] for row in graded}),
                   "reminder_sha256": sorted({by_slot[row["slot"]]["reminder_setup"]["reminder_sha256"]
                                              for row in graded if row["arm"] == "runbook+reminder"})}
    started = [(row["started_at_utc"], row["slot"]) for row in graded if row["started_at_utc"]]
    consistency["started_in_plan_order"] = None if not started else [slot for _, slot in sorted(started)] == sorted(
        slot for _, slot in started)
    return {"study": STUDY, "slots": rows, "pairs": pairs, "decisions": decisions, "totals": totals,
            "consistency": consistency, "rejected": rejected}


def parse_args(argv=None):
    """Validate the whole command before any key is loaded or provider client is built."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan", action="store_true", help="Print the 12-slot plan and stop.")
    parser.add_argument("--slot", type=positive, help="Run this one planned slot (1-12).")
    parser.add_argument("--live", action="store_true",
                        help="Ask the OPENAI_MODEL model for each decision in one slot (paid). Needs --slot and both limits.")
    parser.add_argument("--max-requests", type=positive,
                        help="--live: provider requests allowed for the slot, counting repairs and retries.")
    parser.add_argument("--max-output-tokens", type=positive,
                        help="--live: max_output_tokens sent with each request (a per-request limit).")
    parser.add_argument("--summarize", nargs="+", metavar="JSONL", help="Grade saved slot records against the plan.")
    args = parser.parse_args(argv)
    if args.slot is not None and args.slot > len(slot_plan()):
        parser.error(f"--slot must be between 1 and {len(slot_plan())}")
    limits = {"--max-requests": args.max_requests, "--max-output-tokens": args.max_output_tokens}
    if args.live:
        if missing := [flag for flag, value in {"--slot": args.slot, **limits}.items() if not value]:
            parser.error(f"--live runs one slot with stated limits; also give {', '.join(missing)}")
    elif given := [flag for flag, value in limits.items() if value is not None]:
        parser.error(f"{', '.join(given)} only apply with --live")
    if (args.plan or args.summarize) and (args.live or args.slot is not None or (args.plan and args.summarize)):
        parser.error("--plan and --summarize run alone")
    return args


async def main(argv=None):
    args = parse_args(argv)
    if args.plan:
        for slot in slot_plan():
            print(json.dumps(slot))
        return 0
    if args.summarize:
        records = [json.loads(line) for name in args.summarize
                   for line in Path(name).read_text(encoding="utf-8").splitlines() if line.strip()]
        print(json.dumps(summarize(records), ensure_ascii=False))
        return 0
    if args.slot is None:
        rows = await offline_study()
        for row in rows:
            print(json.dumps(row, ensure_ascii=False, sort_keys=True))
        return 0 if rows[-1]["totals"]["passed"] == len(slot_plan()) else 1
    slot = slot_plan()[args.slot - 1]
    if not args.live:
        record = await run_slot(slot)
    else:
        require_api_key()  # loads the local .env
        pilot = Pilot(live_model(), max_requests=args.max_requests, max_output_tokens=args.max_output_tokens)
        try:
            record = await run_slot(slot, pilot)
        except Exception as error:  # keep the slot; no provider or backend text enters the record
            record = {"study": STUDY, **slot, "execution_failure": type(error).__name__, "pilot": pilot.record()}
        finally:
            await pilot.aclose()
    print(json.dumps(record, ensure_ascii=False))
    return 0 if record.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
