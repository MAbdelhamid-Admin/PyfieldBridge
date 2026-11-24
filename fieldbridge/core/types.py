from dataclasses import dataclass
from typing import Any, Literal, Mapping

Protocol = Literal[
    "ethernet", "profinet", "profibus-pa", "profibus-dp",
    "modbus-tcp", "modbus-rtu", "can", "lin", "flexray", "ethercat",
]

protocols = [
    "ethernet", "profinet", "profibus-pa", "profibus-dp",
    "modbus-tcp", "modbus-rtu", "can", "lin", "flexray", "ethercat",
]
supported_protocols = protocols
envelope_fields = ["address", "source_address", "destination_address", "identifier"]

# Compatibility aliases for code using the original wire names.
envelopeFields = envelope_fields

CAMEL_ALIASES = {
    "deviceId": "device_id",
    "sourceAddress": "source_address",
    "destinationAddress": "destination_address",
    "targetProtocol": "target_protocol",
    "targetDeviceId": "target_device_id",
    "requiredContext": "required_context",
    "maxPayload": "max_payload",
    "usesDeviceAddress": "uses_device_address",
    "rtrLength": "rtr_length",
    "transactionId": "transaction_id",
    "ethernetDestination": "ethernet_destination",
    "ethernetSource": "ethernet_source",
    "workingCounter": "working_counter",
    "logicalAddress": "logical_address",
    "vlanId": "vlan_id",
    "vlanPriority": "vlan_priority",
}


def key_variants(key):
    variants = [key]
    snake = CAMEL_ALIASES.get(key)
    if snake and snake not in variants:
        variants.append(snake)
    for camel, candidate in CAMEL_ALIASES.items():
        if candidate == key and camel not in variants:
            variants.append(camel)
    return variants


class AttrDict(dict):
    """A dict with attribute access and camel-case compatibility."""

    def __getattr__(self, name):
        for key in key_variants(name):
            if dict.__contains__(self, key):
                value = dict.__getitem__(self, key)
                if isinstance(value, dict) and not isinstance(value, AttrDict):
                    value = AttrDict(value)
                    dict.__setitem__(self, key, value)
                return value
        raise AttributeError(name)

    def __setattr__(self, name, value):
        key = CAMEL_ALIASES.get(name, name)
        self[key] = value

    def __getitem__(self, key):
        for variant in key_variants(key):
            if dict.__contains__(self, variant):
                value = dict.__getitem__(self, variant)
                if isinstance(value, dict) and not isinstance(value, AttrDict):
                    value = AttrDict(value)
                    dict.__setitem__(self, variant, value)
                return value
        raise KeyError(key)

    def get(self, key, default=None):
        for variant in key_variants(key):
            if dict.__contains__(self, variant):
                value = dict.__getitem__(self, variant)
                if isinstance(value, dict) and not isinstance(value, AttrDict):
                    value = AttrDict(value)
                    dict.__setitem__(self, variant, value)
                return value
        return default

    def __contains__(self, key):
        return any(dict.__contains__(self, variant) for variant in key_variants(key))

    def __eq__(self, other):
        if isinstance(other, Mapping):
            try:
                return dict_normalized(self) == dict_normalized(other)
            except Exception:
                pass
        return super().__eq__(other)


@dataclass
class NormalizedFrame:
    protocol: str
    payload: list[int]
    device_id: str | int | float | None = None
    address: int | None = None
    source_address: int | None = None
    destination_address: int | None = None
    identifier: int | None = None
    metadata: dict[str, str | int | float | bool] | None = None
    signals: dict[str, int | float | bool] | None = None


ProtocolFrame = NormalizedFrame


@dataclass
class ProtocolAdapter:
    protocol: str
    required_context: tuple[str, ...]
    fields: tuple[str, ...]
    uses_device_address: bool
    decode: Any
    encode: Any


@dataclass
class ConversionResult(AttrDict):
    frame: dict
    warnings: list[str]

    def __init__(self, frame, warnings):
        dict.__init__(self, frame=frame, warnings=warnings)
        self.frame = frame
        self.warnings = warnings


@dataclass
class MessageConversionResult(AttrDict):
    message: dict
    warnings: list[str]
    device_id: str | int | float | None = None

    def __init__(self, message, warnings, device_id=None):
        values = {"message": message, "warnings": warnings}
        if device_id is not None:
            values["device_id"] = device_id
        dict.__init__(self, values)
        self.message = message
        self.warnings = warnings
        if device_id is not None:
            self.device_id = device_id


class Result(AttrDict):
    pass


def normalize_keys(mapping: Mapping[str, Any]) -> dict:
    result = {}
    for key, value in mapping.items():
        result[CAMEL_ALIASES.get(key, key)] = value
    return result


def dict_normalized(value: Mapping[str, Any]) -> dict:
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import asdict
        value = asdict(value)
    return normalize_keys(value)


def frame_dict(frame: Any, protocol: str | None = None) -> dict:
    if frame is None:
        raise TypeError("frame must be an object")
    if hasattr(frame, "__dataclass_fields__"):
        from dataclasses import asdict
        raw = asdict(frame)
    elif isinstance(frame, Mapping):
        raw = dict(frame)
    elif hasattr(frame, "__dict__"):
        raw = vars(frame).copy()
    else:
        raise TypeError("frame must be an object")
    result = normalize_keys(raw)
    if protocol is not None:
        result["protocol"] = protocol
    return result
