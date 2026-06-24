"""Auto-detect TMSL vs TMDL and return the normalised SemanticModel."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..models import SemanticModel
from .tmdl import TmdlParser
from .tmsl import TmslParser


class SemanticModelLoader:
    """Load a semantic model from a *.SemanticModel folder (TMSL or TMDL)."""

    def load(self, sm_folder: Path) -> Optional[SemanticModel]:
        # TMSL: model.bim
        bim = sm_folder / "model.bim"
        if bim.exists():
            print(f"  [model] TMSL  → {bim.relative_to(sm_folder.parent)}")
            return TmslParser().parse(bim)

        # TMDL: definition/ folder
        defn = sm_folder / "definition"
        if defn.is_dir():
            print(f"  [model] TMDL  → {defn.relative_to(sm_folder.parent)}/")
            return TmdlParser().parse_folder(defn)

        print("  [model] (not found — report-only mode)")
        return None
