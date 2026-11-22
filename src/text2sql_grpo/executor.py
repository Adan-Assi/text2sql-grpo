import sqlite3
from dataclasses import dataclass

# Build an in-memory SQLite database from the given context string.
def build_database(context: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:") # creates a new in-memory database
    conn.executescript(context) # runs multiple SQL statements at once from a single string
    return conn


# Close the database connection.
def close_database(conn: sqlite3.Connection) -> None:
    conn.close()


# Enable read-only mode for the database connection.
def set_read_only(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA query_only = ON")


# Return the names of all user-created tables and views in the database.
def user_relations(conn: sqlite3.Connection) -> list[str]: # a relation means a table or a view
    """
    SQLite maintains an internal catalog called sqlite_master (or sqlite_schema),
    which stores metadata about database objects, including their names, types, and creation SQL.

    We query this catalog to retrieve the names of tables and views,
    excluding SQLite's internal objects.
    """
    rows = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type IN ('table', 'view') "
        "AND name NOT LIKE 'sqlite_%' " # excludes internal SQLite objects
        "ORDER BY name"
    ).fetchall() # retrieves all returned rows

    return [row[0] for row in rows]


# Recall that sqlite_master stores metadata about database objects,
# including their creation SQL in the `sql` column.
# Return the SQL definitions of all user-created tables and views.
def schema_sql(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE type IN ('table', 'view') "
        "AND name NOT LIKE 'sqlite_%' "  
        "AND sql IS NOT NULL "           # excludes objects without a stored SQL definition
        "ORDER BY name"
    ).fetchall()

    # Combine the SQL definitions into a single SQL script:
    # 1. Strip leading and trailing whitespace from each definition.
    # 2. Remove trailing semicolons to avoid duplicate separators.
    # 3. Join the definitions with a semicolon and a newline.
    # 4. Append a final semicolon.
    #
    # Example result:
    # CREATE TABLE sales (salesperson TEXT, amount REAL);
    # CREATE VIEW sales_view AS SELECT * FROM sales;
    return ";\n".join(
        row[0].strip().rstrip(";") for row in rows
    ) + ";"


# Count the total number of ROWS across all user-created tables.
def total_table_rows(conn: sqlite3.Connection) -> int:
    table_names = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%'"
    ).fetchall() # example of the fetchall() result: [('employees',), ('sales',)]

    total_rows = 0
    for row in table_names: # each row is a tuple containing one table name, e.g. ('sales',)
        table = row[0] # extracts the table name from the tuple, e.g. 'sales'
        count = conn.execute(
            f'SELECT COUNT(*) FROM "{table}"'
        ).fetchone()[0] # fetchone() returns a tuple like (42,); [0] extracts the count.
        total_rows += count

    return total_rows


@dataclass

# Class used for a consistent format of execution results.
@dataclass
class ExecResult:
    """Stores the outcome of executing a SQL query."""
    success: bool # indicates whether the SQL execution was successful
    data: list[tuple] | None = None # the returned rows, or None if there are no rows to return or execution failed
    columns: list[str] | None = None # the names of the columns in the returned rows, or None if there are no rows to return or execution failed
    error: str | None = None # an error message, or None if the execution was successful


# Execute a SQL query and return an ExecResult object containing the outcome.
def execute_query(conn: sqlite3.Connection, query: str) -> ExecResult:
    try:
        cursor = conn.execute(query)

        # Execution succeeds but the statement doesn't return a result set,
        # (e.g. INSERT, UPDATE, DELETE), return a successful result without rows or columns.
        if cursor.description is None:
            return ExecResult(success=True)

        # For queries that return a result set, cursor.description contains
        # metadata about each result column, represented as a 7-item tuple:
        # (name, type_code, display_size, internal_size, precision, scale, null_ok).
        # We only need the column names, which are the first item in each tuple.
        column_names = [column[0] for column in cursor.description]

        rows = cursor.fetchall()

        # Reaching this point means:
        # - execution succeeded, and
        # - the query returned a result set, so `rows` is a list (possibly empty).
        return ExecResult(
            success=True,
            data=rows,
            columns=column_names
        )

    except sqlite3.Error as e: # an SQLite error occurred during execution
        return ExecResult(
            success=False,
            error=str(e) # convert the error to a string for easier display and logging
            # Note: data and columns are None by default.
        )