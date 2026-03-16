"""Token types for the DECL lexer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional

from .errors import SourceLocation


class TokenType(Enum):
    # Literals
    NUMBER = auto()
    STRING = auto()
    UNIT_LITERAL = auto()

    # Identifier
    IDENT = auto()

    # Keywords
    KW_PROTOCOL = auto()
    KW_COMPONENT = auto()
    KW_SCHEMATIC = auto()
    KW_IMPORT = auto()
    KW_PINS = auto()
    KW_FEATURES = auto()
    KW_ATTRIBUTES = auto()
    KW_INTERNAL = auto()
    KW_EXTERNAL = auto()
    KW_USING = auto()
    KW_ROLE = auto()
    KW_LINES = auto()
    KW_RULES = auto()
    KW_COMMON = auto()
    KW_INSTANCE = auto()
    KW_NET = auto()
    KW_CONNECT = auto()
    KW_WIRE = auto()
    KW_AS = auto()
    KW_PIN = auto()
    KW_VARIANT = auto()
    KW_OF = auto()
    KW_PINOUT = auto()

    # Pin types (also act as keywords)
    PIN_INPUT = auto()
    PIN_OUTPUT = auto()
    PIN_BIDIRECTIONAL = auto()
    PIN_TRISTATE = auto()
    PIN_PASSIVE = auto()
    PIN_FREE = auto()
    PIN_POWER_INPUT = auto()
    PIN_POWER_OUTPUT = auto()
    PIN_UNCONNECTED = auto()
    PIN_ANALOG = auto()
    PIN_OPEN_DRAIN = auto()

    # Symbols
    LBRACE = auto()       # {
    RBRACE = auto()       # }
    LPAREN = auto()       # (
    RPAREN = auto()       # )
    COLON = auto()        # :
    DOT = auto()          # .
    COMMA = auto()        # ,
    EQUALS = auto()       # =
    ARROW = auto()        # ->
    DASH_DASH = auto()    # --

    # Special
    EOF = auto()


KEYWORDS: dict[str, TokenType] = {
    "protocol": TokenType.KW_PROTOCOL,
    "component": TokenType.KW_COMPONENT,
    "schematic": TokenType.KW_SCHEMATIC,
    "import": TokenType.KW_IMPORT,
    "pins": TokenType.KW_PINS,
    "features": TokenType.KW_FEATURES,
    "attributes": TokenType.KW_ATTRIBUTES,
    "internal": TokenType.KW_INTERNAL,
    "external": TokenType.KW_EXTERNAL,
    "using": TokenType.KW_USING,
    "role": TokenType.KW_ROLE,
    "lines": TokenType.KW_LINES,
    "rules": TokenType.KW_RULES,
    "common": TokenType.KW_COMMON,
    "instance": TokenType.KW_INSTANCE,
    "net": TokenType.KW_NET,
    "connect": TokenType.KW_CONNECT,
    "wire": TokenType.KW_WIRE,
    "as": TokenType.KW_AS,
    "pin": TokenType.KW_PIN,
    "variant": TokenType.KW_VARIANT,
    "of": TokenType.KW_OF,
    "pinout": TokenType.KW_PINOUT,
    # Pin types
    "Input": TokenType.PIN_INPUT,
    "Output": TokenType.PIN_OUTPUT,
    "Bidirectional": TokenType.PIN_BIDIRECTIONAL,
    "TriState": TokenType.PIN_TRISTATE,
    "Passive": TokenType.PIN_PASSIVE,
    "Free": TokenType.PIN_FREE,
    "PowerInput": TokenType.PIN_POWER_INPUT,
    "PowerOutput": TokenType.PIN_POWER_OUTPUT,
    "Unconnected": TokenType.PIN_UNCONNECTED,
    "Analog": TokenType.PIN_ANALOG,
    "OpenDrain": TokenType.PIN_OPEN_DRAIN,
}

PIN_TYPE_TOKENS = {
    TokenType.PIN_INPUT,
    TokenType.PIN_OUTPUT,
    TokenType.PIN_BIDIRECTIONAL,
    TokenType.PIN_TRISTATE,
    TokenType.PIN_PASSIVE,
    TokenType.PIN_FREE,
    TokenType.PIN_POWER_INPUT,
    TokenType.PIN_POWER_OUTPUT,
    TokenType.PIN_UNCONNECTED,
    TokenType.PIN_ANALOG,
    TokenType.PIN_OPEN_DRAIN,
}


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: Any
    loc: SourceLocation

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, {self.loc})"
