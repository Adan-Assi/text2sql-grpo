"""Audit the first 500 SQaLe 2 training queries by SQL statement type.

This is a preliminary dataset audit. It classifies queries by their first
SQL keyword after removing comments. It does not prove that WITH queries
are read-only or validate SQL execution.
"""

from collections import Counter
import re

from datasets import load_dataset


DATASET_ID = "trl-lab/SQaLe-2-text-to-SQL-Queries"
SPLIT = "train"
LIMIT = 500
EXAMPLES_PER_TYPE = 2


def first_keyword(sql: str) -> str:
    """Return the first SQL keyword after removing comments."""
    if not isinstance(sql, str) or not sql.strip():
        return "<EMPTY>"

    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)

    match = re.search(r"[A-Za-z]+", sql)
    return match.group(0).upper() if match else "<EMPTY>"


def main() -> None:
    print(f"Dataset: {DATASET_ID}")
    print(f"Split: {SPLIT}")
    print(f"Limit: {LIMIT}\n")

    queries = load_dataset(
        DATASET_ID,
        split=SPLIT,
        streaming=True,
    )

    counts = Counter()
    examples = {}

    for index, row in enumerate(queries):
        sql = row.get("sql")
        keyword = first_keyword(sql)

        counts[keyword] += 1
        examples.setdefault(keyword, [])

        if len(examples[keyword]) < EXAMPLES_PER_TYPE:
            examples[keyword].append(sql)

        if index + 1 >= LIMIT:
            break

    total = sum(counts.values())

    print(f"QUERIES INSPECTED: {total}")
    print("\nFIRST KEYWORD COUNTS:")

    for keyword, count in counts.most_common():
        percentage = count / total * 100 if total else 0
        print(f"{keyword}: {count} ({percentage:.1f}%)")

    print("\nREPRESENTATIVE EXAMPLES:")

    for keyword, sql_examples in examples.items():
        for number, sql in enumerate(sql_examples, start=1):
            print(f"\n--- {keyword}, example {number} ---")
            print(sql[:500] if isinstance(sql, str) else sql)

    print("\nIMPORTANT:")
    print("This is a first-keyword classification only.")
    print("WITH queries still require read-only validation.")
    print("This audit does not validate database reconstruction or execution.")


if __name__ == "__main__":
    main()
