"""Error and warning types with source location tracking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SourceLocation:
    file: str = "<unknown>"
    line: int = 0
    col: int = 0

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.col}"


class DeclError(Exception):
    """Base class for all DECL errors."""

    def __init__(self, message: str, loc: Optional[SourceLocation] = None) -> None:
        self.loc = loc
        if loc:
            super().__init__(f"{loc}: {message}")
        else:
            super().__init__(message)


class LexError(DeclError):
    """Error during lexical analysis."""
    pass


class ParseError(DeclError):
    """Error during parsing."""
    pass


class AnalysisError(DeclError):
    """Error during semantic analysis."""

    def __init__(
        self, code: str, message: str, loc: Optional[SourceLocation] = None
    ) -> None:
        self.code = code
        full = f"[{code}] {message}"
        super().__init__(full, loc)


@dataclass(frozen=True)
class Warning:
    code: str
    message: str
    loc: Optional[SourceLocation] = None

    def __str__(self) -> str:
        prefix = f"{self.loc}: " if self.loc else ""
        return f"{prefix}[{self.code}] {self.message}"
