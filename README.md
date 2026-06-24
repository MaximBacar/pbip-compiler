# pbip-compiler

Compile a **Power BI Project (`.pbip`)** folder into a single **`.pbix`** file —
in pure Python. No Power BI Desktop, no external CLI tools, no Windows required.

It parses the project's semantic model (TMDL / `model.bim`) and PBIR report,
builds a real VertiPaq `DataModel` (via [`pbix-mcp`](https://pypi.org/project/pbix-mcp/)),
preserves each table's Power Query (M) so the report stays refreshable, and
assembles the final `.pbix` ZIP.

## Features

- 📦 `.pbip` → `.pbix` entirely in Python
- 🧮 Builds a real VertiPaq DataModel (tables, columns, measures, relationships)
- 🔁 Preserves partition M expressions → **Refresh** in Power BI loads the data
- 🌐 Handles **live-connection** reports (bound to a published semantic model)
- 🪶 Falls back to a thin / report-only `.pbix` when there is no local model

## Installation

```bash
# with uv (recommended)
uv add pbip-compiler

# or with pip
pip install pbip-compiler
```

Requires Python ≥ 3.11.

## Quick start (CLI)

```bash
pbip-compiler --pbip ./MyProject --output ./MyReport.pbix
```

## Using `pbip_compiler` as a module

### 1. Compile a `.pbip` folder to a `.pbix` file

```python
from pbip_compiler import PbipCompiler

compiler = PbipCompiler("./MyProject")        # path to the .pbip folder
output = compiler.compile("./MyReport.pbix")  # returns the resolved Path

print(f"Compiled → {output}")
```

### 2. Compile to bytes (no file written)

Useful when serving the result over HTTP, uploading it, or writing it yourself.

```python
from pbip_compiler import PbipCompiler

compiler = PbipCompiler("./MyProject")
pbix_bytes: bytes = compiler.compile_to_bytes()

# e.g. write it yourself, stream it, upload it...
with open("MyReport.pbix", "wb") as f:
    f.write(pbix_bytes)
```

### 3. Handle errors

```python
from pathlib import Path
from pbip_compiler import PbipCompiler

try:
    result: Path = PbipCompiler("./MyProject").compile("./out.pbix")
    print(f"✅ Success → {result}")
except FileNotFoundError as exc:
    # e.g. no *.Report folder inside the project
    print(f"❌ Project layout problem: {exc}")
except Exception as exc:
    print(f"❌ Compilation failed: {exc}")
```

### 4. Build a `.pbix` from a semantic model defined in code

You don't have to start from a `.pbip` folder. You can describe a model with the
data classes and build the DataModel directly.

```python
from pbip_compiler import Column, Measure, Relationship, SemanticModel, Table
from pbip_compiler.datamodel import PbixMcpDataModelBuilder

model = SemanticModel(
    tables=[
        Table(
            name="Sales",
            columns=[
                Column(name="OrderId",   data_type="Int64"),
                Column(name="ProductId", data_type="Int64"),
                Column(name="Amount",    data_type="Decimal"),
            ],
            measures=[
                Measure(name="Total Sales", expression="SUM(Sales[Amount])"),
            ],
            # Power Query (M) source — preserved so Refresh loads the data
            m_expression='let Source = Csv.Document(File.Contents("sales.csv")) in Source',
        ),
        Table(
            name="Product",
            columns=[
                Column(name="ProductId", data_type="Int64"),
                Column(name="Name",      data_type="String"),
            ],
        ),
    ],
    relationships=[
        Relationship(
            from_table="Sales",   from_column="ProductId",
            to_table="Product",   to_column="ProductId",
        ),
    ],
)

datamodel_bytes: bytes = PbixMcpDataModelBuilder().build(model)
```

## Public API

| Object | Description |
| --- | --- |
| `PbipCompiler(pbip_path)` | Orchestrates a `.pbip` → `.pbix` compilation. |
| `PbipCompiler.compile(output)` | Compile and write the `.pbix`; returns the `Path`. |
| `PbipCompiler.compile_to_bytes()` | Compile and return the `.pbix` as `bytes`. |
| `SemanticModel` | A model: `tables` + `relationships`. |
| `Table` | `name`, `columns`, `measures`, `is_hidden`, `m_expression`. |
| `Column` | `name`, `data_type`, `source_column`. |
| `Measure` | `name`, `expression` (DAX). |
| `Relationship` | `from_table`/`from_column` → `to_table`/`to_column`. |

## How it works

```
.pbip folder
   ├── *.Report/         → PBIR report  ─┐
   └── *.SemanticModel/  → TMDL / .bim  ─┤
                                         ▼
        SemanticModelLoader  +  ReportLayoutLoader
                                         ▼
        PbixMcpDataModelBuilder  (VertiPaq DataModel, M preserved)
                                         ▼
        PbixAssembler  →  MyReport.pbix
```

- **Live connection** — if the report binds to a published semantic model, no
  local DataModel is built; the report + a Connections part are embedded.
- **No / empty semantic model** — a thin (report-only) `.pbix` is produced.

## License

[MIT](LICENSE) © 2026 Maxim Bacar