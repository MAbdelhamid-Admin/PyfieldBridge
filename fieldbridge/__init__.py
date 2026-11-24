"""
Python implementation of fieldbridge: validated envelope conversion and wire parsing.
"""

from .core.types import (
    Protocol, protocols, supported_protocols, envelope_fields, envelopeFields,
    NormalizedFrame, ProtocolFrame, ProtocolAdapter, ConversionResult,
    MessageConversionResult, Result,
)
from .core.errors import FieldbridgeError, FieldbridgeErrorCode, is_fieldbridge_error, isFieldbridgeError
from .core.result import to_result, toResult
from .core.validation import (
    assert_protocol, is_protocol, validate_frame,
    assertProtocol, isProtocol, validateFrame,
)
from .core.adapter import create_adapter, createAdapter, AdapterDefinition
from .core.convert import (
    convert_frame, convert_message, try_convert_frame, try_convert_message,
    convertFrame, convertMessage, tryConvertFrame, tryConvertMessage,
    create_converter, createConverter, supportedProtocols,
)
from .adapters.index import adapters

__all__ = [
    "Protocol", "protocols", "supported_protocols", "supportedProtocols",
    "envelope_fields", "envelopeFields", "NormalizedFrame", "ProtocolFrame",
    "ProtocolAdapter", "ConversionResult", "MessageConversionResult", "Result",
    "FieldbridgeError", "FieldbridgeErrorCode", "is_fieldbridge_error", "isFieldbridgeError",
    "to_result", "toResult", "assert_protocol", "is_protocol", "validate_frame",
    "assertProtocol", "isProtocol", "validateFrame", "create_adapter", "createAdapter",
    "AdapterDefinition", "convert_frame", "convert_message", "try_convert_frame",
    "try_convert_message", "convertFrame", "convertMessage", "tryConvertFrame",
    "tryConvertMessage", "create_converter", "createConverter", "adapters",
]
