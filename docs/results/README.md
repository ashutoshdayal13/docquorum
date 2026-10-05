# Results shown in the pipeline guide

These are frozen source snapshots checked on **5 October 2026**. The PDF includes
the complete UNIKIE constrained-category Table 4 (15 published systems, all 11
scenarios and the average) and the complete ExtractBench headline value-F1 table
(49 published systems, overall/split F1, category and cost).

DocQuorum's measured configurations are added separately and highlighted. Each
configuration's reference rank compares it independently against the published
systems at two-decimal precision. No external submission has been accepted.

| Benchmark / configuration | Score (%) | Reference rank |
|---|---:|---|
| ExtractBench stored primary | 95.4278 | 5 |
| ExtractBench incremental development | 95.6430 | 5 |
| UNIKIE original 3 readings | 80.6450 | 2 |
| UNIKIE development 4 readings | 81.3175 | 2 |
| UNIKIE tuned 6 readings | 82.3746 | 1, displayed tie with Gemini-3-Pro |

ExtractBench's published leader now scores 96.38 and third place scores 96.03.
The previous rank-3 comparison in older result reports belongs to an earlier
leaderboard snapshot. The dataset revision still matches the recorded local
evaluation; all 95 evaluation-source files are unchanged between its scorer
revision and this snapshot. These checks are recorded in [provenance](provenance.json).

Local rows reuse complete stored-output evaluations. The incremental repair and
four/six-reading configurations are development results. No fresh inference was
run for this documentation update; these examples do not establish a new
held-out result or statistical superiority. UNIKIE's multi-category track is not
evaluated here.

- [Complete original ExtractBench CSV](extractbench-leaderboard.csv), including
  the additional precision/recall, grounding, latency and split-cost columns.
  Only line endings are normalized to LF; all rows and values are retained.
  Published source: [run-llama / ExtractBench, pinned revision](https://github.com/run-llama/ExtractBench/blob/c972087fe7a5132132f7230d1bdb841d3fbf07ed/leaderboard.csv).
- [Complete UNIKIE published table](unikie-published.json), from
  [UNIKIE-BENCH Table 4](https://arxiv.org/html/2602.07038v2#S4.T4).
  Every numerical cell was checked against the paper.
- [DocQuorum ExtractBench measurements](docquorum-extractbench.json), copied
  from the stored-primary and incremental-development provenance summaries.
- [DocQuorum UNIKIE measurements](docquorum-unikie.json), retaining scores,
  scenario values and configuration descriptions from the full coverage audit.
- [Snapshot hashes, source revisions and verification](provenance.json).

The [generator](generate_tables.py) checks snapshot hashes and emits
[the LaTeX tables](../results-tables.tex). `make -C docs` regenerates them when
the snapshots or generator change. Building uses local files only.
