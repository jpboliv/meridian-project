"""#17 handover study, offline: plan, reminder exposure, arm equivalence on the mock wire, the bounded one-slot CLI,
acceptance controls and the summary. No key, network or provider charge."""

import asyncio
import copy
import json

import pytest

import handover_study as study
from demo import scripted
from m2_demo import build_shift
from scoped_memory import ScopedMemory
from test_pilot import MODEL, FakeResponses, pilot_with, user_json

TRACE = study.HERE / "offline-study-m2.jsonl"
FIXED = {"C": [{"step": "instances"}, {"step": "tickets"}, {"step": "links"},
               {"step": "restart", "target": "order-gateway-1"}],
         "D": [{"step": "instances"}, {"step": "tickets"}, {"step": "links"},
               {"step": "handover", "target": "reference-db"}]}


def slot(case, arm):
    return next(row for row in study.slot_plan() if (row["case"], row["arm"]) == (case, arm))


def run(coroutine):
    return asyncio.run(coroutine)


def offline_records():
    return [json.loads(line) for line in TRACE.read_text(encoding="utf-8").splitlines()]


def test_plan_is_fixed_and_counterbalanced():
    plan = study.slot_plan()
    assert [row["slot"] for row in plan] == list(range(1, 13))
    units = {}
    for row in plan:
        units.setdefault((row["case"], row["pair"]), []).append(row["arm"])
    assert len(units) == 6 and all(sorted(arms) == sorted(study.ARMS) for arms in units.values())
    assert sum(arms[0] == "runbook" for arms in units.values()) == 3
    assert [(row["pair"], row["case"], row["arm"]) for row in plan[:4]] == [
        (1, "C", "runbook"), (1, "C", "runbook+reminder"), (1, "D", "runbook+reminder"), (1, "D", "runbook")]


def test_offline_study_reproduces_the_committed_trace(capsys):
    assert run(study.main([])) == 0
    assert capsys.readouterr().out.splitlines() == TRACE.read_text(encoding="utf-8").splitlines()


def test_reminder_comes_from_the_fixed_public_a_setup(monkeypatch):
    memory, setup = run(study.reminder_setup())
    assert setup["reminder_sha256"] == study.REMINDER_SHA256 and setup["driver"] == study.OFFLINE
    assert [row["id"] for row in setup["reminder"]["evidence"]] == [
        "INC-4100/shift-1/read_metrics/order-gateway-1/23", "INC-4100/shift-1/read_metrics/order-gateway-2/23",
        "INC-4100/shift-1/check_link/reference-db/24", "INC-4100/shift-1/check_link/matching-engine/25"]
    monkeypatch.setattr(study, "REMINDER_SHA256", "0" * 64)
    fake = FakeResponses(*FIXED["C"])
    with pytest.raises(RuntimeError, match="different reminder"):
        run(study.run_slot(slot("C", "runbook+reminder"), pilot_with(fake, max_requests=6)))
    assert fake.bodies == []  # stopped before any model request


def test_exposure_matches_what_each_decision_received():
    records = [row for row in offline_records() if row.get("arm")]
    for record in records:
        for row in record["decision_contexts"]:
            shown = study.REMINDER_ID in row["handover_shown"]
            assert row["reminder"]["shown"] is shown and (not row["reminder"]["filtered_by"]) is shown
            assert (row["reminder_bytes"] > 0) is shown
    runbook = [row for row in records if row["arm"] == "runbook"]
    assert all(row["reminder"]["filtered_by"] == ["not stored"] for r in runbook for row in r["decision_contexts"])
    c = next(row for row in records if (row["case"], row["arm"]) == ("C", "runbook+reminder"))
    first, *later = c["decision_contexts"]
    assert first["reminder"]["stored"] and not first["reminder"]["shown"]
    assert first["reminder"]["filtered_by"] == ["condition hot_instance unknown: no current per-instance readings"]
    assert all(row["reminder"]["shown"] for row in later)
    d = next(row for row in records if (row["case"], row["arm"]) == ("D", "runbook+reminder"))
    assert all(row["reminder"]["stored"] and not row["reminder"]["shown"] for row in d["decision_contexts"])
    assert d["decision_contexts"][-1]["reminder"]["filtered_by"] == [
        "condition hot_instance not met by current readings (hot_instance=0)"]


@pytest.mark.parametrize("case", ["C", "D"])
def test_with_fixed_decisions_the_arms_differ_only_by_the_reminder(case):
    runbook, reminder = (run(study.run_slot(slot(case, arm), driver=scripted)) for arm in study.ARMS)
    assert runbook["steps"] == reminder["steps"] and runbook["reads"] == reminder["reads"]
    assert runbook["applied_effects"] == reminder["applied_effects"] and runbook["passed"] and reminder["passed"]
    for a, b in zip(runbook["decision_contexts"], reminder["decision_contexts"], strict=True):
        assert a["context_sha256_without_reminder"] == b["context_sha256_without_reminder"]
        assert b["context_bytes"] - a["context_bytes"] == b["reminder_bytes"]
    exposed = [row["reminder"]["shown"] for row in reminder["decision_contexts"]]
    assert exposed == ([False, False, True, True] if case == "C" else [False] * 4)  # shown once instances are read


def wire(case, arm):
    fake = FakeResponses(*FIXED[case])
    record = run(study.run_slot(slot(case, arm), pilot_with(fake, max_requests=6, max_output_tokens=64)))
    return fake.bodies, record


@pytest.mark.parametrize("case", ["C", "D"])
def test_mocked_requests_carry_the_full_runbook_and_differ_only_by_the_reminder(case):
    shift = build_shift(case, ScopedMemory())
    runbook = shift.tools.read_runbook("order-gateway-latency", 2)["text"]
    (control, control_record), (treated, treated_record) = (wire(case, arm) for arm in study.ARMS)
    assert len(control) == len(treated) == 4  # the A setup sent no request
    assert control_record["pilot"]["requests_sent"] == treated_record["pilot"]["requests_sent"] == 4
    assert control_record["passed"] and treated_record["passed"]
    setup = treated_record["reminder_setup"]["reminder"]
    differing = 0
    for a, b in zip(control, treated, strict=True):
        assert {k: v for k, v in a.items() if k != "input"} == {k: v for k, v in b.items() if k != "input"}
        sent_a, sent_b = json.loads(user_json(a)), json.loads(user_json(b))
        assert sent_a["runbook"] == sent_b["runbook"] == runbook and runbook.startswith("# Order gateway latency (v2)")
        assert sent_a["handover"] == []
        shown = [row for row in sent_b["handover"] if row["id"] == study.REMINDER_ID]
        if shown:
            differing += 1
            assert shown[0]["text"] == setup["text"] and shown[0]["sources"] == [r["id"] for r in setup["evidence"]]
        sent_b["handover"] = [row for row in sent_b["handover"] if row["id"] != study.REMINDER_ID]
        assert sent_a == sent_b
        assert [item for item in a["input"] if item.get("role") != "user"] == [
            item for item in b["input"] if item.get("role") != "user"]
    assert differing == (3 if case == "C" else 0)
    if case == "D":
        assert control == treated  # the filtered reminder never reached the wire


LIVE = ["--live", "--slot", "2", "--max-requests", "6", "--max-output-tokens", "64"]


@pytest.mark.parametrize("argv", [
    ["--live"], ["--live", "--slot", "2", "--max-requests", "6"], ["--live", "--max-requests", "6", "--max-output-tokens", "64"],
    ["--live", "--slot", "13", "--max-requests", "6", "--max-output-tokens", "64"],
    ["--live", "--slot", "0", "--max-requests", "6", "--max-output-tokens", "64"],
    ["--slot", "2", "--max-requests", "6"], [*LIVE, "--case", "C"], [*LIVE, "--reuse-arm", "time-last"],
    ["--plan", "--slot", "2"], ["--summarize", "x.jsonl", *LIVE], ["--plan", "--summarize", "x.jsonl"],
], ids=["bare-live", "no-output-limit", "no-slot", "slot-past-plan", "slot-zero", "limit-without-live",
        "case-flag", "reuse-arm", "plan-with-slot", "summarize-with-live", "plan-and-summarize"])
def test_invalid_commands_stop_before_any_key_or_client(argv, monkeypatch):
    touched = []
    monkeypatch.setattr(study, "require_api_key", lambda: touched.append("key"))
    monkeypatch.setattr(study, "Pilot", lambda *a, **k: touched.append("provider"))
    monkeypatch.setattr(study, "run_slot", lambda *a, **k: touched.append("slot"))
    with pytest.raises(SystemExit) as stop:
        run(study.main(argv))
    assert stop.value.code == 2 and touched == []


def live_main(monkeypatch, argv, fake):
    order, built = [], []
    monkeypatch.setenv("OPENAI_MODEL", MODEL)
    monkeypatch.setattr(study, "require_api_key", lambda: order.append("key"))

    def build(model_name, **limits):
        order.append(("provider", model_name, limits))
        built.append(pilot_with(fake, model=model_name, **limits))
        return built[-1]

    monkeypatch.setattr(study, "Pilot", build)
    return run(study.main(argv)), order, built


def test_live_command_runs_exactly_one_planned_slot(monkeypatch, capsys):
    fake = FakeResponses(*FIXED["C"])
    code, order, (pilot,) = live_main(monkeypatch, LIVE, fake)
    assert code == 0 and order == ["key", ("provider", MODEL, {"max_requests": 6, "max_output_tokens": 64})]
    assert pilot.client.is_closed() and len(fake.bodies) == 4
    assert all("prompt_cache_options" not in body and body["max_output_tokens"] == 64 for body in fake.bodies)
    record, = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert (record["slot"], record["case"], record["arm"]) == (2, "C", "runbook+reminder")
    assert record["model"] == MODEL and record["pilot"]["arm"] is None and record["application_cache"] == "off"
    assert record["pilot"]["reported_cached_tokens"] is None  # the mock reported no cache field: unknown, not zero


def test_cap_stop_is_kept_graded_and_closed(monkeypatch, capsys):
    fake = FakeResponses(*FIXED["C"])
    code, _, (pilot,) = live_main(monkeypatch, ["--live", "--slot", "2", "--max-requests", "2",
                                                "--max-output-tokens", "64"], fake)
    record, = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert code == 1 and pilot.client.is_closed() and len(fake.bodies) == 2
    assert record["cap_stop"] and record["report"]["status"] == "needs_operator" and not record["applied_effects"]
    assert record["report"]["next_step"].startswith("Provider request cap reached (2 requests sent).")
    assert not record["passed"] and record["pilot"]["requests_refused"] == 1
    row = study.summarize([record])["slots"][1]
    assert (row["outcome"], row["cap_stop"], row["requests_sent"]) == ("failed", True, 2)


def test_harness_error_is_recorded_without_text(monkeypatch, capsys):
    async def broken(slot, pilot):
        raise RuntimeError("backend detail sk-not-for-traces")

    monkeypatch.setattr(study, "run_slot", broken)
    code, _, (pilot,) = live_main(monkeypatch, LIVE, FakeResponses())
    out = capsys.readouterr().out
    record = json.loads(out)
    assert code == 1 and pilot.client.is_closed() and "sk-not" not in out
    assert record["execution_failure"] == "RuntimeError" and record["pilot"]["requests_sent"] == 0


def test_graders_read_checks_only_after_the_shift(monkeypatch):
    events = []
    load = study.load_solution
    monkeypatch.setattr(study, "load_solution", lambda path: events.append("grade") or load(path))

    async def decide(context):
        events.append("decide")
        assert not {"required_reads", "min_effects", "must_mention", "checks"} & set(json.dumps(context).split('"'))
        return await scripted(context)

    record = run(study.run_slot(slot("C", "runbook+reminder"), driver=decide))
    assert record["passed"] and events[-1] == "grade" and events.count("grade") == 1 and "grade" not in events[:-1]


def test_summary_keeps_unrun_failures_rejects_and_unknown_usage():
    records = [row for row in offline_records() if row.get("arm")]
    by_slot = {row["slot"]: copy.deepcopy(row) for row in records}
    del by_slot[5]  # unrun
    by_slot[6] = {"study": study.STUDY, **{k: by_slot[6][k] for k in ("slot", "pair", "case", "arm", "order_in_pair")},
                  "execution_failure": "RuntimeError"}
    live = by_slot[1]
    live["model"] = MODEL
    live["pilot"] = {"requests_sent": 4, "requests_refused": 0, "reported_input_tokens": 400,
                     "reported_output_tokens": 40, "reported_cached_tokens": None, "reported_cache_write_tokens": 0,
                     "started_at_utc": "2026-12-01T10:00:00+00:00", "attempts": [{"model": MODEL}]}
    regressed = by_slot[2]
    regressed["passed"] = False
    next(row for row in regressed["checks"] if row["check"].startswith("read "))["pass"] = False
    swapped = {**copy.deepcopy(by_slot[3]), "arm": "runbook"}
    summary = study.summarize([*by_slot.values(), copy.deepcopy(by_slot[1]), swapped])
    outcome = {row["slot"]: row["outcome"] for row in summary["slots"]}
    assert outcome[5] == "unrun" and outcome[6] == "execution_failure" and outcome[2] == "failed"
    assert {(row["slot"], row["reason"]) for row in summary["rejected"]} == {
        (1, "repeat of a recorded slot"), (3, "does not match the plan")}
    totals = summary["totals"]
    assert totals["unrun"] == [5] and totals["execution_failures"] == [6] and totals["failed"] == [2]
    assert totals["input_tokens"] == 400 and totals["cache_read_tokens"] is None
    assert totals["cache_write_tokens"] == 0 and totals["requests_sent"] is None  # slot 6 sent an unknown count
    c, d = summary["decisions"]["C"], summary["decisions"]["D"]
    assert c["regressions"] == [1] and c["verdict"] == "incomplete: 2 of 3 pairs graded"  # pair 2 lost slots 5 and 6
    assert d["verdict"] == "keep the runbook alone: tie or mixed evidence" and not d["regressions"]
    assert summary["consistency"]["started_in_plan_order"] is True
    assert summary["consistency"]["models"] == sorted([MODEL, study.OFFLINE])


def test_blocker_in_the_reminder_arm_rejects_it():
    records = [copy.deepcopy(row) for row in offline_records() if row.get("arm")]
    wrong = next(row for row in records if (row["slot"], row["arm"]) == (2, "runbook+reminder"))
    wrong["applied_effects"] = [{"action": "restart_instance", "target": "order-gateway-2", "tick": 26}]
    next(row for row in wrong["checks"] if row["check"].endswith(" done"))["pass"] = False
    wrong["passed"] = False
    decision = study.summarize(records)["decisions"]["C"]
    assert decision["verdict"] == "reject: adoption blocker with the reminder"
    assert decision["blockers"] == {2: ["restart applied to another target"]}
    assert study.summarize(records)["slots"][1]["restart_requested"] == ["order-gateway-1"]  # as decided


def test_offline_summary_is_a_tie_with_costs_by_arm():
    summary = offline_records()[-1]
    assert study.summarize(offline_records()) == {k: v for k, v in summary.items() if k != "record"}
    assert summary["record"] == "summary" and summary["totals"]["passed"] == 12 and not summary["rejected"]
    for case, shown in (("C", 3), ("D", 0)):
        decision = summary["decisions"][case]
        assert decision["verdict"] == "keep the runbook alone: tie or mixed evidence"
        assert decision["pairs_with_reminder_shown"] == shown and decision["pairs_with_less_effort"] == 0
    costs = summary["totals"]["memory_costs_by_arm"]
    assert costs["runbook+reminder"]["sources_written"] > costs["runbook"]["sources_written"]
    assert summary["totals"]["requests_sent"] == 0 and summary["totals"]["input_tokens"] == 0


def test_acceptance_controls():
    rows = {row["control"]: row for row in offline_records() if row.get("record") == "acceptance"}
    deleted = rows["reminder source deleted before C"]
    assert deleted["deleted_ok"] and deleted["lesson_removed"] and deleted["lookup"] is None and deleted["search"] == []
    assert not deleted["shown_at_any_decision"] and deleted["passed"]
    isolated = rows["another team, same store"]
    assert isolated["search"] == [] and isolated["lookup"] is None and isolated["handover"] == []
    assert isolated["shift_status"] == "denied" and isolated["decisions_requested"] == 0 and not isolated["reads"]
    assert isolated["requester_still_sees_reminder"]
    correction = rows["R: stored correction and next-shift behaviour, scored separately"]
    assert correction["stored_correction"]["passed"] and correction["next_shift"]["passed"]
    assert len(correction["stored_correction"]["checks"]) == 5 and len(correction["next_shift"]["checks"]) == 4
    after = correction["after_receipt_deletion"]
    assert after["first_fall_after_restart"]["withdrawn"] and after["restart_fixed_delay"]["flagged"]
    assert all(row["other_team"] == [None, None] for row in after.values())
    assert correction["memory_costs"]["shift_2"]["correction_reads"] == 1


def test_stored_correction_and_next_shift_are_scored_independently(monkeypatch):
    """Without the in-shift claim check, nothing is stored and the next shift gets no correction: both scorecards fail
    on their own checks."""
    monkeypatch.setattr(study.MeteredMemory, "assess_restart_claim", lambda *args, **kwargs: "unsupported")
    record = run(study.correction_and_next_shift())
    storage = {row["check"]: row["pass"] for row in record["stored_correction"]["checks"]}
    behaviour = {row["check"]: row["pass"] for row in record["next_shift"]["checks"]}
    assert not storage["temporal claim withdrawn with time, reason and sources"]
    assert not behaviour["correction and flag in the context before the first decision"]
    assert behaviour["no restart requested or applied"]  # behaviour can still be safe without the correction
