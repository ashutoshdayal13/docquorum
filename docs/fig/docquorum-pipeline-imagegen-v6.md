# Pipeline v6 image: DocQuorum v1.3

This new image follows the route-lane composition of v4, with the current implementation replacing the old flow. The automation legend is a small key. Generated with the built-in image tool; the final generation and arrow-correction prompts are in [the prompt file](docquorum-pipeline-imagegen-v6-prompt.txt). The standalone PDF embeds the raster without claiming vector resolution. Earlier draft renders were discarded after reviewing their routing arrows.

## Implementation basis

Reviewed at repository revision `7200901` against `docs/DESIGN.md`, `RELEASE.json`, and the pipeline source. The source hashes in the v1.3 release manifest were checked before drawing. The code is authoritative where wording in comments or the design differs.

| Image element | Implementation |
|---|---|
| Native files; TIFF pages; orientation, transparency and small-image enlargement | `extract.as_pdf`, `tools/native.py`, `tools/images.py` |
| Task extends the schema description; native input counts as text-bearing | `extract._extract` |
| Layout first; read the target list plus remaining schema fields | `agents/layout.py`, `agents/column_reader.py`, `agents/ruled_reader.py`, `extract._extract` |
| Layout fallback on no records or missing rules on most eligible table pages | `extract._extract`, `agents/layout.rules_missing` |
| P/M are independent runs of the same adaptive reader | `agents/reader.py`, `agents/whole.py` |
| One-shot is attempted only on no-text documents of at most 12 pages | `extract._extract`, `agents/oneshot.py` |
| Long scans use quorum when multiple readings remain | `extract._extract`; the previous prefer-parse return was removed |
| Opening-page legends, per-entity reference rows and shared facts reach list chunks | `agents/reader._reference`, `_reference_for`, `_read_list`, `agents/prompts.py` |
| Null-aware grammar and required-key retries | `tools/llm.extra_body`, `tools/schema.py`, `agents/reader._read_whole` |
| Repetition detection and bounded splitting/retry/fallback | `agents/reader.py`, `tools/rows.py` |
| Source-specific deterministic checks | `checks/__init__.py`; OUTPUT now includes `printed_suffix` |
| Whole-reading selection; exclude looped winners when alternatives exist | `quorum.pick` |
| Disagreement-guided zoom after multi-candidate selection | `extract._extract`, `zoom.reread` |
| Template restoration and extraction report | `extract._finish`, `tools/schema.fill_template` |

## Selection and zoom: important boundaries

Layout and one-reading paths return directly. Short and long no-text routes keep the sole retained candidate or use quorum for multiple candidates. Quorum first keeps one complete reading, with ties following insertion order. It does not synthesize a record from multiple candidates.

After quorum, zoom can correct disputed leaf values of that retained reading. It considers up to 40 disputed paths present in the kept reading, locates a source block with MinerU, and makes an independent extraction-model call on a 300-dpi crop. Candidate values guide block location but are not shown to the crop-reading model. Zoom updates a value only if the re-read matches an existing proposal and that proposal's original support plus two zoom votes strictly exceeds support for the kept value. Unlocated, ineligible or unconfirmed disagreements leave the selected value unchanged. Zoom is enabled by default when the parser is available and can be disabled with `--no-zoom`. No second whole-document extraction or unbounded verifier loop is implied.

## Scope and simplifications

The figure describes `docquorum.extract.extract`, not the separate benchmark-specific ensemble protocols. No model identity, benchmark rank or score is part of this architecture. MinerU parsing is model-based; routing, checks and comparison are code. Python manages adaptive state and tool invocation; the LLM does not choose arbitrary tools.

The diagram shows successful paths and summaries of the implemented guards. Image use depends on scope: text fragments split from a chunk omit page images to avoid reading outside their scope. The parse mode needs sufficient cached-page coverage. An attempted reading may fail, and no successful reading remains an exception. Checks indicate processing rather than guaranteed semantic correctness. Optional scalars admitted by the grammar may be null; this is not a claim that every required field is nullable or that every model call uses a full schema grammar.
