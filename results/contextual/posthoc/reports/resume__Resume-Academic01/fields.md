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
| other | array_llm | 0.714 | Yes |  | 5 | 2 | 38 | 0.12 | 0.71 | 0.20 |
| education | array_llm | 0.333 | No |  | 1 | 2 | 2 | 0.33 | 0.33 | 0.33 |
| workExperience | array_llm | 0.500 | No |  | 9 | 9 | 7 | 0.56 | 0.50 | 0.53 |
| certificationsAndAwards | array_llm | 0.267 | No |  | 8 | 22 | 115 | 0.07 | 0.27 | 0.10 |
| publications | array_llm | 0.696 | No |  | 16 | 7 | 10 | 0.62 | 0.70 | 0.65 |