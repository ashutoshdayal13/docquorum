# DocQuorum: additional benchmark experiments

Branch: `experiment/multibench-20261002`, based on `fb69fc4eab65ec690c892e36e43f7a3c53936693`. Checked 2 October 2026. Work remains in progress. No result here has been submitted to an external leaderboard.

The strongest current evidence is the existing UNIKIE evaluation: the original three-reading configuration re-scores to **80.6450** across all 4,472 constrained-category documents, above the paper's third-place 79.12. The separately tuned six-reading configuration re-scores to **82.3746**, tying the displayed leader, 82.37. It must not replace the original held-out result. The added four-reading configuration scores 81.3175 and is also development work. [Primary paper, Table 4](https://arxiv.org/html/2602.07038v2); [full coverage audit](results/multibench/unikie_audit.json).

## Benchmarks and targets

Scores within each row use that benchmark's metric; percentages across rows are not interchangeable. Published commercial benchmark results are reference comparisons, rather than our own paired re-runs of those providers.

| Benchmark and scope | Metric | Published leader | Published third | DocQuorum evidence | Status |
|---|---|---:|---:|---|---|
| [run-llama ExtractBench](https://github.com/run-llama/ExtractBench), 370 documents | Mean document unified value F1 | 95.91, LlamaExtract Agentic Plus / Pulse Effort | 94.77, LlamaExtract Agentic | Historical 95.25; current stored-output re-score is being audited | Development reference; no official submission |
| [UNIKIE](https://arxiv.org/html/2602.07038v2), 4,472 constrained-category documents | Macro scenario field F1 | 82.37, Gemini 3 Pro | 79.12, Qwen3-VL 8B | Original 80.6450; tuned 82.3746 | Full stored-output re-score; original result exceeds third |
| [DocuBench](https://github.com/DocuPipe/DocuBench), all 72 tasks / 10 formats, v0.2.0 | Macro document field accuracy | 97.0170, DocuPipe high | 91.7324, Claude Sonnet 5 | Full 8B variant run underway | Public peer outputs independently re-scored with official code |
| [VAREX](https://udibarzi.github.io/varex-bench/), 1,777 forms, image-only track | Micro normalized field exact match | 98.0, Gemini 2.5 Pro | 96.6, Qwen3-VL 8B | 36-document pilot: 94.8081; full run underway | Pilot is ineligible for ranking |
| [LongArray-Extract](https://www.extend.ai/resources/long-array-extraction-benchmark), all 45 PDFs | Mean document accuracy; failed documents score zero | 99.2, Extend MAX | 83.1, Claude Opus 4.7 | Three-document pilot underway | All 45 source inputs prepared; official reference scorer |
| [Contextual AI Extract Bench](https://arxiv.org/html/2602.12247v1), all 35 tasks | End-to-end field pass rate, official Gemini 2.5 Flash judge | 6.9, Gemini 3 Flash | 5.2, GPT-5.2 | 32/35 stored outputs are schema-valid; **content pass rate unknown** | Matching judge configuration needed |
| [LongExtractBench](https://github.com/micro1-research/longextract-bench), public 50-document subset | Completed-document leaf accuracy, with row P/R and failures separately | No verified public-50 comparison | Unknown | Sources downloaded and pinned | Published 225-document outcomes cannot rank our public-50 run |

DocuBench's high and standard profiles and Claude were reproduced from every public output, rather than copied from rounded table entries: 97.0169874, 96.1401270 and 91.7323502. All ten available peer result folders cover 72 documents, including the Pulse folder not shown in the README's nine-entry table. [Machine-readable audit](results/multibench/docubench_public_audit.json).

Contextual's stored `cx_scores.json` contains all-zero scores from an adapter with empty expected outputs; those are not valid benchmark scores. Older local judge logs used Qwen and include judge context failures, which also prevent comparison to the published Gemini-judged results. The schema audit validates against the original supplied schemas and confirms that all 35 schema/gold/PDF inputs match the pinned current official repository. Validity is **91.43% (32/35)**, with 6/7 SEC filing outputs valid, but this does not establish an accuracy rank. [Audit](results/multibench/contextual_schema_audit.json).

## Configurations being measured

The original frozen configuration uses Qwen3.8-27B and MinerU. The model and parser endpoints are down; the shared H100 has about 21 GB of spare memory. The new runs therefore use an explicitly separate **Qwen3-VL-8B-Instruct-FP8** variant, revision `9cdc6310a8cb770ce18efaf4e9935334512aee45`, with a 32,768-token context and 8,192-token output ceiling. Its server uses 0.18 of GPU memory and does not stop the existing GPU process. These scores will not be labelled as fresh measurements of the frozen 27B pipeline.

VAREX's `official` reading uses the publisher's extraction prompt and original image; `whole` uses DocQuorum's whole-page prompt; `guided` uses that prompt with schema decoding. The quorum follows the existing recall-weighted agreement rule, beta 2, with the fixed order official → whole → guided. No supplied OCR/layout text is used in the image-only track. The fixed pilot takes 12 documents per official split in SHA256 order, selected without labels. On its 443 scoreable fields: official 94.8081, whole 94.1309, guided 94.1309, quorum 94.8081. There is **no measured quorum gain in this pilot**. The full-run policy was started before evaluating the pilot. [Pilot results](results/multibench/varex/scores/pilot/summary.json).

DocuBench and LongArray use the existing reader and checks under `DocQuorum8B-bounded-v1`: exact server tokenization reserves output space before requests; full source text is never clipped by the budget guard; multiple images supplied through that client are composed in page order with a disclosed five-million-pixel cap. DocuBench additionally reads XLSX, DOCX, TXT, XML, HTML and CSV directly, preserving Unicode, cells and source order; multi-frame TIFF is converted with all frames. Its published per-document guidelines are included. All 72 tasks count in the score, and unavailable/failed outputs score zero.

The running baseline exposed two source-derived problems. The scalar reader can exceed the smaller context and silently produce `{}`; it also only reads the first two pages for scan scalars. The external one-shot provider builds its own client, bypassing our guard, and its context-fitting fallback can drop pages or prune schema fields. These are diagnosed from input/request behavior, rather than gold errors.

`DocQuorum8B-bounded-v2` is a separate candidate: scalar schema/page partitions visit the complete source; the external one-shot call uses the guarded client directly, without its dropping/pruning fallback; truncated one-shot outputs are rejected. V2's score and gain are **not measured yet**. Changes are confined to experiment runner processes; the frozen pipeline source is unchanged.

LongArray inference sees only the original PDF and supplied vertical schema. Its ground truth, `target_count`, target field metadata and generated page maps are excluded. Scoring loads the publisher's reference implementation verbatim from the pinned dataset card. It reports predicted and expected array lengths because that metric alone does not penalize surplus rows. A complete result must count all 45 documents, with failures contributing zero.

## Reproduction and next measurements

The third-party sources live in ignored `data/multibench_sources/`. Pin these revisions:

| Source | Revision |
|---|---|
| `DocuPipe/DocuBench` GitHub | `43a3f3bc00e591e711075678ca6d154acfedcf42` |
| `udibarzi/varex-bench` GitHub | `3cce9c18530748cfc843f38c02e2f43e0694d167` |
| `ContextualAI/extract-bench` GitHub | `ca817638852a23bb17ca9aaeb82ccdd29e9af9ca` |
| `micro1-research/longextract-bench` GitHub | `b28888d7e864a84dfed810b00c899f308f0d24d0` |
| `ibm-research/VAREX` Hugging Face | `2dfc3386a4567c7d56bf1abf4d12ff42afed27b6` |
| `Extend-AI/LongArray-Extract` Hugging Face | `f2ae30264ecd942fa0a9b9e787bb42e1e2577184` |
| `micro1-inc/longextract-bench-50` Hugging Face | `d4ca332f72f6d3649ecd11b69445a8f4ef5fcb02` |

Use the project's configured Python/Poppler paths in `configs/local.env`, install `benchmarks/multibench/requirements.txt`, and start `bash benchmarks/multibench/serve_8b.sh` after checking spare GPU memory. Set `DQ_LLM_URL=http://localhost:8078/v1` and `DQ_MODEL_NAME=dq-multibench8b` for inference.

```bash
source configs/local.env
export DQ_LLM_URL=http://localhost:8078/v1 DQ_MODEL_NAME=dq-multibench8b
"$DQ_PYTHON" benchmarks/multibench/audit.py
"$DQ_PYTHON" benchmarks/multibench/varex.py prepare
"$DQ_PYTHON" benchmarks/multibench/varex.py run --scope full
"$DQ_PYTHON" benchmarks/multibench/varex.py combine --scope full
"$DQ_PYTHON" benchmarks/multibench/varex.py score --scope full
"$DQ_PYTHON" benchmarks/multibench/docubench.py run
"$DQ_PYTHON" benchmarks/multibench/docubench.py score
"$DQ_PYTHON" benchmarks/multibench/longarray.py prepare
"$DQ_PYTHON" benchmarks/multibench/longarray.py run --scope full
"$DQ_PYTHON" benchmarks/multibench/longarray.py score --scope full
```

For V2, pass `--profile bounded-v2 --out results/multibench/docubench_v2` to the DocuBench run and `--out results/multibench/docubench_v2` to scoring. LongArray likewise supports a distinct output directory; prepare its inputs there first. Do not mix predictions across policies or overwrite the running baseline.

**Validation:** 23 tests pass (8 evaluation/adapter regression tests plus 15 existing core tests). The new checks cover missing-prediction penalties, correct pilot eligibility, exact context reservation, page composition order, Hebrew text fidelity, full scalar page coverage, and rejection of incomplete one-shot output. Public peer re-scoring and full input/manifest coverage are independent integration checks.

The next steps are full DocuBench/VAREX scoring, a controlled V1/V2 comparison, full LongArray evaluation, and official Contextual content judging. Top-three potential is strongest on Contextual's demonstrated schema reliability and LongArray's page-wise extraction, but remains an inference until the full comparable results exist. DocuBench's third-place margin and VAREX's 96.6 cutoff are substantial targets for an 8B model; the pilot supplies no evidence that we already meet them.

DocILE requires page/box localization and line-item grouping plus gated annotated data; RealKIE uses span extraction; OmniDocBench measures parsing. They need separate output adapters and metrics. Datalab's OmniExtractBench substantially overlaps existing extraction datasets, so it can test robustness to revised annotations but cannot count as wholly independent evidence. None of these has an established DocQuorum rank here.

Higher ranks alone will not establish an A* paper or general superiority. A defensible claim needs a frozen cross-benchmark policy, complete cohorts, independent held-out evaluation, matched backbone baselines, repair/quorum ablations, row completeness, and measured cost/latency. This branch preserves those distinctions while testing whether the fixes transfer.
