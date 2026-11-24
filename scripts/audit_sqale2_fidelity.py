from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from importlib import metadata
from pathlib import Path

import platform

import pyarrow
import pyarrow.parquet as pq
from sqale import build_database

# --- constants ---------------------------------------------------------------
SCHEMA_COLS = ("schema_id", "full_schema", "schema_content")
QUERY_COLS = ("question_id", "schema_id", "difficulty", "sql",
              "relevant_tables", "execution_result")

# README says "up to the first 50 rows"; the source docstring only says "first rows".
# UNVERIFIED: the summary prints the observed maximum stored length to check this.
STORED_RESULT_CAP = 50

# Replicated from sqale 0.2.0 deserialize.py (private constants); re-check on upgrade.
INT64_MIN, INT64_MAX = -9223372036854775808, 9223372036854775807
FLOAT_MAX = 1.7976931348623157e308

LENGTH_LIMIT = 5_000_000      # SQLITE_LIMIT_LENGTH for audit runs (arbitrary; see notes)
PROGRESS_N = 1000
INTERNAL_TABLES = {"sqlite_master", "sqlite_schema", "sqlite_temp_master", "sqlite_temp_schema"}
NONDET_FUNCS = {"random", "randomblob", "changes", "total_changes", "last_insert_rowid"}
NONDET_SQL = re.compile(r"'now'|\bcurrent_(?:date|time|timestamp)\b", re.IGNORECASE)

ALLOWED_ACTIONS = frozenset({
    sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE,
})


# --- parquet helpers (no streaming, no `datasets`) ---------------------------
def find_shards(root: str, split: str) -> list[Path]:
    files = sorted(Path(root).expanduser().rglob(f"{split}-*.parquet"))
    if not files:
        raise SystemExit(f"no {split}-*.parquet files under {root}")
    return files


def check_columns(files: list[Path], required, label: str) -> dict[str, str]:
    schema = pq.ParquetFile(str(files[0])).schema_arrow
    missing = [c for c in required if c not in schema.names]
    if missing:
        raise SystemExit(f"{label}: missing columns {missing}; found {schema.names}")
    return {f.name: str(f.type) for f in schema}     # recorded: raw column types


def iter_rows(files, columns, batch_size):
    for path in files:
        pf = pq.ParquetFile(str(path))
        for batch in pf.iter_batches(batch_size=batch_size, columns=list(columns)):
            yield from batch.to_pylist()


def column_values(files, column):
    return {str(r[column]) for r in iter_rows(files, [column], 65536)}


def pick_schema_ids(schema_files, query_files, n, seed):
    # Restricting to ids present in BOTH downloaded sets allows a partial download.
    ids = sorted(column_values(schema_files, "schema_id") & column_values(query_files, "schema_id"))
    return random.Random(seed).sample(ids, min(n, len(ids)))


def load_questions(query_files, ids, cap, seed):
    wanted, by_schema = set(ids), defaultdict(list)
    for row in iter_rows(query_files, QUERY_COLS, 2048):
        sid = str(row["schema_id"])
        if sid in wanted:
            by_schema[sid].append(row)
    rng, out = random.Random(seed), []
    for sid in ids:
        rows = by_schema.get(sid, [])
        rng.shuffle(rows)
        out.extend(rows[:cap])
    return out


def load_schema_rows(schema_files, ids):
    wanted, found = set(ids), {}
    gen = iter_rows(schema_files, SCHEMA_COLS, 4)
    try:
        for row in gen:
            sid = str(row["schema_id"])
            if sid in wanted and sid not in found:
                found[sid] = row
                if len(found) == len(wanted):
                    break
    finally:
        gen.close()
    return found


def parse_json_field(raw):
    """-> (value, status) with status in ok|missing|malformed.  Unlike the package,
    a parse failure is never silently turned into []."""
    if raw is None:
        return None, "missing"
    if isinstance(raw, (list, dict)):
        return raw, "ok"
    if isinstance(raw, str):
        if not raw.strip():
            return None, "missing"
        try:
            return json.loads(raw), "ok"
        except json.JSONDecodeError:
            return None, "malformed"
    return None, "malformed"


# --- reconstruction audit ----------------------------------------------------
_IDENT = r'(?:"[^"]+"|`[^`]+`|\[[^\]]+\]|[\w$]+)'
_CREATE_TABLE = re.compile(
    rf"CREATE\s+(?:(?:GLOBAL\s+|LOCAL\s+)?(?:TEMP|TEMPORARY)\s+)?TABLE\s+"
    rf"(?:IF\s+NOT\s+EXISTS\s+)?({_IDENT}(?:\s*\.\s*{_IDENT})?)", re.IGNORECASE)


def ddl_table_names(ddl: str) -> set[str]:
    """HEURISTIC (regex, not a parser): table names the DDL tries to create."""
    names = set()
    for m in _CREATE_TABLE.finditer(ddl or ""):
        last = re.split(r"\s*\.\s*", m.group(1))[-1]
        names.add(last.strip('"`[]').lower())
    return names


def replay_ddl(ddl: str) -> dict:
    """Replays DDL with the SAME splitting the package uses (re.split on ';\\s*',
    mirrored from sqale 0.2.0 _split_ddl) but records failures it swallows."""
    scratch = sqlite3.connect(":memory:")
    stmts = [s.strip() for s in re.split(r";\s*", ddl or "") if s.strip()]
    failures = []
    for s in stmts:
        try:
            scratch.execute(s)
        except sqlite3.Error as e:
            failures.append({"statement": s[:160], "error": str(e)})
    scratch.close()
    return {"statements": len(stmts), "failed": len(failures), "failures": failures[:5]}


def analyze_content(content: dict) -> dict:
    """Per-table expectations and silent-loss risks, mirroring what the package's
    _insert_rows/_coerce_row do (columns come from the FIRST dict row only)."""
    stats = {}
    for table, rows in content.items():
        is_list = isinstance(rows, list)
        dict_rows = [r for r in rows if isinstance(r, dict)] if is_list else []
        st = {"table": str(table), "expected_rows": len(dict_rows),
              "non_dict_rows": (len(rows) - len(dict_rows)) if is_list else None,
              "first_keys": [], "rows_with_extra_keys": 0, "extra_keys": [],
              "rows_missing_keys": 0, "clamped_ints": 0, "clamped_floats": 0,
              "json_encoded_cells": 0}
        if dict_rows:
            first = list(dict_rows[0].keys())
            fset, extra = set(first), set()
            for r in dict_rows:
                ex = set(r) - fset
                if ex:
                    st["rows_with_extra_keys"] += 1
                    extra |= ex
                if fset - set(r):
                    st["rows_missing_keys"] += 1       # filled with NULL, not dropped
                for c in first:
                    v = r.get(c)
                    if isinstance(v, (dict, list)):
                        st["json_encoded_cells"] += 1
                    elif isinstance(v, bool):
                        pass
                    elif isinstance(v, int):
                        if v < INT64_MIN or v > INT64_MAX:
                            st["clamped_ints"] += 1
                    elif isinstance(v, float):
                        if abs(v) > FLOAT_MAX:          # +/-inf
                            st["clamped_floats"] += 1
            st["first_keys"], st["extra_keys"] = first, sorted(extra)
        stats[str(table).lower()] = st
    return stats


def built_row_counts(conn) -> dict[str, int]:
    names = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    return {n: conn.execute('SELECT COUNT(*) FROM "%s"' % n.replace('"', '""')).fetchone()[0]
            for n in names}


def compare_tables(content_stats, built_counts, ddl_names) -> dict:
    built = {t.lower(): n for t, n in built_counts.items()}
    reports = {}
    for key in sorted(set(content_stats) | set(ddl_names) | set(built)):
        st = content_stats.get(key)
        exp = st["expected_rows"] if st else None
        act = built.get(key)
        if act is None:
            status = "table_missing"
        elif exp is not None and act < exp:
            status = "rows_missing"
        else:
            status = "ok"
        reports[key] = {
            "status": status, "expected_rows": exp, "actual_rows": act,
            "in_ddl": key in ddl_names, "in_content": st is not None,
            "dropped_values_risk": bool(st and st["rows_with_extra_keys"]),
            "extra_keys": st["extra_keys"] if st else [],
            "clamped": bool(st and (st["clamped_ints"] or st["clamped_floats"])),
        }
    return reports


# --- guarded execution -------------------------------------------------------
class AuditAuthorizer:
    """Allowlist authorizer that also records what each statement touches."""
    def reset(self):
        self.denied, self.reads, self.functions = [], set(), set()

    def __call__(self, action, arg1, arg2, db_name, source):
        if action == sqlite3.SQLITE_READ:
            self.reads.add(str(arg1).lower())            # arg1 = table, arg2 = column
        elif action == sqlite3.SQLITE_FUNCTION and arg2:
            self.functions.add(str(arg2).lower())        # arg2 = function name
        if action in ALLOWED_ACTIONS:
            return sqlite3.SQLITE_OK
        self.denied.append(action)
        return sqlite3.SQLITE_DENY


def guard(conn, auth):
    conn.execute("PRAGMA query_only=ON")                 # before the authorizer
    conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, LENGTH_LIMIT)
    conn.set_authorizer(auth)
    # In-memory DB: no mode=ro URI is possible; the authorizer is the real guard.
    # The soft deadline cannot interrupt a single long native call (see tests).


def run_gold(conn, auth, sql, budget_s):
    auth.reset()
    t0 = time.monotonic()
    t_end = t0 + budget_s
    conn.set_progress_handler(lambda: 1 if time.monotonic() > t_end else 0, PROGRESS_N)
    rows, err, kind = None, None, "ran"
    try:
        rows = [list(r) for r in conn.execute(sql).fetchmany(STORED_RESULT_CAP + 1)]
    except (sqlite3.Error, sqlite3.Warning) as e:        # Warning: multi-statement input
        msg = str(e)
        if auth.denied or "not authorized" in msg or "authorization denied" in msg:
            kind = "denied"
        elif "interrupted" in msg:
            kind = "timeout"
        else:
            kind = "error"
        err = f"{type(e).__name__}: {msg}"
    finally:
        conn.set_progress_handler(None, 0)
    return {"kind": kind, "rows": rows, "error": err,
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1)}


# --- result comparison -------------------------------------------------------
def top_level_text(sql: str) -> str:
    """SQL with strings, comments and everything inside parentheses removed."""
    out, i, n, depth = [], 0, len(sql), 0
    while i < n:
        c = sql[i]
        if c in "'\"`":
            j = i + 1
            while j < n:
                if sql[j] == c:
                    if j + 1 < n and sql[j + 1] == c:
                        j += 2
                        continue
                    break
                j += 1
            i = j + 1
            out.append(" ")
        elif c == "[":
            j = sql.find("]", i + 1)
            i = n if j == -1 else j + 1
            out.append(" ")
        elif sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j == -1 else j + 1
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            i = n if j == -1 else j + 2
        elif c == "(":
            depth += 1
            i += 1
        elif c == ")":
            depth = max(0, depth - 1)
            i += 1
        else:
            if depth == 0:
                out.append(c)
            i += 1
    return "".join(out)


def has_top_level_order_by(sql: str) -> bool:
    """HEURISTIC: ORDER BY outside any parentheses (CTE bodies, subqueries and
    window clauses are ignored)."""
    return bool(re.search(r"\border\s+by\b", top_level_text(sql), re.IGNORECASE))


def norm_cell(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if v != v:
            return "NaN"
        if v.is_integer() and abs(v) < 2 ** 53:
            return int(v)                                # 3.0 == 3
        return float(f"{v:.8g}")                         # relative tolerance
    if isinstance(v, str):
        return v
    raise TypeError(type(v).__name__)


def norm_rows(rows):
    out = []
    for r in rows:
        if not isinstance(r, (list, tuple)):
            raise TypeError("row_not_list")
        out.append([norm_cell(c) for c in r])
    return out


def canonical(rows):
    return sorted(json.dumps(r, sort_keys=True) for r in rows)


def stringify(rows):
    return [[None if c is None else str(c) for c in r] for r in rows]


def compare_results(actual, stored, ordered):
    a, s = norm_rows(actual), norm_rows(stored)
    if (a == s) if ordered else (canonical(a) == canonical(s)):
        return "match", None
    if canonical(a) == canonical(s):
        return "mismatch", "order_only"                  # ordered query, ties/order differ
    if canonical(stringify(a)) == canonical(stringify(s)):
        return "mismatch", "type_only"                   # e.g. 3 vs "3": serialization artifact?
    return "mismatch", f"value_diff(actual={len(a)},stored={len(s)})"


def is_degenerate(rows):
    flat = [c for r in rows for c in r]
    if all(c is None for c in flat):
        return True
    return len(rows) == 1 and len(rows[0]) == 1 and rows[0][0] in (None, 0, 1, "")


# --- per-example audit -------------------------------------------------------
def audit_example(conn, auth, q, table_reports, budget_s, observed):
    rec = {"question_id": q.get("question_id"), "schema_id": str(q.get("schema_id")),
           "difficulty": q.get("difficulty"), "sql": q.get("sql"),
           "reason": None, "detail": None}
    sql = q.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        rec.update(reason="malformed_record", detail="empty_sql")
        return rec

    run = run_gold(conn, auth, sql, budget_s)
    rec.update(elapsed_ms=run["elapsed_ms"], error=run["error"],
               tables_read=sorted(auth.reads - INTERNAL_TABLES),
               functions=sorted(auth.functions), denied_codes=list(auth.denied))

    # reconstruction flags for the tables this query actually reads
    flags = []
    for t in rec["tables_read"]:
        tr = table_reports.get(t)
        if tr is None:
            flags.append(f"unknown_table:{t}")
            continue
        if tr["status"] != "ok":
            flags.append(f"{tr['status']}:{t}({tr['expected_rows']}->{tr['actual_rows']})")
        if tr["dropped_values_risk"]:
            flags.append(f"dropped_values_risk:{t}")
        if tr["clamped"]:
            flags.append(f"clamped:{t}")
    rec["fidelity_flags"] = flags

    relevant, rstatus = parse_json_field(q.get("relevant_tables"))
    if rstatus == "ok" and isinstance(relevant, list) and all(isinstance(x, str) for x in relevant):
        rec["reads_outside_relevant"] = sorted(set(rec["tables_read"]) - {x.lower() for x in relevant})
    else:
        rec["reads_outside_relevant"] = "relevant_tables_unparsed"   # UNRESOLVED: element format

    if run["kind"] != "ran":
        rec.update(reason=run["kind"], detail=run["error"])
        return rec
    actual = run["rows"]
    rec["n_actual"], rec["actual_head"] = len(actual), actual[:3]
    if any(isinstance(c, (bytes, bytearray, memoryview)) for r in actual for c in r):
        rec.update(reason="uninterpretable", detail="blob_in_actual_result")
        return rec
    if (set(rec["functions"]) & NONDET_FUNCS) or NONDET_SQL.search(sql):
        rec.update(reason="nondeterministic")
        return rec

    stored, sstatus = parse_json_field(q.get("execution_result"))
    if sstatus != "ok" or not isinstance(stored, list):
        rec.update(reason="malformed_stored", detail=sstatus if sstatus != "ok" else "not_a_list")
        return rec
    observed["max_stored_len"] = max(observed["max_stored_len"], len(stored))
    rec["n_stored"], rec["stored_head"] = len(stored), stored[:3]
    if len(stored) >= STORED_RESULT_CAP:
        rec.update(reason="skipped_truncated")
        return rec

    ordered = has_top_level_order_by(sql)
    rec["ordered"] = ordered
    try:
        outcome, detail = compare_results(actual, stored, ordered)
    except TypeError as e:
        rec.update(reason="malformed_stored", detail=f"unsupported_cell_or_row:{e}")
        return rec
    if outcome == "mismatch":
        rec.update(reason="mismatch", detail=detail)
    elif not actual:
        rec.update(reason="empty")
    elif is_degenerate(norm_rows(actual)):
        rec.update(reason="degenerate")
    else:
        rec.update(reason="ok")
    return rec


def audit_schema(schema_row, questions, budget_s, observed):
    sid = str(schema_row.get("schema_id"))
    report = {"schema_id": sid, "n_questions": len(questions)}
    ddl = schema_row.get("full_schema") or ""
    content, cstatus = parse_json_field(schema_row.get("schema_content"))
    report["content_status"] = cstatus
    content = content if isinstance(content, dict) else {}
    report["ddl_replay"] = replay_ddl(ddl)

    try:
        conn = build_database(schema_row)                # package baseline, unchanged
    except Exception as exc:                             # noqa: BLE001
        report["build_exception"] = f"{type(exc).__name__}: {exc}"
        return report, [{"schema_id": sid, "question_id": q.get("question_id"),
                         "reason": "error", "detail": "build_database_raised"} for q in questions]

    tables = compare_tables(analyze_content(content), built_row_counts(conn), ddl_table_names(ddl))
    report["tables"] = tables
    report["table_status_counts"] = dict(Counter(t["status"] for t in tables.values()))

    auth = AuditAuthorizer()
    auth.reset()
    guard(conn, auth)
    records = [audit_example(conn, auth, q, tables, budget_s, observed) for q in questions]
    conn.close()
    return report, records


# --- main --------------------------------------------------------------------
def parse_args():
    def n_schemas(v):
        v = int(v)
        if not 1 <= v <= 10:
            raise argparse.ArgumentTypeError("draft audit is deliberately capped at 1-10 schemas")
        return v
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--schemas-dir", required=True)
    p.add_argument("--queries-dir", required=True)
    p.add_argument("--split", default="train", choices=["train", "test"])
    p.add_argument("--n-schemas", type=n_schemas, default=8)
    p.add_argument("--max-questions-per-schema", type=int, default=25)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--time-budget", type=float, default=5.0, help="soft per-query deadline, seconds")
    p.add_argument("--out", default="audit_out/sqale2_fidelity")
    return p.parse_args()


def main():
    args = parse_args()
    schema_files = find_shards(args.schemas_dir, args.split)
    query_files = find_shards(args.queries_dir, args.split)
    col_types = {"schemas": check_columns(schema_files, SCHEMA_COLS, "schemas"),
                 "queries": check_columns(query_files, QUERY_COLS, "queries")}

    ids = pick_schema_ids(schema_files, query_files, args.n_schemas, args.seed)
    questions = load_questions(query_files, ids, args.max_questions_per_schema, args.seed)
    schema_rows = load_schema_rows(schema_files, ids)
    by_schema = defaultdict(list)
    for q in questions:
        by_schema[str(q["schema_id"])].append(q)

    observed = {"max_stored_len": 0}
    schema_reports, examples = [], []
    for sid in ids:
        if sid not in schema_rows:
            schema_reports.append({"schema_id": sid, "error": "schema row not found"})
            continue
        rep, recs = audit_schema(schema_rows[sid], by_schema[sid], args.time_budget, observed)
        schema_reports.append(rep)
        examples.extend(recs)
        print(f"{sid}: {dict(Counter(r['reason'] for r in recs))}", flush=True)

    reasons = Counter(r["reason"] for r in examples)
    summary = {
        "n_schemas": len(ids), "n_examples": len(examples), "reasons": dict(reasons),
        "mismatch_details": dict(Counter(r["detail"] for r in examples if r["reason"] == "mismatch")),
        "reasons_by_difficulty": {d: dict(Counter(r["reason"] for r in examples if r.get("difficulty") == d))
                                  for d in sorted({str(r.get("difficulty")) for r in examples})},
        "fidelity_flag_counts": dict(Counter(f.split(":")[0] for r in examples for f in r.get("fidelity_flags", []))),
        "observed_max_stored_len": observed["max_stored_len"],
        "assumed_stored_cap": STORED_RESULT_CAP,
        "config": vars(args), "schema_ids": ids, "column_types": col_types,
        "env": {"python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
                "pyarrow": pyarrow.__version__, "platform": platform.platform(),
                "sqale": metadata.version("SQaLe")},
        "files": {"schemas": [f"{f.name}:{f.stat().st_size}" for f in schema_files],
                  "queries": [f"{f.name}:{f.stat().st_size}" for f in query_files]},
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (out / "schemas.jsonl").write_text("\n".join(json.dumps(r, default=str) for r in schema_reports))
    (out / "examples.jsonl").write_text("\n".join(json.dumps(r, default=str) for r in examples))
    print(json.dumps({k: summary[k] for k in ("n_examples", "reasons", "mismatch_details",
                                              "fidelity_flag_counts", "observed_max_stored_len")}, indent=2))


if __name__ == "__main__":
    main()