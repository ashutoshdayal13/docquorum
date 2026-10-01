# TODO

## Find more key-information-extraction (KIE) benchmarks to compare on (to run later)

Search broadly for public KIE / schema-guided document-extraction datasets on which DocQuorum can be compared with other
published systems, then pick the ones to run. Nothing is to be run until the list is agreed.

For each candidate, record:

| what to record | why |
|---|---|
| name, paper, year, venue, link | to cite it |
| documents: kind (receipts, invoices, forms, contracts, filings, ...), count, pages, language, scans vs digital PDFs | coverage beyond ExtractBench and UNIKIE-BENCH |
| task format: a schema or template per document, or a fixed label set | DocQuorum takes a JSON Schema or JSON template; a fixed label set needs an adapter |
| the official scorer, and whether it can be run locally | results must use the benchmark's own scoring |
| published results: which systems (open and commercial), which metric, zero-shot or fine-tuned | a benchmark is only useful if there are others to compare with, in the same regime (zero-shot here) |
| license and access (download, registration, redistribution) | whether it can be used, and what may be published |
| size of a full run on one GPU | to plan the runs |

Rules for the runs, as for UNIKIE-BENCH:
* freeze the configuration before opening a new benchmark, and report that frozen result as held out;
* replicate the benchmark's own protocol (its prompt for the baseline, image size, post-processing, scorer);
* no labels in any method step, and no rules fitted to one benchmark's answer conventions.

Starting points to check: the UNIKIE-BENCH and ExtractBench papers' related-work sections (`ref_papers/`, local only),
the datasets UNIKIE-BENCH is built from, and recent KIE / document-extraction benchmark papers and leaderboards.
