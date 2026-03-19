"""Hand-written tokenizer for the DECL language."""

from __future__ import annotations

from .errors import LexError, SourceLocation
from .tokens import KEYWORDS, Token, TokenType
from .units import parse_unit


class Lexer:
    def __init__(self, source: str, filename: str = "<stdin>") -> None:
        self._src = source
        self._filename = filename
        self._pos = 0
        self._line = 1
        self._col = 1

    def _loc(self) -> SourceLocation:
        return SourceLocation(self._filename, self._line, self._col)

    def _peek(self) -> str:
        if self._pos >= len(self._src):
            return ""
        return self._src[self._pos]

    def _peek2(self) -> str:
        if self._pos + 1 >= len(self._src):
            return ""
        return self._src[self._pos + 1]

    def _advance(self) -> str:
        ch = self._src[self._pos]
        self._pos += 1
        if ch == "\n":
            self._line += 1
            self._col = 1
        else:
            self._col += 1
        return ch

    def _skip_whitespace_and_comments(self) -> None:
        while self._pos < len(self._src):
            ch = self._peek()
            if ch in " \t\r\n":
                self._advance()
            elif ch == "/" and self._peek2() == "/":
                while self._pos < len(self._src) and self._peek() != "\n":
                    self._advance()
            else:
                break

    def _read_string(self) -> Token:
        loc = self._loc()
        self._advance()  # opening "
        chars: list[str] = []
        while self._pos < len(self._src):
            ch = self._peek()
            if ch == '"':
                self._advance()
                return Token(TokenType.STRING, "".join(chars), loc)
            if ch == "\n":
                raise LexError("Unterminated string literal", loc)
            chars.append(self._advance())
        raise LexError("Unterminated string literal", loc)

    def _read_system_import_path(self) -> Token:
        """Path inside ``import <protocols/foo.decl>`` (C++-style system include)."""
        loc = self._loc()
        self._advance()  # <
        chars: list[str] = []
        while self._pos < len(self._src):
            c = self._peek()
            if c == ">":
                self._advance()
                path = "".join(chars).strip()
                if not path:
                    raise LexError("Empty path in import <...>", loc)
                return Token(TokenType.SYSTEM_IMPORT_PATH, path, loc)
            if c == "\n" or c == "<":
                raise LexError("Unterminated system import path (expected >)", loc)
            chars.append(self._advance())
        raise LexError("Unterminated system import path", loc)

    def _read_number_or_unit(self) -> Token:
        loc = self._loc()
        start = self._pos

        while self._pos < len(self._src) and (self._peek().isdigit() or self._peek() == "."):
            self._advance()

        # Try to read a unit suffix (prefix + unit) directly attached to the number
        unit_start = self._pos
        while self._pos < len(self._src) and self._peek().isalpha():
            self._advance()

        # Also consume % for percentage
        if self._pos < len(self._src) and self._peek() == "%":
            self._advance()

        full_text = self._src[start : self._pos]
        uv = parse_unit(full_text)
        if uv is not None:
            return Token(TokenType.UNIT_LITERAL, uv, loc)

        # Not a unit -- backtrack the alpha portion and return just the number
        self._pos = unit_start
        self._col = loc.col + (unit_start - start)
        num_text = self._src[start:unit_start]
        try:
            value = int(num_text) if "." not in num_text else float(num_text)
        except ValueError:
            raise LexError(f"Invalid numeric literal: {num_text}", loc)
        return Token(TokenType.NUMBER, value, loc)

    def _read_ident_or_keyword(self) -> Token:
        loc = self._loc()
        start = self._pos
        while self._pos < len(self._src) and (
            self._peek().isalnum() or self._peek() == "_"
        ):
            self._advance()
        text = self._src[start : self._pos]
        tt = KEYWORDS.get(text, TokenType.IDENT)
        return Token(tt, text, loc)

    def _next_token(self) -> Token:
        self._skip_whitespace_and_comments()

        if self._pos >= len(self._src):
            return Token(TokenType.EOF, None, self._loc())

        loc = self._loc()
        ch = self._peek()

        if ch == '"':
            return self._read_string()

        if ch == "<":
            return self._read_system_import_path()

        # Negative number: '-' followed by digit (e.g. TemperatureRange(-40, 85))
        if ch == "-" and self._peek2().isdigit():
            neg_loc = self._loc()
            self._advance()  # consume '-'
            tok = self._read_number_or_unit()
            if tok.type == TokenType.NUMBER:
                return Token(TokenType.NUMBER, -tok.value, neg_loc)
            # Unit literal after minus (e.g. -5V): treat as invalid for now
            raise LexError("Negative unit literal not supported", tok.loc)

        if ch.isdigit():
            return self._read_number_or_unit()

        if ch.isalpha() or ch == "_":
            return self._read_ident_or_keyword()

        # Two-character symbols
        ch2 = ch + self._peek2()
        if ch2 == "->":
            self._advance()
            self._advance()
            return Token(TokenType.ARROW, "->", loc)
        if ch2 == "--":
            self._advance()
            self._advance()
            return Token(TokenType.DASH_DASH, "--", loc)

        # Single-character symbols
        SINGLE: dict[str, TokenType] = {
            "{": TokenType.LBRACE,
            "}": TokenType.RBRACE,
            "(": TokenType.LPAREN,
            ")": TokenType.RPAREN,
            ":": TokenType.COLON,
            ".": TokenType.DOT,
            ",": TokenType.COMMA,
            "=": TokenType.EQUALS,
            "*": TokenType.STAR,
        }
        if ch in SINGLE:
            self._advance()
            return Token(SINGLE[ch], ch, loc)

        raise LexError(f"Unexpected character: {ch!r}", loc)

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while True:
            tok = self._next_token()
            tokens.append(tok)
            if tok.type == TokenType.EOF:
                break
        return tokens
