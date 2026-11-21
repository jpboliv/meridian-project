"""The single-case pilot, offline: CLI validation, the shared request cap, and per-request output limits.

A mock HTTP transport stands in for the Responses API. No key, network, or provider charge.
"""

import asyncio
import json
import statistics

import httpx2
import pytest
from meridian.scenarios import load_scenario
from openai import AsyncOpenAI, APIStatusError

import demo
from pilot import ARMS, Pilot, ProviderBudget, with_current_time

MODEL = "pilot-test-model"  # a placeholder: no model has been chosen for the paid pilot


class FakeResponses:
    """Answers each request in turn. A dict is a decision; an int is an error status; an exception is raised.

    `details` gives `usage.input_tokens_details` for each successful response in turn; `...` omits the field."""

    def __init__(self, *answers, usage=True, details=()):
        self.answers = list(answers)
        self.bodies = []
        self.usage = usage  # False: successful responses carry no usage field
        self.details = list(details)

    def __call__(self, request):
        body = json.loads(request.content)
        self.bodies.append(body)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, int):
            return httpx2.Response(answer, headers={"retry-after-ms": "1"},  # keeps any SDK retry fast
                                   json={"error": {"message": "upstream detail sk-not-for-traces"}})
        tool = body["tools"][0]["name"]  # the output tool the agent declared
        body = {
            "id": f"resp_{len(self.bodies)}", "object": "response", "created_at": 1763700000, "status": "completed",
            "model": f"{body['model']}-2026-11-01", "parallel_tool_calls": True, "tool_choice": "required", "tools": [],
            "output": [{"type": "function_call", "id": f"fc_{len(self.bodies)}", "call_id": f"call_{len(self.bodies)}",
                        "name": tool, "arguments": json.dumps(answer), "status": "completed"}]}
        if self.usage:
            body["usage"] = {"input_tokens": 100 + len(self.bodies), "output_tokens": 10,
                             "total_tokens": 110 + len(self.bodies)}
            details = self.details.pop(0) if self.details else ...
            if details is not ...:
                body["usage"]["input_tokens_details"] = details
        return httpx2.Response(200, json=body)


def pilot_with(fake, max_requests=3, max_output_tokens=64, arm=None, model=MODEL):
    return Pilot(model, max_requests=max_requests, max_output_tokens=max_output_tokens, arm=arm,
                 api_key="test-key-not-a-secret", transport=httpx2.MockTransport(fake))


def user_json(body):
    """The decision context as sent: the text of the first user message on the wire."""
    item = next(item for item in body["input"] if item.get("role") == "user")
    content = item["content"]
    return content if isinstance(content, str) else "".join(part["text"] for part in content)


LIVE_A = ["--live", "--case", "A", "--max-requests", "3", "--max-output-tokens", "64"]


@pytest.mark.parametrize("argv", [
    ["--live"],
    ["--live", "--case", "A", "--max-requests", "3"],
    ["--live", "--max-requests", "3", "--max-output-tokens", "64"],
    ["--live", "--case", "A", "--max-requests", "0", "--max-output-tokens", "64"],
    ["--live", "--case", "A", "--max-requests", "3", "--max-output-tokens", "-1"],
    ["--live", "--case", "A", "--max-requests", "two", "--max-output-tokens", "64"],
    ["--live", "--case", "F", "--max-requests", "3", "--max-output-tokens", "64"],
    [*LIVE_A, "--model", MODEL],
    ["--case", "A", "--max-requests", "3"],
    ["--case", "A", "--reuse-arm", "time-last"],
    [*LIVE_A, "--reuse-arm", "time-middle"],
    [*LIVE_A, "--reuse-arm", "time-first-no-cache"],
], ids=["no-case-or-limits", "no-output-limit", "no-case", "zero-requests", "negative-output",
        "non-numeric", "unknown-case", "no-model-flag", "limit-without-live", "arm-without-live",
        "unknown-arm", "no-factorial-arm"])
def test_invalid_live_command_stops_before_any_key_or_client(argv, monkeypatch):
    touched = []
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(demo, "require_api_key", lambda: touched.append("key"))
    monkeypatch.setattr(demo, "Pilot", lambda *a, **k: touched.append("provider"))
    monkeypatch.setattr(demo, "run_case", lambda *a, **k: touched.append("case"))
    with pytest.raises(SystemExit) as stop:
        asyncio.run(demo.main(argv))
    assert stop.value.code == 2 and touched == []


def test_offline_runs_all_five_cases_or_one_unchanged(capsys):
    recorded = (demo.HERE / "offline-traces-m1.6.jsonl").read_text(encoding="utf-8").splitlines()
    assert asyncio.run(demo.main([])) == 0
    assert capsys.readouterr().out.splitlines() == recorded
    assert asyncio.run(demo.main(["--case", "b"])) == 0
    assert capsys.readouterr().out.splitlines() == [line for line in recorded if '"case": "shift-b"' in line]
    # m1.6 changed only the decision context and live instructions: scripted runs keep every m1.5 outcome.
    earlier = (demo.HERE / "offline-traces-m1.5.jsonl").read_text(encoding="utf-8").splitlines()
    strip = lambda line: {k: v for k, v in json.loads(line).items() if k not in ("revision", "harness_sha256")}
    assert [strip(line) for line in recorded] == [strip(line) for line in earlier]


def live_main(monkeypatch, argv, fake, env_model):
    """Run the CLI with the key loader stubbed (no .env is read) and the provider on a mock transport."""
    order, built = [], []
    if env_model is None:
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
    else:
        monkeypatch.setenv("OPENAI_MODEL", env_model)
    monkeypatch.setattr(demo, "require_api_key", lambda: order.append("key"))

    def build(model_name, **limits):
        order.append(("provider", model_name, limits))
        built.append(pilot_with(fake, model=model_name, **limits))
        return built[-1]

    monkeypatch.setattr(demo, "Pilot", build)
    return asyncio.run(demo.main(argv)), order, built


def test_valid_live_command_uses_openai_model_and_runs_only_the_selected_case(monkeypatch, capsys):
    fake = FakeResponses({"step": "tickets"}, {"step": "instances"})
    argv = ["--live", "--case", "C", "--max-requests", "2", "--max-output-tokens", "32"]
    code, order, (pilot,) = live_main(monkeypatch, argv, fake, f"  {MODEL} ")
    assert code == 1  # C expects a verified restart; the pilot stopped first
    assert order == ["key", ("provider", MODEL, {"max_requests": 2, "max_output_tokens": 32, "arm": None})]
    assert all("current_time" not in json.loads(user_json(body)) for body in fake.bodies)  # baseline layout
    assert all("prompt_cache_options" not in body for body in fake.bodies)
    assert pilot.client.is_closed()
    record, = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert record["case"] == "shift-c" and record["model"] == MODEL and record["pilot"]["configured_model"] == MODEL
    assert record["report"]["status"] == "needs_operator" and record["applied_effects"] == 0
    assert record["pilot"]["max_requests"] == 2 and record["pilot"]["max_output_tokens_per_request"] == 32
    assert (record["pilot"]["requests_sent"], record["pilot"]["requests_refused"]) == (2, 1)


@pytest.mark.parametrize("env_model", [None, "", "   "], ids=["unset", "empty", "blank"])
def test_live_command_without_a_model_stops_before_the_provider(env_model, monkeypatch, capsys):
    with pytest.raises(SystemExit) as stop:
        live_main(monkeypatch, LIVE_A, FakeResponses(), env_model)
    assert "OPENAI_MODEL is not set" in str(stop.value.code)
    assert capsys.readouterr().out == ""


def test_live_client_is_closed_after_a_harness_error(monkeypatch):
    built = []

    def build(model_name, **limits):
        built.append(pilot_with(FakeResponses(), **limits))
        return built[-1]

    async def broken(path, pilot):
        raise RuntimeError("simulated harness failure")

    monkeypatch.setenv("OPENAI_MODEL", MODEL)
    monkeypatch.setattr(demo, "require_api_key", lambda: None)
    monkeypatch.setattr(demo, "Pilot", build)
    monkeypatch.setattr(demo, "run_case", broken)
    with pytest.raises(RuntimeError):
        asyncio.run(demo.main(LIVE_A))
    assert built[0].client.is_closed()


def test_successful_response_without_usage_is_unknown_not_zero():
    fake = FakeResponses({"step": "tickets"}, usage=False)
    pilot = pilot_with(fake, max_requests=1)
    record = asyncio.run(demo.run_case(demo.CASES["A"], pilot))
    call, = record["completed_model_calls"]
    assert call == {"model": f"{MODEL}-2026-11-01", "requests": 1, "input_tokens": None, "output_tokens": None}
    run = record["pilot"]
    assert run["attempts"] == [{"status": 200, "model": f"{MODEL}-2026-11-01", "input_tokens": None, "output_tokens": None,
                                "cached_tokens": None, "cache_write_tokens": None}]
    assert run["reported_input_tokens"] is None and run["reported_output_tokens"] is None
    assert run["reported_cached_tokens"] is None and run["reported_cache_write_tokens"] is None


def test_request_cap_spans_decisions_and_output_repairs():
    # Decision 1 needs a repair (an invalid step, then a valid one); decision 2 takes the third request.
    fake = FakeResponses({"step": "reboot"}, {"step": "tickets"}, {"step": "instances"}, {"step": "links"})
    pilot = pilot_with(fake, max_requests=3, max_output_tokens=48)
    record = asyncio.run(demo.run_case(demo.CASES["A"], pilot))
    assert len(fake.bodies) == 3 and fake.answers == [{"step": "links"}]  # the fourth request was never sent
    assert all(body["max_output_tokens"] == 48 for body in fake.bodies)
    assert [d["step"] for d in record["decisions"]] == ["tickets", "instances"]
    run = record["pilot"]
    assert (run["requests_sent"], run["requests_refused"], run["requests_without_usage"]) == (3, 1, 0)
    assert [a["output_tokens"] for a in run["attempts"]] == [10, 10, 10]  # includes the rejected first answer
    assert (run["reported_input_tokens"], run["reported_output_tokens"]) == (306, 30)
    assert run["attempts"][0]["model"] == f"{MODEL}-2026-11-01"
    assert [c["requests"] for c in record["completed_model_calls"]] == [2, 1]
    assert record["completed_model_calls"][0]["output_tokens"] == 20  # known usage is kept
    assert record["report"]["status"] == "needs_operator" and record["report"]["action"] is None
    assert record["report"]["next_step"].startswith("Provider request cap reached (3 requests sent).")
    assert "unavailable" not in record["report"]["next_step"]
    assert record["applied_effects"] == 0 and "recovery" not in record["report"]["observations"]


@pytest.mark.parametrize("failure", [503, 429, httpx2.ConnectError("connection reset")], ids=["503", "429", "connect"])
def test_retryable_provider_failure_is_sent_once_and_handed_over(failure):
    fake = FakeResponses(failure, {"step": "tickets"})
    pilot = pilot_with(fake)
    record = asyncio.run(demo.run_case(demo.CASES["A"], pilot))
    assert len(fake.bodies) == 1  # SDK retries are off
    run = record["pilot"]
    assert run["requests_sent"] == 1 and run["requests_refused"] == 0
    assert run["attempts"] == [{"status": failure if isinstance(failure, int) else None, "model": None,
                                "input_tokens": None, "output_tokens": None,
                                "cached_tokens": None, "cache_write_tokens": None}]
    assert run["reported_cached_tokens"] is None and run["reported_cache_write_tokens"] is None
    assert run["requests_without_usage"] == 1
    assert run["reported_input_tokens"] is None and run["reported_output_tokens"] is None  # unknown, not zero
    assert record["completed_model_calls"] == [] and record["decisions"] == []
    assert record["report"]["status"] == "needs_operator" and record["applied_effects"] == 0
    assert record["report"]["next_step"].startswith("Model unavailable")  # a provider failure, not the cap
    assert "sk-not-for-traces" not in json.dumps(record) and "connection reset" not in json.dumps(record)


def test_sdk_retries_would_still_count_against_the_cap():
    """The cap is on HTTP requests, so even a client with SDK retries enabled cannot exceed it."""
    fake = FakeResponses(500, 500, 500)
    budget = ProviderBudget(max_requests=2)
    client = AsyncOpenAI(api_key="test-key-not-a-secret", max_retries=2,
                         http_client=budget.client(httpx2.MockTransport(fake)))

    async def ask():
        with pytest.raises(Exception) as failure:
            await client.with_options(timeout=5).responses.create(model=MODEL, input="ping", max_output_tokens=8)
        return failure.value

    error = asyncio.run(ask())
    assert not isinstance(error, APIStatusError)  # the third attempt was refused locally, not answered
    assert len(fake.bodies) == 2 and budget.refused == 1
    assert [a["status"] for a in budget.attempts] == [500, 500]


# --- #21: timestamp arms, the no-cache arm, and provider-reported cache usage -------------------------------

LUNA = "gpt-6-luna"  # the owner's chosen model; the mock transport stands in for it, so nothing is called
RESTART_A = ({"step": "tickets"}, {"step": "instances"}, {"step": "links"},
             {"step": "restart", "target": "order-gateway-2"})


def run_arm(arm, *answers, max_requests=4, details=()):
    fake = FakeResponses(*answers, details=details)
    record = asyncio.run(demo.run_case(demo.CASES["A"], pilot_with(fake, max_requests, arm=arm, model=LUNA)))
    return record, fake


def test_arms_send_the_same_data_with_the_current_simulated_time_first_or_last():
    runs = {arm: run_arm(arm, *RESTART_A) for arm in (None, *ARMS)}
    baseline, base_fake = runs[None]
    sent_base = [user_json(body) for body in base_fake.bodies]
    assert len(sent_base) == 4 and all("current_time" not in json.loads(text) for text in sent_base)
    for arm, (record, fake) in runs.items():
        # Same decisions, reads, effects, and verified report in every arm: only the request layout differs.
        assert record["passed"] and record["applied_effects"] == 1
        for key in ("decisions", "reads_and_actions", "report", "end_tick"):
            assert record[key] == baseline[key], (arm, key)
        assert "current_time" not in json.dumps(record["report"])  # stored observations are not changed
        assert record["pilot"]["arm"] == arm
        if arm is None:
            continue
        sent = [user_json(body) for body in fake.bodies]
        times = [json.loads(text)["current_time"] for text in sent]
        assert times == sorted(times) and len(set(times)) == len(times)  # read again at each decision
        position = ARMS[arm][0]
        for text, base, now in zip(sent, sent_base, times):
            field = f'"current_time": "{now}"'
            # Byte-for-byte the baseline JSON with one field added at the start or end.
            assert text == ("{" + field + ", " + base[1:] if position == "first" else base[:-1] + ", " + field + "}")
            data = json.loads(text)
            assert list(data)[0 if position == "first" else -1] == "current_time"
            assert data["incident"] == json.loads(base)["incident"]  # the incident's own time is unchanged
        # The alert stays at 10:05; the runbook read has already moved the clock before the first decision.
        assert json.loads(sent[0])["incident"]["time"] == "10:05" and times[0] == "10:06"


def substance(body):
    """The request without its cache mode or the SDK's incidental cache-diagnostic reference."""
    body = json.loads(json.dumps(body))
    options = body.pop("prompt_cache_options", {})
    options.pop("mode", None)
    options.pop("comparison_response_id", None)
    if options:
        body["prompt_cache_options"] = options
    return body


@pytest.mark.parametrize("answers, repair", [(RESTART_A, False),
                                             (({"step": "reboot"}, {"step": "tickets"}, {"step": "instances"}), True)],
                         ids=["four-decisions", "output-repair"])
def test_no_cache_arm_sends_the_control_request_with_explicit_mode_and_no_breakpoints(answers, repair):
    control, control_fake = run_arm("time-last", *answers, max_requests=len(answers))
    no_cache, fake = run_arm("time-last-no-cache", *answers, max_requests=len(answers))
    assert len(fake.bodies) == len(control_fake.bodies) == len(answers)
    if repair:  # the second request repairs the first decision's invalid output, at the same simulated time
        assert any(item.get("type") == "function_call_output" for item in fake.bodies[1]["input"])
        assert user_json(fake.bodies[0]) == user_json(fake.bodies[1])
    for body, control_body in zip(fake.bodies, control_fake.bodies):
        assert body["prompt_cache_options"]["mode"] == "explicit"  # on every request, repairs included
        assert control_body.get("prompt_cache_options", {}).get("mode") is None  # provider default (implicit)
        wire = json.dumps(body)
        for marker in ("prompt_cache_breakpoint", "prompt_cache_key", "prompt_cache_retention", '"ttl"'):
            assert marker not in wire and marker not in json.dumps(control_body)
        # With the same fixed decisions: same instructions, messages, tools, output limit, and simulated time.
        assert substance(body) == substance(control_body)
    for key in ("decisions", "reads_and_actions", "report"):
        assert no_cache[key] == control[key]
    assert no_cache["pilot"]["prompt_cache_options"] == {"mode": "explicit"}
    assert control["pilot"]["prompt_cache_options"] is None


@pytest.mark.parametrize("model", [MODEL, "gpt-4.1-mini", "gpt-5.6", "gpt-6-lunar", "gpt-6-luna-2026-11-01",
                                   "GPT-6-LUNA"])
def test_no_cache_arm_on_an_unconfirmed_model_stops_before_any_request(model, monkeypatch, capsys):
    fake = FakeResponses(*RESTART_A)
    with pytest.raises(SystemExit) as stop:
        live_main(monkeypatch, [*LIVE_A, "--reuse-arm", "time-last-no-cache"], fake, model)
    assert "supported only for gpt-6-luna" in str(stop.value.code)
    assert fake.bodies == [] and capsys.readouterr().out == ""  # no fallback to default caching


def test_rejected_no_cache_setting_is_not_retried_without_it_or_counted_as_a_hit():
    record, fake = run_arm("time-last-no-cache", 400, *RESTART_A)
    assert len(fake.bodies) == 1 and fake.bodies[0]["prompt_cache_options"] == {"mode": "explicit"}
    run = record["pilot"]
    assert run["attempts"][0]["status"] == 400 and run["attempts"][0]["cached_tokens"] is None
    assert run["reported_cached_tokens"] is None and run["reported_cache_write_tokens"] is None
    assert record["report"]["next_step"].startswith("Model unavailable") and record["applied_effects"] == 0


def test_cache_reads_and_writes_are_recorded_per_attempt_and_totalled_separately():
    details = [{"cached_tokens": 0, "cache_write_tokens": 0},  # zero is a reported result
               {"cached_tokens": 64},                          # write count omitted: unknown
               {"cached_tokens": 64, "cache_write_tokens": 32}]  # 96 of 103 input tokens: consistent
    record, _ = run_arm("time-last", *RESTART_A[:3], max_requests=3, details=details)
    run = record["pilot"]
    assert [(a["input_tokens"], a["cached_tokens"], a["cache_write_tokens"]) for a in run["attempts"]] == [
        (101, 0, 0), (102, 64, None), (103, 64, 32)]
    assert run["reported_input_tokens"] == 306  # cache counts are part of input tokens, not added to them
    # The read total stays known although one write count is missing; the write total does not.
    assert run["reported_cached_tokens"] == 128 and run["reported_cache_write_tokens"] is None
    assert not [key for key in run if any(word in key for word in ("cost", "price", "hit", "saving"))]
    assert run["started_at_utc"].endswith("+00:00")  # wall-clock start, so trial order can be reconstructed


@pytest.mark.parametrize("details, inconsistent", [
    ({"cached_tokens": 60, "cache_write_tokens": 41}, False),  # 101 of 101: valid, no ordinary input left
    ({"cached_tokens": 61, "cache_write_tokens": 41}, True),   # 102 of 101: each valid, the pair is not
], ids=["sum-equals-input", "sum-exceeds-input"])
def test_a_read_and_write_pair_above_input_tokens_is_unknown(details, inconsistent):
    record, _ = run_arm("time-last", {"step": "tickets"}, max_requests=1, details=[details])
    attempt, = record["pilot"]["attempts"]
    expected = (None, None) if inconsistent else (details["cached_tokens"], details["cache_write_tokens"])
    assert (attempt["cached_tokens"], attempt["cache_write_tokens"]) == expected
    assert attempt["input_tokens"] == record["pilot"]["reported_input_tokens"] == 101
    assert (record["pilot"]["reported_cached_tokens"], record["pilot"]["reported_cache_write_tokens"]) == expected


@pytest.mark.parametrize("details", [..., None, "12", {"cached_tokens": None}, {"cached_tokens": "12"},
                                     {"cached_tokens": -1}, {"cached_tokens": True}, {"cached_tokens": 1.5},
                                     {"cached_tokens": 102}],
                         ids=["no-details", "null-details", "string-details", "null", "string", "negative",
                              "bool", "float", "more-than-input"])
@pytest.mark.filterwarnings("ignore")  # the SDK warns about the deliberately invalid usage values
def test_missing_or_invalid_cache_reads_stay_unknown(details):
    record, _ = run_arm("time-last", {"step": "tickets"}, max_requests=1, details=[details])
    run = record["pilot"]
    assert run["attempts"][0]["input_tokens"] == 101 and run["attempts"][0]["cached_tokens"] is None
    assert run["reported_input_tokens"] == 101 and run["reported_cached_tokens"] is None


def test_offline_prefix_overlap_matches_the_issue_21_measurement():
    """Scripted A-E decisions with the arm's layout: identical leading UTF-8 bytes of consecutive user JSON.
    This reproduces the 13-pair byte check recorded on #21. It measures bytes, not tokens or cache hits."""
    async def overlaps(position):
        pairs = []
        for path in demo.CASES.values():
            sim, sent = demo.start_exchange(path), []

            async def decide(context):
                now = sim.clock.label(sim.state.tick)
                sent.append(json.dumps(with_current_time(context, now, position)).encode())
                return await demo.scripted(context)
            identity = demo.identity_for(sim.scenario.actor["role"])
            await demo.Shift(demo.IncidentDeps(demo.MeridianTools(sim, actor=identity["name"]),
                                               identity=identity)).run(decide)
            pairs += [next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
                      for a, b in zip(sent, sent[1:])]
        return pairs

    first, last = asyncio.run(overlaps("first")), asyncio.run(overlaps("last"))
    assert len(first) == len(last) == 13
    assert (min(first), statistics.median(first), max(first)) == (21, 22, 22)
    assert (min(last), statistics.median(last), max(last)) == (821, 920, 1315)


# --- #13: what each live decision sees after the ticket read (gateway-m1.6) ----------------------------------
# The mock replays chosen decisions. A mocked pass shows what the harness permits, not what a model would choose.

def sent_progress(fake):
    return [json.loads(user_json(body))["progress"] for body in fake.bodies]


TICKET_STATES = ("not searched", "matched", "no match")


def test_recorded_pilot_choices_now_see_the_matched_ticket_and_still_fail():
    """The 21 November pilot's three `tickets` choices, replayed under its limits (cap 3, 512 output tokens)."""
    fake = FakeResponses(*[{"step": "tickets"}] * 4)
    record = asyncio.run(demo.run_case(demo.CASES["B"], pilot_with(fake, 3, 512, model=LUNA)))
    assert len(fake.bodies) == 3
    for body in fake.bodies:
        # The rule, not its wording: no unconditional "start with the ticket", and every cue state is explained.
        assert "Start by correlating" not in body["instructions"]
        assert all(f'"{state}"' in body["instructions"] for state in TICKET_STATES)
        assert list(json.loads(user_json(body)))[-1] == "progress"  # after the stable prefix and observations
    assert sent_progress(fake) == [
        {"ticket": "not searched", "completed_steps": {}},
        {"ticket": "matched", "completed_steps": {"tickets": 1}},
        {"ticket": "matched", "completed_steps": {"tickets": 2}}]
    assert user_json(fake.bodies[1]) != user_json(fake.bodies[2])  # byte-identical under m1.5
    # Nothing routes the run: repeated choices are executed, spend the cap, and the case still fails.
    assert [d["step"] for d in record["decisions"]] == ["tickets"] * 3
    assert record["pilot"]["requests_refused"] == 1 and not record["passed"] and record["applied_effects"] == 0
    assert record["report"]["next_step"].startswith("Provider request cap reached (3 requests sent).")


@pytest.mark.parametrize("steps", [("tickets", "instances"), ("tickets", "links", "instances")],
                         ids=["monitor-next", "link-next"])
def test_an_alternate_next_read_proceeds_within_the_same_cap(steps):
    fake = FakeResponses(*[{"step": step} for step in steps])
    record = asyncio.run(demo.run_case(demo.CASES["B"], pilot_with(fake, 3, 512, model=LUNA)))
    assert [d["step"] for d in record["decisions"]] == list(steps) and record["pilot"]["requests_refused"] == 0
    assert record["passed"] and record["applied_effects"] == 0  # mocked choices: not model evidence
    assert all(p["ticket"] == "matched" for p in sent_progress(fake)[1:])
    assert record["report"]["follow_up"]["targets"] == ["order-gateway-1", "order-gateway-2"]
    if "links" in steps[:-1]:  # one completed links step, although it made two check_link calls
        assert sent_progress(fake)[-1] == {"ticket": "matched", "completed_steps": {"tickets": 1, "links": 1}}
        tools = [row["tool"] for row in record["reads_and_actions"]]
        assert tools[:tools.index("deployments.get_service")].count("check_link") == 2


@pytest.mark.parametrize("tickets", [[], [{"at": 14, "key": "MRX-4101", "component": "order-gateway",
                                          "summary": "New operator access request"}]],
                         ids=["no-tickets", "unrelated-ticket"])
def test_an_empty_or_unmatched_search_is_not_called_matched_and_can_be_repeated(tickets):
    case = load_scenario(demo.CASES["B"])
    case.tickets = tickets
    sim = demo.start_exchange(case)
    identity = demo.identity_for(sim.scenario.actor["role"])
    shift = demo.Shift(demo.IncidentDeps(demo.MeridianTools(sim, actor=identity["name"]), identity=identity))
    fake = FakeResponses({"step": "tickets"}, {"step": "tickets"}, {"step": "handover"})
    report = asyncio.run(shift.run(pilot_with(fake, 3, 512, model=LUNA).decider([])))
    assert report["observations"]["tickets"] == []
    assert sent_progress(fake) == [
        {"ticket": "not searched", "completed_steps": {}},
        {"ticket": "no match", "completed_steps": {"tickets": 1}},
        {"ticket": "no match", "completed_steps": {"tickets": 2}}]
    assert sum(c.tool == "tickets.search_issues" for c in shift.tools.trace) == 2  # the repeat was not blocked
    assert report["status"] == "needs_operator" and not sim.executor.effects()
