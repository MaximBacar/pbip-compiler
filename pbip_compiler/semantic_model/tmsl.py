from __future__ import annotations

import json
from pathlib import Path

from ..models import Column, Measure, Relationship, SemanticModel, Table
from .types import bim_type


class TmslParser:
    """Parse a TMSL model.bim file into a SemanticModel."""

    def parse(self, bim_path: Path) -> SemanticModel:
        with open(bim_path, encoding="utf-8-sig") as f:
            raw = json.load(f)

        model = (
            raw.get("model")
            or raw.get("database", {}).get("model")
            or raw
        )

        tables = [self._parse_table(t) for t in model.get("tables", []) if t.get("name")]
        relationships = self._parse_relationships(model.get("relationships", []))
        return SemanticModel(tables=tables, relationships=relationships)

    def _parse_table(self, t: dict) -> Table:
        cols: list[Column] = []
        for c in t.get("columns", []):
            # skip calculated columns — no VertiPaq storage
            if c.get("type") == "calculated":
                continue
            cname = c.get("name") or c.get("ExplicitName", "")
            cols.append(Column(
                name=cname,
                data_type=bim_type(c.get("dataType", "string")),
                source_column=c.get("sourceColumn") or cname,
            ))

        measures: list[Measure] = []
        for m in t.get("measures", []):
            mname = m.get("name", "")
            expr = m.get("expression", "")
            if isinstance(expr, list):
                expr = "\n".join(expr)
            if mname:
                measures.append(Measure(name=mname, expression=expr.strip()))

        # partition M source expression (import partitions only)
        m_expression = ""
        for p in t.get("partitions", []):
            src = p.get("source", {})
            if src.get("type") == "m":
                expr = src.get("expression", "")
                m_expression = "\n".join(expr) if isinstance(expr, list) else expr
                break

        return Table(
            name=t["name"],
            columns=cols,
            measures=measures,
            is_hidden=t.get("isHidden", False),
            m_expression=m_expression,
        )

    def _parse_relationships(self, rels: list) -> list[Relationship]:
        out: list[Relationship] = []
        for r in rels:
            ft, fc = r.get("fromTable", ""), r.get("fromColumn", "")
            tt, tc = r.get("toTable", ""),   r.get("toColumn", "")
            if ft and fc and tt and tc:
                out.append(Relationship(
                    from_table=ft, from_column=fc, to_table=tt, to_column=tc,
                ))
        return out
