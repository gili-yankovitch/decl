"""AST node definitions for the DECL language."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Union

from .errors import SourceLocation
from .units import UnitValue


# ---------------------------------------------------------------------------
# Pin direction enum (mirrors the token pin types but lives in the AST layer)
# ---------------------------------------------------------------------------

class PinDirection(Enum):
    INPUT = auto()
    OUTPUT = auto()
    BIDIRECTIONAL = auto()
    TRI_STATE = auto()
    PASSIVE = auto()
    FREE = auto()
    POWER_INPUT = auto()
    POWER_OUTPUT = auto()
    UNCONNECTED = auto()
    ANALOG = auto()
    OPEN_DRAIN = auto()

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Value types that can appear in attributes / assignments
# ---------------------------------------------------------------------------

ValueExpr = Union[UnitValue, int, float, str, "TypeExpr"]


@dataclass
class TypeExpr:
    """A type reference, possibly parameterized: e.g. VoltageRange(1.8V, 5.5V)."""
    name: str
    args: list[ValueExpr] = field(default_factory=list)
    loc: Optional[SourceLocation] = None


# ---------------------------------------------------------------------------
# Protocol AST
# ---------------------------------------------------------------------------

@dataclass
class LineDirDecl:
    """A line-direction assignment inside a role: ``MOSI: Output``."""
    line_name: str
    direction: PinDirection
    loc: Optional[SourceLocation] = None


@dataclass
class RoleDef:
    """A role block inside a protocol."""
    name: str
    line_dirs: list[LineDirDecl] = field(default_factory=list)
    loc: Optional[SourceLocation] = None


@dataclass
class WiringRule:
    """``master.MOSI -- slave.MOSI``."""
    left_role: str
    left_line: str
    right_role: str
    right_line: str
    loc: Optional[SourceLocation] = None


@dataclass
class CommonRule:
    """``common GND``."""
    line_name: str
    loc: Optional[SourceLocation] = None


RuleStmt = Union[WiringRule, CommonRule]


@dataclass
class ProtocolDef:
    name: str
    lines: list[str] = field(default_factory=list)
    roles: list[RoleDef] = field(default_factory=list)
    rules: list[RuleStmt] = field(default_factory=list)
    loc: Optional[SourceLocation] = None


# ---------------------------------------------------------------------------
# Component AST
# ---------------------------------------------------------------------------

@dataclass
class PinDef:
    """``1: Passive as A`` (numbered) or ``PD4: Bidirectional`` (named-only for base components)."""
    number: Optional[int]
    direction: PinDirection
    name: str
    loc: Optional[SourceLocation] = None


@dataclass
class AttrAssign:
    """Simple key-value: ``frequency: 8MHz``."""
    name: str
    value: ValueExpr
    loc: Optional[SourceLocation] = None


@dataclass
class PinMapping:
    """``MOSI -> pin 17`` or ``MOSI -> pin PD4``."""
    line_name: str
    pin_number: Optional[int] = None
    pin_name: Optional[str] = None
    loc: Optional[SourceLocation] = None


@dataclass
class InternalFeature:
    name: str
    properties: list[AttrAssign] = field(default_factory=list)
    loc: Optional[SourceLocation] = None


@dataclass
class ExternalFeature:
    name: str
    protocol_name: str
    role_name: str
    pin_mappings: list[PinMapping] = field(default_factory=list)
    loc: Optional[SourceLocation] = None


FeatureDef = Union[InternalFeature, ExternalFeature]


@dataclass
class AttrDecl:
    """``resistance: Resistance`` or ``tolerance: Percentage = 5%``."""
    name: str
    type_expr: TypeExpr
    default: Optional[ValueExpr] = None
    loc: Optional[SourceLocation] = None


@dataclass
class RequiresEntry:
    """``Capacitor { capacitance = 100nF } * 2`` inside a requires block."""
    component_type: str
    attributes: list[AttrAssign] = field(default_factory=list)
    count: int = 1
    loc: Optional[SourceLocation] = None


@dataclass
class ComponentDef:
    name: str
    pins: list[PinDef] = field(default_factory=list)
    features: list[FeatureDef] = field(default_factory=list)
    attributes: list[AttrDecl] = field(default_factory=list)
    requires: list[RequiresEntry] = field(default_factory=list)
    loc: Optional[SourceLocation] = None


# ---------------------------------------------------------------------------
# Schematic AST
# ---------------------------------------------------------------------------

@dataclass
class InstanceDecl:
    """``instance mcu: ATmega328P`` or ``instance r1: Resistor { resistance = 10kohm }``."""
    name: str
    component_name: str
    overrides: list[AttrAssign] = field(default_factory=list)
    loc: Optional[SourceLocation] = None


@dataclass
class NetDecl:
    """``net VCC_3V3``."""
    name: str
    loc: Optional[SourceLocation] = None


@dataclass
class PinRef:
    """``mcu.VCC`` -- reference to a pin on an instance."""
    instance_name: str
    pin_name: str
    loc: Optional[SourceLocation] = None


@dataclass
class NetRef:
    """``net GND`` used as a connect endpoint."""
    net_name: str
    loc: Optional[SourceLocation] = None


ConnectEndpoint = Union[PinRef, NetRef]


@dataclass
class ConnectStmt:
    """``connect r1.A -- mcu.PD0``."""
    left: ConnectEndpoint
    right: ConnectEndpoint
    loc: Optional[SourceLocation] = None


@dataclass
class WireBinding:
    """``master: mcu``."""
    role_name: str
    instance_name: str
    loc: Optional[SourceLocation] = None


@dataclass
class WireStmt:
    """``wire SPI { master: mcu  slave: flash }``."""
    protocol_name: str
    bindings: list[WireBinding] = field(default_factory=list)
    loc: Optional[SourceLocation] = None


@dataclass
class SchematicDef:
    name: str
    instances: list[InstanceDecl] = field(default_factory=list)
    nets: list[NetDecl] = field(default_factory=list)
    connects: list[ConnectStmt] = field(default_factory=list)
    wires: list[WireStmt] = field(default_factory=list)
    loc: Optional[SourceLocation] = None


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

@dataclass
class ImportDecl:
    path: str
    is_system: bool = False
    loc: Optional[SourceLocation] = None


# ---------------------------------------------------------------------------
# Variant (package variant of a base component)
# ---------------------------------------------------------------------------

@dataclass
class PinoutMapping:
    """``PD4 -> 1``."""
    pin_name: str
    physical_number: int
    loc: Optional[SourceLocation] = None


@dataclass
class VariantDef:
    """``variant CH32V003F4P6 of CH32V003 { ... }``."""
    name: str
    base_component: str
    properties: list[AttrAssign] = field(default_factory=list)
    pinout: list[PinoutMapping] = field(default_factory=list)
    loc: Optional[SourceLocation] = None


# ---------------------------------------------------------------------------
# Top-level program
# ---------------------------------------------------------------------------

TopLevelDecl = Union[ImportDecl, ProtocolDef, ComponentDef, SchematicDef, VariantDef]


@dataclass
class Program:
    declarations: list[TopLevelDecl] = field(default_factory=list)
