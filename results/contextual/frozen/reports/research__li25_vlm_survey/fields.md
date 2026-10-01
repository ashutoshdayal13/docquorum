| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| ids | string_exact | 0.000 | No |  | | | | | | |
| venue | string_semantic | 0.000 | No | extracted_null | | | | | | |
| keywords | array_llm | 0.000 | No | gold_empty_array | | | | | | |
| number_of_pages | integer_exact | 1.000 | Yes |  | | | | | | |
| publication_type | string_exact | 1.000 | Yes |  | | | | | | |
| abstract | string_semantic | 1.000 | Yes |  | | | | | | |
| title | string_semantic | 1.000 | Yes |  | | | | | | |
| publication_date | string_semantic | 1.000 | Yes |  | | | | | | |
| authors | array_llm | 1.000 | Yes |  | 6 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| citations | array_llm | 1.000 | Yes |  | 200 | 0 | 0 | 1.00 | 1.00 | 1.00 |