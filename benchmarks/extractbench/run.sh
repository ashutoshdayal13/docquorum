#!/bin/bash
# Run DocQuorum end to end on an ExtractBench split (fresh model calls) and score it.
#
#   benchmarks/extractbench/run.sh <short|medium|long> [doc_workers]
#
# Needs: the extraction model served at $DQ_LLM_URL (serve/serve_qwen38_27b.sh), the MinerU
# parser at $DQ_PARSER_URL for scans (serve/serve_mineru.sh; parses are cached in
# cache/parse), ExtractBench's data at data/extractbench. Outputs go to $DQ_RUNS (runs/).
#
# The rule, one rule for both benchmarks:
#   * a document that carries a text layer (a digital PDF, or a scan with an OCR layer) is
#     read once, by the reader agent on its text and page images;
#   * a document WITHOUT a text layer is read through its MinerU parse (OCR text + page images,
#     pairs of pages side by side for 13-24 pages); when it fits one call (<= 12 pages) it is
#     also read from the page images alone and by the one-shot reader, and the quorum keeps
#     the reading the others agree with most;
#   * layout readers (column flow, ruled scans) replace the reading where the document's own
#     layout selects them.
# Every reading passes its chain of checks (python -m docquorum.checks).
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

# documents without a text layer: all of them (SCANS) and those that fit one call (IMG)
$PY "$HERE/scans.py" "$S" > "$R/${S}_scans.txt"
SCANS=$(sed -n 1p "$R/${S}_scans.txt"); IMG=$(sed -n 2p "$R/${S}_scans.txt")
if [ -n "$SCANS" ]; then
  echo "[2/4] parse reading for $(echo "$SCANS" | tr ',' '\n' | wc -l) documents without a text layer"
  $PY -m docquorum.agents.reader --split $S --tag ${S}_parse --parsed --only "$SCANS" --doc-workers $DW > logs/${S}_parse.log 2>&1
  $PY -m docquorum.checks parse $S "$R/${S}_parse" "$R/${S}_parse_final"
  cp "$R/${S}_parse_final"/*.json "$R/${S}_final/"          # a scan is read through its parse
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
