# Dataset Concepts: Schemas, Databases, and Queries

## 1. What is a schema?

A schema defines the structure of a database. It tells us:
- Which tables exist.
- Which columns each table contains.
- The structure of the data stored in those columns.

A schema is like a **blueprint**. It describes how a database is organized, but it does not contain the actual records (rows).

## 2. Example: A music database

Imagine a schema describing a music database.

It defines a `songs` table with the following columns:

| Column | Meaning |
|---|---|
| `song_id` | Song identifier |
| `title` | Song title |
| `artist` | Artist name |
| `duration` | Song duration in seconds |

The schema tells us that the `songs` table exists and has these four columns. It does not tell us which songs are actually stored in it.

The same schema could also define other tables, such as `artists`, `albums`, and `playlists`.

## 3. What is a database?

The database contains the actual tables and their data.

For example, a database built according to the music schema might contain:

**Table: `songs`**

| song_id | title | artist | duration |
|---|---|---|---|
| 1 | Imagine | John Lennon | 183 |
| 2 | Billie Jean | Michael Jackson | 294 |
| 3 | Halo | Beyoncé | 261 |

Each row represents one song.
Each column holds a particular piece of information about that song.

The schema defines the structure; the database contains the actual records.

## 4. How schemas and databases relate to SQaLe 2

SQaLe 2 contains many different schemas, each describing a different database structure.

For example:
- One schema might describe a music database.
- Another might describe a university database.
- Another might describe a hospital database.

A schema is associated with a database containing the actual data for its tables.

The Text-to-SQL task works as follows:

1. The model receives a natural-language question and the relevant schema.
2. It uses the schema to understand which tables and columns are available.
3. It generates an SQL query.
4. The query is executed against the corresponding populated database.
5. The result is evaluated against the expected result.

**The distinction to remember:**

- Schema = the database's blueprint (tables and columns).
- Database = the actual tables and records (rows).
- SQL query = instructions for retrieving or manipulating data in the database.