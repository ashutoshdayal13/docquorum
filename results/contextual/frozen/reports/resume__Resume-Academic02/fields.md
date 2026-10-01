| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| skills | array_llm | 0.000 | No | gold_null | | | | | | |
| socialLinks | array_llm | 1.000 | Yes | both_empty_array | | | | | | |
| personalInfo.contact.emails | array_llm | 1.000 | Yes | both_empty_array | | | | | | |
| personalInfo.contact.phones | array_llm | 1.000 | Yes | both_empty_array | | | | | | |
| personalInfo.fullName | string_semantic | 1.000 | Yes |  | | | | | | |
| personalInfo.personalStatement | string_semantic | 1.000 | Yes |  | | | | | | |
| languages | array_llm | 1.000 | Yes |  | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| media | array_llm | 1.000 | Yes |  | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| other | array_llm | 0.889 | Yes |  | 8 | 1 | 0 | 1.00 | 0.89 | 0.94 |
| education | array_llm | 1.000 | Yes |  | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| publications | array_llm | 1.000 | Yes |  | 15 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| workExperience | array_llm | 0.857 | Yes |  | 6 | 1 | 1 | 0.86 | 0.86 | 0.86 |
| certificationsAndAwards | array_llm | 0.944 | Yes |  | 17 | 1 | 1 | 0.94 | 0.94 | 0.94 |