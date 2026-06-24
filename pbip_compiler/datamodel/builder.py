from __future__ import annotations

import warnings
from abc import ABC, abstractmethod

from pbix_mcp.builder import PBIXBuilder

from ..models import Column, SemanticModel, Table
from .sources import MSourceDetector


def _sentinel_row(columns: list[Column]) -> dict:
    """Return one placeholder row with zero/empty values per column type."""
    row: dict = {}
    for c in columns:
        if c.data_type == "String":
            row[c.name] = " "    # non-empty: DBCC rejects zero-length strings
        elif c.data_type == "Boolean":
            row[c.name] = False
        else:                    # Int64, Double, Decimal, DateTime
            row[c.name] = 0
    return row


class DataModelBuilder(ABC):
    """Abstract DataModel backend. Build a PBIX (bytes) from a SemanticModel."""

    @abstractmethod
    def build(self, model: SemanticModel) -> bytes:
        ...


class PbixMcpDataModelBuilder(DataModelBuilder):
    """Adapter over the pbix-mcp PBIXBuilder."""

    def __init__(self) -> None:
        self._detector = MSourceDetector()

    def build(self, model: SemanticModel) -> bytes:
        """Build a complete valid PBIX from the semantic model."""
        builder = PBIXBuilder()

        for t in model.tables:
            self._add_table(builder, t)
            for m in t.measures:
                builder.add_measure(t.name, m.name, m.expression)

        for r in model.relationships:
            builder.add_relationship(
                r.from_table, r.from_column, r.to_table, r.to_column,
            )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return builder.build()

    def _add_table(self, builder: "PBIXBuilder", t: Table) -> None:
        src = self._detector.detect(t.m_expression, t.name)

        if src.refreshable:
            print(f"    [data] {t.name}: {src.kind} source → "
                  f"refreshable (Refresh in Power BI loads the data)")
        else:
            print(f"    [warn] {t.name}: {src.kind} source → "
                  f"not refreshable, table will be empty")

        builder.add_table(
            name       = t.name,
            columns    = [c.model_dump(include={"name", "data_type"}) for c in t.columns],
            rows       = [_sentinel_row(t.columns)],
            hidden     = t.is_hidden,
            source_db  = src.source_db,
            source_csv = src.source_csv,
        )
