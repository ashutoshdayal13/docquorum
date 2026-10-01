# DocQuorum

**Agentic document extraction by a quorum of grounded readings.**

Give DocQuorum a document (PDF or image) and a JSON Schema (or a JSON template); it returns
JSON that follows the schema. It runs on open-weight models on a single GPU.

| benchmark | result | standing |
|---|---|---|
| ExtractBench (370 enterprise PDFs, 1-163 pages) | Overall **95.25** (short 96.11, medium 94.03, long 90.41) | 3rd of 45 leaderboard rows (behind two commercial systems at 95.91) |
| UNIKIE-BENCH (4,472 images, 11 scenarios) | **80.64** frozen, held-out / **82.37** tuned | 2nd of 16 / ties 1st (Gemini-3-Pro 82.37) |
| Contextual AI ExtractBench (35 PDFs, 2,076 pages, schemas of 12-369 fields) | pass rate **5.8%** frozen, held-out (26/35 valid) / **10.8%** with post-hoc fixes (35/35 valid); gold itself reaches 22.4% | 2nd of 7 / 1st of 7 (Gemini 3 Flash 6.9%) |

Details, caveats and per-document scores: [`results/README.md`](results/README.md).
How it works, with a diagram: [`docs/docquorum.pdf`](docs/docquorum.pdf).

---

## How it works (short version)

```
document ─► front end ─► readings ──────────────► repairs & page checks ─► consensus ─► JSON
            text layer    primary (agentic)        carry-down, dedupe,      scans: keep the
            MinerU parse  parse   (agentic, scans) page numbers, record     reading the others
            page images   one-shot (scans, 1 call) counts, figures ...      agree with most
```

1. **Front end** — the PDF's text layer, with page images at 220 dpi; for scans and images the
   MinerU2.5 parse. Text under a scan (an OCR layer, or the parse) is labelled as machine-read,
   and the page image decides where the two disagree.
2. **Agentic reading** — a planner picks one whole-document call when the document and its
   answer fit the budget; splits the *schema* into parts when the schema is what does not
   fit; otherwise reads page chunks, checks each call's `finish_reason`, splits truncated
   chunks and re-asks pages that came back empty. A reply that leaves schema keys out is read
   again with every key required. Layout readers (column flow, ruled scanned tables) take over
   where the page's own geometry calls for them.
3. **Repairs and page checks** — every answer is checked against the document itself, not by
   asking the model: values carried down to continuation rows, keyed duplicates removed,
   template rows dropped, rows copied between arrays removed, repeated records capped at the
   count the page prints, printed page numbers located by content, quotes and figures rendered
   as printed, every schema field present (an empty list as the schema's declared default), blank check boxes false and blank
   pre-printed lines dropped where the schema says so.
4. **Consensus** — a PDF with a text layer is read once. A scan or image that fits one call is
   read three ways (page images, parse, one-shot) and the quorum keeps the reading that agrees
   most with the others (recall-weighted, beta = 2). Measured: it helps when the readings are
   of comparable quality (single images), not when one reading is grounded in exact
   characters (PDF text layers).

---

## Install

```bash
# 1. Python environment (3.10+)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install llama-extract-bench        # ExtractBench: scorer + reference one-shot reader (Apache-2.0; github.com/run-llama/ExtractBench)

# 2. Poppler (pdftotext, pdftoppm, pdfinfo)
sudo apt-get install poppler-utils        # or: conda install -c conda-forge poppler

# 3. vLLM (separate environment recommended) for serving the models
pip install vllm==0.27.1
```

On this machine everything is already installed; just run `source configs/local.env`.

## Serve the models

```bash
serve/serve_qwen38_27b.sh      # main extraction model  -> http://localhost:8079/v1
serve/serve_mineru.sh          # MinerU2.5 parser (optional; scans, images, parse reading) -> :8081
# optional extra readers for the tuned UNIKIE configuration
serve/serve_qwen3vl_32b.sh     # Qwen3-VL-32B-Instruct-FP8
serve/serve_qwen3vl_8b.sh      # Qwen3-VL-8B-Instruct
```

The 27B model at `GPU_UTIL=0.74 MAX_LEN=131072 MAX_SEQS=48` and the parser at 0.13 fit
together on one 94 GB H100. Endpoints and paths are set in `docquorum/config.py` and can be
overridden with environment variables (`DQ_LLM_URL`, `DQ_MODEL_NAME`, `DQ_PARSER_URL`,
`DQ_POPPLER_BIN`, `DQ_PARSE_CACHE`, `DQ_RUNS`, `DQ_EXTRACTBENCH_DATA`, `DQ_UNIKIE_DIR`). Every
other setting of the measured configuration (page images at 220 dpi / 5 MP, reasoning off,
structured decoding, quorum beta = 2, ...) is a constant in the module that uses it.

## Use

Command line:

```bash
python -m docquorum.extract invoice.pdf --schema invoice_schema.json -o invoice.json
python -m docquorum.extract receipt.jpg --schema receipt_template.json      # template in, template out
python -m docquorum.extract report.pdf --schema s.json --task "Extract every holding in the schedule of investments."
```

Python:

```python
from docquorum.extract import extract
result, report = extract("invoice.pdf", schema_dict, task=None)
print(report)   # readings produced, the one the consensus kept, agreement scores
```

A JSON template is a JSON object whose values are empty (`""`, `[{...}]`, `{...}`); the result
then follows the template, with `""` for anything the document does not contain.

## Reproduce the benchmark results

```bash
source configs/local.env        # or your own paths

# exact: re-score the stored final outputs
for s in short medium long; do python benchmarks/extractbench/score_run.py --split $s \
    --run results/extractbench/predictions/$s --json /tmp/$s.json; done
python benchmarks/extractbench/overall.py /tmp/short.json /tmp/medium.json /tmp/long.json
python benchmarks/extractbench/robustness.py /tmp/short.json /tmp/medium.json /tmp/long.json
benchmarks/unikie/run.sh score                  # frozen and tuned, from the stored readings

# fresh: run the pipeline end to end (model calls; results within noise of the stored ones)
benchmarks/extractbench/run.sh short            # medium, long
benchmarks/unikie/run.sh read                   # then: run.sh score
benchmarks/contextual/run.sh                    # Contextual AI ExtractBench (held out); see results/README.md
```

ExtractBench data: `data/extractbench/` (`short.jsonl`, `medium.jsonl`, `long.jsonl`, `docs/`),
as distributed by the benchmark. UNIKIE-BENCH: `data/unikie-bench/` (its repository, with
`datasets/`).

## Layout

```
docquorum/            the pipeline (file by file: docs/CODE_GUIDE.md)
  extract.py            the whole pipeline on one document (CLI + Python API)
  config.py             endpoints and paths
  extractbench.py       benchmark records and the benchmark's scorer
  quorum.py             the reading the others agree with most
  tools/                what the agents act with, no decisions:
    pdf.py parser.py llm.py schema.py rows.py layout.py
  agents/               the readers
    reader.py whole.py    the reader agent (plan / act / observe) and its one-call actions
    oneshot.py            ExtractBench's one-shot reader
    layout.py             the layout agent, choosing:
    column_reader.py ruled_reader.py
    prompts.py            every prompt
  checks/               deterministic repairs and checks, one file each, and their chains
benchmarks/           ExtractBench, UNIKIE-BENCH and Contextual AI ExtractBench runners and scorers
serve/                model-serving scripts (+ gpu_hold.py, for shared GPUs)
configs/local.env     paths for this machine
results/              scores, final outputs, research log; archive/ holds the code before the
                      2026-09-29 reorganisation
docs/                 docquorum.tex / docquorum.pdf (the pipeline explained), CODE_GUIDE.md,
                      examples/ (six documents, output after every stage)
ref_papers/           the ExtractBench and UNIKIE-BENCH papers
tests/                unit tests of the checks, the quorum weighting and the schema helpers
```

## Notes

* Lessons that shaped the design are recorded in `results/RESEARCH_LOG.md`, including
  negative results (asking the model to verify its own output did not help in 22 attempts;
  prompt rules fixed one scenario and broke others) and one correction (an earlier consensus
  measured agreement with the benchmark's annotated record and so used gold; all numbers above
  are clean).
* `serve/gpu_hold.py` keeps GPU memory reserved on a shared machine; release it before
  starting a server, and never use it on memory other people need.
