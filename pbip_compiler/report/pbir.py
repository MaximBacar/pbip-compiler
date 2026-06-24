from    pathlib import Path
import  json


class PbirCompiler:
    """Convert a PBIR definition/ folder into a legacy Report/Layout dict."""

    _RESOURCE_PKG_TYPE: dict[str, int] = {
        "RegisteredResources": 1,
        "SharedResources":     2,
    }
    _RESOURCE_ITEM_TYPE: dict[str, int] = {
        "Image":      100,
        "BaseTheme":  202,
        "CustomTheme": 600,
    }
    _DISPLAY_OPTION: dict[str, int] = {
        "FitToPage":   1,
        "FitToWidth":  2,
        "ActualSize":  0,
    }
    _EXPORT_DATA_MODE: dict[str, int] = {
        "AllowSummarized": 1,
        "DenySummarized":  0,
    }
    # The legacy report config needs a schema version or Desktop rejects the report.
    _LEGACY_LAYOUT_VERSION = "5.73"

    def compile(self, defn_dir: Path) -> dict:
        # Top-level report config (theme, resourcePackages, settings, objects)
        report_cfg: dict = {}
        report_cfg_path = defn_dir / "report.json"
        if report_cfg_path.exists():
            with open(report_cfg_path, encoding="utf-8") as f:
                report_cfg = json.load(f)

        # resourcePackages: convert to the legacy wrapped/numeric form
        resource_packages = self._legacy_resource_packages(
            report_cfg.get("resourcePackages", [])
        )

        # Global report config — MUST carry a version + themeCollection or the
        # report fails to load even though the DataModel is fine.
        report_level_cfg: dict = {"version": self._LEGACY_LAYOUT_VERSION}
        theme_collection = self._legacy_theme_collection(report_cfg.get("themeCollection", {}))
        if theme_collection:
            report_level_cfg["themeCollection"] = theme_collection
        report_level_cfg["activeSectionIndex"] = 0
        if "settings" in report_cfg:
            report_level_cfg["settings"] = self._legacy_settings(report_cfg["settings"])
            if report_cfg["settings"].get("defaultDrillFilterOtherVisuals"):
                report_level_cfg["defaultDrillFilterOtherVisuals"] = True
        if "objects" in report_cfg:
            report_level_cfg["objects"] = report_cfg["objects"]

        sections = self._compile_sections(defn_dir)

        return {
            "id": 0,
            "resourcePackages": resource_packages,
            "sections": sections,
            "config": json.dumps(report_level_cfg, separators=(",", ":")) if report_level_cfg else "{}",
            "filters": "[]",
            "layoutOptimization": 0,
        }

    # ── sections / pages ─────────────────────────────────────────────────
    def _compile_sections(self, defn_dir: Path) -> list:
        sections: list = []
        pages_dir = defn_dir / "pages"
        if not pages_dir.is_dir():
            return sections

        page_dirs = sorted(
            [p for p in pages_dir.iterdir() if p.is_dir()],
            key=self._page_ordinal,
        )

        for ordinal, page_dir in enumerate(page_dirs):
            page_json_path = page_dir / "page.json"
            if not page_json_path.exists():
                continue
            with open(page_json_path, encoding="utf-8") as f:
                page_data = json.load(f)

            section: dict = {
                "name":        page_data.get("name", f"ReportSection{ordinal + 1}"),
                "displayName": page_data.get("displayName", f"Page {ordinal + 1}"),
                "ordinal":     ordinal,
                "width":       page_data.get("width", 1280),
                "height":      page_data.get("height", 720),
                "config":      "{}",
                "filters":     "[]",
                "visualContainers": [],
            }

            # displayOption is a numeric section-level key in legacy layouts,
            # not a string inside the config blob.
            if "displayOption" in page_data:
                dopt = page_data["displayOption"]
                section["displayOption"] = self._DISPLAY_OPTION.get(dopt, dopt) \
                    if isinstance(dopt, str) else dopt

            page_cfg: dict = {}
            if "objects" in page_data:
                page_cfg["objects"] = page_data["objects"]
            if page_cfg:
                section["config"] = json.dumps(page_cfg, separators=(",", ":"))

            visuals_dir = page_dir / "visuals"
            if visuals_dir.is_dir():
                visual_dirs = sorted(
                    [v for v in visuals_dir.iterdir() if v.is_dir()],
                    key=self._visual_tab_order,
                )
                for vis_dir in visual_dirs:
                    vis_json_path = vis_dir / "visual.json"
                    if vis_json_path.exists():
                        with open(vis_json_path, encoding="utf-8") as f:
                            pbir_vis = json.load(f)
                        section["visualContainers"].append(
                            self._visual_to_legacy(pbir_vis)
                        )

            sections.append(section)
        return sections

    # ── visual conversion ────────────────────────────────────────────────
    def _visual_to_legacy(self, pbir_visual: dict) -> dict:
        """Convert a PBIR visual.json to a legacy Report/Layout visualContainer.

        PBIR (new format) uses position.{x,y,z,width,height,tabOrder},
        visual.query.queryState.<Role>.projections[].field, filterConfig.filters[].field.
        Legacy needs flat x/y/z/width/height, config (singleVisual.projections +
        prototypeQuery), and filters as JSON strings. prototypeQuery From/Select
        use short aliases; projections use queryRefs.
        """
        pos  = pbir_visual.get("position", {})
        vis  = pbir_visual.get("visual", {})
        name = pbir_visual.get("name", "visual_0")
        visual_type = vis.get("visualType", "card")

        query_state = vis.get("query", {}).get("queryState", {})
        from_sources: dict[str, str] = {}   # entity → short alias

        def _alias(entity: str) -> str:
            if entity not in from_sources:
                base = entity[0].lower()
                existing = set(from_sources.values())
                alias, n = base, 0
                while alias in existing:
                    n += 1
                    alias = base + str(n)
                from_sources[entity] = alias
            return from_sources[entity]

        select_list: list = []
        projections: dict[str, list] = {}

        for role, role_data in query_state.items():
            role_projs = []
            for proj in role_data.get("projections", []):
                field = proj.get("field", {})
                qref  = proj.get("queryRef", "")

                if "Column" in field:
                    col    = field["Column"]
                    entity = col["Expression"]["SourceRef"]["Entity"]
                    prop   = col["Property"]
                    alias  = _alias(entity)
                    select_list.append({
                        "Column": {
                            "Expression": {"SourceRef": {"Source": alias}},
                            "Property": prop,
                        },
                        "Name": qref,
                    })
                elif "Aggregation" in field:
                    agg    = field["Aggregation"]
                    icol   = agg["Expression"]["Column"]
                    entity = icol["Expression"]["SourceRef"]["Entity"]
                    prop   = icol["Property"]
                    func   = agg["Function"]
                    alias  = _alias(entity)
                    select_list.append({
                        "Aggregation": {
                            "Expression": {
                                "Column": {
                                    "Expression": {"SourceRef": {"Source": alias}},
                                    "Property": prop,
                                }
                            },
                            "Function": func,
                        },
                        "Name": qref,
                    })
                elif "Measure" in field:
                    meas   = field["Measure"]
                    entity = meas["Expression"]["SourceRef"]["Entity"]
                    prop   = meas["Property"]
                    alias  = _alias(entity)
                    select_list.append({
                        "Measure": {
                            "Expression": {"SourceRef": {"Source": alias}},
                            "Property": prop,
                        },
                        "Name": qref,
                    })

                role_projs.append({"queryRef": qref, "active": True})

            if role_projs:
                projections[role] = role_projs

        from_list = [
            {"Name": alias, "Entity": entity, "Type": 0}
            for entity, alias in from_sources.items()
        ]
        prototype_query = (
            {"Version": 2, "From": from_list, "Select": select_list}
            if from_list else {}
        )

        single_visual: dict = {"visualType": visual_type}
        if projections:
            single_visual["projections"] = projections
        if prototype_query:
            single_visual["prototypeQuery"] = prototype_query
        if "objects" in vis:
            single_visual["objects"] = vis["objects"]
        if vis.get("drillFilterOtherVisuals"):
            single_visual["drillFilterOtherVisuals"] = True

        config = {"name": name, "singleVisual": single_visual}

        filters_list: list = []
        for flt in pbir_visual.get("filterConfig", {}).get("filters", []):
            field    = flt.get("field", {})
            flt_name = flt.get("name", "")
            flt_type = flt.get("type", "Categorical")
            legacy_field: dict = {}

            if "Column" in field:
                col    = field["Column"]
                entity = col["Expression"]["SourceRef"]["Entity"]
                prop   = col["Property"]
                alias  = _alias(entity)
                legacy_field = {
                    "Column": {
                        "Expression": {"SourceRef": {"Source": alias}},
                        "Property": prop,
                    }
                }
            elif "Aggregation" in field:
                agg    = field["Aggregation"]
                icol   = agg["Expression"]["Column"]
                entity = icol["Expression"]["SourceRef"]["Entity"]
                prop   = icol["Property"]
                func   = agg["Function"]
                alias  = _alias(entity)
                legacy_field = {
                    "Aggregation": {
                        "Expression": {
                            "Column": {
                                "Expression": {"SourceRef": {"Source": alias}},
                                "Property": prop,
                            }
                        },
                        "Function": func,
                    }
                }

            if legacy_field:
                filters_list.append({
                    "name": flt_name,
                    "field": legacy_field,
                    "type": flt_type,
                })

        container: dict = {
            "x":      pos.get("x", 0),
            "y":      pos.get("y", 0),
            "width":  pos.get("width", 300),
            "height": pos.get("height", 200),
            "config": json.dumps(config, separators=(",", ":")),
        }
        z = pos.get("z", 0)
        if z:
            container["z"] = z
        if filters_list:
            container["filters"] = json.dumps(filters_list, separators=(",", ":"))

        return container

    # ── PBIR → legacy enum/shape conversions ─────────────────────────────
    def _legacy_resource_packages(self, pbir_packages: list) -> list:
        """PBIR resourcePackages → legacy wrapped/numeric form."""
        out: list = []
        for pkg in pbir_packages:
            items = []
            for item in pkg.get("items", []):
                it = dict(item)
                it["type"] = self._RESOURCE_ITEM_TYPE.get(item.get("type"), item.get("type"))
                items.append(it)
            out.append({
                "resourcePackage": {
                    "name":     pkg.get("name", ""),
                    "type":     self._RESOURCE_PKG_TYPE.get(pkg.get("type"), pkg.get("type")),
                    "items":    items,
                    "disabled": False,
                }
            })
        return out

    def _legacy_theme_collection(self, pbir_theme: dict) -> dict:
        """PBIR themeCollection → legacy form (numeric type, version key)."""
        base = pbir_theme.get("baseTheme")
        if not base:
            return {}
        legacy_base = {
            "name": base.get("name", ""),
            # PBIR calls it reportVersionAtImport; legacy calls it version
            "version": base.get("reportVersionAtImport") or base.get("version") or {},
            "type": self._RESOURCE_PKG_TYPE.get(base.get("type"), base.get("type")),
        }
        return {"baseTheme": legacy_base}

    def _legacy_settings(self, pbir_settings: dict) -> dict:
        """Map PBIR settings string-enums to the legacy numeric equivalents."""
        s = dict(pbir_settings)
        if isinstance(s.get("exportDataMode"), str):
            s["exportDataMode"] = self._EXPORT_DATA_MODE.get(
                s["exportDataMode"], s["exportDataMode"]
            )
        return s

    # ── ordering helpers ─────────────────────────────────────────────────
    @staticmethod
    def _visual_tab_order(vis_dir: Path) -> int:
        p = vis_dir / "visual.json"
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("position", {}).get("tabOrder", 0)
            except Exception:
                pass
        return 0

    @staticmethod
    def _page_ordinal(page_dir: Path) -> int:
        p = page_dir / "page.json"
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f).get("ordinal", 0)
            except Exception:
                pass
        return 0
