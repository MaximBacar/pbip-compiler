from    pbix_mcp.builder    import PBIXBuilder
from    ..models            import Column, SemanticModel, Table
from    .mpatch             import patch_partition_m
from    abc                 import ABC, abstractmethod

import  warnings

class DataModelBuilder(ABC):
    @abstractmethod
    def build(self, model: SemanticModel) -> bytes:
        ...

class PbixMcpDataModelBuilder(DataModelBuilder):

    def _sentinel_row(columns: list[Column]) -> dict:
        """Return one placeholder row with zero/empty values per column type."""
        row: dict = {}
        for c in columns:
            if c.data_type == "String":
                row[c.name] = " "
            elif c.data_type == "Boolean":
                row[c.name] = False
            else:
                row[c.name] = 0
        return row


    def build(self, model: SemanticModel) -> bytes:
        
        builder : PBIXBuilder = PBIXBuilder()

        for table in model.tables:
            self._add_table(builder, table)
            for measure in table.measures:
                builder.add_measure(table.name, measure.name, measure.expression)

        for relationship in model.relationships:
            builder.add_relationship(
                relationship.from_table, relationship.from_column, relationship.to_table, relationship.to_column,
            )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pbix_bytes : bytes = builder.build()

        # Overwrite pbix-mcp's placeholder partition query with the real M, so
        # Refresh loads the data. Tables without an M keep the placeholder.
        m_by_table = {t.name: t.m_expression for t in model.tables if t.m_expression}
        for table in model.tables:
            if table.m_expression:
                print(f"    [data] {table.name}: M preserved → refreshable "
                      f"(Refresh in Power BI loads the data)")
            else:
                print(f"    [warn] {table.name}: no partition M → empty table")

        return patch_partition_m(pbix_bytes, m_by_table)

    def _add_table(self, builder: PBIXBuilder, t: Table) -> None:
        # No source_db: pbix-mcp writes a placeholder #table query, which build()
        # overwrites with the table's real M. One sentinel row keeps VertiPaq's
        # column store valid (rows=[] corrupts it).
        builder.add_table(
            name    = t.name,
            columns = [c.model_dump(include={"name", "data_type"}) for c in t.columns],
            rows    = [PbixMcpDataModelBuilder._sentinel_row(t.columns)],
            hidden  = t.is_hidden,
        )
