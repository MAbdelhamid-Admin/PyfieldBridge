"""
Validated conversion of frame envelopes between industrial and automotive
protocols.

PyfieldBridge converts the **envelope** of a frame: addresses, identifiers,
payload limits and metadata, while preserving the payload bytes exactly.
Nothing about the payload's meaning is guessed.

Supported protocols: Ethernet, PROFINET, PROFIBUS DP/PA, Modbus RTU/TCP,
CAN / CAN FD, LIN, FlexRay and EtherCAT.

## Install

```bash
python -m pip install pyfieldbridge
```

Or, from a checkout:

```bash
python -m pip install -e .
```

The import package is `fieldbridge`; `pyfieldbridge` is a compatibility
package name.

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

print(result.message)
print(result.warnings)
```

Every conversion returns `warnings` describing anything that was inferred,
overridden or dropped.

## Main entry points

- `convert_frame` and `convert_message`
- `try_convert_frame` and `try_convert_message` for a non-throwing API
- `create_converter` and `create_adapter` for custom protocol adapters
- `validate_frame`, `assert_protocol`, `is_protocol`
- `FieldbridgeError` with stable `code`, `protocol`, `field` and `cause`

Raw bytes are handled by the `fieldbridge.wire` module.

## Links

- [README and full behaviour reference](https://github.com/MAbdelhamid-Admin/PyfieldBridge#readme)
- [Node.js / TypeScript version](https://github.com/MAbdelhamid-Admin/fieldBridge)
- [Source code](https://github.com/MAbdelhamid-Admin/PyfieldBridge)
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
