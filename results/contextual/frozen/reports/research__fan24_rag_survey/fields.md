| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| ids | string_exact | 0.000 | No |  | | | | | | |
| number_of_pages | integer_exact | 1.000 | Yes |  | | | | | | |
| publication_type | string_exact | 0.000 | No |  | | | | | | |
| publication_date | string_semantic | 0.000 | No |  | | | | | | |
| venue | string_semantic | 0.000 | No |  | | | | | | |
| title | string_semantic | 1.000 | Yes |  | | | | | | |
| abstract | string_semantic | 1.000 | Yes |  | | | | | | |
| keywords | array_llm | 0.833 | Yes |  | 5 | 1 | 1 | 0.83 | 0.83 | 0.83 |
| authors | array_llm | 0.875 | Yes |  | 7 | 1 | 1 | 0.88 | 0.88 | 0.88 |
| citations | array_llm | 1.000 | Yes |  | 170 | 0 | 0 | 1.00 | 1.00 | 1.00 |