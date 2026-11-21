"""The single-case pilot, offline: CLI validation, the shared request cap, and per-request output limits.

A mock HTTP transport stands in for the Responses API. No key, network, or provider charge.
"""

import asyncio
import json

import httpx2
import pytest
from openai import AsyncOpenAI, APIStatusError

import demo
from pilot import Pilot, ProviderBudget

MODEL = "pilot-test-model"  # a placeholder: no model has been chosen for the paid pilot


class FakeResponses:
    """Answers each request in turn. A dict is a decision; an int is an error status; an exception is raised."""

    def __init__(self, *answers, usage=True):
        self.answers = list(answers)
        self.bodies = []
        self.usage = usage  # False: successful responses carry no usage field

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
            "model": f"{MODEL}-2026-11-01", "parallel_tool_calls": True, "tool_choice": "required", "tools": [],
            "output": [{"type": "function_call", "id": f"fc_{len(self.bodies)}", "call_id": f"call_{len(self.bodies)}",
                        "name": tool, "arguments": json.dumps(answer), "status": "completed"}]}
        if self.usage:
            body["usage"] = {"input_tokens": 100 + len(self.bodies), "output_tokens": 10,
                             "total_tokens": 110 + len(self.bodies)}
        return httpx2.Response(200, json=body)


def pilot_with(fake, max_requests=3, max_output_tokens=64):
    return Pilot(MODEL, max_requests=max_requests, max_output_tokens=max_output_tokens,
                 api_key="test-key-not-a-secret", transport=httpx2.MockTransport(fake))


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
], ids=["no-case-or-limits", "no-output-limit", "no-case", "zero-requests", "negative-output",
        "non-numeric", "unknown-case", "no-model-flag", "limit-without-live"])
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
    recorded = (demo.HERE / "offline-traces-m1.5.jsonl").read_text(encoding="utf-8").splitlines()
    assert asyncio.run(demo.main([])) == 0
    assert capsys.readouterr().out.splitlines() == recorded
    assert asyncio.run(demo.main(["--case", "b"])) == 0
    assert capsys.readouterr().out.splitlines() == [line for line in recorded if '"case": "shift-b"' in line]


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
        built.append(pilot_with(fake, **limits))
        return built[-1]

    monkeypatch.setattr(demo, "Pilot", build)
    return asyncio.run(demo.main(argv)), order, built


def test_valid_live_command_uses_openai_model_and_runs_only_the_selected_case(monkeypatch, capsys):
    fake = FakeResponses({"step": "tickets"}, {"step": "instances"})
    argv = ["--live", "--case", "C", "--max-requests", "2", "--max-output-tokens", "32"]
    code, order, (pilot,) = live_main(monkeypatch, argv, fake, f"  {MODEL} ")
    assert code == 1  # C expects a verified restart; the pilot stopped first
    assert order == ["key", ("provider", MODEL, {"max_requests": 2, "max_output_tokens": 32})]
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
    assert run["attempts"] == [{"status": 200, "model": f"{MODEL}-2026-11-01", "input_tokens": None, "output_tokens": None}]
    assert run["reported_input_tokens"] is None and run["reported_output_tokens"] is None


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
                                "input_tokens": None, "output_tokens": None}]
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
