| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| championship | string_fuzzy | 1.000 | Yes |  | | | | | | |
| event_details.sex | string_case_insensitive | 1.000 | Yes |  | | | | | | |
| event_details.length | string_exact | 0.000 | No |  | | | | | | |
| event_details.category | string_exact | 1.000 | Yes |  | | | | | | |
| age_groups | array_llm | 1.000 | Yes |  | 23 | 0 | 0 | 1.00 | 1.00 | 1.00 |