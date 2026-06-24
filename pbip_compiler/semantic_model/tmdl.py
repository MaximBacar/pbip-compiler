"""TMDL parser — SemanticModel/definition/ folder (one .tmdl per object)."""

from __future__ import annotations

import re
from pathlib import Path

from ..models import Column, Measure, Relationship, SemanticModel, Table
from .types import tmdl_type


class TmdlParser:
    """Parse TMDL files / a definition/ folder into a SemanticModel."""

    def parse_file(self, path: Path) -> tuple[list[Table], list[Relationship]]:
        """Parse a single .tmdl file. A file can hold a table and/or relationships."""
        text = path.read_text(encoding="utf-8-sig")
        tables: list[Table] = []
        rels: list[Relationship] = []

        table_match = re.search(r"^table\s+['\"]?(.+?)['\"]?\s*$", text, re.MULTILINE)
        if table_match:
            tables.append(self._parse_table(table_match.group(1).strip().strip("'\""), text))

        rels.extend(self._parse_relationships(text))
        return tables, rels

    def parse_folder(self, defn_dir: Path) -> SemanticModel:
        all_tables: list[Table] = []
        all_rels: list[Relationship] = []

        # tables/ sub-folder — one .tmdl per table
        tables_dir = defn_dir / "tables"
        if tables_dir.is_dir():
            for tmdl_file in sorted(tables_dir.glob("*.tmdl")):
                t, r = self.parse_file(tmdl_file)
                all_tables.extend(t)
                all_rels.extend(r)

        # relationships.tmdl (often at the defn_dir root)
        rel_file = defn_dir / "relationships.tmdl"
        if rel_file.exists():
            _, r = self.parse_file(rel_file)
            all_rels.extend(r)

        # Any remaining .tmdl files at the defn_dir root (model.tmdl, database.tmdl …)
        for tmdl_file in sorted(defn_dir.glob("*.tmdl")):
            t, r = self.parse_file(tmdl_file)
            all_tables.extend(t)
            all_rels.extend(r)

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

    def _parse_table(self, tname: str, text: str) -> Table:
        cols: list[Column] = []
        # columns: each 'column <name>' block runs until the next 1-tab keyword.
        # We grab dataType and sourceColumn (the source field name the partition
        # query exposes — needed to map fetched rows onto columns).
        for col_m in re.finditer(
            r"\n\tcolumn\s+['\"]?(.+?)['\"]?\s*\n"
            r"(.*?)(?=\n\t(?:column|measure|partition|hierarchy)\b|\Z)",
            "\n" + text, re.DOTALL,
        ):
            cname = col_m.group(1).strip().strip("'\"")
            block = col_m.group(2)
            # skip calculated columns — they have no VertiPaq source storage
            if re.search(r"^\s*type:\s*calculated\b", block, re.MULTILINE):
                continue
            dt_m = re.search(r"dataType:\s*(\S+)", block)
            sc_m = re.search(r"sourceColumn:\s*(.+)", block)
            cols.append(Column(
                name=cname,
                data_type=tmdl_type(dt_m.group(1) if dt_m else "string"),
                source_column=sc_m.group(1).strip().strip("'\"") if sc_m else cname,
            ))

        measures: list[Measure] = []
        for meas_m in re.finditer(
            r"measure\s+['\"]?(.+?)['\"]?\s*=\s*(.*?)(?=\n\s*(?:measure|column|table|\Z))",
            text, re.DOTALL,
        ):
            measures.append(Measure(
                name=meas_m.group(1).strip().strip("'\""),
                expression=meas_m.group(2).strip(),
            ))

        # partition M source — 'partition <name> = m' then an indented 'source ='.
        m_expression = ""
        part_m = re.search(
            r"\n\tpartition\s+.+?=\s*m\b(.*?)(?=\n\tpartition\b|\n\ttable\b|\Z)",
            "\n" + text, re.DOTALL,
        )
        if part_m:
            src_m = re.search(r"source\s*=\s*(.*)", part_m.group(1), re.DOTALL)
            if src_m:
                m_expression = src_m.group(1).strip()

        is_hidden = bool(re.search(r"^\s*isHidden\s*$", text, re.MULTILINE))
        return Table(
            name=tname,
            columns=cols,
            measures=measures,
            is_hidden=is_hidden,
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
