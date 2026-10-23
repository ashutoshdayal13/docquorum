# DocQuorum: the pipeline on real benchmark documents (LaTeX Beamer)

Open [docquorum-flow.pdf](docquorum-flow.pdf): 26 slides at 16:9, written by `build_beamer.py` as [docquorum-flow.tex](docquorum-flow.tex).

| Slide | Content |
|---|---|
| 1-2 | Title; outline |
| 3 | Problem statement: input (document, JSON Schema or template, optional task) and output; a real scanned form with its 77-field schema and a real task text |
| 4 | Pipeline overview: the pipeline figure, including the reader agent's plan-act-observe loop |
| 5-6 | Routing: five real documents and the route each takes; MinerU returns a scanned table as cells |
| 7-9 | Readers: the column reader, the ruled-table reader, three readings of one scan |
| 10-11 | Deterministic checks: real before/after cases, each with its measured value F1 |
| 12-13 | The quorum's choice; one checked JSON, in the form requested |
| 14 | Results on six benchmarks: score, place, the best published system below DocQuorum, and measured calls, dollars and seconds per document |
| 15 | What the pipeline adds to the same model: Qwen3.8-27B called once against DocQuorum, with the place each reaches |
| 16 | Accuracy at a fraction of the cost: ExtractBench, every priced system scoring 85 or more |
| 17 | Zoom re-reading and its three tests |
| 18 | Summary: results, method, limitations |
| 19-26 | Complete results, one design for every benchmark: VAREX, UNIKIE-BENCH, LongArray-Extract, UNIKIE open, ExtractBench (3), DocuBench |

[pipeline-talk.txt](pipeline-talk.txt) is a plain-English script for presenting the pipeline figure (slide 4), with notes and likely questions.

## Where the numbers come from

No model was called to build the slides; every example is a real benchmark document and a stored output.

- **Pages and parses:** rendered from `data/extractbench/docs/` with Poppler, and cached MinerU parses from `cache/parse/`.
- **Layout overlays:** drawn with the pipeline's own geometry code (`docquorum/tools/layout.py`).
- **Three readings and quorum:** the stored, checked readings of `2A-9-160298_109929`.
  - The agreements were computed by `docquorum.quorum.pick` and saved in `assets/quorum_example.json`.
  - Answer-key F1 appears only as an illustration; the pipeline never uses it.
- **Check examples:** stored readings before each check, re-run through `docquorum/checks` and scored with ExtractBench's scorer.
  - The examples are the cases each check was designed for.
  - The slide notes that some repairs lower the score slightly on a few short documents.
- **Results:** the snapshots and summaries in `docs/results/` (the same ones as `docs/docquorum.pdf`, `README.md` and
  `docs/results/TABLES.md`, through `docs/results/leaderboards.py`), the measured costs in `results/costs/`, and the one-call
  baselines in `results/varex/one-call/` and `results/unikie/summary.json`.

## Rebuild

From the repository root:

```sh
python ppt/flow/make_assets.py     # page renders and overlays -> ppt/flow/assets/, facts.json
python ppt/flow/build_beamer.py    # charts, then docquorum-flow.tex, compiled to docquorum-flow.pdf
```
`make_assets.py` needs the benchmark data (`data/`, `cache/parse/`), Poppler, Pillow and the ExtractBench package; its outputs
are stored in `assets/`. `build_beamer.py` needs only the stored results, matplotlib, and pdflatex with the Beamer `metropolis` theme.

`assets/quorum_example.json` and `assets/unikie_example.json` were computed from the stored readings. They are kept here so the slides build without the run folders.

`pptx-version/` holds a shorter PowerPoint version of this deck (its own builder, the same tables' design). The worked-example
walkthrough deck is `ppt/docquorum.pdf` (`ppt/README.md`).
