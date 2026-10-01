# DocQuorum

**Agentic document extraction by a quorum of grounded readings.**

Give DocQuorum a document (PDF or image) and a JSON Schema (or a JSON template); it returns JSON that
follows the schema. It runs on open-weight models (Qwen3.8-27B) on a single GPU; no commercial API is used.

| benchmark | result | standing |
|---|---|---|
| ExtractBench (370 enterprise PDFs, 1-163 pages) | Overall **95.25** (short 96.11, medium 94.03, long 90.41) | 3rd of 45 leaderboard rows (behind two commercial systems at 95.91) |
| UNIKIE-BENCH (4,472 images, 11 scenarios) | **80.64** frozen, held-out / **82.37** tuned | 2nd of 16 / ties 1st (Gemini-3-Pro 82.37) |
| Contextual AI ExtractBench (35 PDFs, 2,076 pages, schemas of 12-369 fields) | pass rate **5.8%** frozen, held-out (26/35 valid) / **10.8%** with post-hoc fixes (35/35 valid); gold itself reaches 22.4% | 2nd of 7 / 1st of 7 (Gemini 3 Flash 6.9%) |

* Details, caveats, per-document scores: [`results/README.md`](results/README.md)
* How it works, with a diagram and worked examples: [`docs/docquorum.pdf`](docs/docquorum.pdf), [`docs/examples/`](docs/examples/)
* The code, file by file: [`docs/CODE_GUIDE.md`](docs/CODE_GUIDE.md)

---

## Which part of this README do I need?

| I want to ... | needs a GPU? | read |
|---|---|---|
| **check the reported numbers** (re-score the stored outputs) | no | [1. Quick start](#1-quick-start-check-the-reported-numbers-no-gpu-about-10-minutes) |
| **extract from my own document** | yes | [2. Install](#2-install), [3. Serve the models](#3-serve-the-models), [4. Extract from one document](#4-extract-from-one-document) |
| **re-run a benchmark end to end** | yes | [2](#2-install), [3](#3-serve-the-models), [5. Run the benchmarks](#5-run-the-benchmarks) |
| **understand the code** | no | [`docs/CODE_GUIDE.md`](docs/CODE_GUIDE.md) |

---

## 1. Quick start: check the reported numbers (no GPU, about 10 minutes)

This re-scores the final outputs stored in this repository with the benchmark's own scorer. No model is called.

**Step 1. Get a Python 3.12+ environment with the dependencies.**
```bash
git clone git@github.com:ashutoshdayal13/docquorum.git && cd docquorum
python3.12 -m venv .venv && source .venv/bin/activate      # any Python >= 3.12 works
pip install -r requirements.txt
pip install llama-extract-bench          # ExtractBench's scorer and reference one-shot reader (Apache-2.0)
```

**Step 2. Get the ExtractBench data.** Download the dataset from
[huggingface.co/datasets/llamaindex/ExtractBench](https://huggingface.co/datasets/llamaindex/ExtractBench)
and place it as:
```
data/extractbench/short.jsonl
data/extractbench/medium.jsonl
data/extractbench/long.jsonl
data/extractbench/docs/<split>/<document>.pdf        (not needed for scoring; needed from section 4 on)
```
For scoring, the three `.jsonl` files are enough. To keep the data elsewhere, set `DQ_EXTRACTBENCH_DATA` to that folder.

**Step 3. Score.**
```bash
for s in short medium long; do
  python benchmarks/extractbench/score_run.py --split $s \
      --run results/extractbench/predictions/$s --json /tmp/$s.json | tail -n 1
done
python benchmarks/extractbench/overall.py /tmp/short.json /tmp/medium.json /tmp/long.json
python benchmarks/extractbench/robustness.py /tmp/short.json /tmp/medium.json /tmp/long.json
```
**Expected output:** the three `MEAN` lines read `96.11`, `94.03` and `90.41` (first number on each line), and
`overall.py` prints `ours: Overall 95.25 | Short 96.11 | Medium 94.03 | Long 90.41`, then the ranking against the
44 leaderboard rows (DocQuorum is 3rd).

**UNIKIE-BENCH (optional).** Clone [github.com/NEUIR/UNIKIE-BENCH](https://github.com/NEUIR/UNIKIE-BENCH), download its
images as its `DATA.md` describes, and point `DQ_UNIKIE_DIR` at the clone (default: `data/unikie-bench`). Then:
```bash
benchmarks/unikie/run.sh score     # frozen and tuned, test and full split, from results/unikie/readings
```
**Expected output:** four lines; the `full` ones read `frozen full macro 80.64` and `tuned  full macro 82.37`
(the `test` lines: 80.01 and 81.89).

---

## 2. Install

| what | version / note |
|---|---|
| Python | 3.12 or newer (the ExtractBench scorer needs it; the pipeline itself runs on 3.10+) |
| Python packages | `pip install -r requirements.txt` and `pip install llama-extract-bench` |
| Poppler | `pdftotext`, `pdftoppm`, `pdfinfo`, `pdffonts`, `pdfimages`: `sudo apt-get install poppler-utils`, or `conda install -c conda-forge poppler` |
| GPU (only to run the models) | one 80-96 GB GPU (developed on one 94 GB H100). The 27B model takes 74% of it, the parser (MinerU2.5) another 13% |
| vLLM (only to run the models) | `vllm==0.27.1`, in its own environment (recommended) |

Then **configure**: copy [`configs/example.env`](configs/example.env) to `configs/local.env`, edit it, and load it in every shell:
```bash
cp configs/example.env configs/local.env       # edit the paths
source configs/local.env
```
These are the only environment variables; every other setting of the measured configuration is a constant in the code.

| variable | default | meaning |
|---|---|---|
| `DQ_LLM_URL` | `http://localhost:8079/v1` | the extraction model's OpenAI-compatible endpoint |
| `DQ_MODEL_NAME` | `qwen3vl` | the name that server was started with |
| `DQ_PARSER_URL` | `http://localhost:8081/v1` | the MinerU2.5 parser (only for scans and images) |
| `DQ_POPPLER_BIN` | (on `PATH`) | folder with the Poppler tools |
| `DQ_EXTRACTBENCH_DATA` | `data/extractbench` | the benchmark's `.jsonl` files and `docs/` |
| `DQ_PARSE_CACHE` | `cache/parse` | parsed pages are cached here as `<document>/NNNN.txt` |
| `DQ_RUNS` | `runs` | where the runners write their outputs |
| `DQ_UNIKIE_DIR` | `data/unikie-bench` | the UNIKIE-BENCH repository |
| `DQ_UNIKIE_READINGS` | `results/unikie/readings` | where UNIKIE readings are read and written |
| `DQ_PYTHON` | `python` | the interpreter the `benchmarks/*/run.sh` scripts use |
| `VLLM_ENV`, `HF_HOME` | `vllm` on `PATH`, `~/.cache/huggingface` | used by `serve/*.sh` only |

---

## 3. Serve the models

Start each server in its own terminal (or in the background) and wait until it reports that it is ready; the first start
downloads the model and compiles, which takes several minutes.

```bash
source configs/local.env
serve/serve_qwen38_27b.sh      # extraction model Qwen3.8-27B-FP8  -> http://localhost:8079/v1
serve/serve_mineru.sh          # MinerU2.5 parser, needed only for scans and images -> http://localhost:8081/v1
```
Check that they answer: `curl http://localhost:8079/v1/models` and `curl http://localhost:8081/v1/models`.

* The 27B server runs at `GPU_UTIL=0.74 MAX_LEN=131072 MAX_SEQS=48`; the parser at 0.13. Together they fit one 94 GB GPU.
  Do not lower `MAX_LEN` or the image limit: the planner assumes a 131k-token context and up to 12 page images per call.
* Only the tuned UNIKIE configuration needs the extra readers `serve/serve_qwen3vl_32b.sh` (port 8079, in place of the 27B)
  and `serve/serve_qwen3vl_8b.sh` (port 8078).
* `serve/gpu_hold.py` was used on a shared GPU machine to keep memory reserved; you do not need it.

---

## 4. Extract from one document

**Command line.** The document may be a PDF or an image; the schema a JSON Schema or a JSON template.
```bash
python -m docquorum.extract invoice.pdf --schema invoice_schema.json -o invoice.json
python -m docquorum.extract receipt.jpg --schema receipt_template.json          # template in, template out
python -m docquorum.extract report.pdf --schema s.json --task "Extract every holding in the schedule of investments."
```
Run these from the project folder (or add it to `PYTHONPATH`). Progress and a final report (which readings were made,
which one was kept, their agreement) go to stderr; the JSON goes to `-o` or stdout.

**Python.**
```python
from docquorum.extract import extract
result, report = extract("invoice.pdf", schema_dict, task=None)
print(report)   # the readings produced, the one the quorum kept, their agreement
```

**A JSON template** is a JSON object whose leaves are empty (`""`, `[{...}]`, `{...}`); the result follows the template
exactly, with `""` for anything the document does not contain. **A JSON Schema** gives typed output, and every reply is decoded
under it. Put field instructions in the schema's `description` fields: they are sent to the model.

**What happens to your document.** A PDF with a text layer is read once by the reader agent. A scan or image of 12 pages or fewer is read
three ways (the reader agent on its page images, the reader agent on its MinerU parse, and a one-shot reader) and the quorum keeps
the reading the others agree with most; a longer scan is read through its parse. Documents printed as columns of records, and ruled tables on scans, go to a layout reader. Every
reading is repaired and checked against the schema and the page text before it is returned. Without the parser server, a scan is
read from its page images (and, up to 12 pages, by the one-shot reader).

---

## 5. Run the benchmarks

All commands run from the project folder, with `source configs/local.env` done and the servers of section 3 up.
They call the model thousands of times and take hours on one GPU. A fresh run lands within noise of the stored results
(on the short split, 61 of 251 documents change by a mean of 0.76 points; the split mean moves by 0.15).

### ExtractBench
Data: section 1, step 2, **including `docs/`** (the PDFs). Outputs go to `runs/` (`DQ_RUNS`), logs to `logs/`.
```bash
benchmarks/extractbench/run.sh short        # then: medium, long
```
The script runs, in order: the reader agent on every document; the checks; the parse reading for scans; the one-shot reading
and the quorum for scans of 12 pages or fewer; the layout readers (medium and long only); and scoring. The last line it prints
is the split's mean value F1. Per-document scores are in `runs/<split>_scores.json`, the final outputs in `runs/<split>_final/`.
Each step is also a command you can run alone:

| step | command |
|---|---|
| reader agent | `python -m docquorum.agents.reader --split S --tag T [--parsed] [--only a,b]` |
| checks | `python -m docquorum.checks <primary\|parse\|oneshot\|layout> S in_dir out_dir` |
| quorum | `python -m docquorum.quorum S out_dir reading_dir reading_dir ...` |
| layout readers | `python -m docquorum.agents.layout S [--decide-only]` |
| parse the scans | `python -m docquorum.tools.parser S` |
| score | `python benchmarks/extractbench/score_run.py --split S --run DIR [--json FILE]` |

### UNIKIE-BENCH
Data: `DQ_UNIKIE_DIR` (section 1). The parser server must be up for `read`.
```bash
benchmarks/unikie/run.sh read                 # parses the images, then makes the four readings with the 27B model
benchmarks/unikie/run.sh read-extra 32        # tuned configuration: one-shot reading by Qwen3-VL-32B (serve_qwen3vl_32b.sh running instead of the 27B)
benchmarks/unikie/run.sh read-extra 8         # tuned configuration: one-shot reading by Qwen3-VL-8B (serve_qwen3vl_8b.sh running; set DQ_LLM_URL=http://localhost:8078/v1)
benchmarks/unikie/run.sh score                # frozen and tuned macro F1
python benchmarks/unikie/unikie_eval.py report   # placed against the published systems
```
Readings are written to `results/unikie/readings/`, so a fresh `read` adds to (or replaces) the stored ones: to keep the stored
results, run with `DQ_UNIKIE_READINGS=/some/other/folder`.

### Contextual AI ExtractBench (held out)
Needs the benchmark's repository (`pip install -e <repo>`) and a judge endpoint (by default the same 27B server: no document is sent
to an external API).
```bash
benchmarks/contextual/run.sh                  # adapter -> parse -> pipeline -> the benchmark's evaluator
```
See [`results/README.md`](results/README.md) for what the two reported configurations (frozen, post-hoc) mean.

### Tests
```bash
python -m pytest tests/                        # 15 unit tests; no model, parser or data needed
```

---

## 6. Troubleshooting

| message or symptom | cause and fix |
|---|---|
| `FileNotFoundError: ... 'pdftotext'` | Poppler is not on `PATH`: install it, or set `DQ_POPPLER_BIN` to its folder |
| `ModuleNotFoundError: docquorum` | run from the project folder, or `export PYTHONPATH=$PWD` |
| `openai.APIConnectionError` / connection refused | the model server is not up (section 3), or `DQ_LLM_URL` is wrong. `curl $DQ_LLM_URL/models` must answer |
| `ModuleNotFoundError: extract_bench`, or a Python-version error | `pip install llama-extract-bench` in a **Python 3.12+** environment, and use that interpreter (`DQ_PYTHON`) |
| a scan gives poor or empty output | the parser is not running (`DQ_PARSER_URL`); scans then fall back to page images only |
| `FileNotFoundError` for a PDF under `data/extractbench/docs` | the PDFs are missing: the `.jsonl` files alone are enough only for scoring |
| `kie_evaluator` not found (UNIKIE) | `DQ_UNIKIE_DIR` does not point at a clone of the UNIKIE-BENCH repository |
| vLLM runs out of memory at start | another process holds the GPU (`nvidia-smi`); the 27B needs about 70 GB free at `GPU_UTIL=0.74` |
| scores differ slightly from the tables after a fresh run | expected (noise figures in section 5). Re-scoring the stored outputs (section 1) reproduces the tables exactly |

---

## 7. Repository layout

```
docquorum/            the pipeline (file by file: docs/CODE_GUIDE.md)
  extract.py            the whole pipeline on one document (CLI + Python API)
  config.py             endpoints and paths (the only environment variables)
  extractbench.py       benchmark records and the benchmark's scorer
  quorum.py             the reading the others agree with most
  tools/                what the agents act with, no decisions: pdf, parser, llm, schema, rows, layout
  agents/               the readers: reader (plan / act / observe), whole, oneshot, layout (+ column_reader, ruled_reader), prompts
  checks/               deterministic repairs and checks, one file each, and their chains
benchmarks/           ExtractBench, UNIKIE-BENCH and Contextual AI ExtractBench runners and scorers
serve/                vLLM serving scripts
configs/              example.env (copy it to local.env)
results/              scores, final outputs, research log; archive/ holds the code before the 2026-09-29 reorganisation
docs/                 docquorum.tex / .pdf (the pipeline explained), CODE_GUIDE.md, examples/ (six documents, output after every stage)
tests/                unit tests
FROZEN.json           the configuration frozen before the held-out benchmarks were downloaded
```
Not in the repository (too large, or third-party): `data/` (benchmark data), `cache/` (parses), `runs/` and `logs/` (outputs of
fresh runs), `ref_papers/`. `runs/`, `logs/` and `cache/` are created on first use.

## 8. Notes

* Lessons that shaped the design are in [`results/RESEARCH_LOG.md`](results/RESEARCH_LOG.md), including negative results (asking the
  model to verify its own output did not help in 22 attempts; prompt rules fixed one scenario and broke others) and one correction
  (an earlier quorum measured agreement with the benchmark's annotated record and so used gold; all numbers above are clean: the
  quorum sees only the schema and the readings).
* ExtractBench served as the development set. The numbers labelled "frozen" or "held-out" were produced by a configuration fixed
  before those benchmarks were opened; see [`FROZEN.json`](FROZEN.json) and `results/README.md`.
* `docs/examples/` includes small benchmark PDFs and their answer keys, for illustration.
* License: MIT (see `LICENSE`). The benchmarks and models keep their own licenses.
