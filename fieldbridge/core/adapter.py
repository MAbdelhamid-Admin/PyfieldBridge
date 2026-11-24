from collections.abc import Mapping

from .errors import FieldbridgeError
from .types import envelope_fields, frame_dict, ProtocolAdapter
from .validation import assert_protocol, validate_frame


class AdapterDefinition(dict):
    pass


def create_adapter(definition):
    if isinstance(definition, Mapping):
        values = dict(definition)
    elif hasattr(definition, "__dict__"):
        values = vars(definition).copy()
    else:
        raise FieldbridgeError("INVALID_FRAME", "adapter definition must be an object")
    if "requiredContext" in values:
        values["required_context"] = values.pop("requiredContext")
    if "usesDeviceAddress" in values:
        values["uses_device_address"] = values.pop("usesDeviceAddress")
    if "maxPayload" in values:
        values["max_payload"] = values.pop("maxPayload")

    protocol = values.get("protocol")
    assert_protocol(protocol)
    max_payload = values.get("max_payload")
    validate = values.get("validate")
    required_context = tuple(values.get("required_context", ()) or ())
    fields = tuple(values.get("fields", envelope_fields))
    uses_device_address = bool(values.get("uses_device_address", False))

    def check(frame):
        if max_payload is not None and len(frame["payload"]) > max_payload:
            raise FieldbridgeError("PAYLOAD_TOO_LARGE",
                                   f"{protocol} payload exceeds {max_payload} bytes",
                                   protocol=protocol, field="payload")
        if validate is not None:
            validate(frame)

    def clone_frame(frame, output_protocol):
        copied = dict(frame)
        copied["protocol"] = output_protocol
        copied["payload"] = list(copied.get("payload", []))
        if copied.get("metadata") is not None:
            copied["metadata"] = dict(copied["metadata"])
        if copied.get("signals") is not None:
            copied["signals"] = dict(copied["signals"])
        return copied

    def decode(frame):
        validate_frame(frame)
        raw = frame_dict(frame)
        if raw.get("protocol") != protocol:
            raise FieldbridgeError("PROTOCOL_MISMATCH",
                                   f"Expected {protocol} frame, got {raw.get('protocol')}",
                                   protocol=protocol)
        decoded = clone_frame(raw, protocol)
        check(decoded)
        return decoded

    def encode(frame):
        validate_frame(frame)
        raw = frame_dict(frame)
        encoded = clone_frame(raw, protocol)
        check(encoded)
        for field in required_context:
            metadata = encoded.get("metadata") or {}
            if metadata.get(field) is None:
                raise FieldbridgeError("MISSING_CONTEXT",
                                       f'{protocol} requires context field "{field}"',
                                       protocol=protocol, field=field)
        return encoded

    return ProtocolAdapter(protocol, required_context, fields, uses_device_address, decode, encode)


createAdapter = create_adapter
