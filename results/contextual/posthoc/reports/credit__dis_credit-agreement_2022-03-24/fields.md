| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| parties.administrative_agent | string_fuzzy | 0.483 | No |  | | | | | | |
| parties.borrower | string_fuzzy | 1.000 | Yes |  | | | | | | |
| terms.beneficial_ownership_certification_required | boolean_exact | 0.000 | No | extracted_null | | | | | | |
| terms.loan_commitment.amount | number_exact | 1.000 | Yes |  | | | | | | |
| terms.loan_commitment.currency | string_case_insensitive | 1.000 | Yes |  | | | | | | |
| terms.agreement_date | string_semantic | 1.000 | Yes |  | | | | | | |
| terms.maturity_date | string_semantic | 1.000 | Yes |  | | | | | | |
| terms.governing_law | string_semantic | 1.000 | Yes |  | | | | | | |
| terms.use_of_proceeds | string_semantic | 0.400 | No |  | | | | | | |
| terms.authorized_officer_definition | string_semantic | 1.000 | Yes |  | | | | | | |
| parties.lead_arranger | array_llm | 1.000 | Yes |  | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| terms.borrowing_request | string_semantic | 0.900 | Yes |  | | | | | | |
| parties.lenders | array_llm | 0.000 | No |  | 0 | 1 | 25 | 0.00 | 0.00 | 0.00 |