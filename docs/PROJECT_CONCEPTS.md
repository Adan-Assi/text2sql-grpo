
# Project Concepts and Architecture

This document is intended as a reference while developing the Text-to-SQL GRPO project. It focuses on understanding why things are structured the way they are, not just what each component does.

---

# 1. Why Do We Need a Python Package?

Our project contains several Python modules that work together to implement the Text-to-SQL system.

We could place all of them directly inside `src/`:

```text
src/
├── executor.py
├── data_prep.py
├── prompts.py
└── reward.py
```

However, as the project grows, having all modules directly inside `src/` becomes less organized, while packaging them is more useful for several reasons:

1. **Organization:** The package groups code that belongs to the same system **under one namespace.**
    This becomes increasingly useful as we add more modules.

2. **Imports:** Modules need to use functions defined in other modules.
    For example, `data_prep.py` needs functions from `executor.py`.
    With the package structure, it can import them using:

    ```python
    from text2sql_grpo.executor import build_database, run_select
    ```

    This tells Python to:

    - find the `text2sql_grpo` package.
    - find the `executor` module inside it.
    - import the requested functions.


3. **Reusability:** The package can be installed as a Python package, allowing its modules to be imported consistently from different parts of the project.



So, we group related modules inside a package:

```text
src/
└── text2sql_grpo/
    ├── __init__.py
    ├── executor.py
    ├── data_prep.py
    ├── prompts.py
    └── reward.py
```

#### Q: Why use `src/` at all? Why not put the package directly in the project root?

#### A: The `src/` layout separates the actual installable package from other project files.

For example:

- `src/`: application code.
- `scripts/`: standalone scripts used to run experiments or tasks.
- `tests/`: automated tests.
- `docs/`: documentation.
- `reports/`: generated reports.

This separation makes the project easier to maintain and helps ensure that the package is imported from its installed location rather than accidentally from the project root.

---

# 2. Understanding the Package Modules

We're following the principle of **separation of concerns**: instead of putting all the project's logic into one large file, we divide it into components that handle different tasks.

The package:

```text
src/
└── text2sql_grpo/
    ├── __init__.py
    ├── executor.py
    ├── data_prep.py
    └── prompts.py
```

## How the modules work together

We'll demonstrate using an example from the Gretel dataset:

**Question:**

"Which salesperson generated the highest total sales?"

**Database context (`sql_context`):**

```sql
CREATE TABLE sales (
    salesperson TEXT,
    amount REAL
);

INSERT INTO sales VALUES ('Ali', 100);
INSERT INTO sales VALUES ('Sara', 250);
INSERT INTO sales VALUES ('Omar', 150);
```

**Gold SQL (`sql`):**

```sql
SELECT salesperson, SUM(amount)
FROM sales
GROUP BY salesperson
ORDER BY SUM(amount) DESC
LIMIT 1;
```

**Expected result:**

```text
Sara | 250
```
---

### A. `executor.py`: Working with SQLite

The executor provides reusable Python functions for interacting with SQLite.

Its job is to take the database context supplied by a dataset example, turn it into an actual database, inspect that database, and execute SQL queries against it.

Let's follow the sales example.

**Starting point: The example's database context (`sql_context`)**

```sql
CREATE TABLE sales (
    salesperson TEXT,
    amount REAL
);

INSERT INTO sales VALUES ('Ali', 100);
INSERT INTO sales VALUES ('Sara', 250);
INSERT INTO sales VALUES ('Omar', 150);
```

This is not yet an actual database. Its a set of SQL instructions describing how to create and populate one.

#### 1. Building the database

```python
conn = build_database(context)
```

The `build_database()` function receives the context above.

Inside the function, it essentially does the following:

```python
conn = sqlite3.connect(":memory:")
conn.executescript(context)
```

Where:
- The first line asks SQLite to create a new, temporary database in memory. The database exists only while the connection remains open; it is **not saved as a database file.**

- The variable `conn` is a connection object. Python uses it to communicate with that particular SQLite database.

- The second line executes the SQL statements contained in context, one after another. In our example, these statements create the sales table and insert the three sales records into it.



In our example, SQLite:

1. Executes `CREATE TABLE sales (...)`, creating a table named `sales` with two columns.
2. Executes the first `INSERT`, adding Ali's record.
3. Executes the second `INSERT`, adding Sara's record.
4. Executes the third `INSERT`, adding Omar's record.

The database now contains:

**Table: `sales`**

| salesperson | amount |
|---|---:|
| Ali | 100 |
| Sara | 250 |
| Omar | 150 |

giving us an actual database that can be queried.

#### 2. Inspecting the database schema

Now that the database exists, we can inspect its structure.

The **schema** describes the database's structure: its tables, columns, and data types. It does not include the actual records.

For our example, the schema is:

```sql
CREATE TABLE sales (
    salesperson TEXT,
    amount REAL
);
```

The executor provides `schema_sql()` to retrieve this information:

```python
schema = schema_sql(conn)
```

The function reads the table definitions stored in SQLite's internal `sqlite_master` table.

It returns the `CREATE TABLE` statement, without the `INSERT` statements or sales records.

**Why do we need this?**

The language model needs to know which tables and columns exist so it can generate SQL that refers to the actual database structure.

#### 3. Executing a SQL query

We now have the database, its schema, and the gold SQL query from our example.

Before executing the query, we restrict the connection:

```python
lock_down(conn)
```

This enables read-only restrictions, preventing subsequent queries from modifying the database.

We then execute the gold SQL:

```python
result = run_select(conn, gold_sql)
```

For our sales example, the query:

```sql
SELECT salesperson, SUM(amount)
FROM sales
GROUP BY salesperson
ORDER BY SUM(amount) DESC
LIMIT 1;
```

Produces the following result:

| salesperson | SUM(amount) |
|---|---:|
| Sara | 250 |

In short, SQLite groups the sales records by salesperson, calculates each person's total, sorts the totals from highest to lowest, and returns the first row.

#### 4. Understanding the execution result

The `run_select()` function returns an `ExecResult` object containing information about the execution.

For our example, it would look conceptually like this:

```python
ExecResult(
    ok=True,
    rows=[("Sara", 250)],
    error=None,
    detail=None
)
```

- `ok=True`: The query executed successfully.
- `rows`: The result returned by SQLite.
- `error` and `detail`: Information about a failure, if one occurred.

**So, what is the responsibility of `executor.py`?**

It provides reusable functions to build SQLite databases, inspect their schemas, and execute SQL queries. It does not decide which dataset examples to keep. That is the responsibility of `data_prep.py`.

---

### B. `data_prep.py`: Preparing and Filtering the Dataset

The original Gretel dataset contains 100,000 training examples, but not all of them are necessarily suitable for our project.

The responsibility of `data_prep.py` is to decide which examples should be included in the prepared dataset.

It uses `executor.py` to perform database construction and SQL execution, then applies the project's filtering rules to the returned results.

For our sales example:

1. `data_prep.py` passes the example's `sql_context` and gold SQL to the executor.
2. The executor builds the database and executes the query.
3. The executor returns an `ExecResult` containing `Sara | 250`.
4. `data_prep.py` checks whether the example satisfies the filtering requirements.
5. If it passes, the example is kept. Otherwise, it is rejected, and the reason is recorded.

In addition, `data_prep.py` processes the dataset splits, tracks filtering statistics, and saves the prepared datasets and reports.

**The distinction:** `executor.py` knows how to execute SQL. `data_prep.py` uses that functionality to decide which dataset examples are suitable.

This separation allows us to change filtering rules without rewriting the database execution code.

---

### C. `prompts.py`: Preparing Instructions for the Language Model

After preparing the dataset, we need to construct the input that will be given to the language model.

For our sales example, we need two pieces of information:

**Question:**

```text
Which salesperson generated the highest total sales?
```

**Database schema:**

```sql
CREATE TABLE sales (
    salesperson TEXT,
    amount REAL
);
```

The `prompts.py` module combines these into a consistent instruction for the model.

For example:

```text
You are a SQL assistant.

Generate a SQL query that answers the question
using the provided SQLite database schema.

Database schema:
CREATE TABLE sales (
    salesperson TEXT,
    amount REAL
);

Question:
Which salesperson generated the highest total sales?

Return only the SQL query.
```

The model receives this prompt and generates a SQL query.

The purpose of `prompts.py` is to centralize prompt construction so that the model receives instructions in a consistent format.

---

### D. `__init__.py`: The Package Initializer

The `__init__.py` file marks the directory as a regular Python package.

It can also expose selected functions at the package level, but we do not need that for now. It can remain empty.

We can still import functions directly from their modules:

```python
from text2sql_grpo.executor import build_database
```

---

### E. `reward.py`: Evaluating Model-Generated SQL

This module becomes important during model training.

Unlike dataset preparation, where we execute the gold SQL, during training the model generates its own SQL. We need to evaluate whether its output is correct.

For our sales example, the gold SQL returns:

| salesperson | total |
|---|---:|
| Sara | 250 |

Suppose the model generates a different query:

```sql
SELECT salesperson, SUM(amount) AS total_sales
FROM sales
GROUP BY salesperson
ORDER BY total_sales DESC
LIMIT 1;
```

Although the SQL is written differently, it produces the same result.

We can execute both queries against the same database and compare their results instead of comparing their SQL text.

If the results match, the generated query can receive a positive reward. If they differ or the generated query fails, its reward can be lower.

**The distinction between the modules:**

- `executor.py` executes SQL and returns results.
- `reward.py` uses those results to evaluate generated SQL and calculate a reward.

The exact reward rules will be developed in a later phase.

---

# 3. How Everything Fits Together

Using our sales example, the overall project flow is:

```text
              ORIGINAL DATASET
                     |
                     v
                data_prep.py
              (processes examples)
                     |
                     | calls functions from
                     v
                 executor.py
              (provides SQL operations)
                     |
          +----------+----------+
          |                     |
          v                     v
    Build database         Execute gold SQL
          |                     |
          +----------+----------+
                     |
                     v
              Return ExecResult
                     |
                     v
                data_prep.py
             (applies filtering rules)
                     |
              +------+------+
              |             |
              v             v
            KEEP          REJECT
              |             |
              v             v
       Prepared dataset  Record reason
```

Each module has a separate responsibility:

| Module | Responsibility |
|---|---|
| `executor.py` | Build SQLite databases, inspect schemas, and execute SQL |
| `data_prep.py` | Process and filter dataset examples |
| `prompts.py` | Construct instructions for the language model |
| `reward.py` | Evaluate generated SQL and calculate rewards |
| `__init__.py` | Mark the directory as a Python package |

---

# 4. Important Notes

- **Successful execution does not guarantee correctness.** A gold query might execute successfully but still fail to answer the natural-language question accurately.
- **An empty result is not necessarily an execution failure.** It can be a valid result, so whether to exclude such examples is a filtering decision.
- **Execution-based comparison has limitations.** The final reward implementation must account for details such as row ordering, duplicate rows, and data types.
- **SQL safety matters.** Building a database from dataset-provided context and executing model-generated queries require different safety restrictions.