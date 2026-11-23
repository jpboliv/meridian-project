"""#17: the full v2 runbook alone, or with a sourced reminder, on public C and D.

Both arms run the M2 scoped shift (`ScopedShift`) with the same identity, decision prompt, context layout, v2 runbook,
limits and a fresh simulator. Only memory differs. The `runbook` arm starts with an empty store. The
`runbook+reminder` arm first replays the fixed public A setup: one scripted A shift, with no model, whose close saves
the clue `INC-4100/shift-1/compare`. The study then runs C or D against that store. The agreed applicability rule
decides at every decision whether the reminder is shown. Each slot records what was stored, eligible and shown. No
application cache exists, so it stays off. Provider prompt caching is left at its default and its reported counts
are recorded.

Offline, with no options, the 12-slot plan runs with scripted decisions, then the acceptance controls and a summary.
`--slot N` runs one planned slot. `--freeze-protocol` starts a live ledger with the expected model, limits, harness and
reminder hashes. `--live --slot N` asks the model named by OPENAI_MODEL for each decision in that one slot, within
explicit request and output-token limits (a paid run that needs owner authorization), and appends its start and end
records to the ledger. `--summarize` grades the ledger against its protocol and plan; scripted records stay a separate
harness control. The graders read `checks/` only after a shift has ended.
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
import uuid
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
    except BaseException as error:  # a failure or interruption keeps what the shift did and showed so far
        error.partial = {"decision_contexts": contexts, "steps": [row["step"] for row in shift.decisions],
                         "reads": [call.tool for call in shift.tools.trace],
                         "applied_effects": [{"action": row.action, "target": row.target, "tick": row.tick}
                                             for row in shift.deps.sim.executor.effects()]}
        raise
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


# Draft until the owner decides (#8). Token counts are a usage proxy: the summary never prices them.
RULE = ("Draft #17 effort and adoption rule, not agreed; it needs an owner decision. Only a complete comparable pair "
        "in which the reminder was eligible and shown can credit the reminder. A pair without exposure is a control "
        "only. A reminder shown while ineligible is an adoption blocker, graded or not.")
UNITS = ("Provider-reported token and request counts: a usage proxy, not dollars. A metric is unknown if any request "
         "behind it lacks a report. Spending is estimated separately, at owner-approved rates.")
METRICS = {"input_tokens": "input_tokens", "output_tokens": "output_tokens", "cache_read_tokens": "cached_tokens",
           "cache_write_tokens": "cache_write_tokens"}  # summary name: per-request attempt field
PILOT_SETTINGS = {"api": "api", "configured_model": "model", "max_requests": "max_requests",
                  "max_output_tokens_per_request": "max_output_tokens_per_request", "sdk_retries": "sdk_retries",
                  "arm": "arm", "prompt_cache_options": "prompt_cache_options"}  # pilot field: protocol field
SKIPPED = ("plan", "acceptance", "summary")


def scenario_seeds():
    return {case: build_shift(case, MeteredMemory()).deps.sim.scenario.seed for case in CASES}


def frozen_protocol(model, max_requests, max_output_tokens):
    """What every live slot must match. Freezing it decides nothing: the owner still decides settings and spending."""
    return {"record": "protocol", "study": STUDY, "model": model, "api": "openai-responses",
            "max_requests": max_requests, "max_output_tokens_per_request": max_output_tokens, "sdk_retries": 0,
            "arm": None, "prompt_cache_options": None, "application_cache": "off", "seeds": scenario_seeds(),
            "decision_limit": MAX_DECISIONS, "identity": REQUESTER.id, "reminder_sha256": REMINDER_SHA256,
            "harness_sha256": harness_hashes(), "plan": slot_plan()}


def protocol_sha256(protocol):
    return sha256(json.dumps(protocol, sort_keys=True))


def returned_as(model, returned):
    """The provider may return the configured alias or a dated snapshot of it."""
    return returned == model or re.fullmatch(re.escape(model) + r"-\d{4}-\d{2}-\d{2}", returned) is not None


def is_scripted(record):
    return record.get("model") == OFFLINE and "pilot" not in record and "run_id" not in record


def mismatches(record, protocol):
    """Why a live start or end record is not evidence under the frozen protocol. Checked before its slot counts."""
    if protocol is None:
        return ["no single frozen protocol in the inputs"]
    found = [f"{key} differs from the protocol" for key in ("study", "model", "harness_sha256")
             if record.get(key) != protocol[key]]
    if record.get("record") == "start":
        if record.get("protocol_sha256") != protocol_sha256(protocol):
            found.append("started under another protocol")
        return found
    pilot = record.get("pilot")
    if not isinstance(pilot, dict):
        return [*found, "no provider record"]
    found += [f"pilot {key} differs from the protocol" for key, name in PILOT_SETTINGS.items()
              if pilot.get(key) != protocol[name]]
    returned = {row.get("model") for row in pilot.get("attempts") or [] if row.get("status") == 200}
    if None in returned:
        found.append("a completed request did not report its model")
    if any(not returned_as(protocol["model"], model) for model in returned - {None}):
        found.append("returned model differs from the protocol")
    if len(returned - {None}) > 1:
        found.append("several returned models in one slot")
    if "execution_failure" in record or "interrupted" in record:
        return found
    found += [f"{key} differs from the protocol" for key in ("application_cache", "decision_limit", "identity")
              if record.get(key) != protocol[key]]
    if record.get("seed") != protocol["seeds"].get(record.get("case")):
        found.append("seed differs from the protocol")
    setup = record.get("reminder_setup")
    if record.get("arm") == "runbook+reminder":
        if (setup or {}).get("reminder_sha256") != protocol["reminder_sha256"]:
            found.append("reminder hash differs from the protocol")
    elif setup is not None:
        found.append("runbook arm carries a reminder setup")
    return found


def usage(record):
    """Usage per metric from every request the slot sent: decisions, repairs, failed and interrupted requests. A
    metric is unknown if any request lacks it. A scripted record built no client, so its usage is a known zero."""
    if record is not None and is_scripted(record):
        return {"requests_sent": 0, **dict.fromkeys(METRICS, 0)}
    pilot = (record or {}).get("pilot")
    attempts = pilot.get("attempts") if isinstance(pilot, dict) else None
    if not isinstance(attempts, list) or pilot.get("requests_sent") != len(attempts):
        return dict.fromkeys(("requests_sent", *METRICS))
    return {"requests_sent": len(attempts),
            **{name: known_sum([row.get(key) for row in attempts]) for name, key in METRICS.items()}}


def exposure_summary(record):
    """What memory each decision showed. The reminder counts as eligible exposure only when shown with no filter."""
    eligible, ineligible, other = 0, [], []
    for row in record.get("decision_contexts") or []:
        reminder, shown = row.get("reminder") or {}, row.get("handover_shown") or []
        if REMINDER_ID in shown or reminder.get("shown"):
            if reminder.get("filtered_by"):
                ineligible.append({"decision": row.get("decision"), "filtered_by": reminder["filtered_by"]})
            else:
                eligible += 1
        if extra := [lesson for lesson in shown if lesson != REMINDER_ID]:
            other.append({"decision": row.get("decision"), "shown": extra})
    return {"eligible": eligible, "ineligible": ineligible, "other": other}


def blockers(record):
    """Adoption blockers. Memory shown while ineligible (stale, another team's, filtered by its condition, or never
    stored), or any other memory shown, counts in every record that kept its contexts, graded or not. The case grader
    adds a forbidden or extra effect, a restart of the wrong target, or a recovery claim it rejects."""
    seen = exposure_summary(record)
    found = [f"reminder shown while ineligible at decision {row['decision']}: {'; '.join(row['filtered_by'])}"
             for row in seen["ineligible"]]
    found += [f"other memory shown at decision {row['decision']}: {', '.join(row['shown'])}" for row in seen["other"]]
    checks = record.get("checks") or []
    found += [row["check"] for row in checks if not row["pass"] and row["check"].startswith(("no ", "at most "))]
    done = [row for row in checks if row["check"].endswith(" done")]
    if record.get("applied_effects") and any(not row["pass"] for row in done):
        found.append("restart applied to another target")
    if (record.get("report") or {}).get("status") == "recovered" and any(
            not row["pass"] for row in checks if row["check"] == "report claim"):
        found.append("unsupported recovery claim")
    return found


def slot_row(planned, record, outcome, problems=()):
    if record is None:
        known = 0 if outcome == "unrun" else None  # no start record means nothing was sent
        return {**planned, "outcome": outcome, "problems": list(problems), "blockers": [],
                **{key: known for key in ("requests_sent", *METRICS)}}
    pilot = record.get("pilot") if isinstance(record.get("pilot"), dict) else {}
    report = record.get("report") or {}
    contexts = record.get("decision_contexts") or []
    seen = exposure_summary(record)
    return {**planned, "outcome": outcome, "problems": list(problems),
            "error": record.get("execution_failure") or record.get("interrupted"),
            "failed_checks": [row["check"] for row in record.get("checks") or [] if not row["pass"]],
            "blockers": blockers(record), "cap_stop": record.get("cap_stop"),
            "model_failure": report.get("model_failure"), "status": report.get("status"),
            "steps": record.get("steps"), "reads_before_decision": record.get("reads_before_decision"),
            "effects": [f"{row['action']} {row['target']}" for row in record.get("applied_effects") or []],
            # A requested target the evidence gate refused never becomes an effect, so list requests separately.
            "restart_requested": [row["target"] for row in record.get("decisions") or [] if row["step"] == "restart"],
            "decisions": len(contexts), "decisions_with_reminder_shown": seen["eligible"] + len(seen["ineligible"]),
            "decisions_with_eligible_reminder": seen["eligible"],
            "decisions_with_other_memory": len(seen["other"]),
            "reminder_bytes_sent": (record.get("memory_costs") or {}).get(
                "reminder_bytes_sent", sum(row.get("reminder_bytes", 0) for row in contexts)),
            "memory_costs": (record.get("memory_costs") or {}).get("shift"),
            "setup_memory_costs": (record.get("reminder_setup") or {}).get("memory_costs"),
            **usage(record), "requests_refused": pilot.get("requests_refused", 0 if is_scripted(record) else None),
            "started_at_utc": pilot.get("started_at_utc"), "returned_models": sorted(
                {row["model"] for row in pilot.get("attempts", []) if row.get("model")})}


def compare(control, reminder):
    """One pair. It is complete when both slots are graded, comparable when no memory reached the control and no
    other memory reached the reminder arm, and exposed when the reminder was eligible and shown at least once. Only
    a comparable exposed pair can credit the reminder; effort counts only at equal success."""
    if {control["outcome"], reminder["outcome"]} - {"passed", "failed"}:
        return {"complete": False, "comparable": False, "exposed": False}
    comparable = not (control["decisions_with_reminder_shown"] or control["decisions_with_other_memory"]
                      or reminder["decisions_with_other_memory"])
    exposed = reminder["decisions_with_eligible_reminder"] > 0
    credit = comparable and exposed and control["outcome"] == reminder["outcome"] == "passed"
    proxy = [None if row["input_tokens"] is None or row["output_tokens"] is None
             else row["input_tokens"] + row["output_tokens"] for row in (control, reminder)]
    return {"complete": True, "comparable": comparable, "exposed": exposed,
            "regression": control["outcome"] == "passed" != reminder["outcome"],
            "improvement": reminder["outcome"] == "passed" != control["outcome"],
            "reads_before_decision": [control["reads_before_decision"], reminder["reads_before_decision"]],
            "fewer_reads": credit and reminder["reads_before_decision"] < control["reads_before_decision"],
            "more_reads": comparable and control["outcome"] == reminder["outcome"] == "passed"
            and reminder["reads_before_decision"] > control["reads_before_decision"],
            "token_proxy": proxy, "fewer_tokens": credit and None not in proxy and proxy[1] < proxy[0],
            "same_steps": control["steps"] == reminder["steps"]}


def pair_units(rows, case):
    units = []
    for pair in range(1, PAIRS + 1):
        arms = {row["arm"]: row for row in rows if (row["case"], row["pair"]) == (case, pair)}
        units.append({"case": case, "pair": pair, **compare(arms["runbook"], arms["runbook+reminder"])})
    return units


def decide(case, rows, units, heterogeneous):
    """The Draft verdict for one case from accepted live slots only."""
    comparable = [unit for unit in units if unit["comparable"]]
    exposed = [unit for unit in comparable if unit["exposed"]]
    passes = {arm: sum(row["outcome"] == "passed" for row in rows if (row["case"], row["arm"]) == (case, arm)
                       and any(unit["pair"] == row["pair"] for unit in exposed)) for arm in ARMS}
    effort = sum(unit["fewer_reads"] or unit["fewer_tokens"] for unit in exposed)
    case_rows = [row for row in rows if row["case"] == case]
    if any(row["blockers"] for row in case_rows if row["arm"] == "runbook+reminder"):
        verdict = "reject: adoption blocker with the reminder"
    elif heterogeneous:
        verdict = f"invalid: heterogeneous evidence ({heterogeneous})"
    elif len(comparable) < PAIRS:
        verdict = f"incomplete: {len(comparable)} of {PAIRS} pairs complete and comparable"
    elif not exposed:
        verdict = "control only: the reminder was never eligible and shown, so differences are run-to-run variance"
    elif passes["runbook+reminder"] < passes["runbook"]:
        verdict = "keep the runbook alone: fewer verified passes where the reminder was shown"
    elif passes["runbook+reminder"] > passes["runbook"]:
        verdict = "reminder candidate: more verified passes where the reminder was shown"
    elif effort >= 2:
        verdict = "reminder candidate: less effort at equal success in at least two exposed pairs"
    else:
        verdict = f"keep the runbook alone: tie or mixed evidence ({len(exposed)} of {PAIRS} pairs exposed)"
    return {"verdict": verdict, "passes_in_exposed_pairs": passes,
            "blockers": {row["slot"]: row["blockers"] for row in case_rows if row["blockers"]},
            "regressions": [{"pair": unit["pair"], "reminder_shown": unit["exposed"]}
                            for unit in units if unit["complete"] and unit["regression"]],
            "pairs_comparable": len(comparable), "pairs_exposed": len(exposed), "pairs_with_less_effort": effort}


def scripted_control(records):
    """Scripted slots, kept apart from the live verdict: they show what the harness delivers, not model behaviour."""
    plan, by_slot, rejected = slot_plan(), {}, []
    for record in records:
        slot = next((row for row in plan if row["slot"] == record.get("slot")), None)
        if slot is None or any(record.get(key) != slot[key] for key in ("pair", "case", "arm")):
            rejected.append({"slot": record.get("slot"), "reason": "scripted record does not match the plan"})
        elif record["slot"] in by_slot:
            rejected.append({"slot": record["slot"], "reason": "repeat of a scripted slot"})
        else:
            by_slot[record["slot"]] = record
    rows = [slot_row(slot, by_slot.get(slot["slot"]), "unrun" if slot["slot"] not in by_slot else
                     "passed" if by_slot[slot["slot"]]["passed"] else "failed") for slot in plan]
    cases = {}
    for case in CASES:
        units = pair_units(rows, case)
        cases[case] = {"passes": {arm: sum(row["outcome"] == "passed" for row in rows
                                           if (row["case"], row["arm"]) == (case, arm)) for arm in ARMS},
                       "pairs_exposed": sum(unit["exposed"] for unit in units),
                       "pairs_with_fewer_reads": sum(unit.get("fewer_reads", False) for unit in units),
                       "pairs_with_same_steps": sum(unit.get("same_steps", False) for unit in units),
                       "blockers": {row["slot"]: row["blockers"] for row in rows if row["blockers"] and row["case"] == case}}
    return {"note": "scripted decisions (no LLM): a harness control, never live evidence", "records": len(by_slot),
            "passed": sum(row["outcome"] == "passed" for row in rows), "by_case": cases,
            "memory_costs_by_arm": {arm: dict(sum((Counter(row["memory_costs"]) + Counter(row["setup_memory_costs"] or {})
                                                   for row in rows if row["arm"] == arm and row["outcome"] != "unrun"),
                                                  Counter())) for arm in ARMS},
            "reminder_bytes_sent": sum(row.get("reminder_bytes_sent", 0) for row in rows), "rejected": rejected}


def summarize(records):
    """Grade a live ledger against its frozen protocol and plan.

    The first start record for a planned slot claims it, and the slot is never retried: a later start or end for it is
    rejected. A record counts as evidence only if its start and end both match the protocol (model, run mode, limits,
    harness and reminder hashes); otherwise the slot is `invalid`. A start with no end is `interrupted_without_end_record`
    with unknown usage. Failures and interruptions stay attempted, never unrun. Scripted records never enter the live
    verdict. Every live run in the inputs, accepted or not, is counted in `incurred`."""
    plan = slot_plan()
    planned = {row["slot"]: row for row in plan}
    protocols = {protocol_sha256(row): row for row in records if row.get("record") == "protocol"}
    protocol = next(iter(protocols.values())) if len(protocols) == 1 else None
    rejected = [{"reason": "several different frozen protocols"}] if len(protocols) > 1 else []
    starts, claimed, ends, scripted, loose = {}, {}, {}, [], []
    for record in records:
        kind = record.get("record")
        if kind in SKIPPED or kind == "protocol":
            continue
        if kind == "unreadable":
            rejected.append({"line": record.get("line"), "reason": "unreadable line"})
            continue
        if kind is None and is_scripted(record):
            scripted.append(record)
            continue
        slot = planned.get(record.get("slot"))
        run_id = record.get("run_id")
        if slot is None or any(record.get(key) != slot[key] for key in ("pair", "case", "arm")):
            rejected.append({"slot": record.get("slot"), "run_id": run_id, "reason": "does not match the plan"})
            if kind is None:
                loose.append(record)
        elif kind == "start":
            if run_id in starts:
                rejected.append({"slot": slot["slot"], "run_id": run_id, "reason": "duplicate start record"})
                continue
            starts[run_id] = record
            if slot["slot"] in claimed:
                rejected.append({"slot": slot["slot"], "run_id": run_id, "reason": "retry of an already started slot"})
            else:
                claimed[slot["slot"]] = run_id
        elif run_id not in starts:
            rejected.append({"slot": slot["slot"], "run_id": run_id, "reason": "live record without a start record"})
            loose.append(record)
        elif run_id in ends:
            rejected.append({"slot": slot["slot"], "run_id": run_id, "reason": "duplicate end record"})
        elif starts[run_id]["slot"] != slot["slot"]:
            rejected.append({"slot": slot["slot"], "run_id": run_id, "reason": "end record names another slot"})
            loose.append(record)
        else:
            ends[run_id] = record
            if claimed.get(slot["slot"]) != run_id:
                rejected.append({"slot": slot["slot"], "run_id": run_id, "reason": "retry of an already started slot"})
    rows = []
    for slot in plan:
        run_id = claimed.get(slot["slot"])
        record = ends.get(run_id)
        if run_id is None:
            rows.append(slot_row(slot, None, "unrun"))
            continue
        problems = list(dict.fromkeys(mismatches(starts[run_id], protocol) + (mismatches(record, protocol) if record else [])))
        outcome = ("interrupted_without_end_record" if record is None else "invalid" if problems
                   else "interrupted" if "interrupted" in record else "execution_failure" if "execution_failure" in record
                   else "passed" if record.get("passed") else "failed")
        rows.append({**slot_row(slot, record, outcome, problems), "run_id": run_id,
                     "started_at_utc": starts[run_id].get("started_at_utc")})
    graded = [row for row in rows if row["outcome"] in ("passed", "failed")]
    returned = sorted({model for row in graded for model in row["returned_models"]})
    heterogeneous = f"returned models {', '.join(returned)}" if len(returned) > 1 else ""
    pairs, decisions = [], {}
    for case in CASES:
        units = pair_units(rows, case)
        pairs.extend(units)
        decisions[case] = decide(case, rows, units, heterogeneous)
    attempted = [row for row in rows if row["outcome"] != "unrun"]
    totals = {"planned": len(plan), "unrun": [row["slot"] for row in rows if row["outcome"] == "unrun"],
              **{outcome: [row["slot"] for row in rows if row["outcome"] == outcome] for outcome in
                 ("invalid", "interrupted", "interrupted_without_end_record", "execution_failure", "failed")},
              "attempted": len(attempted), "passed": sum(row["outcome"] == "passed" for row in rows),
              "cap_stops": [row["slot"] for row in graded if row["cap_stop"]],
              **{key: known_sum([row[key] for row in attempted]) for key in ("requests_sent", *METRICS)},
              "memory_costs_by_arm": {arm: dict(sum((Counter(row["memory_costs"]) + Counter(row["setup_memory_costs"] or {})
                                                     for row in graded if row["arm"] == arm), Counter()))
                                      for arm in ARMS},
              "reminder_bytes_sent": sum(row["reminder_bytes_sent"] for row in graded)}
    # Every live run seen, including invalid, rejected and retried ones: a run with no end record has unknown usage.
    runs = [usage(ends.get(run_id)) for run_id in starts] + [usage(record) for record in loose]
    incurred = {"runs": len(runs), "runs_without_end_record": sorted(
                    starts[run_id]["slot"] for run_id in starts if run_id not in ends),
                **{key: known_sum([run[key] for run in runs]) for key in ("requests_sent", *METRICS)}}
    started = sorted((row["started_at_utc"], row["slot"]) for row in attempted if row.get("started_at_utc"))
    consistency = {"protocol_sha256": protocol_sha256(protocol) if protocol else None,
                   "protocol_model": protocol["model"] if protocol else None, "returned_models": returned,
                   "started_in_plan_order": None if not started else [slot for _, slot in started] == sorted(
                       slot for _, slot in started)}
    return {"study": STUDY, "rule": RULE, "units": UNITS, "slots": rows, "pairs": pairs, "decisions": decisions,
            "totals": totals, "incurred": incurred, "consistency": consistency, "rejected": rejected,
            "scripted_control": scripted_control(scripted)}


def read_ledger(path):
    """Ledger lines in order. A line that is not a JSON object is kept as `unreadable`, never skipped."""
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            row = None
        rows.append(row if isinstance(row, dict) else {"record": "unreadable", "line": number})
    return rows


def append(path, row):
    """Append one line and flush it to disk before going on."""
    with open(path, "a", encoding="utf-8") as ledger:
        ledger.write(json.dumps(row, ensure_ascii=False) + "\n")
        ledger.flush()
        os.fsync(ledger.fileno())


def preflight(path, slot, max_requests, max_output_tokens):
    """Before any key is loaded: the ledger starts with one frozen protocol that this code and these limits match,
    and this slot has never been started in it."""
    rows = read_ledger(path) if Path(path).exists() else []
    protocols = [row for row in rows if row.get("record") == "protocol"]
    if not rows or rows[0].get("record") != "protocol" or len(protocols) != 1:
        raise SystemExit("The ledger must start with one frozen protocol (--freeze-protocol). No key was loaded.")
    protocol, problems = protocols[0], []
    if protocol.get("study") != STUDY or protocol.get("plan") != slot_plan():
        problems.append("the protocol names another study revision or plan")
    if protocol.get("harness_sha256") != harness_hashes():
        problems.append("the harness differs from the frozen protocol")
    if protocol.get("reminder_sha256") != REMINDER_SHA256:
        problems.append("the reminder hash differs from the frozen protocol")
    if (protocol.get("max_requests"), protocol.get("max_output_tokens_per_request")) != (max_requests, max_output_tokens):
        problems.append("the limits differ from the frozen protocol")
    if any(row.get("record") == "unreadable" for row in rows):
        problems.append("the ledger has an unreadable line")
    if any(row.get("slot") == slot["slot"] for row in rows):
        problems.append(f"slot {slot['slot']} was already started in this ledger, and a started slot is never retried")
    if problems:
        raise SystemExit("Not started: " + "; ".join(problems) + ". No key was loaded and no request was sent.")
    return protocol


def parse_args(argv=None):
    """Validate the whole command before any key is loaded or provider client is built."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan", action="store_true", help="Print the 12-slot plan and stop.")
    parser.add_argument("--slot", type=positive, help="Run this one planned slot (1-12).")
    parser.add_argument("--live", action="store_true",
                        help="Ask the OPENAI_MODEL model for each decision in one slot (paid). Needs --slot, both "
                             "limits and --ledger.")
    parser.add_argument("--freeze-protocol", action="store_true",
                        help="Start a new ledger with the frozen protocol. Needs --model, both limits and --ledger.")
    parser.add_argument("--model", help="--freeze-protocol: the expected model name.")
    parser.add_argument("--ledger", help="--live or --freeze-protocol: the append-only JSONL ledger of the live study.")
    parser.add_argument("--max-requests", type=positive,
                        help="--live: provider requests allowed for the slot, counting repairs and retries.")
    parser.add_argument("--max-output-tokens", type=positive,
                        help="--live: max_output_tokens sent with each request (a per-request limit).")
    parser.add_argument("--summarize", nargs="+", metavar="JSONL", help="Grade a live ledger against its protocol.")
    args = parser.parse_args(argv)
    if args.slot is not None and args.slot > len(slot_plan()):
        parser.error(f"--slot must be between 1 and {len(slot_plan())}")
    limits = {"--max-requests": args.max_requests, "--max-output-tokens": args.max_output_tokens}
    if args.live and args.freeze_protocol:
        parser.error("--live and --freeze-protocol run alone")
    if args.live:
        if missing := [flag for flag, value in {"--slot": args.slot, **limits, "--ledger": args.ledger}.items()
                       if not value]:
            parser.error(f"--live runs one slot with stated limits and a ledger; also give {', '.join(missing)}")
    elif args.freeze_protocol:
        if missing := [flag for flag, value in {"--model": args.model, **limits, "--ledger": args.ledger}.items()
                       if not value]:
            parser.error(f"--freeze-protocol also needs {', '.join(missing)}")
        if args.slot is not None:
            parser.error("--freeze-protocol takes no --slot")
    elif given := [flag for flag, value in {**limits, "--ledger": args.ledger}.items() if value is not None]:
        parser.error(f"{', '.join(given)} only apply with --live or --freeze-protocol")
    if args.model is not None and not args.freeze_protocol:
        parser.error("--model only applies with --freeze-protocol; --live takes the model from OPENAI_MODEL")
    if (args.plan or args.summarize) and (args.live or args.freeze_protocol or args.slot is not None
                                          or (args.plan and args.summarize)):
        parser.error("--plan and --summarize run alone")
    return args


async def live_slot(args, slot):
    """One paid slot. Its start record reaches the ledger before the first request. A failure or interruption still
    writes an end record with every request sent and what the shift showed; an interruption is then re-raised."""
    protocol = preflight(args.ledger, slot, args.max_requests, args.max_output_tokens)
    require_api_key()  # loads the local .env
    model = live_model()
    if model != protocol["model"]:
        raise SystemExit("OPENAI_MODEL differs from the frozen protocol. No request was sent.")
    pilot = Pilot(model, max_requests=args.max_requests, max_output_tokens=args.max_output_tokens)
    run_id = uuid.uuid4().hex
    append(args.ledger, {"record": "start", "study": STUDY, **slot, "run_id": run_id, "model": model,
                         "protocol_sha256": protocol_sha256(protocol), "harness_sha256": harness_hashes(),
                         "started_at_utc": pilot.started_at})
    try:
        record = {**await run_slot(slot, pilot), "run_id": run_id}
    except BaseException as error:  # no provider or backend text enters the record
        record = {"study": STUDY, **slot, "run_id": run_id, "model": model, "harness_sha256": harness_hashes(),
                  **getattr(error, "partial", {}), "pilot": pilot.record(),
                  ("execution_failure" if isinstance(error, Exception) else "interrupted"): type(error).__name__}
        append(args.ledger, record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
        if not isinstance(error, Exception):
            raise
        return record
    finally:
        await pilot.aclose()
    append(args.ledger, record)
    print(json.dumps(record, ensure_ascii=False))
    return record


async def main(argv=None):
    args = parse_args(argv)
    if args.plan:
        for slot in slot_plan():
            print(json.dumps(slot))
        return 0
    if args.freeze_protocol:
        if Path(args.ledger).exists() and Path(args.ledger).read_text(encoding="utf-8").strip():
            raise SystemExit("The ledger already has records. Freeze a protocol only in a new ledger.")
        protocol = frozen_protocol(args.model, args.max_requests, args.max_output_tokens)
        append(args.ledger, protocol)
        print(json.dumps(protocol))
        return 0
    if args.summarize:
        records = [row for name in args.summarize for row in read_ledger(name)]
        print(json.dumps(summarize(records), ensure_ascii=False))
        return 0
    if args.slot is None:
        rows = await offline_study()
        for row in rows:
            print(json.dumps(row, ensure_ascii=False, sort_keys=True))
        return 0 if rows[-1]["scripted_control"]["passed"] == len(slot_plan()) else 1
    slot = slot_plan()[args.slot - 1]
    record = await live_slot(args, slot) if args.live else await run_slot(slot)
    if not args.live:
        print(json.dumps(record, ensure_ascii=False))
    return 0 if record.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
