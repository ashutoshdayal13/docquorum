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
| Zoom re-reading (optional) | After the quorum: each field the candidates disagree on is located on the page and read again from a sharp crop; a value changes only to one a candidate proposed | [zoom.py](../docquorum/zoom.py) |

P and M identify evidence modes, not different model identities. Column and ruled-table readers are alternatives producing the same candidate source label L. Calling a module an agent does not make its decisions LLM-based: layout routing is implemented with geometry and schema-mapping rules.

| Tool or service | What it produces | Who uses it |
|---|---|---|
| Pillow | Image-to-PDF conversion and image manipulation | Input preparation and image-based reading workflows |
| Poppler (`pdfinfo`, `pdftotext`, `pdftoppm`) | Page count, embedded text, rendered pages | Controller, readers, parser preparation and source checks |
| MinerU parser | Learned page parsing: cached text blocks and HTML tables | Scan preparation; parse-based reader, layout routing, zoom re-reading (block locations) and applicable source checks |
| Schema helpers | Compact schemas, groups, scalar/list schemas and missing-key detection | Reader planning and reply handling |
| Row/layout helpers | Evidence row estimates, text chunks, panels, column crops and ruled bands | Reader planning and specialized layouts |
| Extraction-model API | Schema-guided JSON replies from text and/or image evidence | Primary, parse, column, ruled and one-shot workflows |

MinerU and the extraction model are distinct learned services. MinerU's parse is source evidence, not the task's final extracted JSON. Tools are invoked by Python; they are not exposed as arbitrary tool choices to a planning LLM.

The adaptive reader chooses an eligible scope, reads, inspects truncation or missing keys, and may retry with a larger budget, required keys or smaller pieces. An empty chunk despite sufficient row evidence can trigger another read. Python retains the reading state and enforces the bounds. Eligible scopes are alternatives, not four mandatory sequential calls. This bounded feedback loop is the agentic behavior shown in the main figure.
