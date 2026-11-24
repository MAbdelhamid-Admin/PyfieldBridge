from typing import Any, Literal

FieldbridgeErrorCode = Literal[
    "UNSUPPORTED_PROTOCOL",
    "INVALID_FRAME",
    "PROTOCOL_MISMATCH",
    "INVALID_PAYLOAD",
    "PAYLOAD_TOO_LARGE",
    "MISSING_FIELD",
    "INVALID_FIELD",
    "MISSING_CONTEXT",
    "INVALID_DEVICE_ID",
    "CHECKSUM_MISMATCH",
    "UNSUPPORTED_FEATURE",
    "INTERNAL",
]


_FIELD_NAMES = {
    "device_id": "deviceId",
    "source_address": "sourceAddress",
    "destination_address": "destinationAddress",
    "target_device_id": "targetDeviceId",
}


def field_name(field: str | None) -> str | None:
    """Report envelope fields with the same names as the TypeScript API."""
    if field is None:
        return None
    return _FIELD_NAMES.get(field, field)


class FieldbridgeError(Exception):
    def __init__(self, code: FieldbridgeErrorCode, message: str, *, protocol: str | None = None,
                 field: str | None = None, cause: Any = None):
        super().__init__(message)
        self.name = "FieldbridgeError"
        self.code = code
        self.protocol = protocol
        self.field = field_name(field)
        self.cause = cause


def is_fieldbridge_error(error: object) -> bool:
    return isinstance(error, FieldbridgeError)


# Camel-case compatibility name.
isFieldbridgeError = is_fieldbridge_error
