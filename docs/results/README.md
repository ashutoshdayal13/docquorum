# Results shown in the pipeline guide

The PDF uses the **historical ExtractBench table from our 2 October 2026
comparison**, where DocQuorum ranked third. It includes all 47 published systems,
overall/split F1, category and cost. The complete UNIKIE constrained-category
Table 4 contains 15 published systems, all 11 scenarios and the average; its
values were verified against the paper on 5 October 2026.

DocQuorum's measured configurations are added separately and highlighted. Each
configuration's reference rank compares it independently against the published
systems at two-decimal precision. No external submission has been accepted.

| Benchmark / configuration | Score (%) | Reference rank |
|---|---:|---|
| ExtractBench stored primary | 95.4278 | 3, historical snapshot |
| ExtractBench incremental development | 95.6430 | 3, historical snapshot |
| UNIKIE original 3 readings | 80.6450 | 2 |
| UNIKIE development 4 readings | 81.3175 | 2 |
| UNIKIE tuned 6 readings | 82.3746 | 1, displayed tie with Gemini-3-Pro |

In this historical ExtractBench snapshot, LlamaExtract Agentic Plus and Pulse
(Effort) both score 95.91; the next published system, LlamaExtract Agentic, scores
94.77. Each DocQuorum variant is compared independently, placing it third among
47 published systems plus that variant. This is a historical reference rank.
The pinned upstream CSV exactly matches all 47 systems and overall scores in
our earlier saved comparison, `results/multibench/extractbench_public_rows.json`.
Its revision is also the recorded scorer revision for the local measurements.
Source revision, commit date and hashes are recorded in [provenance](provenance.json).

Local rows reuse complete stored-output evaluations. The incremental repair and
four/six-reading configurations are development results. No fresh inference was
run for this documentation update; these examples do not establish a new
held-out result or statistical superiority. UNIKIE's multi-category track is not
evaluated here.

- [Complete original ExtractBench CSV](extractbench-leaderboard.csv), including
  the additional precision/recall, grounding, latency and split-cost columns.
  Only line endings are normalized to LF; all rows and values are retained.
  Published source: [run-llama / ExtractBench, historical pinned revision](https://github.com/run-llama/ExtractBench/blob/c8e59696b19c50d904801390dedef8d292d529e7/leaderboard.csv).
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
