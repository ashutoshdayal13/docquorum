| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| ids | string_exact | 0.000 | No |  | | | | | | |
| venue | string_semantic | 0.000 | No | extracted_null | | | | | | |
| number_of_pages | integer_exact | 1.000 | Yes |  | | | | | | |
| publication_type | string_exact | 1.000 | Yes |  | | | | | | |
| abstract | string_semantic | 1.000 | Yes |  | | | | | | |
| title | string_semantic | 1.000 | Yes |  | | | | | | |
| publication_date | string_semantic | 1.000 | Yes |  | | | | | | |
| keywords | array_llm | 0.000 | No |  | 0 | 1 | 8 | 0.00 | 0.00 | 0.00 |
| authors | array_llm | 0.667 | No |  | 4 | 2 | 2 | 0.67 | 0.67 | 0.67 |
| citations | array_llm | 1.000 | Yes |  | 63 | 0 | 0 | 1.00 | 1.00 | 1.00 |