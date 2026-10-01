| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| parties.administrative_agent | string_fuzzy | 1.000 | Yes |  | | | | | | |
| parties.borrower | string_fuzzy | 1.000 | Yes |  | | | | | | |
| terms.beneficial_ownership_certification_required | boolean_exact | 1.000 | Yes |  | | | | | | |
| terms.authorized_officer_definition | string_semantic | 0.000 | No | gold_null | | | | | | |
| terms.loan_commitment.amount | number_exact | 1.000 | Yes |  | | | | | | |
| terms.loan_commitment.currency | string_case_insensitive | 1.000 | Yes |  | | | | | | |
| terms.governing_law | string_semantic | 1.000 | Yes |  | | | | | | |
| terms.agreement_date | string_semantic | 1.000 | Yes |  | | | | | | |
| terms.maturity_date | string_semantic | 1.000 | Yes |  | | | | | | |
| terms.use_of_proceeds | string_semantic | 0.200 | No |  | | | | | | |
| terms.borrowing_request | string_semantic | 0.850 | Yes |  | | | | | | |
| parties.lenders | array_llm | 1.000 | Yes |  | 10 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| parties.lead_arranger | array_llm | 1.000 | Yes |  | 3 | 0 | 1 | 0.75 | 1.00 | 0.86 |