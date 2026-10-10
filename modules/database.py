"""Small SQLite/PostgreSQL compatibility layer for application persistence."""

import os
import re
import sqlite3
from typing import Any


def _postgres_sql(statement: str) -> str:
    statement = re.sub(
        r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
        "BIGSERIAL PRIMARY KEY",
        statement,
        flags=re.IGNORECASE,
    )
    return statement.replace("?", "%s")


class _Cursor:
    def __init__(self, cursor: Any, postgres: bool):
        self._cursor = cursor
        self._postgres = postgres

    def execute(self, statement: str, parameters: Any = None):
        if self._postgres:
            statement = _postgres_sql(statement)
        if parameters is None:
            self._cursor.execute(statement)
        else:
            self._cursor.execute(statement, parameters)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self):
        return self._cursor.rowcount


class Connection:
    def __init__(self, connection: Any, postgres: bool):
        self._connection = connection
        self.is_postgres = postgres
        if not postgres:
            connection.row_factory = sqlite3.Row

    def execute(self, statement: str, parameters: Any = None):
        return _Cursor(self._connection.cursor(), self.is_postgres).execute(statement, parameters)

    def cursor(self):
        return _Cursor(self._connection.cursor(), self.is_postgres)

    def executescript(self, script: str):
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)

    def commit(self):
        self._connection.commit()

    def close(self):
        self._connection.close()

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self._connection.__exit__(exc_type, exc_value, traceback)


def connect_database(sqlite_path: str) -> Connection:
    """Connect to Neon/Postgres when DATABASE_URL is configured, otherwise SQLite."""
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        import psycopg
        from psycopg.rows import dict_row

        return Connection(
            psycopg.connect(database_url, row_factory=dict_row),
            postgres=True,
        )
    if os.environ.get("VERCEL"):
        raise RuntimeError(
            "DATABASE_URL is required on Vercel. Configure a Neon PostgreSQL connection string."
        )
    os.makedirs(os.path.dirname(os.path.abspath(sqlite_path)), exist_ok=True)
    return Connection(sqlite3.connect(sqlite_path), postgres=False)
