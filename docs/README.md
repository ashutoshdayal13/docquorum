# DocQuorum pipeline guide

Start with [the document](docquorum.pdf): task definition, complete data flow, exact reader behavior, checks, candidate selection, and a synthetic walkthrough.

- [LaTeX source](docquorum.tex)
- [Main pipeline diagram (PDF)](fig/pipeline.pdf) and [editable TikZ source](fig/pipeline.tex)
- [Illustrated purchase-order trace](fig/scan-trace.tex) and [four routing examples](fig/route-examples.tex)
- [Implementation map](CODE_GUIDE.md)

![Illustrated API flow](fig/pipeline.png)

The landscape overview on page 2 follows the flow from left to right: route, read, check, select, return. Four document lanes share one checks panel, with the exact chain shown once for each reading source. The rest of the guide stays portrait. Page 8 follows a synthetic purchase order through three independent candidates and into the final JSON. Page 9 compares four document routes; page 10 explains how the ExtractBench and UNIKIE runners differ. The main diagram describes the single-document API. The guide is based on source revision `b4ea9a1`; numerical examples are illustrative, not measured benchmark results.

## Build

With `pdflatex`, TikZ/PGF, Latin Modern, and the standard LaTeX packages installed:

```sh
make -C docs
make -C docs preview  # optional PNG refresh; requires Poppler's pdftoppm
make -C docs clean
```

Run from the repository root. If Poppler is outside your `PATH`, set `PDFTOPPM=/path/to/pdftoppm` when running the preview target. Both PDFs and the PNG preview are committed so reading the guide does not require LaTeX. The diagram is vector artwork and shares its source with the document. There are no model calls, dataset dependencies, or network downloads in the build.

This folder replaces the former write-up and benchmark-example bundle. Benchmark outputs and results remain in `results/`; older documentation is available in Git history.
