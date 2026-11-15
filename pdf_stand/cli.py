from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pdf_stand.pipeline import parse_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pdf-stand", description="Parse PDF tables to JSON")
    sub = parser.add_subparsers(dest="command", required=True)
    parse_p = sub.add_parser("parse", help="Extract tables from a PDF")
    parse_p.add_argument("file", type=Path)
    parse_p.add_argument("--out", type=Path, default=None, help="Write JSON to this path")
    args = parser.parse_args(argv)

    if args.command == "parse":
        result = parse_file(args.file)
        payload = result.to_dict()
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0 if result.ok else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
