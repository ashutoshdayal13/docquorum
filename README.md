# DocQuorum

**Agentic document extraction with open models.** Give DocQuorum a document (a PDF, an image, or a spreadsheet, Word,
HTML, XML, CSV or text file) and a JSON Schema (or a JSON template); it returns JSON that follows the schema. It runs on
open-weight models (Qwen3.8-27B and the MinerU2.5 parser) on one GPU; no commercial API is used.

## Results

Each benchmark is scored with its own official scorer and placed against every published system. No result was
submitted to a leaderboard.

| benchmark | DocQuorum | place | cost per document |
|---|---:|---|---:|
| VAREX (1,777 government forms) | **98.23** | **1st of 21** | $0.021 |
| UNIKIE-BENCH (4,472 images) | **82.65** | **1st of 16** | $0.010 |
| LongArray-Extract (45 long documents) | **98.05** | 2nd of 12 | $0.68 |
| UNIKIE-BENCH open category (1,661 documents) | **72.33** | 2nd of 16 | $0.018 |
| ExtractBench (370 PDFs) | **95.43** | 3rd of 48 | $0.029 per page |
| DocuBench (72 documents, 10 file types) | **91.54** | 4th of 10 | $0.21 |

* The same Qwen3.8-27B called once, with each benchmark's own prompt, scores VAREX 97.48, UNIKIE-BENCH 80.45,
  UNIKIE open 70.91 and ExtractBench 89.75: the pipeline adds 0.75 to 5.68 points.
* Cost: the measured tokens priced at the model's public API price (`results/costs/`). On its own GPU there is no
  price per call. On ExtractBench the two systems above it cost $0.081 and $0.105 per page.
* ExtractBench was used during development; the other benchmarks were run with the pipeline as it stood.

## How it works

1. **Route.** A file with a text layer is read once; a scan or image is read two or three separate ways (page images,
   the MinerU parse, one single call); pages printed in columns and ruled tables go to layout readers.
2. **Read.** A reader agent reads the whole document, part of the schema, a window of pages or a chunk at a time,
   looks at its own output (cut off, missing keys, repeated rows) and reads again where needed.
3. **Check.** 14 rule-based checks repair the structure and make values match what the page prints.
4. **Choose.** The quorum keeps the reading the other readings agree with most.
5. **Zoom.** Fields the readings disagree on are read once more from a sharp crop of the page; the new value counts as
   two votes and must match a value some reading proposed.

## Install

* Python 3.12+, then `pip install -r requirements.txt` and ExtractBench's scorer:
  `pip install "git+https://github.com/run-llama/ExtractBench.git@123cea5f4940b5d5211677e3a95a6c300ab474f5"`
* Poppler (`pdftotext`, `pdftoppm`, `pdfinfo`): `sudo apt-get install poppler-utils`.
* To run the models: one 80-96 GB GPU and `vllm==0.27.1`.
* Settings: `cp configs/example.env configs/local.env`, edit it, then `source configs/local.env` in every shell.

## Serve the models

```bash
serve/serve_qwen38_27b.sh      # Qwen3.8-27B-FP8      -> http://localhost:8079/v1
serve/serve_mineru.sh          # MinerU2.5 parser     -> http://localhost:8081/v1  (scans and images only)
```
Stop both servers when you are done.

## Extract from one document

```bash
python -m docquorum.extract invoice.pdf --schema invoice_schema.json -o invoice.json
python -m docquorum.extract receipt.jpg --schema receipt_template.json        # template in, template out
python -m docquorum.extract form.png --schema form_schema.json --no-zoom      # without zoom re-reading
```
```python
from docquorum.extract import extract
result, report = extract("invoice.pdf", schema_dict, task=None)
```
Put field instructions in the schema's `description` fields: the model reads them.

## Check the reported numbers (no GPU)

The stored outputs are in `results/<benchmark>/<run>/predictions.jsonl` (one line per document). Re-scoring them needs
each benchmark's data under `data/` (paths in `configs/example.env` and `benchmarks/multibench/sources.py`).
```bash
for s in short medium long; do      # ExtractBench: 96.34 / 94.11 / 90.41, Overall 95.43
  python benchmarks/extractbench/score_run.py --split $s --run results/extractbench/predictions/$s.jsonl --json /tmp/$s.json | tail -n 1
done
python benchmarks/extractbench/overall.py /tmp/short.json /tmp/medium.json /tmp/long.json

python benchmarks/multibench/run.py varex score --stored results/varex/final          # 98.23
python benchmarks/multibench/run.py docubench score --stored results/docubench/v1.4   # 91.54
python benchmarks/multibench/run.py longarray score --stored results/longarray/final  # 98.05

benchmarks/unikie/run.sh score && python benchmarks/unikie/zoom_unikie.py score       # UNIKIE-BENCH: 82.65
# the open category: set -a; source configs/unikie_open.env; set +a, then the same two commands (72.33)
```

## Run the benchmarks

* ExtractBench: `benchmarks/extractbench/run.sh short` (then `medium`, `long`).
* UNIKIE-BENCH: `benchmarks/unikie/run.sh read`, then `score`.
* VAREX, LongArray-Extract, DocuBench: `python benchmarks/multibench/run.py <benchmark> run --variant mine`, then
  `score --variant mine`.
* Tests: `python -m pytest tests/` (no model or data needed).

## Repository layout

```
docquorum/      the pipeline: extract.py (entry point), agents/ (readers), tools/, checks/, quorum.py, zoom.py
benchmarks/     runners and scorers: extractbench/, unikie/, multibench/ (VAREX, LongArray-Extract, DocuBench)
results/        the reported results: outputs, scores and provenance per run; measured costs
serve/          the model servers
configs/        settings (copy example.env to local.env)
tests/          unit tests
```

MIT License.
