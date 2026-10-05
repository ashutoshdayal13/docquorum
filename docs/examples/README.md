# Schema and answer demonstrations

These complete JSON files are included in the PDF guide. Answers are displayed
for explanation; they are not extraction inputs and do not represent new model
measurements.

| Example | Schema | Answer | Origin |
|---|---|---|---|
| Purchase order | [schema](purchase-order.schema.json) | [answer](purchase-order.answer.json) | Synthetic example matching the guide's purchase-order walkthrough. |
| Electric bill | [schema](electric-bill.schema.json) | [reference answer](electric-bill.answer.json) | Actual DocuBench task `PSU5pciM`, copied without content changes and reformatted for display. |

The purchase-order example contains two scalar fields and two repeated item
records. The electric-bill example contains six scalar fields and four charge
records; its total is a scalar, not another charge row. Small examples illustrate
the schema structure; a whole-document call may already fit, so these examples do
not claim the scalars + lists fallback was executed.

The electric-bill schema and reference answer are attributed to **DocuPipe /
DocuBench** and redistributed under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
Only whitespace formatting changed; field names, descriptions, types, and all
answer values are retained. Source revision:
`43a3f3bc00e591e711075678ca6d154acfedcf42`.

- [Original schema](https://github.com/DocuPipe/DocuBench/blob/43a3f3bc00e591e711075678ca6d154acfedcf42/schemas/PSU5pciM.json)
- [Original reference answer](https://github.com/DocuPipe/DocuBench/blob/43a3f3bc00e591e711075678ca6d154acfedcf42/labels/PSU5pciM.json)
- [Dataset license](https://github.com/DocuPipe/DocuBench/blob/43a3f3bc00e591e711075678ca6d154acfedcf42/LICENSE)
- [Original CPS Energy redacted bill](https://www.cpsenergy.com/content/dam/corporate/en/Documents/RAC/CustomerBills/Bill%20Sample%20-%20RA%20Rate%20-%20Non-Summer%20%20Redacted.pdf)
- [Local provenance and source hashes](provenance.json)

The original bill is linked, not redistributed here. The PDF guide displays a
reconstruction of selected source facts, rather than an image of that bill.
