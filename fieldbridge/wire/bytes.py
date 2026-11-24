from collections.abc import Iterable
from ..core.errors import FieldbridgeError


def to_bytes(input, protocol):
    if isinstance(input, bytes):
        return input
    if isinstance(input, (bytearray, memoryview)):
        input = bytes(input)
        # Validate values in bytes conversion as bytes are guaranteed 0..255.
        return input
    if input is None or not isinstance(input, (list, tuple)):
        raise FieldbridgeError("INVALID_FRAME",
                               f"{protocol} wire input must be a Uint8Array or byte array",
                               protocol=protocol)
    out = bytearray()
    for index, byte in enumerate(input):
        if isinstance(byte, bool) or not isinstance(byte, int) or byte < 0 or byte > 255:
            raise FieldbridgeError("INVALID_PAYLOAD",
                                   f"{protocol} wire input byte {index} is not 0..255",
                                   protocol=protocol)
        out.append(byte)
    return bytes(out)


def truncated(protocol, what, need, got):
    return FieldbridgeError("INVALID_FRAME",
                            f"{protocol} frame truncated: {what} needs {need} bytes, got {got}",
                            protocol=protocol)


def expect_protocol(frame, protocol):
    if frame is None or not hasattr(frame, "get"):
        raise FieldbridgeError("INVALID_FRAME", "frame must be an object", protocol=protocol)
    if frame.get("protocol") != protocol:
        raise FieldbridgeError("PROTOCOL_MISMATCH",
                               f"Cannot serialize a {frame.get('protocol')} frame as {protocol}",
                               protocol=protocol)


def meta_int(frame, key, minimum, maximum, fallback=None):
    metadata = frame.get("metadata") or {}
    value = metadata.get(key)
    aliases = {
        "transactionId": "transaction_id",
        "transaction_id": "transactionId",
        "rtrLength": "rtr_length",
        "rtr_length": "rtrLength",
        "ethernetDestination": "ethernet_destination",
        "ethernetSource": "ethernet_source",
        "workingCounter": "working_counter",
        "working_counter": "workingCounter",
        "logicalAddress": "logical_address",
        "logical_address": "logicalAddress",
        "vlanId": "vlan_id",
        "vlan_id": "vlanId",
        "vlanPriority": "vlan_priority",
        "vlan_priority": "vlanPriority",
    }
    if value is None:
        value = metadata.get(aliases.get(key, key))
    if value is None:
        return fallback
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise FieldbridgeError("INVALID_FIELD",
                               f"{frame['protocol']} metadata.{key} must be an integer {minimum}..{maximum}",
                               protocol=frame["protocol"], field=f"metadata.{key}")
    return value


def require_value(value, protocol, field, hint):
    if value is None:
        raise FieldbridgeError("MISSING_FIELD",
                               f"{protocol} serialization requires {hint}",
                               protocol=protocol, field=field)
    return value


def read_mac(data, offset):
    value = 0
    for index in range(6):
        value = value * 256 + data[offset + index]
    return value


def write_mac(out, offset, mac):
    rest = mac
    for index in range(5, -1, -1):
        out[offset + index] = rest & 0xff
        rest >>= 8


# Camel-case compatibility aliases
toBytes = to_bytes
expectProtocol = expect_protocol
metaInt = meta_int
requireValue = require_value
readMac = read_mac
writeMac = write_mac
