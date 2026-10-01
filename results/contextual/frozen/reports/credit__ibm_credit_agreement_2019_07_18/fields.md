| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| parties.administrative_agent | string_fuzzy | 1.000 | Yes |  | | | | | | |
| parties.borrower | string_fuzzy | 0.976 | Yes |  | | | | | | |
| terms.maturity_date | string_semantic | 1.000 | Yes | both_null | | | | | | |
| terms.beneficial_ownership_certification_required | boolean_exact | 0.000 | No | extracted_null | | | | | | |
| terms.governing_law | string_semantic | 0.000 | No | extracted_null | | | | | | |
| terms.use_of_proceeds | string_semantic | 0.000 | No | extracted_null | | | | | | |
| terms.borrowing_request | string_semantic | 0.000 | No | extracted_null | | | | | | |
| terms.authorized_officer_definition | string_semantic | 0.000 | No | extracted_null | | | | | | |
| terms.loan_commitment.amount | number_exact | 1.000 | Yes |  | | | | | | |
| terms.loan_commitment.currency | string_case_insensitive | 1.000 | Yes |  | | | | | | |
| terms.agreement_date | string_semantic | 1.000 | Yes |  | | | | | | |
| parties.lead_arranger | array_llm | 0.000 | No |  | 0 | 2 | 4 | 0.00 | 0.00 | 0.00 |
| parties.lenders | array_llm | 0.314 | No |  | 11 | 24 | 1 | 0.92 | 0.31 | 0.47 |