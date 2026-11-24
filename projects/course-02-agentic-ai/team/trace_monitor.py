"""Offline monitor for single-intent M3 replacement records (one JSON object per line)."""
import json
import sys
from pathlib import Path


def latest_window(record, worker):
    ticks = [r['tick'] for r in worker.get('reads', []) if r['tool'] == 'read_metrics']
    if not ticks:
        return None
    tick = ticks[-1]
    source = f'metrics/order-gateway/{tick}'
    if 'metrics' in record:  # source tool payloads in the post-release recording
        for call in record['metrics']:
            result = call['result']
            if call['tick'] == tick and result.get('source_ref') == source and result.get('component') == 'order-gateway':
                return tick, result.get('readings')
    else:  # M3 retained sampled observations and tool/tick, not the full tool payload
        for obs in (worker.get('post_restart'), worker.get('recovery')):
            if obs and obs.get('source') == source:
                return tick, obs.get('samples')
    return None


def inspect(record):
    worker = record.get('replacement', {})
    checkpoint = worker.get('resume', {}).get('checkpoint', {})
    original = (record.get('stopped') or {}).get('ledger', {})
    key = next(iter(original)) if len(original) == 1 else (checkpoint.get('key') if isinstance(checkpoint, dict) else None)
    # The naive worker appended :retry to its recorded intent. Do not group unrelated keys by target alone.
    audit = record.get('executor_audit')
    rows = [r for r in audit or [] if key and r.get('key') in (key, key + ':retry') and r.get('effect') is True]
    ids = {r['action_id'] for r in rows}
    intent = original.get(key, {})
    target = intent.get('binding', {}).get('parameters', {}).get('target')
    if intent.get('state') == 'completed' and not any(
            r['key'] == key and r.get('outcome') == 'completed'
            and ('target' not in r or r['target'] == target)
            and ('tick' not in r or r['tick'] == intent.get('received_tick')) for r in rows):
        effects = 'unknown'  # the final audit does not account for the original completion
    elif len(ids) > 1:
        effects = 'duplicate'
    elif not key or audit is None or any(r.get('effect') is not False and r not in rows for r in audit):
        effects = 'unknown'
    else:
        effects = 'single' if ids else 'none'
    recovery = 'unknown'
    action = worker.get('action') or {}
    receipt = next((r for r in rows if r['action_id'] == action.get('receipt') and r['outcome'] == 'completed'
                    and r.get('target') == action.get('target') and r.get('tick') == action.get('tick')), None)
    if worker.get('status') == 'recovered' and effects == 'single' and action and not receipt:
        recovery = 'unsupported'  # claimed receipt differs from the observed effect
    window = latest_window(record, worker)
    if receipt and window:
        end, samples = window
        if isinstance(samples, list) and len(samples) == 3 and all(
                isinstance(s, dict) and type(s.get(k)) in (int, float) for s in samples
                for k in ('tick', 'latency_ms', 'error_rate')):
            healthy = ([s['tick'] for s in samples] == [end-2, end-1, end] and end-2 > receipt['tick']
                       and all(s['latency_ms'] < 20 and s['error_rate'] < .01 for s in samples))
            if worker.get('status') == 'recovered':
                recovery = 'supported' if healthy else 'unsupported'
            elif worker.get('status') == 'needs_operator' and not healthy:
                recovery = 'non-recovery handover'
    return {'effects': effects, 'recovery': recovery}


if __name__ == '__main__':
    for path in map(Path, sys.argv[1:]):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            record = json.loads(line)
            if 'executor_audit' in record:
                print(f'{path.name}:{number}', json.dumps(inspect(record)))
