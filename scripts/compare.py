#!/usr/bin/env python3
"""Strict, read-only paired analysis of published or newly recorded JSONL metrics."""
import argparse
import json
import math
from pathlib import Path
import statistics


def compare(rows, baseline, candidate):
    expected = {(trial,kind,size) for trial in (0,1) for kind,size in
                [('fresh',8192),('fresh',131072),('fresh',260000),('cached',131072)]}
    arms = {}
    for arm in (baseline,candidate):
        indexed = {}
        for row in rows:
            if row['arm'] != arm:
                continue
            key = (row['trial'],row['kind'],row['target'])
            assert key not in indexed, f'Duplicate row: {arm}/{key}'
            timing = row['timings']
            n = 256 if row['kind'] == 'fresh' else 1024
            assert timing['predicted_n'] == row['usage']['completion_tokens'] == n
            assert row['finish_reason'] == 'length'
            assert timing['cache_n'] == 0 if row['kind'] == 'fresh' else timing['cache_n'] >= 129024
            assert all(math.isfinite(v) and v>0 for v in
                       (row['wall_s'],timing['prompt_per_second'],timing['predicted_per_second']))
            indexed[key] = row
        assert set(indexed) == expected, f'Incomplete or unexpected workload: {arm}'
        arms[arm] = indexed
    for key in expected:
        a,b = arms[baseline][key],arms[candidate][key]
        assert a['prompt_sha256'] == b['prompt_sha256'], f'Prompt differs: {key}'
        assert a['usage']['prompt_tokens'] == b['usage']['prompt_tokens']
        for metric in ('cache_n','prompt_n','predicted_n'):
            assert a['timings'][metric] == b['timings'][metric]
    output = []
    for kind,size in [('fresh',8192),('fresh',131072),('fresh',260000),('cached',131072)]:
        values = {}
        for arm in (baseline,candidate):
            selected = [arms[arm][(trial,kind,size)] for trial in (0,1)]
            values[arm] = dict(wall_s=statistics.median(r['wall_s'] for r in selected),
                pp_tps=statistics.median(r['timings']['prompt_per_second'] for r in selected),
                tg_tps=statistics.median(r['timings']['predicted_per_second'] for r in selected))
        a,b = values[baseline],values[candidate]
        output.append(dict(kind=kind,target=size,baseline=a,candidate=b,
            wall_increase_pct=100*(b['wall_s']/a['wall_s']-1),
            pp_change_pct=100*(b['pp_tps']/a['pp_tps']-1),tg_change_pct=100*(b['tg_tps']/a['tg_tps']-1)))
    return dict(baseline=baseline,candidate=candidate,rounds=2,cases=output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', type=Path)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--candidate', required=True)
    args = parser.parse_args()
    if args.baseline == args.candidate:
        parser.error('Baseline and candidate must differ')
    rows = [json.loads(line) for path in args.files for line in path.read_text().splitlines() if line.strip()]
    print(json.dumps(compare(rows,args.baseline,args.candidate),indent=2))


if __name__ == '__main__':
    main()
