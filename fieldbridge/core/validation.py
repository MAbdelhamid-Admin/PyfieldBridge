import math
from collections.abc import Mapping

from .errors import FieldbridgeError, field_name
from .types import protocols, envelope_fields, CAMEL_ALIASES


def _plain_object(value):
    return isinstance(value, Mapping) or hasattr(value, "__dict__") or hasattr(value, "__dataclass_fields__")


def _normalized(value):
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import asdict
        raw = asdict(value)
    elif isinstance(value, Mapping):
        raw = dict(value)
    elif hasattr(value, "__dict__"):
        raw = vars(value).copy()
    else:
        return None
    return {CAMEL_ALIASES.get(k, k): v for k, v in raw.items()}


def is_protocol(value):
    return isinstance(value, str) and value in protocols


def assert_protocol(value):
    if not is_protocol(value):
        raise FieldbridgeError("UNSUPPORTED_PROTOCOL", f"Unsupported protocol: {value}")


def validate_frame(frame):
    raw = _normalized(frame)
    if raw is None:
        raise FieldbridgeError("INVALID_FRAME", "frame must be an object")
    protocol = raw.get("protocol")
    assert_protocol(protocol)

    payload = raw.get("payload")
    if not isinstance(payload, (list, tuple, bytearray, bytes)):
        raise FieldbridgeError("INVALID_PAYLOAD",
                               "payload must contain only bytes in the range 0..255",
                               protocol=protocol, field="payload")
    for byte in payload:
        if isinstance(byte, bool) or not isinstance(byte, int) or byte < 0 or byte > 255:
            raise FieldbridgeError("INVALID_PAYLOAD",
                                   "payload must contain only bytes in the range 0..255",
                                   protocol=protocol, field="payload")

    for field in envelope_fields:
        value = raw.get(field)
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int) or not math.isfinite(value) or value < 0:
                raise FieldbridgeError("INVALID_FIELD",
                                       f"{field_name(field)} must be a non-negative integer",
                                       protocol=protocol, field=field)

    device_id = raw.get("device_id")
    if device_id is not None:
        if isinstance(device_id, str):
            pass
        elif isinstance(device_id, bool) or not isinstance(device_id, (int, float)) or not math.isfinite(device_id):
            raise FieldbridgeError("INVALID_FIELD",
                                   "deviceId must be a string or finite number",
                                   protocol=protocol, field="device_id")

    metadata = raw.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, Mapping):
            raise FieldbridgeError("INVALID_FIELD", "metadata must be an object",
                                   protocol=protocol, field="metadata")
        for key, value in metadata.items():
            if not isinstance(value, (str, int, float, bool)):
                raise FieldbridgeError("INVALID_FIELD",
                                       f'metadata "{key}" must be a string, number or boolean',
                                       protocol=protocol, field="metadata")
            if isinstance(value, float) and not math.isfinite(value):
                raise FieldbridgeError("INVALID_FIELD",
                                       f'metadata "{key}" must be a string, number or boolean',
                                       protocol=protocol, field="metadata")

    signals = raw.get("signals")
    if signals is not None:
        if not isinstance(signals, Mapping):
            raise FieldbridgeError("INVALID_FIELD", "signals must be an object",
                                   protocol=protocol, field="signals")
        for name, value in signals.items():
            if isinstance(value, bool):
                continue
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise FieldbridgeError("INVALID_FIELD",
                                       f'signal "{name}" must be a finite number or boolean',
                                       protocol=protocol, field="signals")


validateFrame = validate_frame
assertProtocol = assert_protocol
isProtocol = is_protocol
