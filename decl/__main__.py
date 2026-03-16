"""CLI entry point for the DECL toolchain."""

import argparse
import sys
from pathlib import Path

from .errors import DeclError
from .lexer import Lexer
from .parser import Parser
from .analyzer import Analyzer


def main() -> int:
    ap = argparse.ArgumentParser(prog="decl", description="DECL language toolchain")
    sub = ap.add_subparsers(dest="command")

    check_p = sub.add_parser("check", help="Parse and validate a .decl file")
    check_p.add_argument("file", type=Path, help="Path to .decl file")

    args = ap.parse_args()
    if args.command is None:
        ap.print_help()
        return 1

    if args.command == "check":
        return _cmd_check(args.file)

    return 0


def _cmd_check(path: Path) -> int:
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    source = path.read_text()
    try:
        lexer = Lexer(source, filename=str(path))
        tokens = lexer.tokenize()

        parser = Parser(tokens, filename=str(path))
        program = parser.parse()

        analyzer = Analyzer()
        analyzer.analyze(program)

        warnings = analyzer.warnings
        for w in warnings:
            print(f"Warning: {w}", file=sys.stderr)

        print(f"OK: {path} ({len(warnings)} warning(s))")
        return 0

    except DeclError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
