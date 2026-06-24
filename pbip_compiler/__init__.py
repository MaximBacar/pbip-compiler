"""pbip_compiler — compile a Power BI Project (.pbip) folder into a full .pbix file.

Pure Python — no CLI tools, no Power BI Desktop, no Windows required.

Public API
──────────
    from pbip_compiler import compile_pbip
    compile_pbip("./MyProject", "./MyReport.pbix")

Package layout
──────────────
    discovery        – locate the .Report / .SemanticModel folders
    semantic_model/  – parse TMSL (model.bim) and TMDL into a normalised model
    datamodel/       – build the VertiPaq DataModel via pbix-mcp (+ data fetch)
    report/          – compile the PBIR report into a legacy Report/Layout
    pbix/            – assemble the final .pbix ZIP
    compiler         – orchestrates the above (compile_pbip)
"""

from __future__ import annotations

from .compiler import PbipCompiler
from .models import (
    Column,
    Measure,
    Relationship,
    SemanticModel,
    Table,
)

__all__ = [
    "PbipCompiler",
    "SemanticModel",
    "Table",
    "Column",
    "Measure",
    "Relationship",
]
