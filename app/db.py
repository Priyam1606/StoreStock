import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from app.config import get_settings


def get_db_path() -> str:
    return get_settings().db_path


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    target_path = db_path if db_path is not None else get_db_path()
    conn = sqlite3.connect(target_path, timeout=30.0, check_same_thread=False)
    conn.isolation_level = None
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


@contextmanager
def get_db(db_path: str | None = None) -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Generator[sqlite3.Connection, None, None]:
    conn.execute("BEGIN IMMEDIATE;")
    try:
        yield conn
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise


def init_db(db_path: str | None = None) -> None:
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as file:
        schema_sql = file.read()
    with get_db(db_path) as conn:
        conn.executescript(schema_sql)
