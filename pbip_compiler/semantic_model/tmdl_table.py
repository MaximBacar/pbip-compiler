"""Indentation-based TMDL table parser.

Parses a single table .tmdl file into a rich Table model. Unlike a regex
scanner, it uses indentation to delimit each object's block, so multi-line
expressions and trailing properties/annotations are never mixed into a
measure's DAX or a partition's M source.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# ─── Sub-models ───────────────────────────────────────────────────────────────

class Annotation(BaseModel):
    name: str
    value: str

class Column(BaseModel):
    name: str
    data_type: Optional[str] = None
    source_column: Optional[str] = None
    lineage_tag: Optional[str] = None
    summarize_by: Optional[str] = None
    format_string: Optional[str] = None
    display_folder: Optional[str] = None
    description: Optional[str] = None
    is_hidden: bool = False
    is_key: bool = False
    is_available_in_mdx: Optional[bool] = None
    is_name_inferred: bool = False
    is_calculated: bool = False          # True if sourceColumn starts with [ or has expression
    expression: Optional[str] = None     # DAX expression for calculated columns
    annotations: list[Annotation] = Field(default_factory=list)

class Measure(BaseModel):
    name: str
    expression: str
    format_string: Optional[str] = None
    display_folder: Optional[str] = None
    lineage_tag: Optional[str] = None
    description: Optional[str] = None
    is_hidden: bool = False
    annotations: list[Annotation] = Field(default_factory=list)

class Partition(BaseModel):
    name: str
    mode: Optional[str] = None           # import / directQuery / etc.
    type: Optional[str] = None           # m / calculated / entity
    source: Optional[str] = None         # M or DAX expression
    description: Optional[str] = None

class HierarchyLevel(BaseModel):
    name: str
    column: Optional[str] = None
    ordinal: Optional[int] = None

class Hierarchy(BaseModel):
    name: str
    lineage_tag: Optional[str] = None
    display_folder: Optional[str] = None
    description: Optional[str] = None
    is_hidden: bool = False
    levels: list[HierarchyLevel] = Field(default_factory=list)

class Table(BaseModel):
    name: str
    lineage_tag: Optional[str] = None
    description: Optional[str] = None
    is_hidden: bool = False
    is_private: bool = False
    show_as_variations_only: bool = False
    columns: list[Column] = Field(default_factory=list)
    measures: list[Measure] = Field(default_factory=list)
    partitions: list[Partition] = Field(default_factory=list)
    hierarchies: list[Hierarchy] = Field(default_factory=list)
    annotations: list[Annotation] = Field(default_factory=list)


# ─── Parser ───────────────────────────────────────────────────────────────────

class TmdlTableParser:
    """Parses a single table .tmdl file into a Table pydantic model."""

    def __init__(self, content: str):
        self.content = content
        self.lines = content.splitlines()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _strip_quotes(s: str) -> str:
        """Remove surrounding single quotes from TMDL names."""
        return s.strip().strip("'")

    @staticmethod
    def _indent(line: str) -> int:
        return len(line) - len(line.lstrip('\t'))

    def _extract_block_lines(self, start_index: int) -> list[str]:
        """
        Starting from start_index (the object declaration line),
        collect all lines belonging to that block (deeper indent).
        """
        base_indent = self._indent(self.lines[start_index])
        block = []
        for line in self.lines[start_index + 1:]:
            stripped = line.strip()
            if not stripped:
                continue
            if self._indent(line) > base_indent:
                block.append(line)
            else:
                break
        return block

    @staticmethod
    def _kv(lines: list[str], key: str) -> Optional[str]:
        """Extract a simple key: value property from a list of lines."""
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(f"{key}:"):
                return stripped[len(key) + 1:].strip()
        return None

    @staticmethod
    def _flag(lines: list[str], keyword: str) -> bool:
        """Return True if a bare keyword (e.g. isHidden) exists in the block."""
        return any(line.strip() == keyword for line in lines)

    def _extract_multiline_expression(self, start_index: int, key: str = "source") -> Optional[str]:
        """
        Extract a multi-line or single-line expression that follows `key =`.
        Handles both backtick (```) and plain indented forms.
        """
        for i, line in enumerate(self.lines):
            stripped = line.strip()
            pattern = re.compile(rf'^{re.escape(key)}\s*=\s*(.*)')
            m = pattern.match(stripped)
            if m:
                first = m.group(1).strip()
                # Triple-backtick verbatim block
                if first == '```' or first == '= ```':
                    expr_lines = []
                    for follow in self.lines[i + 1:]:
                        if follow.strip() == '```':
                            break
                        expr_lines.append(follow)
                    return '\n'.join(expr_lines).strip()
                # Single-line
                if first:
                    return first
                # Multi-line indented
                base_ind = self._indent(self.lines[i])
                expr_lines = []
                for follow in self.lines[i + 1:]:
                    if not follow.strip():
                        expr_lines.append('')
                        continue
                    if self._indent(follow) > base_ind:
                        expr_lines.append(follow.strip())
                    else:
                        break
                return '\n'.join(expr_lines).strip() or None
        return None

    def _parse_annotations(self, lines: list[str]) -> list[Annotation]:
        annotations = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            m = re.match(r'^annotation\s+(\S+)\s*=\s*(.*)', stripped)
            if m:
                annotations.append(Annotation(name=m.group(1), value=m.group(2).strip()))
        return annotations

    def _description_above(self, index: int) -> Optional[str]:
        """Read /// doc-comment lines immediately above a declaration."""
        doc_lines = []
        i = index - 1
        while i >= 0:
            stripped = self.lines[i].strip()
            if stripped.startswith('///'):
                doc_lines.insert(0, stripped[3:].strip())
                i -= 1
            else:
                break
        return ' '.join(doc_lines) if doc_lines else None

    # ── Table-level ───────────────────────────────────────────────────────────

    def _parse_table_header(self) -> dict:
        """Extract top-level table properties."""
        for i, line in enumerate(self.lines):
            m = re.match(r'^table\s+(.*)', line.strip())
            if m:
                name = self._strip_quotes(m.group(1))
                header_lines = self._extract_block_lines(i)
                # Only top-level lines (not deeper sub-blocks)
                top = [l for l in header_lines
                       if self._indent(l) == self._indent(self.lines[i]) + 1]
                return {
                    "name": name,
                    "lineage_tag": self._kv(top, "lineageTag"),
                    "is_hidden": self._flag(top, "isHidden"),
                    "is_private": self._flag(top, "isPrivate"),
                    "show_as_variations_only": self._flag(top, "showAsVariationsOnly"),
                    "description": self._description_above(i),
                }
        return {"name": "unknown"}

    # ── Columns ───────────────────────────────────────────────────────────────

    def _parse_columns(self) -> list[Column]:
        columns = []
        for i, line in enumerate(self.lines):
            m = re.match(r'^\t?column\s+(.*)', line)
            if not m:
                continue
            raw_decl = m.group(1).strip()
            # Calculated column: `column Name = DAX`
            calc_match = re.match(r"^(.+?)\s*=\s*(.+)$", raw_decl)
            if calc_match:
                col_name = self._strip_quotes(calc_match.group(1))
                expression = calc_match.group(2).strip()
                is_calculated = True
            else:
                col_name = self._strip_quotes(raw_decl)
                expression = None
                is_calculated = False

            block = self._extract_block_lines(i)
            source_col = self._kv(block, "sourceColumn")
            # Also calculated if sourceColumn starts with [
            if source_col and source_col.startswith('['):
                is_calculated = True

            columns.append(Column(
                name=col_name,
                data_type=self._kv(block, "dataType"),
                source_column=source_col,
                lineage_tag=self._kv(block, "lineageTag"),
                summarize_by=self._kv(block, "summarizeBy"),
                format_string=self._kv(block, "formatString"),
                display_folder=self._kv(block, "displayFolder"),
                description=self._description_above(i),
                is_hidden=self._flag(block, "isHidden"),
                is_key=self._flag(block, "isKey"),
                is_name_inferred=self._flag(block, "isNameInferred"),
                is_available_in_mdx=None if self._kv(block, "isAvailableInMdx") is None
                                    else self._kv(block, "isAvailableInMdx") != "false",
                is_calculated=is_calculated,
                expression=expression,
                annotations=self._parse_annotations(block),
            ))
        return columns

    # ── Measures ──────────────────────────────────────────────────────────────

    def _parse_measures(self) -> list[Measure]:
        measures = []
        for i, line in enumerate(self.lines):
            m = re.match(r"^\t?measure\s+'?([^'=]+)'?\s*=\s*(.*)", line)
            if not m:
                continue
            name = self._strip_quotes(m.group(1))
            first_expr = m.group(2).strip()

            # Collect continuation lines
            expr_lines = [first_expr] if first_expr else []
            j = i + 1
            base_ind = self._indent(self.lines[i])
            while j < len(self.lines):
                nxt = self.lines[j]
                nxt_stripped = nxt.strip()
                if not nxt_stripped:
                    j += 1
                    continue
                if self._indent(nxt) > base_ind and not re.match(
                    r'^\t*(formatString|displayFolder|lineageTag|isHidden|annotation|//)', nxt_stripped
                ):
                    expr_lines.append(nxt_stripped)
                    j += 1
                else:
                    break

            block = self._extract_block_lines(i)
            measures.append(Measure(
                name=name,
                expression='\n'.join(expr_lines).strip(),
                format_string=self._kv(block, "formatString"),
                display_folder=self._kv(block, "displayFolder"),
                lineage_tag=self._kv(block, "lineageTag"),
                description=self._description_above(i),
                is_hidden=self._flag(block, "isHidden"),
                annotations=self._parse_annotations(block),
            ))
        return measures

    # ── Partitions ────────────────────────────────────────────────────────────

    def _parse_partitions(self) -> list[Partition]:
        partitions = []
        for i, line in enumerate(self.lines):
            m = re.match(r"^\t?partition\s+'?([^'=]+)'?\s*=\s*(\w+)", line)
            if not m:
                continue
            name = self._strip_quotes(m.group(1))
            ptype = m.group(2).strip()   # m / calculated / entity

            block = self._extract_block_lines(i)
            # Source is everything after `source =`
            source = None
            for bi, bl in enumerate(block):
                sm = re.match(r'^\t*source\s*=\s*(.*)', bl)
                if sm:
                    first = sm.group(1).strip()
                    src_lines = [first] if first else []
                    base_ind = self._indent(bl)
                    for bl2 in block[bi + 1:]:
                        if self._indent(bl2) > base_ind:
                            src_lines.append(bl2.strip())
                        else:
                            break
                    source = '\n'.join(src_lines).strip() or None
                    break

            partitions.append(Partition(
                name=name,
                type=ptype,
                mode=self._kv(block, "mode"),
                source=source,
                description=self._description_above(i),
            ))
        return partitions

    # ── Hierarchies ───────────────────────────────────────────────────────────

    def _parse_hierarchies(self) -> list[Hierarchy]:
        hierarchies = []
        for i, line in enumerate(self.lines):
            m = re.match(r"^\t?hierarchy\s+'?([^']+)'?", line)
            if not m:
                continue
            name = self._strip_quotes(m.group(1))
            block = self._extract_block_lines(i)

            levels = []
            for bi, bl in enumerate(block):
                lm = re.match(r"^\t+level\s+'?([^']+)'?", bl)
                if lm:
                    lvl_name = self._strip_quotes(lm.group(1))
                    lvl_block = []
                    base_ind = self._indent(bl)
                    for bl2 in block[bi + 1:]:
                        if self._indent(bl2) > base_ind:
                            lvl_block.append(bl2)
                        else:
                            break
                    ordinal = self._kv(lvl_block, "ordinal")
                    levels.append(HierarchyLevel(
                        name=lvl_name,
                        column=self._kv(lvl_block, "column"),
                        ordinal=int(ordinal) if ordinal else None,
                    ))

            hierarchies.append(Hierarchy(
                name=name,
                lineage_tag=self._kv(block, "lineageTag"),
                display_folder=self._kv(block, "displayFolder"),
                description=self._description_above(i),
                is_hidden=self._flag(block, "isHidden"),
                levels=levels,
            ))
        return hierarchies

    # ── Top-level table annotations ───────────────────────────────────────────

    def _parse_table_annotations(self) -> list[Annotation]:
        """Annotations at the table level (top indentation)."""
        result = []
        for line in self.lines:
            # Only tab-1 depth (direct child of table)
            if self._indent(line) == 1:
                m = re.match(r'^\tannotation\s+(\S+)\s*=\s*(.*)', line)
                if m:
                    result.append(Annotation(name=m.group(1), value=m.group(2).strip()))
        return result

    # ── Entry point ───────────────────────────────────────────────────────────

    def parse(self) -> Table:
        header = self._parse_table_header()
        return Table(
            **header,
            columns=self._parse_columns(),
            measures=self._parse_measures(),
            partitions=self._parse_partitions(),
            hierarchies=self._parse_hierarchies(),
            annotations=self._parse_table_annotations(),
        )


# ─── Public API ───────────────────────────────────────────────────────────────

def parse_tmdl_table(path: str | Path) -> Table:
    """Load a .tmdl file and return a fully-populated Table pydantic model."""
    content = Path(path).read_text(encoding='utf-8-sig')
    return TmdlTableParser(content).parse()
