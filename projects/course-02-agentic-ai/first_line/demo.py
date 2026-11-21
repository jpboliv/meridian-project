"""Run the public M1 cases from fresh simulators and evaluate their effects."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from meridian.agent_runtime import IncidentDeps, default_model, identity_for, require_api_key
from meridian.scenarios import load_solution
from meridian.tools import MeridianTools
from case_checks import evaluate_case
from shift import Decision, MAX_DECISIONS, REVISION, Shift, live_decider
from workbench import start_exchange

HERE = Path(__file__).resolve().parent


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


async def run_case(path, model=None):
    """Run one case in a fresh simulator, then evaluate it. Returns one trace record."""
    calls = []
    decide = live_decider(model, calls) if model else scripted
    sim = start_exchange(path)
    identity = identity_for(sim.scenario.actor["role"])
    tools = MeridianTools(sim, actor=identity["name"])
    shift = Shift(IncidentDeps(tools, identity=identity))
    report = await shift.run(decide)
    # Evaluation can advance the world; capture the last agent tick first.
    end_tick = sim.state.tick
    solution = load_solution(HERE / "checks" / path.name)
    checks = evaluate_case(sim, tools.trace, report, solution)
    return {
        "case": path.stem, "revision": REVISION,
        "harness_sha256": hashlib.sha256((HERE / "shift.py").read_bytes()).hexdigest(),
        "model": model or "offline scripted decisions (no LLM)",
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


async def main(live):
    if live:
        require_api_key()
    model = default_model() if live else None
    passed = True
    for path in sorted((HERE / "cases").glob("*.yaml")):
        record = await run_case(path, model)
        passed &= record["passed"]
        print(json.dumps(record, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Ask the configured course model for each decision.")
    raise SystemExit(asyncio.run(main(parser.parse_args().live)))
