| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| ids | string_exact | 1.000 | Yes | both_null | | | | | | |
| venue | string_semantic | 1.000 | Yes | both_null | | | | | | |
| number_of_pages | integer_exact | 1.000 | Yes |  | | | | | | |
| publication_date | string_semantic | 1.000 | Yes | both_null | | | | | | |
| publication_type | string_exact | 1.000 | Yes |  | | | | | | |
| title | string_semantic | 1.000 | Yes |  | | | | | | |
| abstract | string_semantic | 1.000 | Yes |  | | | | | | |
| keywords | array_llm | 1.000 | Yes |  | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| authors | array_llm | 1.000 | Yes |  | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| citations | array_llm | 0.985 | Yes |  | 131 | 2 | 3 | 0.98 | 0.98 | 0.98 |