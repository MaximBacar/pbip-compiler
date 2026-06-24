import argparse
import sys
from pbip_compiler import PbipCompiler
from pathlib import Path

def main() -> None:
    p = argparse.ArgumentParser(
        description="Compile a .pbip folder into a .pbix file (pure Python).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--pbip",   required=True, help="Path to the .pbip project folder")
    p.add_argument("--output", required=True, help="Destination .pbix path")
    args = p.parse_args()

    compiler : PbipCompiler = PbipCompiler(args.pbip)
    try:
        
        result : Path = compiler.compile(args.output)
        print(f"\n✅  Success → {result}")
        
    except Exception as exc:
        print(f"\n❌  Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
