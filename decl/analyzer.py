"""Semantic analyzer for DECL: symbol resolution, type checking, and protocol validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .ast_nodes import (
    CommonRule,
    ComponentDef,
    ConnectStmt,
    ExternalFeature,
    ImportDecl,
    InstanceDecl,
    NetDecl,
    NetRef,
    PinDef,
    PinDirection,
    PinRef,
    Program,
    ProtocolDef,
    RoleDef,
    SchematicDef,
    TopLevelDecl,
    VariantDef,
    WireStmt,
    WiringRule,
)
from .errors import AnalysisError, SourceLocation, Warning
from .units import DISPLAY_TO_UNIT_TYPE, UnitValue


# ---------------------------------------------------------------------------
# Pin direction compatibility matrix
# ---------------------------------------------------------------------------

_COMPAT: dict[PinDirection, set[PinDirection]] = {
    PinDirection.INPUT: {
        PinDirection.OUTPUT,
        PinDirection.BIDIRECTIONAL,
        PinDirection.TRI_STATE,
        PinDirection.PASSIVE,
        PinDirection.FREE,
        PinDirection.OPEN_DRAIN,
    },
    PinDirection.OUTPUT: {
        PinDirection.INPUT,
        PinDirection.BIDIRECTIONAL,
        PinDirection.PASSIVE,
        PinDirection.FREE,
    },
    PinDirection.BIDIRECTIONAL: {
        PinDirection.INPUT,
        PinDirection.OUTPUT,
        PinDirection.BIDIRECTIONAL,
        PinDirection.TRI_STATE,
        PinDirection.PASSIVE,
        PinDirection.FREE,
        PinDirection.OPEN_DRAIN,
    },
    PinDirection.TRI_STATE: {
        PinDirection.INPUT,
        PinDirection.BIDIRECTIONAL,
        PinDirection.TRI_STATE,
        PinDirection.PASSIVE,
        PinDirection.FREE,
    },
    PinDirection.PASSIVE: {
        PinDirection.INPUT,
        PinDirection.OUTPUT,
        PinDirection.BIDIRECTIONAL,
        PinDirection.TRI_STATE,
        PinDirection.PASSIVE,
        PinDirection.FREE,
        PinDirection.POWER_OUTPUT,
        PinDirection.ANALOG,
        PinDirection.OPEN_DRAIN,
    },
    PinDirection.FREE: {
        PinDirection.INPUT,
        PinDirection.OUTPUT,
        PinDirection.BIDIRECTIONAL,
        PinDirection.TRI_STATE,
        PinDirection.PASSIVE,
        PinDirection.FREE,
        PinDirection.POWER_INPUT,
        PinDirection.POWER_OUTPUT,
        PinDirection.ANALOG,
        PinDirection.OPEN_DRAIN,
    },
    PinDirection.POWER_INPUT: {
        PinDirection.POWER_OUTPUT,
        PinDirection.FREE,
    },
    PinDirection.POWER_OUTPUT: {
        PinDirection.POWER_INPUT,
        PinDirection.PASSIVE,
        PinDirection.FREE,
    },
    PinDirection.UNCONNECTED: set(),
    PinDirection.ANALOG: {
        PinDirection.ANALOG,
        PinDirection.PASSIVE,
        PinDirection.FREE,
    },
    PinDirection.OPEN_DRAIN: {
        PinDirection.INPUT,
        PinDirection.OPEN_DRAIN,
        PinDirection.BIDIRECTIONAL,
        PinDirection.PASSIVE,
        PinDirection.FREE,
    },
}


def _directions_compatible(a: PinDirection, b: PinDirection) -> bool:
    return b in _COMPAT.get(a, set())


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class Analyzer:
    def __init__(self) -> None:
        self.protocols: dict[str, ProtocolDef] = {}
        self.components: dict[str, ComponentDef] = {}
        self.schematics: dict[str, SchematicDef] = {}
        self.variants: dict[str, VariantDef] = {}
        self.warnings: list[Warning] = []

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def analyze(self, program: Program) -> None:
        # First pass: register all top-level names
        for decl in program.declarations:
            if isinstance(decl, ImportDecl):
                continue
            self._register_global(decl)

        # Second pass: materialize variants into concrete components
        for var in list(self.variants.values()):
            self._materialize_variant(var)

        # Third pass: validate internals
        for proto in self.protocols.values():
            self._validate_protocol(proto)
        for comp in self.components.values():
            self._validate_component(comp)
        for schem in self.schematics.values():
            self._validate_schematic(schem)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _register_global(self, decl: TopLevelDecl) -> None:
        if isinstance(decl, ProtocolDef):
            if decl.name in self.protocols:
                raise AnalysisError("E001", f"Duplicate protocol '{decl.name}'", decl.loc)
            self.protocols[decl.name] = decl
        elif isinstance(decl, ComponentDef):
            if decl.name in self.components:
                raise AnalysisError("E001", f"Duplicate component '{decl.name}'", decl.loc)
            self.components[decl.name] = decl
        elif isinstance(decl, SchematicDef):
            if decl.name in self.schematics:
                raise AnalysisError("E001", f"Duplicate schematic '{decl.name}'", decl.loc)
            self.schematics[decl.name] = decl
        elif isinstance(decl, VariantDef):
            if decl.name in self.variants or decl.name in self.components:
                raise AnalysisError("E001", f"Duplicate name '{decl.name}'", decl.loc)
            self.variants[decl.name] = decl

    # ------------------------------------------------------------------
    # Variant materialization
    # ------------------------------------------------------------------

    def _materialize_variant(self, var: VariantDef) -> None:
        if var.base_component not in self.components:
            raise AnalysisError(
                "E002",
                f"Base component '{var.base_component}' referenced by variant "
                f"'{var.name}' is not defined",
                var.loc,
            )
        base = self.components[var.base_component]
        base_pin_names = {p.name for p in base.pins}

        mapped_names: set[str] = set()
        phys_numbers: set[int] = set()
        concrete_pins: list[PinDef] = []

        for pm in var.pinout:
            if pm.pin_name not in base_pin_names:
                raise AnalysisError(
                    "E002",
                    f"Pin '{pm.pin_name}' in variant '{var.name}' pinout is not "
                    f"defined in base component '{var.base_component}'",
                    pm.loc,
                )
            if pm.pin_name in mapped_names:
                raise AnalysisError(
                    "E001",
                    f"Duplicate pin mapping for '{pm.pin_name}' in variant '{var.name}'",
                    pm.loc,
                )
            if pm.physical_number in phys_numbers:
                raise AnalysisError(
                    "E008",
                    f"Duplicate physical pin number {pm.physical_number} in variant '{var.name}'",
                    pm.loc,
                )
            mapped_names.add(pm.pin_name)
            phys_numbers.add(pm.physical_number)

            base_pin = next(p for p in base.pins if p.name == pm.pin_name)
            concrete_pins.append(PinDef(
                number=pm.physical_number,
                direction=base_pin.direction,
                name=pm.pin_name,
                loc=pm.loc,
            ))

        from .ast_nodes import ExternalFeature as EF, InternalFeature as IF, PinMapping

        def _resolve_base_pin_name(fpm: PinMapping) -> str | None:
            if fpm.pin_name is not None:
                return fpm.pin_name
            if fpm.pin_number is not None:
                bp = next((p for p in base.pins if p.number == fpm.pin_number), None)
                return bp.name if bp else None
            return None

        concrete_features = []
        for feat in base.features:
            if isinstance(feat, IF):
                concrete_features.append(feat)
            elif isinstance(feat, EF):
                all_available = True
                new_mappings = []
                for fpm in feat.pin_mappings:
                    bname = _resolve_base_pin_name(fpm)
                    if bname is None or bname not in mapped_names:
                        all_available = False
                        break
                    variant_pm = next(pm for pm in var.pinout if pm.pin_name == bname)
                    new_mappings.append(PinMapping(
                        line_name=fpm.line_name,
                        pin_number=variant_pm.physical_number,
                        loc=fpm.loc,
                    ))
                if all_available:
                    concrete_features.append(EF(
                        name=feat.name,
                        protocol_name=feat.protocol_name,
                        role_name=feat.role_name,
                        pin_mappings=new_mappings,
                        loc=feat.loc,
                    ))

        concrete = ComponentDef(
            name=var.name,
            pins=concrete_pins,
            features=concrete_features,
            attributes=list(base.attributes),
            loc=var.loc,
        )
        self.components[var.name] = concrete

    # ------------------------------------------------------------------
    # Protocol validation
    # ------------------------------------------------------------------

    def _validate_protocol(self, proto: ProtocolDef) -> None:
        line_set = set(proto.lines)
        role_names: set[str] = set()
        for role in proto.roles:
            if role.name in role_names:
                raise AnalysisError(
                    "E001", f"Duplicate role '{role.name}' in protocol '{proto.name}'", role.loc
                )
            role_names.add(role.name)
            for ld in role.line_dirs:
                if ld.line_name not in line_set:
                    raise AnalysisError(
                        "E002",
                        f"Line '{ld.line_name}' in role '{role.name}' is not declared "
                        f"in protocol '{proto.name}' lines block",
                        ld.loc,
                    )

        for rule in proto.rules:
            if isinstance(rule, WiringRule):
                if rule.left_role not in role_names:
                    raise AnalysisError(
                        "E002",
                        f"Role '{rule.left_role}' referenced in wiring rule not defined "
                        f"in protocol '{proto.name}'",
                        rule.loc,
                    )
                if rule.right_role not in role_names:
                    raise AnalysisError(
                        "E002",
                        f"Role '{rule.right_role}' referenced in wiring rule not defined "
                        f"in protocol '{proto.name}'",
                        rule.loc,
                    )
                if rule.left_line not in line_set:
                    raise AnalysisError(
                        "E002",
                        f"Line '{rule.left_line}' referenced in wiring rule not declared "
                        f"in protocol '{proto.name}'",
                        rule.loc,
                    )
                if rule.right_line not in line_set:
                    raise AnalysisError(
                        "E002",
                        f"Line '{rule.right_line}' referenced in wiring rule not declared "
                        f"in protocol '{proto.name}'",
                        rule.loc,
                    )
            elif isinstance(rule, CommonRule):
                if rule.line_name not in line_set:
                    raise AnalysisError(
                        "E002",
                        f"Common line '{rule.line_name}' not declared in protocol '{proto.name}'",
                        rule.loc,
                    )

    # ------------------------------------------------------------------
    # Component validation
    # ------------------------------------------------------------------

    def _validate_component(self, comp: ComponentDef) -> None:
        pin_numbers: dict[int, PinDef] = {}
        pin_names: dict[str, PinDef] = {}

        for pin in comp.pins:
            if pin.number is not None:
                if pin.number in pin_numbers:
                    raise AnalysisError(
                        "E008",
                        f"Duplicate pin number {pin.number} in component '{comp.name}'",
                        pin.loc,
                    )
                pin_numbers[pin.number] = pin

            if pin.name in pin_names:
                raise AnalysisError(
                    "E001",
                    f"Duplicate pin name '{pin.name}' in component '{comp.name}'",
                    pin.loc,
                )
            pin_names[pin.name] = pin

        feat_names: set[str] = set()
        for feat in comp.features:
            if feat.name in feat_names:
                raise AnalysisError(
                    "E001",
                    f"Duplicate feature '{feat.name}' in component '{comp.name}'",
                    feat.loc,
                )
            feat_names.add(feat.name)

            if isinstance(feat, ExternalFeature):
                if feat.protocol_name not in self.protocols:
                    raise AnalysisError(
                        "E002",
                        f"Protocol '{feat.protocol_name}' referenced by feature "
                        f"'{feat.name}' in component '{comp.name}' is not defined",
                        feat.loc,
                    )

                proto = self.protocols[feat.protocol_name]
                role_map = {r.name: r for r in proto.roles}
                if feat.role_name not in role_map:
                    raise AnalysisError(
                        "E002",
                        f"Role '{feat.role_name}' not defined in protocol '{feat.protocol_name}'",
                        feat.loc,
                    )

                role = role_map[feat.role_name]
                role_line_names = {ld.line_name for ld in role.line_dirs}
                mapped_lines: set[str] = set()

                for pm in feat.pin_mappings:
                    if pm.line_name not in role_line_names:
                        raise AnalysisError(
                            "E002",
                            f"Line '{pm.line_name}' in pin mapping is not part of role "
                            f"'{feat.role_name}' in protocol '{feat.protocol_name}'",
                            pm.loc,
                        )
                    if pm.pin_number is not None:
                        if pm.pin_number not in pin_numbers:
                            raise AnalysisError(
                                "E007",
                                f"Pin {pm.pin_number} referenced in feature '{feat.name}' "
                                f"does not exist in component '{comp.name}'",
                                pm.loc,
                            )
                    elif pm.pin_name is not None:
                        if pm.pin_name not in pin_names:
                            raise AnalysisError(
                                "E007",
                                f"Pin '{pm.pin_name}' referenced in feature '{feat.name}' "
                                f"does not exist in component '{comp.name}'",
                                pm.loc,
                            )
                    mapped_lines.add(pm.line_name)

                missing = role_line_names - mapped_lines
                if missing:
                    raise AnalysisError(
                        "E006",
                        f"External feature '{feat.name}' in component '{comp.name}' is "
                        f"missing pin mappings for protocol lines: {', '.join(sorted(missing))}",
                        feat.loc,
                    )

        attr_names: set[str] = set()
        for attr in comp.attributes:
            if attr.name in attr_names:
                raise AnalysisError(
                    "E001",
                    f"Duplicate attribute '{attr.name}' in component '{comp.name}'",
                    attr.loc,
                )
            attr_names.add(attr.name)

            if attr.default is not None:
                self._check_attr_value_type(attr.type_expr.name, attr.default, attr.loc)

        for req in comp.requires:
            if req.component_type not in self.components:
                self.warnings.append(
                    Warning(
                        "W004",
                        f"Required component type '{req.component_type}' in component "
                        f"'{comp.name}' is not defined (may be defined elsewhere)",
                        req.loc,
                    )
                )

    def _check_attr_value_type(
        self, type_name: str, value: object, loc: Optional[SourceLocation]
    ) -> None:
        expected = DISPLAY_TO_UNIT_TYPE.get(type_name)
        if expected is None:
            return  # custom or parameterized type -- skip for now
        if isinstance(value, UnitValue):
            if value.unit_type != expected:
                raise AnalysisError(
                    "E005",
                    f"Attribute type mismatch: expected {type_name}, got {value.unit_type}",
                    loc,
                )

    # ------------------------------------------------------------------
    # Schematic validation
    # ------------------------------------------------------------------

    def _validate_schematic(self, schem: SchematicDef) -> None:
        inst_map: dict[str, InstanceDecl] = {}
        net_names: set[str] = set()
        connected_pins: set[tuple[str, str]] = set()

        # Register instances
        for inst in schem.instances:
            if inst.name in inst_map:
                raise AnalysisError(
                    "E001",
                    f"Duplicate instance name '{inst.name}' in schematic '{schem.name}'",
                    inst.loc,
                )
            if inst.component_name not in self.components:
                raise AnalysisError(
                    "E002",
                    f"Component '{inst.component_name}' referenced by instance "
                    f"'{inst.name}' is not defined",
                    inst.loc,
                )
            inst_map[inst.name] = inst

            comp = self.components[inst.component_name]
            comp_attr_names = {a.name for a in comp.attributes}
            for ov in inst.overrides:
                if ov.name not in comp_attr_names:
                    raise AnalysisError(
                        "E002",
                        f"Attribute '{ov.name}' not declared in component '{inst.component_name}'",
                        ov.loc,
                    )
                attr_decl = next(a for a in comp.attributes if a.name == ov.name)
                self._check_attr_value_type(attr_decl.type_expr.name, ov.value, ov.loc)

        # Register nets
        for net in schem.nets:
            if net.name in net_names:
                raise AnalysisError(
                    "E001",
                    f"Duplicate net name '{net.name}' in schematic '{schem.name}'",
                    net.loc,
                )
            net_names.add(net.name)

        # Validate connect statements
        for conn in schem.connects:
            self._validate_endpoint(conn.left, inst_map, net_names, schem.name)
            self._validate_endpoint(conn.right, inst_map, net_names, schem.name)
            self._check_connect_directions(conn, inst_map)

            for ep in (conn.left, conn.right):
                if isinstance(ep, PinRef):
                    connected_pins.add((ep.instance_name, ep.pin_name))

        # Validate wire statements
        for wire in schem.wires:
            if wire.protocol_name not in self.protocols:
                raise AnalysisError(
                    "E002",
                    f"Protocol '{wire.protocol_name}' referenced in wire statement "
                    f"is not defined",
                    wire.loc,
                )
            proto = self.protocols[wire.protocol_name]
            role_map = {r.name: r for r in proto.roles}

            for binding in wire.bindings:
                if binding.role_name not in role_map:
                    raise AnalysisError(
                        "E002",
                        f"Role '{binding.role_name}' not defined in protocol "
                        f"'{wire.protocol_name}'",
                        binding.loc,
                    )
                if binding.instance_name not in inst_map:
                    raise AnalysisError(
                        "E002",
                        f"Instance '{binding.instance_name}' not defined in schematic "
                        f"'{schem.name}'",
                        binding.loc,
                    )

                inst = inst_map[binding.instance_name]
                comp = self.components[inst.component_name]
                has_feature = any(
                    isinstance(f, ExternalFeature)
                    and f.protocol_name == wire.protocol_name
                    and f.role_name == binding.role_name
                    for f in comp.features
                )
                if not has_feature:
                    raise AnalysisError(
                        "E009",
                        f"Component '{inst.component_name}' (instance '{inst.name}') "
                        f"does not have an external feature for protocol "
                        f"'{wire.protocol_name}' role '{binding.role_name}'",
                        binding.loc,
                    )

            self._validate_wire_rules(wire, proto, inst_map, connected_pins)

        # Warn about unconnected pins
        for inst in schem.instances:
            comp = self.components[inst.component_name]
            for pin in comp.pins:
                if pin.direction == PinDirection.UNCONNECTED:
                    continue
                if (inst.name, pin.name) not in connected_pins:
                    self.warnings.append(
                        Warning(
                            "W001",
                            f"Pin '{pin.name}' on instance '{inst.name}' "
                            f"({inst.component_name}) is not connected",
                            inst.loc,
                        )
                    )

        # Warn about required attributes without defaults that are not overridden
        for inst in schem.instances:
            comp = self.components[inst.component_name]
            overridden = {ov.name for ov in inst.overrides}
            for attr in comp.attributes:
                if attr.default is None and attr.name not in overridden:
                    self.warnings.append(
                        Warning(
                            "W003",
                            f"Attribute '{attr.name}' on instance '{inst.name}' "
                            f"({inst.component_name}) has no default and is not overridden",
                            inst.loc,
                        )
                    )

    def _validate_endpoint(
        self,
        ep: object,
        inst_map: dict[str, InstanceDecl],
        net_names: set[str],
        schem_name: str,
    ) -> None:
        if isinstance(ep, PinRef):
            if ep.instance_name not in inst_map:
                raise AnalysisError(
                    "E002",
                    f"Instance '{ep.instance_name}' not defined in schematic '{schem_name}'",
                    ep.loc,
                )
            inst = inst_map[ep.instance_name]
            comp = self.components[inst.component_name]
            pin_names = {p.name for p in comp.pins}
            if ep.pin_name not in pin_names:
                raise AnalysisError(
                    "E002",
                    f"Pin '{ep.pin_name}' not defined in component '{inst.component_name}'",
                    ep.loc,
                )
            pin_def = next(p for p in comp.pins if p.name == ep.pin_name)
            if pin_def.direction == PinDirection.UNCONNECTED:
                raise AnalysisError(
                    "E010",
                    f"Cannot connect to Unconnected pin '{ep.pin_name}' on "
                    f"instance '{ep.instance_name}'",
                    ep.loc,
                )
        elif isinstance(ep, NetRef):
            if ep.net_name not in net_names:
                raise AnalysisError(
                    "E002",
                    f"Net '{ep.net_name}' not defined in schematic '{schem_name}'",
                    ep.loc,
                )

    def _resolve_pin_direction(
        self, ep: object, inst_map: dict[str, InstanceDecl]
    ) -> Optional[PinDirection]:
        if isinstance(ep, PinRef):
            inst = inst_map[ep.instance_name]
            comp = self.components[inst.component_name]
            pin_def = next(p for p in comp.pins if p.name == ep.pin_name)
            return pin_def.direction
        return None  # net endpoints don't have inherent direction

    def _check_connect_directions(
        self, conn: ConnectStmt, inst_map: dict[str, InstanceDecl]
    ) -> None:
        left_dir = self._resolve_pin_direction(conn.left, inst_map)
        right_dir = self._resolve_pin_direction(conn.right, inst_map)
        if left_dir is not None and right_dir is not None:
            if not _directions_compatible(left_dir, right_dir):
                raise AnalysisError(
                    "E003",
                    f"Pin direction incompatibility: {left_dir.name} cannot connect "
                    f"to {right_dir.name}",
                    conn.loc,
                )

    def _validate_wire_rules(
        self,
        wire: WireStmt,
        proto: ProtocolDef,
        inst_map: dict[str, InstanceDecl],
        connected_pins: set[tuple[str, str]],
    ) -> None:
        binding_map = {b.role_name: b.instance_name for b in wire.bindings}

        for rule in proto.rules:
            if not isinstance(rule, WiringRule):
                continue

            left_inst_name = binding_map.get(rule.left_role)
            right_inst_name = binding_map.get(rule.right_role)
            if left_inst_name is None or right_inst_name is None:
                raise AnalysisError(
                    "E004",
                    f"Wire block for protocol '{wire.protocol_name}' is missing binding "
                    f"for role '{rule.left_role if left_inst_name is None else rule.right_role}'",
                    wire.loc,
                )

            left_pin = self._resolve_protocol_pin(
                wire.protocol_name, rule.left_role, rule.left_line,
                left_inst_name, inst_map,
            )
            right_pin = self._resolve_protocol_pin(
                wire.protocol_name, rule.right_role, rule.right_line,
                right_inst_name, inst_map,
            )

            if left_pin:
                connected_pins.add(left_pin)
            if right_pin:
                connected_pins.add(right_pin)

    def _resolve_protocol_pin(
        self,
        protocol_name: str,
        role_name: str,
        line_name: str,
        instance_name: str,
        inst_map: dict[str, InstanceDecl],
    ) -> Optional[tuple[str, str]]:
        inst = inst_map[instance_name]
        comp = self.components[inst.component_name]
        for feat in comp.features:
            if (
                isinstance(feat, ExternalFeature)
                and feat.protocol_name == protocol_name
                and feat.role_name == role_name
            ):
                for pm in feat.pin_mappings:
                    if pm.line_name == line_name:
                        if pm.pin_number is not None:
                            pin_def = next(
                                (p for p in comp.pins if p.number == pm.pin_number), None
                            )
                        elif pm.pin_name is not None:
                            pin_def = next(
                                (p for p in comp.pins if p.name == pm.pin_name), None
                            )
                        else:
                            pin_def = None
                        if pin_def:
                            return (instance_name, pin_def.name)
        return None
