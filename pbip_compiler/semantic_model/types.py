"""Data-type maps: PBIP (TMSL/TMDL) dataType → pbix-mcp data_type string."""

from __future__ import annotations

# BIM (TMSL) dataType → PBIXBuilder data_type string
BIM_TYPE_MAP: dict[str, str] = {
    "string":   "String",
    "int64":    "Int64",
    "double":   "Double",
    "float64":  "Double",
    "decimal":  "Decimal",
    "dateTime": "DateTime",
    "boolean":  "Boolean",
    "binary":   "String",   # fallback
    "variant":  "String",
}

# TMDL dataType → PBIXBuilder data_type string
TMDL_TYPE_MAP: dict[str, str] = {
    "string":   "String",
    "int64":    "Int64",
    "double":   "Double",
    "decimal":  "Decimal",
    "dateTime": "DateTime",
    "boolean":  "Boolean",
    "binary":   "String",
}


def bim_type(dt: str) -> str:
    return BIM_TYPE_MAP.get(dt, "String")


def tmdl_type(raw: str) -> str:
    return TMDL_TYPE_MAP.get(raw.strip().lower(), "String")
