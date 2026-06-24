"""Load the report layout from a PBIP report folder.

Supports PBIR-legacy (Report/report.json) and PBIR (definition/ folder).
"""

from __future__ import annotations

import json
from pathlib import Path

from .pbir import PbirCompiler


class ReportLayoutLoader:
    """Produce a legacy Report/Layout dict from a *.Report folder."""

    def load(self, report_folder: Path) -> dict:
        # A: PBIR-legacy flat report.json
        flat = report_folder / "report.json"
        if flat.exists():
            with open(flat, encoding="utf-8") as f:
                return json.load(f)

        # B: PBIR definition/ folder
        defn_dir = report_folder / "definition"
        if defn_dir.is_dir():
            return PbirCompiler().compile(defn_dir)

        print("  [report] No report.json or definition/ found — blank layout")
        return self._blank_layout()

    @staticmethod
    def _blank_layout() -> dict:
        return {
            "id": 0,
            "resourcePackages": [],
            "sections": [{
                "id": 0,
                "name": "ReportSection",
                "displayName": "Page 1",
                "visualContainers": [],
                "config": "{}",
                "filters": "[]",
                "ordinal": 0,
                "width": 1280,
                "height": 720,
            }],
            "config": "{}",
            "filters": "[]",
            "layoutOptimization": 0,
        }
