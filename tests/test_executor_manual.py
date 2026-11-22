"""Manually test the SQL execution functions."""

from text2sql_grpo.executor import build_database, execute_query


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

conn.close()