# DocQuorum: the pipeline on real benchmark documents (LaTeX Beamer)

Open [docquorum-flow.pdf](docquorum-flow.pdf): 18 slides at 16:9, built from [docquorum-flow.tex](docquorum-flow.tex).

| Slide | Content |
|---|---|
| 1-2 | Title; outline |
| 3 | Problem statement: input (document, JSON Schema or template, optional task) and output; a real scanned form with its 77-field schema and a real task text |
| 4 | Pipeline overview: the pipeline figure (generated with Codex), including the reader agent's plan-act-observe loop |
| 5 | Step 2, routing: five real documents and the route each takes (A-D), with pages and embedded characters per page |
| 6 | Step 2, MinerU: a scanned FTX table page, the raw MinerU HTML, and the same rows as cells |
| 7 | Step 3, column reader: Oklahoma register, 7 detected columns, the records returned |
| 8 | Step 3, ruled-table reader: FTX page 47, detected rules, one header-plus-12-row band; 67 rows counted, 67 returned |
| 9 | Step 3, three readings of one scan (1955 form): image 59/77 fields, parse 59/77, one-shot 1/77 |
| 10-11 | Step 4, deterministic checks: eight real before/after cases, each with its measured value F1 |
| 12 | Step 5, quorum: pairwise agreement, the kept reading, and a case where agreement is not accuracy |
| 13 | Step 6, output: schema in, JSON out; template in, filled template out |
| 14-16 | ExtractBench, complete table: all 47 published systems and DocQuorum (3rd, 95.43) |
| 17 | UNIKIE-BENCH, complete table: all 15 published systems and DocQuorum, all 11 scenarios (tied 1st, 82.37) |
| 18 | Summary: results, method, limitations |

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
- **Results tables:** the snapshots in `docs/results/`, the same ones used by `docs/docquorum.pdf`.
  - ExtractBench: 95.43, scored with the scorer revision of that leaderboard snapshot.
  - UNIKIE-BENCH: 82.37, the quorum over six readings.

## Rebuild

From the repository root (needs `data/`, `cache/parse/`, Poppler, Pillow, the ExtractBench package, and pdflatex with the Beamer `metropolis` theme):

```sh
python ppt/flow/make_assets.py     # page renders and overlays -> ppt/flow/assets/, facts.json
python ppt/flow/build_beamer.py    # writes docquorum-flow.tex and compiles docquorum-flow.pdf
```

`assets/quorum_example.json` and `assets/unikie_example.json` were computed from the stored readings. They are kept here so the slides build without the run folders.

`pptx-version/` holds the earlier, less formal PowerPoint version of this deck, which this one replaces. The separate deck in `ppt/` (`docquorum.pptx`) was built independently, by another session.
