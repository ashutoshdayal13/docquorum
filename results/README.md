# DocQuorum results

All numbers use each benchmark's own scorer. The research log (`RESEARCH_LOG.md`) records
every experiment, including the rejected ones and one correction (§13).

## ExtractBench (LlamaIndex; arXiv 2607.29677)

370 documents (252 short, 98 medium, 20 long), current scorer (`extract_unified_value_f1`),
Overall = mean over all 370 documents, as on the public leaderboard.
Model: Qwen3.8-27B-FP8 served with vLLM, one GPU.

| split | DocQuorum | rank among the 11 leaderboard rows scored with the current scorer |
|---|---:|---|
| short (252) | **96.11** | 3 |
| medium (98) | **94.03** | 3 |
| long (20) | **90.41** | 3 (above LlamaExtract Agentic Plus, 90.18) |
| **Overall** | **95.25** (95% CI 94.64-95.85) | **3** (also 3 of all 45 rows) |

Leaders: LlamaExtract Agentic Plus 95.91, Pulse (Effort) 95.91; then DocQuorum; then
LlamaExtract Agentic 94.77 and Codex (GPT-5.6 Sol Evidence) 93.77. The best open-weight entry on
the leaderboard (Qwen3.8-27B, one call) is 89.75 (older scorer); the same model through the
benchmark's own one-shot code scores ~90 on the short split under the current scorer.

Configuration (one rule for both benchmarks):
* a PDF with a text layer (born-digital, or a scan carrying an OCR layer) is read once by the
  agentic reader, on its text plus page images rendered at 220 dpi (<= 5 MP); an OCR layer is
  labelled as machine-read, with the page image deciding;
* a document without a text layer is read through its MinerU parse; when it fits one call
  (<= 12 pages) it is also read from the page images alone and by the one-shot reader, and the
  quorum keeps the reading the others agree with most (UNIKIE's images are all of this kind);
* a layout reader replaces the reading where the document's own page geometry selects one
  (column flow; ruled tables on scans);
* every reading passes the repairs and the page-grounded checks, which now include numbers as
  printed (`checks/printed_numbers.py`) and the schema's declared default for an empty list;
* a whole-document reply that leaves schema keys out is read again with every key required.

What changed since the 94.18 of the previous version (short split, each on top of the
previous; RESEARCH_LOG §14):

| change | short |
|---|---:|
| previous configuration | 94.97 |
| numbers as printed | 95.06 |
| text-layer PDFs keep the primary reading | 95.14 |
| page images at 220 dpi instead of 150 | 95.57 |
| OCR layers labelled as OCR; tax-return scans reach the schema split | 95.71 |
| skipped schema keys -> re-read with every key required | 95.82 |
| empty list -> the schema's declared default | 95.98 |
| blank check box -> false where the description says so | 96.03 |
| blank pre-printed lines dropped, never given a carried-down value | 96.11 |

Medium: numbers as printed 93.12 -> 93.57; long tax-return scans read by the schema split with
page images in windows of <= 8 pages (their OCR parse had the form labels without the typed
entries; 12 of 14 up, 1 down by 0.27) 93.57 -> 94.03. Long (the page-geometry layout readers re-run with the current 27B model on
the documents they select: two ruled scans 87.9 -> 95.4 and 83.7 -> 92.7, a column-flow list
87.0 -> 89.0), and the remaining scan read through its parse (97.3 -> 98.3): 89.44 -> 90.41.

Rejected this round (measured): a field-level vote over four readings, filling one reading's
nulls from the others, page tiles for 13-24-page text PDFs, reasoning mode (39 documents:
+0.01 at 2-3x the time, one empty reply), a 220-dpi one-shot reading, re-asking fields returned
null (at most 13% of our nulls are wrong, so a re-ask would cost more than it recovers).

`extractbench/provenance.json` names the reading behind every final output;
`extractbench/scores/short_quorum_picks.json` has the quorum's agreement scores for the
97 short scans; `extractbench/previous_94.18/` keeps the previous version's outputs.

Caveats:
* The benchmark was used for development (errors were read document by document to find
  the defects the pipeline repairs). The one frozen held-out run (types never inspected,
  before later fixes) scored **94.55** on 195 short and **87.01** on 76 medium documents.
* The final outputs were assembled from separate runs of the same code (the 220-dpi primary
  reading, its OCR-labelled and require-all re-reads, the parse and one-shot readings, the
  layout readers; `provenance.json` names each document's source), not from one pass of
  `benchmarks/extractbench/run.sh`, which chains the same steps. Run-to-run noise measured on
  the short split: 61 of 251 documents change, mean |change| 0.76, split mean within 0.15.
* Where the annotation contradicts its own schema (a masked SSN the schema says to return
  as 'XXX-XX-XXXX', margins the schema says to round to two decimals, a check amount the
  schema says to print with '$'), the pipeline follows the schema and loses those cells.

Files: `extractbench/predictions/<split>/<doc>.json` (final outputs),
`extractbench/scores/<split>.json` (per-document F1 / precision / recall).
Re-score: `benchmarks/extractbench/score_run.py` (see the top-level README).

## UNIKIE-BENCH (ACL 2026; arXiv 2602.07038)

All 11 constrained scenarios, 4,472 images, the benchmark's own evaluator, every input capped
at the benchmark's 1,605,632 pixels (the cap all published systems were measured under).

| macro F1 | test (2,986 docs) | full set (4,472) | vs. the paper's Table 4 |
|---|---:|---:|---|
| Qwen3.8-27B, the benchmark's own one-shot protocol | 79.94 | 80.45 | |
| **DocQuorum, frozen** (held-out: never developed on UNIKIE) | 80.01 | **80.64** | **2nd of 16** |
| **DocQuorum, tuned** (3 open models; developed on a fixed dev third) | **81.89** | **82.37** | **ties 1st** |
| Gemini-3-Pro (best published) | -- | 82.37 | 1st |
| Qwen3-VL-8B (best published open model) | -- | 79.12 | |

* Frozen: consensus over three readings of Qwen3.8-27B (agentic image reading, agentic reading
  on the MinerU parse, the benchmark's one-shot prompt).
* Tuned: + a one-shot reading with the OCR text (27B), + one-shot readings from
  Qwen3-VL-32B and Qwen3-VL-8B. Developed on the dev third (1,486 documents) of a
  hash-fixed split (`benchmarks/unikie/unikie_split.json`), run once on the test two-thirds.
  Unrounded: 82.3746 vs Gemini-3-Pro's 82.3664 (mean of its 11 published two-decimal
  scores) -- a tie within the table's rounding, not a win.
* Above every published system on: Administrative, Catering, Retail, Tax-Compliant (tuned).

Per scenario (F1 on all 4,472 images; published values from the paper's Table 4; **bold** =
best of the 16 published systems and DocQuorum; rank = DocQuorum's position when inserted
among the 16 published systems, frozen / tuned):

| scenario | GPT-5 | Claude Sonnet 4.5 | Qwen3-VL-Plus | Gemini-3-Pro | Qwen3-VL-8B (best open) | DocQuorum frozen | DocQuorum tuned | rank |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| Retail | 71.90 | 69.24 | 89.12 | 89.27 | 88.26 | 89.63 | **90.71** | 1 / 1 |
| Catering-Services | 71.33 | 73.65 | 86.45 | 83.54 | 86.23 | 80.70 | **87.56** | 5 / 1 |
| Commercial | 45.94 | 45.92 | 50.57 | **53.87** | 51.14 | 51.86 | 53.46 | 2 / 2 |
| Accommodation | 69.29 | 69.29 | 77.86 | **81.43** | 71.07 | 78.93 | 80.00 | 2 / 2 |
| Postal-Label | 80.95 | 79.45 | 83.55 | **90.74** | 83.80 | 85.15 | 85.65 | 2 / 2 |
| Administrative | 62.79 | 69.20 | 78.91 | 84.32 | 78.90 | 85.57 | **86.60** | 1 / 1 |
| Education | 50.26 | 39.46 | **87.44** | 80.71 | 87.39 | 84.53 | 85.46 | 3 / 3 |
| Advertisement | 75.48 | 85.06 | 83.14 | **90.54** | 81.23 | 83.91 | 86.21 | 3 / 2 |
| Tax-Compliant | 72.05 | 67.79 | 78.93 | 81.54 | 78.74 | 81.43 | **82.10** | 2 / 1 |
| Medical-Services | 67.71 | 63.96 | 76.46 | **77.60** | 77.19 | 76.56 | 77.50 | 3 / 2 |
| Nutrition-Label | 75.83 | 67.24 | 89.72 | **92.47** | 86.36 | 88.83 | 90.87 | 3 / 2 |
| *macro average* | 67.59 | 66.39 | 80.20 | **82.37** | 79.12 | 80.64 | **82.37** | 2 / 1 (tie) |

Commercial is the hardest scenario for every system (GPT-5 45.94, Claude Sonnet 4.5 45.92);
DocQuorum is second only to Gemini-3-Pro there, frozen and tuned.

Why Commercial is low for everyone (dev split, tuned configuration, 817 wrong fields of 206
documents): its answer key is inherited from DocILE and does not follow UNIKIE's own guideline
of "exact textual content". The key drops the currency symbol from every amount (0 of 1,579
amounts carry one, although the invoices print "$510.00"), while Advertisement keeps it (56 of
61). 188 of the 817 errors are exactly that `$`. Most of the rest are block boundaries
applied inconsistently (an address with or without the company name above it) and the choice
among several printed numbers for `order_id`. The templates give no way to tell the two
conventions apart (no currency field in any scenario). Stripping the symbol everywhere lowers
the macro (Advertisement 91.0 -> 67.4). Stripping it in Commercial alone would add about
+1.0 macro on dev, but that is learning one scenario's annotation convention from its
labels, so it is not used: every number above is zero-shot with respect to output conventions.

The OCR label added to ExtractBench readings (RESEARCH_LOG §14) also transfers here: the
parse reading alone goes from 80.50 to 80.96 on the dev split, while the quorums absorb it
(frozen 81.87 -> 81.93, tuned 83.30 -> 83.29), so neither configuration changes.

Files: `unikie/readings/<reading>/<scenario>.json` (every reading),
`unikie/summary.json` (per-scenario scores). Re-score: `benchmarks/unikie/run.sh score`.

## Held out: Contextual AI's ExtractBench (KDD 2026; arXiv 2602.12247)

A second, independently built benchmark that DocQuorum had never seen: 35 PDFs (2,076 pages)
in five domains, one JSON Schema per domain (12 to 369 fields), human-annotated gold, and the
benchmark's own evaluator (`extract_bench`: each field declares its metric; arrays are judged
by an LLM).

**Protocol.** The pipeline was frozen (`FROZEN.json`: 61 file hashes, 2026-09-28 02:40:55
UTC) before the benchmark was downloaded. Only adapters were written
(`benchmarks/contextual/`): the input adapter passes each schema without its scoring
annotations (`evaluation_config`) and no gold; the frozen ExtractBench runner ran unchanged;
the output adapter calls the benchmark's evaluator. One run; the hashes were checked
unchanged at scoring time. (A first start was stopped after five minutes, before any
document finished or anything was scored, when the input adapter turned out to pass the
resume schema's wrapper instead of the schema inside it.)

**Judge.** The paper judged with Gemini 2.5 Flash. Here the evaluator's LLM metrics ran on a
local model -- Qwen3.8-27B, the extraction model, reasoning off, temperature 0, the paper's
pass threshold 0.7 -- so no document left the machine. Scored against itself, the gold passes
690 of the 691 fields the evaluator checks; the one failure is a 1,081-item citation list too
long for the local judge's 131k-token context, and it fails for DocQuorum too.

**Metric**, as in the paper's Table 5: *valid JSON* = the output parses and validates against
the schema; *pass rate* = passed fields / (schema keys x documents) = passed / 3,086, an
invalid extraction passing none; *Acc (valid)* = passed / evaluated fields over valid
extractions. The released evaluator judges an array as one field, so the keys inside arrays
can never pass: the gold itself reaches a pass rate of 22.4%, not 100%.

| system | valid JSON | Credit | Research | Resumes | Sports | SEC 10-K/Q | pass rate | Acc (valid) |
|---|---|---|---|---|---|---|---|---|
| **DocQuorum, frozen (held out)** | **26/35** | 57/130 (43.8%) | 29/96 (30.2%) | 12/217 (5.5%) | **24/60 (40.0%)** | **57/2583 (2.2%)** | 179/3086 (5.8%) | 33.3% |
| DocQuorum, post-hoc fixes (not held out) | **35/35** | 103/130 (79.2%) | 45/96 (46.9%) | **69/217 (31.8%)** | **24/60 (40.0%)** | **91/2583 (3.5%)** | **332/3086 (10.8%)** | 48.0% |
| Gemini 3 Flash (paper) | 25/35 | 111/130 (85.4%) | 46/96 (47.9%) | 45/217 (20.7%) | 11/60 (18.3%) | 0/2583 (0.0%) | 213/3086 (6.9%) | 74.7% |
| Gemini 3 Pro (paper) | 21/35 | 110/130 (84.6%) | 5/96 (5.2%) | 46/217 (21.2%) | 8/60 (13.3%) | 0/2583 (0.0%) | 169/3086 (5.5%) | 74.8% |
| GPT-5.2 (paper) | 21/35 | 105/130 (80.8%) | 6/96 (6.2%) | 43/217 (19.8%) | 8/60 (13.3%) | 0/2583 (0.0%) | 162/3086 (5.2%) | 71.7% |
| GPT-5 (paper) | 13/35 | **113/130 (86.9%)** | 0/96 (0.0%) | 8/217 (3.7%) | 2/60 (3.3%) | 0/2583 (0.0%) | 123/3086 (4.0%) | **80.4%** |
| Claude Sonnet 4.5 (paper) | 15/35 | 0/130 (0.0%) | **47/96 (49.0%)** | 46/217 (21.2%) | 8/60 (13.3%) | 0/2583 (0.0%) | 101/3086 (3.3%) | 66.9% |
| Claude Opus 4.5 (paper) | 12/35 | 0/130 (0.0%) | 16/96 (16.7%) | 52/217 (24.0%) | 8/60 (13.3%) | 0/2583 (0.0%) | 76/3086 (2.5%) | 65.0% |
| *gold scored against itself (ceiling)* | 35/35 | 130/130 | 59/96 (61.5%) | 91/217 (41.9%) | 25/60 (41.7%) | 385/2583 (14.9%) | 690/3086 (22.4%) | 99.9% |

* **Frozen, held out: 2nd of 7 on the pass rate** (5.8% against Gemini 3 Flash's 6.9%), with
  the most valid outputs of any system (26/35) and the only valid SEC 10-Q outputs (6 of 7;
  every model in the paper 0 of 7). Sports is at 40.0% of a 41.7% ceiling.
* Acc (valid) is not like for like: the paper's models have no valid SEC output, so SEC never
  enters their denominator. Without SEC, DocQuorum's Acc (valid) is 58.7% frozen and 78.8%
  post-hoc (paper: 65.0-80.4%).
* Judge-independent fields (exact, fuzzy, numeric, boolean metrics) pass 70 of 102 frozen
  (validity ignored) and 80 of 102 post-hoc; the other 589 are judged by the local model.

**What the held-out run exposed** (frozen): four generic defects, none visible on the
benchmarks DocQuorum was built on.

1. *Invalid output*, 9 of 35 documents, each then counting zero: nulls written into optional
   fields that do not admit null (the re-read with every key required made them nullable), 4
   documents; lists of strings returned as `{"type": ...}` objects (the page-chunk reader
   guided every list as a list of objects), 4; a required section missing, 1. Six of the
   seven resumes were invalid although 70 of their 91 checkable fields were right.
2. *A routing gap*: a document too long for one call whose schema keeps its arrays inside
   objects (a 10-Q's 52 statement lines, a credit agreement's lenders) went to a single call
   that saw its whole text only up to 240k characters -- otherwise its first three and last
   two pages -- with a reply capped for scalar fields. Credit: the one agreement read whole
   passed 11 of 13 fields, the nine others 3 to 7.
3. *A crash on font names*: the five sports PDFs use Shift-JIS font names, which made a strict
   UTF-8 decode of `pdffonts` output raise and cost them the whole-document reading (the
   fallback still reached 24 of 25 checkable fields).
4. *Fiscal periods* (not fixed): the 10-Q schema labels periods by fiscal quarter, and the
   model often names the calendar quarter instead (McKesson's fiscal Q2 as "FY2025 Q3"), so
   right values sit in wrong items and whole arrays fail. The gold has errors of its own
   here (McKesson's quarter end recorded as 2024-08-02; it is 2024-09-30).

**Post-hoc fixes** (`results/contextual/POSTHOC.json`; each reads only the document, the
schema or the tool output): F1 decode tool output leniently; F2 read such long documents in
windows of their text that each fit one call, every window asked for the whole schema,
windows merged; F3 read a list of plain values as one-field records under the item's own
schema; F4 keep the output schema-valid (drop a null the schema does not admit in an optional
field, add a missing required object or list empty). These numbers are **not held out**:
the defects were found by reading this benchmark's failures. On the benchmarks above they
change nothing: F4 changes none of the 370 stored ExtractBench outputs, F1-F3 change no
routing decision for any of the 370 documents (including the whole-document fallbacks in the
run logs), and UNIKIE's template schemas admit null everywhere with every image fitting one
call. The reported ExtractBench and UNIKIE numbers therefore stand.

Files: `contextual/frozen/` (held-out predictions, the evaluator's report per document,
scores, logs, and the four frozen source files the fixes later changed, byte-identical to
`FROZEN.json`), `contextual/posthoc/`, `contextual/gold_ceiling/`. Re-score:
`python benchmarks/contextual/score.py --run results/contextual/frozen/predictions --out /tmp/cx
--ceiling results/contextual/gold_ceiling/scores.json` (needs `pip install -e` of the
benchmark's repository and a judge endpoint). Run: `benchmarks/contextual/run.sh`.
