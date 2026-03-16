"""Tests for the DECL parser."""

import pytest

from decl.lexer import Lexer
from decl.parser import Parser
from decl.ast_nodes import (
    AttrAssign,
    AttrDecl,
    CommonRule,
    ComponentDef,
    ConnectStmt,
    ExternalFeature,
    ImportDecl,
    InstanceDecl,
    InternalFeature,
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
    SchematicDef,
    VariantDef,
    WireBinding,
    WireStmt,
    WiringRule,
)
from decl.errors import ParseError
from decl.units import UnitValue


def _parse(source: str) -> Program:
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


class TestImport:
    def test_basic_import(self):
        prog = _parse('import "protocols/spi.decl"')
        assert len(prog.declarations) == 1
        decl = prog.declarations[0]
        assert isinstance(decl, ImportDecl)
        assert decl.path == "protocols/spi.decl"


class TestProtocol:
    SPI_SRC = """
protocol SPI {
    lines {
        MOSI
        MISO
        CLK
        SS
    }

    role master {
        MOSI: Output
        MISO: Input
        CLK: Output
        SS: Output
    }

    role slave {
        MOSI: Input
        MISO: Output
        CLK: Input
        SS: Input
    }

    rules {
        master.MOSI -- slave.MOSI
        slave.MISO -- master.MISO
        master.CLK -- slave.CLK
        master.SS -- slave.SS
    }
}
"""

    def test_parse_protocol(self):
        prog = _parse(self.SPI_SRC)
        assert len(prog.declarations) == 1
        proto = prog.declarations[0]
        assert isinstance(proto, ProtocolDef)
        assert proto.name == "SPI"
        assert proto.lines == ["MOSI", "MISO", "CLK", "SS"]
        assert len(proto.roles) == 2
        assert proto.roles[0].name == "master"
        assert proto.roles[1].name == "slave"
        assert len(proto.rules) == 4

    def test_role_line_directions(self):
        prog = _parse(self.SPI_SRC)
        proto = prog.declarations[0]
        master = proto.roles[0]
        assert master.line_dirs[0].line_name == "MOSI"
        assert master.line_dirs[0].direction == PinDirection.OUTPUT
        assert master.line_dirs[1].line_name == "MISO"
        assert master.line_dirs[1].direction == PinDirection.INPUT

    def test_wiring_rules(self):
        prog = _parse(self.SPI_SRC)
        proto = prog.declarations[0]
        rule = proto.rules[0]
        assert isinstance(rule, WiringRule)
        assert rule.left_role == "master"
        assert rule.left_line == "MOSI"
        assert rule.right_role == "slave"
        assert rule.right_line == "MOSI"

    def test_common_rule(self):
        src = """
protocol Power {
    lines { GND VCC }
    role source { GND: Passive VCC: PowerOutput }
    rules { common GND }
}
"""
        prog = _parse(src)
        proto = prog.declarations[0]
        assert len(proto.rules) == 1
        rule = proto.rules[0]
        assert isinstance(rule, CommonRule)
        assert rule.line_name == "GND"


class TestComponent:
    RESISTOR_SRC = """
component Resistor {
    pins {
        1: Passive as A
        2: Passive as B
    }
    attributes {
        resistance: Resistance
        tolerance: Percentage = 5%
        power_rating: Power = 0.25W
    }
}
"""

    def test_simple_component(self):
        prog = _parse(self.RESISTOR_SRC)
        comp = prog.declarations[0]
        assert isinstance(comp, ComponentDef)
        assert comp.name == "Resistor"
        assert len(comp.pins) == 2
        assert comp.pins[0].number == 1
        assert comp.pins[0].direction == PinDirection.PASSIVE
        assert comp.pins[0].name == "A"

    def test_attributes(self):
        prog = _parse(self.RESISTOR_SRC)
        comp = prog.declarations[0]
        assert len(comp.attributes) == 3
        assert comp.attributes[0].name == "resistance"
        assert comp.attributes[0].type_expr.name == "Resistance"
        assert comp.attributes[0].default is None
        assert comp.attributes[1].name == "tolerance"
        assert isinstance(comp.attributes[1].default, UnitValue)
        assert comp.attributes[1].default.suffix == "%"

    def test_parameterized_type(self):
        src = """
component MCU {
    pins { 1: PowerInput as VCC }
    attributes {
        voltage_range: VoltageRange(1.8V, 5.5V)
    }
}
"""
        prog = _parse(src)
        comp = prog.declarations[0]
        attr = comp.attributes[0]
        assert attr.type_expr.name == "VoltageRange"
        assert len(attr.type_expr.args) == 2

    def test_internal_feature(self):
        src = """
component MCU {
    pins { 1: PowerInput as VCC }
    features {
        internal clock {
            frequency: 8MHz
        }
    }
}
"""
        prog = _parse(src)
        comp = prog.declarations[0]
        feat = comp.features[0]
        assert isinstance(feat, InternalFeature)
        assert feat.name == "clock"
        assert len(feat.properties) == 1
        assert feat.properties[0].name == "frequency"

    def test_external_feature(self):
        src = """
protocol SPI {
    lines { MOSI MISO CLK SS }
    role master { MOSI: Output MISO: Input CLK: Output SS: Output }
}

component MCU {
    pins {
        1: Bidirectional as MOSI_PIN
        2: Bidirectional as MISO_PIN
        3: Bidirectional as CLK_PIN
        4: Bidirectional as SS_PIN
    }
    features {
        external SPI using protocol SPI role master {
            MOSI -> pin 1
            MISO -> pin 2
            CLK -> pin 3
            SS -> pin 4
        }
    }
}
"""
        prog = _parse(src)
        comp = prog.declarations[1]
        feat = comp.features[0]
        assert isinstance(feat, ExternalFeature)
        assert feat.name == "SPI"
        assert feat.protocol_name == "SPI"
        assert feat.role_name == "master"
        assert len(feat.pin_mappings) == 4
        assert feat.pin_mappings[0].line_name == "MOSI"
        assert feat.pin_mappings[0].pin_number == 1


class TestSchematic:
    FULL_SRC = """
component Resistor {
    pins {
        1: Passive as A
        2: Passive as B
    }
    attributes {
        resistance: Resistance
    }
}

component LED {
    pins {
        1: Passive as anode
        2: Passive as cathode
    }
}

schematic Simple {
    instance r1: Resistor { resistance = 220ohm }
    instance led1: LED

    net VCC
    net GND

    connect r1.A -- net VCC
    connect r1.B -- led1.anode
    connect led1.cathode -- net GND
}
"""

    def test_instances(self):
        prog = _parse(self.FULL_SRC)
        schem = prog.declarations[2]
        assert isinstance(schem, SchematicDef)
        assert schem.name == "Simple"
        assert len(schem.instances) == 2
        assert schem.instances[0].name == "r1"
        assert schem.instances[0].component_name == "Resistor"
        assert len(schem.instances[0].overrides) == 1

    def test_nets(self):
        prog = _parse(self.FULL_SRC)
        schem = prog.declarations[2]
        assert len(schem.nets) == 2
        assert schem.nets[0].name == "VCC"
        assert schem.nets[1].name == "GND"

    def test_connects(self):
        prog = _parse(self.FULL_SRC)
        schem = prog.declarations[2]
        assert len(schem.connects) == 3

        c0 = schem.connects[0]
        assert isinstance(c0.left, PinRef)
        assert c0.left.instance_name == "r1"
        assert c0.left.pin_name == "A"
        assert isinstance(c0.right, NetRef)
        assert c0.right.net_name == "VCC"

    def test_wire_statement(self):
        src = """
protocol SPI {
    lines { MOSI MISO CLK SS }
    role master { MOSI: Output MISO: Input CLK: Output SS: Output }
    role slave { MOSI: Input MISO: Output CLK: Input SS: Input }
    rules {
        master.MOSI -- slave.MOSI
        slave.MISO -- master.MISO
        master.CLK -- slave.CLK
        master.SS -- slave.SS
    }
}

component MCU {
    pins {
        1: Bidirectional as M 2: Bidirectional as I
        3: Bidirectional as C 4: Bidirectional as S
    }
    features {
        external SPI using protocol SPI role master {
            MOSI -> pin 1 MISO -> pin 2 CLK -> pin 3 SS -> pin 4
        }
    }
}

component Flash {
    pins {
        1: Bidirectional as M 2: Bidirectional as I
        3: Bidirectional as C 4: Bidirectional as S
    }
    features {
        external SPI using protocol SPI role slave {
            MOSI -> pin 1 MISO -> pin 2 CLK -> pin 3 SS -> pin 4
        }
    }
}

schematic Board {
    instance mcu: MCU
    instance flash: Flash
    wire SPI {
        master: mcu
        slave: flash
    }
}
"""
        prog = _parse(src)
        schem = prog.declarations[3]
        assert isinstance(schem, SchematicDef)
        assert len(schem.wires) == 1
        wire = schem.wires[0]
        assert wire.protocol_name == "SPI"
        assert len(wire.bindings) == 2
        assert wire.bindings[0].role_name == "master"
        assert wire.bindings[0].instance_name == "mcu"


class TestNamedOnlyPins:
    def test_named_only_pin_decl(self):
        src = """
component MCU {
    pins {
        PA1: Bidirectional
        VDD: PowerInput
        ADC_IN: Analog
    }
}
"""
        prog = _parse(src)
        comp = prog.declarations[0]
        assert isinstance(comp, ComponentDef)
        assert len(comp.pins) == 3
        assert comp.pins[0].number is None
        assert comp.pins[0].name == "PA1"
        assert comp.pins[0].direction == PinDirection.BIDIRECTIONAL
        assert comp.pins[1].name == "VDD"
        assert comp.pins[1].direction == PinDirection.POWER_INPUT
        assert comp.pins[2].direction == PinDirection.ANALOG

    def test_pin_mapping_by_name(self):
        src = """
protocol P {
    lines { A }
    role r { A: Output }
}
component MCU {
    pins { PA1: Bidirectional }
    features {
        external F using protocol P role r {
            A -> pin PA1
        }
    }
}
"""
        prog = _parse(src)
        comp = prog.declarations[1]
        feat = comp.features[0]
        assert isinstance(feat, ExternalFeature)
        assert feat.pin_mappings[0].pin_name == "PA1"
        assert feat.pin_mappings[0].pin_number is None

    def test_pin_mapping_pin_number_first(self):
        """Pin mapping form NUMBER -> IDENT (e.g. 3 -> DI) for numbered pins."""
        src = """
protocol SPI {
    lines { DI DO CLK CS }
    role slave { DI: Input DO: Output CLK: Input CS: Input }
}
component W25Q128JV {
    pins {
        1: PowerInput as VCC
        2: Input as CS
        3: Input as DI
        4: Output as DO
        7: Input as CLK
    }
    features {
        external SPI using protocol SPI role slave {
            3 -> DI
            4 -> DO
            7 -> CLK
            2 -> CS
        }
    }
}
"""
        prog = _parse(src)
        comp = prog.declarations[1]
        feat = comp.features[0]
        assert isinstance(feat, ExternalFeature)
        assert len(feat.pin_mappings) == 4
        by_line = {pm.line_name: pm for pm in feat.pin_mappings}
        assert by_line["DI"].pin_number == 3
        assert by_line["DO"].pin_number == 4
        assert by_line["CLK"].pin_number == 7
        assert by_line["CS"].pin_number == 2
        assert by_line["DI"].pin_name is None


class TestVariant:
    VARIANT_SRC = """
component Base {
    pins {
        PA: Bidirectional
        PB: Bidirectional
        VDD: PowerInput
    }
}

variant BaseV1 of Base {
    package: "SOIC8"
    pinout {
        PA -> 1
        PB -> 2
        VDD -> 3
    }
}
"""

    def test_parse_variant(self):
        prog = _parse(self.VARIANT_SRC)
        assert len(prog.declarations) == 2
        var = prog.declarations[1]
        assert isinstance(var, VariantDef)
        assert var.name == "BaseV1"
        assert var.base_component == "Base"
        assert len(var.properties) == 1
        assert var.properties[0].name == "package"
        assert var.properties[0].value == "SOIC8"

    def test_pinout_mappings(self):
        prog = _parse(self.VARIANT_SRC)
        var = prog.declarations[1]
        assert len(var.pinout) == 3
        assert var.pinout[0].pin_name == "PA"
        assert var.pinout[0].physical_number == 1
        assert var.pinout[2].pin_name == "VDD"
        assert var.pinout[2].physical_number == 3

    def test_variant_in_schematic(self):
        src = self.VARIANT_SRC + """
schematic S {
    instance chip: BaseV1
    net N
    connect chip.PA -- net N
    connect chip.PB -- net N
    connect chip.VDD -- net N
}
"""
        prog = _parse(src)
        schem = prog.declarations[2]
        assert isinstance(schem, SchematicDef)
        assert schem.instances[0].component_name == "BaseV1"


class TestNewPinTypes:
    def test_analog_pin(self):
        src = "component X { pins { 1: Analog as ADC_IN } }"
        prog = _parse(src)
        assert prog.declarations[0].pins[0].direction == PinDirection.ANALOG

    def test_open_drain_pin(self):
        src = "component X { pins { 1: OpenDrain as SDA } }"
        prog = _parse(src)
        assert prog.declarations[0].pins[0].direction == PinDirection.OPEN_DRAIN


class TestParseErrors:
    def test_unexpected_top_level(self):
        with pytest.raises(ParseError, match="Expected top-level"):
            _parse("foobar")

    def test_missing_brace(self):
        with pytest.raises(ParseError, match="got EOF"):
            _parse("component X { pins { 1: Passive as A }")

    def test_bad_pin_type(self):
        with pytest.raises(ParseError, match="Expected pin type"):
            _parse("component X { pins { 1: NotAPinType as A } }")
