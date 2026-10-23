# ExtractBench — held-out test: Short 94.55, Medium 87.01; Long (development) 90.19. See sections 6-7.

_Paths in entries before 2026-10-23 refer to the repository's layout at the time; the stored results are now under `results/<benchmark>/<run>/` (see `results/README.md`), and removed scripts are in the git history._

**Latest standing (section 14, 2026-09-27 evening): ExtractBench Overall 95.25 (short 96.11, medium 94.03, long 90.41), 3rd of 45; UNIKIE-BENCH frozen 80.64 / tuned 82.37.** The title line above is the historical first result.

Qwen3-VL-8B + Qwen3-VL-30B-A3B + MinerU2.5 parser, three extraction views reconciled by
source-grounded arbitration and routed by a no-gold quality signal.
20 documents / 1,816 pages, scored with ExtractBench's own scorer (gold in => 1.0, verified).

## 0. Result

| configuration | mean Long F1 |
|---|---:|
| single-pass text, fixed partition | 65.85 |
| + agentic refine on `finish_reason` | 67.07 |
| + MinerU2.5 parser + 5 implementation fixes | 71.55 |
| + spacing reconciliation to the text layer | 71.84 |
| source-grounded arbitration across 3 views | 70.95 |
| + routing over the three views | 75.77 |
| + four defects found by reading the schema text (section 5) | **76.61** |
| best per-document choice among the three views | 78.08 |
| best open-weight entry on the leaderboard | 38.45 |
| Codex (GPT-5.6 Terra Evidence) | 77.36 |
| Codex GPT-5.5 | 78.88 |
| Claude Code, Opus 4.8 | 88.07 |
| Pulse (Effort), commercial | 93.51 |

**2.0x the best open-weight system**, and within 0.8 of a frontier coding agent.

The 75.77 row is the figure recorded when routing was first built; re-running the same
selection with the router in `route.py` gives 75.88, and 76.61 is that same selection with
the section-5 fixes applied to every view. The 75.77 / 75.88 difference is procedural, not
a result.

## 0-A. The mechanism: source-grounded arbitration

Views with disjoint failure modes (text layer / parsed structure / larger model) are aligned
record by record, and every field they disagree on is settled by a signal taken from the
DOCUMENT rather than from a model: prefer the candidate value that appears verbatim in the
page's own text.

Measured on 206,473 aligned field values:

| | |
|---|---|
| per-view field accuracy | text 35.0%, parse 38.8%, 30B 40.4% |
| oracle across the three views | **55.7%** |
| all views agree | 21.3% of fields |
| views disagree, at least one right | **34.4%** <- the exploitable share |
| no view right | 44.3% <- unreachable |
| arbitration by 2-of-3 **majority vote** | **52.0%** correct |
| arbitration by **verbatim presence** | **93.9%** correct, on 67% of disagreements |
| arbitration by model judgement | not attempted: five model-judgement verification layers failed earlier in this project |

**Majority voting is near-chance here, and that is itself a finding**: two of the three views
share the same 8B extractor, so their errors correlate. Ensembling assumes independence that
multi-view extraction pipelines do not have.

Arbitration is not a strict improvement -- it is a third view with its own profile. It wins
where views are complementary (gov_clin_0005 49.41 -> **86.16**, ofac +4.06, oklahoma +4.49,
ftx +3.85) and loses where one view was already excellent (sm0801_eco 91.65 -> 65.59). Hence
routing over all three rather than replacing them.

## 0-B. Seven implementation defects, and what they cost

 Implementation defects found and fixed (the largest source of gain)

| # | defect | effect |
|---|---|---|
| 1 | item schema truncated at 4,000 chars | cut the descriptions carrying "COLUMN 4 - VALUE"; two fields scored **0.0%** |
| 2 | `$defs` not passed to guided decoding | nested `voting_authority` ref dangled; model emitted **8 of 11** fields |
| 3 | `required` not forced | 4 arrays declare none, sm0801_ae declares 4 of 19; sf1449 emitted **4.0 and 4.6 of 8** fields |
| 4 | pages downsampled to 2.2M px before parsing | OCR garbage: `POBOX757`, `WAI KER DEBBIE`, `SITETATIDENDENES` |
| 5 | image-only PDFs report ~0 chars, so "not dense" | the documents most dependent on the parser got the worst renders |
| 6 | a re-parse raced a live run | contaminated one 30B measurement |

Fix 1+2 alone: 13F_0010 63.04 -> **88.68**, 13F_0026 66.54 -> **97.79**.

**Method note worth keeping.** Per-case F1 hid all of this for the whole project. Only
field-level instrumentation (`field_loss.py`) exposed 206,473 field values at 33.7% accuracy
with two fields at exactly 0.0%. Every ceiling estimate made before that measurement was
taken on broken plumbing.

## 0b. Scale does not help, and this survived a bug fix

Qwen3-VL-30B-A3B on the identical fixed pipeline: **67.39** against the 8B's 71.55. The
first 30B run (62.87) was invalid -- it predated the schema fix and emitted 8-field rows --
so it was rerun. The conclusion held:

| 30B better | 8B better |
|---|---|
| imedia_corrupted 64.31 -> 74.82 | dd1155_0012 88.57 -> **35.21** |
| ofac 74.44 -> 79.32 | dd1155_0011 96.00 -> 82.14 |
| ishares 64.15 -> 69.93 | eco_corrupted 90.15 -> 84.66 |
| oklahoma 11.03 -> 16.82 | sm0801_eco 91.66 -> 84.65 |

Scale improves dense-table reading and degrades small-subset precision. Per-case best of the
two models is higher than either, so capability-aware routing is a real lever; model size
alone is not.

## 0c. The reconciliation, and why the trigger had to be narrow

Oklahoma was caught between front ends: the text layer has verbatim characters but a
scrambled 6-column layout, the parse fixes the layout but its OCR drops spaces -- and the
scorer collapses whitespace *runs* while still failing on absent whitespace
(`POBOX757` != `PO BOX 757`). Snapping parsed values onto verbatim page text fixes it, but
the trigger matters:

| trigger | ofac rewrites | oklahoma repairs | mean |
|---|---:|---:|---:|
| alphanumeric key match | 10,472 | 3,993 | 70.43 |
| + skip already-verbatim values | 8,650 | 3,844 | 71.00 |
| + unique rendering only | 4,290 | 3,804 | 71.18 |
| **spacing differences only** | **13** | **2,663** | **71.84** |

Matching on content alone rewrote values that were already correct. Restricting the repair
to the one defect actually diagnosed keeps oklahoma's +5.40 and removes the collateral.

## 0d. Why 90+ is not reachable here

Four of twenty cases are already >=90 and four more are 84-89; the remaining twelve span
11-83 and each needs separate work (section localisation for the form cases, multi-array
schemas, perception on degraded scans, and oklahoma's layout-vs-verbatim bind). Fixing all
of them is worth roughly +12, giving ~85.

The decisive external evidence: **no frontier agentic system on this leaderboard reaches 90**.
Claude Code on Opus 4.8 scores 88.07 and seven frontier coding-agent configurations span
77-88. The 90+ tier is five purpose-built commercial extraction products (Pulse, Reducto,
LlamaExtract x2, Extend). An 8-30B open model exceeding all of them is not a tuning gap.

## 0b. What produced each jump

| change | gain | mechanism |
|---|---:|---|
| refine on `finish_reason == "length"` | +1.22 | 57 truncated chunks repaired on imedia (87.76 -> 97.12) |
| **schema fix** | large | item schema was truncated at 4000 chars, cutting exactly the descriptions of the three fields scoring 0.0%/0.0%/69.9%; `$defs` were not passed to guided decoding so a nested `voting_authority` ref dangled and the model emitted 8 of 11 fields. Fixing both: 13F_0026 66.54 -> **97.79**, 13F_0010 63.04 -> **88.68** |
| MinerU2.5 parser | mixed | HTML cells instead of whitespace columns: ftx_corrupted +14.68, ofac +14.34, dd1155_0011 +19.20; but over-extracts where text was already faithful (imedia -11.03, ftx -9.73) |
| output routing | +1.87 | pick the front end whose output fills more of the schema and repeats fewer rows; correct on 15/20 |

The routing rule uses no gold, but its *form* was chosen by inspecting these 20 cases, so it
needs validating on the short/medium splits (350 documents) before it counts as clean.

## 0c. Why 90+ is not reachable from here

Remaining losses are oklahoma 11.03 (26,725 records in a 6-column newspaper layout),
the constraint-following family (gov_clin, sf1449: the schema asks for a specific subset --
"the PRIMARY contract's Section B, NOT the latest amendment"), and credit_strategies /
ishares (multi-array schemas). Fixing all of them is worth roughly +12, giving ~85.

The last five points need what the 90+ tier has: parser ensembling with agreement voting,
evidence grounding as a hard constraint, and per-document-family handling. Scaling the
extractor does not help -- Qwen3-VL-30B-A3B scored **62.87** against the 8B's 67.07,
reading dense tables better and following schema constraints worse.

## 1. Headline

**Long-split value F1 = 65.85** (precision 73.91, recall 61.75).
That is **rank 15 of 45** on the Long column, and **1st of 21 open-weight entries**.

| | Long F1 | vs ours |
|---|---:|---:|
| Pulse (Effort), specialized | 93.51 | −27.66 |
| Reducto Deep Extract, specialized | 92.01 | −26.16 |
| LlamaExtract Agentic | 91.83 | −25.98 |
| Extend (Max Context), specialized | 90.46 | −24.61 |
| Claude Code (Opus 4.8), coding agent | 88.07 | −22.22 |
| Codex (GPT-5.5), coding agent | 78.88 | −13.03 |
| Codex (GPT-5.6 Terra Evidence) | 77.36 | −11.51 |
| **ours — Qwen3-VL-8B, page-chunked** | **65.85** | — |
| Extend Extract, specialized | 47.21 | **+18.64** |
| Datalab (Accurate + Balanced), specialized | 42.04 | **+23.81** |
| **Qwen3.8 27B — best open-weight** | **38.45** | **+27.40 (1.71x)** |
| Qwen3.6 35B, open-weight | 36.90 | +28.95 |
| OpenAI GPT-5.4 Nano | 35.81 | +30.04 |
| NuExtract3, open-weight | 32.71 | +33.14 |
| Google Gemini 3.5 Flash | 27.90 | +37.95 |

So: it beats **all 20 open-weight entries**, two specialized commercial configurations, and
every general commercial model on this split. It loses to the coding agents (77–88) and the
top specialized systems (89–94).

## 1b. The precision/recall signature is the evidence for the mechanism

| | P_Long | R_Long |
|---|---:|---:|
| Qwen3.8 27B (best open) | 92.29 | **33.00** |
| Qwen3.6 35B | 90.57 | 31.73 |
| NuExtract3 | 80.62 | 29.04 |
| **ours** | 73.91 | **61.75** |

Every open single-pass entry shows the same pattern: precision above 80–92 with recall near
30. What they return is right; most of the document never comes back. Ours trades ~18 points
of precision for **1.87x the recall**, which is exactly what exhaustive page-chunked coverage
should do and is the clearest evidence the mechanism does what it claims.

**A correction to earlier drafts of this file.** They cited Extend (Max Context) at 51.3 and
the best open model at 26.8, taken from a web summary of the paper rather than the
leaderboard. The real figures are 90.46 and 38.45: Extend (Max Context) is *not* beaten (the
47.21 entry is "Extend Extract", a different configuration), and the open-model margin is
+27.40 rather than +39.05.

## 2. Per case, and what the two fixes were worth

| case | first run | fixed | gold rows |
|---|---:|---:|---:|
| real_sm0801_eco_full | 96.79 | **97.02** | 951 |
| real_sm0801_eco_full_corrupted | 0.00 | **95.58** | 951 |
| real_ftx_full | 84.01 | **90.83** | 7,554 |
| real_imedia_full | 87.68 | **87.76** | 8,624 |
| dd1155_schedule_continuation_0012 | 80.00 | 80.00 | 5 |
| real_freer_register_full | 83.13 | 79.43 | 3,308 |
| dd1155_schedule_continuation_0011 | 76.80 | 76.80 | 20 |
| sf1449_supplies_services_0042 | 21.33 | **71.74** | 5 |
| real_sm0801_ae_full | 66.83 | 67.46 | 666 |
| sec_13f_0026_brown_brothers_harriman | 65.95 | 65.78 | 1,769 |
| sec_13f_0010_renaissance_technologies | 62.73 | 62.92 | 3,063 |
| sf1449_supplies_services_0059 | 3.46 | **60.08** | 70 |
| gov_clin_schedule_0005 | 50.39 | **60.00** | 13 |
| real_ofac_ssi_full | 57.67 | 58.94 | 1,238 |
| real_credit_strategies_full | 57.42 | 56.50 | 588 |
| real_ftx_full_corrupted | 0.00 | **54.83** | 7,554 |
| gov_clin_schedule_0031 | 40.94 | **50.23** | 23 |
| real_imedia_full_corrupted | 0.00 | **49.08** | 8,624 |
| real_ishares_iboxx_bond_etfs | 0.54 | **42.09** | 4,299 |
| real_oklahoma_unclaimed_2024 | 9.12 | 9.99 | 26,725 |
| **MEAN** | **47.24** | **65.85** | |

The +18.6 came from two omissions of mine, not from new ideas:

1. **The array's own name and description were never passed to the model** — only the item
   schema. The schemas state precisely what belongs in each list (*"only industries the
   report subtotals"*, *"every line item in the SCHEDULE OF SUPPLIES/SERVICES"*), and
   withholding that made the model return every table row it saw: 1,531 rows where gold
   wanted 70. Also `find_array_field` now picks the largest record type rather than
   whichever property came last.
2. **No fallback for image-only PDFs.** ExtractBench includes `_corrupted` variants as a
   perception axis; `pdftotext` returns one character per page for them, so the array pass
   saw nothing and three of twenty cases scored 0. They now render to page images and go
   through the VLM.

`real_sm0801_eco_full_corrupted` reaching 95.58 against its readable twin's 97.02 is the
useful check: same document, same content, so the fallback is genuinely reading it.

## 3. Remaining weaknesses

* **Image reading is markedly worse than text**: the two large `_corrupted` creditor lists
  land at 54.83 and 49.08 against 90.83 and 87.76 for the same documents as text.
* **`ishares` is capped at 42.09**: its schema has three arrays (`holdings`, `funds`,
  `industry_subtotals`) and the pipeline extracts one.
* **`real_oklahoma_unclaimed_2024` at 9.99 (6.6% recall on 26,725 rows)** is a real
  capability limit, not a bug — the densest document in the split.

## 4. What the ablation says about method

On `sec_13f_0010` (3,063 gold rows), with chunking held identical:

| variant | F1 | prec | recall | rows |
|---|---:|---:|---:|---:|
| **plain chunked** | **62.65** | 84.23 | 49.88 | 3,359 |
| + header lines carried into each chunk | 43.87 | 60.19 | 34.52 | 3,262 |
| + whole first page carried into each chunk | 37.75 | 45.72 | 32.14 | 3,999 |

Both additions hurt. The diagnosis behind them was correct — mid-document chunks see bare
rows, and `figi`/`put_call` are named in the header but blank in every row, so the model
slid each numeric value one column left (the precision-84 / recall-50 signature) — but
supplying the header did not repair it, and supplying the whole first page made the model
re-emit page 1's data rows in every chunk.

**This is the fourth measured instance in this project of an added reasoning layer losing
to the plain structural version** (coverage audit in `../multi_agent_test_6`, snapping on
top of the verbatim prompt in `../multi_agent_test_8`, and both variants here). The win
comes from decomposing the work so the failure cannot occur — here, one call per page
group so an output limit can never truncate the record list — not from a layer that
inspects or advises.

## 5. Caveats

* 20 documents. Per-case variance is large and a mean over 20 is not a tight number.
* The two systems above 90 are closed commercial products with no published method.
* Cost is not matched: this is 20–100 calls per document against whatever the published
  entries spend, which ExtractBench reports but this run does not yet measure.
* `real_oklahoma_unclaimed_2024` at 6% recall is a real capability limit, not a bug.

---

## 5. Five further defects, found by reading what the schema states

Every fix in this section is deterministic, needs no GPU, and reads only inputs the
benchmark supplies: the page text and the schema's own description strings. None of them
touches gold. Measured on the parse+snap view (`runs/final_snap4`), one fix at a time:

**Single view** (`runs/final_snap4`, parse + spacing reconciliation), one fix at a time:

| step | mean Long F1 |
|---|---:|
| previous best single view | 71.84 |
| + carry values down the rows they govern | 72.62 |
| + report the printed folio, not the PDF page index | 73.35 |
| + collapse rows in arrays the schema declares set-valued | 74.94 |

**Routed over three views** (text / parse+snap / arbitrated), same selector both rows, so
the two numbers differ only by the fixes:

| configuration | mean Long F1 |
|---|---:|
| original views | 75.88 |
| **all four fixes applied to every view** | **76.61** |

The routed gain (+0.73) is far smaller than the single-view gain (+3.10), and that is the
more interesting number: routing was already avoiding the views these defects damaged, so
per-view repairs largely bought what view selection had bought already. The fixes matter
most for a single-view pipeline, which is the cheap one to deploy -- one front end instead
of three.

Two controls on the routed figure. Substituting the 30B view for the arbitrated one in the
same router gives 73.88 before the fixes and 76.21 after, so neither number depends on the
particular third view. And the stacked-line assembly, which is worth a lot on the parse
view in isolation, moves the routed mean by **0.00** -- the router already picks the text
view for sm0801_ae, and that view emits one row per record and must not be folded.

Per document, the routed change is concentrated and includes one loss:

| document | before | after | delta |
|---|---:|---:|---:|
| ishares_iboxx_bond_etfs | 66.39 | 76.77 | +10.38 |
| credit_strategies_full | 59.95 | 64.28 | +4.33 |
| gov_clin_schedule_0031 | 56.96 | 59.45 | +2.49 |
| sm0801_eco_full | 96.78 | 97.47 | +0.69 |
| freer_register_full | 81.29 | 81.41 | +0.12 |
| sm0801_ae_full | 67.14 | 67.18 | +0.04 |
| **sm0801_eco_full_corrupted** | 95.45 | 92.04 | **-3.41** |

The regression is the cost of the mechanism: carrying a value down multiplies it across
every row it governs, so on a degraded scan a misread source occurrence becomes wrong on
all of them, and the changed identity fields also shift how rows align. It is the same
document as the +0.69 row, clean versus corrupted, which isolates the cause to scan
quality rather than to the rule.

### 5.1 Values that govern rows were not carried down

Ten fields across five documents state their own semantics: `check_number` is "printed
only on the check's first line — carry forward for continuation lines", `subject_id` is
"carried forward on continuation rows", `industry` is the "Industry heading the row sits
under". Gold repeats the value on every row it governs (`check_number` is filled on
3,308 of 3,308 gold rows); we emitted it only where the ink sits, leaving the rest null
or empty. Carrying it down recovers **10,249 values**.

The extractor also writes **4,859 empty strings** where it means "nothing here", so `""`
has to count as missing or the carry stops at the first one.

Identified from the description text, with one trap: a description may use the same words
about a COLUMN of the row ("COLUMN 5 — VALUE", "column '23. UNIT PRICE'"), which is a
per-row value and must never be carried. An explicit carry-forward statement is taken at
its word; a heading-shaped description is vetoed by per-row language.

A hierarchical variant, resetting an inner heading when an outer one changes, measured
72.61 against 72.62 — no effect, so the simpler rule stands.

### 5.2 The printed page number is not the PDF page index

Four documents say so outright:

> "This document's printed page numbering is offset from the PDF page index; report the
> number printed on the page, not the PDF page position."

We reported the index, so every value was wrong by a constant: **+7 on 99%** of
credit_strategies rows, **+2 on 96%** of ishares rows. The folio is in the parsed text as
the page's trailing standalone line ("CONSOLIDATED SCHEDULE OF INVESTMENTS" / "1"), so it
is read off and each page translated through its own printed number.

A map, not a single offset: credit_strategies numbers its schedule pages 1-19 at PDF
pages 8-26 while PDF page 30 prints 33, so no constant shift describes the document.

Measured against gold on key-matched rows: credit_strategies `source_page` **0.0% ->
99.2%**, ishares **3.6% -> 96.4%**.

**A correction to §0-B.** An earlier reading of this project had `source_page` at 53.4%
wrong across all views, 17,539 values, and called it the largest single failure. That was
an artefact of pairing predicted rows to gold on one identifying field, which repeats
across pages in these documents. Matched on a composite key of every non-page field,
`source_page` is **99.9-100% correct** on ftx, freer and oklahoma — it is right wherever
the row itself is right. Only the printed-folio translation above was ever a real defect.

Also measured and rejected: locating each row's page by its rare tokens in the parsed
text. It changed almost nothing where the model was already right and made sm0801_ae
worse (26.4% -> 16.4%), so the page the model names is kept and only translated.

### 5.3 Arrays that declare themselves set-valued were emitted as bags

`gov_clin_0005` has 13 gold rows, one per CLIN, and we emitted 29 — `item_no` '0007'
eight times — because each CLIN's funding sub-lines print as separate lines. Every extra
row is a false positive on all twelve fields, on a document worth 5% of the mean.

Whether the list is a set or a bag is stated in the ARRAY description, and only there:

| document | array text | gold |
|---|---|---|
| dd1155 | "DEDUPLICATED list ... EACH CLIN/SLIN APPEARS EXACTLY ONCE ... SET-VALUED FIELD KEYED BY item_number, NOT A BAG OF EVERY MENTION" | 20 distinct / 20 rows |
| gov_clin | "One entry per CLIN block where a fresh 'ITEM NO' header introduces a new identifier" | 13/13 and 23/23 |
| sf1449_0059 | "Ordered list of every line item **that appears**" | 9 distinct / 70 rows |
| ofac | "one record per entity NAME per directive section, so the same entity **appears multiple times**" | 1,172 / 1,238 |

The field descriptions do not carry this and must not be used: sf1449's `item_no` calls
itself "unique" while gold repeats it 61 times in 70 rows, so keying off the field text
would delete most of that document.

Two traps. A prohibition uses the same words — the 13F schemas say "Do NOT deduplicate
across pages or merge rows that look similar", and honouring that match cost 220 of 3,063
gold rows until the match was tested for a preceding negation. And which copy wins is
also stated, differently: dd1155 says "Update or merge into the first LineItem instead",
gov_clin says "use the LATEST printed values (the conformed state after all mods)".

Result: gov_clin_0005 29 -> 13 rows, exactly gold, F1 **79.25**; gov_clin_0031 30 -> 27.
On the 30B view the same rule takes dd1155_0011 from 25 to 20 rows, also exactly gold.

### 5.4 Records that print across stacked lines were emitted one row per line

The CSR adverse-event listing prints one record over three lines, and the schema says so:
`preferred_term` is "(second stacked line)", `system_organ_class` is "(third stacked
line)". We emitted a row per line, so 666 gold records came back as 1,172 rows with the
values filed under the wrong record:

```
gold   R1002  Irritability      onset 2009-03-22  resolved 2009-03-27  SOC 'General Dis...'
ours   R1002  Irritability      onset 2009-03-22  resolved UNK
       R1002  Irritability      onset 2009-03-27        <- this is the resolved date
       R1002  'General Dis...'                          <- the organ class, as an event
```

That is why `system_organ_class` was filled on 48% of our rows against 84% of gold's and
`resolved_time` on 5% against 86%: the values were read correctly and put in the wrong
place. Reading the line count and the per-line field from the schema and reassembling:
1,172 -> **705 rows** (gold 666), and fills move to `resolved_date` 18.4 -> 50.1%,
`resolved_time` 5.1 -> 38.7%, `serious` 63.9 -> 89.6%, `severity_code` 71.7 -> 90.4%.

### 5.5 The task description was never shown to the model

The schema's top-level `description` was not in the prompt at any call site. Fourteen of
the twenty documents carry one, **7,187 characters** of task statement, and the array
descriptions cross-refer to it — gov_clin's says "see DOC-SCOPE POLICY in the top-level
schema description", so the model was told to apply a policy it had never been given.

For sm0801_ae the withheld text is, in full:

> "Extract every adverse-event row from a CSR by-subject AE listing. The subject number
> and study product are printed only on the subject's first row — carry them forward.
> Coded columns print as code digits; decode them using the page footer legend. Subjects
> with no AEs print a single "NONE" row — include it with verbatim_term 'NONE' and null
> clinical fields."

Every failure measured on that document is named in that paragraph. This is the same
family as the truncated item schema and the missing `$defs`: the task was specified and
the specification was withheld. Fixed at both call sites; the re-run needs the GPU.

### 5.6 What is left, and what it needs

| document | F1 | cause | fixable without a re-run? |
|---|---:|---|---|
| oklahoma_unclaimed_2024 | 16.82 | OCR. 460 records/page, no text layer in the PDF; MinerU renders "RT 1 BOX 220" as "BT 1 ROY 320" and merges records into "RITBOX220JOHNSONJOH" | no — needs a better parser |
| sf1449_0059 | 55.99 | `unit`/`quantity` absent from all 62 rows; `required` was not forced when this run was made | no — re-run |
| ftx_corrupted | 69.23 | degraded scan | no |
| gov_clin_0031 | 73.27 | scope constraints ("EXCLUDE rows from the Shipment Information table") need applying at extraction time | no |

The `required` fix was verified by compiling the guided-decoding grammar offline: a row
missing `unit`/`quantity` is rejected outright. `runs/final_all` predates that fix by
seven hours, so the parse view — the strongest single view — has never run with it.

### 5.7 The repairs and the arbitration are order-dependent

Source-grounded arbitration settles a disagreement by preferring the candidate value that
appears **verbatim in the page text**. A carried-forward value is, by definition, not
printed on the row it governs -- that is the whole reason it has to be carried -- so the
arbitration rule deletes precisely the values section 5.1 restores:

| field | gold | after the repairs | after arbitration re-runs on the repaired views |
|---|---:|---:|---:|
| `vendor_number` (freer) | 100.0% | 100.0% | **41.3%** |
| `industry_group` (ishares) | 100.0% | 100.0% | **49.7%** |
| `industry_percent` (ishares) | 99.9% | 100.0% | 71.3% |
| `check_number` (freer) | 100.0% | 100.0% | 88.0% |
| `subject_number` (sm0801_eco) | 100.0% | 100.0% | 93.4% |

Arbitration over the repaired views therefore scores **67.62**, below the 70.95 it scored
over the raw ones, and routing that output gives 76.29 against 76.61.

So the order is fixed, and it is the opposite of the intuitive one: **arbitrate across the
raw views first, then apply the repairs to every view including the arbitrated one.** The
repairs add values the document does not print on that row, which is legitimate because
gold does the same, but it means any later step that checks a value against the page must
not run after them -- or must exempt the fields the schema marks as carried.

Best configuration, therefore:

```
extract 3 views  ->  arbitrate across the raw views  ->  headfill, pagefix, dedupe,
stackfold on each of the 4  ->  route by completeness minus duplicate rate     = 76.61
```

---

## 6. Session of 2026-09-25: 76.61 -> 84.35 (interim), and what moved it

All numbers are the official scorer on the 20-document long split. Every choice below
was made while looking at these 20 documents, so the split is now effectively a
development set; the numbers must be re-measured on the short and medium splits before
being claimed.

### 6.1 Defect 9: structured decoding was never on

vLLM 0.27.1 removed the `guided_json` request field and drops unknown fields silently, so
every run until today decoded unconstrained -- the `required` / `$defs` / `maxItems` fixes
of section 0-B never reached inference. Verified directly: with `guided_json` the model
wraps its reply in a markdown fence and omits required keys; with
`structured_outputs={"json": ...}` neither happens. `pipeline.ask` now uses the latter
(`EB_GUIDED=0` restores the old behaviour).

A/B on the six government forms, text view, task description on: identical to the
hundredth on five (at temperature 0 the grammar never intervenes when the free output is
already schema-valid), +6.2 on sf1449_0059 where it forced the missing keys.

### 6.2 The task description, and where it backfires

Passing the schema's top-level description (section 5.5), text view, before repairs:

| document | before | with task description |
|---|---:|---:|
| dd1155_0012 | 77.14 | 91.43 |
| sf1449_0042 | 73.91 | 84.78 |
| sf1449_0059 | 55.99 | 64.54 |
| gov_clin_0031 | 59.45 | 66.02 |
| dd1155_0011 | 92.80 | 96.80 |

sm0801_ae returned 646 records against 666 gold, where it had returned 1,172 (one per
printed line) -- the description states the record layout.

It backfires on ishares with the 8B: seven "Schedule of Investments (continued)" pages
came back with **zero** rows. Reproduced on one page: with the description the 8B returns
`[]` guided or not; without it, 82 rows. It misapplies the document-level "Only the
Schedules of Investments are in scope" at chunk level. Qwen3-VL-32B-FP8 with the same
prompt reads the page (80 rows before the output limit).

### 6.3 oklahoma: read the register one column at a time -- 20.92 -> 91.64

Seven independent alphabetical columns per page, no text layer. The parser emits one table
row per horizontal slice, interleaving seven people, and a whole page of small type at
once gives 'BT 1 ROY 320' for 'RT 1 BOX 220'. `okcols.py` finds the columns from the ink
(7 on every page checked); `okextract.py` sends each crop at native resolution and stamps
the page. 24,620 records against 26,725; precision 95.6, recall 88.0. Worth +3.54 on the
mean by itself. Chosen by the schema's own words ("seven-column newspaper flow ... column
reading order").

### 6.4 Scanned ruled tables: count rows from the rules, not from generation

ftx_corrupted and imedia_corrupted have no text layer. Two failure modes, neither of them
reading:
* the model falls into repetition loops on identical rows -- 143 consecutive
  'NAME ON FILE' on a page with 69 rows, in the parse view AND reading the image directly;
* the parser degenerates on some pages -- 441 repeats of a LaTeX fragment; a 327-row table
  invented where the page prints 74.

Three tools, chosen per page from the page's own evidence:
* `tabconv.py` -- when the parsed header maps onto the schema's field names, convert rows
  deterministically (cannot loop). Health check per page: row count within 0.5-1.6x the
  document median.
* `ruled.py` -- deskew (the angle that sharpens the row-ink profile), find the printed
  rules, count the rows between them: exact on 10 of 13 pages checked, off by 1-2 on the
  rest. A filled header band (imedia) must be recognised or the first data row is lost.
* `ruledview.py` -- bands of <= 12 rows, header row stacked on top, output constrained to
  exactly the counted number of items. A loop has nowhere to go.

| document | start | parse conversion + fallback | ruled reader, every page |
|---|---:|---:|---:|
| ftx_full_corrupted | 69.23 | 88.64 | **92.80** |
| imedia_full_corrupted | 64.31 | 76.95 | **87.34** |

Cell accuracy on ftx: ruled reader 95.7%, MinerU conversion ~84%.

### 6.5 Routing: two negative results

* **Arbitration now hurts.** Once views come from different pipeline versions, record-level
  merging made the arbitrated view the worst of three (mean 68.65 against 72.26 text,
  75.92 parse). Routing text + parse only: 83.73 against 82.91 with it. Removed.
* **Routing by verbatim grounding** (supported cells minus unsupported) scored 78.60 against
  82.91 for completeness-minus-duplicates. Withdrawn.

### 6.6 Interim result

| | mean |
|---|---:|
| start of session | 76.61 |
| interim (8B, task description, guided on re-run documents, layout readers) | **84.35** |

Remaining weakest: sf1449_0059 55.99, gov_clin_0031 66.02, sm0801_ae 68.41, ishares 69.79
(the empty-page regression), credit_strategies 70.74, ofac 74.47. Being re-run with
Qwen3-VL-32B-Instruct-FP8 (DeepGEMM disabled: its JIT needs nvcc >= 12.3).

### 6.7 Qwen3-VL-32B as the extractor

Global choice, made per front end over the ten weakest documents (not per document):

| view | 8B | 32B |
|---|---:|---:|
| text layer | 72.75 | **77.15** |
| parse | 72.77 | **75.84** |

Largest moves: freer text 82.02 -> 96.83, ofac parse 74.47 -> 87.82, ishares parse
76.77 -> 82.80, credit text 70.74 -> 77.85. Served FP8 with `VLLM_USE_DEEP_GEMM=0`
(DeepGEMM's JIT needs nvcc >= 12.3, which this environment lacks).

### 6.8 Consensus routing: 86.32 -> 87.72, ceiling 87.80

Per document, choose the candidate reading (32B text, 32B parse) that agrees most with the
other independent readings (the 8B text and parse views), agreement measured with the
benchmark's own scorer between two predictions. No gold, no tuned parameter. It picks the
better candidate on 16 of 17 routed documents -- including both sf1449 forms the
completeness selector got wrong (71.05 -> 89.13, 59.25 -> 63.76) -- and lands 0.08 below
routing every document to its best view by hand. Cost: it needs witness readings, i.e. a
second (cheaper) model over the same front ends.

### 6.9 Three failure modes found this round, each fixed generically

* **Panels glued by the parser.** On ishares pdf 40/45/48 MinerU returned the two
  side-by-side panel tables as one 6-column table ('Security | Par | Value | Security |
  Par | Value'); both 8B and 32B then returned no records for the page. `tablefix.py`
  splits a table whose header is one >= 3-cell sequence repeated k times. Fires on
  ishares and credit_strategies only.
* **Panels interleaved in the text layer.** `pdftotext -layout` puts both panels on every
  line. `textpanels.py` cuts every line of the page at the offsets where a repeated
  (>= 3-cell) header line starts its repetitions. Two before/after tables in gov_clin
  ('QUANTITY AMOUNT QUANTITY AMOUNT') repeat only two cells and are correctly left alone.
* **Borderline empty answers.** Under structured decoding "[]" is always valid and very
  short. ishares LQD pages came back empty inside a run yet returned ~75 rows when the
  identical request was sent alone: the model sits near the boundary and batch-level
  numeric noise tips it. A page whose measured evidence (row-like lines, or HTML table rows
  for a parse) is >= 5 rows but which yields nothing is now re-read once, told the
  measured count; "[]" remains allowed so an out-of-scope page can still be empty.

### 6.10 The column reader, made generic

`colflow.py` replaces the oklahoma-specific `okextract.py`: the document's own schema and
task text as the prompt, and a geometric trigger (>= 3 text columns of near-equal width,
width CV < 0.12) instead of schema wording. The trigger selects oklahoma and ofac among the
long documents and none of 45 sampled short/medium ones. On oklahoma (Qwen3-VL-32B) it
returns 433-469 records per page against gold's ~441-469.

`layout_stage.py` makes every reader decision from measured evidence for any split; on the
long split it reproduces all four special-reader choices (ruled: ftx/imedia corrupted,
completeness 1.00 / 0.99; column flow: oklahoma, ofac) without a document name or a schema
phrase.

---

## 7. Held-out evaluation (frozen pipeline, first test run)

### 7.1 Protocol
Document types = identical `data_schema` (71 types). Types with a long-split member are
"seen" and go to development; ~20% of the unseen types are added to development by a
fixed hash order (`runs/heldout_split.json`). Development: 57 short + 22 medium documents.
Test: 195 short + 76 medium documents in 49 types, run once with the configuration frozen
on development, never inspected per document before freezing.

Frozen configuration: Qwen3.8-27B-FP8; structured decoding; reasoning off; task
description in the prompt; planner = one whole-document call when input (<= 100k tokens,
page images when <= 12 pages, text otherwise) and output (<= 28k tokens) fit, chunked
agentic path otherwise; reading = text layer when the PDF has one, MinerU parse when not;
layout readers from measured evidence; schema-driven repairs (dedupe only on a named key).

### 7.2 Results (current scorer)

| split | development | **test (held out)** | benchmark's own one-shot code, same documents |
|---|---:|---:|---:|
| Short | 93.27 (57) | **94.55** (195) | 87.84 (dev) / **90.36** (test) |
| Medium | 93.36 (22) | **87.01** (76) | not runnable here (> 12 pages per request) |
| Long | 87.62 single model / 90.19 two-model ensemble (20, all development) | -- | leaderboard: 38.45 (older scorer) |

Short, same documents, same weights: **+4.19** over the benchmark's own pipeline
(better on 52 documents, worse on 34, tied on 85). Medium test is far below medium
development: the development medium set was dominated by one document type (11 GSA labour
schedules) whose spread-out evidence is exactly what whole-document mode fixes.

### 7.3 The leaderboard mixes scorer versions
The scoring rules changed on 2026-08-31 and 2026-09-11 (e.g. an omitted key is now a miss,
not an implicit null). Only 10 of 44 leaderboard rows were re-scored afterwards (the
LlamaExtract tiers, Pulse, the Codex/Claude Code "Evidence" pipelines); the other 34 --
including every open-weight model, Reducto, Extend, plain Claude Code and Codex -- are on
the older scorer. Evidence: Qwen3.8-27B's published Short is 94.68; the benchmark's own
code for that model scores ~89.8 on all 252 short documents under the current scorer.
Comparisons in this project are therefore made only against same-scorer rows, or against
baselines re-run and re-scored here.

### 7.4 Negative results this round
* Reasoning on for short forms (unconstrained, reasoning stripped): 93.20 vs 93.27 off.
* The long-list repairs misfired on short forms (dedupe keyed on a grouping field,
  35 rows -> 6); dedupe now requires a key named in the schema text.
* Whole-document mode on the five small-output long forms: +3.8 / +4.6 / +6.5 on three,
  -20 on dd1155_0012 -- useful as an extra reading for consensus, not as a replacement.

### 7.5 Consensus over several readings
Short development, three readings (text view, parse view, one-shot output): 93.27 ->
93.78 (beta=1) / **93.82** (beta=2). With the long-split result (two models: 87.62 ->
90.19), the next step is a second model's reading for short and medium, configuration to
be decided on development and applied to test once, as a second disclosed test run.

## 8. Session of 2026-09-27: four output defects, all found by reading the losses

All numbers are the benchmark's own scorer (`extract_unified_value_f1`, current version)
over every document of the split; the whole benchmark is the development set.

### 8.1 Large schemas integrated (defect 14 follow-up)
The schema-partitioned outputs replaced the truncated ones: medium 90.35 -> **92.73**
(14 documents 77.33 -> 93.99); short 94.62 -> 94.67 through the consensus (17 documents,
90.07 -> 90.87 alone; the consensus keeps less of it because its other two readings came
from the broken pipeline).

### 8.2 Defect 15: every PDF looked one page longer than it is
`page_texts` split pdftotext output on form feeds, and pdftotext ends every page with
one, so an n-page PDF gave n+1 pages. The parse-cache gate (>= 90% of pages parsed) then
failed for every document of 8 pages or fewer: on the short split the MinerU parse was
never used for 243 of 252 documents (all 94 scans among them). The "parse view" of §7.5
was therefore a second text/image reading, which is why readings A and B agree so often.
Fixed at the source; the true parse view is being run on all 252 short documents.

### 8.3 Defect 16: null-valued keys were omitted (`conform.py`)
Under structured decoding a non-required property may be left out, and Qwen3.8 leaves out
the ones whose answer is null -- as does the benchmark's own one-shot provider. The
current scorer counts an absent key as a missed value (§7.3), so a correct reading of a
Caterpillar spec sheet scored 67.14 (precision 100, recall 50.5). The final stage now
fills every absent property whose schema admits null. Short 94.67 -> **95.17**
(caterpillar x4 -> 99.5-100); medium and long unchanged. One document lost 1.9: a value
we missed now counts as a wrong null instead of an absent key.

### 8.4 Defect 17: template rows (`emptyrows.py`)
A W-14 prints a fixed casing grid (Surface / Intermediate / Long String / Liner / Other);
the schema says "Emit a row object only for rows that have at least one filled cell", yet
all five rows came back, three holding only the printed label. A row whose only filled
cell is its label, in an array that has rows with >= 3 filled cells, is dropped. Gold has
this pattern in 3 of ~107k rows. Short 95.17 -> **95.32** (six W-14s +3 to +11),
medium +0.02; two 990-PF subtotal rows that gold keeps were removed (-1.5 each).

### 8.5 Defect 18: printed page numbers translated twice (`pagegrid.py`)
`pagefix` assumed the model always reports the PDF index and translated every value
through the page's printed folio. With the task description in the prompt the model often
reports the printed number itself, as the schema asks, and the second translation
scrambled it (credit_strategies: 375 of 588 wrong, 19 printed pages collapsed onto 12).
`pagegrid` ignores the incoming value: each row is scored against each page by its rare
tokens (thousands separators removed, so share counts and values vote, not only names
that summary pages repeat), the best non-decreasing page sequence is found by dynamic
programming, and the page is reported as the schema asks. Folios are read as
"Page X of Y" or a lone footer number and smoothed over neighbours (a stray "2" in a table
cell, pages with no folio). Applied only where the schema asks for the printed number;
where it asks for the PDF index the model's own page was the better reading (ftx -0.65
when overridden).

| split | before | after | largest changes |
|---|---:|---:|---|
| long | 90.19 | **90.73** | credit_strategies +4.55, sm0801_eco +2.74 / +3.83, sm0801_ae -0.50 |
| medium | 92.75 | **92.88** | vg_divappr 95.83 -> 100, blackrock_schedule +5.04, fidelity +3.51 |
| short | 95.32 | 95.34 | clinton_property x2 +2.2 |

### 8.6 Losses left alone on purpose
* gov_clin_0031 (long, 68.54): the schema says to return a visible FOIA marker verbatim
  ("(b) (4)"); the page shows the marker in red over each redacted cell; gold has null.
* sm0801_ae (long, 77.53): legend decodes print "Probably Related"; gold stores
  PROBABLY_RELATED. The schema never states that format (only `severity` has an enum).
* Earnings decks (medium T2): numbers compare with `==`; gold keeps 90.457 where the
  model wrote 90.46, and the printed "19%" where the model computed 18.87 as the
  schema's formula says. Fitting these would be fitting the annotation, not the task.

### 8.7 Serving
The server was restarted at the configuration proven on 2026-09-26 (gpu util 0.74,
48 sequences, default batched tokens, 12-image profiling): KV cache 162k -> 609k tokens,
decoding ~250 -> ~530 tok/s with 16 documents in flight. The GPU hold was never released
to anyone else during the handoff.

### 8.8 The real parse view, and a consensus that can use it
With defect 15 fixed, the parse view was run on all 252 short documents (0 failures). Alone
it scores 94.50 against 94.87 for the primary reading, but it errs on different documents:
the per-document ceiling over (primary, parse, one-shot) is 96.37, against 95.66 with the
old second reading, which was the primary view read twice. Consensus (medoid, beta=2) over
the three readings, each through the output stages first: short **95.99** (95.34 before;
beta=1 is within 0.02). Adding the old second reading as a fourth input lowers it (96.05
-> 95.99, measured when 245 of the 252 parse readings were in): a duplicated view votes
twice.

### 8.9 Two more output defects
* **Rows copied across arrays (`xarray.py`).** pueblo's schema gives `batches` no
  description; the chunked reader filed each of 511 check lines under `batches` too (562
  rows for 51 subtotals). A row whose distinctive values all sit in one row of another
  array, with at least one value in a differently named field (check_number ->
  batch_number), is the same printed line read twice; an array is cleaned when most of its
  rows are such copies. Fires on no gold record in any split; pueblo 84.73 -> **99.91**.
* **Repeated records beyond what the page prints (`dupcap.py`).** ftx prints redacted
  creditors as identical 'NAME ON FILE' lines; the text layer's per-page count equals the
  gold row count on every page checked, while the readers wrote 131 on a page printing 35
  and 0 on its neighbour. Identical records are interchangeable, so only their per-page
  count can be wrong: keep up to the page's count, move the excess to an adjacent page
  that prints more than we have, drop the rest. ftx 84.47 -> **90.77**. It also trims the
  one-shot reading's repeated census tables (21 -> 3), which then wins one census
  document under beta=2 (98.78 -> 83.60): recall-weighted agreement favours the most
  complete reading, and a cleaned over-complete reading is still the most complete.

### 8.10 Standing (all 370 documents, current scorer)

| | Short | Medium | Long | **Overall** |
|---|---:|---:|---:|---:|
| start of session | 94.62 | 90.35 | 90.19 | 93.25 |
| now | **95.99** | **93.03** | **91.04** | **94.94** |
| LlamaExtract Agentic Plus / Pulse (Effort) | 96.94 / 96.46 | 94.45 / 95.01 | 90.18 / 93.51 | 95.91 / 95.91 |
| LlamaExtract Agentic | 96.04 | 92.11 | 91.83 | 94.77 |
| Codex (GPT-5.6 Sol Evidence) | 96.04 | 90.19 | 82.73 | 93.77 |

Rank 3 of the 11 same-scorer rows overall (and of all 45 rows), 3rd on medium, 3rd on
long among same-scorer rows, 5th on short. Open-weight models only, on one GPU: Qwen3.8-27B
(FP8) for every split, plus Qwen3-VL-32B (FP8) readings inside the long-split consensus
(the `i4` readings of §6.7-6.8) -- short and medium use the 27B model alone.
Caveat that matters for a paper: the whole benchmark was the development set in this
session (§7 holds the one frozen held-out run); the repairs in §8 are generic in form but
were found by reading these documents' losses, so generality has to be shown on a second
benchmark.

### 8.11 Quotes as printed (`typosnap.py`)
GSA schedules print "Bachelor’s" (U+2019); readers and OCR write "Bachelor's", and the
scorer compares characters (90 of 106 education values wrong on one schedule). A value
containing a quote is located in the page's whitespace-free text with quotes folded, and
only its quote characters take the page's -- never the page's spacing, because text layers
split words by kerning ("f rom"). Dashes were tried and rejected: gold keeps a plain
hyphen where several pages print an en dash or minus (short -0.03 net). Short +0.02,
medium +0.09 (gsa_0011 80.81 -> 89.28). Final: short 96.01, medium 93.12, long 91.04,
**Overall 94.97**.

### 8.12 One routing rule on every split
Medium had been assembled from a single reading. With the output stages applied to all
three medium readings (primary, alternate view, tiled scans), the same consensus as short
and long (medoid, beta=2) gives 93.37 against 93.12: 8 documents up, 2 down (sign test
p = 0.11; smfg +17.2, erie +11.0, transunion +10.0; the 1G1PC5 valuation -24.3). Long
gains fresh readings from the current pipeline on three documents (gov_clin_0005 93.08 ->
96.86 through the consensus). Both are ExtractBench assembly decisions taken after the
freeze; no code changed, and the UNIKIE arms of §10 are unaffected.
**Standing: short 96.01, medium 93.37, long 91.23, Overall 95.05 (95% CI [94.38, 95.69]);
P(above 95.91) = 0.003, P(above 94.77) = 0.80.**

## 9. How robust is 94.97?

### 9.1 Does each stage generalise beyond the document that motivated it?
Each output stage applied alone to the routed readings, scored only where it changed the
output; "other types" excludes every document sharing the motivating document's schema.

| stage | motivated by | total (pts, all splits) | other types | docs up / down (other types) |
|---|---|---:|---:|---|
| conform | caterpillar spec sheet | +164.8 | **+30.6** | 5 / 1 |
| emptyrows | W-14 casing grid | +21.4 | +0.5 | 1 / 1 |
| xarray | pueblo batches | +15.2 | 0.0 | -- |
| dupcap | ftx creditor matrix | +73.5 | **+67.2** | 1 / 0 (a census table) |
| pagegrid | credit_strategies | +27.7 | **+23.1** | 10 / 2 |
| typosnap | GSA schedule | +13.0 | +4.5 | 3 / 0 |

conform, dupcap and pagegrid carry most of their gain on document types they were not
designed on; emptyrows and xarray have, so far, only the evidence of the type that
motivated them and should be presented that way.

Paired sign tests over the documents a stage changed: conform 10 up / 1 down (p = 0.012);
pagegrid 11 / 2 (p = 0.023), and 10 / 2 on other types alone (p = 0.039) -- the one stage
with significant evidence of generalising. emptyrows 5 / 1, typosnap 4 / 0, dupcap 2 / 0,
xarray 1 / 0 touch too few documents to test. Most of this session's gain came from
pipeline-level changes rather than repairs: the real parse view plus consensus (short
+0.72) and schema partitioning (medium +2.38).

### 9.2 Sampling uncertainty
Documents resampled within each split, 10,000 draws: Overall **94.97, 95% CI [94.33,
95.61]**; short [95.33, 96.62], medium [91.43, 94.70], long [87.53, 93.97]. Share of draws
above: 95.91 (the two leaders) 0.1%; 94.77 (LlamaExtract Agentic) 73.5%; 93.77 (Codex Sol
Evidence) 100%. So "ahead of the Codex/Claude Code evidence pipelines" is robust; "3rd,
ahead of LlamaExtract Agentic" is inside the noise; "1st" is not within reach of this
configuration.

### 9.3 Dependence on a clean text layer
ExtractBench ships corrupted-text-layer twins of 38 documents. Mean twin gap: short -1.57
(23 pairs, worst -8.70), medium -4.54 (12 pairs, worst -18.21), long -2.49 (3 pairs).
Several stages (typosnap, dupcap, pagegrid's token votes) read the text layer; the parse
view and the consensus are what keep the corrupted twins within a few points.

### 9.4 What is still required before any "state of the art" claim
The whole benchmark was the development set for §8, and some rules were sanity-checked
against gold (e.g. the cross-array rule was tightened after it fired on a gold record).
The claim needs a frozen pipeline run once on data it has never seen: UNIKIE-BENCH (ACL
2026, official evaluator) and, ideally, a second multi-page benchmark with extraction schemas.

## 10. Held-out test on UNIKIE-BENCH (protocol fixed before any result was seen)

Written 2026-09-27 03:50 UTC, before any UNIKIE reading was scored.

* **Pipeline:** frozen as `FROZEN_2026-09-27.json` (79 code files hashed). No UNIKIE
  document or label was used to develop it; `unikie_eval.py` is input/output plumbing only.
* **Data and scorer:** all 11 constrained scenarios, 4,472 documents, the benchmark's own
  evaluator (`kie_evaluator.cal_f1_all`, micro-F1 per scenario, macro over scenarios).
* **Arms**, all on Qwen3.8-27B-FP8: (1) the benchmark's own one-shot protocol -- the
  controlled baseline; (2) the pipeline's whole-document call on the image; (3) the same
  call with the MinerU parse as text; (4) **the pipeline: consensus over (1)-(3), beta=2,
  agreement measured with the benchmark's evaluator, output conformed to the template.**
* **Primary result:** arm 4 vs arm 1, macro F1, plus per-scenario. Reported whatever it
  is, including if the pipeline loses. Arms 2-3 are reported as ablations.
* **Known asymmetry, stated in advance:** UNIKIE's evaluator scores null as the string
  "None", so every arm's output is conformed to the template (absent -> "") before scoring;
  the baseline arm gets the same treatment. The baseline is ALSO scored raw (the
  official post-processing only), which is the number comparable to the published table.
* No re-runs with changed prompts or settings after scoring; any later change is a new,
  separately reported run.

### 10.1 Result (run once, as specified above; nothing changed after scoring)

All 4,472 documents read in every arm, 0 failures. Benchmark's own evaluator.

| scenario | one-shot raw | one-shot conformed | image | parse | **pipeline** | Gemini-3-Pro | best published |
|---|---:|---:|---:|---:|---:|---:|---:|
| Accommodation | 78.57 | 78.57 | 78.57 | 80.00 | **80.36** | 81.43 | 81.43 |
| Administrative | 82.20 | 84.24 | 85.49 | 85.40 | **86.24** | 84.32 | 84.32 |
| Advertisement | 83.14 | 83.14 | 83.52 | 87.36 | **84.67** | 90.54 | 90.54 |
| Catering-Services | 86.55 | 86.36 | 76.82 | 76.77 | **80.33** | 83.54 | 86.45 |
| Commercial | 50.72 | 50.78 | 52.08 | 54.02 | **52.78** | 53.87 | 53.87 |
| Education | 85.25 | 85.25 | 83.80 | 79.96 | **84.94** | 80.71 | 87.44 |
| Medical-Services | 75.94 | 75.94 | 76.46 | 75.94 | **76.77** | 77.60 | 77.60 |
| Nutrition-Label | 87.99 | 88.02 | 86.93 | 88.26 | **88.96** | 92.47 | 92.47 |
| Postal-Label | 85.05 | 85.05 | 84.80 | 84.65 | **85.30** | 90.74 | 90.74 |
| Retail | 87.32 | 87.32 | 88.76 | 84.65 | **89.99** | 89.27 | 89.27 |
| Tax-Compliant | 80.17 | 80.27 | 81.75 | 81.33 | **82.09** | 81.54 | 81.54 |
| **macro** | 80.26 | 80.45 | 79.91 | 79.85 | **81.13** | **82.37** | |

* **Rank 2 of 16** against the paper's Table 4: behind Gemini-3-Pro (82.37), ahead of
  Qwen3-VL-Plus (80.20), every open model (best Qwen3-VL-8B 79.12), GPT-5, Claude Sonnet 4.5.
  Above every published system on 3 scenarios (Retail, Administrative, Tax-Compliant).
* **Against its own backbone** under the benchmark's protocol: +0.68 macro over the
  conformed one-shot (+0.87 over raw), better on 9 of 11 scenarios.
* **The consensus transfers**: 81.13 is above every single reading (best 80.45), even
  though two of the three readings share one prompt.
* **Failure found**: Catering -6.03. On receipts with item lists the pipeline's
  schema-guided prompt collapses the list into one field (all items and totals in one
  `nm` string) on 13 of 66 receipts (parse reading 10, one-shot 3). The benchmark's
  prompt says outright that a list template repeats per element; the pipeline's prompt
  relies on the JSON schema. Both pipeline readings share the prompt, so they share the
  failure and outvote the one-shot in the consensus.
* **Confound, stated plainly**: the pipeline's readings used its own image size
  (2.6 MP; MinerU parses at up to 9 MP), the one-shot arm and every published system the
  benchmark's 1.6 MP cap. Part of the +0.68 may be resolution; a comparison that can be
  claimed against Table 4 needs the pipeline rerun at the 1.6 MP cap (a separate run).
* What this does and does not test: UNIKIE documents are single images with no text
  layer, so it tests the readings, the consensus and output conformance -- not the
  multi-page mechanisms (planning, schema partitioning, page grounding, count
  grounding) that carried most of the ExtractBench gains.

### 10.2 Fair-resolution rerun (specified before it ran)
Identical to §10 except that every pipeline input respects the benchmark's cap of
1,605,632 pixels: the image reading's page image, and the image MinerU parses for the
parse reading (re-parsed at the cap). The one-shot arm already used the cap and is reused.
Consensus and scoring unchanged. This is the number that can be set against Table 4;
reported whatever it is.

Result (all 4,472 documents, 0 failures; one-shot arm reused from §10.1):

| scenario | one-shot conformed | image @1.6MP | parse @1.6MP | **pipeline @1.6MP** | vs one-shot | Gemini-3-Pro |
|---|---:|---:|---:|---:|---:|---:|
| Accommodation | 78.57 | 77.86 | 78.57 | **78.93** | +0.36 | 81.43 |
| Administrative | 84.24 | 85.04 | 84.37 | **85.57** | +1.33 | 84.32 |
| Advertisement | 83.14 | 83.52 | 84.67 | **83.91** | +0.77 | 90.54 |
| Catering-Services | 86.36 | 75.98 | 76.47 | **80.70** | -5.66 | 83.54 |
| Commercial | 50.78 | 51.23 | 53.36 | **51.86** | +1.08 | 53.87 |
| Education | 85.25 | 84.01 | 78.71 | **84.53** | -0.72 | 80.71 |
| Medical-Services | 75.94 | 76.25 | 76.77 | **76.56** | +0.62 | 77.60 |
| Nutrition-Label | 88.02 | 87.23 | 88.42 | **88.83** | +0.81 | 92.47 |
| Postal-Label | 85.05 | 84.95 | 84.55 | **85.15** | +0.10 | 90.74 |
| Retail | 87.32 | 88.40 | 84.51 | **89.63** | +2.31 | 89.27 |
| Tax-Compliant | 80.27 | 81.14 | 81.10 | **81.43** | +1.16 | 81.54 |
| **macro** | 80.45 (raw 80.26) | 79.60 | 79.23 | **80.64** | **+0.19** | **82.37** |

* **Rank 2 of 16 on equal input terms** (Gemini-3-Pro 82.37 first; then ours 80.64; the same
  backbone's one-shot 80.45 / raw 80.26; Qwen3-VL-Plus 80.20; best open 79.12). Above every
  published system on Retail and Administrative.
* **Resolution was most of §10.1's margin**: at the cap the pipeline's readings lose 0 to
  2.7 points per scenario, and the gain over the same backbone falls from +0.68 to +0.19
  (9 of 11 scenarios up, 2 down; sign test p = 0.065). The placement on this benchmark is
  mostly the backbone's; the pipeline adds a small, consistent gain except where its list
  handling fails (Catering -5.66).
* **Consensus still beats every single reading** (80.64 vs 80.45 / 79.60 / 79.23).
* Gap to the state of the art: 1.73 macro. Closing it would need the list fix (Catering
  alone is worth ~0.5 macro), readings that fail independently, and a perception gain on
  Postal / Nutrition / Advertisement (4-7 points behind Gemini) that the resolution cap
  does not allow. Any such work would be development on UNIKIE, so it would be reported on
  the test part of the fixed split (`runs/unikie_split.json`: 1,486 dev / 2,986 test,
  fixed by hash before this score was seen), separately from this frozen result.

## 11. Tuned attempt at UNIKIE #1 (development on the dev third only)

Goal set by the user: pass Gemini-3-Pro's 82.37 macro at the benchmark's 1.6 MP cap.
Protocol: every change is developed on `runs/unikie_split.json`'s dev third (1,486
documents); the final configuration runs once on the test two-thirds (2,986); results are
reported test-only and full-set and labelled TUNED, separately from the frozen §10.2.

### 11.1 Where the points are (dev, frozen consensus)
Field classes: exact 78.6%, content differs 13.8%, missing 1.4%, extra 1.6%, case-only
0.8%, punctuation-only 3.9%. Rendering errors concentrate in Commercial (12.0% of fields
punctuation-only; 177 of ~200 are a '$' the model prepends where the invoice prints none),
Postal-Label (7.6% case/punctuation: gold keeps 'PITTSBURGH', 'NeVADA') and Retail (4.6%:
printed upper-case addresses rewritten in title case).

Commercial is the column the benchmark paper singles out: every system collapses there
(Gemini-3-Pro 53.87 best; Qwen3-VL-8B 51.14 best open; GPT-5 45.94; Claude Sonnet 4.5
45.92). Ours at the cap: one-shot 50.72, frozen pipeline 51.86, parse reading alone 53.36.

### 11.2 Rejected on dev
* **Character-level snap to the MinerU text** (case and punctuation as the OCR renders
  them): consensus 81.87 -> 80.50; Retail, Postal, Nutrition, Administrative all fall. The
  OCR's rendering disagrees with the gold's conventions more often than the model's does.
* **Edge-symbol-only variant** (drop a leading/trailing symbol the page does not print):
  consensus 81.87 -> 81.77; Commercial +1.0 but Nutrition -1.4, Administrative -1.3.
* **Field-level vote instead of the medoid**: 81.83 vs 81.87.

Earlier evidence to respect (multi_agent_test_8): with Qwen3-VL-8B, a prompt instruction of
the same kind reached 55.51 on Commercial, but two paraphrases of it differed by 6.46 on
Commercial and 11.12 on Advertisement. Any gain from wording must be confirmed on test.

### 11.3 New readings (dev)
| dev macro | |
|---|---:|
| frozen consensus (image, parse, one-shot) | 81.87 |
| one-shot with the page's OCR text appended ("oneshot_text"), alone | 81.54 |
| consensus (image, oneshot_text, one-shot) | **82.23** |
| consensus (oneshot_text, one-shot, image, parse) | 82.27 |

Replacing the parse reading with an OCR-assisted one-shot gives the consensus two prompt
families instead of one pipeline prompt read twice; Catering's list collapse disappears
from the result (85.32 -> 89.30) without any list rule.

**Prompt rules are fragile** (list rule + "do not add a currency symbol or unit not printed
next to the value"): Commercial +2.72 / +3.59 (image / parse reading) -- the rule removes
exactly the diagnosed '$' error -- but Advertisement -3.37 / -10.11 and, in the image
reading, Catering 80.66 -> 47.52. Selecting rules per scenario would fit the benchmark's
own labels and is not done. A rule that fixes a systematic error helps only if most
readings carry it: when every other reading prepends the '$', the correct reading is the
odd one out and the consensus outvotes it.

**Second model (not run):** Qwen3-VL-32B readings would add model diversity, the lever
that moved ExtractBench long 87.62 -> 90.19. It requires swapping the served model under
the GPU hold, which awaits the user's approval. Projection with the 27B model alone:
about 81 on the full set, ~1.4 short of Gemini-3-Pro.

### 11.4 Second model (user-approved swap to Qwen3-VL-32B, proven config)
The served model was swapped 27B -> Qwen3-VL-32B-FP8 under the GPU hold (util 0.90, 32k,
2 images per request: the 30 three-page Commercial invoices get no 32B reading). Alone the
32B is slightly weaker than the 27B (one-shot, dev: Commercial -3.5, Accommodation -2.2,
Administrative -1.8), but its errors differ, which is what the consensus needs:

| dev macro | |
|---|---:|
| frozen consensus (27B: image, parse, one-shot) | 81.87 |
| 27B: image, oneshot_text, one-shot, parse | 82.34 |
| **+ 32B: one-shot, oneshot_text (6 readings)** | **82.99** |
| the same six, other tie-break orders | 82.72 |
| without the 27B parse reading (5) | 82.41 |

The six-reading consensus improves 7 of 11 dev scenarios over the 27B-only four. The
tie-break order is fixed as listed (pipeline image reading first), chosen on dev.

### 11.5 Tuned configuration, frozen before any test score was seen
Chosen on dev (best of ~15 configurations compared; differences below ~0.3 are within the
noise of an 11-scenario macro whose smallest scenario has 13 dev documents):

**medoid (beta = 2) over six readings from three open models, in this tie-break order:**
27B pipeline image reading, 27B one-shot + OCR text, 27B one-shot, 27B pipeline parse
reading, 32B one-shot, 8B one-shot (the earlier multi_agent_test_8 official-protocol run).
All inputs at the benchmark's 1.6 MP cap; output conformed to the template. Dev macro
83.29 (frozen §10.2 configuration on dev: 81.87). The next step is ONE run of exactly
this configuration on the 2,986 test documents, reported test-only and full-set.

### 11.6 Result of the one test run (TUNED; reported as run)

| macro, 1.6 MP cap | test (2,986 documents, never tuned on) | full set (4,472) |
|---|---:|---:|
| 27B official one-shot | 79.94 | 80.45 |
| frozen pipeline (§10.2) | 80.01 | 80.64 |
| **tuned pipeline (§11.5)** | **81.89** | **82.37** |
| Gemini-3-Pro (paper, full set only) | -- | 82.37 |

Per scenario, full set: Accommodation 79.64, Administrative 86.73, Advertisement 86.21,
Catering 87.62, Commercial 53.34, Education 85.77, Medical 77.50, Nutrition 90.81,
Postal 85.65, Retail 90.71, Tax-Compliant 82.10. Above every published system on 4 of 11
scenarios (Administrative, Catering, Retail, Tax-Compliant).

* **A tie with the best published system, not a win**: 82.3717 against Gemini-3-Pro's
  82.3664 recomputed from its eleven published (two-decimal) per-scenario values -- a gap
  smaller than the table's own rounding.
* **The tuning generalised**: +1.88 over the frozen pipeline on the untouched test
  documents, more than on the dev documents it was chosen on (+1.42). The full-set number
  still contains the dev third; test-only 81.89 is the unbiased estimate (the paper gives
  no test-only figure for Gemini).
* **What it is**: a consensus over three open models (Qwen3.8-27B, Qwen3-VL-32B,
  Qwen3-VL-8B) plus a MinerU parse, all at the benchmark's input cap -- not a single model.
  The gain came from diversity of readings (a second prompt family, then second and third
  models); prompt rules and OCR-based rendering repairs were measured and rejected.

## 12. A second model on ExtractBench short (in progress)
Qwen3-VL-32B (proven config: 32k context, 2 images per request) read the short split in
the text and parse views as extra consensus inputs. Interim, on the 121 documents with both
readings: 32B readings alone 87.27 (text) / 86.47 (parse) against ~95 for the 27B readings;
five-reading consensus 96.13 against 95.99 for the current three (+0.14). On multi-page,
schema-driven extraction under a 32k/2-image limit the 32B is ~8 points weaker, so model
diversity buys far less here than on UNIKIE (+1.9 on test). Medium was not read with the
32B: its documents overflow the 32k context in the scalar call, which would make the
readings weaker still.

## 13. CORRECTION (2026-09-27): gold leaked into the ExtractBench consensus

**What was wrong.** The consensus (`medoidroute.agree`) measured agreement between two
readings with `ebscore.score(record, ...)`, passing the full benchmark record. ExtractBench's
`field_rules` carry evidence entries whose `value` is the gold value, and the scorer accepts a
prediction that matches the expected value OR any evidence value. So a reading that matched
the gold earned extra "agreement" and was preferentially chosen. Found when the new
single-document entry point (no benchmark record) chose differently from the benchmark path on
identical readings.

**Invalid results:** every ExtractBench number produced through the consensus -- §6.8,
§7.5, §8.8, §8.10, §8.12, §9.2, §12 and the ExtractBench standings quoted in chat
(Overall 94.94 / 95.05, "#3"). The per-stage deltas of §9.1 are valid as measured deltas,
but their base was the leaked routing.
**Not affected:** every single-reading result; the frozen held-out ExtractBench run of §7
(single reading, short test 94.55); all of UNIKIE (§10-11: its consensus uses only the
UNIKIE evaluator's generic normalisation, never gold); the layout-reader decisions (audited:
document evidence and the schema only).

**Clean results** (agreement from the schema only; `field_rules` and `repeated_structure`
removed):

| ExtractBench | primary reading alone | clean consensus |
|---|---:|---:|
| short | 95.00 | 94.97 |
| medium | 93.12 | 92.97 |
| long (with the oklahoma column-reader override) | **89.36** | 87.32 |

Consensus helps only when the readings are of comparable quality. On UNIKIE's single images
they are (frozen consensus 80.64 vs best single reading 80.45; three models 82.37 tuned). On
ExtractBench's long PDFs the agentic primary reading dominates (long: 86.29 vs 77-79 for the
others before overrides) and the medoid drags the result toward weaker readings. Normalising
strings in the agreement (case, punctuation, dates) does not change this (short 94.94).

**Configuration adopted (one rule for both benchmarks):** consensus over the readings for
documents that fit one call (UNIKIE; ExtractBench short), the agentic primary reading alone
otherwise (ExtractBench medium, long).

| ExtractBench, clean | score | rank (same-scorer rows) |
|---|---:|---|
| short | 94.97 | 7 of 11 |
| medium | 93.12 | 3 of 11 |
| long | 89.36 | 4 of 11 |
| **Overall** | **94.17** (95% CI 93.48-94.85) | **4 of 11**, also 4 of 45 |

P(bootstrap Overall above LlamaExtract Agentic's 94.77) = 0.04; above Codex Sol Evidence's
93.77 = 0.87.

## 14. Session of 2026-09-27, evening: ExtractBench 94.18 -> 95.04

Every number: the benchmark's own scorer, all documents of the split, no annotation used in
any method step (consensus agreement from the schema alone, §13). As in §8, the whole
benchmark is the development set.

### 14.1 Where the loss was
The scorer was instrumented (`Scorer._score_cell`, `Scorer._count_subtree`) to attribute the
5.82 lost Overall points to cell outcomes:

| error kind | Overall pts |
|---|---:|
| null where the gold has a value | 1.08 |
| wrong content | 1.00 |
| value too long / too short | 0.73 |
| rendering only (case, punctuation, spacing) | 0.73 |
| extra rows | 0.60 |
| different number | 0.59 |
| value where the gold is null | 0.53 |
| missing rows | 0.50 |

No single field is worth more than 0.13. Several of the largest items are the annotation
contradicting its own schema, left alone: a masked SSN the schema says to return as
'XXX-XX-XXXX' is 'XXX-XX-XXXXX' in the gold (20 documents); margins the schema says to round
to 2 decimals are rounded to 1; a check amount the schema says to print with '$' is stored
without it (451 cells); an equipment list the schema asks for is empty in every gold record of
the valuation reports.

### 14.2 What worked (short split, each on top of the previous)

| change | short | how it was found |
|---|---:|---|
| stored clean configuration (§13) | 94.97 | |
| numbers as printed (`numsnap.py`) | 95.06 | decks: 26.11 written for a printed 26,107 thousand |
| text-layer PDFs keep the primary reading; the quorum only for scans | 95.14 | census table 98.5 alone, 68.0 in the quorum |
| page images at 220 dpi, <= 5 MP (was 150 dpi, 2.6 MP) | 95.57 | misread handwriting and check boxes on scans |
| OCR layers labelled as OCR; tax-return scans reach the schema split | 95.71 | "550000" for 55.0000 shares in an OCR layer |
| schema keys left out -> re-read with every key required | 95.82 | a labelled requisition number returned as a missing key |
| an empty list written as the schema's declared default (null) | 95.98 | 225 cells of `[]` vs null on one customs form |

Resolution, paired on the primary reading (225 documents): +0.62 (80 up / 38 down, sign test
p < 0.001); by the benchmark's perception tags: scanned or handwritten (P2/P3) +0.86,
rotated / image-only (P1) +2.3, neither +0.06. The key-skip re-read fires
on 15 of 252 documents: +2.25 each (7 up / 1 down). The OCR wording, on the 84 OCR-layer
documents: +0.25 (two broker statements +10 each; four documents -2 to -4). The tax returns:
arif-2021 90.2 -> 97.6, arif-2022 89.6 -> 97.1, arif-2024 88.5 -> 97.6, bianco-2024
85.2 -> 96.6 (their scans never reached the schema split, which required a text layer).

Medium: numbers as printed 93.12 -> 93.57 (byline 64.3 -> 85.7, crh 78.3 -> 87.0, a Q4 press release 71.4 -> 85.7); the
other changes do not reach medium documents (> 12 pages: no per-page images).
Long: the page-geometry layout readers, re-run with the current 27B model on the documents they
select (they had been left out when the long split became 27B-only), 89.44 -> **90.36**:
ftx_corrupted 87.87 -> 95.36 and imedia_corrupted 83.74 -> 92.67 (ruled tables),
ofac 87.00 -> 89.00 (column flow); oklahoma keeps its 27B column-flow reading (98.23).

### 14.3 Negative results
* Fresh primary reading, same code: 94.88 vs 95.00 stored. Run-to-run noise: 61 of 251
  documents change, mean |change| 0.76 points.
* Field-level vote over four readings: 95.01 / 95.00 vs 95.02 for the primary alone.
* Filling the primary's nulls from the other readings (1 or 2 agreeing): 95.01 / 95.00. On
  the Oklahoma purchase order all four readings miss the same three labelled fields.
* Abstaining on values the text layer does not support: 2,041 correct values are unsupported
  against 23 wrong ones -- rejected without a run.
* Page tiles for 13-24-page medium documents with a text layer: 9 up, 9 down.
* Reasoning on (unconstrained JSON after the reasoning, 220 dpi), 39 random short documents:
  +0.01 once a planner difference is removed, with +37 on one census table and -47 on one
  well form (an empty object), at 2-3x the time. The §7.4 result (57 documents, -0.07) stands.
* The quorum on scans, with the 220-dpi readings: 95.82 vs 95.83 for the primary alone and
  95.90 for a two-reading quorum -- within noise; the three-reading quorum is kept because it
  is the configuration UNIKIE's images use.

### 14.4 The OCR label on UNIKIE (held out from its development)
The UNIKIE parse reading shows the MinerU text as "the document's text layer (exact
characters)". Relabelled as machine-read OCR, with the image deciding (reading `parse_ocr`,
dev split, 1,486 images): the parse reading alone 80.50 -> **80.96** (Commercial +2.1,
Education +2.3), so the fix transfers. The quorum absorbs it: frozen three-reading quorum
81.87 -> 81.93, tuned six-reading quorum 83.30 -> 83.29. Neither UNIKIE configuration changes
(dev decides; the test split was not run).

### 14.5 Standing
| ExtractBench | score | rank (11 same-scorer rows / all 45) |
|---|---:|---|
| short | 95.98 | 5 / 7 |
| medium | 93.57 | 3 / 3 |
| long | 90.36 | 3 / 5 (above LlamaExtract Agentic Plus, 90.18) |
| **Overall** | **95.04** (95% CI 94.41-95.63) | **3 / 3** |

P(bootstrap Overall above LlamaExtract Agentic's 94.77) = 0.81; above the leaders' 95.91 =
0.002. The final outputs, their scores and the reading behind each one are in DocQuorum's
`results/extractbench/` (`provenance.json`); the previous version is in `previous_94.18/`.

Also this round: the UNIKIE Commercial scenario, where every published system scores 46-54,
was examined (dev split only). Its answer key strips the currency symbol from every amount
(0 of 1,579) although the invoices print it; Advertisement keeps it (56 of 61); no template has
a currency field. A Commercial-only rule would add ~+1.0 macro on dev but is fitting one
scenario's labels, so it was not adopted (decided with the user: the headline stays
zero-shot with respect to output conventions).

### 14.6 Later the same night: three more fixes, each read off the schema or the page
* **Blank check boxes (`boolblank.py`).** The well forms describe every check box as
  "Boolean: true only if this box is marked/checked on the scan, false if left blank"; the
  reader returned null for the blank ones (16-24 per W-2 form). A null boolean becomes false
  where the field's own description says so (and gives null no meaning of its own).
  Short 95.98 -> 96.03 (4 up, 0 down).
* **Blank lines.** A form's pre-printed empty lines came back as records ({name: null,
  amt: "0", id: null}; the schema says "one object per FILLED row"), and the carry-down
  repair then copied a gatherer name into them. Rows with no printed content (every value
  null or zero) are dropped, and the carry-down never fills an otherwise blank row.
  Short 96.03 -> 96.11 (3 up, 0 down); medium and long unchanged.
* **Page windows for long scans read by the schema split.** A 25-38-page tax-return scan was
  read from its MinerU parse alone (no page images beyond 12 pages), and the parse held the
  form's labels without the typed entries (page 1 of bar-lev-2022: no address, no income
  lines). Each schema group is now read in windows of <= 8 pages, each call with that
  window's page images (220 dpi) and OCR text, and the windows' values are merged (a value
  found fills an empty one; the longer list is kept). 14 medium tax-return scans: 12 up, 1 down (-0.27), +45 document-points; medium 93.57 ->
  **94.03**. Also, for consistency with the rule, the long split's one scan without a layout
  reader now uses its parse reading (97.27 -> 98.26): long 90.36 -> 90.41.

**Standing after 14.6: ExtractBench Overall 95.25 (95% CI 94.64-95.85; short 96.11, medium
94.03, long 90.41), 3rd of 45 and 3rd on every split among the 11 same-scorer rows.
P(above 94.77) = 0.94, P(above 95.91) = 0.014.**

Tried and not adopted: page images for the chunked reading of long scans (the three candidates
all took the whole-document path); re-asking fields returned null (at most 13% of our nulls
are wrong, by schema size); a shape-based count of printed identifiers (mostly false alarms).

### 14.7 Pushing further: what did not move
* **Sharper pages (300 dpi, <= 7.5 MP, 60 MP per call).** On 68 scanned short documents against
  the 220-dpi reading: +0.07, 12 up / 12 down. Resolution has saturated at 220 dpi.
* **Reasoning on, with the outliers set aside.** The 39-document test is +0.27 without its two
  extremes (+37 on a census table, -47 from an all-null reply), about +0.6 on image-only scans
  and ~0 elsewhere, at 2-3x the time -- not adopted.
* **The quorum on ExtractBench scans** is now neutral: the primary reading alone scores 96.12 on
  short against 96.11 with the quorum. It is kept because it is the configuration UNIKIE's
  images use (where it adds +0.2 frozen and +1.9 tuned).
* **UNIKIE Nutrition-Label field codes** (CE-P1, CE-PS, ...) come from the source dataset and
  are not defined anywhere in the benchmark's protocol; giving the model their meaning would be
  scenario-specific outside knowledge the published systems did not get -- not done.

What remains after §14 is, by the error analysis of §14.1, largely annotation conventions (which
we do not fit), handwriting misreads on scans, and one-off semantic slips (a wide single-audit
table read with its columns shifted). No further generic fix has been found.

---

_The section below was the repository's RESULTS_README.md until 2026-10-23: an earlier experiment with an 8B model, superseded by the 27B results in the top-level README. Its scripts and run folders are in the git history (before commit of 2026-10-23); the paths it names refer to that layout._

## Earlier: additional benchmark experiments with an 8B model (superseded)

<!-- completed-results:start -->
## Completed full-cohort results

These results cover every task in their stated cohort. Reference ranks compare published scores; no external leaderboard submission has been accepted. Stored-output and development results are labelled explicitly.

| Benchmark | Configuration / measurement | Tasks | Score (%) | Reference rank | Gap to leader (pp) |
|---|---|---:|---:|---|---:|
| run-llama ExtractBench | [Stored primary, current public annotations](results/multibench/extractbench_current_reference.json) | 370 | **95.4278** | 3 | 0.4822 |
| run-llama ExtractBench | [Archived incremental repair development](results/multibench/extractbench_archived_candidate.json) | 370 | **95.6430** | 3 | 0.2670 |
| UNIKIE constrained-category | [Original 3 readings; stored-output re-score](results/multibench/unikie_audit.json) | 4472 | **80.6450** | 2 | 1.7250 |
| UNIKIE constrained-category | [Development 4 readings; stored-output re-score](results/multibench/unikie_audit.json) | 4472 | **81.3175** | 2 | 1.0525 |
| UNIKIE constrained-category | [Tuned 6 readings; stored-output re-score](results/multibench/unikie_audit.json) | 4472 | **82.3746** | 1 (displayed tie) | 0.0000 |
| DocuBench v0.2.0 | [DocQuorum8B-bounded-v1](results/multibench/docubench/summary.json) | 72 | **63.8574** | 11 | 33.1596 |
| DocuBench v0.2.0 | [DocQuorum8B-bounded-v4](results/multibench/docubench_v4/summary.json) | 72 | **70.3995** | 10 | 26.6175 |
| DocuBench v0.2.0 | [DocQuorum8B-bounded-v6](results/multibench/docubench_v6/summary.json) | 72 | **74.7936** | 8 | 22.2234 |
| VAREX image_only | [8B official](results/multibench/varex/scores/full/summary.json) | 1777 | **96.9503** | 3 | 1.0497 |
| VAREX image_only | [8B whole](results/multibench/varex/scores/full/summary.json) | 1777 | **97.4530** | 2 | 0.5470 |
| VAREX image_only | [8B guided](results/multibench/varex/scores/full/summary.json) | 1777 | **97.6807** | 2 | 0.3193 |
| VAREX image_only | [8B quorum](results/multibench/varex/scores/full/summary.json) | 1777 | **96.9503** | 3 | 1.0497 |
| VAREX image_only | [8B repaired quorum; stored-output development](results/multibench/varex_selector_v2/scores/full/summary.json) | 1777 | **97.7898** | 2 | 0.2102 |
| LongArray-Extract | [DocQuorum8B-bounded-v4](results/multibench/longarray_v4/scores/full/summary.json) | 45 | **66.8972** | 6 | 32.3028 |

Pilots, selected routing checks and incomplete runs remain below in the experiment notes. They receive no full-cohort rank. This table refreshes and is committed/pushed whenever a complete score changes.
<!-- completed-results:end -->

Branch: `experiment/multibench-20261002`, based on `fb69fc4eab65ec690c892e36e43f7a3c53936693`. Checked 2 October 2026. Work remains in progress. No result here has been submitted to an external leaderboard.

The strongest current evidence is the existing UNIKIE evaluation: the original three-reading configuration re-scores to **80.6450** across all 4,472 constrained-category documents, above the paper's third-place 79.12. The separately tuned six-reading configuration re-scores to **82.3746**, tying the displayed leader, 82.37. It must not replace the original held-out result. The added four-reading configuration scores 81.3175 and is also development work. [Primary paper, Table 4](https://arxiv.org/html/2602.07038v2); [full coverage audit](results/multibench/unikie_audit.json).

## Benchmarks and targets

Scores within each row use that benchmark's metric; percentages across rows are not interchangeable. Published commercial benchmark results are reference comparisons, rather than our own paired re-runs of those providers.

| Benchmark and scope | Metric | Published leader | Published third | DocQuorum evidence | Status |
|---|---|---:|---:|---|---|
| [run-llama ExtractBench](https://github.com/run-llama/ExtractBench), 370 documents | Mean document unified value F1 | 95.91, LlamaExtract Agentic Plus / Pulse Effort | 94.77, LlamaExtract Agentic | Stored primary: **95.4278** on current public annotations | Estimated reference rank 3; development result, no official submission |
| [UNIKIE](https://arxiv.org/html/2602.07038v2), 4,472 constrained-category documents | Macro scenario field F1 | 82.37, Gemini 3 Pro | 79.12, Qwen3-VL 8B | Original 80.6450; tuned 82.3746 | Full stored-output re-score; original result exceeds third |
| [DocuBench](https://github.com/DocuPipe/DocuBench), all 72 tasks / 10 formats, v0.2.0 | Macro document field accuracy | 97.0170, DocuPipe high | 91.7324, Claude Sonnet 5 | Full 8B V6: **74.7936** | Reference rank 8; 16.9388 pp below third |
| [VAREX](https://udibarzi.github.io/varex-bench/), 1,777 forms, image-only track | Micro normalized field exact match | 98.0, Gemini 2.5 Pro | 96.6, Qwen3-VL 8B | Full repaired quorum: **97.7898**; stored-output development | Reference rank 2; 0.2102 pp below leader |
| [LongArray-Extract](https://www.extend.ai/resources/long-array-extraction-benchmark), all 45 PDFs | Mean document accuracy; failed documents score zero | 99.2, Extend MAX | 83.1, Claude Opus 4.7 | V1 three-document pilot: **76.2477**; V4 pilot: **75.2347** | Pilot receives no full-cohort rank |
| [Contextual AI Extract Bench](https://arxiv.org/html/2602.12247v1), all 35 tasks | End-to-end field pass rate, official Gemini 2.5 Flash judge | 6.9, Gemini 3 Flash | 5.2, GPT-5.2 | 26/35 stored outputs are schema-valid; **content pass rate unknown** | Judge configuration and paper/scorer field-count reconciliation needed |
| [LongExtractBench](https://github.com/micro1-research/longextract-bench), public 50-document subset | Completed-document leaf accuracy, with row P/R and failures separately | No verified public-50 comparison | Unknown | All 50 source inputs prepared; official adapter implemented | Published 225-document outcomes cannot rank our public-50 run |

DocuBench's high and standard profiles and Claude were reproduced from every public output, rather than copied from rounded table entries: 97.0169874, 96.1401270 and 91.7323502. All ten available peer result folders cover 72 documents, including the Pulse folder not shown in the README's nine-entry table. [Machine-readable audit](results/multibench/docubench_public_audit.json).

ExtractBench is **0.4822 percentage points below its leaders**, and 0.6578 above the published third-place score. The local original-annotation re-score reproduces 95.2535; the current-annotation reference reproduces 95.4278. The latter reuses the previous archived evaluation after validating every one of the 370 original prediction hashes and verifying that both the public dataset and scorer revisions remain current. It is not new inference. The previously archived repair candidate scored 95.6430, with 14 gains and no regressions in an incremental development evaluation, but that candidate has not been run on these additional benchmarks. [Current reference provenance](results/multibench/extractbench_current_reference.json); [original-annotation re-score](results/multibench/extractbench_rescore/summary.json).

Contextual's stored `cx_scores.json` contains all-zero scores from an adapter with empty expected outputs; those are not valid benchmark scores. Older local judge logs used Qwen and include judge context failures, which also prevent comparison to the published Gemini-judged results. The schema audit validates against the original supplied schemas and confirms that all 35 schema/gold/PDF inputs match the pinned current official repository. After unwrapping the resume schema, validity is **74.29% (26/35)**, with 6/7 SEC filing outputs valid, but this does not establish an accuracy rank. [Corrected audit](results/multibench/contextual_schema_audit.json). The earlier audit incorrectly treated the resume schema wrapper as a schema and overcounted validity by six documents; the runnable auditor now unwraps it and rejects non-schema inputs.

An offline deterministic diagnostic earns **63 passed evaluations** when every semantic/array judge evaluation is forced to zero and all schema-invalid outputs earn zero. The public scorer visits **691 positions**, whereas the paper denominator is **3,086**: its array metric stops traversal, while the paper counts additional schema fields. This is an evaluation protocol discrepancy to resolve before reporting a comparable content score, even with the matching judge available. These diagnostic counts do not receive a rank. [Diagnostic and per-document reconciliation](results/multibench/contextual_deterministic_diagnostic.json).

## Configurations being measured

The original frozen configuration uses Qwen3.8-27B and MinerU. The model and parser endpoints are down; the shared H100 has about 21 GB of spare memory. The new runs therefore use an explicitly separate **Qwen3-VL-8B-Instruct-FP8** variant, revision `9cdc6310a8cb770ce18efaf4e9935334512aee45`, with a 32,768-token context and 8,192-token output ceiling. Its server uses 0.18 of GPU memory and does not stop the existing GPU process. These scores will not be labelled as fresh measurements of the frozen 27B pipeline.

VAREX's `official` reading uses the publisher's extraction prompt and original image; `whole` uses DocQuorum's whole-page prompt; `guided` uses that prompt with schema decoding. The quorum follows the existing recall-weighted agreement rule, beta 2, with the fixed order official → whole → guided. No supplied OCR/layout text is used in the image-only track. The fixed pilot takes 12 documents per official split in SHA256 order, selected without labels. On its 443 scoreable fields: official 94.8081, whole 94.1309, guided 94.1309, quorum 94.8081. There is **no measured quorum gain in this pilot**. All three full-cohort readings have finished. Their scores are official **96.9503**, whole **97.4530**, and guided **97.6807** across all 1,777 documents. The original adapter quorum scores **96.9503**. The full-run policy was started before evaluating the pilot. [Pilot results](results/multibench/varex/scores/pilot/summary.json).

A selector audit found that the VAREX adapter omitted the `pdf` key required by the agreement scorer. Its helper caught `KeyError` and returned zero: all 1,776 documents with usable readings tied and selected `official`; one document had no usable reading. The separately frozen `varex_selector_v2` supplies the document path and propagates scorer errors. It reuses the same three readings, without model calls or gold during selection, and scores **97.7898** over all 1,777 documents / 21,084 fields. This is **+0.8395 pp** over the original adapter (177 net correct fields) and **+0.1091 pp** over guided (23 net fields), reference rank 2 and **0.2102 pp below the leader**. The document-cluster 95% bootstrap interval versus guided is **−0.0142 to +0.2397 pp**, so a reliable advantage over guided is not established. This is stored-output development, not fresh inference or an independent holdout; the original outputs remain intact. [Repaired score](results/multibench/varex_selector_v2/scores/full/summary.json); [selection audit](results/multibench/varex_selector_v2/selection_audit.json); [paired comparison](results/multibench/varex_selector_v2/paired_comparison.json).

DocuBench and LongArray use the existing reader and checks under `DocQuorum8B-bounded-v1`: exact server tokenization reserves output space before requests; full source text is never clipped by the budget guard; multiple images supplied through that client are composed in page order with a disclosed five-million-pixel cap. DocuBench additionally reads XLSX, DOCX, TXT, XML, HTML and CSV directly, preserving Unicode, cells and source order; multi-frame TIFF is converted with all frames. Its published per-document guidelines are included. All 72 tasks count in the score, and unavailable/failed outputs score zero.

The running baseline exposed two source-derived problems. The scalar reader can exceed the smaller context and silently produce `{}`; it also only reads the first two pages for scan scalars. The external one-shot provider builds its own client, bypassing our guard, and its context-fitting fallback can drop pages or prune schema fields. These are diagnosed from input/request behavior, rather than gold errors.

`DocQuorum8B-bounded-v2` is a separate candidate: scalar schema/page partitions visit the complete source; the external one-shot call uses the guarded client directly, without its dropping/pruning fallback; truncated one-shot outputs are rejected. V2's score and gain are **not measured yet**.

`DocQuorum8B-bounded-v3` adds record-preserving fixes: disjoint page windows accumulate array rows, including repeated rows; every schema/window partition must finish before the pipeline accepts it; dense tables keep complete rows rather than splitting columns away from their identifiers; oversized or truncated text blocks are recursively partitioned; failed list calls propagate instead of being accepted as empty arrays. Complete refinements replace truncated replies regardless of which has more rows. Source-derived tests pass, but there is **no measured V3 accuracy gain yet**. `DocQuorum8B-bounded-v4` additionally restores images to short native PDFs, routes mixed native/scanned PDFs through complete page images, and makes scan chunks one physical page each. V1 could treat a scanned data page as absent because an instructions page had native text; its two-page scan chunks also discarded the second image under the one-image server limit. Native-text record chunks can still span two pages. A source-only audit finds 3 mixed PDFs and 21 scan/sparse-text PDFs among the 58 PDF tasks; the fallback scan-chunk rule could omit 147 physical pages. This is a route-specific potential-loss count, not a claim that every affected document took that route. [Source modality audit](results/multibench/docubench_modality_audit.json).

The two error-selected routing checks improve from **0 → 80.9524** and **12.5 → 86.6667**; they are development checks and receive no rank. The V4 policy was frozen before measuring them, and its complete 72-task run has finished at **70.3995**, with separate predictions; it retains all seven failed tasks as zero. V1's complete 72-task score is **63.8574**, reference rank 11 among the ten published peers plus this variant. It is **27.8749 percentage points below third** and **33.1596 below the leader**. One XML task failed because its complete native source needed 78,302 prompt tokens; it contributes zero rather than being dropped. A return marked completed does not imply accurate extraction: the remaining 71 documents also contain field errors. [Routing checks](results/multibench/docubench_v4/routing_check.json). All candidates are confined to experiment runner processes; the frozen pipeline source is unchanged.

`DocQuorum8B-bounded-v5` is a separate recovery experiment, frozen after V4 reported image-output truncation on two scanned tasks. It retries smaller horizontal bands with disjoint ownership: a red margin marks the body, while repeated headers and neighbouring pixels provide context; only records whose first line lies in the owned body should be emitted. Printed duplicates are retained. This instruction needs measured visual recall and boundary-error checks; code coverage alone cannot establish completeness. Oversized native XML is partitioned at complete element boundaries with ancestor tags preserved, and every partition must finish. A source-only audit preserves all 6,083 XML leaf occurrences in order over 13 partitions; oversized individual leaves fail explicitly. The selected XML task improves from failed/zero to **23.9726**, using 13 completed calls, 92,806 prompt tokens and 3,288 output tokens. This is a development-selected task, not a cohort score or rank; unrelated-order values still reduce accuracy. [Native source audit](results/multibench/docubench_v5/native_source_audit.json).

`DocQuorum8B-bounded-v6` addresses that native query-scope error: a field explicitly referring to a record identifier is scheduled only in source windows containing that identifier, with every root field required to have a window assignment. Unbound fields still visit every window. Identifiers must occur in the full original source and use an explicit query phrase; examples and format hints do not create bindings. This guards absence, not correctness within a window. Eleven of the XML task's fifteen fields receive bindings. On the selected XML task, V6 scores **100.0000**, versus V5's 23.9726 and V1's failure/zero. All 15 fields have source-window assignments, all 13 calls finish, and output tokens fall from 3,288 to 871. Shared-GPU wall time rises from 475.6 to 818.9 seconds, so this run does not establish a latency gain. It is a development-selected case, not a cohort rank. [Query-scope check](results/multibench/docubench_v6/native_query_check.json). V6 uses the same visual recovery as V5. Its complete 72-task run has finished at **74.7936**, with 71 completed tasks and one failure counted as zero. This improves on V1 by **10.9362 percentage points**, but remains **16.9388 below published third** and **22.2234 below the leader**; reference rank 8.

The first selected scan recovery, the 10-page `9hPCh7ca`, now completes at **42.8142**, versus V1 **25.8371** and V4 failure (**0**). This is a development check selected after runtime truncation, and its remaining field errors are substantial. The complete V6 cohort has since finished; this selected-case artifact is retained as a development diagnostic. [Measured image recovery](results/multibench/docubench_v6/image_recovery_progress.json).

A paired development diagnostic on V4's first 27 attempted tasks improves from **68.1680 to 79.0588** on those same documents: 9 gains, 5 regressions and 13 unchanged; two candidate tasks fail on image truncation. Completion order is not a random sample, and these values do not receive a full-cohort rank. [Paired progress snapshot](results/multibench/docubench_v4/paired_progress.json).

LongArray inference sees only the original PDF and supplied vertical schema. Its ground truth, `target_count`, target field metadata and generated page maps are excluded. Scoring loads the publisher's reference implementation verbatim from the pinned dataset card. It reports predicted and expected array lengths because that metric alone does not penalize surplus rows. A complete result must count all 45 documents, with failures contributing zero. The original three-document pilot completes all tasks at **76.2477**: clinical 61.5354 (356 predicted rows / 198 expected), financial 79.4150 (917 / 923), and legal 87.7927 (319 / 319). It receives no comparison rank against the full 45-document references. The V4 three-document pilot has finished at **75.2347**, a regression from V1; the full 45-document V4 run is underway. [Pilot score](results/multibench/longarray/scores/pilot/summary.json). The reference collector includes all 11 published systems, so lower scores cannot obtain inflated ranks by omitting intermediate peers. [Published reference rows](results/multibench/longarray_public_reference.json).

V4 does not yet solve LongArray’s clinical extraction: its completed pilot task scores **59.4545**, versus V1 **61.5354**, with **363 / 198** rows. The output still includes zero-event subject blocks that the schema excludes. Inspection of the original source also shows global code legends, demographic context and supportive listings that repeat primary events; these require explicit scope and context handling. The financial and legal tasks finish at 78.4760 and 87.7735 respectively; the complete three-document V4 pilot scores **75.2347** and receives no full-cohort rank. [Clinical task comparison](results/multibench/longarray_v4/clinical_progress.json).

A larger-backbone follow-up is being prepared using [the pinned 27B INT4 checkpoint](https://huggingface.co/ulkaa/Qwen3.8-27B-AWQ-INT4/tree/2bf7f1646dc0875cff4404fdfef976cfb0ff2199). Its safetensors total 18.2054 GiB, with MTP tensors preserved on disk; the installed vLLM regular loader skips `mtp.` tensors. The pinned weights are now cached; the inspected tensor headers total 18.2051 GiB, or an estimated 17.4140 GiB after excluding unused MTP tensors. The 8B runs continue. GPU fit, speed and extraction accuracy remain unmeasured, and its scores will use a separate backbone label. [Candidate metadata](results/multibench/larger_backbone_candidates.json); [completed download and tensor inventory](results/multibench/backbone_27b_int4_ready.json).

## Reproduction and next measurements

The third-party sources live in ignored `data/multibench_sources/`. Pin these revisions:

| Source | Revision |
|---|---|
| `DocuPipe/DocuBench` GitHub | `43a3f3bc00e591e711075678ca6d154acfedcf42` |
| `udibarzi/varex-bench` GitHub | `3cce9c18530748cfc843f38c02e2f43e0694d167` |
| `ContextualAI/extract-bench` GitHub | `ca817638852a23bb17ca9aaeb82ccdd29e9af9ca` |
| `micro1-research/longextract-bench` GitHub | `b28888d7e864a84dfed810b00c899f308f0d24d0` |
| `ibm-research/VAREX` Hugging Face | `2dfc3386a4567c7d56bf1abf4d12ff42afed27b6` |
| `Extend-AI/LongArray-Extract` Hugging Face | `f2ae30264ecd942fa0a9b9e787bb42e1e2577184` |
| `micro1-inc/longextract-bench-50` Hugging Face | `d4ca332f72f6d3649ecd11b69445a8f4ef5fcb02` |

Use the project's configured Python/Poppler paths in `configs/local.env`, install `benchmarks/multibench/requirements.txt`, and start `bash benchmarks/multibench/serve_8b.sh` after checking spare GPU memory. Set `DQ_LLM_URL=http://localhost:8078/v1` and `DQ_MODEL_NAME=dq-multibench8b` for inference.

```bash
source configs/local.env
export DQ_LLM_URL=http://localhost:8078/v1 DQ_MODEL_NAME=dq-multibench8b
"$DQ_PYTHON" benchmarks/multibench/audit.py
"$DQ_PYTHON" benchmarks/multibench/contextual.py audit
"$DQ_PYTHON" benchmarks/multibench/varex.py prepare
"$DQ_PYTHON" benchmarks/multibench/varex.py run --scope full
"$DQ_PYTHON" benchmarks/multibench/varex.py combine --scope full
"$DQ_PYTHON" benchmarks/multibench/varex.py score --scope full
# Corrected selection into a distinct folder, reusing frozen outputs:
"$DQ_PYTHON" benchmarks/multibench/varex_selector.py combine
"$DQ_PYTHON" benchmarks/multibench/varex_selector.py score
"$DQ_PYTHON" benchmarks/multibench/docubench.py run
"$DQ_PYTHON" benchmarks/multibench/docubench.py score
"$DQ_PYTHON" benchmarks/multibench/longarray.py prepare
"$DQ_PYTHON" benchmarks/multibench/longarray.py run --scope full
"$DQ_PYTHON" benchmarks/multibench/longarray.py score --scope full
```

For the complete V4 comparison, use `docubench.py run --profile bounded-v4 --out results/multibench/docubench_v4`, followed by `docubench.py score --out results/multibench/docubench_v4`. `--only ID ...` can resume selected tasks while preserving the full 72-task scoring denominator. LongArray V4 inputs are also prepared; use its separate output directory and the same profile.

V5 accepts the same distinct-output convention, for example `docubench.py run --profile bounded-v5 --out results/multibench/docubench_v5`. Keep its predictions separate from V4. LongArray and LongExtract also accept V5 for later transfer measurements.

For V3, use `--profile bounded-v3 --out results/multibench/docubench_v3` or `--profile bounded-v3 --out results/multibench/longarray_v3`. V3 LongArray inputs and all 50 public LongExtract inputs are prepared. LongExtract also accepts `--profile bounded-v4 --out results/multibench/longextract_v4`; prepare into that directory, run the full cohort with those same flags, then score with `--out results/multibench/longextract_v4 --scope full`. The supplied profile is recorded from the actual run policy, and complete publication requires all 50 attempts. Its official leaf accuracy averages only successful documents; row P/R, failures and latency are reported separately, and it never receives a rank against the private 225-document evaluation.

For V2, pass `--profile bounded-v2 --out results/multibench/docubench_v2` to the DocuBench run and `--out results/multibench/docubench_v2` to scoring. LongArray likewise supports a distinct output directory; prepare its inputs there first. Do not mix predictions across policies or overwrite the running baseline.

**Validation:** 50 tests in the committed suite pass (35 evaluation/adapter regression tests plus 15 existing core tests), including real agreement scoring, rejection of silent scorer failure, and retention of all-reader failure. The new checks cover missing-prediction penalties, pilot/tie eligibility, exact context reservation, page composition order, Hebrew text fidelity, wrapped schemas, full scalar coverage, incomplete one-shot/partition rejection, preservation of repeated records and identifier/value association, failed-call propagation, and LongExtract's separate recall/failure accounting. Public peer re-scoring and full input/manifest coverage are independent integration checks.

DocuBench V4/V6 and full VAREX are complete. The full LongArray V4 and public-50 LongExtract V4 runs remain underway; Contextual content judging remains pending. VAREX exceeds published third on a matching complete image-only cohort, while DocuBench is still 16.9388 points below third. The next accuracy experiment should preserve source scope, global context and physical-row ownership, then measure source verification and selective rereading. See [the Jev applicability and experiment proposal](docs/jev-proposal.md).

Contextual diagnostics use a separate environment because both benchmarks publish a Python package named `extract_bench`. Create it with `"$DQ_PYTHON" -m venv --system-site-packages data/multibench_sources/contextual_eval_env`, install `litellm==1.82.3 loguru==0.7.3` there, then run `contextual_eval_env/bin/python benchmarks/multibench/contextual.py diagnostic` using the full environment path. This diagnostic makes no model calls.

Run `"$DQ_PYTHON" benchmarks/multibench/leaderboard.py` after scoring to refresh [the accumulated result table](results/multibench/leaderboard.json). It assigns no rank to pilots, and uses published rounding precision to avoid claiming a win over a rounded tie.

DocILE requires page/box localization and line-item grouping plus gated annotated data; RealKIE uses span extraction; OmniDocBench measures parsing. They need separate output adapters and metrics. Datalab's OmniExtractBench substantially overlaps existing extraction datasets, so it can test robustness to revised annotations but cannot count as wholly independent evidence. None of these has an established DocQuorum rank here.

Higher ranks alone will not establish an A* paper or general superiority. A defensible claim needs a frozen cross-benchmark policy, complete cohorts, independent held-out evaluation, matched backbone baselines, repair/quorum ablations, row completeness, and measured cost/latency. This branch preserves those distinctions while testing whether the fixes transfer.

## Publishing completed benchmarks

`benchmarks/multibench/publish_completed.py --watch` checks scored results every 30 seconds. When a full cohort finishes, it refreshes the completed-results table and commits/pushes its summary and manifests to this experiment branch. UNIKIE and both the stored-primary and archived development ExtractBench results remain in the accumulated table. Pilots and incomplete cohorts are excluded. Raw inputs/predictions are not staged. A branch guard refuses publication to `main`.
