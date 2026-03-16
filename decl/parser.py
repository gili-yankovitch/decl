"""Recursive descent parser for the DECL language."""

from __future__ import annotations

from typing import Optional, Union

from .ast_nodes import (
    AttrAssign,
    AttrDecl,
    CommonRule,
    ComponentDef,
    ConnectEndpoint,
    ConnectStmt,
    ExternalFeature,
    FeatureDef,
    ImportDecl,
    InstanceDecl,
    InternalFeature,
    LineDirDecl,
    NetDecl,
    NetRef,
    PinDef,
    PinDirection,
    PinMapping,
    PinoutMapping,
    PinRef,
    Program,
    ProtocolDef,
    RoleDef,
    RuleStmt,
    SchematicDef,
    TopLevelDecl,
    TypeExpr,
    ValueExpr,
    VariantDef,
    WireBinding,
    WireStmt,
    WiringRule,
)
from .errors import ParseError, SourceLocation
from .tokens import PIN_TYPE_TOKENS, Token, TokenType
from .units import UnitValue


_TOKEN_TO_PIN_DIR: dict[TokenType, PinDirection] = {
    TokenType.PIN_INPUT: PinDirection.INPUT,
    TokenType.PIN_OUTPUT: PinDirection.OUTPUT,
    TokenType.PIN_BIDIRECTIONAL: PinDirection.BIDIRECTIONAL,
    TokenType.PIN_TRISTATE: PinDirection.TRI_STATE,
    TokenType.PIN_PASSIVE: PinDirection.PASSIVE,
    TokenType.PIN_FREE: PinDirection.FREE,
    TokenType.PIN_POWER_INPUT: PinDirection.POWER_INPUT,
    TokenType.PIN_POWER_OUTPUT: PinDirection.POWER_OUTPUT,
    TokenType.PIN_UNCONNECTED: PinDirection.UNCONNECTED,
    TokenType.PIN_ANALOG: PinDirection.ANALOG,
    TokenType.PIN_OPEN_DRAIN: PinDirection.OPEN_DRAIN,
}


class Parser:
    def __init__(self, tokens: list[Token], filename: str = "<stdin>") -> None:
        self._tokens = tokens
        self._filename = filename
        self._pos = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cur(self) -> Token:
        return self._tokens[self._pos]

    def _loc(self) -> SourceLocation:
        return self._cur().loc

    def _at(self, *types: TokenType) -> bool:
        return self._cur().type in types

    def _eat(self, tt: TokenType) -> Token:
        tok = self._cur()
        if tok.type != tt:
            raise ParseError(
                f"Expected {tt.name}, got {tok.type.name} ({tok.value!r})", tok.loc
            )
        self._pos += 1
        return tok

    def _expect_ident(self) -> str:
        tok = self._eat(TokenType.IDENT)
        return tok.value

    def _try_eat(self, tt: TokenType) -> Optional[Token]:
        if self._cur().type == tt:
            tok = self._cur()
            self._pos += 1
            return tok
        return None

    # ------------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------------

    def parse(self) -> Program:
        decls: list[TopLevelDecl] = []
        while not self._at(TokenType.EOF):
            decls.append(self._parse_top_level())
        return Program(declarations=decls)

    def _parse_top_level(self) -> TopLevelDecl:
        tok = self._cur()
        if tok.type == TokenType.KW_IMPORT:
            return self._parse_import()
        if tok.type == TokenType.KW_PROTOCOL:
            return self._parse_protocol()
        if tok.type == TokenType.KW_COMPONENT:
            return self._parse_component()
        if tok.type == TokenType.KW_SCHEMATIC:
            return self._parse_schematic()
        if tok.type == TokenType.KW_VARIANT:
            return self._parse_variant()
        raise ParseError(
            f"Expected top-level declaration (import/protocol/component/schematic/variant), "
            f"got {tok.type.name}",
            tok.loc,
        )

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def _parse_import(self) -> ImportDecl:
        loc = self._loc()
        self._eat(TokenType.KW_IMPORT)
        path_tok = self._eat(TokenType.STRING)
        return ImportDecl(path=path_tok.value, loc=loc)

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def _parse_protocol(self) -> ProtocolDef:
        loc = self._loc()
        self._eat(TokenType.KW_PROTOCOL)
        name = self._expect_ident()
        self._eat(TokenType.LBRACE)

        lines: list[str] = []
        roles: list[RoleDef] = []
        rules: list[RuleStmt] = []

        while not self._at(TokenType.RBRACE):
            if self._at(TokenType.KW_LINES):
                lines = self._parse_lines_block()
            elif self._at(TokenType.KW_ROLE):
                roles.append(self._parse_role_block())
            elif self._at(TokenType.KW_RULES):
                rules = self._parse_rules_block()
            else:
                raise ParseError(
                    f"Expected 'lines', 'role', or 'rules' in protocol body, "
                    f"got {self._cur().type.name}",
                    self._loc(),
                )

        self._eat(TokenType.RBRACE)
        return ProtocolDef(name=name, lines=lines, roles=roles, rules=rules, loc=loc)

    def _parse_lines_block(self) -> list[str]:
        self._eat(TokenType.KW_LINES)
        self._eat(TokenType.LBRACE)
        names: list[str] = []
        while not self._at(TokenType.RBRACE):
            names.append(self._expect_ident())
        self._eat(TokenType.RBRACE)
        return names

    def _parse_role_block(self) -> RoleDef:
        loc = self._loc()
        self._eat(TokenType.KW_ROLE)
        name = self._expect_ident()
        self._eat(TokenType.LBRACE)
        dirs: list[LineDirDecl] = []
        while not self._at(TokenType.RBRACE):
            dirs.append(self._parse_line_dir_decl())
        self._eat(TokenType.RBRACE)
        return RoleDef(name=name, line_dirs=dirs, loc=loc)

    def _parse_line_dir_decl(self) -> LineDirDecl:
        loc = self._loc()
        line_name = self._expect_ident()
        self._eat(TokenType.COLON)
        direction = self._parse_pin_type()
        return LineDirDecl(line_name=line_name, direction=direction, loc=loc)

    def _parse_pin_type(self) -> PinDirection:
        tok = self._cur()
        if tok.type in _TOKEN_TO_PIN_DIR:
            self._pos += 1
            return _TOKEN_TO_PIN_DIR[tok.type]
        raise ParseError(f"Expected pin type, got {tok.type.name}", tok.loc)

    def _parse_rules_block(self) -> list[RuleStmt]:
        self._eat(TokenType.KW_RULES)
        self._eat(TokenType.LBRACE)
        rules: list[RuleStmt] = []
        while not self._at(TokenType.RBRACE):
            rules.append(self._parse_rule_stmt())
        self._eat(TokenType.RBRACE)
        return rules

    def _parse_rule_stmt(self) -> RuleStmt:
        if self._at(TokenType.KW_COMMON):
            return self._parse_common_rule()
        return self._parse_wiring_rule()

    def _parse_common_rule(self) -> CommonRule:
        loc = self._loc()
        self._eat(TokenType.KW_COMMON)
        name = self._expect_ident()
        return CommonRule(line_name=name, loc=loc)

    def _parse_wiring_rule(self) -> WiringRule:
        loc = self._loc()
        left_role = self._expect_ident()
        self._eat(TokenType.DOT)
        left_line = self._expect_ident()
        self._eat(TokenType.DASH_DASH)
        right_role = self._expect_ident()
        self._eat(TokenType.DOT)
        right_line = self._expect_ident()
        return WiringRule(
            left_role=left_role,
            left_line=left_line,
            right_role=right_role,
            right_line=right_line,
            loc=loc,
        )

    # ------------------------------------------------------------------
    # Component
    # ------------------------------------------------------------------

    def _parse_component(self) -> ComponentDef:
        loc = self._loc()
        self._eat(TokenType.KW_COMPONENT)
        name = self._expect_ident()
        self._eat(TokenType.LBRACE)

        pins: list[PinDef] = []
        features: list[FeatureDef] = []
        attributes: list[AttrDecl] = []

        while not self._at(TokenType.RBRACE):
            if self._at(TokenType.KW_PINS):
                pins = self._parse_pins_block()
            elif self._at(TokenType.KW_FEATURES):
                features = self._parse_features_block()
            elif self._at(TokenType.KW_ATTRIBUTES):
                attributes = self._parse_attributes_block()
            else:
                raise ParseError(
                    f"Expected 'pins', 'features', or 'attributes' in component body, "
                    f"got {self._cur().type.name}",
                    self._loc(),
                )

        self._eat(TokenType.RBRACE)
        return ComponentDef(
            name=name, pins=pins, features=features, attributes=attributes, loc=loc
        )

    def _parse_pins_block(self) -> list[PinDef]:
        self._eat(TokenType.KW_PINS)
        self._eat(TokenType.LBRACE)
        pins: list[PinDef] = []
        while not self._at(TokenType.RBRACE):
            pins.append(self._parse_pin_decl())
        self._eat(TokenType.RBRACE)
        return pins

    def _parse_pin_decl(self) -> PinDef:
        loc = self._loc()
        if self._at(TokenType.NUMBER):
            num_tok = self._eat(TokenType.NUMBER)
            self._eat(TokenType.COLON)
            direction = self._parse_pin_type()
            self._eat(TokenType.KW_AS)
            name = self._expect_ident()
            return PinDef(number=int(num_tok.value), direction=direction, name=name, loc=loc)
        # Named form: NAME: PinType [ as ALIAS ]
        ident = self._expect_ident()
        self._eat(TokenType.COLON)
        direction = self._parse_pin_type()
        alias_tok = self._try_eat(TokenType.KW_AS)
        if alias_tok is not None:
            name = self._expect_ident()
        else:
            name = ident
        return PinDef(number=None, direction=direction, name=name, loc=loc)

    def _parse_features_block(self) -> list[FeatureDef]:
        self._eat(TokenType.KW_FEATURES)
        self._eat(TokenType.LBRACE)
        features: list[FeatureDef] = []
        while not self._at(TokenType.RBRACE):
            features.append(self._parse_feature_decl())
        self._eat(TokenType.RBRACE)
        return features

    def _parse_feature_decl(self) -> FeatureDef:
        if self._at(TokenType.KW_INTERNAL):
            return self._parse_internal_feature()
        if self._at(TokenType.KW_EXTERNAL):
            return self._parse_external_feature()
        raise ParseError(
            f"Expected 'internal' or 'external' feature, got {self._cur().type.name}",
            self._loc(),
        )

    def _parse_internal_feature(self) -> InternalFeature:
        loc = self._loc()
        self._eat(TokenType.KW_INTERNAL)
        name = self._expect_ident()
        self._eat(TokenType.LBRACE)
        props: list[AttrAssign] = []
        while not self._at(TokenType.RBRACE):
            props.append(self._parse_attr_assign())
        self._eat(TokenType.RBRACE)
        return InternalFeature(name=name, properties=props, loc=loc)

    def _parse_external_feature(self) -> ExternalFeature:
        loc = self._loc()
        self._eat(TokenType.KW_EXTERNAL)
        name = self._expect_ident()
        self._eat(TokenType.KW_USING)
        # 'protocol' keyword is optional here for readability but expected by grammar
        self._eat(TokenType.KW_PROTOCOL)
        protocol_name = self._expect_ident()
        self._eat(TokenType.KW_ROLE)
        role_name = self._expect_ident()
        self._eat(TokenType.LBRACE)
        mappings: list[PinMapping] = []
        while not self._at(TokenType.RBRACE):
            mappings.append(self._parse_pin_mapping())
        self._eat(TokenType.RBRACE)
        return ExternalFeature(
            name=name,
            protocol_name=protocol_name,
            role_name=role_name,
            pin_mappings=mappings,
            loc=loc,
        )

    def _parse_pin_mapping(self) -> PinMapping:
        loc = self._loc()
        line_name = self._expect_ident()
        self._eat(TokenType.ARROW)
        self._eat(TokenType.KW_PIN)
        if self._at(TokenType.NUMBER):
            num_tok = self._eat(TokenType.NUMBER)
            return PinMapping(line_name=line_name, pin_number=int(num_tok.value), loc=loc)
        name = self._expect_ident()
        return PinMapping(line_name=line_name, pin_name=name, loc=loc)

    def _parse_attributes_block(self) -> list[AttrDecl]:
        self._eat(TokenType.KW_ATTRIBUTES)
        self._eat(TokenType.LBRACE)
        attrs: list[AttrDecl] = []
        while not self._at(TokenType.RBRACE):
            attrs.append(self._parse_attr_decl())
        self._eat(TokenType.RBRACE)
        return attrs

    def _parse_attr_decl(self) -> AttrDecl:
        loc = self._loc()
        name = self._expect_ident()
        self._eat(TokenType.COLON)
        type_expr = self._parse_type_expr()
        default: Optional[ValueExpr] = None
        if self._try_eat(TokenType.EQUALS):
            default = self._parse_value_expr()
        return AttrDecl(name=name, type_expr=type_expr, default=default, loc=loc)

    def _parse_type_expr(self) -> TypeExpr:
        loc = self._loc()
        name = self._expect_ident()
        args: list[ValueExpr] = []
        if self._try_eat(TokenType.LPAREN):
            args.append(self._parse_value_expr())
            while self._try_eat(TokenType.COMMA):
                args.append(self._parse_value_expr())
            self._eat(TokenType.RPAREN)
        return TypeExpr(name=name, args=args, loc=loc)

    def _parse_value_expr(self) -> ValueExpr:
        tok = self._cur()
        if tok.type == TokenType.UNIT_LITERAL:
            self._pos += 1
            return tok.value  # UnitValue
        if tok.type == TokenType.NUMBER:
            self._pos += 1
            return tok.value  # int or float
        if tok.type == TokenType.STRING:
            self._pos += 1
            return tok.value  # str
        if tok.type == TokenType.IDENT:
            self._pos += 1
            return tok.value  # identifier as string
        raise ParseError(
            f"Expected value (number, unit, string, or identifier), got {tok.type.name}",
            tok.loc,
        )

    def _parse_attr_assign(self) -> AttrAssign:
        loc = self._loc()
        name = self._expect_ident()
        self._eat(TokenType.COLON)
        value = self._parse_value_expr()
        return AttrAssign(name=name, value=value, loc=loc)

    # ------------------------------------------------------------------
    # Schematic
    # ------------------------------------------------------------------

    def _parse_schematic(self) -> SchematicDef:
        loc = self._loc()
        self._eat(TokenType.KW_SCHEMATIC)
        name = self._expect_ident()
        self._eat(TokenType.LBRACE)

        instances: list[InstanceDecl] = []
        nets: list[NetDecl] = []
        connects: list[ConnectStmt] = []
        wires: list[WireStmt] = []

        while not self._at(TokenType.RBRACE):
            if self._at(TokenType.KW_INSTANCE):
                instances.append(self._parse_instance())
            elif self._at(TokenType.KW_NET):
                nets.append(self._parse_net())
            elif self._at(TokenType.KW_CONNECT):
                connects.append(self._parse_connect())
            elif self._at(TokenType.KW_WIRE):
                wires.append(self._parse_wire())
            else:
                raise ParseError(
                    f"Expected 'instance', 'net', 'connect', or 'wire' in schematic body, "
                    f"got {self._cur().type.name}",
                    self._loc(),
                )

        self._eat(TokenType.RBRACE)
        return SchematicDef(
            name=name,
            instances=instances,
            nets=nets,
            connects=connects,
            wires=wires,
            loc=loc,
        )

    def _parse_instance(self) -> InstanceDecl:
        loc = self._loc()
        self._eat(TokenType.KW_INSTANCE)
        inst_name = self._expect_ident()
        self._eat(TokenType.COLON)
        comp_name = self._expect_ident()

        overrides: list[AttrAssign] = []
        if self._try_eat(TokenType.LBRACE):
            while not self._at(TokenType.RBRACE):
                overrides.append(self._parse_instance_attr_assign())
            self._eat(TokenType.RBRACE)

        return InstanceDecl(
            name=inst_name, component_name=comp_name, overrides=overrides, loc=loc
        )

    def _parse_instance_attr_assign(self) -> AttrAssign:
        """Attribute assignment in instance block uses ``=`` instead of ``:``."""
        loc = self._loc()
        name = self._expect_ident()
        self._eat(TokenType.EQUALS)
        value = self._parse_value_expr()
        return AttrAssign(name=name, value=value, loc=loc)

    def _parse_net(self) -> NetDecl:
        loc = self._loc()
        self._eat(TokenType.KW_NET)
        name = self._expect_ident()
        return NetDecl(name=name, loc=loc)

    def _parse_connect(self) -> ConnectStmt:
        loc = self._loc()
        self._eat(TokenType.KW_CONNECT)
        left = self._parse_connect_endpoint()
        self._eat(TokenType.DASH_DASH)
        right = self._parse_connect_endpoint()
        return ConnectStmt(left=left, right=right, loc=loc)

    def _parse_connect_endpoint(self) -> ConnectEndpoint:
        loc = self._loc()
        if self._at(TokenType.KW_NET):
            self._eat(TokenType.KW_NET)
            name = self._expect_ident()
            return NetRef(net_name=name, loc=loc)
        # instance.pin
        inst_name = self._expect_ident()
        self._eat(TokenType.DOT)
        pin_name = self._expect_ident()
        return PinRef(instance_name=inst_name, pin_name=pin_name, loc=loc)

    def _parse_wire(self) -> WireStmt:
        loc = self._loc()
        self._eat(TokenType.KW_WIRE)
        protocol_name = self._expect_ident()
        self._eat(TokenType.LBRACE)
        bindings: list[WireBinding] = []
        while not self._at(TokenType.RBRACE):
            bindings.append(self._parse_wire_binding())
        self._eat(TokenType.RBRACE)
        return WireStmt(protocol_name=protocol_name, bindings=bindings, loc=loc)

    def _parse_wire_binding(self) -> WireBinding:
        loc = self._loc()
        role_name = self._expect_ident()
        self._eat(TokenType.COLON)
        inst_name = self._expect_ident()
        return WireBinding(role_name=role_name, instance_name=inst_name, loc=loc)

    # ------------------------------------------------------------------
    # Variant
    # ------------------------------------------------------------------

    def _parse_variant(self) -> VariantDef:
        loc = self._loc()
        self._eat(TokenType.KW_VARIANT)
        name = self._expect_ident()
        self._eat(TokenType.KW_OF)
        base = self._expect_ident()
        self._eat(TokenType.LBRACE)

        properties: list[AttrAssign] = []
        pinout: list[PinoutMapping] = []

        while not self._at(TokenType.RBRACE):
            if self._at(TokenType.KW_PINOUT):
                pinout = self._parse_pinout_block()
            elif self._at(TokenType.IDENT):
                properties.append(self._parse_attr_assign())
            else:
                raise ParseError(
                    f"Expected 'pinout' or property in variant body, "
                    f"got {self._cur().type.name}",
                    self._loc(),
                )

        self._eat(TokenType.RBRACE)
        return VariantDef(
            name=name, base_component=base, properties=properties,
            pinout=pinout, loc=loc,
        )

    def _parse_pinout_block(self) -> list[PinoutMapping]:
        self._eat(TokenType.KW_PINOUT)
        self._eat(TokenType.LBRACE)
        mappings: list[PinoutMapping] = []
        while not self._at(TokenType.RBRACE):
            mappings.append(self._parse_pinout_mapping())
        self._eat(TokenType.RBRACE)
        return mappings

    def _parse_pinout_mapping(self) -> PinoutMapping:
        loc = self._loc()
        pin_name = self._expect_ident()
        self._eat(TokenType.ARROW)
        num_tok = self._eat(TokenType.NUMBER)
        return PinoutMapping(pin_name=pin_name, physical_number=int(num_tok.value), loc=loc)
