# Second interruption: can the next worker trust the receipt and budget?

[#43](https://github.com/jpboliv/meridian-project/issues/43), after M3 `b409006`. The [agreed resume contract](../docs/specs/execution.md) separates a completed action from service recovery. M3 stopped one worker. This experiment stops its replacement immediately after it saves the reconciled receipt, at the entry to verification. The third worker has a new access object and empty memory; only the checkpoint and current exchange (including executor ledger) survive.

| Public input | Observed calls by worker | Dispatches / effects | Third worker's evidence |
|---|---:|---:|---|
| A | 13 + 1 + 2 = 16/32 | 1 / 1 | ACT-001 at tick 27; ledger lookup at 29, metrics at 30. Ticks 28–30 meet both thresholds. |
| N (link degrades) | 13 + 1 + 7 = 21/32 | 1 / 1 | Same receipt; final window at ticks 33–35 shows 190 ms each. Hands over. |

**Defect measured before the fix:** after 14 calls, the receipt checkpoint still said 20. The next worker subtracted the dispatch reservation again and started with 19 instead of 18. Neither fixture exhausted the budget; the defect was a refunded call, not an observed 33rd call. Receipt checkpoints now store the balance at save time (version 3). Only a pre-receipt balance needs the dispatch reservation. Older saved receipts lack a reliable remaining balance, so verification hands over. This implements the existing shared limit; it does not change restart authority. The experiment covers the stated stop boundary, not arbitrary crashes between subsequent reads or loss of the executor process.

**What the independent monitor sees:** on the tagged M3 resume records it finds two supported recoveries, the degraded-link handover, and both applied IDs in the naive retry. On M3 line 15 the stopped ledger records a completed restart, but the new simulator’s audit is empty. The monitor reports `effects: unknown`: a missing original action is not permission to repeat it. For the new adverse trace, changing only the report status to `recovered` produces `unsupported`; removing the metric results instead produces `unknown`. The monitor checks applied IDs for the recorded key and its explicit retry alias, not arbitrary relationships between unrelated keys. It compares the claimed receipt with the executor audit and the latest gateway read with the three-sample post-action rule. M3 retained source-labelled samples and call ticks rather than full tool results: those records permit cross-checking the source and time, not authenticating the payload. The [new recording](two-stops.jsonl) includes the actual verification tool results separately from the report.

**Course coverage:** [session 6 trajectory checks](../../../sessions/course-02-agentic-ai/06-evaluation/starter/trajectory.py) motivate checking source and order; [session 8 monitors](../../../sessions/course-02-agentic-ai/08-agents-in-production/starter/monitors.py) motivate running cheap rules on every replacement record. This is local JSON, not an OpenTelemetry integration. [Session 9](../../../sessions/course-02-agentic-ai/09-efficiency/) motivates measuring the shared budget across workers. A2A, model routing and alert storms do not exercise this boundary. Scripted offline only; no model calls or spending.

From the repository root inside the isolated shell:

```bash
set -eo pipefail
export PYTHONPATH="$PWD"
p=projects/course-02-agentic-ai
python -m pytest -q meridian/tests "$p"/{first_line,team,study_results}
cd "$p/team"
python interruption_demo.py | cmp - ../post_release/two-stops.jsonl
python trace_monitor.py offline-traces-m3.jsonl ../post_release/two-stops.jsonl
python m3_demo.py | cmp - offline-traces-m3.jsonl
cd ../first_line
python demo.py | cmp - offline-traces-m1.7.jsonl
python m2_demo.py | cmp - offline-traces-m2.jsonl
python handover_study.py | cmp - offline-study-m2.jsonl
```

Recorded offline: 300 tests passed (295 simulator/first-line/team and five study-result tests). Byte comparisons matched both new records and all 19 M3, five M1.7, 14 M2 and 17 study records against the public files at the M3 tag.
