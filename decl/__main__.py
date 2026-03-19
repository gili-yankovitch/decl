"""CLI entry point for the DECL toolchain."""

import argparse
import sys
from pathlib import Path

from .ast_nodes import ImportDecl, Program
from .errors import AnalysisError, DeclError
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


def _find_stdlib_root(anchor_dir: Path) -> Path | None:
    """Directory that contains both ``protocols/`` and ``components/`` (DECL stdlib layout).

    Also accepts ``<parent>/stdlib/`` when the repo root holds the library in a subfolder.
    """
    anchor_dir = anchor_dir.resolve()
    for d in [anchor_dir, *anchor_dir.parents]:
        proto = d / "protocols"
        comp = d / "components"
        if proto.is_dir() and comp.is_dir():
            return d.resolve()
        nested = d / "stdlib"
        if (nested / "protocols").is_dir() and (nested / "components").is_dir():
            return nested.resolve()
    return None


def _resolve_imports(path: Path, program: Program) -> Program:
    """Resolve all import declarations and return a single program with merged declarations.

    Quoted imports ``import "path"`` resolve relative to the importing file's directory.
    Bracket imports ``import <path>`` resolve relative to the stdlib root (ancestor of the
    entry file containing ``protocols/`` and ``components/``).

    Circular imports raise E001.
    """
    stdlib_root = _find_stdlib_root(path.parent)
    loading: set[Path] = set()
    cache: dict[Path, Program] = {}

    def load_program(current_path: Path) -> Program:
        current_path = current_path.resolve()
        if current_path in loading:
            raise AnalysisError(
                "E001",
                f"Circular import: {current_path}",
                None,
            )
        if current_path in cache:
            return cache[current_path]
        loading.add(current_path)
        try:
            source = current_path.read_text()
            tokens = Lexer(source, filename=str(current_path)).tokenize()
            parsed = Parser(tokens, filename=str(current_path)).parse()
            declarations = [d for d in parsed.declarations if not isinstance(d, ImportDecl)]
            merged_names = {getattr(d, "name", None) for d in declarations}
            for d in parsed.declarations:
                if isinstance(d, ImportDecl):
                    if d.is_system:
                        if stdlib_root is None:
                            raise AnalysisError(
                                "E002",
                                "System import <...> requires a stdlib root directory "
                                "(a parent of the file with both 'protocols/' and 'components/')",
                                d.loc,
                            )
                        resolved = (stdlib_root / d.path).resolve()
                    else:
                        resolved = (current_path.parent / d.path).resolve()
                    if not resolved.exists():
                        raise AnalysisError(
                            "E002",
                            f"Import file not found: {resolved}",
                            d.loc,
                        )
                    sub = load_program(resolved)
                    for sub_d in sub.declarations:
                        name = getattr(sub_d, "name", None)
                        if name is not None and name not in merged_names:
                            declarations.append(sub_d)
                            merged_names.add(name)
            result = Program(declarations=declarations)
            cache[current_path] = result
            return result
        finally:
            loading.discard(current_path)

    return load_program(path)


def _cmd_check(path: Path) -> int:
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    try:
        source = path.read_text()
        lexer = Lexer(source, filename=str(path))
        tokens = lexer.tokenize()
        parser = Parser(tokens, filename=str(path))
        program = parser.parse()
        program = _resolve_imports(path, program)

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
