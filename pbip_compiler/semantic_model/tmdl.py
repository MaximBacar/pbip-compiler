"""TMDL parser — SemanticModel/definition/ folder (one .tmdl per object).

Table parsing is delegated to the indentation-based TmdlTableParser (robust for
multi-line expressions and trailing annotations). Its rich Table model is mapped
down to the canonical model the DataModel builder consumes; relationships are
parsed separately (they live in relationships.tmdl / model.tmdl, not per-table).
"""

from __future__ import annotations

import re
from pathlib import Path

from ..models import Column, Measure, Relationship, SemanticModel, Table
from .tmdl_table import Table as TmdlTable
from .tmdl_table import TmdlTableParser
from .types import tmdl_type


class TmdlParser:
    """Parse a TMDL definition/ folder into a (canonical) SemanticModel."""

    def parse_folder(self, defn_dir: Path) -> SemanticModel:
        all_tables: list[Table] = []
        all_rels: list[Relationship] = []

        # Candidate .tmdl files: tables/ sub-folder + the definition root
        # (model.tmdl, database.tmdl, relationships.tmdl, …).
        candidates: list[Path] = []
        tables_dir = defn_dir / "tables"
        if tables_dir.is_dir():
            candidates += sorted(tables_dir.glob("*.tmdl"))
        candidates += sorted(defn_dir.glob("*.tmdl"))

        for tmdl_file in candidates:
            text = tmdl_file.read_text(encoding="utf-8-sig")
            if re.search(r"^table\s+", text, re.MULTILINE):
                rich = TmdlTableParser(text).parse()
                all_tables.append(self._to_canonical(rich))
            all_rels.extend(self._parse_relationships(text))

        # De-duplicate tables by name (last wins)
        seen: dict[str, Table] = {t.name: t for t in all_tables}
        unique_tables = list(seen.values())

        # De-duplicate relationships
        seen_rels: set[tuple] = set()
        unique_rels: list[Relationship] = []
        for r in all_rels:
            key = (r.from_table, r.from_column, r.to_table, r.to_column)
            if key not in seen_rels:
                seen_rels.add(key)
                unique_rels.append(r)

        return SemanticModel(tables=unique_tables, relationships=unique_rels)

    def _to_canonical(self, rt: TmdlTable) -> Table:
        """Map the rich parsed table to the builder's canonical Table."""
        cols: list[Column] = []
        for c in rt.columns:
            # Calculated columns have no VertiPaq source storage — skip them.
            if c.is_calculated:
                continue
            cols.append(Column(
                name=c.name,
                data_type=tmdl_type(c.data_type or "string"),
                source_column=c.source_column or c.name,
            ))

        measures = [Measure(name=m.name, expression=m.expression) for m in rt.measures]

        # The import partition's M source becomes the table's query.
        m_expression = ""
        for p in rt.partitions:
            if (p.type or "").lower() == "m" and p.source:
                m_expression = p.source
                break

        return Table(
            name=rt.name,
            columns=cols,
            measures=measures,
            is_hidden=rt.is_hidden,
            m_expression=m_expression,
        )

    def _parse_relationships(self, text: str) -> list[Relationship]:
        out: list[Relationship] = []
        for rel_m in re.finditer(r"relationship\s+\S+\s*\n((?:\s+\S.*\n?)+)", text):
            body = rel_m.group(1)
            from_t = re.search(r"fromTable:\s*(.+)", body)
            from_c = re.search(r"fromColumn:\s*(.+)", body)
            to_t   = re.search(r"toTable:\s*(.+)",   body)
            to_c   = re.search(r"toColumn:\s*(.+)",   body)
            if from_t and from_c and to_t and to_c:
                out.append(Relationship(
                    from_table=from_t.group(1).strip().strip("'\""),
                    from_column=from_c.group(1).strip().strip("'\""),
                    to_table=to_t.group(1).strip().strip("'\""),
                    to_column=to_c.group(1).strip().strip("'\""),
                ))
        return out
