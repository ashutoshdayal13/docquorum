| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| media | array_llm | 0.000 | No | gold_empty_array | | | | | | |
| other | array_llm | 1.000 | Yes | both_empty_array | | | | | | |
| languages | array_llm | 1.000 | Yes | both_empty_array | | | | | | |
| publications | array_llm | 1.000 | Yes | both_empty_array | | | | | | |
| personalInfo.contact.emails | array_llm | 0.000 | No | extracted_missing | | | | | | |
| personalInfo.contact.phones | array_llm | 0.000 | No | extracted_missing | | | | | | |
| personalInfo.fullName | string_semantic | 1.000 | Yes |  | | | | | | |
| personalInfo.personalStatement | string_semantic | 1.000 | Yes |  | | | | | | |
| socialLinks | array_llm | 0.000 | No |  | 0 | 1 | 1 | 0.00 | 0.00 | 0.00 |
| skills | array_llm | 0.000 | No |  | 0 | 32 | 0 | 1.00 | 0.00 | 0.00 |
| education | array_llm | 0.000 | No |  | 0 | 1 | 1 | 0.00 | 0.00 | 0.00 |
| workExperience | array_llm | 1.000 | Yes |  | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| certificationsAndAwards | array_llm | 0.000 | No |  | 0 | 9 | 9 | 0.00 | 0.00 | 0.00 |