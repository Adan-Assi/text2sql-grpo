"""Manually test the SQL execution functions."""

import sqlite3

from text2sql_grpo.executor import (
    build_database,
    close_database,
    execute_query,
    set_read_only
)

context = """
CREATE TABLE sales (
    salesperson TEXT,
    amount REAL
);

INSERT INTO sales VALUES ('Ali', 100);
INSERT INTO sales VALUES ('Sara', 250);
INSERT INTO sales VALUES ('Omar', 150);
"""

conn = build_database(context)

# ---------- SELECT ----------

# 1. SELECT with matching rows.
result = execute_query(conn, "SELECT * FROM sales")

print("SELECT with rows:")
print(result)

# 2. SELECT with no matching rows.
result = execute_query(conn, "SELECT * FROM sales WHERE amount > 1000")

print("\nSELECT with no rows:")
print(result)

# ---------- INSERT ----------

# 3. INSERT without a result set.
result = execute_query(conn, "INSERT INTO sales VALUES ('Lina', 200)")

print("\nINSERT:")
print(result)

# ---------- Invalid Query ----------

# 4. Invalid SELECT.
result = execute_query(conn, "SELECT salary FROM sales")

print("\nInvalid SELECT:")
print(result)

# ---------- READ-ONLY MODE ----------

# Enable read-only mode after building the database.
set_read_only(conn)

# 5. SELECT should still work.
result = execute_query(conn, "SELECT * FROM sales")

print("\nSELECT in read-only mode:")
print(result)

# 6. INSERT should be rejected.
result = execute_query(conn, "INSERT INTO sales VALUES ('Lina', 200)")

print("\nINSERT in read-only mode:")
print(result)

# 7. UPDATE should be rejected.
result = execute_query(conn, "UPDATE sales SET amount = 0")

print("\nUPDATE in read-only mode:")
print(result)

# 8. DELETE should be rejected.
result = execute_query(conn, "DELETE FROM sales")

print("\nDELETE in read-only mode:")
print(result)

# ---------- DATABASE CONSTRUCTION ----------

# Case A: Valid context
valid_context = """
CREATE TABLE products (
    name TEXT,
    price REAL
);

INSERT INTO products VALUES ('Laptop', 3000);
"""

conn = build_database(valid_context)

print("\nValid context:")
print(execute_query(conn, "SELECT * FROM products"))

close_database(conn)


# Case B: Invalid context
invalid_context = """
CREATE TABLE products (
    name TEXT,
    price REAL
);

INSERT INTO nonexistent_table VALUES ('Laptop', 3000);
"""

try:
    conn = build_database(invalid_context)
except sqlite3.Error as e:
    print("\nInvalid context:")
    print(type(e).__name__, e)

# ----------- Close Database ----------
close_database(conn)