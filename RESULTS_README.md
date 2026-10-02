# DocQuorum: additional benchmark experiments

<!-- completed-results:start -->
## Completed full-cohort results

These results cover every task in their stated cohort. Reference ranks compare published scores; no external leaderboard submission has been accepted. Stored-output and development results are labelled explicitly.

| Benchmark | Configuration / measurement | Tasks | Score (%) | Reference rank | Gap to leader (pp) |
|---|---|---:|---:|---|---:|
| run-llama ExtractBench | [Stored primary, current public annotations](results/multibench/extractbench_current_reference.json) | 370 | **95.4278** | 3 | 0.4822 |
| run-llama ExtractBench | [Archived incremental repair development](results/multibench/extractbench_archived_candidate.json) | 370 | **95.6430** | 3 | 0.2670 |
| UNIKIE constrained-category | [Original 3 readings; stored-output re-score](results/multibench/unikie_audit.json) | 4472 | **80.6450** | 2 | 1.7250 |
| UNIKIE constrained-category | [Development 4 readings; stored-output re-score](results/multibench/unikie_audit.json) | 4472 | **81.3175** | 2 | 1.0525 |
| UNIKIE constrained-category | [Tuned 6 readings; stored-output re-score](results/multibench/unikie_audit.json) | 4472 | **82.3746** | 1 (displayed tie) | 0.0000 |
| DocuBench v0.2.0 | [DocQuorum8B-bounded-v1](results/multibench/docubench/summary.json) | 72 | **63.8574** | 11 | 33.1596 |
| DocuBench v0.2.0 | [DocQuorum8B-bounded-v4](results/multibench/docubench_v4/summary.json) | 72 | **70.3995** | 10 | 26.6175 |
| DocuBench v0.2.0 | [DocQuorum8B-bounded-v6](results/multibench/docubench_v6/summary.json) | 72 | **74.7936** | 8 | 22.2234 |
| VAREX image_only | [8B official](results/multibench/varex/scores/full/summary.json) | 1777 | **96.9503** | 3 | 1.0497 |
| VAREX image_only | [8B whole](results/multibench/varex/scores/full/summary.json) | 1777 | **97.4530** | 2 | 0.5470 |
| VAREX image_only | [8B guided](results/multibench/varex/scores/full/summary.json) | 1777 | **97.6807** | 2 | 0.3193 |
| VAREX image_only | [8B quorum](results/multibench/varex/scores/full/summary.json) | 1777 | **96.9503** | 3 | 1.0497 |

Pilots, selected routing checks and incomplete runs remain below in the experiment notes. They receive no full-cohort rank. This table refreshes and is committed/pushed whenever a complete score changes.
<!-- completed-results:end -->

Branch: `experiment/multibench-20261002`, based on `fb69fc4eab65ec690c892e36e43f7a3c53936693`. Checked 2 October 2026. Work remains in progress. No result here has been submitted to an external leaderboard.

The strongest current evidence is the existing UNIKIE evaluation: the original three-reading configuration re-scores to **80.6450** across all 4,472 constrained-category documents, above the paper's third-place 79.12. The separately tuned six-reading configuration re-scores to **82.3746**, tying the displayed leader, 82.37. It must not replace the original held-out result. The added four-reading configuration scores 81.3175 and is also development work. [Primary paper, Table 4](https://arxiv.org/html/2602.07038v2); [full coverage audit](results/multibench/unikie_audit.json).

## Benchmarks and targets

Scores within each row use that benchmark's metric; percentages across rows are not interchangeable. Published commercial benchmark results are reference comparisons, rather than our own paired re-runs of those providers.

| Benchmark and scope | Metric | Published leader | Published third | DocQuorum evidence | Status |
|---|---|---:|---:|---|---|
| [run-llama ExtractBench](https://github.com/run-llama/ExtractBench), 370 documents | Mean document unified value F1 | 95.91, LlamaExtract Agentic Plus / Pulse Effort | 94.77, LlamaExtract Agentic | Stored primary: **95.4278** on current public annotations | Estimated reference rank 3; development result, no official submission |
| [UNIKIE](https://arxiv.org/html/2602.07038v2), 4,472 constrained-category documents | Macro scenario field F1 | 82.37, Gemini 3 Pro | 79.12, Qwen3-VL 8B | Original 80.6450; tuned 82.3746 | Full stored-output re-score; original result exceeds third |
| [DocuBench](https://github.com/DocuPipe/DocuBench), all 72 tasks / 10 formats, v0.2.0 | Macro document field accuracy | 97.0170, DocuPipe high | 91.7324, Claude Sonnet 5 | Full 8B V1: **63.8574**; V4 run underway | Reference rank 11; 27.8749 pp below third |
| [VAREX](https://udibarzi.github.io/varex-bench/), 1,777 forms, image-only track | Micro normalized field exact match | 98.0, Gemini 2.5 Pro | 96.6, Qwen3-VL 8B | 36-document pilot: 94.8081; full run underway | Pilot is ineligible for ranking |
| [LongArray-Extract](https://www.extend.ai/resources/long-array-extraction-benchmark), all 45 PDFs | Mean document accuracy; failed documents score zero | 99.2, Extend MAX | 83.1, Claude Opus 4.7 | V1 three-document pilot: **76.2477**; V4 pilot running | Pilot receives no full-cohort rank |
| [Contextual AI Extract Bench](https://arxiv.org/html/2602.12247v1), all 35 tasks | End-to-end field pass rate, official Gemini 2.5 Flash judge | 6.9, Gemini 3 Flash | 5.2, GPT-5.2 | 26/35 stored outputs are schema-valid; **content pass rate unknown** | Judge configuration and paper/scorer field-count reconciliation needed |
| [LongExtractBench](https://github.com/micro1-research/longextract-bench), public 50-document subset | Completed-document leaf accuracy, with row P/R and failures separately | No verified public-50 comparison | Unknown | All 50 source inputs prepared; official adapter implemented | Published 225-document outcomes cannot rank our public-50 run |

DocuBench's high and standard profiles and Claude were reproduced from every public output, rather than copied from rounded table entries: 97.0169874, 96.1401270 and 91.7323502. All ten available peer result folders cover 72 documents, including the Pulse folder not shown in the README's nine-entry table. [Machine-readable audit](results/multibench/docubench_public_audit.json).

ExtractBench is **0.4822 percentage points below its leaders**, and 0.6578 above the published third-place score. The local original-annotation re-score reproduces 95.2535; the current-annotation reference reproduces 95.4278. The latter reuses the previous archived evaluation after validating every one of the 370 original prediction hashes and verifying that both the public dataset and scorer revisions remain current. It is not new inference. The previously archived repair candidate scored 95.6430, with 14 gains and no regressions in an incremental development evaluation, but that candidate has not been run on these additional benchmarks. [Current reference provenance](results/multibench/extractbench_current_reference.json); [original-annotation re-score](results/multibench/extractbench_rescore/summary.json).

Contextual's stored `cx_scores.json` contains all-zero scores from an adapter with empty expected outputs; those are not valid benchmark scores. Older local judge logs used Qwen and include judge context failures, which also prevent comparison to the published Gemini-judged results. The schema audit validates against the original supplied schemas and confirms that all 35 schema/gold/PDF inputs match the pinned current official repository. After unwrapping the resume schema, validity is **74.29% (26/35)**, with 6/7 SEC filing outputs valid, but this does not establish an accuracy rank. [Corrected audit](results/multibench/contextual_schema_audit.json). The earlier audit incorrectly treated the resume schema wrapper as a schema and overcounted validity by six documents; the runnable auditor now unwraps it and rejects non-schema inputs.

An offline deterministic diagnostic earns **63 passed evaluations** when every semantic/array judge evaluation is forced to zero and all schema-invalid outputs earn zero. The public scorer visits **691 positions**, whereas the paper denominator is **3,086**: its array metric stops traversal, while the paper counts additional schema fields. This is an evaluation protocol discrepancy to resolve before reporting a comparable content score, even with the matching judge available. These diagnostic counts do not receive a rank. [Diagnostic and per-document reconciliation](results/multibench/contextual_deterministic_diagnostic.json).

## Configurations being measured

The original frozen configuration uses Qwen3.8-27B and MinerU. The model and parser endpoints are down; the shared H100 has about 21 GB of spare memory. The new runs therefore use an explicitly separate **Qwen3-VL-8B-Instruct-FP8** variant, revision `9cdc6310a8cb770ce18efaf4e9935334512aee45`, with a 32,768-token context and 8,192-token output ceiling. Its server uses 0.18 of GPU memory and does not stop the existing GPU process. These scores will not be labelled as fresh measurements of the frozen 27B pipeline.

VAREX's `official` reading uses the publisher's extraction prompt and original image; `whole` uses DocQuorum's whole-page prompt; `guided` uses that prompt with schema decoding. The quorum follows the existing recall-weighted agreement rule, beta 2, with the fixed order official → whole → guided. No supplied OCR/layout text is used in the image-only track. The fixed pilot takes 12 documents per official split in SHA256 order, selected without labels. On its 443 scoreable fields: official 94.8081, whole 94.1309, guided 94.1309, quorum 94.8081. There is **no measured quorum gain in this pilot**. The full scheduler now finishes the official reading across all documents before completing the other two readings; completed predictions, prompts, model and sampling remain unchanged. The full-run policy was started before evaluating the pilot. [Pilot results](results/multibench/varex/scores/pilot/summary.json).

DocuBench and LongArray use the existing reader and checks under `DocQuorum8B-bounded-v1`: exact server tokenization reserves output space before requests; full source text is never clipped by the budget guard; multiple images supplied through that client are composed in page order with a disclosed five-million-pixel cap. DocuBench additionally reads XLSX, DOCX, TXT, XML, HTML and CSV directly, preserving Unicode, cells and source order; multi-frame TIFF is converted with all frames. Its published per-document guidelines are included. All 72 tasks count in the score, and unavailable/failed outputs score zero.

The running baseline exposed two source-derived problems. The scalar reader can exceed the smaller context and silently produce `{}`; it also only reads the first two pages for scan scalars. The external one-shot provider builds its own client, bypassing our guard, and its context-fitting fallback can drop pages or prune schema fields. These are diagnosed from input/request behavior, rather than gold errors.

`DocQuorum8B-bounded-v2` is a separate candidate: scalar schema/page partitions visit the complete source; the external one-shot call uses the guarded client directly, without its dropping/pruning fallback; truncated one-shot outputs are rejected. V2's score and gain are **not measured yet**.

`DocQuorum8B-bounded-v3` adds record-preserving fixes: disjoint page windows accumulate array rows, including repeated rows; every schema/window partition must finish before the pipeline accepts it; dense tables keep complete rows rather than splitting columns away from their identifiers; oversized or truncated text blocks are recursively partitioned; failed list calls propagate instead of being accepted as empty arrays. Complete refinements replace truncated replies regardless of which has more rows. Source-derived tests pass, but there is **no measured V3 accuracy gain yet**. `DocQuorum8B-bounded-v4` additionally restores images to short native PDFs, routes mixed native/scanned PDFs through complete page images, and makes scan chunks one physical page each. V1 could treat a scanned data page as absent because an instructions page had native text; its two-page scan chunks also discarded the second image under the one-image server limit. Native-text record chunks can still span two pages. A source-only audit finds 3 mixed PDFs and 21 scan/sparse-text PDFs among the 58 PDF tasks; the fallback scan-chunk rule could omit 147 physical pages. This is a route-specific potential-loss count, not a claim that every affected document took that route. [Source modality audit](results/multibench/docubench_modality_audit.json).

The two error-selected routing checks improve from **0 → 80.9524** and **12.5 → 86.6667**; they are development checks and receive no rank. The V4 policy was frozen before measuring them, and its complete 72-task run is now underway, with separate predictions. V1's complete 72-task score is **63.8574**, reference rank 11 among the ten published peers plus this variant. It is **27.8749 percentage points below third** and **33.1596 below the leader**. One XML task failed because its complete native source needed 78,302 prompt tokens; it contributes zero rather than being dropped. A return marked completed does not imply accurate extraction: the remaining 71 documents also contain field errors. [Routing checks](results/multibench/docubench_v4/routing_check.json). All candidates are confined to experiment runner processes; the frozen pipeline source is unchanged.

`DocQuorum8B-bounded-v5` is a separate recovery experiment, frozen after V4 reported image-output truncation on two scanned tasks. It retries smaller horizontal bands with disjoint ownership: a red margin marks the body, while repeated headers and neighbouring pixels provide context; only records whose first line lies in the owned body should be emitted. Printed duplicates are retained. This instruction needs measured visual recall and boundary-error checks; code coverage alone cannot establish completeness. Oversized native XML is partitioned at complete element boundaries with ancestor tags preserved, and every partition must finish. A source-only audit preserves all 6,083 XML leaf occurrences in order over 13 partitions; oversized individual leaves fail explicitly. The selected XML task improves from failed/zero to **23.9726**, using 13 completed calls, 92,806 prompt tokens and 3,288 output tokens. This is a development-selected task, not a cohort score or rank; unrelated-order values still reduce accuracy. [Native source audit](results/multibench/docubench_v5/native_source_audit.json).

`DocQuorum8B-bounded-v6` addresses that native query-scope error: a field explicitly referring to a record identifier is scheduled only in source windows containing that identifier, with every root field required to have a window assignment. Unbound fields still visit every window. Identifiers must occur in the full original source and use an explicit query phrase; examples and format hints do not create bindings. This guards absence, not correctness within a window. Eleven of the XML task's fifteen fields receive bindings. On the selected XML task, V6 scores **100.0000**, versus V5's 23.9726 and V1's failure/zero. All 15 fields have source-window assignments, all 13 calls finish, and output tokens fall from 3,288 to 871. Shared-GPU wall time rises from 475.6 to 818.9 seconds, so this run does not establish a latency gain. It is a development-selected case, not a cohort rank. [Query-scope check](results/multibench/docubench_v6/native_query_check.json). V6 uses the same visual recovery as V5; the selected scan checks remain underway. A complete 72-task V6 run is queued after those checks and the full V4 comparison, retaining the same policy and all task failures in the denominator.

The first selected scan recovery, the 10-page `9hPCh7ca`, now completes at **42.8142**, versus V1 **25.8371** and V4 failure (**0**). This is a development check selected after runtime truncation, and its remaining field errors are substantial. The second selected scan is still running. [Measured image recovery](results/multibench/docubench_v6/image_recovery_progress.json).

A paired development diagnostic on V4's first 27 attempted tasks improves from **68.1680 to 79.0588** on those same documents: 9 gains, 5 regressions and 13 unchanged; two candidate tasks fail on image truncation. Completion order is not a random sample, and these values do not receive a full-cohort rank. [Paired progress snapshot](results/multibench/docubench_v4/paired_progress.json).

LongArray inference sees only the original PDF and supplied vertical schema. Its ground truth, `target_count`, target field metadata and generated page maps are excluded. Scoring loads the publisher's reference implementation verbatim from the pinned dataset card. It reports predicted and expected array lengths because that metric alone does not penalize surplus rows. A complete result must count all 45 documents, with failures contributing zero. The original three-document pilot completes all tasks at **76.2477**: clinical 61.5354 (356 predicted rows / 198 expected), financial 79.4150 (917 / 923), and legal 87.7927 (319 / 319). It receives no comparison rank against the full 45-document references. The V4 pilot now runs before the full V4 cohort. [Pilot score](results/multibench/longarray/scores/pilot/summary.json). The reference collector includes all 11 published systems, so lower scores cannot obtain inflated ranks by omitting intermediate peers. [Published reference rows](results/multibench/longarray_public_reference.json).

V4 does not yet solve LongArray’s clinical extraction: its completed pilot task scores **59.4545**, versus V1 **61.5354**, with **363 / 198** rows. The output still includes zero-event subject blocks that the schema excludes. Inspection of the original source also shows global code legends, demographic context and supportive listings that repeat primary events; these require explicit scope and context handling. The other two V4 pilot tasks remain in progress, so there is no complete V4 pilot score yet. [Clinical task comparison](results/multibench/longarray_v4/clinical_progress.json).

A larger-backbone follow-up is being prepared using [the pinned 27B INT4 checkpoint](https://huggingface.co/ulkaa/Qwen3.8-27B-AWQ-INT4/tree/2bf7f1646dc0875cff4404fdfef976cfb0ff2199). Its safetensors total 18.2054 GiB, with MTP tensors preserved on disk; the installed vLLM regular loader skips `mtp.` tensors. The pinned weights are now cached; the inspected tensor headers total 18.2051 GiB, or an estimated 17.4140 GiB after excluding unused MTP tensors. The 8B runs continue. GPU fit, speed and extraction accuracy remain unmeasured, and its scores will use a separate backbone label. [Candidate metadata](results/multibench/larger_backbone_candidates.json); [completed download and tensor inventory](results/multibench/backbone_27b_int4_ready.json).

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
"$DQ_PYTHON" benchmarks/multibench/contextual.py audit
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

For the complete V4 comparison, use `docubench.py run --profile bounded-v4 --out results/multibench/docubench_v4`, followed by `docubench.py score --out results/multibench/docubench_v4`. `--only ID ...` can resume selected tasks while preserving the full 72-task scoring denominator. LongArray V4 inputs are also prepared; use its separate output directory and the same profile.

V5 accepts the same distinct-output convention, for example `docubench.py run --profile bounded-v5 --out results/multibench/docubench_v5`. Keep its predictions separate from V4. LongArray and LongExtract also accept V5 for later transfer measurements.

For V3, use `--profile bounded-v3 --out results/multibench/docubench_v3` or `--profile bounded-v3 --out results/multibench/longarray_v3`. V3 LongArray inputs and all 50 public LongExtract inputs are prepared. LongExtract also accepts `--profile bounded-v4 --out results/multibench/longextract_v4`; prepare into that directory, run the full cohort with those same flags, then score with `--out results/multibench/longextract_v4 --scope full`. The supplied profile is recorded from the actual run policy, and complete publication requires all 50 attempts. Its official leaf accuracy averages only successful documents; row P/R, failures and latency are reported separately, and it never receives a rank against the private 225-document evaluation.

For V2, pass `--profile bounded-v2 --out results/multibench/docubench_v2` to the DocuBench run and `--out results/multibench/docubench_v2` to scoring. LongArray likewise supports a distinct output directory; prepare its inputs there first. Do not mix predictions across policies or overwrite the running baseline.

**Validation:** 47 tests pass (32 evaluation/adapter regression tests plus 15 existing core tests). The new checks cover missing-prediction penalties, pilot/tie eligibility, exact context reservation, page composition order, Hebrew text fidelity, wrapped schemas, full scalar coverage, incomplete one-shot/partition rejection, preservation of repeated records and identifier/value association, failed-call propagation, and LongExtract's separate recall/failure accounting. Public peer re-scoring and full input/manifest coverage are independent integration checks.

The next steps are the full DocuBench V4/V6 comparisons against the completed V1 baseline, full VAREX and LongArray evaluation, the public-50 LongExtract evaluation, and official Contextual content judging. Contextual's six valid SEC outputs and LongArray's page-wise extraction are useful leads, but top-three potential remains unmeasured. DocuBench's third-place margin and VAREX's 96.6 cutoff are substantial targets for an 8B model; the pilot supplies no evidence that we already meet them.

Contextual diagnostics use a separate environment because both benchmarks publish a Python package named `extract_bench`. Create it with `"$DQ_PYTHON" -m venv --system-site-packages data/multibench_sources/contextual_eval_env`, install `litellm==1.82.3 loguru==0.7.3` there, then run `contextual_eval_env/bin/python benchmarks/multibench/contextual.py diagnostic` using the full environment path. This diagnostic makes no model calls.

Run `"$DQ_PYTHON" benchmarks/multibench/leaderboard.py` after scoring to refresh [the accumulated result table](results/multibench/leaderboard.json). It assigns no rank to pilots, and uses published rounding precision to avoid claiming a win over a rounded tie.

DocILE requires page/box localization and line-item grouping plus gated annotated data; RealKIE uses span extraction; OmniDocBench measures parsing. They need separate output adapters and metrics. Datalab's OmniExtractBench substantially overlaps existing extraction datasets, so it can test robustness to revised annotations but cannot count as wholly independent evidence. None of these has an established DocQuorum rank here.

Higher ranks alone will not establish an A* paper or general superiority. A defensible claim needs a frozen cross-benchmark policy, complete cohorts, independent held-out evaluation, matched backbone baselines, repair/quorum ablations, row completeness, and measured cost/latency. This branch preserves those distinctions while testing whether the fixes transfer.

## Publishing completed benchmarks

`benchmarks/multibench/publish_completed.py --watch` checks scored results every 30 seconds. When a full cohort finishes, it refreshes the completed-results table and commits/pushes its summary and manifests to this experiment branch. UNIKIE and both the stored-primary and archived development ExtractBench results remain in the accumulated table. Pilots and incomplete cohorts are excluded. Raw inputs/predictions are not staged. A branch guard refuses publication to `main`.
