from    pbip_compiler.report.resources  import StaticResourceCollector
from    .constants          import LIVE_CONTENT_TYPES, LIVE_METADATA, LIVE_SETTINGS, LIVE_VERSION, THIN_CONTENT_TYPES, THIN_DIAGRAM, THIN_METADATA, THIN_SETTINGS, THIN_VERSION

from    pathlib             import Path
from    typing              import Optional
from    io                  import BytesIO

import  json
import  zipfile

class PbixAssembler:
    """Write the final .pbix file from a layout and an optional base PBIX."""

    def __init__(self) -> None:
        self._resources = StaticResourceCollector()

    def assemble(
        self,
        output_path: Path,
        layout: dict,
        base_pbix: Optional[bytes],
        report_folder: Optional[Path] = None,  # for copying theme/static resources
    ) -> None:
        print(f"\n[build] Assembling {output_path.name} …")

        if base_pbix is not None:
            raw = self._patch_layout_into_pbix(base_pbix, layout, report_folder)
        else:
            raw = self._build_thin_pbix(layout)

        output_path.write_bytes(raw)
        print(f"\n[done] {output_path}  ({len(raw) / 1024:,.1f} KB)")

    def _patch_layout_into_pbix(
        self,
        base_pbix: bytes,
        layout: dict,
        report_folder: Optional[Path],
    ) -> bytes:
        """Replace Report/Layout in a pbix-mcp-generated PBIX with our own layout,
        and embed any StaticResources (themes) referenced by resourcePackages.

        Without the theme files the report engine raises "report load failed"
        even though the DataModel loads fine — the layout references them by path.
        """
        layout_bytes = json.dumps(
            layout, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-16-le")

        extra_files: dict[str, bytes] = {}
        if report_folder is not None:
            extra_files = self._resources.collect(report_folder, layout)

        buf = BytesIO()
        with zipfile.ZipFile(BytesIO(base_pbix)) as zf_in:
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf_out:
                for name in zf_in.namelist():
                    if name == "Report/Layout":
                        info = zipfile.ZipInfo(filename=name)
                        info.compress_type = zipfile.ZIP_DEFLATED
                        zf_out.writestr(info, layout_bytes)
                        print(f"  ✓  {name:<55} {len(layout_bytes):>10,} bytes  (from PBIP)")
                    elif name == "DataModel":
                        raw = zf_in.read(name)
                        info = zipfile.ZipInfo(filename=name)
                        info.compress_type = zipfile.ZIP_STORED
                        zf_out.writestr(info, raw)
                        print(f"  ✓  {name:<55} {len(raw):>10,} bytes  (from pbix-mcp)")
                    else:
                        raw = zf_in.read(name)
                        info = zipfile.ZipInfo(filename=name)
                        info.compress_type = zipfile.ZIP_DEFLATED
                        zf_out.writestr(info, raw)
                        print(f"  ✓  {name:<55} {len(raw):>10,} bytes")

                for zip_key, data in extra_files.items():
                    info = zipfile.ZipInfo(filename=zip_key)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    zf_out.writestr(info, data)

        return buf.getvalue()

    def _build_thin_pbix(self, layout: dict) -> bytes:
        """Build a minimal PBIX with no DataModel (thin/report-only).

        Opens in Power BI Desktop as an empty report that can connect to
        an external semantic model (Live Connection or DirectQuery).
        """
        layout_bytes = json.dumps(
            layout, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-16-le")

        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            def add(name: str, data: bytes, compress: bool = True) -> None:
                info = zipfile.ZipInfo(filename=name)
                info.compress_type = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
                zf.writestr(info, data)
                print(f"  ✓  {name:<55} {len(data):>10,} bytes")

            add("Version",             THIN_VERSION,        compress=False)
            add("[Content_Types].xml", THIN_CONTENT_TYPES)
            add("DiagramLayout",       THIN_DIAGRAM)
            add("Settings",            THIN_SETTINGS)
            add("Metadata",            THIN_METADATA)
            add("Report/Layout",       layout_bytes)
            print("  –  DataModel                                              (omitted — thin report)")
        return buf.getvalue()

    # ── Live connection (connect to a published semantic model) ──────────────
    def assemble_live_connection(
        self,
        output_path: Path,
        report_folder: Path,
        connection_string: str,
    ) -> None:
        """Write a live-connection .pbix: no DataModel, a Connections part, and
        the PBIR report (definition/ + StaticResources/) embedded verbatim under
        Report/. The report binds to the remote model named in connection_string.
        """
        print(f"\n[build] Assembling {output_path.name} (live connection) …")

        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            def add(name: str, data: bytes, compress: bool = True) -> None:
                info = zipfile.ZipInfo(filename=name)
                info.compress_type = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
                zf.writestr(info, data)
                print(f"  ✓  {name:<60} {len(data):>10,} bytes")

            add("Version",             LIVE_VERSION, compress=False)
            add("[Content_Types].xml", LIVE_CONTENT_TYPES)
            add("Settings",            LIVE_SETTINGS)
            add("Metadata",            LIVE_METADATA)
            add("Connections",         self._build_connections(connection_string))

            # Embed the PBIR report verbatim: definition/ + StaticResources/.
            # (definition.pbir, .platform, .pbi … stay out — not PBIX parts.)
            for sub in ("definition", "StaticResources"):
                base = report_folder / sub
                if not base.is_dir():
                    continue
                for f in sorted(base.rglob("*")):
                    if f.is_file():
                        rel = f.relative_to(report_folder).as_posix()
                        add(f"Report/{rel}", f.read_bytes())

            print("  –  DataModel                                              (omitted — live connection)")

        output_path.write_bytes(buf.getvalue())
        print(f"\n[done] {output_path}  ({len(buf.getvalue()) / 1024:,.1f} KB)")

    @staticmethod
    def _build_connections(connection_string: str) -> bytes:
        """Turn a PBIP byConnection string into the PBIX Connections part (UTF-8).

        The PBIP connectionString carries the standard AS/Power BI keys plus
        extra semanticmodelid/modelid params; the PBIX Connections part keeps the
        four standard keys and lifts modelid → PbiServiceModelId, initial catalog
        → PbiModelDatabaseName.
        """
        pairs = PbixAssembler._parse_conn_string(connection_string)

        def unquote(s: str) -> str:
            return s[1:-1] if len(s) >= 2 and s[0] == '"' and s[-1] == '"' else s

        ds   = pairs.get("data source", "")
        ic   = pairs.get("initial catalog", "")
        ip   = unquote(pairs.get("identity provider", ""))
        isec = pairs.get("integrated security", "ClaimsToken")

        clean = (f'Data Source={ds};Initial Catalog={ic};'
                 f'Identity Provider="{ip}";Integrated Security={isec}')

        conn: dict = {
            "Name": "EntityDataSource",
            "ConnectionString": clean,
            "ConnectionType": "pbiServiceLive",
        }
        if "modelid" in pairs:
            try:
                conn["PbiServiceModelId"] = int(pairs["modelid"])
            except ValueError:
                pass
        conn["PbiModelVirtualServerName"] = "sobe_wowvirtualserver"
        conn["PbiModelDatabaseName"] = ic

        doc = {"Version": 2, "Connections": [conn]}
        return json.dumps(doc, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def _parse_conn_string(cs: str) -> dict:
        """Parse a `key=value;…` connection string into a lowercased-key dict,
        respecting double-quoted values (which may contain commas)."""
        parts: list[str] = []
        buf, in_quotes = "", False
        for ch in cs:
            if ch == '"':
                in_quotes = not in_quotes
                buf += ch
            elif ch == ";" and not in_quotes:
                parts.append(buf)
                buf = ""
            else:
                buf += ch
        if buf.strip():
            parts.append(buf)

        pairs: dict = {}
        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                pairs[k.strip().lower()] = v.strip()
        return pairs
