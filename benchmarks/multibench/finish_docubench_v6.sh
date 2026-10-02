#!/usr/bin/env bash
# Finish all 72 tasks after the V4 comparison and selected V6 checks.
set -euo pipefail
cd "$(dirname "$0")/../.."
test "$(git branch --show-current)" = experiment/multibench-20261002
source configs/local.env
export DQ_LLM_URL=http://localhost:8078/v1 DQ_MODEL_NAME=dq-multibench8b
python3 - "${1:?V4 controller PID}" "${2:?V6 checks controller PID}" <<'PY'
import json,sys,time
from pathlib import Path
jobs=zip(sys.argv[1:],[
 'benchmarks/multibench/docubench.py run --profile bounded-v4',
 'benchmarks/multibench/docubench.py run --profile bounded-v6'])
for pid,expected in jobs:
    if not pid.isdecimal():raise ValueError('Expected process ID')
    path=Path(f'/proc/{pid}/cmdline');initial=True
    while path.exists():
        try:command=path.read_bytes().replace(b'\0',b' ').decode()
        except FileNotFoundError:break
        if expected not in command:
            if initial:raise RuntimeError('Predecessor does not match owned evaluation')
            break
        initial=False;time.sleep(10)
reference=json.loads(Path('results/multibench/docubench_v4/summary.json').read_text())
if not (reference['attempted']==reference['expected']==72 and reference['eligible_for_full_ranking']):
    raise RuntimeError('V4 comparison is not complete')
print('Predecessors completed; running the full frozen V6 cohort',flush=True)
PY
"$DQ_PYTHON" benchmarks/multibench/docubench.py run --profile bounded-v6 --out results/multibench/docubench_v6 --workers 1
"$DQ_PYTHON" benchmarks/multibench/docubench.py score --out results/multibench/docubench_v6
"$DQ_PYTHON" benchmarks/multibench/leaderboard.py
"$DQ_PYTHON" benchmarks/multibench/publish_completed.py
