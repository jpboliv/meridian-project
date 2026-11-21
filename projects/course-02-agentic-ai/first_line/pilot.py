"""Bounds for one live case: a provider request cap and a per-request output limit.

Every HTTP request the OpenAI client sends passes through `ProviderBudget`. That includes each decision,
each output-validation repair, and any SDK retry, so the cap counts what reaches the provider. The SDK's own
retries are also switched off. When the cap is reached, the next request is refused before it is sent, and
the decision raises `RequestCapStop`. The caller hands over with a reason that names the cap.

`max_output_tokens` is set on every request. It limits each response, so a case produces at most
`max_requests × max_output_tokens` output tokens. Input tokens are measured, not capped.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx2
from openai import AsyncOpenAI
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from shift import live_decider

USAGE = ("input_tokens", "output_tokens")


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
        row = {"status": None, "model": None, "input_tokens": None, "output_tokens": None}
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
        if isinstance(body.get("model"), str):
            row["model"] = body["model"]
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        for key in USAGE:
            if isinstance(usage.get(key), int):
                row[key] = usage[key]

    def client(self, transport=None) -> httpx2.AsyncClient:
        """An HTTP client that passes every request through this budget. `transport` is for offline tests."""
        return httpx2.AsyncClient(transport=transport,
                                  event_hooks={"request": [self.before_send], "response": [self.after_receive]})

    def summary(self) -> dict:
        unknown = sum(any(row[key] is None for key in USAGE) for row in self.attempts)
        # A total is reported only when every request sent reported its usage; otherwise it is unknown.
        totals = {f"reported_{key}": None if unknown else sum(row[key] for row in self.attempts) for key in USAGE}
        return {"requests_sent": len(self.attempts), "requests_refused": self.refused,
                "requests_without_usage": unknown, **totals, "attempts": self.attempts}


class Pilot:
    """One bounded live case on the OpenAI Responses API. The caller validates the limits and loads the key."""

    def __init__(self, model_name: str, *, max_requests: int, max_output_tokens: int, api_key=None, transport=None):
        if not model_name or max_requests < 1 or max_output_tokens < 1:
            raise ValueError("A pilot needs a model name and positive request and output-token limits.")
        self.model_name = model_name
        self.max_output_tokens = max_output_tokens
        self.budget = ProviderBudget(max_requests)
        self.client = AsyncOpenAI(api_key=api_key, http_client=self.budget.client(transport), max_retries=0)
        self.model = OpenAIResponsesModel(model_name, provider=OpenAIProvider(openai_client=self.client),
                                          settings=ModelSettings(max_tokens=max_output_tokens))

    def decider(self, calls: list):
        """`live_decider` within this budget: a cap stop is named, and unreported usage stays unknown."""
        decide = live_decider(self.model, calls)

        async def bounded(context):
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
                "sdk_retries": 0, "pilot_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                **self.budget.summary()}
