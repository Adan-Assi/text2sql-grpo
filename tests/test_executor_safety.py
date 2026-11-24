"""
Tests for SQLite executor safety.

What this file tests:

Setup (lines 1-90):
    Defines a guarded SQLite connection and test database.

A. Accepted queries (lines 93-120):
    Checks that normal SELECT queries, joins, subqueries, and CTEs work.

B. Rejected queries (lines 123-196):
    Checks that writes, schema changes, ATTACH, PRAGMA, and VACUUM are blocked.

C. Multiple statements (lines 199-219):
    Checks that SQL cannot sneak a second statement into the input.

D. Security layers (lines 223-291):
    Checks which protection blocks which operation.

E. Resource limits (lines 295-362):
    Tests large values, query timeouts, and result row limits.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# SPEC UNDER TEST (replace with imports from the real executor)
# ---------------------------------------------------------------------------
ALLOWED_ACTIONS = frozenset({
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_RECURSIVE,
})
LENGTH_LIMIT = 1_000_000      # bytes, SQLITE_LIMIT_LENGTH
PROGRESS_INTERVAL = 1000      # VM instructions between progress-handler calls
MAX_ROWS = 100

ERRORS = (sqlite3.Error, sqlite3.Warning)  # multi-statement input raises one of these


def _authorizer(action, arg1, arg2, db_name, source):
    return sqlite3.SQLITE_OK if action in ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def open_guarded(path, *, read_only_uri=True, query_only=True,
                 authorizer=True, length_limit=LENGTH_LIMIT):
    """Open a connection with the layers above.  Flags exist so tests can
    switch individual layers off and show which layer is load-bearing."""
    if read_only_uri:
        conn = sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(str(path))
    if query_only:
        conn.execute("PRAGMA query_only=ON")      # must precede the authorizer
    if length_limit is not None:
        conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, length_limit)
    if authorizer:
        conn.set_authorizer(_authorizer)
    return conn


def run_guarded(conn, sql, *, deadline_s=1.0, max_rows=MAX_ROWS,
                progress_interval=PROGRESS_INTERVAL):
    """Execute ONE statement with a soft deadline and a row cap."""
    t_end = time.monotonic() + deadline_s
    conn.set_progress_handler(lambda: 1 if time.monotonic() > t_end else 0,
                              progress_interval)
    try:
        return conn.execute(sql).fetchmany(max_rows)
    finally:
        conn.set_progress_handler(None, 0)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------
def snapshot(directory: Path) -> dict[str, str]:
    """Hash every file in the directory: detects modified AND newly created files."""
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.iterdir()) if p.is_file()}


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "fixture.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE t(a INTEGER, b TEXT);
        CREATE INDEX idx_t_a ON t(a);
        CREATE TABLE u(x INTEGER);
        INSERT INTO t VALUES (1,'x'),(2,'y'),(3,'z');
        INSERT INTO u VALUES (2),(3);
        """
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def guarded(db_path):
    conn = open_guarded(db_path)
    yield conn
    conn.close()


# ===========================================================================
# A. QUERIES THAT MUST SUCCEED
# ===========================================================================
ACCEPTED = [
    pytest.param("SELECT a FROM t ORDER BY a", [(1,), (2,), (3,)], id="plain_select"),
    pytest.param("SELECT count(*), sum(a) FROM t", [(3, 6)], id="aggregate"),
    pytest.param("SELECT t.a, u.x FROM t JOIN u ON t.a = u.x ORDER BY t.a",
                 [(2, 2), (3, 3)], id="join"),
    pytest.param("SELECT a FROM t WHERE a > (SELECT min(x) FROM u) ORDER BY a",
                 [(3,)], id="subquery"),
    pytest.param("WITH c AS (SELECT a FROM t WHERE a > 1) SELECT a FROM c ORDER BY a",
                 [(2,), (3,)], id="with_select"),
    pytest.param("WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r WHERE n < 5) "
                 "SELECT n FROM r", [(1,), (2,), (3,), (4,), (5,)],
                 id="with_recursive_bounded"),
    # Characterization: reading sqlite_master is permitted (schema is not secret).
    pytest.param("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
                 [("t",), ("u",)], id="read_sqlite_master"),
    # Sanity: the length limit must not break ordinary blob use.
    pytest.param("SELECT length(randomblob(1000))", [(1000,)], id="small_randomblob"),
]


@pytest.mark.parametrize("sql, expected", ACCEPTED)
def test_accepted_query_returns_expected_rows(guarded, db_path, sql, expected):
    before = snapshot(db_path.parent)
    assert run_guarded(guarded, sql) == expected
    assert snapshot(db_path.parent) == before


# ===========================================================================
# B. STATEMENTS THAT MUST BE REJECTED (and must leave no trace on disk)
#    "{tmp}" is replaced by the fixture directory.
# ===========================================================================
REJECTED = [
    # writes wrapped in WITH: a first-keyword check would let these through
    pytest.param("WITH c AS (SELECT 1) DELETE FROM t WHERE a IN (SELECT * FROM c)", id="with_delete"),
    pytest.param("WITH c AS (SELECT 1) UPDATE t SET a = 0 WHERE a IN (SELECT * FROM c)", id="with_update"),
    pytest.param("WITH c AS (SELECT 9) INSERT INTO u SELECT * FROM c", id="with_insert"),
    # plain DML / DDL
    pytest.param("INSERT INTO u VALUES (99)", id="insert"),
    pytest.param("UPDATE t SET a = 0", id="update"),
    pytest.param("DELETE FROM t", id="delete"),
    pytest.param("DROP TABLE t", id="drop_table"),
    pytest.param("CREATE TABLE evil(a)", id="create_table"),
    pytest.param("CREATE TEMP TABLE evil(a)", id="create_temp_table"),
    pytest.param("CREATE INDEX idx_evil ON t(b)", id="create_index"),
    pytest.param("DROP INDEX idx_t_a", id="drop_index"),
    pytest.param("ALTER TABLE t ADD COLUMN c TEXT", id="alter_table"),
    # other databases / files
    pytest.param("ATTACH DATABASE '{tmp}/other.db' AS z", id="attach"),
    pytest.param("DETACH DATABASE z", id="detach"),
    pytest.param("ANALYZE", id="analyze"),
    # PRAGMA in every form we care about
    pytest.param("PRAGMA writable_schema = 1", id="pragma_writable_schema"),
    pytest.param("PRAGMA query_only = OFF", id="pragma_query_only_off"),
    pytest.param("PRAGMA journal_mode = WAL", id="pragma_journal_mode"),
    pytest.param("PRAGMA table_info(t)", id="pragma_table_info"),
    # observed on SQLite 3.45.1: table-valued pragma functions are also denied
    pytest.param("SELECT * FROM pragma_table_info('t')", id="pragma_table_valued"),
    # transaction control (passes read-only+query_only alone; authorizer denies it)
    pytest.param("BEGIN", id="begin"),
    pytest.param("SAVEPOINT sp", id="savepoint"),
    pytest.param("COMMIT", id="commit"),
    pytest.param("ROLLBACK", id="rollback"),
    # extension loading must be unavailable
    pytest.param("SELECT load_extension('nonexistent')", id="load_extension"),
]


@pytest.mark.parametrize("sql", REJECTED)
def test_rejected_statement_raises_and_leaves_no_trace(guarded, db_path, sql):
    before = snapshot(db_path.parent)
    with pytest.raises(ERRORS):
        run_guarded(guarded, sql.format(tmp=db_path.parent))
    assert snapshot(db_path.parent) == before


def test_vacuum_into_cannot_create_a_file(guarded, db_path):
    target = db_path.parent / "leak.db"
    before = snapshot(db_path.parent)
    with pytest.raises(ERRORS):
        run_guarded(guarded, f"VACUUM INTO '{target}'")
    assert not target.exists()
    assert snapshot(db_path.parent) == before


def test_plain_vacuum_rejected(guarded, db_path):
    before = snapshot(db_path.parent)
    with pytest.raises(ERRORS):
        run_guarded(guarded, "VACUUM")
    assert snapshot(db_path.parent) == before


def test_reindex_never_modifies_files(guarded, db_path):
    """UNVERIFIED: a manual test saw REINDEX succeed as a no-op on a database
    WITHOUT indexes.  The fixture has one.  We accept 'rejected' or 'harmless'
    but never 'modified'."""
    before = snapshot(db_path.parent)
    try:
        run_guarded(guarded, "REINDEX")
    except ERRORS:
        pass
    assert snapshot(db_path.parent) == before


# ===========================================================================
# C. MULTI-STATEMENT INPUT
# ===========================================================================
@pytest.mark.parametrize("sql", [
    pytest.param("SELECT 1; SELECT 2", id="two_selects"),
    pytest.param("SELECT 1; DELETE FROM t", id="select_then_delete"),
    pytest.param("SELECT 1; DROP TABLE t", id="select_then_drop"),
])
def test_multi_statement_input_rejected(guarded, db_path, sql):
    before = snapshot(db_path.parent)
    with pytest.raises(ERRORS):
        run_guarded(guarded, sql)
    assert snapshot(db_path.parent) == before


def test_executescript_cannot_smuggle_a_write(guarded, db_path):
    """The executor should never use executescript, but if it did, the
    authorizer still applies to every statement in the script."""
    before = snapshot(db_path.parent)
    with pytest.raises(ERRORS):
        guarded.executescript("SELECT 1; DELETE FROM t")
    assert snapshot(db_path.parent) == before


# ===========================================================================
# D. LAYER TESTS: which layer protects against what
# ===========================================================================
def test_allowlist_is_pinned():
    """Fails loudly if someone widens the allowlist."""
    assert ALLOWED_ACTIONS == {
        sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE,
    }
    forbidden_names = [
        "INSERT", "UPDATE", "DELETE", "PRAGMA", "ATTACH", "DETACH", "ANALYZE",
        "REINDEX", "TRANSACTION", "SAVEPOINT", "ALTER_TABLE", "CREATE_TABLE",
        "CREATE_TEMP_TABLE", "CREATE_INDEX", "CREATE_VIEW", "CREATE_TRIGGER",
        "DROP_TABLE", "DROP_INDEX", "DROP_VIEW", "DROP_TRIGGER",
    ]
    forbidden = {getattr(sqlite3, f"SQLITE_{n}", None) for n in forbidden_names} - {None}
    assert not (ALLOWED_ACTIONS & forbidden)


def test_read_only_layers_block_writes_without_authorizer(db_path):
    """Defence in depth: if the authorizer regresses, ro + query_only still hold."""
    conn = open_guarded(db_path, authorizer=False)
    before = snapshot(db_path.parent)
    try:
        with pytest.raises(ERRORS):
            run_guarded(conn, "INSERT INTO u VALUES (99)")
    finally:
        conn.close()
    assert snapshot(db_path.parent) == before


def test_query_only_pragma_alone_blocks_writes(db_path):
    conn = open_guarded(db_path, read_only_uri=False, authorizer=False)
    before = snapshot(db_path.parent)
    try:
        with pytest.raises(ERRORS):
            run_guarded(conn, "DELETE FROM t")
    finally:
        conn.close()
    assert snapshot(db_path.parent) == before


def test_authorizer_alone_blocks_writes(db_path):
    conn = open_guarded(db_path, read_only_uri=False, query_only=False)
    before = snapshot(db_path.parent)
    try:
        with pytest.raises(ERRORS):
            run_guarded(conn, "WITH c AS (SELECT 1) DELETE FROM t WHERE a IN (SELECT * FROM c)")
    finally:
        conn.close()
    assert snapshot(db_path.parent) == before


def test_characterization_authorizer_is_load_bearing_for_vacuum_into(db_path):
    """Documents WHY the authorizer is mandatory.  Observed on SQLite 3.45.1:
    with only mode=ro + query_only, VACUUM INTO still created a new file.
    This test PASSES when that is still true and SKIPS if SQLite changes."""
    target = db_path.parent / "leak.db"
    conn = open_guarded(db_path, authorizer=False)
    try:
        try:
            run_guarded(conn, f"VACUUM INTO '{target}'")
        except ERRORS:
            pytest.skip("this SQLite blocks VACUUM INTO under ro+query_only; "
                        "the authorizer is still required for other SQLite versions")
    finally:
        conn.close()
    if not target.exists():
        pytest.skip("VACUUM INTO produced no file on this SQLite version")
    assert target.exists()


# ===========================================================================
# E. RESOURCE LIMITS AND TIMEOUTS
# ===========================================================================
@pytest.mark.parametrize("sql", [
    pytest.param("SELECT length(randomblob(900000000))", id="large_randomblob"),
    pytest.param("SELECT length(zeroblob(900000000))", id="large_zeroblob"),
    # input is under the limit, output (hex doubles it) is not
    pytest.param("SELECT length(hex(randomblob(600000)))", id="hex_doubles_size"),
])
def test_length_limit_rejects_oversized_values_quickly(guarded, sql):
    start = time.monotonic()
    with pytest.raises(sqlite3.Error) as exc_info:
        run_guarded(guarded, sql, deadline_s=5.0)
    assert time.monotonic() - start < 2.0           # fails fast, does not allocate
    assert "too big" in str(exc_info.value).lower()


def test_progress_handler_is_not_a_hard_timeout(db_path):
    """The handler is only consulted every N VM instructions.  A statement with
    far fewer than N instructions never consults it, however long one native
    call runs, so a 'timeout' based on the handler alone is not a guarantee.
    (A manual test saw a 900 MB randomblob run 2.6 s against a 0.5 s budget.)
    Length limit is disabled here ONLY to let the statement run."""
    calls = {"n": 0}

    def handler():
        calls["n"] += 1
        return 1   # would abort if ever consulted

    conn = open_guarded(db_path, length_limit=None)
    try:
        conn.set_progress_handler(handler, 1000)
        rows = conn.execute("SELECT length(randomblob(50000000))").fetchall()
    finally:
        conn.close()
    assert rows == [(50_000_000,)]
    assert calls["n"] == 0


RUNAWAY = [
    pytest.param("WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r) "
                 "SELECT count(*) FROM r", id="infinite_recursive_cte"),
    pytest.param("WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r WHERE n < 1000000000000) "
                 "SELECT sum(n) FROM r", id="huge_finite_recursive_cte"),
    pytest.param("WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r WHERE n < 3000) "
                 "SELECT count(*) FROM r a, r b, r c", id="cartesian_explosion"),
]


@pytest.mark.parametrize("sql", RUNAWAY)
def test_progress_handler_interrupts_runaway_queries(guarded, sql):
    deadline = 0.3
    start = time.monotonic()
    with pytest.raises(sqlite3.OperationalError, match="interrupted"):
        run_guarded(guarded, sql, deadline_s=deadline)
    assert time.monotonic() - start < deadline + 3.0     # generous slack for CI
    # connection must stay usable after an interrupt
    assert run_guarded(guarded, "SELECT 1") == [(1,)]


def test_row_cap_is_enforced_by_the_caller(guarded):
    rows = run_guarded(
        guarded,
        "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r WHERE n < 1000000) "
        "SELECT n FROM r",
        max_rows=100,
    )
    assert len(rows) == 100