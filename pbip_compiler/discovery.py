import json
from pathlib import Path
from typing import Optional


def find_report_folder(pbip_root: Path) -> Path:
    """Return the *.Report folder (or any folder that looks like a report)."""
    for d in pbip_root.glob("*.Report"):
        if d.is_dir():
            return d
    for d in pbip_root.iterdir():
        if d.is_dir() and (
            (d / "definition.pbir").exists()
            or (d / "report.json").exists()
            or (d / "definition").is_dir()
        ):
            return d
    raise FileNotFoundError(
        f"No *.Report folder found inside {pbip_root}.\n"
        "Expected:  MyProject/MyProject.Report/  (with report.json or definition/)"
    )


def find_semantic_model_folder(pbip_root: Path) -> Optional[Path]:
    """Return the *.SemanticModel folder, or None for a report-only project."""
    for d in pbip_root.glob("*.SemanticModel"):
        if d.is_dir():
            return d
    return None


def read_live_connection(report_folder: Path) -> Optional[str]:
    """Return the live-connection string if the report binds to a remote model.

    A "connect to a published semantic model" report has, in its
    definition.pbir, datasetReference.byConnection.connectionString. Returns
    that string, or None for a local-model (byPath) / model-less report.
    """
    pbir = report_folder / "definition.pbir"
    if not pbir.exists():
        return None
    try:
        with open(pbir, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    by_conn = data.get("datasetReference", {}).get("byConnection")
    if isinstance(by_conn, dict):
        return by_conn.get("connectionString")
    return None
