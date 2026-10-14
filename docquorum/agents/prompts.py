"""
Every prompt the readers send. Words in braces are filled per call; the schema itself goes to
the server as the decoding schema as well as into the prompt.
"""

# ---- the reader agent: one call over the whole document (or a schema part, or a window) ----
WHOLE = """You are extracting structured data from a complete document.

{task}The document has {n} page(s). {modality}

{text_block}Return ONE JSON object that follows this schema exactly:
{schema}

Rules:
- Extract every field from wherever it appears in the document; fill each list with every
  entry the document contains, in document order.
- Copy values exactly as printed unless a field's description asks for a normalised form.
{rules}
- If a field is blank, not applicable, or not present in the document, use null -- never
  invent a value.
Reply with the JSON object only."""

TEXT_LAYER = "The document's text layer (exact characters):\n{body}\n--- END TEXT ---\n\n"
OCR_TEXT = ("OCR text of the scanned pages (machine-read: it can misread characters and drop "
            "decimal points, spaces or punctuation; where it disagrees with the page images, "
            "follow the images):\n{body}\n--- END TEXT ---\n\n")

# ---- the reader agent: one chunk of pages, for one list ----
CHUNK = """You are extracting rows of a table from one part of a long document.

{context}Below is the text of pages {p0}-{p1}, with column alignment preserved.

--- PAGE TEXT ---
{text}
--- END PAGE TEXT ---

You are collecting the list called "{array_name}".
{array_desc}Each entry of that list is one JSON object with this schema:
{item_schema}

Return EVERY entry of "{array_name}" that appears in the text above, in the order
it appears. Only rows belonging to "{array_name}" count -- if the pages also contain other
kinds of rows, leave those out.
- Do not include column headers, page headers/footers, case captions or totals.
- Do not invent rows, and do not skip rows that look similar to their neighbours.
- If a field is blank for a row, use null.
- If there are no data rows in this text at all, return [].

Reply with a JSON array only:
[{{...}}, {{...}}]"""

# material from elsewhere in the document that a chunk's rows depend on (legends, code keys,
# per-entity reference tables), copied once per list and put before every chunk's text; when
# the document has none, CHUNK is sent exactly as without it
REFERENCE = """Below are the opening pages of a long document. Later pages hold the list "{array_name}",
which will be read a few pages at a time by a reader who sees only those pages.
{array_desc}Each entry has these fields:
{fields}

Copy out, VERBATIM, only the material in these opening pages that a reader of a later page
would need to fill those fields but would not find on that page:
- code legends and abbreviation keys (for example "1=mild; 2=moderate; 3=severe");
- reference tables giving attributes of the people, accounts or items the entries belong to
  (one line per identifier, with its attributes), when the entries' own rows do not repeat them.
Do NOT copy entries of "{array_name}" themselves, narrative text, or anything else.
If these pages contain no such material, reply with exactly: NONE

--- OPENING PAGES ---
{text}
--- END OPENING PAGES ---"""
REFERENCE_BLOCK = ("REFERENCE MATERIAL copied from elsewhere in the document (legends, codes, "
                   "per-entity details). Use it to interpret and complete the rows below; do not "
                   "return rows from it.\n--- REFERENCE ---\n{body}\n--- END REFERENCE ---\n\n")

# a page that shows rows but came back empty is asked once more, told what was counted
EMPTY_NUDGE = ("NOTE: an earlier reading of this text returned no entries, but the text "
               "contains about {n} table rows. Read it again and return every entry of "
               "\"{a}\" those rows contain. Return [] only if none of the rows belong to "
               "\"{a}\".\n")

# ---- the reader agent: the fields outside the lists, when the document is long ----
SCALARS = """Extract the document-level fields below from this document's text.

--- DOCUMENT TEXT ---
{text}
--- END TEXT ---

Fields to extract (ignore any array/table fields, they are handled separately):
{scalar_schema}

Reply with a JSON object only, using null for anything not present."""

# ---- column-flow reader: one column cut from a page image ----
COLUMN = """You will be shown ONE column cut from a page of a document whose pages are
printed as several independent columns of records. Read this column top to bottom.

{task}You are collecting the list called "{array_name}".
{array_desc}
Each entry of that list is one JSON object with this schema:
{item_schema}

Return every entry of "{array_name}" in this column, top to bottom, copying values exactly
as printed. Headings that are not entries (section, county, city or category titles) are
not entries. If the column STARTS with the continuation of an entry that began in the
previous column (its first line is missing), return that fragment first with "{lead}" set
to null."""

# ---- ruled-table reader: a header row stacked on a band of counted rows ----
RULED = """You will be shown an image cut from a scanned document: the header row of a
table followed by a band of data rows.

{task}You are collecting the list called "{array_name}".
{array_desc}
Each entry of that list is one JSON object with this schema:
{item_schema}

Return one entry for each data row below the header, top to bottom, copying each cell
exactly as printed. Rows that look identical are still separate rows. If a cell is blank
use null."""
RULED_TAIL = "This band is from page {page} and holds exactly {n} data rows; return exactly {n} entries."
