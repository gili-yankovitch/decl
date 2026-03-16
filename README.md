# DECL -- Declarative Electronic Component Language

A domain-specific language for defining electronic components, communication protocols, and circuit schematics with built-in protocol-aware connection validation.

## Quick Start

```bash
pip install -e ".[dev]"
decl check examples/blink_led.decl
```

## Language Overview

DECL files (`.decl`) contain three kinds of declarations:

- **`protocol`** -- communication standards (SPI, I2C, UART) with connection rules
- **`component`** -- parts with pins, features, and electrical attributes
- **`schematic`** -- circuit designs that instantiate components and wire them together

### Example

```
component Resistor {
    pins {
        1: Passive as A
        2: Passive as B
    }
    attributes {
        resistance: Resistance
    }
}

schematic PullUp {
    instance r1: Resistor { resistance = 10kohm }
    net VCC
    net SIGNAL
    connect r1.A -- net VCC
    connect r1.B -- net SIGNAL
}
```

See `docs/language_spec.md` for the full specification and `examples/` for more.

## Project Structure

```
decl/           Python package (lexer, parser, analyzer)
stdlib/         Built-in protocols and component definitions
examples/       Example .decl files
tests/          Unit tests
docs/           Language specification
```

## Running Tests

```bash
pytest
```
