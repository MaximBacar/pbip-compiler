from typing import Optional

from pydantic import BaseModel, Field


class Column(BaseModel):
    """A storage (non-calculated) column of a table."""
    name: str
    data_type: str = "String"          # pbix-mcp data_type string
    source_column: str = ""            # source field name (defaults to name)

    def model_post_init(self, __context) -> None:
        if not self.source_column:
            object.__setattr__(self, "source_column", self.name)


class Measure(BaseModel):
    name: str
    expression: str = ""


class Relationship(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str


class Table(BaseModel):
    name: str
    columns: list[Column] = Field(default_factory=list)
    measures: list[Measure] = Field(default_factory=list)
    is_hidden: bool = False
    m_expression: str = ""             # partition Power Query (M) source


class SemanticModel(BaseModel):
    tables: list[Table] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)


class MSource(BaseModel):
    """Result of classifying a partition's M source."""
    kind: str = "unknown"              # e.g. "json", "sqlserver", "unknown"
    source_db: Optional[dict] = None   # → PBIXBuilder.add_table(source_db=…)
    source_csv: Optional[str] = None   # → PBIXBuilder.add_table(source_csv=…)
    refreshable: bool = False          # True if Desktop/Service can refresh it
