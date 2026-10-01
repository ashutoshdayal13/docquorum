| system | valid JSON | Credit | Research | Resumes | Sports | SEC 10-K/Q | pass rate | Acc (valid) |
|---|---|---|---|---|---|---|---|---|
| **DocQuorum** (Qwen3.8-27B, 1 GPU) | **26/35** | 57/130 (43.8%) | 29/96 (30.2%) | 12/217 (5.5%) | 24/60 (40.0%) | 57/2583 (2.2%) | **179/3086 (5.8%)** | **33.3%** |
| Gemini 3 Flash (paper) | 25/35 | 111/130 (85.4%) | 46/96 (47.9%) | 45/217 (20.7%) | 11/60 (18.3%) | 0/2583 (0.0%) | 213/3086 (6.9%) | 74.7% |
| Gemini 3 Pro (paper) | 21/35 | 110/130 (84.6%) | 5/96 (5.2%) | 46/217 (21.2%) | 8/60 (13.3%) | 0/2583 (0.0%) | 169/3086 (5.5%) | 74.8% |
| GPT-5.2 (paper) | 21/35 | 105/130 (80.8%) | 6/96 (6.2%) | 43/217 (19.8%) | 8/60 (13.3%) | 0/2583 (0.0%) | 162/3086 (5.2%) | 71.7% |
| GPT-5 (paper) | 13/35 | 113/130 (86.9%) | 0/96 (0.0%) | 8/217 (3.7%) | 2/60 (3.3%) | 0/2583 (0.0%) | 123/3086 (4.0%) | 80.4% |
| Claude Sonnet 4.5 (paper) | 15/35 | 0/130 (0.0%) | 47/96 (49.0%) | 46/217 (21.2%) | 8/60 (13.3%) | 0/2583 (0.0%) | 101/3086 (3.3%) | 66.9% |
| Claude Opus 4.5 (paper) | 12/35 | 0/130 (0.0%) | 16/96 (16.7%) | 52/217 (24.0%) | 8/60 (13.3%) | 0/2583 (0.0%) | 76/3086 (2.5%) | 65.0% |
| gold scored against itself (ceiling) | 35/35 | 130/130 (100.0%) | 59/96 (61.5%) | 91/217 (41.9%) | 25/60 (41.7%) | 385/2583 (14.9%) | 690/3086 (22.4%) | 99.9% |

Pass rate = passed fields / (schema keys x documents), an invalid extraction passing none (the paper's Table 5). Acc (valid) = passed / evaluated fields over valid extractions. Judge: qwen3vl at http://localhost:8079/v1 (reasoning off, temperature 0, pass threshold 0.7); paper rows used Gemini 2.5 Flash (Table 5 of arXiv 2602.12247).
