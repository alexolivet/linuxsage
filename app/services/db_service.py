from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatabaseService:
    """SQLite access layer.

    The app ships a bundled SQLite DB. Historically the schema included an
    `examples` column, but the new DB (`knowledge_base_01.db`) uses:
      - command
      - description
      - category

    To keep the UI resilient, we introspect the DB and dynamically adjust the
    SELECT/WHERE clauses based on which columns exist.

    Notes on threading:
    - Do not share sqlite3 connections across threads.
    - This service opens a fresh connection per call.
    """

    db_path: Path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _get_table_names(conn: sqlite3.Connection) -> list[str]:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        return [str(r[0]) for r in cur.fetchall()]

    @staticmethod
    def _get_table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
        cur = conn.execute(f"PRAGMA table_info({table_name})")
        # row tuple: (cid, name, type, notnull, dflt_value, pk)
        return {str(r[1]) for r in cur.fetchall()}

    @classmethod
    def _resolve_commands_table(
        cls, conn: sqlite3.Connection
    ) -> tuple[str | None, set[str]]:
        """Find a table that looks like the command knowledge base.

        We prefer a table literally named 'commands', but fall back to any table
        that contains at least the required columns: command, description.
        """

        tables = cls._get_table_names(conn)
        if not tables:
            return None, set()

        # Prefer a stable name when present.
        ordered = (['commands'] if 'commands' in tables else []) + [
            t for t in tables if t != 'commands'
        ]

        required = {"command", "description"}

        for t in ordered:
            cols = cls._get_table_columns(conn, t)
            if required.issubset(cols):
                return t, cols

        return None, set()

    def health_check(self) -> dict[str, Any]:
        """Return basic DB readiness info."""

        with self._connect() as conn:
            table_name, cols = self._resolve_commands_table(conn)
            has_required_table = table_name is not None

            row_count = 0
            if has_required_table:
                cur = conn.execute(f"SELECT COUNT(*) AS c FROM {table_name}")
                row_count = int(cur.fetchone()[0])

        # Keep `table_exists` for backward compatibility with older UI code.
        return {
            "table_exists": has_required_table,
            "has_required_table": has_required_table,
            "table_name": table_name or "",
            "columns": sorted(cols),
            "row_count": row_count,
        }

    def search_commands(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return []

        like = f"%{q}%"

        with self._connect() as conn:
            table_name, cols = self._resolve_commands_table(conn)
            if table_name is None:
                raise RuntimeError(
                    "No suitable table found. Expected columns: command, description."
                )

            # Provide a stable id for list rendering.
            id_expr = "id" if "id" in cols else "rowid AS id"

            select_parts = [id_expr, "command", "description"]
            if "category" in cols:
                select_parts.append("category")
            if "examples" in cols:
                select_parts.append("examples")

            search_cols = ["command", "description"]
            if "category" in cols:
                search_cols.append("category")
            if "examples" in cols:
                search_cols.append("examples")

            where_parts = [f"{c} LIKE ? COLLATE NOCASE" for c in search_cols]

            sql = f"""
                SELECT {', '.join(select_parts)}
                FROM {table_name}
                WHERE {' OR '.join(where_parts)}
                ORDER BY command ASC
                LIMIT ?
            """

            params = [like for _ in search_cols] + [int(limit)]
            cur = conn.execute(sql, params)
            rows = cur.fetchall()

        results: list[dict[str, Any]] = []
        for r in rows:
            results.append(
                {
                    "id": r["id"],
                    "command": (r["command"] if "command" in r.keys() else "") or "",
                    "description": (
                        r["description"] if "description" in r.keys() else ""
                    )
                    or "",
                    "category": (r["category"] if "category" in r.keys() else "") or "",
                    "examples": (r["examples"] if "examples" in r.keys() else "") or "",
                }
            )

        return results
