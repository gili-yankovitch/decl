"""Electrical unit system: parsing, normalization, and type checking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class UnitType(Enum):
    RESISTANCE = auto()
    CAPACITANCE = auto()
    INDUCTANCE = auto()
    VOLTAGE = auto()
    CURRENT = auto()
    POWER = auto()
    FREQUENCY = auto()
    PERCENTAGE = auto()
    DATA_SIZE = auto()

    def __str__(self) -> str:
        return _UNIT_TYPE_DISPLAY[self]


_UNIT_TYPE_DISPLAY = {
    UnitType.RESISTANCE: "Resistance",
    UnitType.CAPACITANCE: "Capacitance",
    UnitType.INDUCTANCE: "Inductance",
    UnitType.VOLTAGE: "Voltage",
    UnitType.CURRENT: "Current",
    UnitType.POWER: "Power",
    UnitType.FREQUENCY: "Frequency",
    UnitType.PERCENTAGE: "Percentage",
    UnitType.DATA_SIZE: "DataSize",
}

DISPLAY_TO_UNIT_TYPE = {v: k for k, v in _UNIT_TYPE_DISPLAY.items()}

SUFFIX_TO_UNIT: dict[str, UnitType] = {
    "ohm": UnitType.RESISTANCE,
    "F": UnitType.CAPACITANCE,
    "H": UnitType.INDUCTANCE,
    "V": UnitType.VOLTAGE,
    "A": UnitType.CURRENT,
    "W": UnitType.POWER,
    "Hz": UnitType.FREQUENCY,
    "%": UnitType.PERCENTAGE,
    "B": UnitType.DATA_SIZE,
}

PREFIX_MULTIPLIER: dict[str, float] = {
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "M": 1e6,
    "G": 1e9,
}

_SUFFIXES_BY_LENGTH = sorted(SUFFIX_TO_UNIT.keys(), key=len, reverse=True)
_UNIT_RE = re.compile(
    r"^(\d+(?:\.\d+)?)"
    r"([pnumkMG])?"
    r"(ohm|Hz|F|H|V|A|W|%|B)$"
)


@dataclass(frozen=True)
class UnitValue:
    """A numeric value with an associated electrical unit."""

    raw_number: float
    prefix: Optional[str]
    suffix: str
    unit_type: UnitType

    @property
    def base_value(self) -> float:
        mult = PREFIX_MULTIPLIER.get(self.prefix, 1.0) if self.prefix else 1.0
        return self.raw_number * mult

    def __repr__(self) -> str:
        return f"UnitValue({self.raw_number}{self.prefix or ''}{self.suffix})"

    def __str__(self) -> str:
        return f"{self.raw_number}{self.prefix or ''}{self.suffix}"


def parse_unit(text: str) -> Optional[UnitValue]:
    """Parse a unit literal string into a UnitValue, or return None if not valid."""
    m = _UNIT_RE.match(text)
    if not m:
        return None
    raw = float(m.group(1))
    prefix = m.group(2)
    suffix = m.group(3)
    unit_type = SUFFIX_TO_UNIT[suffix]
    return UnitValue(raw_number=raw, prefix=prefix, suffix=suffix, unit_type=unit_type)


def try_split_unit(text: str) -> Optional[tuple[str, str, str]]:
    """Try to split a string into (number, prefix, suffix) parts.

    Returns None if the string doesn't look like a unit literal.
    Used by the lexer to detect unit tokens.
    """
    m = _UNIT_RE.match(text)
    if not m:
        return None
    return m.group(1), m.group(2) or "", m.group(3)
