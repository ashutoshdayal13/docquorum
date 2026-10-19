# Controller, readers and tools

All operations after input submission run automatically. The extraction model supplies values; Python selects the workflow, prepares evidence, calls the model and handles its replies. The model does not autonomously choose tools.

| Component | Role | Implementation |
|---|---|---|
| Extraction controller | Normalize input, inspect evidence, route, run readers, apply checks, select and format | [extract.py](../docquorum/extract.py) |
| Primary reader (P) | Bounded adaptive reader using PDF text and eligible page images | [reader.py](../docquorum/agents/reader.py), [whole.py](../docquorum/agents/whole.py) |
| Parse-based reader (M) | Separate run of the same adaptive reader, using cached MinerU evidence when coverage permits; eligible plans can use images | Same code, `use_parsed=True` |
| Column reader (L) | Scheduled column crops, model reading and continuation assembly | [column_reader.py](../docquorum/agents/column_reader.py) |
| Ruled-table reader (L) | Scheduled header-plus-row-band reading with constrained row counts | [ruled_reader.py](../docquorum/agents/ruled_reader.py) |
| One-shot reader (O) | Whole-document extraction through the ExtractBench provider | [oneshot.py](../docquorum/agents/oneshot.py) |
| Checks | Deterministic transformations of one candidate using schema and available source evidence | [checks](../docquorum/checks/__init__.py) |
| Quorum | Deterministic candidate comparison; retain one complete JSON | [quorum.py](../docquorum/quorum.py) |
| Zoom re-reading | Enabled by default after quorum when the parser is available; locate disputed fields and read sharp crops independently. Apply an existing proposal only when its support plus two zoom votes beats support for the kept value. Can be disabled with `--no-zoom`. | [zoom.py](../docquorum/zoom.py) |

P and M identify evidence modes, not different model identities. Column and ruled-table readers are alternatives producing the same candidate source label L. Calling a module an agent does not make its decisions LLM-based: layout routing is implemented with geometry and schema-mapping rules.

In v1.3, the layout reader extracts its target list and the general reader supplies remaining schema fields. Empty results or insufficient ruled-page coverage fall back to normal routing. Both short and long no-text routes use quorum when multiple readings remain; the old long-scan preference for parse is gone. Text-bearing/native and sole-reading routes return without zoom. Quorum keeps a complete reading first; the subsequent guarded zoom step may change disputed leaf values, so the final output is not necessarily identical to that original reading.

| Tool or service | What it produces | Who uses it |
|---|---|---|
| Pillow | Image-to-PDF conversion and image manipulation | Input preparation and image-based reading workflows |
| Native-file helpers | Text-bearing PDF from spreadsheet cells, Word text or other supported textual files | Input preparation; native files count as text-bearing even when short |
| Poppler (`pdfinfo`, `pdftotext`, `pdftoppm`) | Page count, embedded text, rendered pages | Controller, readers, parser preparation and source checks |
| MinerU parser | Learned page parsing: cached text blocks and HTML tables | Scan preparation; parse-based reader, layout routing, zoom re-reading (block locations) and applicable source checks |
| Schema helpers | Compact schemas, groups, scalar/list schemas and missing-key detection | Reader planning and reply handling |
| Row/layout helpers | Evidence row estimates, text chunks, panels, column crops and ruled bands | Reader planning and specialized layouts |
| Extraction-model API | Extraction JSON from text and/or images; independent field-value replies for zoom | Primary, parse, column, ruled, one-shot and zoom workflows |

MinerU and the extraction model are distinct learned services. MinerU's parse is source evidence, not the task's final extracted JSON. Tools are invoked by Python; they are not exposed as arbitrary tool choices to a planning LLM.

The adaptive reader chooses an eligible scope, reads, inspects truncation, missing keys or repetition loops, and may retry with a larger budget, nullable required keys, smaller pieces or a repetition penalty. The model server ends a reply that keeps repeating one stretch of tokens (40 times in a row), so a loop is caught after a few thousand tokens rather than at the output limit. An empty chunk despite sufficient row evidence can trigger another read. List chunks receive relevant legends and entity facts copied from the opening text. Python retains the reading state and enforces the bounds. Eligible scopes are alternatives, not four mandatory sequential calls. This bounded feedback loop is the agentic behavior shown in the main figure.

Zoom reads at most 40 disputed leaf paths from the selected reading. MinerU uses proposed values to locate source blocks, but the crop-reading model sees only the field description and image, not candidate answers. Unlocated or unconfirmed disputes keep the selected value. This is a bounded source re-read rather than an open-ended verifier agent.
