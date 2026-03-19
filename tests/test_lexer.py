"""Tests for the DECL lexer."""

import pytest

from decl.lexer import Lexer
from decl.tokens import TokenType
from decl.errors import LexError
from decl.units import UnitValue


class TestBasicTokens:
    def _types(self, source: str) -> list[TokenType]:
        return [t.type for t in Lexer(source).tokenize()]

    def test_empty(self):
        assert self._types("") == [TokenType.EOF]

    def test_symbols(self):
        toks = self._types("{ } ( ) : . , = -> --")
        assert toks == [
            TokenType.LBRACE, TokenType.RBRACE,
            TokenType.LPAREN, TokenType.RPAREN,
            TokenType.COLON, TokenType.DOT, TokenType.COMMA,
            TokenType.EQUALS, TokenType.ARROW, TokenType.DASH_DASH,
            TokenType.EOF,
        ]

    def test_keywords(self):
        src = "protocol component schematic import pins features attributes"
        toks = self._types(src)
        assert toks == [
            TokenType.KW_PROTOCOL, TokenType.KW_COMPONENT,
            TokenType.KW_SCHEMATIC, TokenType.KW_IMPORT,
            TokenType.KW_PINS, TokenType.KW_FEATURES,
            TokenType.KW_ATTRIBUTES, TokenType.EOF,
        ]

    def test_pin_type_keywords(self):
        src = "Input Output Bidirectional TriState Passive Free PowerInput PowerOutput Unconnected Analog OpenDrain"
        toks = self._types(src)
        assert toks == [
            TokenType.PIN_INPUT, TokenType.PIN_OUTPUT,
            TokenType.PIN_BIDIRECTIONAL, TokenType.PIN_TRISTATE,
            TokenType.PIN_PASSIVE, TokenType.PIN_FREE,
            TokenType.PIN_POWER_INPUT, TokenType.PIN_POWER_OUTPUT,
            TokenType.PIN_UNCONNECTED,
            TokenType.PIN_ANALOG, TokenType.PIN_OPEN_DRAIN,
            TokenType.EOF,
        ]

    def test_variant_keywords(self):
        toks = self._types("variant of pinout")
        assert toks == [
            TokenType.KW_VARIANT, TokenType.KW_OF, TokenType.KW_PINOUT,
            TokenType.EOF,
        ]

    def test_identifier(self):
        tokens = Lexer("foo_bar Baz123").tokenize()
        assert tokens[0].type == TokenType.IDENT
        assert tokens[0].value == "foo_bar"
        assert tokens[1].type == TokenType.IDENT
        assert tokens[1].value == "Baz123"

    def test_number_int(self):
        tokens = Lexer("42").tokenize()
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == 42

    def test_number_float(self):
        tokens = Lexer("3.14").tokenize()
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == 3.14

    def test_number_negative(self):
        """Negative integer/float literals (e.g. TemperatureRange(-40, 85))."""
        tokens = Lexer("-40").tokenize()
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == -40
        tokens = Lexer("-3.14").tokenize()
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == -3.14

    def test_string(self):
        tokens = Lexer('"hello world"').tokenize()
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello world"

    def test_unterminated_string(self):
        with pytest.raises(LexError, match="Unterminated string"):
            Lexer('"oops').tokenize()

    def test_system_import_path(self):
        tokens = Lexer("import <protocols/spi.decl>").tokenize()
        assert tokens[0].type == TokenType.KW_IMPORT
        assert tokens[1].type == TokenType.SYSTEM_IMPORT_PATH
        assert tokens[1].value == "protocols/spi.decl"
        assert tokens[2].type == TokenType.EOF


class TestUnitLiterals:
    def test_resistance(self):
        tokens = Lexer("10kohm").tokenize()
        assert tokens[0].type == TokenType.UNIT_LITERAL
        uv = tokens[0].value
        assert isinstance(uv, UnitValue)
        assert uv.raw_number == 10
        assert uv.prefix == "k"
        assert uv.suffix == "ohm"
        assert uv.base_value == 10_000.0

    def test_capacitance(self):
        tokens = Lexer("100nF").tokenize()
        uv = tokens[0].value
        assert uv.suffix == "F"
        assert uv.prefix == "n"
        assert uv.base_value == pytest.approx(100e-9)

    def test_voltage(self):
        tokens = Lexer("3.3V").tokenize()
        uv = tokens[0].value
        assert uv.raw_number == 3.3
        assert uv.suffix == "V"
        assert uv.prefix is None
        assert uv.base_value == 3.3

    def test_percentage(self):
        tokens = Lexer("5%").tokenize()
        uv = tokens[0].value
        assert uv.suffix == "%"
        assert uv.base_value == 5.0

    def test_frequency(self):
        tokens = Lexer("8MHz").tokenize()
        uv = tokens[0].value
        assert uv.suffix == "Hz"
        assert uv.prefix == "M"
        assert uv.base_value == 8e6

    def test_data_size(self):
        tokens = Lexer("32kB").tokenize()
        uv = tokens[0].value
        assert uv.suffix == "B"
        assert uv.prefix == "k"

    def test_bare_unit(self):
        tokens = Lexer("0ohm").tokenize()
        uv = tokens[0].value
        assert uv.base_value == 0.0


class TestComments:
    def test_single_line_comment(self):
        tokens = Lexer("foo // ignore this\nbar").tokenize()
        types = [t.type for t in tokens]
        assert types == [TokenType.IDENT, TokenType.IDENT, TokenType.EOF]

    def test_comment_only(self):
        tokens = Lexer("// nothing here").tokenize()
        assert [t.type for t in tokens] == [TokenType.EOF]


class TestSourceLocation:
    def test_line_tracking(self):
        tokens = Lexer("a\nb\nc").tokenize()
        assert tokens[0].loc.line == 1
        assert tokens[1].loc.line == 2
        assert tokens[2].loc.line == 3

    def test_column_tracking(self):
        tokens = Lexer("abc def").tokenize()
        assert tokens[0].loc.col == 1
        assert tokens[1].loc.col == 5

    def test_unexpected_character(self):
        with pytest.raises(LexError, match="Unexpected character"):
            Lexer("@").tokenize()


class TestComplexInput:
    def test_component_snippet(self):
        src = """component Resistor {
    pins {
        1: Passive as A
    }
    attributes {
        resistance: Resistance = 10kohm
    }
}"""
        tokens = Lexer(src).tokenize()
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert TokenType.KW_COMPONENT in types
        assert TokenType.KW_PINS in types
        assert TokenType.KW_ATTRIBUTES in types
        assert TokenType.UNIT_LITERAL in types
