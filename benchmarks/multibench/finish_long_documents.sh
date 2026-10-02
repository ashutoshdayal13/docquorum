#!/usr/bin/env bash
# Complete the frozen V4 cohorts after the shorter predecessor evaluations.
# Usage: finish_long_documents.sh longextract|longarray OWNED_PREDECESSOR_PID
set -euo pipefail
cd "$(dirname "$0")/../.."
test "$(git branch --show-current)" = experiment/multibench-20261002
source configs/local.env
export DQ_LLM_URL=http://localhost:8078/v1 DQ_MODEL_NAME=dq-multibench8b

benchmark="${1:?benchmark required}"
predecessor="${2:?owned predecessor PID required}"
case "$benchmark" in
  longextract)
    expected='benchmarks/multibench/docubench.py run --profile bounded-v4'
    out=results/multibench/longextract_v4
    ;;
  longarray)
    expected='benchmarks/multibench/longarray.py run --scope pilot --profile bounded-v4'
    out=results/multibench/longarray_v4
    ;;
  *) exit 2 ;;
esac

python3 - "$predecessor" "$expected" <<'PY'
import sys,time
from pathlib import Path
pid, expected = sys.argv[1:]
if not pid.isdecimal(): raise ValueError('Expected a process ID')
path=Path(f'/proc/{pid}/cmdline')
initial=True
while path.exists():
    try: command=path.read_bytes().replace(b'\0',b' ').decode()
    except FileNotFoundError: break
    if expected not in command:
        if initial: raise RuntimeError('Predecessor command does not match the owned job')
        break  # the original PID ended and may have been reused
    initial=False
    time.sleep(10)
print('Predecessor finished; starting frozen full cohort',flush=True)
PY

if [[ "$benchmark" == longarray ]]; then
  test -f "$out/scores/pilot/summary.json"
fi
test -f "$out/manifest.json"
# One document at a time, with the extractor's existing two chunk workers;
# share the model queue with the other authorized runs.
"$DQ_PYTHON" "benchmarks/multibench/$benchmark.py" run --scope full --profile bounded-v4 --out "$out" --workers 1
"$DQ_PYTHON" "benchmarks/multibench/$benchmark.py" score --scope full --out "$out"
"$DQ_PYTHON" benchmarks/multibench/leaderboard.py
"$DQ_PYTHON" benchmarks/multibench/publish_completed.py
