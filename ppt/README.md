# DocQuorum: a real document through the pipeline

Open **[docquorum.pdf](docquorum.pdf)**. This is the revised 15-page presentation, with the latest pipeline image and real source evidence. The editable source is [walkthrough.tex](walkthrough.tex).

The opening diagram names each reader, lists its evidence and tools, and distinguishes automatic execution from adaptive reading. Poppler, MinerU, schema/layout helpers and the extraction-model API have explicit output labels. The whole system runs automatically after receiving its inputs. Python controls routing, checks, selection and the bounded reader loop; the model performs extraction. Primary and parse readers can retry or change scope after inspecting a result. Specialized layout and one-shot readers use scheduled calls.

The walkthrough follows this order:

1. The full pipeline, with the plan → act → observe → retry/replan loop.
2. A real Oklahoma County purchase order, its schema, an alternative teaching template, and an optional teaching task.
3. Digital versus degraded-scan evidence; a scanned form with embedded OCR text.
4. The printed table, actual MinerU HTML, and the reader's field mapping.
5. Real column-flow and ruled-table layout examples.
6. A stored missing-key reply and the subsequent required-field re-read.
7. What a deterministic check does, followed by three source → before → rule → after examples.
8. Three actual checked candidates and the stored quorum decision.
9. The two complete results tables: ExtractBench and UNIKIE-BENCH.

The three check examples are concrete and reproducible:

| Example | Evidence used by the rule | Recorded change |
|---|---|---|
| Texas P-4 checkbox | Boolean schema explicitly defines blank as false | `gatherer: null` → `false` |
| Byline Bancorp net income | Source text uniquely supports a more precise printed number | `26.11` → `26.107` million |
| Pueblo check register | Distinctive values show the same records copied across two arrays | 562 batch records → 51; all 511 checks unchanged |

The checkbox rule does not inspect the page image. The copied-row rule compares candidate arrays. The precision rule uses source text and scale matching; it does not semantically verify every figure. All three require their implemented conditions and make no model calls. The PDF shows source images to explain why each change makes sense to a reader.

## Evidence and limitations

[examples/](examples/) preserves PDFs, schemas, cached parses, raw replies, checked candidates and per-check provenance. Purchase-order and routing artifacts come from repository revision `b4ea9a1`; they are stored runs, not fresh inference. Presentation crops are rendered from real source PDFs. No generated document is presented as real evidence.

The template and optional task are teaching alternatives, labeled on the page; they were not used to produce the stored candidates. MinerU HTML is abbreviated on the page; the complete parse is bundled. The precision replay uses PyMuPDF's sorted text extraction, as recorded in its provenance. Current implementations reproduce the complete before/after JSONs for the three checks.

The stored one-shot candidate wins mean agreement and is returned whole, without field fusion. In this example the primary candidate has a higher historical answer-key score. Agreement is not a guarantee of accuracy, and answer keys are not supplied to selection.

Both result tables use the maintained [results snapshot](results/README.md). ExtractBench is 95.43 overall, 3rd in the pinned 2 October 2026 snapshot, with all 47 published systems plus DocQuorum. ExtractBench was used during development. UNIKIE-BENCH is 82.65 macro F1 with zoom re-reading (82.62 without), 1st, with all 15 published systems plus DocQuorum; it uses a separate six-reading benchmark protocol including extra-model readings, with small images enlarged before reading.

## Rebuild and verify

From the repository root:

```sh
make -C ppt
make -C ppt verify
```

Building requires `pdflatex`, Beamer, TikZ, Latin Modern and standard LaTeX packages. Verification requires the repository's Python dependencies and PyMuPDF. Neither command calls a model or downloads data. The PDF is self-contained and can be shared on its own. [example-hashes.json](example-hashes.json) records the bundled evidence hashes.

The separate `flow/` material is retained. This README and the root PDF describe the revised walkthrough.
