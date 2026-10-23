#!/usr/bin/env bash
# Foreground, one instance; Ctrl+C stops this server. No systemd or production changes.
set -euo pipefail
if [ "$#" -ne 1 ]; then
  echo 'Usage: bash scripts/run.sh CONFIG.local.json' >&2
  exit 2
fi
python3 - "$1" <<'PY'
import json
import os
from pathlib import Path
import socket
import sys
cpath = Path(sys.argv[1]).expanduser().resolve()
c = json.loads(cpath.read_text())
if c.get('host') != '127.0.0.1':
    raise SystemExit('This helper is for localhost configs; set up remote access separately.')
with socket.socket() as probe:
    probe.bind(('127.0.0.1', int(c['port'])))
root = Path(c['cwd'])
os.chdir(root)
python = root/'.venv/bin/python'
os.execv(str(python), [str(python), '-u', 'serve/server.py', '--engine', 'strata',
                      '--config', str(cpath), '--port', str(c['port'])])
PY
