| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| parties.administrative_agent | string_fuzzy | 0.973 | Yes |  | | | | | | |
| parties.borrower | string_fuzzy | 1.000 | Yes |  | | | | | | |
| parties.lead_arranger | array_llm | 1.000 | Yes | both_null | | | | | | |
| terms.beneficial_ownership_certification_required | boolean_exact | 0.000 | No | extracted_null | | | | | | |
| terms.authorized_officer_definition | string_semantic | 0.000 | No | extracted_null | | | | | | |
| terms.loan_commitment.amount | number_exact | 0.000 | No |  | | | | | | |
| terms.loan_commitment.currency | string_case_insensitive | 1.000 | Yes |  | | | | | | |
| terms.governing_law | string_semantic | 1.000 | Yes |  | | | | | | |
| terms.agreement_date | string_semantic | 1.000 | Yes |  | | | | | | |
| terms.maturity_date | string_semantic | 0.000 | No |  | | | | | | |
| terms.use_of_proceeds | string_semantic | 0.000 | No |  | | | | | | |
| terms.borrowing_request | string_semantic | 0.900 | Yes |  | | | | | | |
| parties.lenders | array_llm | 0.929 | Yes |  | 13 | 1 | 1 | 0.93 | 0.93 | 0.93 |