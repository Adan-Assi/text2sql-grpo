# Scripts

Dataset audit scripts for the Text-to-SQL project.

The Gretel scripts are retained for historical reference. The current dataset audit focuses on SQaLe 2.

## Script index

| Script | Dataset | Status | Purpose |
|---|---|---|---|
| `audit_sqale2_query_types.py` | SQaLe 2 | Current | Inspects the first 500 training queries, classifies them by their first SQL keyword, and reports counts and representative examples. Preliminary classification only; does not validate that queries are read-only. |
| `audit_experiment_4.py` | Gretel | Legacy | Initial audit of 100 examples using streaming access, shuffle seed `42`, and buffer size `1,000`. Checks context construction, query execution, SELECT candidates, result sets, and failures. |
| `audit_experiment_5.py` | Gretel | Legacy | Follow-up audit of 100 examples sampled after shuffling the full training split with seed `2026`. Runs the same checks as Experiment 4. |

## Notes

- **Current:** Used for the active dataset and project workflow.
- **Legacy:** Kept for historical reference; not part of the current data pipeline.
- Experiments 4 and 5 are audits of the same Gretel dataset, not separate dataset evaluations.
- Add new scripts to the table with their dataset, status, and a short description of their purpose.