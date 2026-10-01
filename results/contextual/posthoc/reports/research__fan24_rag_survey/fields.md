| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| ids | string_exact | 0.000 | No |  | | | | | | |
| number_of_pages | integer_exact | 1.000 | Yes |  | | | | | | |
| publication_type | string_exact | 0.000 | No |  | | | | | | |
| publication_date | string_semantic | 0.000 | No |  | | | | | | |
| venue | string_semantic | 0.000 | No |  | | | | | | |
| abstract | string_semantic | 1.000 | Yes |  | | | | | | |
| title | string_semantic | 1.000 | Yes |  | | | | | | |
| keywords | array_llm | 1.000 | Yes |  | 6 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| authors | array_llm | 0.875 | Yes |  | 7 | 1 | 1 | 0.88 | 0.88 | 0.88 |
| citations | array_llm | 0.988 | Yes |  | 168 | 2 | 2 | 0.99 | 0.99 | 0.99 |