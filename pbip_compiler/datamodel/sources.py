"""Classify a partition's Power Query (M) source.

Maps each recognised M source onto pbix-mcp source params (source_db /
source_csv) so the partition stays refreshable in Power BI Desktop/Service —
a Refresh runs the generated query and loads all the data. No data is embedded
at compile time.

Supported (everything pbix-mcp can regenerate a refreshable M for):
  SQL Server, Azure SQL, PostgreSQL, MySQL, MariaDB, SQLite, Excel, CSV, JSON/Web.
"""

from __future__ import annotations

import re
from typing import Optional

from ..models import MSource


class MSourceDetector:
    """Best-effort classifier for a partition's M source expression."""

    def detect(self, m_expression: str, table_name: str) -> MSource:
        m = m_expression or ""

        def _s(pattern: str) -> Optional[str]:
            r = re.search(pattern, m)
            return r.group(1) if r else None

        # Table/object name + schema, as exposed by Source{[Schema=..,Item=..]} steps.
        item   = _s(r'Item\s*=\s*"([^"]+)"')
        schema = _s(r'Schema\s*=\s*"([^"]+)"')
        name_  = _s(r'\bName\s*=\s*"([^"]+)"')
        obj    = item or name_ or table_name

        # ── JSON / Web ───────────────────────────────────────────────────
        if "Json.Document" in m:
            url = _s(r'Web\.Contents\(\s*"([^"]+)"')
            if url:
                return MSource(kind="json", refreshable=True,
                               source_db={"type": "json", "url": url})

        # ── SQL Server / Azure SQL ───────────────────────────────────────
        sql = re.search(r'Sql\.Databases?\(\s*"([^"]+)"\s*,\s*"([^"]+)"', m)
        if sql:
            server, database = sql.group(1), sql.group(2)
            kind = "azuresql" if ".database.windows.net" in server.lower() else "sqlserver"
            db = {"type": kind, "server": server, "database": database, "table": obj}
            if schema:
                db["schema"] = schema
            return MSource(kind=kind, source_db=db, refreshable=True)

        # ── PostgreSQL ───────────────────────────────────────────────────
        pg = re.search(r'PostgreSQL\.Database\(\s*"([^"]+?)"\s*,\s*"([^"]+)"', m)
        if pg:
            host, _, port = pg.group(1).partition(":")
            db = {"type": "postgresql", "server": host, "database": pg.group(2), "table": obj}
            if port:
                db["port"] = int(port)
            if schema:
                db["schema"] = schema
            return MSource(kind="postgresql", source_db=db, refreshable=True)

        # ── MySQL / MariaDB ──────────────────────────────────────────────
        my = re.search(r'(MySQL|MariaDB)\.(?:Database|Contents)\(\s*"([^"]+?)"\s*,\s*"([^"]+)"', m)
        if my:
            kind = my.group(1).lower()
            host, _, port = my.group(2).partition(":")
            db = {"type": kind, "server": host, "database": my.group(3), "table": obj}
            if port:
                db["port"] = int(port)
            return MSource(kind=kind, source_db=db, refreshable=True)

        # ── SQLite (ODBC) ────────────────────────────────────────────────
        if "SQLite" in m:
            path = _s(r'Database=([^";]+)')
            if path:
                return MSource(kind="sqlite", refreshable=True,
                               source_db={"type": "sqlite", "path": path, "table": obj})

        # ── Excel workbook (local file) ──────────────────────────────────
        if "Excel.Workbook" in m:
            path = _s(r'File\.Contents\(\s*"([^"]+)"')
            if path:
                return MSource(kind="excel", refreshable=True,
                               source_db={"type": "excel", "path": path, "sheet": item or table_name})

        # ── CSV (local file) ─────────────────────────────────────────────
        if "Csv.Document" in m and "File.Contents" in m:
            path = _s(r'File\.Contents\(\s*"([^"]+)"')
            if path:
                return MSource(kind="csv", source_csv=path, refreshable=True)

        # ── Live connection / dataflow — no embeddable VertiPaq model ─────
        if "AnalysisServices" in m:
            return MSource(kind="analysisservices (live connection — not supported)")
        if "Dataflows" in m:
            return MSource(kind="dataflow (needs service auth — not supported)")

        return MSource(kind="unknown")
