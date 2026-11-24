# PyfieldBridge

[![CI](https://github.com/MAbdelhamid-Admin/PyfieldBridge/actions/workflows/ci.yml/badge.svg)](https://github.com/MAbdelhamid-Admin/PyfieldBridge/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Python port of [fieldbridge](https://github.com/MAbdelhamid-Admin/fieldBridge):
validated frame-envelope conversion and raw-byte parsing for industrial and
automotive protocols.

- Strict validation against each protocol's limits on both encode and decode
- Payload bytes are preserved exactly; nothing is silently guessed
- Device IDs bridge message-addressed buses (CAN, LIN) and device-addressed
  buses (Modbus, PROFIBUS, EtherCAT)
- Parse and serialize real wire bytes: Modbus TCP/RTU, SocketCAN and candump,
  Ethernet, PROFINET RT, EtherCAT
- Typed `FieldbridgeError` exceptions with stable codes, plus a non-throwing
  `try_*` API
- No runtime dependencies; Python 3.10+

The Python API mirrors the TypeScript one, with snake_case names as the
primary spelling and camelCase aliases for drop-in compatibility (for example
`convert_frame` / `convertFrame` and `target_protocol` / `targetProtocol`).

## Install

```bash
python -m pip install -e .
```

The import package is `fieldbridge`; `pyfieldbridge` is provided as a
compatibility package name.

## Quick start

```python
from fieldbridge import convert_message

result = convert_message({
    "source": {
        "device_id": 17,
        "message": {"protocol": "can", "identifier": 0x123, "payload": [3, 0, 10]},
    },
    "target": {"protocol": "modbus-rtu"},
})

print(result.message)   # {'protocol': 'modbus-rtu', 'address': 17, 'device_id': 17, 'payload': [3, 0, 10]}
print(result.warnings)  # explains what was inferred, overridden or dropped
```

## API

- `convert_frame(request)`, `convert_message(request)`
- `try_convert_frame(request)`, `try_convert_message(request)`
- `create_converter({"adapters": ...})`, `create_adapter(...)`
- `validate_frame(frame)`, `assert_protocol(value)`, `is_protocol(value)`
- `FieldbridgeError` with stable `code`, `protocol`, `field`, and `cause`
- `adapters`, `supported_protocols`, `envelope_fields`

Payload bytes are preserved; protocol semantics are not guessed. Conversion
warnings describe mappings, overrides, and dropped envelope fields. Error
codes and warning text match the TypeScript implementation.

See the [fieldbridge README](https://github.com/MAbdelhamid-Admin/fieldBridge#readme)
for the full behaviour reference (device IDs, conflict rules, per-protocol
limits, and wire-format mapping).

## Wire

```python
from fieldbridge.wire import parse, serialize

frames = parse("modbus-rtu", bytes.fromhex("11 03 00 6B 00 03 76 87"))
frame = frames[0]
print(frame.address, frame.payload)

rtu = serialize(frame)
```

Supported: Modbus TCP/RTU, SocketCAN/candump, Ethernet, PROFINET RT,
and EtherCAT. Generic `parse` and `serialize` dispatch LIN, FlexRay, PROFIBUS,
and unsupported formats consistently with `UNSUPPORTED_FEATURE`.

`parse` always returns a list, because one Modbus TCP buffer can hold several
ADUs and one EtherCAT frame several datagrams. `serialize` returns `bytes`.

## Development

```bash
python -m pip install -e . pytest
python -m pytest
```

### Cross-language parity test

`tests/test_cross_language_parity.py` runs the TypeScript implementation and
compares its output with the Python port. It needs a checkout of the
[TypeScript project](https://github.com/MAbdelhamid-Admin/fieldBridge) with
dependencies installed, next to this repository (or pointed to by the
`FIELD_BRIDGE_TS` environment variable). When that checkout is absent the test
is skipped, so the normal suite works from a standalone clone.

The bundled parity test covers a representative set; the port was additionally
checked against the original with 194 targeted and 680 randomised differential
cases (frame conversions, messages, error paths, and wire parse/serialize
round-trips) with identical results.

## License

[MIT](LICENSE)
