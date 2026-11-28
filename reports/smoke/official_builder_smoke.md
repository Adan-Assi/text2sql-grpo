# Official SQaLe Builder Smoke Test

**Date:** 2026-11-27  
**Status:** Passed

## Purpose

Verify that `scripts/audit_sqale2_fidelity.py` runs successfully after restoring the official SQaLe database builder.

## Test scope

- Split: test
- Schemas: 1
- Questions per schema: 1
- Random seed: 0
- Builder: official `sqale==0.2.0` `build_database`

## Command

```bash
python scripts/audit_sqale2_fidelity.py \
  --schemas-dir data/sqale2/schemas_test/data \
  --queries-dir data/sqale2/queries_test/data \
  --split test \
  --n-schemas 1 \
  --max-questions-per-schema 1 \
  --seed 0 \
  --out audit_out/official_builder_smoke
````

## **Results**

| Metric                                | Result |
| ------------------------------------- | ------ |
| Examples audited                      | 1      |
| Successful examples (`ok`)            | 1      |
| Execution mismatches                  | 0      |
| `rows_missing` fidelity flags         | 2      |
| Maximum stored result length observed | 5      |

Schema: `schema_010628`

## **Conclusion**

The audit script successfully ran using the official builder. The example executed without a mismatch.

The two `rows_missing` flags are recorded as fidelity observations. They do not automatically make the example ineligible under the project's reconstruction policy.

## **Limitations**

This was a smoke test of one schema and one question. It verifies basic execution of the restored builder path, not dataset-wide reconstruction fidelity or dataset suitability.
