| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| ids | string_exact | 0.000 | No |  | | | | | | |
| venue | string_semantic | 0.000 | No | extracted_null | | | | | | |
| number_of_pages | integer_exact | 1.000 | Yes |  | | | | | | |
| publication_type | string_exact | 1.000 | Yes |  | | | | | | |
| title | string_semantic | 1.000 | Yes |  | | | | | | |
| abstract | string_semantic | 1.000 | Yes |  | | | | | | |
| publication_date | string_semantic | 1.000 | Yes |  | | | | | | |
| citations | array_llm | 0.000 | No | error | | | | | | |
| authors | array_llm | 1.000 | Yes |  | 22 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| keywords | array_llm | 1.000 | Yes |  | 6 | 0 | 54 | 0.10 | 1.00 | 0.18 |