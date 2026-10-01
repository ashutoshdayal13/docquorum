| Path | Metric | Score | Passed | Reason | Matched | Missed | Spurious | P | R | F1 |
|------|--------|-------|--------|--------|---------|--------|----------|---|---|----| 
| meta.report_period | string_exact | 1.000 | Yes |  | | | | | | |
| meta.report_period_end_date | string_exact | 1.000 | Yes |  | | | | | | |
| balance_sheet.commercial_paper_outstanding | array_llm | 1.000 | Yes | both_missing | | | | | | |
| other_disclosures.notional_options_value | array_llm | 1.000 | Yes | both_empty_array | | | | | | |
| meta.company | string_semantic | 1.000 | Yes |  | | | | | | |
| balance_sheet.inventories | array_llm | 1.000 | Yes |  | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.dividends_payable | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.goodwill | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.cash | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.total_debt | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.total_assets | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.current_assets | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.short_term_debt | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.accounts_payable | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.long_term_debt | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.retained_earnings | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.total_receivables | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.total_liabilities | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.accounts_receivable | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.money_market_funds | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.cash_st_investments | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.current_liabilities | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.shareholders_equity | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.marketable_securities | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.revenue | array_llm | 1.000 | Yes |  | 16 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.additional_paid_in_capital | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.short_term_investments | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| balance_sheet.property_plant_and_equipment | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.gross_margin | array_llm | 1.000 | Yes |  | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.gross_profit | array_llm | 1.000 | Yes |  | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.diluted_eps | array_llm | 1.000 | Yes |  | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.basic_eps | array_llm | 1.000 | Yes |  | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.net_income | array_llm | 1.000 | Yes |  | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.cost_of_revenue | array_llm | 1.000 | Yes |  | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.interest_expense | array_llm | 1.000 | Yes |  | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.operating_margin | array_llm | 1.000 | Yes |  | 12 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.net_income_growth | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.revenue_growth | array_llm | 1.000 | Yes |  | 8 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.operating_expenses | array_llm | 1.000 | Yes |  | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.effective_tax_rate | array_llm | 1.000 | Yes |  | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.income_tax_expense | array_llm | 1.000 | Yes |  | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.restructuring_charge | array_llm | 1.000 | Yes |  | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.stock_based_compensation | array_llm | 1.000 | Yes |  | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| other_disclosures.employees | array_llm | 1.000 | Yes |  | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| other_disclosures.notional_swaps_value | array_llm | 1.000 | Yes |  | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| other_disclosures.notional_forwards_value | array_llm | 1.000 | Yes |  | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| income_statement.operating_income | array_llm | 1.000 | Yes |  | 16 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| cash_flow_statement.capex | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| cash_flow_statement.shares_issued | array_llm | 1.000 | Yes |  | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| cash_flow_statement.commercial_paper_issuance | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| cash_flow_statement.share_repurchases | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| cash_flow_statement.dividends_paid | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| cash_flow_statement.financing_cash_flow | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| cash_flow_statement.operating_cash_flow | array_llm | 1.000 | Yes |  | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| cash_flow_statement.shares_repurchased | array_llm | 1.000 | Yes |  | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |