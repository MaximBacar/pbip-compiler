"""Command-line entry point — compile a .pbip folder into a .pbix file."""

from __future__ import annotations

import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from pathlib import Path

from . import PbipCompiler


def main() -> None:
    parser: ArgumentParser = ArgumentParser(
        description     = "Compile a .pbip folder into a .pbix file (pure Python).",
        formatter_class = RawDescriptionHelpFormatter,
    )
    parser.add_argument("--pbip",   required=True, help="Path to the .pbip project folder")
    parser.add_argument("--output", required=True, help="Destination .pbix path")
    args = parser.parse_args()

    compiler: PbipCompiler = PbipCompiler(args.pbip)

    try:
        result: Path = compiler.compile(args.output)
        print(f"\n✅  Success → {result}")

    except Exception as exc:
        print(f"\n❌  Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()