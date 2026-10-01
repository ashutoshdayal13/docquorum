#!/bin/bash
# DocQuorum on UNIKIE-BENCH (all 11 constrained scenarios, 4,472 images), official evaluator,
# every input capped at the benchmark's 1,605,632 pixels.
#
#   benchmarks/unikie/run.sh score            re-score the stored readings (exact reproduction)
#   benchmarks/unikie/run.sh read             fresh readings with the main model (27B):
#                                             oneshot, image, parse, oneshot_text
#   benchmarks/unikie/run.sh read-extra MODEL fresh one-shot readings from a second model served
#                                             at $DQ_LLM_URL (MODEL = 32 -> oneshot32, 8 -> oneshot8)
#
# DocQuorum: quorum over six readings (image, parse, oneshot, oneshot_text from Qwen3.8-27B;
# oneshot32, oneshot8 from Qwen3-VL-32B / -8B) -> 82.37 macro F1 on all 4,472 images
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
PY=${DQ_PYTHON:-python}
cd "$HERE"
case "$1" in
  read)
    $PY unikie_eval.py parse-images --workers 24          # needs the MinerU parser
    for r in oneshot image parse oneshot_text; do $PY unikie_eval.py read --reading $r --workers 32; done ;;
  read-extra)
    UNIKIE_MAX_IMAGES=$([ "$2" = 32 ] && echo 2 || echo 4) $PY unikie_eval.py read --reading oneshot$2 --workers 32 ;;
  score|*)
    $PY unikie_eval.py score 2>&1 | grep -v donut ;;
esac
