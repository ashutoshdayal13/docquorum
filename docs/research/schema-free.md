# Extraction without a schema: problem, scoring and related work

Research proposal, 2026-10-11. Nothing here has been run yet.

**Summary**

- **The task:** read a document once, with no schema and no question, and build a structured archive of everything it contains. Requests that arrive later (a schema to fill, or a question) are answered from the archive alone.
- **Scoring:** most of it can reuse existing benchmarks and their official scorers, with no new annotation. Hide the schema while the archive is built, then reveal it to an answering step that may only copy values out of the archive.
- **Prior work:** no benchmark found measures this exact setting on business documents. Recent ones cover parts of it: FormStruct-Bench (structure recovery on forms), ExStrucTiny (schema-free queries about one entity), EidosDoc (per-document structure built before any question).
- **Possible contribution:** a scoring protocol, datasets whose answer keys are complete by construction, and an archive builder made from DocQuorum's existing readers and checks.

## 1. The problem

**Extract once, with no schema and no question; answer requests that arrive later.**

- **Input:** one document, or a collection of documents. No schema, no question, no examples.
- **Output:** an archive, built once:
  - a JSON tree whose shape the system chooses: objects for sections and parties, lists of objects for repeated records (table rows, line items), and plain values at the ends ("leaves"). The system names the keys, usually after the printed label;
  - every leaf is text printed in the document, together with its page and box;
  - prose that is neither a field nor a table becomes short self-contained statements, each with its location.
- **Later:** requests the system never saw arrive. Each is either a target schema ("fill this") or a question. The answering step sees only the archive, never the document.
- **Goal:** answer those requests well. Every value must be traceable to the page, and the archive should stay close to the size of the document's own content.

**Rules that make the task well posed.** Without them, trivial archives score well.

1. **Copy only.** The answering step can only point to whole leaves, plus a fixed list of conversions shared by every system (parse a number or a date, strip a currency sign). It cannot read the document or write new text, so anything in an answer must already be in the archive.
2. **Rows stay whole.** Each record in an answer must come from one archive object, plus its parent objects for shared context such as an invoice header. If the archive scattered a line item's fields, the answering step cannot put them back together, so grouping is scored.
3. **One value per leaf.** A leaf holding a paragraph or a whole page cannot be used to supply a single value. This rules out an archive that is just the OCR text.
4. **Report the size.** Leaves per page, and archive length relative to the document's text. This rules out an archive that emits every possible phrase.

**Collection version.** Documents of the same kind must also use the same keys, so that questions across documents work (for example "total invoiced by vendor X in 2024").

## 2. Scoring a pipeline

The answering step uses one fixed model and one fixed prompt for every system compared, so that differences come from the archives.

| # | Measure | What it catches | How it is computed | New annotation |
|---|---|---|---|---|
| 1 | **Projected score** | total loss from not knowing the schema | freeze the archive; show a benchmark's schema to the answering step; score with that benchmark's own scorer. Report it next to the same pipeline's score when it is given the schema | none (ExtractBench, UNIKIE, VAREX, DocILE) |
| 2 | **Value recall** | values never extracted | share of answer-key values that appear as some leaf after the fixed conversions; no model involved | none |
| 3 | **Mapping ceiling** | errors made by the answering step | run the answering step on the answer key itself, reshaped like an archive (keys renamed, order shuffled). Its score is the most that measure 1 can reach | none |
| 4 | **Grounding precision** and **key precision** | invented values; wrong labels | value printed at its cited location: checked automatically from the text layer or OCR. Key describes the value correctly: a person checks about 200 sampled leaves per dataset | small sample |
| 5 | **QA retention** | information lost for questions | accuracy answering from the archive, divided by accuracy answering from the document, with the same answering model. Reported separately for lookup, table, aggregate and chart questions | none (MMLongBench-Doc, LongDocURL, FinanceBench) |
| 6 | **Cost** | — | cost of building the archive once, plus cost per request; and the number of requests after which building once is cheaper than extracting from the document for each request | none |

**Splitting the gap.** Measures 1–3 split the gap between the schema-given score and the projected score into three parts:
- values never extracted (measure 2);
- errors made by the answering step (measure 3);
- the remainder, which is grouping and naming.

This split shows where to work.

**Precision is the hard part.** An answer key never covers everything on a page, so an extra leaf cannot automatically be counted as wrong. Three partial answers:
- measure 4 catches invented values automatically;
- a small checked sample covers the keys;
- the datasets in section 3 have complete answer keys for some kinds of content, so precision can be computed exactly there.

**Scoring ideas taken from existing work**

- **BenchIE** (ACL 2022) scores open information extraction against clusters that list every acceptable phrasing of a fact, instead of word overlap. Under that scoring, leading systems did much worse than under CaRB's word-overlap scoring. "Same value, different key name" is the same problem.
- **Nugget scoring** (TREC QA 2003; AutoNuggetizer for the TREC 2024 RAG track) scores an answer by the share of atomic facts it contains. Automatic matching agreed with human assessors when ranking systems, but was stricter. Value recall (measure 2) is the same idea, with the answer-key values as the facts.
- **A 2025 study of information loss** in document conversion (41 slide decks, 468 questions, answered from Markdown conversions) is QA retention for unstructured output. Text and tables mostly survived conversion; for charts and images, accuracy fell as low as 8–17% in some setups.

## 3. Datasets whose answer keys are complete

Hand-made answer keys are never complete. Some documents, however, are generated from a structured record, and then the record is a complete answer key at no annotation cost.

- **SEC inline XBRL filings (10-K, 10-Q):** every number in the financial statements and notes is tagged with its concept, period, unit and dimensions.
  - FinTagging (2025) uses these filings to test tagging when the list of concepts is given.
  - The schema-free version asks whether the archive holds every tagged fact, with its period and label.
  - EDGAR access is already set up in this project.
- **SEC XML forms (Form 4, 13F, Form D):** the filed XML is the full record, and EDGAR shows a rendered view of it. 13F holdings are long lists of repeated records.
- **Tables:** PubTabNet and FinTabNet label every cell.
- **Forms:** KVP10k labels every key–value pair on 10,707 business-document pages; FUNSD does the same on 199 forms.
- **FormStruct-Bench** (2026): 7,000 synthetic table-form documents from 70 templates, with the full structure labelled.

Each set is complete for one kind of content only (tagged numbers, table cells, form pairs). Text outside that kind still needs the sampled check in measure 4.

## 4. Related work

| Work | What it covers | What is missing for this setting |
|---|---|---|
| **FormStruct-Bench** (Aug 2026) | recovers a form's multilevel structure with no schema; 14 systems; best document-level score 83.85%, fine-grained structure scores below 18% | single forms, synthetic; no later requests |
| **ExStrucTiny** (2026) | "on-demand" queries: find an entity's sub-fields without a schema; 110 multi-page documents, 304 queries; Gemini 2.5 Pro 79.5 ANLS | still driven by a query; small; data on request, research use only |
| **EidosDoc** (Sept 2026) | per-document structure built once, before any question; QA at 50× lower cost than the previous best | a learned vector encoding, not readable records; scored only by QA accuracy |
| **KVP10k** (ICDAR 2024), **FUNSD**, **BLOCKIE** (ACL 2025) | all key–value pairs on a page, with no preset keys; KVP10k scores by edit distance and box overlap | pairs only: no tables, records or hierarchy. KVP10k reports only encoder-model baselines (LayoutLM family) |
| **UNIKIE-BENCH open-category track** | unusual fields per document; Gemini-3-Pro 81.65, best open model 67.36 | each document still comes with its own template |
| **Evaporate** (VLDB 2024), **Structure then Query** (2026), **UDA-Bench**, ZenDB, DocETL, LOTUS, Palimpzest | tables built over a collection of documents, then queried | the schema comes from the question or the collection; mostly text-heavy documents |
| **DTBench**, **Doc2DB-Bench**, **AOE** | document to table or database | the schema is given, or built from the user's request (AOE: best model 28% cell F1) |
| **EDC** (EMNLP 2024), **AutoSchemaKG**, ZOES | knowledge graphs with schemas the system infers itself | text-only triples; no layout, tables or records |
| **StructRAG** (ICLR 2025), GraphRAG, **Dense X** (EMNLP 2024), **PDFTriage** | structure that helps answer questions | built per question, or never checked for completeness |
| MMLongBench-Doc, LongDocURL, UDA, FinanceBench | questions with answers over long documents | no way to tell "the archive lacked the fact" from "answering failed" |

**Verdict.** No benchmark was found for "no schema, no question, whole business document, scored on requests that come later". The closest are:
- FormStruct-Bench: structure recovery, but forms only;
- ExStrucTiny's on-demand queries: partly schema-free, but still driven by a query;
- EidosDoc: no question needed, but the output is not structured.

The search was broad but not exhaustive.

## 5. Proposed method: an archive builder from DocQuorum's parts

1. **Infer the structure from the page.** The existing geometry tools find column flows, ruled tables, repeated rows and side-by-side panels. Repeated structure becomes a list; "label: value" lines become fields; headings become objects. The model only names and groups what the geometry found.
2. **Extract under the inferred schema** with the existing reader agent (whole-document call, schema groups, page windows) and the existing deterministic checks (printed numbers, printed quotes, record counts).
3. **Check coverage against the page text.** This is the new step.
   - Every number, date, identifier, table cell and label–value line on a page must either be in the archive or be explicitly set aside as boilerplate.
   - Uncovered text triggers a targeted re-read of that region, and the schema grows.
   - This gives a stopping rule that needs no answer key. Counting against the page is the kind of signal that has worked in this project; about 22 attempts at having the model review its own output did not.
4. **Location on every value:** word boxes from the text layer, or block boxes from the MinerU parse. This also makes KVP10k scoring possible.
5. **Prose as short self-contained statements**, as in Dense X, so text that is neither a form nor a table is covered.
6. **Aligning keys across documents** of the same kind, so that the archive can answer questions over the whole collection.

**Answering from the archive.** Each question goes to a lookup (fields), a query (tables and aggregates) or retrieval (statements). When the archive lacks the fact, the step falls back to the page and logs the miss; the log is itself a completeness measurement.

**Baselines**

- For the projected score:
  - the same model asked once to "extract everything as JSON";
  - MinerU or Docling Markdown, with label–value lines and table cells split into leaves by a fixed rule;
  - EDC-style triples.
- For QA retention:
  - MinerU or Docling Markdown;
  - page retrieval;
  - a long-context model given the whole document;
  - per-question extraction (DocETL).

## 6. Where results could be strongest

| Target | Outlook |
|---|---|
| ExtractBench, VAREX or UNIKIE with the schema hidden | First result of its kind; the headline number is the gap to our own schema-given score, not a new rank |
| FormStruct-Bench fine-grained structure (best below 18%) | Page geometry is DocQuorum's strongest part |
| KVP10k | Only encoder-model baselines are published |
| AOE (best 28% cell F1) | Long financial reports; an archive plus the answering step may beat agents that read for each request |
| QA benchmarks | Likely gains on tables, numbers and questions across documents, and on cost; likely losses on charts, so the archive keeps page images as a fallback |
| UNIKIE open-category | Cheap to run with the existing UNIKIE code (only the data download is missing), but it supplies a template per document, so it is a side result |

## 7. Risks and rules

- The answering step must not be able to add information. The copy-only rule enforces this.
- "Everything" must be defined, or the task has no end. The coverage check and the size report do this.
- The archive can grow large; report its size.
- Schema-hidden scores will be lower than schema-given ones. They measure a gap, and the write-up must say so.
- No answer key in any method step. On ExtractBench the answering step gets the schema only, never the benchmark's `field_rules`, which contain answer-key values.
- Zero-shot with respect to output conventions: no rules fitted to one benchmark's answer conventions.

## 8. First experiments

1. **ExtractBench short split, schema hidden** (252 documents, about a week):
   - report value recall, projected score and mapping ceiling, against the schema-given 96.11 on that split;
   - this shows at once how big the gap is and where it comes from;
   - needs the vLLM server running.
2. **Coverage check as a predictor:** whether the share of page text left uncovered predicts value recall per document.
3. **XBRL pilot:** 20 10-K filings; value recall and precision on tagged facts.
4. **Archive QA pilot:** 20 MMLongBench-Doc documents, archive against page retrieval.

## Sources

- [FormStruct-Bench](https://arxiv.org/abs/2608.10396) · [ExStrucTiny](https://arxiv.org/abs/2602.12203) · [EidosDoc](https://arxiv.org/abs/2609.27784)
- [Information loss in document conversion (2025)](https://arxiv.org/abs/2508.15817)
- [BenchIE](https://arxiv.org/abs/2109.06850) · [AutoNuggetizer](https://arxiv.org/abs/2504.15068) · [TREC 2024 RAG nugget results](https://arxiv.org/abs/2411.09607)
- [FinTagging](https://arxiv.org/abs/2505.20650) · [EDC](https://arxiv.org/abs/2404.03868) · [ZOES](https://arxiv.org/abs/2506.04458)
- [KVP10k](https://arxiv.org/abs/2405.00505) · [BLOCKIE](https://aclanthology.org/2025.acl-long.844/) · [UNIKIE-BENCH](https://arxiv.org/abs/2602.07038)
- [Evaporate](https://www.vldb.org/pvldb/vol17/p92-arora.pdf) · [Structure then Query](https://arxiv.org/abs/2608.13384) · [UDA-Bench](https://arxiv.org/abs/2510.27119)
- [DTBench](https://arxiv.org/abs/2602.13812) · [Doc2DB-Bench](https://arxiv.org/abs/2608.08459) · [AOE](https://arxiv.org/abs/2507.16271)
- [StructRAG](https://arxiv.org/abs/2410.08815) · [Dense X Retrieval](https://arxiv.org/abs/2312.06648) · [PDFTriage](https://arxiv.org/abs/2309.08872)
- [UDA](https://arxiv.org/abs/2406.15187) · [ExtractBench](https://arxiv.org/abs/2607.29677) · [VAREX](https://arxiv.org/abs/2603.15118) · [DocILE](https://arxiv.org/abs/2302.05658)
