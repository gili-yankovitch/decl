# DECL Language Specification

**Version:** 0.2.0

## 1. Notation

This specification uses Extended Backus-Naur Form (EBNF) to describe the grammar.

- `|` denotes alternatives
- `[ ... ]` denotes optional elements
- `{ ... }` denotes zero or more repetitions
- `( ... )` groups elements
- `"..."` denotes terminal strings (keywords/symbols)
- `UPPER_CASE` denotes token classes produced by the lexer

---

## 2. Lexical Structure

### 2.1 Comments

Single-line comments begin with `//` and extend to end of line.

```
// This is a comment
```

### 2.2 Whitespace

Spaces, tabs, carriage returns, and newlines are whitespace. Whitespace separates tokens but is otherwise insignificant.

### 2.3 Identifiers

```
IDENT       = LETTER { LETTER | DIGIT | "_" }
LETTER      = "a".."z" | "A".."Z" | "_"
DIGIT       = "0".."9"
```

### 2.4 Numeric Literals

```
NUMBER      = DIGITS [ "." DIGITS ]
DIGITS      = DIGIT { DIGIT }
```

### 2.5 String Literals

```
STRING      = '"' { any character except '"' and newline } '"'
```

### 2.6 Unit Literals

A unit literal is a `NUMBER` immediately followed (no whitespace) by an optional SI prefix and a unit suffix.

```
UNIT_LITERAL = NUMBER [ SI_PREFIX ] UNIT_SUFFIX

SI_PREFIX    = "p" | "n" | "u" | "m" | "k" | "M" | "G"
UNIT_SUFFIX  = "ohm" | "F" | "H" | "V" | "A" | "W" | "Hz" | "%" | "B"
```

Prefix multipliers:

| Prefix | Name  | Factor |
|--------|-------|--------|
| `p`    | pico  | 10^-12 |
| `n`    | nano  | 10^-9  |
| `u`    | micro | 10^-6  |
| `m`    | milli | 10^-3  |
| `k`    | kilo  | 10^3   |
| `M`    | mega  | 10^6   |
| `G`    | giga  | 10^9   |

Unit types:

| Suffix | Quantity    | SI Unit |
|--------|------------|---------|
| `ohm`  | Resistance | Ohm     |
| `F`    | Capacitance| Farad   |
| `H`    | Inductance | Henry   |
| `V`    | Voltage    | Volt    |
| `A`    | Current    | Ampere  |
| `W`    | Power      | Watt    |
| `Hz`   | Frequency  | Hertz   |
| `%`    | Percentage | —       |
| `B`    | Data size  | Byte    |

Examples: `10kohm`, `100nF`, `4.7uH`, `3.3V`, `500mA`, `0.25W`, `8MHz`, `5%`, `32kB`

### 2.7 Keywords

```
protocol  component  schematic  import
pins      features   attributes
internal  external   using      role
lines     rules      common
instance  net        connect    wire
as        pin        variant    of
pinout
```

### 2.8 Symbols

```
{  }  (  )  :  .  ,  =  ->  --
```

---

## 3. Grammar

### 3.1 Program

```
program         = { top_level_decl }
top_level_decl  = import_decl | protocol_def | component_def | schematic_def
                | variant_def
```

### 3.2 Import

```
import_decl     = "import" STRING
```

### 3.3 Protocol Definition

```
protocol_def    = "protocol" IDENT "{" { protocol_body } "}"
protocol_body   = lines_block | role_block | rules_block

lines_block     = "lines" "{" { IDENT } "}"

role_block      = "role" IDENT "{" { line_dir_decl } "}"
line_dir_decl   = IDENT ":" pin_type

rules_block     = "rules" "{" { rule_stmt } "}"
rule_stmt       = wiring_rule | common_rule
wiring_rule     = qual_ident "--" qual_ident
common_rule     = "common" IDENT

qual_ident      = IDENT "." IDENT
```

**Semantics:**

- `lines` declares the abstract signal names in this protocol.
- Each `role` assigns a pin direction to every line from that participant's perspective.
- `rules` constrain how lines connect between roles. A `wiring_rule` states that line X on role A must connect to line Y on role B. A `common` rule states all instances of the named line must be joined into a single net.

### 3.4 Component Definition

```
component_def   = "component" IDENT "{" { component_body } "}"
component_body  = pins_block | features_block | attributes_block

pins_block      = "pins" "{" { pin_decl } "}"
pin_decl        = NUMBER ":" pin_type "as" IDENT
                | IDENT ":" pin_type [ "as" IDENT ]

pin_type        = "Input" | "Output" | "Bidirectional" | "TriState"
                | "Passive" | "Free" | "PowerInput" | "PowerOutput"
                | "Unconnected" | "Analog" | "OpenDrain"

features_block  = "features" "{" { feature_decl } "}"
feature_decl    = internal_feature | external_feature

internal_feature = "internal" IDENT "{" { attr_assign } "}"
external_feature = "external" IDENT "using" "protocol" IDENT "role" IDENT
                   "{" { pin_mapping } "}"
pin_mapping     = IDENT "->" "pin" ( NUMBER | IDENT )

attributes_block = "attributes" "{" { attr_decl } "}"
attr_decl       = IDENT ":" type_expr [ "=" value_expr ]

type_expr       = IDENT [ "(" value_expr { "," value_expr } ")" ]
value_expr      = UNIT_LITERAL | NUMBER | STRING | IDENT
attr_assign     = IDENT ":" value_expr
```

**Semantics:**

- `pins`: Each pin has a direction type and a logical name. Two forms:
  - **Numbered:** `NUMBER : pin_type as IDENT` — assigns a physical pin number (used for discrete components and fully-specified ICs).
  - **Named-only:** `IDENT : pin_type` — defines a logical pin without a physical number (used for base components that are materialized via `variant`).
  Pin numbers (when present) must be unique. Sequential gaps are allowed.
- `features`:
  - `internal` features are informational metadata (e.g. internal clock frequency).
  - `external` features bind a protocol role to pins. Every line declared in the protocol's role must have a corresponding `pin_mapping`. The `pin` target can be a number (`pin 17`) or a name (`pin PD5`) for named-only pins.
- `attributes`: Typed properties with optional default values. The type name corresponds to a unit quantity (`Resistance`, `Capacitance`, `Voltage`, `Power`, `Percentage`, etc.) or a parameterized type like `VoltageRange(min, max)`.

#### Pin Types Added in v0.2

| Type        | Description |
|-------------|-------------|
| `Analog`    | Analog signal pin (ADC/DAC). Connects only to `Analog`, `Passive`, or `Free`. |
| `OpenDrain` | Open-drain output (e.g. I2C SDA/SCL). Connects to `Input`, `OpenDrain`, `Bidirectional`, `Passive`, or `Free`. |

### 3.5 Schematic Definition

```
schematic_def   = "schematic" IDENT "{" { schematic_body } "}"
schematic_body  = instance_decl | net_decl | connect_stmt | wire_stmt

instance_decl   = "instance" IDENT ":" IDENT [ "{" { attr_assign } "}" ]

net_decl        = "net" IDENT

connect_stmt    = "connect" connect_endpoint "--" connect_endpoint
connect_endpoint = qual_ident | "net" IDENT

wire_stmt       = "wire" IDENT "{" { wire_binding } "}"
wire_binding    = IDENT ":" IDENT
```

**Semantics:**

- `instance`: Creates a named instance of a previously defined component. Attribute overrides in braces must match declared attributes and satisfy their type constraints.
- `net`: Declares a named wire that multiple pins can join.
- `connect`: Joins two endpoints. An endpoint is either `<instance>.<pin_name>` or `net <net_name>`.
- `wire`: Connects components through a protocol. Each binding maps a role name to a component instance. The validator expands this into individual pin connections per the protocol's `rules`, using each component's `external` feature pin mappings.

### 3.6 Variant Definition

```
variant_def     = "variant" IDENT "of" IDENT "{" { variant_body } "}"
variant_body    = pinout_block | attr_assign

pinout_block    = "pinout" "{" { pinout_mapping } "}"
pinout_mapping  = IDENT "->" NUMBER
```

**Semantics:**

A `variant` defines a concrete, instantiable package variant of a base component. The `of` clause references a previously defined `component`.

- The `pinout` block maps logical pin names from the base component to physical pin numbers for this specific package. Each name must exist in the base component's `pins` block. Physical numbers must be unique.
- Pins from the base component that are **not** listed in the pinout are excluded from the variant (not bonded out in this package).
- External features from the base component are automatically carried forward **only if** all of their mapped pins are available in the variant's pinout. Features whose pins are partially or fully unavailable are silently dropped.
- Internal features and attributes are inherited in full.
- The variant name enters the global namespace and can be used as a component name in `instance` declarations.

**Example:**

```
component CH32V003 {
    pins {
        PA1: Bidirectional
        PA2: Bidirectional
        VDD: PowerInput
        VSS: PowerInput
    }
    // ... features and attributes ...
}

variant CH32V003F4P6 of CH32V003 {
    package: "TSSOP20"
    pinout {
        PA1 -> 5
        PA2 -> 6
        VDD -> 9
        VSS -> 7
    }
}

schematic Board {
    instance mcu: CH32V003F4P6   // uses the variant
    // ...
}
```

---

## 4. Pin Direction Compatibility

When two pins are connected, the following compatibility matrix applies. A connection is valid if the cell is marked YES.

| From \ To     | In  | Out | Bidir | TriSt | Pass | Free | PwrIn | PwrOut | Uncon | Analog | ODrain |
|---------------|-----|-----|-------|-------|------|------|-------|--------|-------|--------|--------|
| **Input**     | —   | YES | YES   | YES   | YES  | YES  | —     | —      | —     | —      | YES    |
| **Output**    | YES | —   | YES   | —     | YES  | YES  | —     | —      | —     | —      | —      |
| **Bidir**     | YES | YES | YES   | YES   | YES  | YES  | —     | —      | —     | —      | YES    |
| **TriState**  | YES | —   | YES   | YES   | YES  | YES  | —     | —      | —     | —      | —      |
| **Passive**   | YES | YES | YES   | YES   | YES  | YES  | —     | YES    | —     | YES    | YES    |
| **Free**      | YES | YES | YES   | YES   | YES  | YES  | YES   | YES    | —     | YES    | YES    |
| **PwrIn**     | —   | —   | —     | —     | —    | YES  | —     | YES    | —     | —      | —      |
| **PwrOut**    | —   | —   | —     | —     | YES  | YES  | YES   | —      | —     | —      | —      |
| **Uncon**     | —   | —   | —     | —     | —    | —    | —     | —      | —     | —      | —      |
| **Analog**    | —   | —   | —     | —     | YES  | YES  | —     | —      | —     | YES    | —      |
| **OpenDrain** | YES | —   | YES   | —     | YES  | YES  | —     | —      | —     | —      | YES    |

Key rules:
- `Output` cannot connect to `Output` (short circuit).
- `PowerInput` can only receive from `PowerOutput` or `Free`.
- `Unconnected` pins must never appear in a `connect` or `wire` statement.
- `Passive` pins are permissive (resistors, capacitors, inductors).
- `Analog` connects only to `Analog`, `Passive`, or `Free` — prevents accidental mixing of analog signals with digital drivers.
- `OpenDrain` connects to `Input`, `Bidirectional`, `OpenDrain`, `Passive`, or `Free` — models wired-AND buses like I2C where multiple open-drain outputs share a line with a pull-up.

---

## 5. Validation Rules

The semantic analyzer enforces these rules and produces errors or warnings:

### 5.1 Errors (fatal)

| Code   | Rule |
|--------|------|
| E001   | Duplicate identifier in the same scope |
| E002   | Reference to undefined component, protocol, instance, pin, or net |
| E003   | Pin direction incompatibility (see Section 4) |
| E004   | Protocol wiring violation: required connection missing or mismatched |
| E005   | Attribute type mismatch (e.g. assigning a Voltage value to a Resistance attribute) |
| E006   | External feature missing pin mapping for a protocol line |
| E007   | Pin mapped in external feature does not exist in the component's pins block |
| E008   | Pin number conflict: same physical number declared twice |
| E009   | `wire` block references a component that lacks the required external feature/role |
| E010   | Connecting to an `Unconnected` pin |

### 5.2 Warnings

| Code   | Rule |
|--------|------|
| W001   | Non-`Unconnected` pin has no connection in the schematic |
| W002   | `common` net rule not satisfied: instances of the line are on different nets |
| W003   | Attribute declared without default and not overridden in instance |

---

## 6. Import Resolution

```
import "path/to/file.decl"
```

Paths are resolved relative to the importing file's directory. The standard library (`stdlib/`) is always on the search path. Circular imports are detected and produce E001.

---

## 7. Scope Rules

- **Global scope:** Protocol names, component names, variant names, and schematic names share a single global namespace. A variant name must not collide with any component name and vice versa.
- **Component scope:** Pin names, feature names, and attribute names are scoped to their enclosing component.
- **Schematic scope:** Instance names, net names are scoped to their enclosing schematic.
- **Protocol scope:** Line names and role names are scoped to their enclosing protocol.
- **Variant scope:** Pinout mappings and property assignments are scoped to the variant. A variant inherits all features and attributes from its base component.
