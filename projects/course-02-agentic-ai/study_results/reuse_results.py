"""Summarize sanitized #21 demo.py JSONL annotated with integer study_slot and round."""
import argparse
import json
from decimal import Decimal

ARMS = ("time-first", "time-last", "time-last-no-cache")
CASES = tuple(f"shift-{letter}" for letter in "abcde")
CONTROL = "time-last"
PLAN = [
    (round_index + 1, case, ARMS[(round_index + case_index + offset) % len(ARMS)])
    for round_index in range(3)
    for case_index, case in enumerate(CASES)
    for offset in range(len(ARMS))
]
RATES = {
    "ordinary_input_tokens": Decimal(".10"),
    "cached_tokens": Decimal(".01"),
    "cache_write_tokens": Decimal(".125"),
    "output_tokens": Decimal(".50"),
}
TOKEN_KEYS = ("input_tokens", *RATES)


def count(value):
    if type(value) is not int or value < 0:
        raise ValueError("expected a nonnegative integer count")
    return value


def known_sum(values):
    values = list(values)
    return None if None in values else sum(values)


def add_tokens(rows):
    return {key: known_sum(row[key] for row in rows) for key in TOKEN_KEYS}


def cost(tokens):
    charges = (None if tokens[key] is None else tokens[key] * rate
               for key, rate in RATES.items())
    total = known_sum(charges)
    return None if total is None else total / 1_000_000


def usd(value):
    return None if value is None else format(value, "f")


def attempt_tokens(attempt):
    tokens = {key: attempt.get(key) for key in TOKEN_KEYS if key != "ordinary_input_tokens"}
    for value in tokens.values():
        if value is not None:
            count(value)
    reads = tokens["cached_tokens"]
    writes = tokens["cache_write_tokens"]
    total = tokens["input_tokens"]
    if total is not None and (reads or 0) + (writes or 0) > total:
        raise ValueError("cache reads and writes exceed reported input")
    tokens["ordinary_input_tokens"] = None if None in (total, reads, writes) else total - reads - writes
    return tokens


def incident(row):
    pilot = row["pilot"]
    attempts = pilot["attempts"]
    if not isinstance(attempts, list) or count(pilot["requests_sent"]) != len(attempts):
        raise ValueError("requests_sent does not match attempts")
    checks = row["checks"]
    passed = row["passed"]
    if (type(passed) is not bool or not isinstance(checks, list) or not checks
            or any(type(check["pass"]) is not bool for check in checks)
            or passed != all(check["pass"] for check in checks)):
        raise ValueError("passed does not match grader checks")

    report = row["report"]
    action = report["action"]
    followup = report.get("follow_up") or {}
    # The observation tick can change without changing the verified follow-up.
    followup = {key: followup[key] for key in ("operation", "source", "target", "targets", "failed")
                if key in followup}
    target = action["target"] if action is not None else None
    tokens = add_tokens([attempt_tokens(attempt) for attempt in attempts])
    return {
        "study_slot": row["study_slot"],
        "round": row["round"],
        "case": row["case"],
        "arm": pilot["arm"],
        "passed": passed,
        "failed_checks": [check["check"] for check in checks if not check["pass"]],
        "applied_effects": count(row["applied_effects"]),
        "reported_action_target": target,
        # The frozen tool trace can omit the instance argument. The report's receipt has the target.
        "restart_call_targets": [call.get("target") for call in row["reads_and_actions"]
                                 if call["tool"] == "restart_instance"],
        "follow_up": followup,
        "report_status": report["status"],
        "requests_sent": len(attempts),
        "tokens": tokens,
        "estimated_usd": usd(cost(tokens)),
    }


def compare(control, treatment):
    if control is None or treatment is None:
        return {"comparison": "unpaired", "control_slot": control and control["study_slot"],
                "treatment_slot": treatment and treatment["study_slot"]}

    fields = ("passed", "applied_effects", "reported_action_target", "restart_call_targets",
              "follow_up", "report_status")
    changed = [key for key in fields if control[key] != treatment[key]]
    baseline = cost(control["tokens"])
    variant = cost(treatment["tokens"])
    delta = None if None in (baseline, variant) else variant - baseline
    if changed:
        comparison = "outcome_changed"
    elif not control["passed"]:
        comparison = "both_failed"
    elif delta is None:
        comparison = "cost_unknown"
    elif delta == 0:
        comparison = "equal_cost_at_same_verified_outcome"
    elif delta < 0:
        comparison = "treatment_cheaper_at_same_verified_outcome"
    else:
        comparison = "control_cheaper_at_same_verified_outcome"

    return {
        "comparison": comparison,
        "control_slot": control["study_slot"],
        "treatment_slot": treatment["study_slot"],
        "changed_outcome_fields": changed,
        "control_passed": control["passed"],
        "treatment_passed": treatment["passed"],
        "treatment_minus_control_usd": usd(delta),
        "treatment_minus_control_tokens": {
            key: None if None in (control["tokens"][key], treatment["tokens"][key])
            else treatment["tokens"][key] - control["tokens"][key]
            for key in TOKEN_KEYS
        },
    }


def unique_keys(pairs):
    row = {}
    for key, value in pairs:
        if key in row:
            raise ValueError(f"duplicate JSON key {key!r}")
        row[key] = value
    return row


def summarize(lines):
    incidents = {}
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line, object_pairs_hook=unique_keys)
            slot = row["study_slot"]
            if not 1 <= count(slot) <= len(PLAN):
                raise ValueError("study_slot must be in 1–45")
            expected = PLAN[slot - 1]
            if (count(row["round"]), row["case"], row["pilot"]["arm"]) != expected:
                raise ValueError(f"slot {slot} expects round, case, arm {expected}")
            if slot in incidents:
                raise ValueError(f"duplicate study_slot {slot}")
            incidents[slot] = incident(row)
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise ValueError(f"line {line_number}: {error}") from error

    by_match = {PLAN[slot - 1]: item for slot, item in incidents.items()}
    groups = []
    for case in CASES:
        for arm in ARMS:
            runs = [item for item in incidents.values() if (item["case"], item["arm"]) == (case, arm)]
            passes = sum(item["passed"] for item in runs)
            tokens = add_tokens([item["tokens"] for item in runs]) if runs else dict.fromkeys(TOKEN_KEYS)
            groups.append({
                "case": case, "arm": arm, "passes": passes, "failures": len(runs) - passes,
                "unrun": 3 - len(runs), "applied_effects": sum(item["applied_effects"] for item in runs),
                "reported_action_targets": sorted({item["reported_action_target"] for item in runs
                                                   if item["reported_action_target"] is not None}),
                "tokens": tokens, "estimated_usd": usd(cost(tokens)),
            })

    pairs = [
        {"round": round_number, "case": case, "treatment_arm": arm,
         **compare(by_match.get((round_number, case, CONTROL)), by_match.get((round_number, case, arm)))}
        for round_number in range(1, 4)
        for case in CASES
        for arm in ARMS if arm != CONTROL
    ]
    total = add_tokens([item["tokens"] for item in incidents.values()]) if incidents else dict.fromkeys(TOKEN_KEYS)
    return {
        "recorded_incidents_total": {"tokens": total, "estimated_usd": usd(cost(total))},
        "by_case_and_arm": groups,
        "incidents": [incidents[slot] for slot in sorted(incidents)],
        "unrun_slots": [slot for slot in range(1, len(PLAN) + 1) if slot not in incidents],
        "shared_control": CONTROL,
        "paired_comparisons": pairs,
        "usd_per_million_tokens": {key: str(rate) for key, rate in RATES.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", help="path to sanitized, annotated #21 demo records")
    args = parser.parse_args()
    try:
        with open(args.jsonl, encoding="utf-8") as source:
            result = summarize(source)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
