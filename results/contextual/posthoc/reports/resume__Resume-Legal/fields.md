| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| media | array_llm | 1.000 | Yes | both_empty_array | | | | | | |
| socialLinks | array_llm | 1.000 | Yes | both_empty_array | | | | | | |
| publications | array_llm | 1.000 | Yes | both_empty_array | | | | | | |
| personalInfo.fullName | string_semantic | 1.000 | Yes |  | | | | | | |
| personalInfo.personalStatement | string_semantic | 1.000 | Yes |  | | | | | | |
| personalInfo.contact.phones | array_llm | 1.000 | Yes |  | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| skills | array_llm | 1.000 | Yes |  | 5 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| languages | array_llm | 1.000 | Yes |  | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| personalInfo.contact.emails | array_llm | 1.000 | Yes |  | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| other | array_llm | 1.000 | Yes |  | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| education | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| workExperience | array_llm | 1.000 | Yes |  | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| certificationsAndAwards | array_llm | 0.667 | No |  | 2 | 1 | 1 | 0.67 | 0.67 | 0.67 |