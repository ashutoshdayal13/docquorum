# Implementation map

Read [the pipeline guide](docquorum.pdf) first. Its main diagram follows `extract()`; the benchmark runners use different orchestration.

| Step | Source | Data contract |
|---|---|---|
| Prepare and orchestrate | [extract.py](../docquorum/extract.py) | Document + schema/template → `(result, report)` |
| Inspect/render PDF | [tools/pdf.py](../docquorum/tools/pdf.py) | PDF → text, page count, rendered images |
| Parse scans | [tools/parser.py](../docquorum/tools/parser.py) | Page image → cached text/HTML tables |
| Route layout | [agents/layout.py](../docquorum/agents/layout.py) | Schema + PDF + cache → `colflow`, `ruled`, or `route` |
| General reading | [agents/reader.py](../docquorum/agents/reader.py) | Evidence + schema → candidate, statistics, plan |
| Whole/group/window calls | [agents/whole.py](../docquorum/agents/whole.py) | Selected evidence + schema share → object; merge windows |
| Column reading | [agents/column_reader.py](../docquorum/agents/column_reader.py) | Ordered column crops → main-array records |
| Ruled-table reading | [agents/ruled_reader.py](../docquorum/agents/ruled_reader.py) | Header + counted row bands → main-array records |
| One-shot reading | [agents/oneshot.py](../docquorum/agents/oneshot.py) | PDF + schema → provider candidate |
| Check each reading | [checks/__init__.py](../docquorum/checks/__init__.py) | Candidate + `Doc` → checked candidate |
| Select | [quorum.py](../docquorum/quorum.py) | Checked candidates + schema → winner, scores, pairwise metrics |
| Format templates | [tools/schema.py](../docquorum/tools/schema.py) | Selected object + template → template-shaped result |

Supporting modules: [prompts](../docquorum/agents/prompts.py), [LLM calls](../docquorum/tools/llm.py), [row estimates](../docquorum/tools/rows.py), [geometry](../docquorum/tools/layout.py), and [configuration](../docquorum/config.py).

## Exact check order

- **Primary:** `carry_down → page_index → dedupe → stacked_rows → OUTPUT`.
- **Parse:** `spacing → primary chain`.
- **One-shot/layout:** `OUTPUT`.
- **OUTPUT:** `conform → blank_boxes → template_rows → copied_rows → record_counts → printed_pages → printed_quotes → printed_numbers`.

Each module in [checks/](../docquorum/checks/) defines `apply(pred, doc)`. Guards make these conditional transformations, not universal corrections. `conform` is not a full schema validator.

## Separate benchmark entry points

[ExtractBench run.sh](../benchmarks/extractbench/run.sh) operates on stage directories and applies layout overrides after the general flow, excluding the short split. Populate parses first with `python -m docquorum.tools.parser SPLIT`. [UNIKIE](../benchmarks/unikie/unikie_eval.py) has its own six-reading protocol, normalization, and quorum matcher. [extractbench.py](../docquorum/extractbench.py) wraps the external scorer; selection replaces the reference with another candidate and removes annotated matching rules.

## Historical names

For the frozen archive referenced by `FROZEN.json`:

| Historical module | Current location |
|---|---|
| `agentic.py`, `wholedoc.py` | `agents/reader.py`, `agents/whole.py` |
| `pipeline.py`, `schemautil.py` | `tools/llm.py`, `tools/pdf.py`, `tools/schema.py`, `tools/rows.py`, `agents/prompts.py` |
| `settings.py`, `docparse.py`, `imgview.py` | `config.py`, `tools/parser.py`, `tools/pdf.py` |
| `tablefix.py`, `textpanels.py`, `okcols.py`, `ruled.py`, `tabconv.py` | `tools/layout.py` |
| `colflow.py`, `ruledview.py`, `layout_stage.py` | `agents/column_reader.py`, `agents/ruled_reader.py`, `agents/layout.py` |
| `medoidroute.py`, `ebscore.py` | `quorum.py`, `extractbench.py` |
| `reconcile.py`, `headfill.py`, `pagefix.py`, `stackfold.py` | `checks/spacing.py`, `checks/carry_down.py`, `checks/page_index.py`, `checks/stacked_rows.py` |
| `boolblank.py`, `emptyrows.py`, `xarray.py`, `dupcap.py` | `checks/blank_boxes.py`, `checks/template_rows.py`, `checks/copied_rows.py`, `checks/record_counts.py` |
| `pagegrid.py`, `typosnap.py`, `numsnap.py` | `checks/printed_pages.py`, `checks/printed_quotes.py`, `checks/printed_numbers.py` |

Historical validation claims are preserved in Git history; this documentation replacement changes no extraction code or benchmark outputs.
