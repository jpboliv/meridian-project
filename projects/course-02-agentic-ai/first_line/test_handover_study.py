"""#17 handover study, offline: plan, reminder exposure, arm equivalence on the mock wire, the bounded one-slot CLI,
acceptance controls and the summary. No key, network or provider charge."""

import asyncio
import copy
import json
import signal

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


LIMITS = ["--max-requests", "6", "--max-output-tokens", "64"]
LIVE = ["--live", "--slot", "2", *LIMITS, "--ledger", "ledger.jsonl"]


@pytest.mark.parametrize("argv", [
    ["--live"], ["--live", "--slot", "2", "--max-requests", "6", "--ledger", "x"], ["--live", *LIMITS, "--ledger", "x"],
    ["--live", "--slot", "2", *LIMITS], ["--live", "--slot", "13", *LIMITS, "--ledger", "x"],
    ["--live", "--slot", "0", *LIMITS, "--ledger", "x"], ["--slot", "2", "--max-requests", "6"],
    ["--slot", "2", "--ledger", "x"], [*LIVE, "--case", "C"], [*LIVE, "--reuse-arm", "time-last"],
    [*LIVE, "--model", "m"], ["--freeze-protocol", *LIMITS, "--ledger", "x"],
    ["--freeze-protocol", "--model", "m", *LIMITS, "--ledger", "x", "--slot", "2"], [*LIVE, "--freeze-protocol"],
    ["--plan", "--slot", "2"], ["--summarize", "x.jsonl", *LIVE], ["--plan", "--summarize", "x.jsonl"],
], ids=["bare-live", "no-output-limit", "no-slot", "no-ledger", "slot-past-plan", "slot-zero", "limit-without-live",
        "ledger-without-live", "case-flag", "reuse-arm", "model-with-live", "freeze-without-model", "freeze-with-slot",
        "live-and-freeze", "plan-with-slot", "summarize-with-live", "plan-and-summarize"])
def test_invalid_commands_stop_before_any_key_or_client(argv, monkeypatch):
    touched = []
    monkeypatch.setattr(study, "require_api_key", lambda: touched.append("key"))
    monkeypatch.setattr(study, "Pilot", lambda *a, **k: touched.append("provider"))
    monkeypatch.setattr(study, "run_slot", lambda *a, **k: touched.append("slot"))
    with pytest.raises(SystemExit) as stop:
        run(study.main(argv))
    assert stop.value.code == 2 and touched == []


def freeze(ledger, max_requests=6, model=MODEL):
    assert run(study.main(["--freeze-protocol", "--model", model, "--max-requests", str(max_requests),
                           "--max-output-tokens", "64", "--ledger", str(ledger)])) == 0


def live_main(monkeypatch, argv, fake, ledger):
    order, built = [], []
    monkeypatch.setenv("OPENAI_MODEL", MODEL)
    monkeypatch.setattr(study, "require_api_key", lambda: order.append("key"))

    def build(model_name, **limits):
        order.append(("provider", model_name, limits))
        built.append(pilot_with(fake, model=model_name, **limits))
        return built[-1]

    monkeypatch.setattr(study, "Pilot", build)
    argv = [str(ledger) if arg == "ledger.jsonl" else arg for arg in argv]
    return run(study.main(argv)), order, built


def ledger_rows(ledger):
    return study.read_ledger(ledger)


def test_live_command_runs_exactly_one_planned_slot(monkeypatch, capsys, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    freeze(ledger)
    capsys.readouterr()
    fake = FakeResponses(*FIXED["C"])
    code, order, (pilot,) = live_main(monkeypatch, LIVE, fake, ledger)
    assert code == 0 and order == ["key", ("provider", MODEL, {"max_requests": 6, "max_output_tokens": 64})]
    assert pilot.client.is_closed() and len(fake.bodies) == 4
    assert all("prompt_cache_options" not in body and body["max_output_tokens"] == 64 for body in fake.bodies)
    record, = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert (record["slot"], record["case"], record["arm"]) == (2, "C", "runbook+reminder")
    assert record["model"] == MODEL and record["pilot"]["arm"] is None and record["application_cache"] == "off"
    assert record["pilot"]["reported_cached_tokens"] is None  # the mock reported no cache field: unknown, not zero
    protocol, start, end = ledger_rows(ledger)
    assert [protocol["record"], start["record"]] == ["protocol", "start"] and end == record
    assert start["run_id"] == end["run_id"] and start["protocol_sha256"] == study.protocol_sha256(protocol)
    row = study.summarize(ledger_rows(ledger))["slots"][1]
    assert (row["outcome"], row["problems"], row["requests_sent"], row["input_tokens"]) == ("passed", [], 4, 410)
    assert row["cache_read_tokens"] is None  # unknown per metric, while input stays known


def test_cap_stop_is_kept_graded_and_closed(monkeypatch, capsys, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    freeze(ledger, max_requests=2)
    capsys.readouterr()
    fake = FakeResponses(*FIXED["C"])
    code, _, (pilot,) = live_main(monkeypatch, ["--live", "--slot", "2", "--max-requests", "2",
                                                "--max-output-tokens", "64", "--ledger", "ledger.jsonl"], fake, ledger)
    record, = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert code == 1 and pilot.client.is_closed() and len(fake.bodies) == 2
    assert record["cap_stop"] and record["report"]["status"] == "needs_operator" and not record["applied_effects"]
    assert record["report"]["next_step"].startswith("Provider request cap reached (2 requests sent).")
    assert not record["passed"] and record["pilot"]["requests_refused"] == 1
    row = study.summarize(ledger_rows(ledger))["slots"][1]
    assert (row["outcome"], row["cap_stop"], row["requests_sent"], row["requests_refused"]) == ("failed", True, 2, 1)


def test_harness_error_is_recorded_without_text(monkeypatch, capsys, tmp_path):
    async def broken(slot, pilot):
        raise RuntimeError("backend detail sk-not-for-traces")

    ledger = tmp_path / "ledger.jsonl"
    freeze(ledger)
    capsys.readouterr()
    monkeypatch.setattr(study, "run_slot", broken)
    code, _, (pilot,) = live_main(monkeypatch, LIVE, FakeResponses(), ledger)
    out = capsys.readouterr().out
    record = json.loads(out)
    assert code == 1 and pilot.client.is_closed() and "sk-not" not in out + ledger.read_text()
    assert record["execution_failure"] == "RuntimeError" and record["pilot"]["requests_sent"] == 0
    row = study.summarize(ledger_rows(ledger))["slots"][1]
    assert (row["outcome"], row["requests_sent"], row["input_tokens"]) == ("execution_failure", 0, 0)


async def sigint():
    signal.raise_signal(signal.SIGINT)  # Ctrl-C: asyncio.run cancels the main task, then raises KeyboardInterrupt
    await asyncio.sleep(30)


async def cancelled():
    raise asyncio.CancelledError


@pytest.mark.parametrize("interrupt, stop", [(sigint, KeyboardInterrupt), (cancelled, asyncio.CancelledError)],
                         ids=["ctrl-c", "cancelled"])
def test_interruption_keeps_requests_exposure_and_unknown_usage_and_is_never_retried(interrupt, stop, monkeypatch,
                                                                                      capsys, tmp_path):
    """A user stop while the third request is in flight: the end record keeps every request sent, the shift's
    contexts so far and unknown usage for the cut request. The slot is attempted, not unrun, and the runner refuses
    to start it again."""
    ledger = tmp_path / "ledger.jsonl"
    freeze(ledger)
    capsys.readouterr()

    class Stopping(FakeResponses):
        def __call__(self, request):
            if len(self.bodies) < 2:
                return super().__call__(request)
            self.bodies.append(json.loads(request.content))
            return interrupt()  # the transport awaits it

    fake = Stopping(*FIXED["C"][:2])
    with pytest.raises(stop):
        live_main(monkeypatch, LIVE, fake, ledger)
    end = ledger_rows(ledger)[-1]
    assert end["interrupted"] == "CancelledError" and end["pilot"]["requests_sent"] == 3
    assert [row["decision"] for row in end["decision_contexts"]] == [1, 2, 3] and end["steps"] == ["instances", "tickets"]
    summary = study.summarize(ledger_rows(ledger))
    row = summary["slots"][1]
    assert (row["outcome"], row["requests_sent"], row["input_tokens"]) == ("interrupted", 3, None)
    assert summary["totals"]["attempted"] == 1 and summary["totals"]["interrupted"] == [2]
    assert summary["totals"]["input_tokens"] is None and summary["incurred"]["requests_sent"] == 3
    assert summary["decisions"]["C"]["verdict"].startswith("incomplete")
    touched = []
    monkeypatch.setattr(study, "require_api_key", lambda: touched.append("key"))
    with pytest.raises(SystemExit, match="already started"):
        run(study.main([str(ledger) if arg == "ledger.jsonl" else arg for arg in LIVE]))
    assert touched == [] and len(ledger_rows(ledger)) == 3


@pytest.mark.parametrize("change, message", [
    (lambda m: m.setattr(study, "harness_hashes", lambda: {"shift.py": "0" * 64}), "harness differs"),
    (lambda m: m.setattr(study, "REMINDER_SHA256", "0" * 64), "reminder hash differs"),
    (lambda m: m.setenv("OPENAI_MODEL", "another-model"), "OPENAI_MODEL differs"),
], ids=["harness", "reminder", "model"])
def test_live_slot_refuses_drift_from_the_frozen_protocol(change, message, monkeypatch, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    freeze(ledger)
    monkeypatch.setenv("OPENAI_MODEL", MODEL)
    monkeypatch.setattr(study, "require_api_key", lambda: None)
    monkeypatch.setattr(study, "Pilot", lambda *a, **k: pytest.fail("no provider client may be built"))
    change(monkeypatch)
    with pytest.raises(SystemExit, match=message):
        run(study.main([str(ledger) if arg == "ledger.jsonl" else arg for arg in LIVE]))
    assert len(ledger_rows(ledger)) == 1  # no start record


def test_live_slot_needs_a_frozen_protocol_with_the_same_limits(monkeypatch, tmp_path):
    monkeypatch.setattr(study, "require_api_key", lambda: pytest.fail("no key may be loaded"))
    with pytest.raises(SystemExit, match="one frozen protocol"):
        run(study.main([str(tmp_path / "none.jsonl") if arg == "ledger.jsonl" else arg for arg in LIVE]))
    ledger = tmp_path / "ledger.jsonl"
    freeze(ledger, max_requests=5)
    with pytest.raises(SystemExit, match="limits differ"):
        run(study.main([str(ledger) if arg == "ledger.jsonl" else arg for arg in LIVE]))
    with pytest.raises(SystemExit, match="already has records"):
        freeze(ledger)


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


_WIRE = {}


def wired(case, arm):
    """One mock-wire live record per case and arm (fixed decisions), computed once."""
    if (case, arm) not in _WIRE:
        _WIRE[case, arm] = wire(case, arm)[1]
    return copy.deepcopy(_WIRE[case, arm])


def live_ledger(edit=lambda slot, record: record):
    """A complete 12-slot live ledger on the mock wire: protocol, then a start and an end record per planned slot."""
    protocol = study.frozen_protocol(MODEL, 6, 64)
    rows = [protocol]
    for planned in study.slot_plan():
        run_id = f"run-{planned['slot']}"
        record = {**wired(planned["case"], planned["arm"]), **planned, "run_id": run_id}
        rows.append({"record": "start", "study": study.STUDY, **planned, "run_id": run_id, "model": MODEL,
                     "protocol_sha256": study.protocol_sha256(protocol), "harness_sha256": study.harness_hashes(),
                     "started_at_utc": f"2026-12-01T10:{planned['slot']:02d}:00+00:00"})
        if (record := edit(planned["slot"], record)) is not None:
            rows.append(record)
    return rows


def test_complete_live_ledger_c_is_a_tie_and_d_is_only_a_control():
    summary = study.summarize(live_ledger())
    assert summary["rule"].startswith("Draft") and "not dollars" in summary["units"]
    assert summary["totals"]["passed"] == 12 and not summary["rejected"] and summary["totals"]["unrun"] == []
    c, d = summary["decisions"]["C"], summary["decisions"]["D"]
    assert c["verdict"] == "keep the runbook alone: tie or mixed evidence (3 of 3 pairs exposed)"
    assert d["verdict"].startswith("control only") and d["pairs_comparable"] == 3 and d["pairs_exposed"] == 0
    assert summary["totals"]["requests_sent"] == summary["incurred"]["requests_sent"] == 48
    assert summary["totals"]["input_tokens"] == summary["incurred"]["input_tokens"] > 0
    assert summary["totals"]["cache_read_tokens"] is None  # the mock reports no cache field
    assert summary["consistency"]["returned_models"] == [f"{MODEL}-2026-11-01"]
    assert summary["consistency"]["started_in_plan_order"] is True and summary["scripted_control"]["records"] == 0


def fewer_reads(slot, record, shown=True):
    if record["arm"] == "runbook+reminder" and record["case"] == "C":
        record["reads_before_decision"] -= 1
        if not shown:
            for row in record["decision_contexts"]:
                row["handover_shown"], row["reminder"]["shown"] = [], False
                row["reminder"]["filtered_by"] = row["reminder"]["filtered_by"] or ["condition hot_instance not met"]
    return record


def test_only_exposed_pairs_can_credit_the_reminder():
    exposed = study.summarize(live_ledger(fewer_reads))["decisions"]["C"]
    assert exposed["verdict"] == "reminder candidate: less effort at equal success in at least two exposed pairs"
    hidden = study.summarize(live_ledger(lambda s, r: fewer_reads(s, r, shown=False)))
    assert hidden["decisions"]["C"]["verdict"].startswith("control only") and not any(
        unit["fewer_reads"] for unit in hidden["pairs"])


def test_ineligible_exposure_blocks_adoption_even_in_an_ungraded_slot():
    def stale(slot, record):
        if slot == 3:  # D, reminder arm: interrupted after showing a stale reminder
            context = record["decision_contexts"][0]
            context["handover_shown"] = [study.REMINDER_ID]
            context["reminder"].update(shown=True, filtered_by=["outside its seven-day review window"])
            return {key: record[key] for key in ("study", "slot", "pair", "case", "arm", "order_in_pair", "run_id",
                                                 "model", "harness_sha256", "pilot", "decision_contexts")} | {
                       "interrupted": "KeyboardInterrupt"}
        return record

    summary = study.summarize(live_ledger(stale))
    d = summary["decisions"]["D"]
    assert summary["slots"][2]["outcome"] == "interrupted"
    assert d["verdict"] == "reject: adoption blocker with the reminder"
    assert d["blockers"] == {3: ["reminder shown while ineligible at decision 1: outside its seven-day review window"]}


def test_memory_reaching_the_control_makes_the_pair_incomparable():
    def leak(slot, record):
        if slot == 1:  # C, runbook arm
            record["decision_contexts"][-1]["handover_shown"] = [study.REMINDER_ID]
            record["decision_contexts"][-1]["reminder"]["shown"] = True
        return record

    summary = study.summarize(live_ledger(leak))
    assert summary["decisions"]["C"]["verdict"] == "incomplete: 2 of 3 pairs complete and comparable"
    assert summary["decisions"]["C"]["blockers"] == {1: ["reminder shown while ineligible at decision 4: not stored"]}


@pytest.mark.parametrize("edit, problem", [
    (lambda r: r["harness_sha256"].update({"shift.py": "0" * 64}), "harness_sha256 differs from the protocol"),
    (lambda r: r["pilot"]["attempts"][0].update(model="other-model"), "returned model differs from the protocol"),
    (lambda r: r.update(model=study.OFFLINE), "model differs from the protocol"),
    (lambda r: r["pilot"].update(max_requests=7), "pilot max_requests differs from the protocol"),
    (lambda r: r["reminder_setup"].update(reminder_sha256="0" * 64), "reminder hash differs from the protocol"),
    (lambda r: r.update(seed=12), "seed differs from the protocol"),
], ids=["harness", "returned-model", "scripted-label-on-live", "limits", "reminder", "seed"])
def test_mismatched_live_records_are_invalid_not_evidence(edit, problem):
    summary = study.summarize(live_ledger(lambda slot, record: edit(record) or record if slot == 2 else record))
    row = summary["slots"][1]
    assert row["outcome"] == "invalid" and problem in row["problems"]
    assert summary["decisions"]["C"]["verdict"] == "incomplete: 2 of 3 pairs complete and comparable"
    assert summary["totals"]["invalid"] == [2] and summary["incurred"]["requests_sent"] == 48  # its cost still counts


def test_without_one_frozen_protocol_nothing_is_live_evidence():
    rows = live_ledger()[1:]
    summary = study.summarize(rows)
    assert {row["outcome"] for row in summary["slots"]} == {"invalid"}
    assert summary["slots"][0]["problems"] == ["no single frozen protocol in the inputs"]
    other = study.frozen_protocol("another-model", 6, 64)
    assert study.summarize([*live_ledger(), other])["rejected"][0]["reason"] == "several different frozen protocols"


def test_scripted_records_never_enter_the_live_verdict():
    scripted_rows = [row for row in offline_records() if row.get("arm")]
    summary = study.summarize([study.frozen_protocol(MODEL, 6, 64), *scripted_rows])
    assert summary["totals"]["unrun"] == list(range(1, 13)) and summary["totals"]["attempted"] == 0
    assert all(d["verdict"].startswith("incomplete: 0 of 3") for d in summary["decisions"].values())
    assert summary["scripted_control"]["records"] == 12 and summary["scripted_control"]["passed"] == 12
    mixed = study.summarize([*live_ledger(lambda slot, record: None if slot == 5 else record), scripted_rows[4]])
    assert mixed["slots"][4]["outcome"] == "interrupted_without_end_record"
    assert mixed["scripted_control"]["records"] == 1 and mixed["decisions"]["C"]["verdict"].startswith("incomplete")


def test_start_without_end_is_attempted_with_unknown_usage():
    summary = study.summarize(live_ledger(lambda slot, record: None if slot == 4 else record))
    row = summary["slots"][3]
    assert row["outcome"] == "interrupted_without_end_record" and row["requests_sent"] is None
    assert summary["totals"]["requests_sent"] is None and summary["incurred"]["input_tokens"] is None
    assert summary["incurred"]["runs_without_end_record"] == [4]


def test_duplicates_retries_and_loose_records_are_rejected_but_their_spending_counts():
    rows = live_ledger()
    end = copy.deepcopy(next(row for row in rows if row.get("run_id") == "run-2" and "record" not in row))
    retry_start = {**next(row for row in rows if row.get("record") == "start" and row["slot"] == 2), "run_id": "retry"}
    retry_end = {**copy.deepcopy(end), "run_id": "retry"}
    loose = {**copy.deepcopy(end), "run_id": "no-start"}
    summary = study.summarize([*rows, end, retry_start, retry_end, loose])
    assert {(row.get("run_id"), row["reason"]) for row in summary["rejected"]} == {
        ("run-2", "duplicate end record"), ("retry", "retry of an already started slot"),
        ("no-start", "live record without a start record")}
    assert summary["slots"][1]["run_id"] == "run-2" and summary["totals"]["requests_sent"] == 48
    assert summary["incurred"]["runs"] == 14 and summary["incurred"]["requests_sent"] == 48 + 4 + 4


def test_failure_usage_counts_per_metric():
    def failed(slot, record):
        if slot == 6:
            record["pilot"]["attempts"].append({"status": 500, "model": None, "input_tokens": None,
                                                "output_tokens": None, "cached_tokens": None,
                                                "cache_write_tokens": None})
            record["pilot"]["requests_sent"] += 1
            return {key: record[key] for key in ("study", "slot", "pair", "case", "arm", "order_in_pair", "run_id",
                                                 "model", "harness_sha256", "pilot")} | {"execution_failure": "X"}
        if slot == 7:
            record["pilot"]["attempts"][0]["output_tokens"] = None
        return record

    summary = study.summarize(live_ledger(failed))
    six, seven = summary["slots"][5], summary["slots"][6]
    assert (six["outcome"], six["requests_sent"], six["input_tokens"]) == ("execution_failure", 5, None)
    assert seven["outcome"] == "passed" and seven["output_tokens"] is None and seven["input_tokens"] > 0
    assert summary["totals"]["requests_sent"] == summary["incurred"]["requests_sent"] == 49
    assert summary["totals"]["input_tokens"] is None and summary["totals"]["output_tokens"] is None


def test_heterogeneous_returned_models_are_not_evidence():
    def snapshot(slot, record):
        if slot == 9:
            for row in record["pilot"]["attempts"]:
                row["model"] = f"{MODEL}-2026-12-01"
        return record

    summary = study.summarize(live_ledger(snapshot))
    assert all(d["verdict"].startswith("invalid: heterogeneous evidence") for d in summary["decisions"].values())


def test_offline_summary_keeps_scripted_slots_out_of_the_live_verdict():
    summary = offline_records()[-1]
    assert study.summarize(offline_records()) == {k: v for k, v in summary.items() if k != "record"}
    assert summary["record"] == "summary" and summary["totals"]["unrun"] == list(range(1, 13))
    assert summary["incurred"]["runs"] == 0 and summary["consistency"]["protocol_sha256"] is None
    control = summary["scripted_control"]
    assert control["passed"] == 12 and not control["rejected"]
    for case, exposed in (("C", 3), ("D", 0)):
        assert control["by_case"][case]["pairs_exposed"] == exposed
        assert control["by_case"][case]["pairs_with_fewer_reads"] == 0 and not control["by_case"][case]["blockers"]
    costs = control["memory_costs_by_arm"]
    assert costs["runbook+reminder"]["sources_written"] > costs["runbook"]["sources_written"]


def test_grader_blocker_in_the_reminder_arm_rejects_it():
    def wrong(slot, record):
        if slot == 2:
            record["applied_effects"] = [{"action": "restart_instance", "target": "order-gateway-2", "tick": 26}]
            next(row for row in record["checks"] if row["check"].endswith(" done"))["pass"] = False
            record["passed"] = False
        return record

    summary = study.summarize(live_ledger(wrong))
    assert summary["decisions"]["C"]["verdict"] == "reject: adoption blocker with the reminder"
    assert summary["decisions"]["C"]["blockers"] == {2: ["restart applied to another target"]}
    assert summary["slots"][1]["restart_requested"] == ["order-gateway-1"]  # as decided


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
