"""gateway-m1.7: offline follow-up to the public M1 live failures (E stall, D decorated identifier, A2 cue, A3 reason).

Decisions are replayed on a mock Responses transport (no key, network or charge). A mocked pass shows what the
harness permits or does with a given choice, not what a live model would choose. Saved live choices come from
`live-baseline-m1.6-2026-11-22.jsonl`; that file and the graders are not changed.
"""

import asyncio
import json

import pytest
from meridian.scenarios import load_scenario

import demo
from shift import MODEL_FAILURES, Decision, Shift
from test_pilot import LUNA, FakeResponses, Wire, cue, pilot_with, sent_progress, user_json

MONITOR = "monitoring.get_instance_datapoints"
TICKS = ("tickets", "instances", "links")


def steps(*names):
    return [{"step": name} for name in names]


def live(case, *answers, max_requests=6, max_output_tokens=512):
    """One public case on the mock transport, under the baseline limits (6 requests, 512 output tokens)."""
    fake = FakeResponses(*answers)
    record = asyncio.run(demo.run_case(demo.CASES[case], pilot_with(fake, max_requests, max_output_tokens, model=LUNA)))
    return record, fake


def modified(case, decide_with, **changes):
    """A public case with a changed fixture (not graded): returns the shift and its report."""
    scenario = load_scenario(demo.CASES[case])
    for name, value in changes.items():
        setattr(scenario, name, value)
    sim = demo.start_exchange(scenario)
    identity = demo.identity_for(sim.scenario.actor["role"])
    shift = Shift(demo.IncidentDeps(demo.MeridianTools(sim, actor=identity["name"]), identity=identity))
    return shift, asyncio.run(shift.run(decide_with(sim)))


def tools(record):
    return [row["tool"] for row in record["reads_and_actions"]]


def no_effect(record):
    report = record["report"]
    return (record["applied_effects"] == 0 and report["action"] is None and report["status"] == "needs_operator"
            and "recovery" not in report["observations"] and "request_approval" not in tools(record))


# --- E: a refresh that brings no new sample -------------------------------------------------------------------

E_SAVED = {"E1": TICKS[:2] + ("instances", "links", "links", "links"),  # slot 5
           "E2/E3": ("tickets",) + ("instances",) * 5}                   # slots 10 and 15


@pytest.mark.parametrize("choices", E_SAVED.values(), ids=E_SAVED.keys())
def test_saved_e_rereads_stop_after_one_unchanged_refresh_with_the_sourced_link(choices):
    record, fake = live("E", *steps(*choices))
    # Three requests instead of six plus a refusal: the second unchanged read ends the model's part.
    assert len(fake.bodies) == 3 and record["pilot"]["requests_refused"] == 0
    assert [d["step"] for d in record["decisions"]] == ["tickets", "instances", "instances"]
    monitor = [row for row in record["reads_and_actions"] if row["tool"] == MONITOR]
    # Both reads really happened and their poll ticks advanced; the sample time did not.
    assert len(monitor) == 4 and len({row["tick"] for row in monitor}) == 4
    samples = record["report"]["observations"]["instances"]
    assert {s["time"] for s in samples.values()} == {"09:00"}
    assert all(s["source"].endswith(f"/{row['tick']}") for s, row in zip(samples.values(), monitor[2:]))
    # The harness, not the model, consulted the independent link monitor, once.
    links = [row for row in record["reads_and_actions"] if row["tool"] == "check_link"]
    assert [row["target"] for row in links] == ["reference-db", "matching-engine"]
    assert all(row["tick"] > monitor[-1]["tick"] for row in links)
    report = record["report"]
    assert report["stale_evidence"] == {
        "rule": "refresh brought no new evidence while gateway samples are stale", "refreshed": "instances",
        "unchanged": {"order-gateway-1": "09:00", "order-gateway-2": "09:00"},
        "stale_samples": {"order-gateway-1": "09:00", "order-gateway-2": "09:00"}, "links_read_by": "harness"}
    assert report["follow_up"] == {"operation": "investigate_link", "source": "order-gateway",
                                   "target": "reference-db", "observed_tick": links[0]["tick"]}
    assert report["next_step"].startswith("Gateway samples from 09:00 do not establish current health.")
    assert record["passed"] and no_effect(record)
    assert sent_progress(fake)[2] == cue("matched", {"tickets": 1, "instances": 1})  # no link observed yet


def test_an_unchanged_link_refresh_under_stale_samples_also_stops():
    record, fake = live("E", *steps("tickets", "instances", "links", "links", "links", "links"))
    assert len(fake.bodies) == 4 and [d["step"] for d in record["decisions"]] == ["tickets", "instances", "links", "links"]
    assert tools(record).count("check_link") == 4  # the model's two link reads; the harness adds none
    evidence = record["report"]["stale_evidence"]
    # The stalled step was the links: the model's just-completed read is already after the stall and is reused.
    assert (evidence["refreshed"], evidence["links_read_by"]) == ("links", "model")
    assert "superseded_link_ticks" not in evidence
    assert evidence["unchanged"] == {"reference-db": "degraded", "matching-engine": "up"}
    assert record["report"]["follow_up"]["observed_tick"] == record["reads_and_actions"][-2]["tick"]  # latest read
    assert record["passed"] and no_effect(record)


def test_e_link_choice_stays_with_the_model_when_it_chooses():
    record, fake = live("E", *steps(*TICKS), {"step": "handover", "target": "reference-db"})
    assert sent_progress(fake)[3] == cue("matched", {"tickets": 1, "instances": 1, "links": 1}, ["reference-db"])
    assert "stale_evidence" not in record["report"] and record["passed"] and no_effect(record)


def resume_collector_after_first_read(fake, seen):
    """The stopped collector starts polling again after the first instance read (a fixture change, not a
    decision). `seen` keeps a copy of each instance observation the decider is shown."""
    def build(sim):
        decide = pilot_with(fake, 6, 512, model=LUNA).decider([])

        async def wrapped(context):
            if "instances" in context["observations"]:
                seen.append(json.loads(json.dumps(context["observations"]["instances"])))
                sim.metrics.component = None  # StoppedCollector now serves the live series
            return await decide(context)
        return wrapped
    return build


def test_a_genuinely_newer_sample_on_refresh_is_progress_even_with_the_same_value():
    fake, seen = FakeResponses(*steps("tickets", "instances", "instances", "links"),
                               {"step": "handover", "target": "reference-db"}), []
    shift, report = modified("E", resume_collector_after_first_read(fake, seen))
    first, refreshed = seen[0], report["observations"]["instances"]
    assert {s["freshness"] for s in first.values()} == {"stale"}
    assert all(refreshed[name]["time"] > first[name]["time"] and refreshed[name]["freshness"] == "current"
               for name in first)
    assert [refreshed[name]["memory_pct"] for name in first] == [s["memory_pct"] for s in first.values()]
    # Not a stall: the model kept deciding, then chose the link handover itself.
    assert "stale_evidence" not in report and len(fake.bodies) == 5
    assert report["follow_up"]["target"] == "reference-db" and not shift.deps.sim.executor.effects()


@pytest.mark.parametrize("faults, expected", [
    ([], None),
    ([{"type": "link", "at": 65, "source": "order-gateway", "target": "matching-engine", "mode": "degraded",
       "extra_latency_ms": 185}], "matching-engine"),
    ([{"type": "link", "at": 65, "source": "order-gateway", "target": target, "mode": "degraded",
       "extra_latency_ms": 185} for target in ("reference-db", "matching-engine")], None),
], ids=["healthy-links", "other-link-faulty", "two-faulty-links"])
def test_unchanged_stale_samples_hand_over_only_what_the_links_establish(faults, expected):
    fake = FakeResponses(*steps("tickets", "instances", "instances", "links"))
    shift, report = modified("E", lambda sim: pilot_with(fake, 6, 512, model=LUNA).decider([]), faults=faults)
    assert len(fake.bodies) == 3 and report["stale_evidence"]["links_read_by"] == "harness"
    sim = shift.deps.sim
    assert report["status"] == "needs_operator" and report["action"] is None
    assert not sim.approvals and not sim.executor.effects() and "recovery" not in report["observations"]
    if expected:
        assert report["follow_up"]["operation"] == "investigate_link" and report["follow_up"]["target"] == expected
        return
    # No single fault established: name the unresolved evidence; never invent a degraded link.
    assert report["follow_up"] == {"operation": "obtain_instance_readings", "source": MONITOR,
                                   "targets": ["order-gateway-1", "order-gateway-2"]}
    assert ("No fault established." in report["next_step"]) == (not faults)
    assert report["next_step"].startswith("Gateway samples for order-gateway-1, order-gateway-2 still end at 09:00")


def test_sample_progress_is_per_replica_and_needs_a_newer_sample_time():
    """Progress means a replica that was stale before the refresh has a newer sample time. Sample times are
    dateless `HH:MM`; these checks stay within one simulated day."""
    sim = demo.start_exchange(demo.CASES["E"])
    shift = Shift(demo.IncidentDeps(demo.MeridianTools(sim), identity=demo.identity_for("first-line")))
    stale = {"memory_pct": 55.0, "time": "09:00", "status": "running", "freshness": "stale"}

    def sample(time):
        return {**stale, "time": time, "freshness": "current" if time >= "10:00" else "stale"}

    def refresh(before, **after):
        shift.observations["instances"] = {name: sample(time) for name, time in after.items()}
        return shift.no_new_evidence("instances", {name: sample(time) for name, time in before.items()})

    both_stale = {"order-gateway-1": "09:00", "order-gateway-2": "09:00"}
    # One outstanding replica advanced (to current, or to a newer but still stale sample): progress, although
    # the other stayed stale. Both observations are kept and the model decides next.
    assert refresh(both_stale, **{"order-gateway-1": "10:09", "order-gateway-2": "09:00"}) == {}
    assert refresh(both_stale, **{"order-gateway-1": "09:05", "order-gateway-2": "09:00"}) == {}
    assert refresh(both_stale, **{"order-gateway-1": "09:05", "order-gateway-2": "09:05"}) == {}
    assert shift.observations["instances"]["order-gateway-2"]["time"] == "09:05"
    # Nothing outstanding advanced: a stall, even when an already-current replica moved on.
    assert refresh(both_stale, **both_stale) == both_stale
    one_current = {"order-gateway-1": "10:09", "order-gateway-2": "09:00"}
    assert refresh(one_current, **{"order-gateway-1": "10:12", "order-gateway-2": "09:00"}) == {
        "order-gateway-2": "09:00"}
    assert refresh(one_current, **{"order-gateway-1": "10:12", "order-gateway-2": "09:01"}) == {}
    assert shift.no_new_evidence("instances", None) == {}  # a first read is never a stall


# --- E: the stall handover uses link evidence from after the stall ---------------------------------------------

LINK_FIRST = ("tickets", "links", "instances", "instances")  # the model read the links before the stalled refresh
DEGRADED_UNTIL_70 = [{"type": "link", "at": 65, "source": "order-gateway", "target": "reference-db",
                      "mode": "degraded", "extra_latency_ms": 185, "until": 70}]
NEWLY_DEGRADED_AT_70 = [{"type": "link", "at": 70, "source": "order-gateway", "target": "matching-engine",
                         "mode": "degraded", "extra_latency_ms": 185}]


def link_rows(shift):
    return [(call.tick, call.args["target"], call.result.get("state")) for call in shift.tools.trace
            if call.tool == "check_link"]


def stall_after_link_read(faults=None, check_link=None):
    """Public E with the link read before the stalled instance refresh (a changed fixture, not graded)."""
    fake = FakeResponses(*steps(*LINK_FIRST))
    changes = {} if faults is None else {"faults": faults}
    if check_link:
        changes["tools"] = load_scenario(demo.CASES["E"]).tools | {"check_link": check_link}
    shift, report = modified("E", lambda sim: pilot_with(fake, 6, 512, model=LUNA).decider([]), **changes)
    assert len(fake.bodies) == 4 and [d["step"] for d in shift.decisions] == list(LINK_FIRST)
    sim = shift.deps.sim
    assert report["status"] == "needs_operator" and report["action"] is None
    assert not sim.approvals and not sim.executor.effects() and "recovery" not in report["observations"]
    stall = max(call.tick for call in shift.tools.trace if call.tool == MONITOR)
    return shift, report, stall


@pytest.mark.parametrize("faults, before, after, cited", [
    (None, "degraded", {"reference-db": "degraded", "matching-engine": "up"}, "reference-db"),
    (DEGRADED_UNTIL_70, "degraded", {"reference-db": "up", "matching-engine": "up"}, None),
    (NEWLY_DEGRADED_AT_70, "up", {"reference-db": "up", "matching-engine": "degraded"}, "matching-engine"),
], ids=["still-degraded", "fault-cleared", "newly-degraded"])
def test_a_stalled_instance_refresh_rereads_the_links_after_the_stall(faults, before, after, cited):
    shift, report, stall = stall_after_link_read(faults)
    rows = link_rows(shift)
    # Before: the model's own read at ticks 67-68. After: one harness read at 75-76, once the refresh ending at
    # tick 74 stalled. The fixtures change state at tick 70, between the two.
    assert [tick for tick, _, _ in rows] == [67, 68, 75, 76] and stall == 74
    assert rows[0][1:] == ("reference-db", before)
    assert {target: state for _, target, state in rows[2:]} == after == {
        name: row["state"] for name, row in report["observations"]["links"].items()}
    evidence = report["stale_evidence"]
    assert (evidence["refreshed"], evidence["links_read_by"], evidence["superseded_link_ticks"]) == (
        "instances", "harness", [67, 68])
    assert all(row["tick"] > stall for row in report["observations"]["links"].values())
    assert "tick 67" not in report["next_step"] and "tick 68" not in report["next_step"]
    if cited:
        assert report["follow_up"] == {"operation": "investigate_link", "source": "order-gateway",
                                       "target": cited, "observed_tick": rows[2 if cited == "reference-db" else 3][0]}
        assert report["next_step"].startswith("Gateway samples from 09:00 do not establish current health. "
                                              f"Investigate the degraded link from order-gateway to {cited}.")
        return
    assert report["follow_up"]["operation"] == "obtain_instance_readings"
    assert "check_link reports reference-db up (tick 75), matching-engine up (tick 76). No fault established." in (
        report["next_step"])


@pytest.mark.parametrize("fail_call", [3, 4], ids=["first-fresh-row", "second-fresh-row"])
def test_a_failed_fresh_link_read_cites_no_earlier_link_and_claims_no_health(fail_call):
    shift, report, stall = stall_after_link_read(check_link={"fail_calls": [fail_call]})
    rows = link_rows(shift)
    assert rows[0][1:] == ("reference-db", "degraded") and rows[0][0] < stall  # the superseded read was faulty
    assert "links" not in report["observations"] and shift.faulty_links() == []
    assert report["observations"]["missing_link"].startswith("Missing link state for ")
    assert report["stale_evidence"]["superseded_link_ticks"] == [67, 68]
    assert report["follow_up"] == {"operation": "obtain_instance_readings", "source": MONITOR,
                                   "targets": ["order-gateway-1", "order-gateway-2"]}
    assert "Dependency link state is unknown." in report["next_step"]
    assert "reference-db degraded" not in report["next_step"] and "No fault established" not in report["next_step"]
    assert "Investigate the" not in report["next_step"]
    candidate, problem = shift.restart_evidence()
    assert problem == "unsupported"


# --- D: the handover target is an exact observed faulty-link identifier ----------------------------------------

D3_DECORATED = "reference-db (observed degraded at tick 22)"  # slot 14, verbatim


def test_saved_d3_decorated_identifier_is_repaired_then_cited():
    record, fake = live("D", *steps(*TICKS, "links"), {"step": "handover", "target": D3_DECORATED},
                        {"step": "handover", "target": "reference-db"})
    assert len(fake.bodies) == 6 and record["pilot"]["requests_refused"] == 0
    repair = [item for item in fake.bodies[5]["input"] if item.get("type") == "function_call_output"]
    assert repair and 'exactly one of ["reference-db"], or empty' in repair[-1]["output"]
    assert user_json(fake.bodies[4]) == user_json(fake.bodies[5])  # same decision context, one repair
    assert record["completed_model_calls"][-1]["requests"] == 2
    assert record["decisions"][-1] == {"step": "handover", "target": "reference-db"}
    link_ticks = [row["tick"] for row in record["reads_and_actions"] if row.get("target") == "reference-db"]
    assert record["report"]["follow_up"] == {"operation": "investigate_link", "source": "order-gateway",
                                             "target": "reference-db", "observed_tick": link_ticks[-1]}
    assert "model_failure" not in record["report"] and record["passed"] and no_effect(record)


@pytest.mark.parametrize("target", [D3_DECORATED, "matching-engine", "payments-db", "order-gateway-2",
                                    "Reference-DB", " reference-db", "reference-db."],
                         ids=["decorated", "healthy", "unseen", "replica", "case", "space", "suffix"])
def test_an_ineligible_identifier_twice_is_a_safe_handover_without_a_link(target):
    record, fake = live("D", *steps(*TICKS), *[{"step": "handover", "target": target}] * 2)
    assert len(fake.bodies) == 5
    report = record["report"]
    assert report["model_failure"] == "validation_exhausted" and "follow_up" not in report
    assert target.strip() not in report["next_step"] and not record["passed"] and no_effect(record)
    assert [d["step"] for d in record["decisions"]] == list(TICKS)  # the invalid choice was never executed


@pytest.mark.parametrize("target", [D3_DECORATED, "matching-engine"], ids=["decorated", "healthy"])
def test_the_shift_itself_cites_only_an_exact_faulty_link(target):
    """Without the live validator (any decider), the code still matches by exact identity and has no effect."""
    async def decide(context):
        done = context["progress"]["completed_steps"]
        return Decision(step=TICKS[len(done)]) if len(done) < 3 else Decision(step="handover", target=target)

    shift, report = modified("D", lambda sim: decide)
    assert "follow_up" not in report and report["status"] == "needs_operator"
    assert not shift.deps.sim.approvals and not shift.deps.sim.executor.effects()


def test_a_link_is_eligible_only_once_observed():
    record, fake = live("D", *steps("tickets", "instances"), *[{"step": "handover", "target": "reference-db"}] * 2)
    assert sent_progress(fake)[2]["faulty_links"] == []
    assert record["report"]["model_failure"] == "validation_exhausted" and no_effect(record)


def test_the_generic_handover_stays_available_after_a_rejected_target():
    record, _ = live("D", *steps(*TICKS), {"step": "handover", "target": "payments-db"}, {"step": "handover"})
    report = record["report"]
    assert report["next_step"] == "Review current per-instance readings and dependency links before a restart."
    assert "follow_up" not in report and "model_failure" not in report and no_effect(record)


# --- A2: when current observations already support the runbook restart ----------------------------------------

def test_the_restart_cue_appears_once_the_evidence_supports_it_and_grants_nothing():
    """Slot 6's saved choices: the cue is shown, the refreshes still run, and the replay still fails at the cap."""
    saved = steps(*TICKS) + [{"step": "instances", "target": "order-gateway-2"}] * 2 + steps("links")
    record, fake = live("A", *saved)
    cues = [p["restart_supported"] for p in sent_progress(fake)]
    # Shown at decisions 4 and 5. By decision 6 the two refreshes have aged the link reads past five ticks, so
    # the same predicate as the gate withdraws it: the saved final `links` read was then a legitimate refresh.
    assert cues == [None, None, None, "order-gateway-2", "order-gateway-2", None]
    assert tools(record).count(MONITOR) == 6 and record["pilot"]["requests_refused"] == 1
    assert record["report"]["next_step"].startswith("Provider request cap reached")
    assert not record["passed"] and no_effect(record)


@pytest.mark.parametrize("choices", [TICKS + ("restart",), TICKS + ("instances", "restart")],
                         ids=["restart-at-cue", "A1-refresh-then-restart"])
def test_restart_at_the_cue_or_after_a_valid_refresh_passes_the_existing_gates(choices):
    answers = [{"step": s, "target": "order-gateway-2" if s == "restart" else ""} for s in choices]
    record, fake = live("A", *answers)
    assert sent_progress(fake)[-1]["restart_supported"] == "order-gateway-2"
    assert "stale_evidence" not in record["report"]  # a current refresh is progress, not a stall
    assert record["passed"] and record["applied_effects"] == 1 and record["report"]["status"] == "recovered"
    assert tools(record).count("request_approval") == 1 and record["report"]["action"]["approval"]


def test_stale_or_expired_evidence_shows_no_cue_and_the_gate_agrees():
    shown = []

    def until_expired(sim):
        async def decide(context):
            progress = context["progress"]
            shown.append(progress["restart_supported"])
            if progress["completed_steps"].get("links") is None:
                return Decision(step=TICKS[len(progress["completed_steps"])])
            # Read tickets until the instance and link reads age out, then ask for the restart anyway.
            return Decision(step="restart" if shown[-1] is None else "tickets", target="order-gateway-2")
        return decide

    shift, report = modified("A", until_expired)
    assert shown[3] == "order-gateway-2" and shown[-1] is None
    assert report["next_step"] == "Read the instance and dependency measurements again before acting."
    assert not shift.deps.sim.approvals and not shift.deps.sim.executor.effects()

    stale_case = load_scenario(demo.CASES["A"]).tools | {"metric_collector": {"component": "order-gateway",
                                                                             "last_poll_tick": 14}}
    shown.clear()
    shift, report = modified("A", until_expired, tools=stale_case)
    assert set(shown) == {None} and report["observations"]["instances"]["order-gateway-2"]["memory_pct"] > 90
    assert report["next_step"].startswith("No supported restart.") and not shift.deps.sim.approvals


# --- A3: why a decision failed, as a bounded code ---------------------------------------------------------------

LIMIT = dict(status="incomplete", reason="max_output_tokens", output_tokens=512)
INVALID = Wire('{"step": "reboot-raw-output"}', output_tokens=512)
TRUNCATED = Wire('{"step": "truncated-raw-out', **LIMIT)
RAW = ("Exceeded maximum", "Model token limit", "Content filter", "sk-not-for-traces", "raw-out")  # SDK and provider text


@pytest.mark.parametrize("final, code, sent", [
    ((Wire(reasoning=True, **LIMIT),), "output_limit", 4),               # the slot-11 shape: no repair is attempted
    ((TRUNCATED, TRUNCATED), "output_limit", 5),
    ((INVALID, INVALID), "validation_exhausted", 5),                     # 512 output tokens, but completed
    ((Wire(output_tokens=512), Wire(output_tokens=512)), "validation_exhausted", 5),  # no call at the ceiling
    ((Wire(reasoning=True, status=None, output_tokens=512),) * 2, "unknown", 5),      # no status: ambiguous
    ((Wire(reasoning=True, status="incomplete", reason="content_filter"),), "unknown", 4),
    ((TRUNCATED, INVALID), "unknown", 5),                                # the earlier limit is not carried over
    ((INVALID, TRUNCATED), "output_limit", 5),                           # the final explicit limit is definitive
    ((TRUNCATED, 500), "provider_error", 5),
    ((503,), "provider_error", 4),
], ids=["reasoning-at-limit", "truncated-call", "invalid-at-512", "empty-at-512", "no-status", "content-filter",
        "limit-then-invalid", "invalid-then-limit", "limit-then-500", "503"])
def test_a_failed_decision_is_handed_over_with_a_bounded_reason(final, code, sent):
    record, fake = live("A", *steps(*TICKS), *final)
    assert len(fake.bodies) == sent and record["pilot"]["requests_refused"] == 0
    report = record["report"]
    assert report["model_failure"] == code
    assert report["next_step"] == f"{MODEL_FAILURES[code]} No effect. Review the saved evidence."
    assert no_effect(record) and [d["step"] for d in record["decisions"]] == list(TICKS)
    if code == "output_limit":
        last = record["pilot"]["attempts"][-1]
        assert (last["response_status"], last["incomplete_reason"], last["output_tokens"]) == (
            "incomplete", "max_output_tokens", 512)
    assert not [raw for raw in RAW if raw in json.dumps(record)]


def test_a_valid_completed_answer_at_the_output_limit_is_a_decision():
    record, _ = live("A", *steps(*TICKS), Wire('{"step": "restart", "target": "order-gateway-2"}', output_tokens=512))
    last = record["pilot"]["attempts"][-1]
    assert (last["status"], last["response_status"], last["output_tokens"]) == (200, "completed", 512)
    assert "model_failure" not in record["report"] and record["passed"]


@pytest.mark.parametrize("first, second, code", [
    ((INVALID, {"step": "instances"}), (503,), "provider_error"),
    ((TRUNCATED, {"step": "instances"}), (INVALID, INVALID), "validation_exhausted"),
    ((INVALID, {"step": "instances"}), (Wire(reasoning=True, status="incomplete", reason="content_filter"),), "unknown"),
], ids=["repaired-then-503", "limit-repaired-then-invalid", "repaired-then-content-filter"])
def test_a_repaired_decision_succeeds_and_leaves_no_reason_for_the_next(first, second, code):
    record, _ = live("A", {"step": "tickets"}, *first, *second)
    assert [d["step"] for d in record["decisions"]] == ["tickets", "instances"]
    assert record["completed_model_calls"][1]["requests"] == 2  # the repaired decision completed
    assert record["report"]["model_failure"] == code and no_effect(record)


def test_a_refused_repair_is_still_the_request_cap():
    record, fake = live("A", INVALID, {"step": "tickets"}, max_requests=1)
    assert len(fake.bodies) == 1 and record["pilot"]["requests_refused"] == 1
    assert record["report"]["next_step"].startswith("Provider request cap reached (1 requests sent).")
    assert "model_failure" not in record["report"] and no_effect(record)
