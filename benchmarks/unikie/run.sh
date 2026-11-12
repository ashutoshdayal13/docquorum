#!/bin/bash
# usage: benchmarks/unikie/run.sh <read|read-extra 32|read-extra 8|score>
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
PY=${DQ_PYTHON:-python}
cd "$HERE"
case "$1" in
  read)
    $PY unikie_eval.py parse-images --workers 24
    for r in oneshot image parse oneshot_text; do $PY unikie_eval.py read --reading $r --workers 32; done ;;
  read-extra)
    UNIKIE_MAX_IMAGES=$([ "$2" = 32 ] && echo 2 || echo 4) $PY unikie_eval.py read --reading oneshot$2 --workers 32 ;;
  score|*)
    $PY unikie_eval.py score 2>&1 | grep -v donut ;;
esac
