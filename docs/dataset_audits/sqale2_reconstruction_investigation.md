# SQaLe 2 Database Reconstruction Investigation

## 1. Problem

During the SQaLe 2 test-split fidelity audit, some tables were found to contain fewer rows after database reconstruction than were present in the original `schema_content`.

One example was `schema_018710`, where the `Songs` table had:

| Source data | Reconstructed SQLite database |
|---:|---:|
| 341 rows | 24 rows |

This raised an important question: were the rows missing from the original dataset, or were they being lost during database reconstruction?

The distinction matters because the project uses database execution to evaluate generated SQL. If the reconstructed database is incomplete, a correct SQL query may produce an incorrect result and receive an incorrect training reward.

## 2. Investigation

### 2.1 Verify the original source data

We loaded `schema_018710` directly from the SQaLe 2 test schema Parquet file and counted the entries in `schema_content` corresponding to the `Songs` table.

Result:

```text
Songs in schema_content: 341
```

This established that all 341 source entries were present in the downloaded dataset.

### 2.2 Verify the official SQaLe reconstruction

We used the official `sqale` package's `build_database()` function to reconstruct the database and counted the rows in SQLite.

Result:

```text
Songs in SQLite: 24
```

Our audit therefore reproduced the same discrepancy as the official reconstruction. The problem was not specific to our audit implementation.

### 2.3 Inspect the official reconstruction implementation

We inspected the source of `build_database()`.

The relevant logic was:

```python
for statement in _split_ddl(row.get("full_schema") or ""):
    try:
        conn.execute(statement)
    except sqlite3.Error:
        pass

content = _parse_json_field(row.get("schema_content"), default={})
if isinstance(content, dict):
    for table, table_rows in content.items():
        _insert_rows(conn, table, table_rows)
```

This showed that:
- Table definitions are created using the SQL statements in `full_schema`.
- Table contents are loaded from `schema_content`.
- Each table's rows are passed to `_insert_rows()`.

We then inspected `_insert_rows()`:

```python
def _insert_rows(conn: sqlite3.Connection, table: str, table_rows) -> None:
    if not isinstance(table_rows, list):
        return
    table_rows = [r for r in table_rows if isinstance(r, dict)]
    if not table_rows:
        return
    cols = list(table_rows[0].keys())
    insert_sql = (
        f"INSERT OR IGNORE INTO {_quote(table)} ({', '.join(map(_quote, cols))}) "
        f"VALUES ({', '.join('?' * len(cols))})"
    )
    for row_dict in table_rows:
        try:
            conn.execute(insert_sql, _coerce_row(row_dict, cols))
        except (sqlite3.Error, OverflowError):
            pass
```

The important detail is `INSERT OR IGNORE`.

SQLite silently ignores rows that violate applicable constraints, such as a `UNIQUE` constraint. The function also catches insertion errors without reporting them.

Therefore, the official reconstruction can silently produce tables with fewer rows than their source data.

## 3. Diagnostic script

To identify the exact reason for the missing rows, we reproduced the official table creation process but used ordinary `INSERT` statements instead of `INSERT OR IGNORE`.

This allowed SQLite to report the errors that the official implementation silently ignores.

The following script reproduces the investigation for `schema_018710`:

```python
import sqlite3
import pyarrow.parquet as pq
from collections import Counter
from sqale import build_database

path = "data/sqale2/schemas_test/data/test-00000-of-00001.parquet"
target_schema = "schema_018710"

# Load the original schema record.
record = None
for batch in pq.ParquetFile(path).iter_batches():
    for row in batch.to_pylist():
        if row["schema_id"] == target_schema:
            record = row
            break
    if record:
        break

assert record is not None, f"{target_schema} not found"

# Reuse the official SQaLe parsing and normalization helpers.
g = build_database.__globals__
schema = g["_normalise"](record)
content = g["_parse_json_field"](
    schema.get("schema_content"), default={}
)

# Find the Songs table regardless of capitalization.
songs_key = next(
    (key for key in content if key.lower() == "songs"),
    None
)
assert songs_key is not None, "Songs table not found"

rows = [
    row for row in content[songs_key]
    if isinstance(row, dict)
]

print("SOURCE TABLE KEY:", repr(songs_key))
print("SOURCE DICTIONARY ROWS:", len(rows))

# Reproduce official table creation.
conn = sqlite3.connect(":memory:")
conn.execute("PRAGMA foreign_keys = OFF")

for statement in g["_split_ddl"](schema.get("full_schema") or ""):
    try:
        conn.execute(statement)
    except sqlite3.Error:
        pass

print("\nSONGS TABLE DEFINITION:")
print(conn.execute(
    "SELECT sql FROM sqlite_master "
    "WHERE type='table' AND lower(name)=lower(?)",
    (songs_key,)
).fetchone())

print("\nTABLE COLUMNS:")
for column in conn.execute(
    f"PRAGMA table_info({g['_quote'](songs_key)})"
):
    print(column)

# Use ordinary INSERT so constraint violations are reported.
cols = list(rows[0].keys())

insert_sql = (
    f'INSERT INTO {g["_quote"](songs_key)} '
    f'({", ".join(g["_quote"](col) for col in cols)}) '
    f'VALUES ({", ".join("?" for _ in cols)})'
)

errors = Counter()
samples = {}

for index, row in enumerate(rows):
    try:
        conn.execute(insert_sql, g["_coerce_row"](row, cols))
    except (sqlite3.Error, OverflowError) as error:
        message = f"{type(error).__name__}: {error}"
        errors[message] += 1
        samples.setdefault(message, (index, row))

print("\nINSERT DIAGNOSTIC:")
print("Source dictionary rows:", len(rows))
print("Successfully inserted:", conn.execute(
    f"SELECT COUNT(*) FROM {g['_quote'](songs_key)}"
).fetchone()[0])
print("Error counts:", dict(errors))

print("\nEXAMPLE REJECTED ROWS:")
for message, (index, row) in samples.items():
    print(f"\nRow index: {index}")
    print("Error:", message)
    print("Row:", row)

conn.close()
```

## 4. Diagnostic results

### 4.1 Source and reconstructed table

The source table key was `Songs`, containing 341 dictionary rows.

The official table definition was:

```sql
CREATE TABLE Songs (
    Id Integer NOT NULL UNIQUE,
    Artist_Id Int,
    Disc_Id Int NOT NULL UNIQUE,
    Genre_Id Int,
    TrackNumber SmallInt,
    Title TEXT NOT NULL,
    TreeTitle TEXT NOT NULL UNIQUE,
    Duration Float NOT NULL,
    Rating Int,
    FileSize Int,
    Checksum Int,
    Bitrate Int,
    LastPlaybackTime Datetime,
    PlaybacksCount Int NOT NULL,
    DeleteDate Datetime,
    FOREIGN KEY (Genre_Id) REFERENCES Genres (Id),
    FOREIGN KEY (Disc_Id) REFERENCES Discs (Id),
    FOREIGN KEY (Artist_Id) REFERENCES Artists (Id)
)
```

The important constraint is:

```sql
Disc_Id Int NOT NULL UNIQUE
```

### 4.2 Insertion results

The diagnostic produced:

```text
SOURCE TABLE KEY: 'Songs'
SOURCE DICTIONARY ROWS: 341

INSERT DIAGNOSTIC:
Source dictionary rows: 341
Successfully inserted: 24
Error counts: {
    'IntegrityError: UNIQUE constraint failed: Songs.Disc_Id': 317
}
```

The first example of a rejected row was:

```text
Row index: 3

Error:
IntegrityError: UNIQUE constraint failed: Songs.Disc_Id

Row:
{
    'Id': 4,
    'Artist_Id': 29,
    'Disc_Id': 7,
    'Genre_Id': 1,
    'TrackNumber': 8,
    'Title': 'Shadow for Whispers',
    ...
}
```

The `Disc_Id` value had already been inserted by an earlier song.

All 317 rejected rows were rejected for the same reason: duplicate `Disc_Id` values.

## 5. Root cause

The source data contains multiple songs associated with the same disc, but the SQL table definition declares `Disc_Id` as `UNIQUE`.

This is inconsistent with the apparent intended relationship:

- One disc can contain multiple songs.
- Each song belongs to a disc.

`Disc_Id` should therefore act as a foreign key in `Songs`, but should not be unique there.

The official reconstruction function uses `INSERT OR IGNORE`, so SQLite silently skips rows that violate this constraint.

The reconstruction process is behaving according to its implementation, but the resulting database does not faithfully represent the source data.

## 6. Conclusion and project decision

For `schema_018710`, the exact cause of the missing rows is confirmed:

| Item | Result |
|---|---:|
| Source `Songs` rows | 341 |
| Reconstructed `Songs` rows | 24 |
| Successfully inserted | 24 |
| Rejected rows | 317 |
| Rejection reason | Duplicate `Songs.Disc_Id` values |
| Underlying issue | Incorrect `UNIQUE` constraint in `full_schema` |

This is a schema/data integrity issue in the SQaLe 2 source record, not an error in our audit script.

### Final project decision

1. Use the official SQaLe 2 reconstruction through `sqale==0.2.0`.
2. Do not modify downloaded source data, the installed package, or the official DDL to repair reconstruction discrepancies.
3. Do not automatically exclude examples solely because reconstructed row counts differ from source row counts.
4. Execute gold SQL and generated SQL against the same official reconstructed database instance.
5. Apply the project's example eligibility rules independently of reconstruction row-count discrepancies.
6. Document reconstruction limitations when interpreting results.

The diagnostic custom reconstruction was used only to identify the cause and assess its impact. It was not retained in the project pipeline.

### Impact on the test audit

In the expanded test audit:

- 100 schemas were sampled.
- 1,840 query examples were audited.
- 13 query examples were flagged for the `Songs` table discrepancy in `schema_018710`.
- The official builder reconstructed 24 `Songs` rows instead of the 341 source rows.

The 13 examples are not automatically excluded from the project dataset on this basis. Their gold SQL and generated SQL will execute against the same official reconstructed database. Consequently, the reward measures agreement within that reconstructed environment, not fidelity to the original source data.

This distinction matters when interpreting results: a query can match its gold result in the reconstructed database even when missing source rows would have changed the result.

### Scope limitation

This investigation establishes the exact cause for `schema_018710` and its `Songs` table only.

Other tables found to have fewer reconstructed rows may have different causes. No general cause should be assumed without further evidence.

**Final takeaway:** The official SQaLe 2 builder can silently discard source rows when DDL constraints conflict with the supplied data. We retain the official reconstruction for a consistent execution environment, document this limitation, and do not treat row-count discrepancies alone as grounds for excluding examples.