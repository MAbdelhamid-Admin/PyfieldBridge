"""
Raw-byte parsing and serialization.

This module turns wire bytes into frames and frames back into bytes. Parsing
checks lengths, checksums, header fields, and the protocol rules enforced by
the adapters.

```python
from fieldbridge.wire import parse, serialize

[rtu] = parse("modbus-rtu", bytes.fromhex("11 03 00 6B 00 03 76 87"))
print(rtu.address, rtu.payload)

wire = serialize(rtu)
```

`parse(protocol, data)` always returns a list of frames, because one Modbus
TCP buffer can hold several ADUs and one EtherCAT frame several datagrams.
`serialize(frame)` returns `bytes`.

Supported wire formats:

- Modbus TCP (MBAP ADU) and Modbus RTU (ADU with CRC-16)
- CAN / CAN FD (Linux SocketCAN structs and candump text)
- Ethernet II / 802.3 with optional 802.1Q
- PROFINET RT
- EtherCAT

LIN, FlexRay and PROFIBUS wire formats depend on the interface hardware and
are not implemented yet; `parse` and `serialize` raise `FieldbridgeError`
with code `UNSUPPORTED_FEATURE` for those protocols.
"""
from .index import *  # noqa: F401,F403
