# DocQuorum

DocQuorum pulls structured data out of documents. You give it a document (PDF, image, or an Office, HTML, XML, CSV
or text file) and a JSON Schema or JSON template, and it returns JSON that follows the schema. It runs locally on
open models: Qwen3.8-27B and the MinerU2.5 parser.

## Results

| Benchmark | Score | Place |
|---|---:|---|
| VAREX | 98.23 | 1st of 21 |
| UNIKIE-BENCH | 82.65 | 1st of 16 |
| LongArray-Extract | 98.05 | 2nd of 12 |
| UNIKIE-BENCH (open category) | 72.33 | 2nd of 16 |
| ExtractBench | 95.43 | 3rd of 48 |
| DocuBench | 91.54 | 4th of 10 |

Each benchmark is scored with its own scorer. The outputs behind these numbers are in `results/`.

## Setup

```bash
pip install -r requirements.txt
pip install "git+https://github.com/run-llama/ExtractBench.git@123cea5f4940b5d5211677e3a95a6c300ab474f5"
sudo apt-get install poppler-utils
cp configs/example.env configs/local.env    # edit it, then: source configs/local.env
```

The models need one 80-96 GB GPU and vllm 0.27.1:

```bash
serve/serve_qwen38_27b.sh    # the model, port 8079
serve/serve_mineru.sh        # the parser, port 8081 (only needed for scans and images)
```

## Usage

```bash
python -m docquorum.extract invoice.pdf --schema invoice_schema.json -o invoice.json
```

```python
from docquorum.extract import extract

result, report = extract("invoice.pdf", schema)
```

## Reproducing the numbers

The stored outputs can be re-scored without a GPU. Each benchmark's data goes under `data/`. ExtractBench is scored
against its published dataset (revision `51bf3a0`).

```bash
for s in short medium long; do
  python benchmarks/extractbench/score_run.py --split $s --run results/extractbench/predictions/$s.jsonl --json $s.json
done
python benchmarks/extractbench/overall.py short.json medium.json long.json

python benchmarks/multibench/run.py varex score --stored results/varex/final
python benchmarks/multibench/run.py longarray score --stored results/longarray/final
python benchmarks/multibench/run.py docubench score --stored results/docubench/v1.4

benchmarks/unikie/run.sh score && python benchmarks/unikie/zoom_unikie.py score
```

For the UNIKIE open category, run `set -a; source configs/unikie_open.env; set +a` first.

To run everything from scratch: `benchmarks/extractbench/run.sh short` (and `medium`, `long`),
`benchmarks/unikie/run.sh read`, and `python benchmarks/multibench/run.py <varex|longarray|docubench> run`.

Tests: `python -m pytest tests/`

## License

MIT
