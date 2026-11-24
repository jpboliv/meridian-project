import asyncio
import json
from pathlib import Path

import pytest

from interruption_demo import trial
from trace_monitor import inspect

HERE = Path(__file__).resolve().parent


def test_tagged_records_without_verdicts():
    records = [json.loads(line) for line in (HERE / 'offline-traces-m3.jsonl').read_text().splitlines()]
    for r in records:
        for field in ('case', 'run', 'checks', 'control', 'effects'):
            r.pop(field, None)
    assert inspect(records[8]) == {'effects': 'single', 'recovery': 'supported'}
    assert inspect(records[-2])['recovery'] == 'non-recovery handover'
    assert inspect(records[-1])['effects'] == 'duplicate'
    assert inspect(records[13])['recovery'] == 'unknown'


@pytest.mark.parametrize('case,status,used', [('A', 'supported', 2), ('N', 'non-recovery handover', 7)])
def test_two_stops(tmp_path, case, status, used):
    r = asyncio.run(trial(case, tmp_path))
    middle, last = r['second_stop'], r['replacement']
    assert [c['tool'] for c in middle['reads']] == ['executor.lookup']
    assert middle['state'] == 'receipt_saved'
    assert last['action']['receipt'] == middle['receipt']['action_id'] == r['executor_audit'][0]['action_id']
    assert last['resume']['ledger']['requests'] == 1
    calls = r['stopped']['reads'] + middle['reads'] + last['reads']
    assert sum(c['tool'] == 'restart_instance' for c in calls) == 1
    assert r['limit'] - len(calls) == last['budget']['limit'] - last['budget']['used']
    assert middle['remaining'] == last['budget']['limit'] == 18
    assert last['budget']['used'] == len(last['reads']) == used
    assert inspect(r) == {'effects': 'single', 'recovery': status}
    if case == 'N':
        last['status'] = 'recovered'  # same executor and tool results, false final report
        assert inspect(r)['recovery'] == 'unsupported'
        r['metrics'].clear()  # missing source data is a different finding
        assert inspect(r)['recovery'] == 'unknown'


def test_legacy_receipt_has_no_reliable_balance(tmp_path):
    from resume_demo import interrupted, replacement
    from scoped_memory import ScopedMemory

    async def resume_old():
        sim, _, store, _, _ = await interrupted('A', tmp_path, 'after_dispatch_before_receipt')
        await replacement(sim, store, ScopedMemory())
        store.save({**store.load(), 'version': 2, 'remaining_budget': 20})
        return await replacement(sim, store, ScopedMemory())

    worker, report = asyncio.run(resume_old())
    assert report['status'] == 'needs_operator' and not worker.tools.trace
    assert 'budget is unknown' in report['next_step']
