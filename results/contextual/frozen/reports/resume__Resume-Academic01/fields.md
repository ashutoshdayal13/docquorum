| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| skills | array_llm | 0.000 | No | gold_null | | | | | | |
| socialLinks | array_llm | 1.000 | Yes | both_empty_array | | | | | | |
| personalInfo.contact.emails | array_llm | 1.000 | Yes | both_absent | | | | | | |
| personalInfo.contact.phones | array_llm | 1.000 | Yes | both_absent | | | | | | |
| personalInfo.personalStatement | string_semantic | 1.000 | Yes |  | | | | | | |
| personalInfo.fullName | string_semantic | 0.900 | Yes |  | | | | | | |
| languages | array_llm | 1.000 | Yes |  | 5 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| media | array_llm | 0.833 | Yes |  | 5 | 1 | 0 | 1.00 | 0.83 | 0.91 |
| certificationsAndAwards | array_llm | 0.267 | No |  | 8 | 22 | 115 | 0.07 | 0.27 | 0.10 |
| education | array_llm | 0.000 | No |  | 0 | 3 | 3 | 0.00 | 0.00 | 0.00 |
| publications | array_llm | 0.696 | No |  | 16 | 7 | 3 | 0.84 | 0.70 | 0.76 |
| workExperience | array_llm | 0.389 | No |  | 7 | 11 | 3 | 0.70 | 0.39 | 0.50 |
| other | array_llm | 0.714 | Yes |  | 5 | 2 | 39 | 0.11 | 0.71 | 0.20 |