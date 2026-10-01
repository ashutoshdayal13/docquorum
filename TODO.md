# TODO

## More key-information-extraction (KIE) benchmarks to compare on (search done 2026-10-01; runs to do later)

Goal: benchmarks where DocQuorum can be compared with other published systems **in the same regime** (zero-shot:
no training on the benchmark), with the benchmark's own scorer. Nothing is run yet.

### Candidates, in the order proposed

| # | benchmark | documents | task format | scorer | published systems to compare with | data / license | fit |
|---|---|---|---|---|---|---|---|
| 1 | **UNIKIE-BENCH, open-category track** ([arXiv 2602.07038](https://arxiv.org/abs/2602.07038), ACL 2026) | receipts, forms, invoices, contracts (open field set) | JSON template per image, fields not fixed in advance | the benchmark's own `kie_evaluator` (already replicated here) | the paper's 16 systems (Gemini-3-Pro best), plus SAYRE ([arXiv 2607.04636](https://arxiv.org/abs/2607.04636)), which reports this track: Gemini-3-Pro 82.01 average over constrained + open | Google Drive link in the benchmark's README; not downloaded yet | **best**: same protocol, scorer and baselines as our 82.37 run; only the data is missing |
| 2 | **VAREX** ([arXiv 2603.15118](https://arxiv.org/abs/2603.15118)) | 1,777 US government forms (flat 299, nested 1,146, tables 332); 21,084 fields | a **JSON Schema per document** (1,771 unique; nested objects and arrays, `$defs`) | exact match (primary), ANLS; order-invariant array matching (Hungarian) | 20 models, all zero-shot, 4 input modalities (text, layout text, image at 200 dpi, text+image): Gemini 2.5 Pro 98.0% EM, GPT-4o 94.8%, small open models down to 9.7% | dataset and evaluation code public, CC BY 4.0 (Hugging Face, GitHub) | **very good**: our native input (schema per document), zero-shot baselines. Top scores are near the ceiling, so the headroom is small |
| 3 | **CC-OCR, KIE track** ([arXiv 2412.02210](https://arxiv.org/abs/2412.02210), ICCV 2025) | several KIE subsets (receipts, forms, certificates; English and Chinese) | JSON output per image | the benchmark's own KIE F1 | general LMMs zero-shot (Qwen2-VL-72B, Qwen-VL-Max, Gemini-1.5-Pro, ...); later reports, e.g. Qianfan-OCR 92.8 | Hugging Face `wulipc/CC-OCR`; license to confirm | good: zero-shot LMM regime; half Chinese |
| 4 | **ReceiptBench** ([arXiv 2605.22413](https://arxiv.org/abs/2605.22413)) | 10,656 real receipts, 98% English (+ 8 languages) | 19 fields in 4 sub-tasks (perception, normalisation, semantic reasoning, nested line items); one JSON per receipt | F1 with a hybrid protocol: exact, numeric, **LLM judge** for semantic fields, Hungarian for lists | zero-shot: Gemini-3-Pro 0.737, GPT-5 0.708, InternVL3.5-241B 0.674. Its open models are fine-tuned (0.795), a different regime | code and data on GitHub (wwwT0ri/ReceiptBench); license to confirm | good: large, recent, same frontier baselines as UNIKIE. The LLM judge needs a local judge model (no documents to external APIs) |
| 5 | **IDP Leaderboard, KIE task** (Nanonets; [idp-leaderboard.org](https://www.idp-leaderboard.org), [github.com/NanoNets/idp-leaderboard-benchmarks](https://github.com/NanoNets/idp-leaderboard-benchmarks)) | Nanonets KIE, DocILE, handwritten forms (part of IDP Core, 6,406 samples over 4 tasks) | fields per document | edit-distance accuracy; evaluation code MIT (`docext`) | a live leaderboard of many VLMs (Gemini 3.1 Pro leads IDP Core at 89.6 overall) | public pipeline; confirm the KIE data's terms | good: an active leaderboard. DocILE overlaps UNIKIE's Commercial source |
| 6 | **OCRBench v2, KIE subsets** ([arXiv 2501.00321](https://arxiv.org/abs/2501.00321), NeurIPS 2025 D&B) | 400 English + 400 Chinese KIE samples from FUNSD, SROIE, POIE, M6Doc, XFUND, SVRD and private receipts | key -> value extraction from a prompt | F1 | a maintained leaderboard of LMMs (Qianfan-OCR 82.8 en / 82.3 cn) | public; license to confirm | medium: small and partly Chinese; SROIE overlaps UNIKIE |
| 7 | **VRDU** ([arXiv 2211.15421](https://arxiv.org/abs/2211.15421), KDD 2023) | FARA registration forms (6 entity types), FCC political ad-buy forms (14 types incl. nested line items) | entities; three settings: single, mixed, unseen template | micro-F1 with the official type-aware matching toolkit | mostly **trained** models (LayoutLM family, LMDX with PaLM 2 / Gemini Pro), few-shot from 10 training documents | GitHub (google-research-datasets); license to confirm | medium: a regime mismatch; only the unseen-template setting is close to zero-shot |
| 8 | Classic KIE sets: SROIE, CORD, FUNSD, XFUND (7 languages), POIE | receipts, forms, multilingual forms | fixed label sets | their own F1 | mostly fine-tuned (LayoutLMv3, Donut, ...); zero-shot LLM numbers scattered across papers (e.g. [arXiv 2609.17538](https://arxiv.org/abs/2609.17538): 2-8B open LLMs, text input) | public | low: fine-tuned regime; SROIE is already in UNIKIE |
| 9 | ExStrucTiny ([arXiv 2602.12203](https://arxiv.org/abs/2602.12203)), K2Q ([arXiv 2410.15484](https://arxiv.org/abs/2410.15484)) (both JPMorgan) | 110 multi-page documents / 304 queries; five KIE sets rewritten as prompts | schema, plain-text and open queries; ANLS, page and box grounding | Gemini 2.5 Pro 79.5 ANLS vs Qwen2.5-VL-72B 61.4 (few-shot) | **data on request, research only** | low: access and size |
| 10 | Structured Output Benchmark ([arXiv 2604.25359](https://arxiv.org/abs/2604.25359)); a medical-document IE benchmark ([medRxiv 2026.01.19](https://www.medrxiv.org/content/10.64898/2026.01.19.26344287v1.full)) | text, images and audio; 1,000 mock medical documents | JSON output | their own | 21 models (images: Gemma-4-31B best); GPT-4.1-mini 55.6 F1 on medical | to check | low: only partly document KIE |

Not KIE, so left out: DocVQA-style question answering (DocVQA, DUDE, InfographicVQA) and page-parsing benchmarks (OmniDocBench, olmOCR-Bench).

### Proposed order of runs
1. UNIKIE-BENCH open-category: download the data only; the protocol, scorer and baselines are already in `benchmarks/unikie/`.
2. VAREX: an adapter from its records to `docquorum.extract` (schema in, JSON out) and its scorer; run on the image modality, the one comparable to the page-image setting of the published models.
3. CC-OCR KIE and ReceiptBench: zero-shot LMM comparisons with the same frontier models as UNIKIE. ReceiptBench needs a local judge model.
4. Optional: the IDP Leaderboard KIE task, and VRDU's unseen-template setting.

### Before each run
* record the license and terms, and whether data or outputs may be published;
* freeze the configuration before opening the benchmark's data, and report that run as held out;
* replicate the benchmark's own protocol (its prompt for the baseline, image size, post-processing, scorer);
* no labels in any method step, and no rules fitted to one benchmark's answer conventions;
* estimate a full run's GPU time on one GPU.
