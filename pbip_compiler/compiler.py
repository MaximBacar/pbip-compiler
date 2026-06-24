"""Public entry point — orchestrate the .pbip → .pbix compilation."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from .datamodel import PbixMcpDataModelBuilder
from .discovery import (
    find_report_folder,
    find_semantic_model_folder,
    read_live_connection,
)
from .pbix import PbixAssembler
from .report import ReportLayoutLoader
from .semantic_model import SemanticModelLoader


class PbipCompiler:
    """Compile a .pbip project folder into a .pbix file."""

    def __init__(self, pbip_path : Union[Path, str]) -> None:
        self._model_loader      = SemanticModelLoader()
        self._layout_loader     = ReportLayoutLoader()
        self._datamodel_builder = PbixMcpDataModelBuilder()
        self._assembler         = PbixAssembler()

        self.pbip_path : Path   = Path(pbip_path).resolve()

    def compile(self, output: Union[Path, str]) -> Path:
        """Compile the project and write the .pbix to ``output``."""
        output : Path = Path(output).resolve()
        self._compile(output)
        return output

    def compile_to_bytes(self) -> bytes:
        """Compile the project and return the .pbix as bytes (no file written)."""
        return self._compile(None)

    def _compile(self, output: Optional[Path]) -> bytes:

        print(f"[pbip→pbix]")
        print(f"  source : {self.pbip_path}")


        report_folder = find_report_folder(self.pbip_path)
        print(f"  report : {report_folder.relative_to(self.pbip_path)}/")

        # Live connection (report bound to a published semantic model): no local
        # model — embed the PBIR report + a Connections part and we're done.
        connection_string = read_live_connection(report_folder)
        if connection_string:
            print(f"  model  : live connection (remote semantic model)")
            return self._assembler.assemble_live_connection(
                output, report_folder, connection_string,
            )

        semantic_folder = find_semantic_model_folder(self.pbip_path)
        print(f"  model  : {semantic_folder.relative_to(self.pbip_path) if semantic_folder else '(none)'}/")

        # report layout
        layout = self._layout_loader.load(report_folder)
        print(f"  pages  : {len(layout.get('sections', []))}")

        # base pbix
        base_pbix = self._build_base_pbix(semantic_folder)

        # Assemble
        return self._assembler.assemble(output, layout, base_pbix, report_folder=report_folder)

    def _build_base_pbix(self, semantic_folder: Optional[Path]) -> Optional[bytes]:
        if not semantic_folder:
            print("  data   : no SemanticModel folder — thin report")
            return None

        model = self._model_loader.load(semantic_folder)
        if not model or not model.tables:
            print("  data   : semantic model empty — thin report")
            return None

        n_t = len(model.tables)
        n_m = sum(len(t.measures) for t in model.tables)
        n_r = len(model.relationships)
        print(f"  data   : building DataModel "
              f"({n_t} tables, {n_m} measures, {n_r} relationships)")

        return self._datamodel_builder.build(model)

