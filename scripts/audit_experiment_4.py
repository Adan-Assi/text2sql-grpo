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
