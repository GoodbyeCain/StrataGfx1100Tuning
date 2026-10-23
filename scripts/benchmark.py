#!/usr/bin/env python3
"""One restarted arm/round of the published synthetic fresh/cached workload."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request

PACKAGE = Path(__file__).resolve().parents[1]


def request(base, path, body=None):
    req = urllib.request.Request(base+path, headers={'Content-Type':'application/json'},
        data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=900) as response:
        return json.load(response)


def followup(trial):
    return ('Continue your audit with 80 additional detailed numbered items. Explain concrete edge cases and tests. '
        'Do not repeat earlier items. Continue until all 80 items are complete.' if trial == 0 else
        'Start a new writing task. Write a standalone, comprehensive JavaScript testing handbook with 100 numbered sections. '
        'For each section give a detailed explanation, a code example, expected results, and edge cases. Cover unit tests, '
        'integration tests, property-based testing, fuzzing, mutation testing, numerical edge cases, Unicode, asynchronous '
        'code, and performance. Begin directly with section 1 and keep writing all 100 sections. Do not summarize or refer '
        'to an earlier review.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', required=True, choices=('dual','single-xtx','clean','patched'))
    parser.add_argument('--trial', required=True, type=int, choices=(0,1))
    parser.add_argument('--out', required=True, type=Path, help='new JSONL file, never appended/overwritten')
    parser.add_argument('--base', default='http://127.0.0.1:18080')
    args = parser.parse_args()
    if args.base != 'http://127.0.0.1:18080':
        parser.error('This benchmark uses the published localhost:18080 configurations')
    if args.out.exists():
        parser.error('Output exists; preserve it and use a new file')
    health = request(args.base, '/health')
    assert health['loaded'] and health['max_context'] == 262144 and health['images']
    params = request(args.base, '/props')['default_generation_settings']['params']
    assert params['presence_penalty'] == params['frequency_penalty'] == 0 and params['repeat_penalty'] == 1
    request(args.base, '/v1/chat/completions', dict(model='strata', messages=[{'role':'user','content':'Reply READY.'}],
        max_tokens=8, temperature=0, reasoning_effort='none'))
    rows = []
    def measure(body, kind, target, prompt_hash):
        start = time.monotonic()
        answer = request(args.base, '/v1/chat/completions', body)
        wall = time.monotonic()-start
        timing, usage = answer['timings'], answer['usage']
        assert answer['choices'][0]['finish_reason'] == 'length'
        assert timing['predicted_n'] == usage['completion_tokens'] == body['max_tokens']
        assert timing['cache_n'] == 0 if kind == 'fresh' else timing['cache_n'] >= 129024
        row = dict(label=f'pair{args.trial}-{args.arm}', arm=args.arm, trial=args.trial, kind=kind,
            target=target, wall_s=wall, timings=timing, usage=usage, finish_reason='length', prompt_sha256=prompt_hash)
        rows.append(row)
        print(json.dumps(row), flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # A failure leaves a separately named partial file; the complete output is never emitted.
    partial = args.out.with_name(args.out.name+'.partial')
    if partial.exists():
        parser.error('Partial output exists; inspect the earlier failure and use a new path')
    try:
        for size in (8192,131072,260000):
            prompt = (PACKAGE/'tests/prompts'/f'v2-{size}-{args.trial}.txt').read_text()
            messages = [{'role':'user','content':prompt}]
            body = dict(model='strata', messages=messages, max_tokens=256, temperature=0,
                        top_k=1, top_p=1, min_p=0, seed=42, reasoning_effort='none')
            measure(body, 'fresh', size, hashlib.sha256(prompt.encode()).hexdigest())
            if size == 131072:
                history = messages+[{'role':'assistant','content':'The initial review has been recorded. Continue the audit.'},
                    {'role':'user','content':followup(args.trial)}]
                measure(dict(body,messages=history,max_tokens=1024), 'cached', size,
                    hashlib.sha256(json.dumps(history).encode()).hexdigest())
    except BaseException:
        with partial.open('x') as stream:
            stream.write(''.join(json.dumps(row)+'\n' for row in rows))
        raise
    with args.out.open('x') as stream:
        stream.write(''.join(json.dumps(row)+'\n' for row in rows))


if __name__ == '__main__':
    main()
