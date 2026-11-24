from collections.abc import Mapping
from dataclasses import is_dataclass, asdict
import math
import json

from ..adapters.index import adapters as built_in_adapters
from .errors import FieldbridgeError, field_name
from .result import to_result
from .types import (
    protocols, envelope_fields, frame_dict, CAMEL_ALIASES,
    AttrDict, ConversionResult, MessageConversionResult,
)
from .validation import assert_protocol, validate_frame


def _pick(mapping, snake, camel=None):
    if mapping is None:
        return None
    if snake in mapping:
        return mapping[snake]
    if camel and camel in mapping:
        return mapping[camel]
    return None


def _js_string(value):
    """Render a value the way JavaScript's String() does, for warning parity."""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return str(int(value))
    return str(value)


def _js_json(value):
    """Render a value the way JSON.stringify() does, for warning parity."""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return json.dumps(value) if math.isfinite(value) else "null"
    return json.dumps(value)


def _object_dict(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "__dict__"):
        return vars(value).copy()
    return None


def _normalized_request(value):
    raw = _object_dict(value)
    if raw is None:
        return None
    return {CAMEL_ALIASES.get(k, k): v for k, v in raw.items()}


def parse_device_address(device_id):
    if isinstance(device_id, bool):
        return None
    if isinstance(device_id, int):
        value = device_id
    elif isinstance(device_id, float):
        if not math.isfinite(device_id) or not device_id.is_integer():
            return None
        value = int(device_id)
    elif isinstance(device_id, str):
        if device_id.isdigit():
            value = int(device_id)
        elif len(device_id) >= 3 and device_id[:2].lower() == "0x":
            try:
                value = int(device_id, 16)
            except ValueError:
                return None
        else:
            return None
    else:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, int) and value >= 0 and value <= 2 ** 53 - 1:
        return value
    return None


def to_device_address(protocol, device_id):
    address = parse_device_address(device_id)
    if address is None:
        raise FieldbridgeError(
            "INVALID_DEVICE_ID",
            f'{protocol} addresses devices by number; deviceId "{_js_string(device_id)}" cannot be used as an address. '
            "Pass a numeric target deviceId or set message.address.",
            protocol=protocol, field="device_id",
        )
    return address


def map_signals(signals, mapping, warnings):
    mapped = {}
    for source, target in mapping.items():
        value = signals.get(source) if signals is not None else None
        if value is None:
            warnings.append(f'Mapped signal "{source}" is not present in the source frame.')
        else:
            mapped[target] = value
    return mapped


class ProtocolConverter:
    def __init__(self, options=None):
        override = (options or {}).get("adapters", {}) if isinstance(options, Mapping) else {}
        registry = dict(built_in_adapters)
        for protocol, adapter in override.items():
            assert_protocol(protocol)
            if adapter is None:
                continue
            if isinstance(adapter, Mapping):
                values = dict(adapter)
                adapter_protocol = values.get("protocol")
                if adapter_protocol != protocol:
                    raise FieldbridgeError("PROTOCOL_MISMATCH",
                                           f'Adapter for "{protocol}" reports protocol "{adapter_protocol}"',
                                           protocol=protocol)
                # Dict custom adapter: use already-supplied methods or create adapter
                if callable(values.get("decode")) and callable(values.get("encode")):
                    registry[protocol] = type("Adapter", (), {})()
                    obj = registry[protocol]
                    obj.protocol = protocol
                    obj.required_context = tuple(values.get("required_context", values.get("requiredContext", ()) or ()))
                    obj.fields = tuple(values.get("fields", envelope_fields))
                    obj.uses_device_address = bool(values.get("uses_device_address", values.get("usesDeviceAddress", False)))
                    obj.decode = values["decode"]
                    obj.encode = values["encode"]
                else:
                    from .adapter import create_adapter
                    registry[protocol] = create_adapter(values)
            else:
                adapter_protocol = getattr(adapter, "protocol", None)
                if adapter_protocol != protocol:
                    raise FieldbridgeError("PROTOCOL_MISMATCH",
                                           f'Adapter for "{protocol}" reports protocol "{adapter_protocol}"',
                                           protocol=protocol)
                registry[protocol] = adapter
        self.adapters = FrozenRegistry(registry)

    def convert_frame(self, input):
        raw = _normalized_request(input)
        if raw is None:
            raise FieldbridgeError("INVALID_FRAME", "conversion request must be an object")
        source = raw.get("source")
        target_protocol = raw.get("target_protocol", raw.get("targetProtocol"))
        options = raw.get("options") or {}
        if source is None:
            raise FieldbridgeError("INVALID_FRAME", "frame must be an object")
        source_raw = frame_dict(source)
        validate_frame(source_raw)
        assert_protocol(target_protocol)
        source_adapter = self.adapters[source_raw["protocol"]]
        target_adapter = self.adapters[target_protocol]
        if isinstance(options, Mapping):
            options = dict(options)
            options = {CAMEL_ALIASES.get(k, k): v for k, v in options.items()}
        else:
            options = {}
        warnings = ["Payload bytes were preserved; no protocol-specific semantic mapping was inferred."]

        normalized = source_adapter.decode(source_raw)

        device_id = normalized.get("device_id")
        if device_id is None and source_adapter.uses_device_address:
            device_id = normalized.get("address")

        signals = normalized.get("signals")
        if options.get("mapping") is not None:
            signals = map_signals(normalized.get("signals"), options["mapping"], warnings)
        else:
            warnings.append("Provide an explicit signal mapping when process-image conversion is required.")

        metadata = dict(normalized.get("metadata") or {})
        for key, value in (options.get("metadata") or {}).items():
            if key in metadata and metadata[key] != value:
                warnings.append(
                    f'metadata "{key}": message value {_js_json(metadata[key])} '
                    f'replaced by target value {_js_json(value)}.'
                )
            metadata[key] = value

        address = None
        target_device = options.get("target_device_id")
        if target_adapter.uses_device_address:
            if normalized.get("address") is not None:
                address = normalized["address"]
                if target_device is not None and parse_device_address(target_device) != address:
                    warnings.append(
                        f'Target deviceId "{_js_string(target_device)}" ignored; the message address {address} takes priority.'
                    )
            elif target_device is not None:
                address = to_device_address(target_protocol, target_device)
            elif device_id is not None:
                address = to_device_address(target_protocol, device_id)
                warnings.append(f"{target_protocol} address {address} was taken from deviceId.")
        elif target_device is not None:
            warnings.append(
                f'Target deviceId "{_js_string(target_device)}" ignored; {target_protocol} does not address devices.'
            )

        target = {"protocol": target_protocol, "payload": list(normalized["payload"])}
        if device_id is not None:
            target["device_id"] = device_id

        dropped = []
        for field in envelope_fields:
            value = address if field == "address" and address is not None else normalized.get(field)
            if value is None:
                continue
            if field in target_adapter.fields:
                target[field] = value
            else:
                if not (field == "address" and source_adapter.uses_device_address):
                    dropped.append(f"{field_name(field)}={value}")
        if dropped:
            warnings.append(f"Dropped fields not used by {target_protocol}: {', '.join(dropped)}.")
        if metadata:
            target["metadata"] = metadata
        if signals is not None:
            target["signals"] = signals

        encoded = target_adapter.encode(target)
        encoded_attr = AttrDict(encoded)
        return AttrDict(frame=encoded_attr, warnings=warnings)

    def convert_message(self, input):
        raw = _normalized_request(input)
        if raw is None:
            raise FieldbridgeError("INVALID_FRAME", "conversion request must have source and target objects")
        source = raw.get("source")
        target = raw.get("target")
        if not isinstance(source, (Mapping,)) and not hasattr(source, "__dict__") and not is_dataclass(source):
            raise FieldbridgeError("INVALID_FRAME", "conversion request must have source and target objects")
        if not isinstance(target, (Mapping,)) and not hasattr(target, "__dict__") and not is_dataclass(target):
            raise FieldbridgeError("INVALID_FRAME", "conversion request must have source and target objects")
        source_raw = _normalized_request(source)
        target_raw = _normalized_request(target)
        if source_raw is None or target_raw is None:
            raise FieldbridgeError("INVALID_FRAME", "conversion request must have source and target objects")
        message = source_raw.get("message")
        validate_frame(message)
        target_protocol = target_raw.get("protocol")
        assert_protocol(target_protocol)

        target_adapter = self.adapters[target_protocol]
        for field in target_adapter.required_context:
            target_context = target_raw.get("context") or {}
            if target_context.get(field) is None:
                raise FieldbridgeError("MISSING_CONTEXT",
                                       f'{target_protocol} requires target context field "{field}"',
                                       protocol=target_protocol, field=field)

        warnings = []
        device_id = source_raw.get("device_id")
        message_raw = frame_dict(message)
        if message_raw.get("device_id") is not None:
            if device_id is not None and _js_string(device_id) != _js_string(message_raw["device_id"]):
                warnings.append(
                    f'source.deviceId "{_js_string(device_id)}" ignored; the message deviceId '
                    f'"{_js_string(message_raw["device_id"])}" takes priority.'
                )
            device_id = message_raw["device_id"]

        source_metadata = dict(source_raw.get("context") or {})
        for key, value in (message_raw.get("metadata") or {}).items():
            if key in source_metadata and source_metadata[key] != value:
                warnings.append(
                    f'source.context "{key}" ignored; the message value {_js_json(value)} takes priority.'
                )
            source_metadata[key] = value

        source_frame = dict(message_raw)
        if device_id is not None:
            source_frame["device_id"] = device_id
        if source_metadata:
            source_frame["metadata"] = source_metadata

        options_raw = raw.get("options") or {}
        if not isinstance(options_raw, Mapping):
            options_raw = {}
        options_out = {CAMEL_ALIASES.get(k, k): v for k, v in dict(options_raw).items()}
        target_metadata = {}
        target_metadata.update(options_out.get("metadata") or {})
        target_metadata.update(target_raw.get("context") or {})
        target_device = target_raw.get("device_id")

        options_for_convert = dict(options_out)
        if target_device is not None:
            options_for_convert["target_device_id"] = target_device
        if target_metadata:
            options_for_convert["metadata"] = target_metadata

        result = self.convert_frame({
            "source": source_frame,
            "target_protocol": target_protocol,
            "options": options_for_convert,
        })
        output = MessageConversionResult(result["frame"], warnings=[*result["warnings"], *warnings])
        if result["frame"].get("device_id") is not None:
            output.device_id = result["frame"]["device_id"]
            output["device_id"] = result["frame"]["device_id"]
        return output

    def try_convert_frame(self, input):
        return to_result(lambda: self.convert_frame(input))

    def try_convert_message(self, input):
        return to_result(lambda: self.convert_message(input))

    # Camel-case compatibility
    convertFrame = convert_frame
    convertMessage = convert_message
    tryConvertFrame = try_convert_frame
    tryConvertMessage = try_convert_message


class FrozenRegistry(dict):
    def __init__(self, values):
        dict.__init__(self, values)

    def __setitem__(self, key, value):
        raise TypeError("adapter registry is frozen")

    def clear(self):
        raise TypeError("adapter registry is frozen")

    def pop(self, key, *args):
        raise TypeError("adapter registry is frozen")

    def popitem(self):
        raise TypeError("adapter registry is frozen")

    def setdefault(self, key, default=None):
        raise TypeError("adapter registry is frozen")

    def update(self, *args, **kwargs):
        raise TypeError("adapter registry is frozen")

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def create_converter(options=None):
    return ProtocolConverter(options)


default_converter = create_converter()
convert_frame = default_converter.convert_frame
convert_message = default_converter.convert_message
try_convert_frame = default_converter.try_convert_frame
try_convert_message = default_converter.try_convert_message

# Compatibility exports
convertFrame = convert_frame
convertMessage = convert_message
tryConvertFrame = try_convert_frame
tryConvertMessage = try_convert_message
createConverter = create_converter
supported_protocols = protocols
supportedProtocols = supported_protocols
