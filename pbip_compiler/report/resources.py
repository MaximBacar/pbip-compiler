from pathlib import Path


class StaticResourceCollector:

    def collect(self, report_folder: Path, layout: dict) -> dict[str, bytes]:
        resources: dict[str, bytes] = {}
        static_root = report_folder / "StaticResources"

        for wrapper in layout.get("resourcePackages", []):
            # Layout stores packages wrapped as {"resourcePackage": {...}}
            pkg = wrapper.get("resourcePackage", wrapper)
            pkg_name = pkg.get("name", "")

            for item in pkg.get("items", []):
                item_path = item.get("path", "")
                if not item_path:
                    continue

                # The file lives in the PBIP at StaticResources/<pkgName>/<path>
                src = static_root / pkg_name / item_path
                if src.exists():
                    # In the PBIX zip it goes at Report/StaticResources/<pkgName>/<path>
                    zip_key = f"Report/StaticResources/{pkg_name}/{item_path}"
                    resources[zip_key] = src.read_bytes()
                    print(f"  ✓  {zip_key:<55} {len(resources[zip_key]):>10,} bytes  (theme)")
                else:
                    print(f"  –  {pkg_name}/{item_path} not found in StaticResources (skipping)")

        return resources
