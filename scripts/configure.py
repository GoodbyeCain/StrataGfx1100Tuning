#!/usr/bin/env python3
"""Render private local configs from public templates. Does not start any service."""
import argparse
import json
import os
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]


def render(value, replacements):
    if isinstance(value, dict):
        return {key: render(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [render(item, replacements) for item in value]
    if isinstance(value, str):
        for key, item in replacements.items():
            value = value.replace('@'+key+'@', str(item))
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strata-root', type=Path, required=True)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--rocm-root', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, default=PACKAGE/'runtime')
    parser.add_argument('--engine', type=Path)
    parser.add_argument('--vision-engine', type=Path)
    parser.add_argument('--xtx-gpu', type=int, default=0)
    parser.add_argument('--xt-gpu', type=int, default=1)
    args = parser.parse_args()
    if min(args.xtx_gpu, args.xt_gpu) < 0 or args.xtx_gpu == args.xt_gpu:
        parser.error('XTX and XT must have distinct non-negative HIP ordinals')
    root = args.strata_root.expanduser().resolve()
    data = args.data_root.expanduser().resolve()
    sdk = args.rocm_root.expanduser().resolve()
    output = args.out_dir.expanduser().resolve()
    replacements = dict(STRATA_ROOT=root, DATA_ROOT=data, ROCM_ROOT=sdk, RUN_ROOT=output,
        ENGINE=(args.engine or root/'build-gfx1100/strata').expanduser().resolve(),
        VISION_ENGINE=(args.vision_engine or root/'build-vision/bin/strata-vision').expanduser().resolve(),
        TUNING_ROOT=PACKAGE/'tuning', XTX_GPU=args.xtx_gpu, XT_GPU=args.xt_gpu)
    configs = {}
    for name in ('single-xtx', 'dual'):
        config = render(json.loads((PACKAGE/'configs'/('strata-'+name+'.json')).read_text()), replacements)
        config['gpu'] = [int(gpu) for gpu in config['gpu']]
        configs[name] = config
        files = [root/'serve/server.py', root/'data/expert-profile.bin', Path(config['exe']),
                 Path(config['vision']['exe']), Path(config['vision']['mmproj'])]
        for flag in ('--native', '--ple-gguf'):
            files.append(Path(config['args'][config['args'].index(flag)+1]))
        pack = Path(config['args'][config['args'].index('--pack')+1])
        files += [pack/'native_experts.txt', pack/'index.txt', pack/'dense.bin',
                  pack/'tokenizer/vocab.json', pack/'tokenizer/merges.txt',
                  pack/'tokenizer/token_type.json']
        mtp = Path(config['args'][config['args'].index('--mtp')+1])
        files += [mtp/f for f in ('experts.bin','dense.bin','dense.txt','draft_vocab.bin')]
        missing = [str(path) for path in files if not path.is_file()]
        if missing:
            parser.error('Required runtime files missing:\n'+'\n'.join(missing))
        if not os.access(config['exe'], os.X_OK) or not os.access(config['vision']['exe'], os.X_OK):
            parser.error('Engine and CPU vision reader must be executable')
    os.umask(0o077)
    output.mkdir(parents=True, exist_ok=True)
    paths = [output/('strata-'+name+'.local.json') for name in configs]
    if any(path.exists() for path in paths):
        parser.error('Config already exists; use a new --out-dir to preserve local edits')
    for name, config in configs.items():
        path = output/('strata-'+name+'.local.json')
        with path.open('x') as stream:
            stream.write(json.dumps(config, indent=2)+'\n')
        print(path)


if __name__ == '__main__':
    main()
