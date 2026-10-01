# DocQuorum pipeline guide

Start with [the document](docquorum.pdf): task definition, complete data flow, exact reader behavior, checks, candidate selection, and a synthetic walkthrough.

- [LaTeX source](docquorum.tex)
- [Main pipeline diagram (PDF)](fig/pipeline.pdf) and [editable TikZ source](fig/pipeline.tex)
- [Implementation map](CODE_GUIDE.md)

The main diagram describes the single-document API. Page 9 explains how the ExtractBench and UNIKIE runners differ. The guide is based on source revision `b4ea9a1`; numerical examples are illustrative, not measured benchmark results.

## Build

With `pdflatex`, TikZ/PGF, Latin Modern, and the standard LaTeX packages installed:

```sh
make -C docs
make -C docs clean
```

Run from the repository root. Both PDFs are committed so reading the guide does not require LaTeX. The diagram is vector artwork and shares its source with the document. There are no model calls, dataset dependencies, or network downloads in the build.

This folder replaces the former write-up and benchmark-example bundle. Benchmark outputs and results remain in `results/`; older documentation is available in Git history.
