#!/bin/bash
# Held-out run of the frozen DocQuorum on Contextual AI's ExtractBench (arXiv 2602.12247:
# 35 PDFs, 2,076 pages, 5 schemas of 12-369 fields). Only adapters live in this folder; the
# pipeline and its runner are the ones frozen before this benchmark was downloaded
# (FROZEN.json; the code has since been reorganised without changing any reading).
#
#   benchmarks/contextual/run.sh [doc_workers]
#   CX_RUNS=<dir> CX_OUT=<dir> benchmarks/contextual/run.sh      (defaults: runs/contextual, results/contextual/latest)
#
#   1. prepare.py  the benchmark's tasks as a DocQuorum split: the schema without its scoring
#                  annotations, no gold
#   2. front end   MinerU parse of the documents without a text layer (the ExtractBench
#                  runner expects the parses in the cache)
#   3. the frozen ExtractBench runner, unchanged, on that split. Its last step scores with
#      the LlamaIndex harness, which has no labels for these documents; that line is ignored.
#   4. score.py    the benchmark's own evaluator (extract_bench.ReportBuilder), in its own
#                  environment ($CX_PYTHON, with `pip install -e <extract-bench repo>`)
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"
PY=${DQ_PYTHON:-python}
export DQ_EXTRACTBENCH_DATA="$ROOT/data/contextual" DQ_RUNS="${CX_RUNS:-$ROOT/runs/contextual}" PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
OUT="${CX_OUT:-$ROOT/results/contextual/latest}"; CEIL="$ROOT/results/contextual/gold_ceiling/scores.json"
mkdir -p "$DQ_RUNS" "$ROOT/logs"

echo "[cx 1/4] input adapter"
$PY "$HERE/prepare.py" --out "$DQ_EXTRACTBENCH_DATA" --split cx

echo "[cx 2/4] MinerU parse of the documents without a text layer"
$PY -m docquorum.tools.parser cx

echo "[cx 3/4] the frozen runner"
"$ROOT/benchmarks/extractbench/run.sh" cx ${1:-8}

echo "[cx 4/4] the benchmark's evaluator"
[ -f "$CEIL" ] || ${CX_PYTHON:-python} "$HERE/score.py" --gold-self --out "$(dirname "$CEIL")"
${CX_PYTHON:-python} "$HERE/score.py" --run "$DQ_RUNS/cx_final" --out "$OUT" --ceiling "$CEIL"
