# PyfieldBridge

[![CI](https://github.com/MAbdelhamid-Admin/PyfieldBridge/actions/workflows/ci.yml/badge.svg)](https://github.com/MAbdelhamid-Admin/PyfieldBridge/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-online-blue.svg)](https://mabdelhamid-admin.github.io/PyfieldBridge/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Validated conversion of **frame envelopes** between industrial and automotive
protocols in Python: Ethernet, PROFINET, PROFIBUS DP/PA, Modbus RTU/TCP,
CAN / CAN FD, LIN, FlexRay and EtherCAT.

- Strict validation against each protocol's limits on both encode and decode
- Payload bytes are preserved exactly; nothing is silently guessed
- Device IDs bridge message-addressed buses (CAN, LIN) and device-addressed
  buses (Modbus, PROFIBUS, EtherCAT)
- Parse and serialize real wire bytes: Modbus TCP/RTU, SocketCAN and candump,
  Ethernet, PROFINET RT, EtherCAT
- Typed `FieldbridgeError` exceptions with stable codes, plus a non-throwing
  `try_*` API
- No runtime dependencies; Python 3.10+

Using Node.js or TypeScript? See the [`fieldbridge`](https://github.com/MAbdelhamid-Admin/fieldBridge)
package for the same protocol model on that platform.

**Documentation:** https://mabdelhamid-admin.github.io/PyfieldBridge/

## Install

From PyPI:

```bash
python -m pip install pyfieldbridge
```

From a checkout:

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

result.message
# {'protocol': 'modbus-rtu', 'address': 17, 'device_id': 17, 'payload': [3, 0, 10]}
result.warnings
# explains what was inferred, overridden or dropped
```

Every conversion returns `warnings` describing anything that was inferred,
overridden or dropped. Log them; they are how you learn what changed.

## Scope and limitations

PyfieldBridge converts the **envelope** (addresses, identifiers, payload
limits, metadata) and preserves payload bytes. It does **not** perform
semantic, bit-level translation: process images, device profiles, cycle
timing, safety semantics, endianness and vendor-specific mappings cannot be
inferred safely from an arbitrary frame. Applications that know those details
can use a `signals` mapping or supply their own adapter.

## API

### `convert_frame({ source, target_protocol, options? })`

Converts a single frame.

```python
from fieldbridge import convert_frame

result = convert_frame({
    "source": {"protocol": "ethernet", "payload": [1], "signals": {"speed": 42}},
    "target_protocol": "ethercat",
    "options": {
        "mapping": {"speed": "velocity"},  # rename/select signals; unlisted ones are dropped
        "metadata": {"cycle": "1ms"},      # metadata for the target frame
        "target_device_id": 3,             # target device if the frame has no address
    },
})

result.frame
result.warnings
```

### `convert_message({ source, target, options? })`

Converts a message that comes with a device identity and context.

```python
from fieldbridge import convert_message

convert_message({
    "source": {
        "device_id": "gateway-1",
        "context": {"line": "A"},
        "message": {"protocol": "can", "identifier": 0x12, "payload": [1, 2]},
    },
    "target": {
        "protocol": "lin",
        "context": {"schedule": "body-controller-10ms"},
    },
})
```

- `source.device_id` identifies the source device.
- `source.context` holds extra facts about the source, used as defaults for the
  message metadata.
- `target.device_id` is the device to address on the target bus.
- `target.context` holds target-specific fields (schedule, slot, profile…). If
  an adapter declares required context keys, they must appear here; a missing
  key fails the conversion instead of being guessed.

### Non-throwing API

```python
from fieldbridge import try_convert_message

result = try_convert_message(request)
if result.ok:
    send(result.value.message)
else:
    print(result.error.code, result.error)  # e.g. "INVALID_DEVICE_ID"
```

The `try_*` functions never raise. Errors raised inside a custom adapter are
wrapped with code `INTERNAL`, and the original exception is kept in `cause`.

### Errors

The throwing functions only raise `FieldbridgeError`, which has a stable `code`
and, where relevant, `protocol` and `field`. Branch on `code`, not on the
message text.

| Code | Meaning |
| --- | --- |
| `UNSUPPORTED_PROTOCOL` | Unknown protocol name |
| `INVALID_FRAME` | Input is not a valid frame/request object |
| `PROTOCOL_MISMATCH` | Frame given to the adapter of a different protocol |
| `INVALID_PAYLOAD` | Non-byte values or a protocol length rule violated |
| `PAYLOAD_TOO_LARGE` | Payload exceeds the protocol maximum |
| `MISSING_FIELD` | A required field (e.g. CAN identifier, Modbus address) is absent |
| `INVALID_FIELD` | A field is out of range |
| `MISSING_CONTEXT` | A required target context key is absent |
| `INVALID_DEVICE_ID` | A device ID cannot be used as a bus address |
| `CHECKSUM_MISMATCH` | A wire frame's checksum (Modbus RTU CRC) is wrong |
| `UNSUPPORTED_FEATURE` | Valid input that PyfieldBridge doesn't support yet (e.g. CAN error frames) |
| `INTERNAL` | Error raised by a custom adapter (`try_*` API only) |

### Custom adapters

The built-in `adapters` registry is frozen. To add or replace adapters, create
your own converter; nothing global is modified.

```python
from fieldbridge import create_adapter, create_converter

converter = create_converter({
    "adapters": {
        "ethercat": create_adapter({
            "protocol": "ethercat",
            "max_payload": 1486,
            "fields": ["address"],
            "uses_device_address": True,
            "required_context": ["profile"],
            "validate": lambda frame: None,  # raise FieldbridgeError on violations
        }),
    },
})

converter.convert_message(request)
converter.try_convert_frame(request)
```

## Wire formats

The main API works on parsed frames. The `fieldbridge.wire` module turns raw
bytes into those frames and back. Parsing checks lengths, checksums, header
fields, and the protocol rules enforced by the adapters.

```python
from fieldbridge import convert_frame
from fieldbridge.wire import parse, serialize

# Modbus RTU -> Modbus TCP gateway
[rtu] = parse("modbus-rtu", rtu_bytes)  # CRC is verified
result = convert_frame({
    "source": rtu,
    "target_protocol": "modbus-tcp",
    "options": {"metadata": {"transactionId": 1}},
})
socket.send(serialize(result.frame))    # MBAP header is built for you
```

`parse(protocol, bytes)` always returns a **list** of frames, because one
Modbus TCP buffer can hold several ADUs and one EtherCAT frame several
datagrams. `serialize(frame)` returns `bytes`.

| Protocol | Functions | Format | Frame mapping |
| --- | --- | --- | --- |
| Modbus TCP | `parse_modbus_tcp`, `parse_modbus_tcp_stream`, `serialize_modbus_tcp` | MBAP header + PDU | `address` = unit id, `payload` = PDU, `metadata.transactionId` |
| Modbus RTU | `parse_modbus_rtu`, `serialize_modbus_rtu`, `crc16_modbus` | address + PDU + CRC-16 | `address` = slave, `payload` = PDU |
| CAN / CAN FD | `parse_socket_can`, `serialize_socket_can` | Linux `struct can_frame` (16 B) / `canfd_frame` (72 B) | `identifier`, `metadata.extended / fd / brs / esi / rtr` |
| CAN / CAN FD | `parse_candump_line`, `format_candump_line` | can-utils `candump` text: log format (`123#DEADBEEF`) and default display format (`can0 123 [4] DE AD BE EF`) | as above, plus `metadata.timestamp / interface` |
| Ethernet | `parse_ethernet`, `serialize_ethernet` | Ethernet II / 802.3, optional 802.1Q | MACs in `destination_address` / `source_address`, `identifier` = EtherType, `metadata.vlanId / vlanPriority` |
| PROFINET RT | `parse_profinet`, `serialize_profinet` | EtherType 0x8892 | `identifier` = FrameID, `payload` = IO data + APDU status |
| EtherCAT | `parse_ethercat`, `serialize_ethercat` | EtherType 0x88A4, one frame per datagram | `metadata.command / index / offset / workingCounter`; `address` for configured (FPxx) commands, `metadata.position` for auto-increment, `metadata.adp` for broadcast, `metadata.logicalAddress` for logical commands |

`parse_ethernet_auto(bytes)` detects PROFINET and EtherCAT from the EtherType.
For a TCP connection, feed each chunk to `parse_modbus_tcp_stream`, which
returns the complete ADUs plus a `rest` to prepend to the next chunk.

Notes:

- Ethernet frames are read and written **without the FCS**, which is how most
  capture tools deliver them. Serialized frames are zero-padded to 60 bytes.
- Modbus RTU parsing expects **one complete frame**. Splitting a raw serial
  stream (by inter-frame silence) is up to your transport layer.
- LIN, FlexRay and PROFIBUS wire formats depend on the interface hardware and
  are not implemented yet. For those protocols `parse` / `serialize` raise
  `UNSUPPORTED_FEATURE`. `wire_protocols` lists the supported ones.

## Conversion rules

### Device IDs and bus addresses

Some buses address *devices* (Modbus slave/unit id, PROFIBUS station,
EtherCAT station). Others only address *messages* (CAN, LIN, FlexRay
identifiers). `device_id` connects the two:

- **To a device-addressed bus**, the target `address` is the first available
  of:
  1. the `address` in the message
  2. `target.device_id` (or `options.target_device_id`)
  3. the source `device_id`

  A numeric `device_id`, or a string like `"17"` or `"0x11"`, is used as the
  address. A name such as `"gateway-1"` is rejected with `INVALID_DEVICE_ID`
  instead of being guessed. The result is then checked against the target's
  address range.
- **From a device-addressed bus**, the source `address` becomes the result's
  `device_id` when none was given.

### Conflicts: the message wins

When the message and the surrounding request disagree, **the value in the
message is used**, and a warning is added:

| Conflict | Used |
| --- | --- |
| `message.address` vs `target.device_id` | `message.address` |
| `message.device_id` vs `source.device_id` | `message.device_id` |
| `message.metadata` vs `source.context` | `message.metadata` |

`target.context` and `options.metadata` are instructions for the target, not
facts about the source, so they set the target frame's metadata. Any message
value they override is also reported in the warnings.

### Envelope fields

Each protocol declares which envelope fields it uses. A field the target
protocol doesn't use is dropped from the result and listed in the warnings.
For example, a CAN `identifier` has no meaning on Modbus.

| Protocol | Fields used | Payload limit | Other rules |
| --- | --- | --- | --- |
| Ethernet | `source_address`, `destination_address` (MAC), `identifier` (EtherType) | 1500 bytes | MAC ≤ 48 bits, EtherType ≤ 0xFFFF |
| PROFINET | `source_address`, `destination_address` (MAC), `identifier` (FrameID) | 1498 bytes (cyclic IO data 40..1440 + status) | FrameID ≤ 0xFFFF |
| PROFIBUS DP / PA | `address` (destination station), `source_address` | 244 bytes | station addresses 0..127 |
| Modbus RTU | `address` | 253-byte PDU | address 0..247 required, valid function code |
| Modbus TCP | `address` (unit id) | 253-byte PDU | unit id 0..255 required, valid function code |
| CAN | `identifier` | 8 bytes classic; CAN FD DLC lengths up to 64 | identifier required; `metadata.extended` / `metadata.fd` flags, inferred when unambiguous |
| LIN | `identifier` | 1..8 bytes | 6-bit identifier required |
| FlexRay | `identifier` (slot) | 0..254 bytes, even length | slot 1..2047 required |
| EtherCAT | `address` (station) | 1486 bytes | station address ≤ 0xFFFF |

For Modbus, `payload` is the PDU (function code followed by data). The address
byte, MBAP header and CRC are not part of it.

## Development

```bash
python -m pip install -e . pytest
python -m pytest
```

Build the documentation site locally:

```bash
python -m pip install -e . "pdoc>=15"
pdoc -o site fieldbridge fieldbridge.wire pyfieldbridge pyfieldbridge.wire
```

Project layout:

```
fieldbridge/
  __init__.py         public API
  core/               types, errors, validation, conversion engine, result helpers
  adapters/           one adapter per protocol + shared rule helpers
  wire/               byte-level parse/serialize
    index.py          generic parse()/serialize() + re-exports
    bytes.py          shared byte helpers
    modbus.py         Modbus TCP / RTU
    can.py            SocketCAN binary, candump text
    ethernet.py       Ethernet, PROFINET RT, EtherCAT
pyfieldbridge/        compatibility package name
tests/                conversion, wire and differential tests
```

## License

[MIT](LICENSE)
