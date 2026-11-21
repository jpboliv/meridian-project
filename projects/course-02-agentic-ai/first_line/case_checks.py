"""Score first-line reports against observations and applied effects after a shift."""

from meridian.evaluate import OPERATORS, Check, evaluate

INSTANCE_MONITOR = "monitoring.get_instance_datapoints"


def has_fields(record, **fields):
    return isinstance(record, dict) and all(record.get(key) == value for key, value in fields.items())


def evaluate_case(sim, trace, report, solution):
    result = evaluate(sim, trace, report, solution)
    if "observed_samples" in solution.get("recovery", {}):
        result.checks.append(observed_recovery(sim, trace, report, solution["recovery"]))
    if expected := solution.get("handover"):
        observations = report.get("observations", {})
        result.checks.append(Check(
            "handed over without an effect or recovery claim",
            report.get("status") == "needs_operator" and report.get("action") is None
            and "recovery" not in observations and not sim.executor.effects(), expected["component"],
        ))
        if expected["operation"] == "obtain_instance_readings":
            result.checks.extend(timeout_checks(sim, trace, report, expected))
        elif expected["operation"] == "investigate_link":
            links = cited_links(sim, trace, observations, expected, "degraded")
            follow_up = report.get("follow_up", {})
            result.checks.append(Check(
                "fresh independent link cited for investigation",
                any(has_fields(follow_up, operation="investigate_link", source=expected["component"],
                               target=expected["dependency"], observed_tick=c.tick) for c in links),
                expected["dependency"],
            ))
        else:
            raise ValueError(f"Unknown handover operation: {expected['operation']}")
        if "sample_tick" in expected:
            result.checks.append(historical_samples(sim, trace, observations, expected))
    return result


def cited_links(sim, trace, observations, expected, state):
    component, target = expected["component"], expected["dependency"]
    route = {"source": component, "target": target}
    link = observations.get("links", {}).get(target, {})
    for call in trace:
        if (call.tool == "check_link" and not call.error and call.tick >= sim.agent_start_tick
                and has_fields(call.args, **route) and has_fields(call.result, **route, state=state, observed_tick=call.tick)
                and has_fields(link, state=state, tick=call.tick)):
            yield call


def timeout_checks(sim, trace, report, expected):
    attempts = [c for c in trace if c.tool == INSTANCE_MONITOR]
    name = "instance monitor timed out twice on the same target"
    if len(attempts) != 2:
        return [Check(name, False, f"{len(attempts)} monitor calls")]
    first, retry = attempts
    component = expected["component"]
    instance = first.args.get("instance")
    same_target = (instance in {i.instance_id for i in sim.state.component(component).instances}
                   and retry.args.get("instance") == instance and first.step < retry.step
                   and sim.agent_start_tick <= first.tick <= retry.tick)
    timed_out = all(c.args.get("device") == component and isinstance(c.result, dict)
                    and c.error == c.result.get("error") == f"{INSTANCE_MONITOR} timed out"
                    and c.result.get("retryable") is True for c in attempts)
    observations = report.get("observations", {})
    links = cited_links(sim, trace, observations, expected, "up")
    return [
        Check(name, same_target and timed_out, f"{instance} at ticks {first.tick}, {retry.tick}"),
        Check("independent link observed after the retry",
              any(c.step > retry.step and c.tick >= retry.tick for c in links), expected["dependency"]),
        Check("handover names the unresolved instance measurement",
              bool(observations.get("missing")) and has_fields(report.get("follow_up"),
                   operation="obtain_instance_readings", source=INSTANCE_MONITOR, target=instance),
              str(instance)),
    ]


def healthy_sample_matches(sample, row, tick, time, conditions):
    if not has_fields(row, tick=tick, time=time) or not has_fields(sample, tick=tick, time=time):
        return False
    for rule in conditions:
        metric = rule["metric"]
        value = row.get(metric)
        if not isinstance(value, (int, float)) or sample.get(metric) != value or not OPERATORS[rule["op"]](value, rule["value"]):
            return False
    return True


def observed_recovery(sim, trace, report, spec):
    count = spec["observed_samples"]
    name = f"{count} consecutive healthy readings observed after the applied restart"
    effects = sim.executor.effects("restart_instance")
    if len(effects) != 1:
        return Check(name, False, f"{len(effects)} applied restarts")
    effect, = effects
    receipt = {"receipt": effect.action_id, "approval": effect.confirmation_ref, "target": effect.target, "tick": effect.tick}
    if not has_fields(report.get("action"), **receipt):
        return Check(name, False, "reported action does not match the executor receipt")

    evidence = report.get("observations", {}).get("recovery") or {}
    source, samples = evidence.get("source"), evidence.get("samples")
    if not source or not isinstance(samples, list) or len(samples) != count:
        return Check(name, False, "missing cited samples")
    conditions = spec["conditions"]
    for call in trace:
        if (call.tool != "read_metrics" or call.error or not isinstance(call.result, dict)
                or call.result.get("source_ref") != source
                or not all(rule["component"] == call.args.get("component") == call.result.get("component")
                           for rule in conditions)):
            continue
        rows = call.result.get("readings")
        first_tick = call.tick - count + 1
        if not isinstance(rows, list) or len(rows) < count or first_tick <= effect.tick:
            continue
        if all(healthy_sample_matches(sample, row, tick, sim.clock.label(tick), conditions)
               for tick, row, sample in zip(range(first_tick, call.tick + 1), rows[-count:], samples)):
            return Check(name, True, f"{source}: ticks {first_tick}–{call.tick}; {effect.action_id} at {effect.tick}")
    return Check(name, False, f"no qualifying readings from {source} after tick {effect.tick}")


def historical_samples(sim, trace, observations, expected):
    component = expected["component"]
    sample_tick = expected["sample_tick"]
    recorded_at = sim.clock.label(sample_tick)
    instances = observations.get("instances", {})

    def matches_sample(call):
        if call.tool != INSTANCE_MONITOR or call.error or not call.result.get("values"):
            return False
        name = call.args.get("instance")
        raw = call.result["values"][-1]
        row = instances.get(name, {})
        return (call.args.get("device") == component and call.result.get("instance") == name
                and raw["time"] == recorded_at and sample_tick < sim.agent_start_tick <= call.tick
                and raw["status"] == "running" and raw["memory_pct"] <= 90
                and row.get("time") == raw["time"] and row.get("read_at") == call.time
                and row.get("memory_pct") == raw["memory_pct"] and row.get("freshness") == "stale"
                and row.get("source") == f"{call.tool}/{name}/{call.tick}")

    return Check("historical samples identified", bool(instances) and
                 {c.args["instance"] for c in trace if matches_sample(c)} == set(instances), recorded_at)
