"""Bounds for one live case: a provider request cap and a per-request output limit.

Every HTTP request the OpenAI client sends passes through `ProviderBudget`. That includes each decision,
each output-validation repair, and any SDK retry, so the cap counts what reaches the provider. The SDK's own
retries are also switched off. When the cap is reached, the next request is refused before it is sent, and
the decision raises `RequestCapStop`. The caller hands over with a reason that names the cap.

`max_output_tokens` is set on every request. It limits each response, so a case produces at most
`max_requests × max_output_tokens` output tokens. Input tokens are measured, not capped.

Provider prompt caching (#21) is observed, not simulated. Each attempt records the provider-reported
`usage.input_tokens_details.cached_tokens` and `cache_write_tokens`. The OpenAI prompt-caching guide describes
them as disjoint subsets of `input_tokens`, so they are never added to it. A missing, invalid, inconsistent, or
failed report stays unknown (`None`), and no price is applied.

Without an arm, requests use the baseline layout. Each opt-in #21 arm (`ARMS`) adds the current simulated time
first or last in each decision's user JSON. `time-last-no-cache` sends the same request as `time-last` with
`prompt_cache_options={"mode": "explicit"}` and no breakpoint, which turns off cache reads and writes. It is
accepted only for the exact model name `gpt-6-luna` on the Responses API.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import httpx2
from openai import AsyncOpenAI
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

from shift import live_decider

USAGE = ("input_tokens", "output_tokens")
CACHE_USAGE = ("cached_tokens", "cache_write_tokens")  # under usage.input_tokens_details
# #21 arms: where the current simulated time goes, and the prompt-cache options sent (None: provider default).
ARMS = {"time-first": ("first", None), "time-last": ("last", None),
        "time-last-no-cache": ("last", {"mode": "explicit"})}
NO_CACHE_MODELS = ("gpt-6-luna",)  # exact model names; the no-cache arm is refused for any other, before a send


def count(value):
    """A provider-reported token count, or None if it is missing or not a non-negative whole number."""
    return value if type(value) is int and value >= 0 else None


def with_current_time(context: dict, now: str, position: str) -> dict:
    """A new decision context with `current_time` as its first or last key. The stored context is not changed."""
    return {"current_time": now, **context} if position == "first" else {**context, "current_time": now}


class RequestCapReached(httpx2.RequestError):
    """Raised before sending: the refused request never reaches the provider."""


class RequestCapStop(Exception):
    """A decision could not finish within the case's request cap. Not an `AgentRunError`, so the shift does
    not report it as an unavailable model; the caller reports the cap instead."""

    def __init__(self, max_requests: int):
        super().__init__(f"Provider request cap reached ({max_requests} requests sent). "
                         "No further model request was made. Review the saved evidence.")


class ProviderBudget:
    def __init__(self, max_requests: int):
        self.max_requests = max_requests
        self.attempts: list[dict] = []  # one row per request sent: status and provider-reported usage, else None
        self.refused = 0
        self._open: dict[int, dict] = {}

    async def before_send(self, request):
        if len(self.attempts) >= self.max_requests:
            self.refused += 1
            raise RequestCapReached("provider request cap reached", request=request)
        row = {"status": None, "model": None, **dict.fromkeys(USAGE + CACHE_USAGE)}
        self.attempts.append(row)
        self._open[id(request)] = row

    async def after_receive(self, response):
        row = self._open.pop(id(response.request), None)
        if row is None:
            return
        row["status"] = response.status_code
        if response.status_code != 200 or "json" not in response.headers.get("content-type", ""):
            return  # error bodies are never copied into the trace
        await response.aread()
        try:
            body = response.json()
        except ValueError:
            return
        if not isinstance(body, dict):
            return
        if isinstance(body.get("model"), str):
            row["model"] = body["model"]
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        details = usage.get("input_tokens_details") if isinstance(usage.get("input_tokens_details"), dict) else {}
        for key in USAGE:
            row[key] = count(usage.get(key))
        for key in CACHE_USAGE:
            row[key] = count(details.get(key))
            if row[key] is not None and row["input_tokens"] is not None and row[key] > row["input_tokens"]:
                row[key] = None  # a cache count is part of input_tokens; a larger one is not a valid report
        reads, writes = (row[key] for key in CACHE_USAGE)
        if None not in (reads, writes, row["input_tokens"]) and reads + writes > row["input_tokens"]:
            # Reads and writes are disjoint parts of input_tokens. A pair that exceeds it is inconsistent:
            # keep both unknown rather than imply negative ordinary input.
            row["cached_tokens"] = row["cache_write_tokens"] = None

    def client(self, transport=None) -> httpx2.AsyncClient:
        """An HTTP client that passes every request through this budget. `transport` is for offline tests."""
        return httpx2.AsyncClient(transport=transport,
                                  event_hooks={"request": [self.before_send], "response": [self.after_receive]})

    def summary(self) -> dict:
        unknown = sum(any(row[key] is None for key in USAGE) for row in self.attempts)
        # A total is reported only when every request sent reported its usage; otherwise it is unknown.
        totals = {f"reported_{key}": None if unknown else sum(row[key] for row in self.attempts) for key in USAGE}
        # Cache reads and writes are totalled independently, by the same rule. They are already inside
        # reported_input_tokens and are never added to it.
        for key in CACHE_USAGE:
            values = [row[key] for row in self.attempts]
            totals[f"reported_{key}"] = None if None in values else sum(values)
        return {"requests_sent": len(self.attempts), "requests_refused": self.refused,
                "requests_without_usage": unknown, **totals, "attempts": self.attempts}


class Pilot:
    """One bounded live case on the OpenAI Responses API. The caller validates the limits and loads the key."""

    def __init__(self, model_name: str, *, max_requests: int, max_output_tokens: int, arm=None,
                 api_key=None, transport=None):
        if not model_name or max_requests < 1 or max_output_tokens < 1:
            raise ValueError("A pilot needs a model name and positive request and output-token limits.")
        if arm is not None and arm not in ARMS:
            raise ValueError(f"Unknown #21 arm {arm!r}; choose one of {', '.join(ARMS)}.")
        self.arm = arm
        self.timestamp_position, options = ARMS[arm] if arm else (None, None)
        self.prompt_cache_options = dict(options) if options else None
        if self.prompt_cache_options is not None and not (
                model_name in NO_CACHE_MODELS
                and OpenAIProvider.model_profile(model_name).get("openai_supports_prompt_cache_breakpoints")):
            # Refuse rather than send a request whose cache setting may be ignored or rejected.
            raise ValueError(f"The {arm} arm is supported only for {', '.join(NO_CACHE_MODELS)} on the "
                             f"Responses API, not {model_name!r}. No request was sent.")
        self.model_name = model_name
        self.max_output_tokens = max_output_tokens
        self.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")  # records trial order
        self.budget = ProviderBudget(max_requests)
        self.client = AsyncOpenAI(api_key=api_key, http_client=self.budget.client(transport), max_retries=0)
        settings = OpenAIResponsesModelSettings(max_tokens=max_output_tokens)
        if self.prompt_cache_options is not None:
            settings["openai_prompt_cache_options"] = dict(self.prompt_cache_options)
        self.model = OpenAIResponsesModel(model_name, provider=OpenAIProvider(openai_client=self.client),
                                          settings=settings)

    def decider(self, calls: list, clock=None):
        """`live_decider` within this budget: a cap stop is named, and unreported usage stays unknown.

        In a #21 arm, `clock()` gives the current simulated time, read once per decision."""
        if self.timestamp_position and clock is None:
            raise ValueError("A #21 arm needs the simulated clock.")
        decide = live_decider(self.model, calls)

        async def bounded(context):
            if self.timestamp_position:
                context = with_current_time(context, clock(), self.timestamp_position)
            first = len(self.budget.attempts)
            try:
                decision = await decide(context)
            except AgentRunError as error:
                if self.budget.refused:
                    raise RequestCapStop(self.budget.max_requests) from error
                raise
            # The SDK reports missing usage as 0; keep it unknown if any request for this decision lacked it.
            for key in USAGE:
                if any(row[key] is None for row in self.budget.attempts[first:]):
                    calls[-1][key] = None
            return decision
        return bounded

    async def aclose(self):
        await self.client.close()  # closes the budget's HTTP client too

    def record(self) -> dict:
        return {"api": "openai-responses", "configured_model": self.model_name,
                "max_requests": self.budget.max_requests, "max_output_tokens_per_request": self.max_output_tokens,
                "sdk_retries": 0, "arm": self.arm, "timestamp_position": self.timestamp_position,
                "prompt_cache_options": self.prompt_cache_options,  # None: the provider's default caching
                "started_at_utc": self.started_at,
                "pilot_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                **self.budget.summary()}
