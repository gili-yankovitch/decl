"""Tests for the DECL semantic analyzer."""

import pytest

from decl.lexer import Lexer
from decl.parser import Parser
from decl.analyzer import Analyzer
from decl.errors import AnalysisError


def _analyze(source: str) -> Analyzer:
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzer = Analyzer()
    analyzer.analyze(program)
    return analyzer


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------

class TestValidPrograms:
    def test_minimal_component(self):
        _analyze("""
component R {
    pins { 1: Passive as A  2: Passive as B }
}
""")

    def test_component_with_attributes(self):
        _analyze("""
component R {
    pins { 1: Passive as A  2: Passive as B }
    attributes {
        resistance: Resistance = 10kohm
    }
}
""")

    def test_simple_schematic(self):
        a = _analyze("""
component R {
    pins { 1: Passive as A  2: Passive as B }
    attributes { resistance: Resistance }
}

schematic S {
    instance r1: R { resistance = 10kohm }
    instance r2: R { resistance = 4.7kohm }
    net N
    connect r1.B -- r2.A
    connect r1.A -- net N
    connect r2.B -- net N
}
""")
        assert len(a.warnings) == 0

    def test_full_protocol_wiring(self):
        a = _analyze("""
protocol SPI {
    lines { MOSI MISO CLK SS }
    role master { MOSI: Output MISO: Input CLK: Output SS: Output }
    role slave  { MOSI: Input  MISO: Output CLK: Input  SS: Input  }
    rules {
        master.MOSI -- slave.MOSI
        slave.MISO  -- master.MISO
        master.CLK  -- slave.CLK
        master.SS   -- slave.SS
    }
}

component MCU {
    pins {
        1: Bidirectional as P1
        2: Bidirectional as P2
        3: Bidirectional as P3
        4: Bidirectional as P4
    }
    features {
        external SPI using protocol SPI role master {
            MOSI -> pin 1
            MISO -> pin 2
            CLK  -> pin 3
            SS   -> pin 4
        }
    }
}

component Flash {
    pins {
        1: Bidirectional as P1
        2: Bidirectional as P2
        3: Bidirectional as P3
        4: Bidirectional as P4
    }
    features {
        external SPI using protocol SPI role slave {
            MOSI -> pin 1
            MISO -> pin 2
            CLK  -> pin 3
            SS   -> pin 4
        }
    }
}

schematic Board {
    instance mcu:   MCU
    instance flash: Flash
    wire SPI {
        master: mcu
        slave:  flash
    }
}
""")
        # All pins connected via wire, no warnings except none
        assert all(w.code != "W003" for w in a.warnings)


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------

class TestVariants:
    def test_variant_materializes_component(self):
        a = _analyze("""
component Base {
    pins {
        PA: Bidirectional
        PB: Bidirectional
        VDD: PowerInput
    }
}
variant Chip of Base {
    pinout {
        PA -> 1
        PB -> 2
        VDD -> 3
    }
}
schematic S {
    instance c: Chip
    net N
    connect c.PA -- c.PB
    connect c.VDD -- net N
}
""")
        assert "Chip" in a.components

    def test_variant_drops_unavailable_features(self):
        """If a variant's pinout excludes pins needed by a feature, that feature is dropped."""
        a = _analyze("""
protocol P {
    lines { A }
    role r { A: Output }
}
component Base {
    pins {
        PA: Bidirectional
        PB: Bidirectional
    }
    features {
        external F using protocol P role r {
            A -> pin PA
        }
    }
}
variant Small of Base {
    pinout {
        PB -> 1
    }
}
""")
        small = a.components["Small"]
        assert len(small.features) == 0

    def test_variant_keeps_available_features(self):
        a = _analyze("""
protocol P {
    lines { X }
    role r { X: Output }
}
component Base {
    pins {
        PA: Bidirectional
        PB: Bidirectional
    }
    features {
        external F using protocol P role r {
            X -> pin PA
        }
    }
}
variant Full of Base {
    pinout {
        PA -> 1
        PB -> 2
    }
}
""")
        full = a.components["Full"]
        assert len(full.features) == 1

    def test_variant_undefined_base(self):
        with pytest.raises(AnalysisError, match="E002.*not defined"):
            _analyze("""
variant V of Missing {
    pinout { X -> 1 }
}
""")

    def test_variant_bad_pin_name(self):
        with pytest.raises(AnalysisError, match="E002.*not defined in base"):
            _analyze("""
component Base { pins { PA: Bidirectional } }
variant V of Base {
    pinout { NOPE -> 1 }
}
""")

    def test_variant_duplicate_physical_number(self):
        with pytest.raises(AnalysisError, match="E008.*Duplicate physical"):
            _analyze("""
component Base { pins { PA: Bidirectional  PB: Bidirectional } }
variant V of Base {
    pinout { PA -> 1  PB -> 1 }
}
""")


# ---------------------------------------------------------------------------
# New pin types: Analog / OpenDrain
# ---------------------------------------------------------------------------

class TestAnalogOpenDrain:
    def test_analog_to_passive_ok(self):
        _analyze("""
component Sensor { pins { 1: Analog as OUT } }
component R { pins { 1: Passive as A  2: Passive as B } }
schematic S {
    instance s: Sensor
    instance r: R
    connect s.OUT -- r.A
}
""")

    def test_analog_to_output_rejected(self):
        with pytest.raises(AnalysisError, match="E003.*incompatibility"):
            _analyze("""
component Sensor { pins { 1: Analog as OUT } }
component Driver { pins { 1: Output as OUT } }
schematic S {
    instance s: Sensor
    instance d: Driver
    connect s.OUT -- d.OUT
}
""")

    def test_open_drain_to_input_ok(self):
        _analyze("""
component OD { pins { 1: OpenDrain as SDA } }
component IC { pins { 1: Input as IN } }
schematic S {
    instance od: OD
    instance ic: IC
    connect od.SDA -- ic.IN
}
""")

    def test_open_drain_to_open_drain_ok(self):
        _analyze("""
component A { pins { 1: OpenDrain as SDA } }
component B { pins { 1: OpenDrain as SDA } }
schematic S {
    instance a: A
    instance b: B
    connect a.SDA -- b.SDA
}
""")


# ---------------------------------------------------------------------------
# Duplicate identifiers (E001)
# ---------------------------------------------------------------------------

class TestE001Duplicates:
    def test_duplicate_component(self):
        with pytest.raises(AnalysisError, match="E001.*Duplicate component"):
            _analyze("""
component X { pins { 1: Passive as A } }
component X { pins { 1: Passive as B } }
""")

    def test_duplicate_pin_name(self):
        with pytest.raises(AnalysisError, match="E001.*Duplicate pin name"):
            _analyze("""
component X { pins { 1: Passive as A  2: Passive as A } }
""")

    def test_duplicate_instance(self):
        with pytest.raises(AnalysisError, match="E001.*Duplicate instance"):
            _analyze("""
component X { pins { 1: Passive as A } }
schematic S {
    instance a: X
    instance a: X
}
""")

    def test_duplicate_net(self):
        with pytest.raises(AnalysisError, match="E001.*Duplicate net"):
            _analyze("""
component X { pins { 1: Passive as A } }
schematic S {
    instance x: X
    net N
    net N
}
""")


# ---------------------------------------------------------------------------
# Undefined references (E002)
# ---------------------------------------------------------------------------

class TestE002Undefined:
    def test_undefined_component_in_instance(self):
        with pytest.raises(AnalysisError, match="E002.*not defined"):
            _analyze("""
schematic S {
    instance x: DoesNotExist
}
""")

    def test_undefined_pin(self):
        with pytest.raises(AnalysisError, match="E002.*Pin.*not defined"):
            _analyze("""
component X { pins { 1: Passive as A } }
schematic S {
    instance x: X
    net N
    connect x.B -- net N
}
""")

    def test_undefined_net(self):
        with pytest.raises(AnalysisError, match="E002.*Net.*not defined"):
            _analyze("""
component X { pins { 1: Passive as A } }
schematic S {
    instance x: X
    connect x.A -- net MISSING
}
""")

    def test_undefined_protocol_in_feature(self):
        with pytest.raises(AnalysisError, match="E002.*Protocol.*not defined"):
            _analyze("""
component X {
    pins { 1: Bidirectional as A }
    features {
        external F using protocol Ghost role r { A -> pin 1 }
    }
}
""")


# ---------------------------------------------------------------------------
# Pin direction compatibility (E003)
# ---------------------------------------------------------------------------

class TestE003Directions:
    def test_output_to_output(self):
        with pytest.raises(AnalysisError, match="E003.*incompatibility"):
            _analyze("""
component X { pins { 1: Output as OUT } }
component Y { pins { 1: Output as OUT } }
schematic S {
    instance x: X
    instance y: Y
    connect x.OUT -- y.OUT
}
""")

    def test_power_input_to_input(self):
        with pytest.raises(AnalysisError, match="E003.*incompatibility"):
            _analyze("""
component X { pins { 1: PowerInput as V } }
component Y { pins { 1: Input as I } }
schematic S {
    instance x: X
    instance y: Y
    connect x.V -- y.I
}
""")

    def test_passive_to_passive_ok(self):
        _analyze("""
component R { pins { 1: Passive as A  2: Passive as B } }
schematic S {
    instance r1: R
    instance r2: R
    connect r1.B -- r2.A
}
""")

    def test_output_to_input_ok(self):
        _analyze("""
component Src { pins { 1: Output as OUT } }
component Snk { pins { 1: Input as IN } }
schematic S {
    instance s: Src
    instance d: Snk
    connect s.OUT -- d.IN
}
""")


# ---------------------------------------------------------------------------
# Attribute type mismatch (E005)
# ---------------------------------------------------------------------------

class TestE005TypeMismatch:
    def test_wrong_unit_in_default(self):
        with pytest.raises(AnalysisError, match="E005.*type mismatch"):
            _analyze("""
component R {
    pins { 1: Passive as A }
    attributes {
        resistance: Resistance = 3.3V
    }
}
""")

    def test_wrong_unit_in_override(self):
        with pytest.raises(AnalysisError, match="E005.*type mismatch"):
            _analyze("""
component R {
    pins { 1: Passive as A }
    attributes { resistance: Resistance }
}
schematic S {
    instance r1: R { resistance = 100nF }
}
""")


# ---------------------------------------------------------------------------
# Missing pin mapping (E006)
# ---------------------------------------------------------------------------

class TestE006MissingMapping:
    def test_incomplete_pin_mapping(self):
        with pytest.raises(AnalysisError, match="E006.*missing pin mappings"):
            _analyze("""
protocol P {
    lines { A B }
    role r { A: Output B: Input }
}
component X {
    pins { 1: Bidirectional as P1 }
    features {
        external F using protocol P role r {
            A -> pin 1
        }
    }
}
""")


# ---------------------------------------------------------------------------
# Pin number not in component (E007)
# ---------------------------------------------------------------------------

class TestE007BadPinRef:
    def test_nonexistent_pin_number(self):
        with pytest.raises(AnalysisError, match="E007.*does not exist"):
            _analyze("""
protocol P {
    lines { A }
    role r { A: Output }
}
component X {
    pins { 1: Bidirectional as P1 }
    features {
        external F using protocol P role r {
            A -> pin 99
        }
    }
}
""")


# ---------------------------------------------------------------------------
# Duplicate pin number (E008)
# ---------------------------------------------------------------------------

class TestE008DuplicatePinNumber:
    def test_same_pin_number(self):
        with pytest.raises(AnalysisError, match="E008.*Duplicate pin number"):
            _analyze("""
component X { pins { 1: Passive as A  1: Passive as B } }
""")


# ---------------------------------------------------------------------------
# Missing external feature for wire (E009)
# ---------------------------------------------------------------------------

class TestE009MissingFeature:
    def test_wire_without_feature(self):
        with pytest.raises(AnalysisError, match="E009.*does not have"):
            _analyze("""
protocol SPI {
    lines { MOSI }
    role master { MOSI: Output }
    role slave { MOSI: Input }
    rules { master.MOSI -- slave.MOSI }
}
component MCU {
    pins { 1: Bidirectional as P1 }
    features {
        external SPI using protocol SPI role master { MOSI -> pin 1 }
    }
}
component Flash {
    pins { 1: Bidirectional as P1 }
}
schematic S {
    instance mcu: MCU
    instance flash: Flash
    wire SPI {
        master: mcu
        slave: flash
    }
}
""")


# ---------------------------------------------------------------------------
# Connect to Unconnected pin (E010)
# ---------------------------------------------------------------------------

class TestE010Unconnected:
    def test_connect_unconnected(self):
        with pytest.raises(AnalysisError, match="E010.*Unconnected"):
            _analyze("""
component X { pins { 1: Unconnected as NC } }
schematic S {
    instance x: X
    net N
    connect x.NC -- net N
}
""")


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------

class TestWarnings:
    def test_w001_unconnected_pin(self):
        a = _analyze("""
component R { pins { 1: Passive as A  2: Passive as B } }
schematic S {
    instance r1: R
    net N
    connect r1.A -- net N
}
""")
        w001s = [w for w in a.warnings if w.code == "W001"]
        assert len(w001s) == 1
        assert "B" in w001s[0].message

    def test_w003_missing_required_attr(self):
        a = _analyze("""
component R {
    pins { 1: Passive as A }
    attributes { resistance: Resistance }
}
schematic S {
    instance r1: R
    net N
    connect r1.A -- net N
}
""")
        w003s = [w for w in a.warnings if w.code == "W003"]
        assert len(w003s) == 1
        assert "resistance" in w003s[0].message
