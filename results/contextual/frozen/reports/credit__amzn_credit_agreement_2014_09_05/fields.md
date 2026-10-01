| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| parties.administrative_agent | string_fuzzy | 1.000 | Yes |  | | | | | | |
| parties.borrower | string_fuzzy | 1.000 | Yes |  | | | | | | |
| terms.maturity_date | string_semantic | 0.000 | No | extracted_null | | | | | | |
| terms.beneficial_ownership_certification_required | boolean_exact | 0.000 | No | extracted_null | | | | | | |
| terms.governing_law | string_semantic | 0.000 | No | extracted_null | | | | | | |
| terms.use_of_proceeds | string_semantic | 0.000 | No | extracted_null | | | | | | |
| terms.borrowing_request | string_semantic | 0.000 | No | extracted_null | | | | | | |
| terms.authorized_officer_definition | string_semantic | 0.000 | No | extracted_null | | | | | | |
| terms.loan_commitment.amount | number_exact | 1.000 | Yes |  | | | | | | |
| terms.loan_commitment.currency | string_case_insensitive | 1.000 | Yes |  | | | | | | |
| terms.agreement_date | string_semantic | 1.000 | Yes |  | | | | | | |
| parties.lead_arranger | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| parties.lenders | array_llm | 0.200 | No |  | 1 | 4 | 1 | 0.50 | 0.20 | 0.29 |