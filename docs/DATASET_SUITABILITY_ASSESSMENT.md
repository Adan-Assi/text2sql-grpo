# Dataset Suitability Assessment: Gretel Synthetic Text-to-SQL

**Status:** Initial investigation in progress\
**Candidate dataset:**
[`gretelai/synthetic_text_to_sql`](https://huggingface.co/datasets/gretelai/synthetic_text_to_sql)\
**Project:** Text-to-SQL with execution-based rewards and GRPO

------------------------------------------------------------------------

## Purpose

This document records the investigation into whether the Gretel
Synthetic Text-to-SQL dataset is suitable for this project.

The goal is to establish whether its examples can reliably become executable Text-to-SQL tasks:

1.  Provide a model with a natural-language question and relevant
    database schema.
2.  Construct the corresponding database.
3.  Generate SQL from the model.
4.  Execute the generated SQL against the database.
5.  Compare its result with the result of the reference SQL.
6.  Use that comparison as part of an execution-based reward for GRPO.

------------------------------------------------------------------------

## 1. Initial dataset-card review

Before running code, we reviewed the dataset card on Hugging Face.

The card describes a detailed synthetic Text-to-SQL dataset with
training and test splits, natural-language prompts, SQL contexts,
reference SQL, explanations, and metadata such as domain and SQL
complexity.

The dataset was considered promising because its `sql_context` field
appears to provide database setup statements. If those statements can be
executed successfully, they may allow us to construct SQLite databases
for execution-based evaluation.

------------------------------------------------------------------------

## 2. Experiment 1: Inspect the dataset schema and sample records

### Goal

Inspect the actual dataset rather than relying only on the dataset card.

We want to establish:

-   Which columns and data types are actually provided.
-   What a natural-language prompt looks like.
-   How database context is represented.
-   What the reference SQL looks like.
-   Whether the fields contain enough information to begin constructing
    executable Text-to-SQL examples.

We use streaming so that we can inspect a few records without
downloading the entire training split.

### Code

``` python
from datasets import load_dataset

dataset = load_dataset(
    "gretelai/synthetic_text_to_sql",
    split="train",
    streaming=True,
)

print("Dataset features:")
print(dataset.features)

print("\nFirst 2 examples:")
for i, example in enumerate(dataset):
    print(f"\n{'=' * 60}")
    print(f"EXAMPLE {i + 1}")

    for key, value in example.items():
        text = str(value)
        print(f"\n{key} ({len(text)} characters):")
        print(text[:1500])
        if len(text) > 1500:
            print("... [truncated]")

    if i == 1:
        break
```

### Results

The dataset loaded successfully. The Hugging Face Hub displayed an
unauthenticated-request warning, but the data was retrieved.

**Observed dataset features:**

``` text
{
    'id': Value('int32'),
    'domain': Value('string'),
    'domain_description': Value('string'),
    'sql_complexity': Value('string'),
    'sql_complexity_description': Value('string'),
    'sql_task_type': Value('string'),
    'sql_task_type_description': Value('string'),
    'sql_prompt': Value('string'),
    'sql_context': Value('string'),
    'sql': Value('string'),
    'sql_explanation': Value('string')
}
```

**Example 1 --- ID 5097**

``` text
domain: forestry
sql_complexity: single join
sql_complexity_description: only one join (specify inner, outer, cross)
sql_task_type: analytics and reporting

sql_prompt:
What is the total volume of timber sold by each salesperson, sorted by salesperson?

sql_context:
CREATE TABLE salesperson (salesperson_id INT, name TEXT, region TEXT);
INSERT INTO salesperson (salesperson_id, name, region)
VALUES (1, 'John Doe', 'North'), (2, 'Jane Smith', 'South');
CREATE TABLE timber_sales (sales_id INT, salesperson_id INT, volume REAL, sale_date DATE);
INSERT INTO timber_sales (sales_id, salesperson_id, volume, sale_date)
VALUES (1, 1, 120, '2021-01-01'), (2, 1, 150, '2021-02-01'), (3, 2, 180, '2021-01-01');

sql:
SELECT salesperson_id, name, SUM(volume) as total_volume
FROM timber_sales
JOIN salesperson ON timber_sales.salesperson_id = salesperson.salesperson_id
GROUP BY salesperson_id, name
ORDER BY total_volume DESC;

sql_explanation:
Joins timber_sales and salesperson tables, groups sales by salesperson,
calculates total volume sold by each salesperson, and orders the results
by total volume in descending order.
```

**Example 2 --- ID 5098**

``` text
domain: defense industry
sql_complexity: aggregation
sql_task_type: analytics and reporting

sql_prompt:
List all the unique equipment types and their corresponding total
maintenance frequency from the equipment_maintenance table.

sql_context:
CREATE TABLE equipment_maintenance (
    equipment_type VARCHAR(255),
    maintenance_frequency INT
);

sql:
SELECT equipment_type,
       SUM(maintenance_frequency) AS total_maintenance_frequency
FROM equipment_maintenance
GROUP BY equipment_type;

sql_explanation:
This query groups the equipment_maintenance table by equipment_type
and calculates the sum of maintenance_frequency for each group, then
returns the equipment_type and the corresponding total_maintenance_frequency.
```

### Conclusion and observations

The observed fields match the expected structure from the dataset card.

The fields appear useful for our intended pipeline:

| Dataset field | Potential project use |
|---|---|
| `sql_prompt` | Natural-language question shown to the model |
| `sql_context` | Database schema and possibly data used to construct the database |
| `sql` | Reference SQL query |
| `sql_explanation` | Optional analysis or future auxiliary use |
| `sql_complexity` | Filtering and difficulty analysis |
| `sql_task_type` | Filtering and task distribution analysis |
| `domain` | Domain distribution and possible held-out-domain evaluation |
| `id` | Source-record identifier |

An important difference appeared between the two examples:

- Example 1 includes both `CREATE TABLE` and `INSERT INTO` statements.
- Example 2 includes a `CREATE TABLE` statement but no `INSERT INTO` statements.

This means we cannot assume that every context contains populated tables. An empty database can make execution-based comparisons less informative.

The next experiment should test whether the contexts can actually be constructed and whether the reference SQL executes against them.

------------------------------------------------------------------------

## 3. Experiment 2: Test SQLite database construction and reference SQL execution

### Goal

Move beyond inspecting SQL as text and test whether the examples work in
SQLite.

For each of the first two examples:

1.  Create an in-memory SQLite database.
2.  Execute `sql_context` to construct the database.
3.  Check whether the context contains `INSERT INTO` statements.
4.  Execute the reference SQL.
5.  Print the result columns and returned rows.

Python's built-in `sqlite3` library is sufficient; no additional package
is required.

### Code

``` python
import sqlite3
from datasets import load_dataset

dataset = load_dataset(
    "gretelai/synthetic_text_to_sql",
    split="train",
    streaming=True,
)

for i, example in enumerate(dataset.take(2), start=1):
    print(f"\n{'=' * 60}")
    print(f"EXAMPLE {i}: ID {example['id']}")
    print(f"Question: {example['sql_prompt']}")

    conn = sqlite3.connect(":memory:")

    try:
        conn.executescript(example["sql_context"])
        print("Database construction: SUCCESS")

        has_inserts = "INSERT INTO" in example["sql_context"].upper()
        print(f"Contains INSERT statements: {has_inserts}")

        cursor = conn.execute(example["sql"])
        rows = cursor.fetchall()

        print("Gold SQL execution: SUCCESS")
        print("Result columns:", [col[0] for col in cursor.description])
        print("Number of result rows:", len(rows))
        print("Result:", rows[:10])

    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

    finally:
        conn.close()
```

### Results

**Example 1 --- ID 5097**

``` text
Database construction: SUCCESS
Contains INSERT statements: True
FAILED: OperationalError: ambiguous column name: salesperson_id
```

The database was constructed, but the reference SQL failed.

Both joined tables contain a `salesperson_id` column. The query selects
`salesperson_id` without qualifying it with a table name, so SQLite
cannot determine which column is intended.

**Example 2 --- ID 5098**

``` text
Database construction: SUCCESS
Contains INSERT statements: False
Gold SQL execution: SUCCESS
Result columns: ['equipment_type', 'total_maintenance_frequency']
Number of result rows: 0
Result: []
```

The database was constructed and the reference SQL executed
successfully, but the context contained no INSERT statements and the
query returned no rows.

### Conclusion and observations

These two examples reveal two different concerns:

1.  A database context can be valid while its reference SQL is invalid.
2.  A reference SQL query can execute successfully while returning an
    empty result because the database contains no records.

For execution-based rewards, both cases matter.

-   A failed reference query cannot provide a reliable reference result
    without correction or exclusion.
-   An empty reference result can provide a weak reward signal: many
    unrelated queries may also return an empty result.

Two examples are not enough to estimate how common these issues are. A
larger sample is needed.

------------------------------------------------------------------------

## 4. Experiment 3: Initial 100-example execution audit

### Goal

Get an initial quantitative picture of the dataset by inspecting 100
examples from the training split.

The audit uses:

-   Streaming to avoid downloading the entire split.
-   A shuffle buffer of 1,000 records with a fixed seed.
-   SQLite in-memory databases.
-   Counters for context construction, INSERT statements, SQL execution,
    SELECT-like result metadata, and empty/non-empty results.
-   Error collection to identify recurring failure patterns.

This is an exploratory audit, not yet a definitive estimate of the
usable dataset size.

### Code

``` python
import sqlite3
import re
from collections import Counter
from datasets import load_dataset

dataset = load_dataset(
    "gretelai/synthetic_text_to_sql",
    split="train",
    streaming=True,
).shuffle(seed=42, buffer_size=1000)

stats = Counter()
errors = Counter()
examples = []

for example in dataset.take(100):
    stats["total"] += 1
    conn = sqlite3.connect(":memory:")

    try:
        conn.executescript(example["sql_context"])
        stats["context_success"] += 1

        has_inserts = bool(
            re.search(r"\bINSERT\s+INTO\b", example["sql_context"], re.I)
        )
        if has_inserts:
            stats["has_inserts"] += 1

        cursor = conn.execute(example["sql"])
        rows = cursor.fetchall()

        stats["sql_success"] += 1

        if cursor.description is not None:
            stats["select_queries"] += 1

        if rows:
            stats["nonempty_results"] += 1
        else:
            stats["empty_results"] += 1

    except Exception as e:
        errors[type(e).__name__ + ": " + str(e)] += 1
        examples.append((example["id"], str(e)))

    finally:
        conn.close()

print("\nAUDIT RESULTS")
for key, value in stats.items():
    print(f"{key}: {value}")

print("\nTOP EXECUTION ERRORS")
for error, count in errors.most_common(10):
    print(f"{count}x {error}")

print("\nFAILED EXAMPLE IDS")
for example_id, error in examples[:10]:
    print(f"ID {example_id}: {error}")
```

### Results

``` text
AUDIT RESULTS
total: 100
context_success: 98
has_inserts: 77
sql_success: 79
select_queries: 74
nonempty_results: 61
empty_results: 18

TOP EXECUTION ERRORS
4x OperationalError: near "1": syntax error
2x OperationalError: near "FROM": syntax error
2x OperationalError: no such function: YEAR
1x OperationalError: no such column: gender
1x OperationalError: unrecognized token: ":"
1x OperationalError: incomplete input
1x OperationalError: table ocean_species already exists
1x OperationalError: no such table: ExcavationSites
1x OperationalError: ambiguous column name: store_id
1x OperationalError: near "SCHEMA": syntax error

FAILED EXAMPLE IDS
ID 5956: no such column: gender
ID 5244: near "1": syntax error
ID 5373: unrecognized token: ":"
ID 5158: near "FROM": syntax error
ID 5717: no such function: YEAR
ID 5850: incomplete input
ID 6000: table ocean_species already exists
ID 5654: no such table: ExcavationSites
ID 5407: ambiguous column name: store_id
ID 5142: near "1": syntax error
```

### Interpretation

**Database context construction**

-   98 of 100 contexts were constructed successfully.
-   2 contexts failed during construction.

**Contexts with data insertion**

-   77 of 100 contexts contained at least one `INSERT INTO` statement.
-   This is encouraging, but the presence of an INSERT statement does
    not prove that every relevant table is populated or that the
    inserted data is sufficient for the query.

**Reference SQL execution**

-   79 of 100 examples reached successful completion of `conn.execute()`
    and `fetchall()`.
-   21 examples raised an exception somewhere in the combined
    context/query `try` block.
-   74 successful executions had a non-`None` `cursor.description`,
    which is a useful indicator of result-producing statements such as
    SELECT queries.

**Returned rows**

-   61 successful executions returned at least one row.
-   18 successful executions returned no rows.

These counts need careful interpretation. The script increments
`nonempty_results` or `empty_results` for every successful execution,
not only SELECT queries. It also does not separate context-construction
exceptions from reference-query exceptions. Therefore, the counts should
not yet be treated as the exact number or percentage of usable SELECT
examples.

### Error patterns observed

The failures suggest several categories of issues:

| Observed error | Possible explanation |
|---|---|
| `no such function: YEAR` | SQL dialect incompatibility: SQLite does not provide `YEAR()` by default |
| `ambiguous column name` | A column used in a join is not qualified with its table |
| `no such column` | Reference query and constructed schema may disagree |
| `no such table` | Context may be incomplete or inconsistent with the query |
| `table already exists` | Context may contain duplicate or conflicting table creation |
| Syntax errors | Malformed SQL or syntax not accepted by SQLite |
| `unrecognized token` / `incomplete input` | Potentially malformed or incomplete SQL/context |

Some issues may be addressable through carefully controlled compatibility handling. Others may indicate flawed examples that should be excluded.

We should not automatically rewrite reference queries at this stage. Any correction policy needs to be explicit and validated so that we do not silently hide source-data quality problems.

### Conclusion and next steps

The initial sample is encouraging enough to continue evaluating Gretel,
but it is not sufficient to use the dataset as-is.

Positive signals:

-   Most sampled contexts could be constructed in SQLite.
-   Most sampled contexts contained INSERT statements.
-   Many reference queries executed and returned rows.

Concerns:

-   Some reference queries failed.
-   Some contexts or queries appear inconsistent.
-   Some SQL uses syntax or functions unsupported by SQLite.
-   Some successful queries returned empty results.
-   The current audit does not distinguish all failure stages or isolate
    SELECT-only statistics.

**Decision so far:** Keep Gretel as the leading candidate and continue
the technical evaluation.

------------------------------------------------------------------------

## 5. Experiment 4: Separate context and query validation

### Goal

Improve the initial audit by tracking database construction and reference SQL execution independently.

Experiment 3 combined both operations in one `try` block. As a result, it could identify failed examples but could not reliably distinguish whether the failure occurred during context construction or query execution.

This experiment separates the stages and adds more precise SELECT-result statistics.

For each of 100 sampled examples, the audit checks:

1. Whether the SQL context executes successfully.
2. Whether the raw context contains `INSERT INTO` statements.
3. Whether the reference query begins with `SELECT` or `WITH`.
4. Whether the reference query executes successfully.
5. Whether a SELECT candidate produces a result set and returns rows.
6. Which error occurred and at which stage.

The script also retains up to 10 representative failed examples, including their IDs, failure stages, error messages, SQL contexts, and reference queries.

### Code

```python
import re
import sqlite3
from collections import Counter
from datasets import load_dataset

dataset = load_dataset(
    "gretelai/synthetic_text_to_sql",
    split="train",
    streaming=True,
).shuffle(seed=42, buffer_size=1000)

stats = Counter()
errors = Counter()
failed_examples = []

for example in dataset.take(100):
    stats["total"] += 1

    context = example["sql_context"]
    query = example["sql"]

    has_inserts = bool(
        re.search(r"\bINSERT\s+INTO\b", context, re.IGNORECASE)
    )

    if has_inserts:
        stats["contexts_with_inserts"] += 1
    else:
        stats["contexts_without_inserts"] += 1

    is_select_candidate = bool(
        re.match(r"^\s*(SELECT|WITH)\b", query, re.IGNORECASE)
    )

    if is_select_candidate:
        stats["select_candidates"] += 1
    else:
        stats["non_select_candidates"] += 1

    conn = sqlite3.connect(":memory:")

    try:
        # Stage 1: Construct the database.
        try:
            conn.executescript(context)
            stats["context_success"] += 1

        except Exception as e:
            stats["context_failure"] += 1
            errors[f"Context: {type(e).__name__}: {e}"] += 1

            if len(failed_examples) < 10:
                failed_examples.append({
                    "id": example["id"],
                    "stage": "Context construction",
                    "error": f"{type(e).__name__}: {e}",
                    "context": context[:1500],
                    "query": query[:1000],
                })

            continue

        # Stage 2: Execute the reference query.
        try:
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            stats["query_success"] += 1

            # Stage 3: Check SELECT results.
            if is_select_candidate:
                if cursor.description is not None:
                    stats["select_result_sets"] += 1

                    if rows:
                        stats["select_nonempty_results"] += 1
                    else:
                        stats["select_empty_results"] += 1
                else:
                    stats["select_candidates_without_result_set"] += 1

        except Exception as e:
            stats["query_failure"] += 1
            errors[f"Query: {type(e).__name__}: {e}"] += 1

            if len(failed_examples) < 10:
                failed_examples.append({
                    "id": example["id"],
                    "stage": "Reference query execution",
                    "error": f"{type(e).__name__}: {e}",
                    "context": context[:1500],
                    "query": query[:1000],
                })

    finally:
        conn.close()


print("\n" + "=" * 60)
print("EXPERIMENT 4: SEPARATE CONTEXT AND QUERY VALIDATION")
print("=" * 60)

print("\nAUDIT RESULTS")
for key, value in stats.items():
    print(f"{key}: {value}")

print("\nTOP ERRORS BY STAGE")
for error, count in errors.most_common(15):
    print(f"{count}x {error}")

print("\n" + "=" * 60)
print("REPRESENTATIVE FAILED EXAMPLES")
print("=" * 60)

for item in failed_examples:
    print(f"\nExample ID: {item['id']}")
    print(f"Failure stage: {item['stage']}")
    print(f"Error: {item['error']}")

    print("\nSQL context (first 1500 characters):")
    print(item["context"])

    print("\nReference query (first 1000 characters):")
    print(item["query"])

    print("\n" + "-" * 60)
```

### Results

#### Audit statistics

```text
EXPERIMENT 4: SEPARATE CONTEXT AND QUERY VALIDATION

AUDIT RESULTS
total: 100
contexts_with_inserts: 78
select_candidates: 93
context_success: 98
query_success: 79
select_result_sets: 74
select_nonempty_results: 61
query_failure: 19
contexts_without_inserts: 22
select_empty_results: 13
non_select_candidates: 7
context_failure: 2
```

#### Top errors by stage

```text
TOP ERRORS BY STAGE
4x Query: OperationalError: near "1": syntax error
2x Query: OperationalError: near "FROM": syntax error
2x Query: OperationalError: no such function: YEAR
1x Query: OperationalError: no such column: gender
1x Query: OperationalError: unrecognized token: ":"
1x Context: OperationalError: incomplete input
1x Query: OperationalError: table ocean_species already exists
1x Query: OperationalError: no such table: ExcavationSites
1x Query: OperationalError: ambiguous column name: store_id
1x Context: OperationalError: near "SCHEMA": syntax error
1x Query: OperationalError: no such table: Dishes
1x Query: OperationalError: no such function: DATE_FORMAT
1x Query: OperationalError: no such function: PERCENTAGE
1x Query: OperationalError: no such table: projects
1x Query: OperationalError: no such table: client_assets
```

#### Representative failed examples

The script retained the first 10 failed examples encountered:

| Example ID | Failure stage | Error |
|---|---|---|
| 5956 | Reference query | `no such column: gender` |
| 5244 | Reference query | `near "1": syntax error` |
| 5373 | Reference query | `unrecognized token: ":"` |
| 5158 | Reference query | `near "FROM": syntax error` |
| 5717 | Reference query | `no such function: YEAR` |
| 5850 | Context construction | `incomplete input` |
| 6000 | Reference query | `table ocean_species already exists` |
| 5654 | Reference query | `no such table: ExcavationSites` |
| 5407 | Reference query | `ambiguous column name: store_id` |
| 5142 | Reference query | `near "1": syntax error` |

The full context and reference SQL for these examples were also printed by the script for manual inspection.

### Interpretation

#### Database context construction

- 98 of 100 contexts were constructed successfully.
- 2 contexts failed during construction.
- The two context failures were an incomplete INSERT statement (ID 5850) and unsupported or malformed context syntax near `SCHEMA`.

This indicates that database construction itself is relatively reliable in this sample, although some contexts are incomplete or incompatible with SQLite.

#### Contexts containing INSERT statements

- 78 of 100 contexts contained at least one `INSERT INTO` statement.
- 22 contexts contained no INSERT statements.

This differs from Experiment 3, which counted 77 contexts with INSERT statements.

The difference is explained by the improved script: Experiment 4 checks the raw context before attempting execution, so contexts that fail construction are also included in the INSERT count.

The presence of INSERT statements does not guarantee that all relevant tables are populated or that the inserted data is sufficient for the query.

#### Reference SQL execution

- 79 reference queries executed successfully.
- 19 reference queries failed after successful context construction.
- 2 examples could not reach query execution because context construction failed.

The separation confirms that most failures in this sample occur during reference query execution rather than database construction.

#### SELECT candidates and returned rows

- 93 queries began with `SELECT` or `WITH`.
- 7 queries began with another SQL statement type.
- 74 SELECT candidates produced result sets.
- 61 returned at least one row.
- 13 returned no rows.

The SELECT classification is based on a simple first-keyword check. A query beginning with `WITH` is counted as a SELECT candidate, although a CTE can also precede an UPDATE, DELETE, or INSERT statement. Therefore, this is an initial classification rather than a complete SQL statement parser.

The 13 empty results are worth investigating because an execution-based reward may be less informative when the reference result is empty. However, an empty result is not automatically an invalid example.

### Error patterns observed

The failures reveal several distinct categories of problems:

| Observed error | Example | Possible explanation |
|---|---|---|
| `no such column` | ID 5956 | Reference query and constructed schema disagree |
| SQL dialect incompatibility | IDs 5244, 5158, 5717 | Query uses functions or syntax unsupported by SQLite, such as `DATE_SUB`, `CURDATE()`, `EXTRACT`, or `YEAR()` |
| Invalid SQL syntax | ID 5373 | Query contains syntax SQLite cannot parse, such as `PERCENTAGE :=` |
| `no such table` | ID 5654 | Query references a table absent from the context |
| Ambiguous column name | ID 5407 | A column used in a join is not qualified with its table |
| Incomplete context | ID 5850 | Context ends with an unfinished INSERT statement |
| Duplicate table creation | ID 6000 | Reference query attempts to create a table that already exists in the context |

Some issues may be addressable through carefully controlled compatibility handling. Others may indicate flawed examples that should be excluded.

We should not automatically rewrite reference queries at this stage. Any correction policy needs to be explicit and validated so that we do not silently hide source-data quality problems.

### Comparison with Experiment 3

The two experiments produced consistent results for the main execution metrics:

| Measurement | Experiment 3 | Experiment 4 |
|---|---:|---:|
| Total examples | 100 | 100 |
| Context construction success | 98 | 98 |
| Successful SQL executions | 79 | 79 |
| SELECT-like result sets | 74 | 74 |
| Non-empty results (all successful statements in Experiment 3) | 61 | 61 |
| Empty results | 18 | 13 SELECT results |
| Contexts with INSERT statements | 77 | 78 |

The difference in empty results is due to the improved classification. Experiment 3 counted empty results from all successfully executed statements, whereas Experiment 4 counts empty results specifically for SELECT candidates.

The INSERT count also changed because Experiment 4 checks the raw context independently of context construction success.

### Conclusion and next steps

Experiment 4 provides a clearer picture of the dataset's technical suitability.

Positive signals:

- 98% of sampled database contexts could be constructed in SQLite.
- 79% of sampled reference queries executed successfully.
- 61 SELECT candidates returned non-empty results.
- The audit now distinguishes context failures from query failures and retains representative examples for inspection.

Concerns:

- Some reference queries disagree with their database schemas.
- Some queries reference missing tables or ambiguous columns.
- Some SQL uses functions or syntax unsupported by SQLite.
- Some contexts are incomplete or malformed.
- 13 successful SELECT candidates returned empty results.
- Successful execution alone does not establish that the reference query correctly answers its natural-language question.

---

## 6. Experiment 5: Full-dataset random sample audit

### Goal

Re-evaluate the dataset's context construction and reference SQL execution reliability using a new sample selected by shuffling the entire training split.

Experiments 3 and 4 used streaming with a shuffle buffer of 1,000 examples. Since the first 100 examples were selected from that limited buffer, they did not constitute a random sample from the entire 100,000-example training split.

This experiment addresses that limitation by:
- Loading the **complete** training split without streaming.
- Shuffling the entire dataset using a **fixed random seed**.
- Selecting 100 examples from the shuffled dataset.
- Repeating the same validation checks as Experiment 4.
- Comparing the results to determine whether the earlier observations remain broadly consistent across a different sample.

### Methodology

The experiment uses:

- **Dataset:** `gretelai/synthetic_text_to_sql`
- **Split:** `train`
- **Training split size:** 100,000 examples
- **Sample size:** 100 examples
- **Random seed:** 2026
- **Shuffle method:** Full-dataset shuffle using Hugging Face `Dataset.shuffle()`, followed by selection of the first 100 shuffled examples.

Unlike the previous streaming approach, this loads the complete training split and shuffles its full set of records before selecting the sample.

Each selected example is evaluated in three stages:

1. **Context construction:** Execute `sql_context` in an in-memory SQLite database.
2. **Reference query execution:** Execute the reference SQL query against the constructed database.
3. **Result-set validation:** For queries classified as SELECT candidates using the same preliminary `SELECT`/`WITH` regex as Experiment 4, check whether execution produces a result set and whether that result set is empty.

The experiment also records whether contexts contain INSERT statements and collects representative failures.

### Code

The script is saved as `scripts/audit_experiment_5.py`.

```python
import re
import sqlite3
from collections import Counter

from datasets import load_dataset


# Load the complete training split (not streaming).
dataset = load_dataset(
    "gretelai/synthetic_text_to_sql",
    split="train",
)

# Shuffle the entire split, then select 100 records.
shuffled_dataset = dataset.shuffle(seed=2026)
sample = shuffled_dataset.select(range(100))

stats = Counter()
errors = Counter()
failed_examples = []

sampled_ids = []

for example in sample:
    stats["total"] += 1
    sampled_ids.append(example["id"])

    context = example["sql_context"]
    query = example["sql"]

    # Check whether the context contains INSERT statements.
    has_inserts = bool(
        re.search(r"\bINSERT\s+INTO\b", context, re.IGNORECASE)
    )

    if has_inserts:
        stats["contexts_with_inserts"] += 1
    else:
        stats["contexts_without_inserts"] += 1

    # Preliminary classification, matching Experiment 4.
    is_select_candidate = bool(
        re.match(r"^\s*(SELECT|WITH)\b", query, re.IGNORECASE)
    )

    if is_select_candidate:
        stats["select_candidates"] += 1
    else:
        stats["non_select_candidates"] += 1

    conn = sqlite3.connect(":memory:")

    try:
        # Stage 1: Construct the database.
        try:
            conn.executescript(context)
            stats["context_success"] += 1

        except Exception as e:
            stats["context_failure"] += 1
            errors[f"Context: {type(e).__name__}: {e}"] += 1

            if len(failed_examples) < 10:
                failed_examples.append({
                    "id": example["id"],
                    "stage": "Context construction",
                    "error": f"{type(e).__name__}: {e}",
                    "context": context[:1500],
                    "query": query[:1000],
                })

            continue

        # Stage 2: Execute the reference query.
        try:
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            stats["query_success"] += 1

            # Stage 3: Check SELECT results.
            if is_select_candidate:
                if cursor.description is not None:
                    stats["select_result_sets"] += 1

                    if rows:
                        stats["select_nonempty_results"] += 1
                    else:
                        stats["select_empty_results"] += 1
                else:
                    stats["select_candidates_without_result_set"] += 1

        except Exception as e:
            stats["query_failure"] += 1
            errors[f"Query: {type(e).__name__}: {e}"] += 1

            if len(failed_examples) < 10:
                failed_examples.append({
                    "id": example["id"],
                    "stage": "Reference query execution",
                    "error": f"{type(e).__name__}: {e}",
                    "context": context[:1500],
                    "query": query[:1000],
                })

    finally:
        conn.close()


# Print results.
print("\n" + "=" * 60)
print("EXPERIMENT 5: FULL-DATASET RANDOM SAMPLE AUDIT")
print("=" * 60)

print("\nSAMPLE INFORMATION")
print("Training split size:", len(dataset))
print("Sample size:", len(sample))
print("Random seed: 2026")
print("Sampled example IDs:")
print(sampled_ids)

print("\nAUDIT RESULTS")
for key, value in stats.items():
    print(f"{key}: {value}")

print("\nTOP ERRORS BY STAGE")
for error, count in errors.most_common(15):
    print(f"{count}x {error}")

print("\n" + "=" * 60)
print("REPRESENTATIVE FAILED EXAMPLES")
print("=" * 60)

for item in failed_examples:
    print(f"\nExample ID: {item['id']}")
    print(f"Failure stage: {item['stage']}")
    print(f"Error: {item['error']}")

    print("\nSQL context (first 1500 characters):")
    print(item["context"])

    print("\nReference query (first 1000 characters):")
    print(item["query"])

    print("\n" + "-" * 60)
```

### Results

The complete training split was loaded for this experiment. The dataset's test split was also downloaded and loaded during the earlier dataset inspection, but it was not used in this audit.

#### Sample information

| Metric | Result |
|---|---:|
| Training split size | 100,000 |
| Sample size | 100 |
| Random seed | 2026 |
| Sampling method | Full-dataset shuffle |

The sampled example IDs were distributed across the training split, rather than concentrated in the initial portion of the dataset.

#### Audit results

| Metric | Count |
|---|---:|
| Total examples | 100 |
| Contexts with INSERT statements | 75 |
| Contexts without INSERT statements | 25 |
| Preliminary SELECT/WITH candidates | 86 |
| Other query candidates | 14 |
| Context construction success | 93 |
| Context construction failure | 7 |
| Reference query success | 79 |
| Reference query failure | 14 |
| SELECT result sets | 67 |
| Non-empty SELECT results | 61 |
| Empty SELECT results | 6 |

#### Top errors by stage

| Count | Stage | Error |
|---:|---|---|
| 4 | Context | `near "SCHEMA": syntax error` |
| 2 | Query | `no such function: YEAR` |
| 1 | Query | `near "1": syntax error` |
| 1 | Context | `no such table: main.website_articles` |
| 1 | Query | `no such function: STDDEV` |
| 1 | Query | `near "10": syntax error` |
| 1 | Context | `incomplete input` |
| 1 | Query | `near "UPDATE": syntax error` |
| 1 | Context | `unknown database public` |
| 1 | Query | `unrecognized token: ":"` |
| 1 | Query | `no such column: day` |
| 1 | Query | `misuse of aggregate function AVG()` |
| 1 | Query | `near "3": syntax error` |
| 1 | Query | `no such function: DATE_TRUNC` |
| 1 | Query | `no such column: cs.product_type` |

#### Representative failed examples

The script retained and printed the first 10 failed examples.

| Example ID | Failure stage | Error | Observation |
|---|---|---|---|
| 63221 | Reference query execution | `no such function: YEAR` | Reference query uses a function unavailable in SQLite. |
| 4399 | Context construction | `near "SCHEMA": syntax error` | Context uses `CREATE SCHEMA` and schema-qualified table names. |
| 76875 | Context construction | `near "SCHEMA": syntax error` | Context uses multiple schemas and schema-qualified tables. |
| 22667 | Reference query execution | `near "1": syntax error` | Reference query uses `DATE_SUB` and `INTERVAL`. |
| 38996 | Context construction | `no such table: main.website_articles` | A view references tables that have not been created. |
| 20409 | Reference query execution | `no such function: STDDEV` | Reference query uses an aggregate function unavailable in SQLite by default. |
| 37051 | Reference query execution | `near "10": syntax error` | Reference query uses `DATE_SUB` and `NOW()`. |
| 36111 | Context construction | `incomplete input` | SQL context contains an incomplete INSERT statement. |
| 52436 | Context construction | `near "SCHEMA": syntax error` | Context uses `CREATE SCHEMA` and `USE`. |
| 81174 | Reference query execution | `near "UPDATE": syntax error` | Reference query uses a data-modifying CTE with UPDATE and RETURNING. |

### Interpretation

#### 1. Context construction reliability

93 out of 100 contexts were successfully constructed (93%).

This is lower than Experiment 4, which recorded 98 successful contexts out of 100 (98%).

The seven failures include:
- Unsupported schema creation and schema-qualified table syntax.
- Missing dependencies referenced by views.
- Incomplete SQL context statements.

This indicates that context construction issues are not limited to the initial sample.

#### 2. Reference query execution reliability

79 out of 93 successfully constructed databases had reference queries that executed successfully.

This gives a conditional execution success rate of approximately 85.0%. The count includes all successfully executed statements, not exclusively read-only SELECT queries.

The remaining 14 queries failed for reasons including:
- SQL dialect incompatibilities.
- Unsupported functions.
- Missing columns.
- Invalid SQL syntax.
- Unsupported data-modifying CTEs.

The same general categories of problems appeared in Experiment 4.

#### 3. SELECT result availability

Of the 86 preliminary SELECT/WITH candidates:
- 67 successfully produced result sets.
- 61 produced non-empty results.
- 6 produced empty results.
The classification is based on the query's opening keyword, not a full SQL statement-type analysis

The 61 non-empty results represent 91.0% of the 67 candidate-query result sets.

The proportion of empty results was lower in Experiment 5 (6/67, approximately 9.0%) than in Experiment 4 (13/74, approximately 17.6%). However, the difference was not statistically significant at the 5% level. The two samples therefore do not provide sufficient evidence to conclude that the underlying empty-result rates differ.

However, the SELECT classification remains preliminary because the regular expression classifies every query beginning with `WITH` as a SELECT candidate, including data-modifying CTEs.

#### 4. Database population

75 contexts contained INSERT statements, while 25 did not.

This is broadly consistent with Experiment 4, which found 78 contexts with INSERT statements and 22 without them.

The presence of INSERT statements does not guarantee that the database is populated correctly, but it provides an initial indication of whether sample data is included in the context.

### Comparison with Experiment 4

| Metric | Experiment 4 | Experiment 5 |
|---|---:|---:|
| Sample size | 100 | 100 |
| Sampling method | Streaming shuffle, buffer size 1,000 | Full-dataset shuffle |
| Context construction success | 98 | 93 |
| Context construction failure | 2 | 7 |
| Contexts with INSERT statements | 78 | 75 |
| Contexts without INSERT statements | 22 | 25 |
| Preliminary SELECT/WITH candidates | 93 | 86 |
| Other query candidates | 7 | 14 |
| Reference query success | 79 | 79 |
| Reference query failure | 19 | 14 |
| SELECT result sets | 74 | 67 |
| Non-empty SELECT results | 61 | 61 |
| Empty SELECT results | 13 | 6 |

The number of successful reference queries is identical (79), although the two experiments used different samples.

Compared with Experiment 4, the full-dataset random sample had:
- Five fewer successful context constructions (93 vs. 98).
- Five fewer reference query failures (14 vs. 19).
- Seven fewer candidate-query result sets (67 vs. 74).
- The same number of non-empty candidate-query results (61 in each sample).
These differences describe the observed samples and should not be interpreted as evidence of meaningful differences in the underlying dataset. Experiment 4 used a streaming shuffle with a buffer of 1,000 examples, whereas Experiment 5 shuffled the complete training split. The two sampling methods therefore do not provide equally strong evidence about dataset-wide rates.

The identical count of 61 non-empty results is coincidental and does not imply that the samples have identical characteristics.

### Comparison and conclusions

Experiment 5 provides a stronger sampling basis than Experiments 3 and 4 because it selects records after shuffling the complete training split.

The results broadly reinforce the earlier observations:

1. Most sampled database contexts can be constructed in SQLite.
2. A meaningful proportion of reference queries fail to execute.
3. SQL dialect incompatibilities and malformed or incomplete SQL are recurring problems.
4. Some contexts lack INSERT statements.
5. A substantial number of executable SELECT queries produce non-empty results.

The results also show that the exact failure rates vary between samples. Context construction success was 98% in Experiment 4 and 93% in Experiment 5, while reference query success was 79 in both samples.

**Important limitation:** Although Experiment 5 uses a full-dataset shuffle, it still examines only 100 examples. It provides a more defensible independent sample than the previous streaming approach, but it does not establish precise dataset-wide rates or guarantee that every domain and SQL complexity category is adequately represented.

The findings are sufficient to identify recurring technical issues and motivate filtering, but not to claim that the entire dataset has the same success rates observed in these samples.

### Conclusion

Experiment 5 provides further evidence that the issues identified in the earlier audits are also present in a sample drawn from the full training split.

The dataset contains examples that are incompatible with SQLite, contexts that cannot be constructed, and reference queries that fail to execute. At the same time, the new sample contains 61 examples with successfully constructed databases, successfully executed candidate queries classified as SELECT/WITH, and non-empty results.

Rather than continuing with increasingly large exploratory samples, the next step is to implement the proposed Phase 1 dataset preparation pipeline.

This pipeline will apply the required validation and filtering rules to the complete training and test splits, record the number of surviving examples at each stage, and provide a concrete estimate of the dataset's usable size.

The final suitability decision will be based on the pipeline results and a manual review of randomly selected surviving examples.

**Note on sample estimates:** The following 95% Wilson confidence intervals
illustrate the uncertainty associated with the observed proportions:

| Metric | Observed rate | 95% confidence interval |
|---|---:|---:|
| Context construction success | 93.0% | 86.3–96.6% |
| Reference query execution success, conditional on context success | 84.9% | 76.3–90.8% |
| Candidate queries producing result sets | 67.0% | 57.3–75.4% |
| Candidate queries producing non-empty results | 61.0% | 51.2–70.0% |

These intervals describe uncertainty from sampling and do not account for
systematic issues such as dataset composition or the preliminary query
classification method.

---

## 7. Overall Assessment and Next Steps

### 7.1 Assessment Decision

Based on Experiments 1–5, `gretelai/synthetic_text_to_sql` is
conditionally accepted as the primary dataset candidate for this project.

The exploratory audits established that:

- The dataset contains a substantial number of examples with database
  contexts that can be constructed successfully in SQLite.
- A meaningful portion of the sampled reference queries execute
  successfully and produce non-empty results.
- The dataset also contains examples with malformed or incomplete
  contexts, missing tables or columns, SQL dialect incompatibilities,
  non-SELECT statements, and empty query results.
- These issues were observed in both the initial streaming audits and
  the random sample drawn from the complete training split.

The results justify proceeding with the dataset, but do not establish
that the full dataset is suitable for training without further
processing.

### 7.2 Remaining Validation

The exploratory audits used samples of 100 examples and therefore
cannot establish the final number or proportion of usable examples
across the complete dataset.

Before final acceptance, the project must:

1. Implement a reproducible dataset preparation pipeline.
2. Process the complete training and test splits independently.
3. Filter examples based on database construction, read-only SQL
   execution, result availability, size constraints, determinism,
   and other justified quality criteria.
4. Record the number of examples removed at each stage and the
   reasons for rejection.
5. Evaluate the resulting dataset's size and composition.
6. Manually inspect 40 randomly selected surviving examples.
7. Confirm that the resulting training and evaluation sets meet
   the project's acceptance criteria.

The filtering pipeline must preserve the original dataset examples
without silently rewriting their SQL or database contexts.

### 7.3 Known Limitations

The dataset contains SQL and database contexts written for different
SQL dialects. The project will use SQLite as its execution environment.

Consequently, the preparation pipeline is expected to exclude some
otherwise valid SQL examples that rely on unsupported dialect-specific
features, including certain date functions, date arithmetic,
statistical aggregates, and schema-management statements.

The resulting dataset will therefore represent a filtered subset
that is compatible with the project's SQLite-based execution setup,
rather than the full range of SQL represented in the original dataset.

The model prompt must explicitly identify SQLite as the target
dialect.

### 7.4 Transition to Phase 1

The exploratory suitability assessment (Experiments 1–5) is complete.

The project now moves to **Phase 1: Dataset Preparation and Filtering**.

Phase 1 will implement and validate the filtering pipeline, produce
the training dataset and evaluation candidate pool, document the
filtering results, and perform the required manual quality review.

The dataset will receive final acceptance only after these checks
have been completed.

No model training is initiated during this phase.