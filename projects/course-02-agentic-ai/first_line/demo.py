"""Run the public M1 cases from fresh simulators and evaluate their effects.

With no options, all five cases run offline with scripted decisions. `--case` runs one case. `--live` asks
the model named by OPENAI_MODEL for each decision in exactly one case, within explicit request and
output-token limits.
"""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path

from meridian.agent_runtime import IncidentDeps, identity_for, require_api_key
from meridian.scenarios import load_solution
from meridian.tools import MeridianTools
from case_checks import evaluate_case
from pilot import Pilot, RequestCapStop
from shift import Decision, MAX_DECISIONS, REVISION, Shift
from workbench import start_exchange

HERE = Path(__file__).resolve().parent
CASES = {path.stem.removeprefix("shift-").upper(): path for path in sorted((HERE / "cases").glob("shift-*.yaml"))}


async def scripted(context):
    """Offline driver: fixed read order, target from observations, no case ID or expected answer."""
    seen = context["observations"]
    for step in ("tickets", "instances", "links"):
        if step not in seen:
            return Decision(step=step)
    for target, link in seen["links"].items():
        if link["state"] != "up":
            return Decision(step="handover", target=target)
    if any(sample["freshness"] != "current" for sample in seen["instances"].values()):
        return Decision(step="handover")
    hot = [name for name, sample in seen["instances"].items() if sample["memory_pct"] > 90]
    if len(hot) == 1:
        return Decision(step="restart", target=hot[0])
    return Decision(step="handover")


async def run_case(path, pilot=None):
    """Run one case in a fresh simulator, then evaluate it. Returns one trace record.

    Without a pilot the decisions are scripted. With one, a model decides within the pilot's limits.
    """
    calls = []
    decide = pilot.decider(calls) if pilot else scripted
    sim = start_exchange(path)
    identity = identity_for(sim.scenario.actor["role"])
    tools = MeridianTools(sim, actor=identity["name"])
    shift = Shift(IncidentDeps(tools, identity=identity))
    try:
        report = await shift.run(decide)
    except RequestCapStop as stop:
        # Raised only while waiting for a decision, so no action was started in this run.
        report = shift.handover(str(stop))
    # Evaluation can advance the world; capture the last agent tick first.
    end_tick = sim.state.tick
    solution = load_solution(HERE / "checks" / path.name)
    checks = evaluate_case(sim, tools.trace, report, solution)
    record = {
        "case": path.stem, "revision": REVISION,
        "harness_sha256": hashlib.sha256((HERE / "shift.py").read_bytes()).hexdigest(),
        "model": pilot.model_name if pilot else "offline scripted decisions (no LLM)",
        "completed_model_calls": calls,
        "seed": sim.scenario.seed, "decision_limit": MAX_DECISIONS, "end_tick": end_tick,
        "decisions": shift.decisions, "reads_and_actions": [
            {"tick": c.tick, "tool": c.tool,
             **{k: c.args[k] for k in ("component", "device", "instance", "source", "target") if k in c.args},
             **({"error": c.error} if c.error else {})} for c in tools.trace],
        "report": report, "applied_effects": len(sim.executor.effects()),
        "checks": [{"check": c.name, "pass": c.passed, "detail": c.detail} for c in checks.checks],
        "passed": checks.passed,
    }
    if pilot:
        record["pilot"] = pilot.record()
    return record


def positive(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive whole number")
    return value


def parse_args(argv=None):
    """Validate the whole command before any key is loaded or provider client is built."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", type=str.upper, choices=list(CASES), help="Run only this public case.")
    parser.add_argument("--live", action="store_true",
                        help="Ask the OPENAI_MODEL model for each decision (paid). Needs --case and both limits.")
    parser.add_argument("--max-requests", type=positive,
                        help="--live: provider requests allowed for the case, counting repairs and retries.")
    parser.add_argument("--max-output-tokens", type=positive,
                        help="--live: max_output_tokens sent with each request (a per-request limit).")
    args = parser.parse_args(argv)
    limits = {"--max-requests": args.max_requests, "--max-output-tokens": args.max_output_tokens}
    if args.live:
        missing = [flag for flag, value in {"--case": args.case, **limits}.items() if not value]
        if missing:
            parser.error(f"--live runs one case with stated limits; also give {', '.join(missing)}")
    elif given := [flag for flag, value in limits.items() if value is not None]:
        parser.error(f"{', '.join(given)} only apply with --live")
    return args


def live_model():
    """The model named by OPENAI_MODEL (local .env or environment). No fallback to a course default."""
    model = os.getenv("OPENAI_MODEL", "").strip()
    if not model:
        raise SystemExit("OPENAI_MODEL is not set. Name the model for the live pilot in the local .env.")
    return model


async def main(argv=None):
    args = parse_args(argv)
    pilot = None
    if args.live:
        require_api_key()  # loads the local .env
        pilot = Pilot(live_model(), max_requests=args.max_requests, max_output_tokens=args.max_output_tokens)
    passed = True
    try:
        for path in [CASES[args.case]] if args.case else CASES.values():
            record = await run_case(path, pilot)
            passed &= record["passed"]
            print(json.dumps(record, ensure_ascii=False))
    finally:
        if pilot:
            await pilot.aclose()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
