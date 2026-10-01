| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| ids | string_exact | 1.000 | Yes | both_null | | | | | | |
| venue | string_semantic | 1.000 | Yes | both_null | | | | | | |
| keywords | array_llm | 1.000 | Yes | both_empty_array | | | | | | |
| number_of_pages | integer_exact | 1.000 | Yes |  | | | | | | |
| publication_date | string_semantic | 1.000 | Yes | both_null | | | | | | |
| publication_type | string_exact | 1.000 | Yes |  | | | | | | |
| title | string_semantic | 1.000 | Yes |  | | | | | | |
| abstract | string_semantic | 1.000 | Yes |  | | | | | | |
| authors | array_llm | 1.000 | Yes |  | 7 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| citations | array_llm | 1.000 | Yes |  | 11 | 0 | 0 | 1.00 | 1.00 | 1.00 |