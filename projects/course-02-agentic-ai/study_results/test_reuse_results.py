import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from reuse_results import PLAN, summarize


def row(slot, round_number, case, arm, *, passed=True, attempts=None, target=None):
    if attempts is None:
        attempts = [{"input_tokens": 100, "cached_tokens": 10,
                     "cache_write_tokens": 20, "output_tokens": 5}]
    return {
        "study_slot": slot, "round": round_number, "case": case, "passed": passed,
        "pilot": {"arm": arm, "attempts": attempts, "requests_sent": len(attempts)},
        "checks": [{"check": "effect", "pass": passed}],
        "report": {"status": "recovered" if target else "needs_operator",
                   "action": {"target": target} if target else None},
        "applied_effects": int(target is not None),
        "reads_and_actions": [{"tool": "restart_instance"}] if target else [],
    }


def report(*rows):
    return summarize(map(json.dumps, rows))


class ReuseResultsTest(unittest.TestCase):
    def test_plan_and_unrun_slots(self):
        self.assertEqual(PLAN[3:6], [(1, "shift-b", arm) for arm in
                                     ("time-last", "time-last-no-cache", "time-first")])
        self.assertEqual(PLAN[15], (2, "shift-a", "time-last"))
        self.assertEqual(PLAN[44], (3, "shift-e", "time-last-no-cache"))
        result = report(row(1, 1, "shift-a", "time-first"))
        self.assertEqual(result["unrun_slots"], list(range(2, 46)))
        group = result["by_case_and_arm"][0]
        self.assertEqual((group["passes"], group["failures"], group["unrun"]), (1, 0, 2))
        self.assertTrue(all(pair["comparison"] == "unpaired" for pair in result["paired_comparisons"]))

    def test_whole_incident_cost_and_verified_pairs(self):
        first = row(1, 1, "shift-a", "time-first", passed=False, target="wrong")
        control = row(2, 1, "shift-a", "time-last", target="right")
        control["pilot"]["attempts"] *= 2
        control["pilot"]["requests_sent"] = 2
        off = row(3, 1, "shift-a", "time-last-no-cache", target="right", attempts=[
            {"input_tokens": 100, "cached_tokens": 0, "cache_write_tokens": 0, "output_tokens": 5}
        ])
        result = report(off, first, control)
        self.assertEqual(result["incidents"][1]["restart_call_targets"], [None])
        self.assertEqual(result["incidents"][1]["reported_action_target"], "right")
        self.assertEqual(result["incidents"][1]["tokens"]["ordinary_input_tokens"], 140)
        self.assertEqual(result["incidents"][1]["estimated_usd"], "0.0000242")
        self.assertEqual(result["recorded_incidents_total"]["estimated_usd"], "0.0000488")
        placement, cache = result["paired_comparisons"][:2]
        self.assertEqual(placement["comparison"], "outcome_changed")
        self.assertEqual(cache["comparison"], "treatment_cheaper_at_same_verified_outcome")
        self.assertEqual(cache["treatment_minus_control_usd"], "-0.0000117")
        self.assertEqual(placement["control_slot"], cache["control_slot"])

    def test_missing_usage_is_independently_unknown(self):
        item = row(3, 1, "shift-a", "time-last-no-cache", attempts=[
            {"input_tokens": 100, "cached_tokens": 0, "output_tokens": 5},
            {"status": 503},
        ])
        outcome = report(row(2, 1, "shift-a", "time-last"), item)
        self.assertIsNone(outcome["incidents"][1]["estimated_usd"])
        self.assertEqual(outcome["paired_comparisons"][1]["comparison"], "cost_unknown")
        item["pilot"]["attempts"].pop()
        item["pilot"]["requests_sent"] = 1
        tokens = report(item)["incidents"][0]["tokens"]
        self.assertEqual(tokens["cached_tokens"], 0)
        self.assertEqual(tokens["output_tokens"], 5)
        self.assertIsNone(tokens["ordinary_input_tokens"])

    def test_bad_input_stops(self):
        item = row(1, 1, "shift-a", "time-first")
        with self.assertRaisesRegex(ValueError, "line 2: duplicate study_slot 1"):
            report(item, item)
        with self.assertRaisesRegex(ValueError, "line 1: slot 1 expects"):
            report(dict(item, round=2))
        with self.assertRaisesRegex(ValueError, "line 1: passed does not match"):
            report(dict(item, passed=False))
        item["pilot"]["attempts"][0]["cached_tokens"] = 90
        with self.assertRaisesRegex(ValueError, "line 1: cache reads and writes exceed"):
            report(item)

    def test_cli_rejects_duplicate_without_emitting_report(self):
        item = row(1, 1, "shift-a", "time-first")
        with tempfile.TemporaryDirectory(dir=".") as directory:
            path = Path(directory) / "public-mock.jsonl"
            path.write_text((json.dumps(item) + "\n") * 2, encoding="utf-8")
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("reuse_results.py")),
                                     str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("line 2: duplicate study_slot 1", result.stderr)


if __name__ == "__main__":
    unittest.main()
