#!/bin/bash
# usage: benchmarks/extractbench/run.sh <short|medium|long> [doc_workers]
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"
PY=${DQ_PYTHON:-python}
S=$1; DW=${2:-8}
export DQ_RUNS=${DQ_RUNS:-$ROOT/runs} PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
R=$DQ_RUNS; mkdir -p "$R" "$ROOT/logs"
cd "$ROOT"

echo "[1/4] primary reading (text layer + page images; page images alone for scans)"
$PY -m docquorum.agents.reader --split $S --tag ${S}_primary --doc-workers $DW > logs/${S}_primary.log 2>&1
$PY -m docquorum.checks primary $S "$R/${S}_primary" "$R/${S}_primary_final"
rm -rf "$R/${S}_final"; cp -r "$R/${S}_primary_final" "$R/${S}_final"

$PY "$HERE/scans.py" "$S" > "$R/${S}_scans.txt"
SCANS=$(sed -n 1p "$R/${S}_scans.txt"); IMG=$(sed -n 2p "$R/${S}_scans.txt")
if [ -n "$SCANS" ]; then
  echo "[2/4] parse reading for $(echo "$SCANS" | tr ',' '\n' | wc -l) documents without a text layer"
  $PY -m docquorum.agents.reader --split $S --tag ${S}_parse --parsed --only "$SCANS" --doc-workers $DW > logs/${S}_parse.log 2>&1
  $PY -m docquorum.checks parse $S "$R/${S}_parse" "$R/${S}_parse_final"
  cp "$R/${S}_parse_final"/*.json "$R/${S}_final/"
fi
if [ -n "$IMG" ]; then
  echo "      one-shot reading and quorum for the $(echo "$IMG" | tr ',' '\n' | wc -l) that fit one call"
  $PY -m docquorum.agents.oneshot $S "$IMG" "$R/${S}_oneshot" > logs/${S}_oneshot.log 2>&1
  $PY -m docquorum.checks oneshot $S "$R/${S}_oneshot" "$R/${S}_oneshot_final"
  T="$R/${S}_quorum_in"; rm -rf "$T"; mkdir -p "$T/image"
  $PY "$HERE/scans.py" --copy "$R/${S}_primary_final" "$T/image" "$IMG"
  $PY -m docquorum.quorum $S "$R/${S}_quorum" "$T/image" "$R/${S}_parse_final" "$R/${S}_oneshot_final"
  cp "$R/${S}_quorum"/*.json "$R/${S}_final/"
  rm -f "$R/${S}_final/_medoid.json"
fi
if [ "$S" != short ]; then
  echo "[3/4] layout readers (column flow / ruled scans) where the layout selects them"
  $PY -m docquorum.agents.layout $S > logs/${S}_layout.log 2>&1 || true
  for d in "$R/${S}_colflow" "$R/${S}_ruled"; do
    [ -d "$d" ] && $PY -m docquorum.checks layout $S "$d" "$d.final" && cp "$d.final"/*.json "$R/${S}_final/"
  done
fi
echo "[4/4] score"
$PY "$HERE/score_run.py" --split $S --run "$R/${S}_final" --json "$R/${S}_scores.json" | tail -n 1
