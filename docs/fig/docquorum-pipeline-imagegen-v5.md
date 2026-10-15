# Pipeline v5: controller, readers and tools

Generated with the built-in image tool as a redesign of v4. The exact prompt is saved alongside the PNG. The standalone PDF embeds the same raster image. The reader and tool mapping is documented in [AGENTS_AND_TOOLS.md](../AGENTS_AND_TOOLS.md).

The three bands distinguish the main data flow, the five reader workflows and their tools, and the bounded adaptive loop plus route policy. Primary and parse-based readings share the same agent implementation but run separately. Column and ruled-table readers are alternatives producing L, not two simultaneous layout candidates. One-shot is a scheduled extraction workflow.

Source review: `docquorum/extract.py`; `agents/reader.py`, `whole.py`, `layout.py`, `column_reader.py`, `ruled_reader.py`, `oneshot.py`; `tools/pdf.py`, `parser.py`, `schema.py`, `rows.py`, `layout.py`, `llm.py`; `checks/__init__.py`; `quorum.py`.

Poppler provides PDF metadata, embedded text and rendered pages. MinerU is a distinct learned parser producing cached text and HTML tables. Schema, row and layout helpers are code. The extraction-model API returns task-specific JSON. Python invokes these tools; the LLM does not autonomously select them. Routing, checks and quorum are deterministic code rather than LLM agents.

The plan/act/observe/adapt loop summarizes the general reader's implemented guards and fallbacks. Scopes are alternatives, not obligatory sequential calls. Image eligibility and parse coverage remain plan-dependent. Parse mode needs cached evidence. Readers may share source evidence but do not receive one another's answers. Candidate labels identify sources, not necessarily different models.

Successful paths are shown; exceptions remain possible. Checks do not guarantee semantic accuracy. Quorum retains a complete candidate without answer keys or field fusion. No formula or error terminal is included in the image.
