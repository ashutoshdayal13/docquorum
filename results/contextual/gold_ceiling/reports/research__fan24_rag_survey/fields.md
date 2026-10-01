| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| ids | string_exact | 1.000 | Yes |  | | | | | | |
| number_of_pages | integer_exact | 1.000 | Yes |  | | | | | | |
| publication_type | string_exact | 1.000 | Yes |  | | | | | | |
| title | string_semantic | 1.000 | Yes |  | | | | | | |
| venue | string_semantic | 1.000 | Yes |  | | | | | | |
| abstract | string_semantic | 1.000 | Yes |  | | | | | | |
| publication_date | string_semantic | 1.000 | Yes |  | | | | | | |
| keywords | array_llm | 1.000 | Yes |  | 6 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| authors | array_llm | 1.000 | Yes |  | 8 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| citations | array_llm | 1.000 | Yes |  | 170 | 0 | 0 | 1.00 | 1.00 | 1.00 |