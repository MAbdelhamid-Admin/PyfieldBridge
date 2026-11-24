from ..core.adapter import create_adapter
from .rules import check_range, payload_error, require_field

MAX_PDU = 253


def create_modbus_validator(max_address):
    def validate(frame):
        require_field(frame, "address", "an address (set message.address or pass a numeric deviceId)")
        check_range(frame, "address", 0, max_address)
        if len(frame["payload"]) < 1:
            raise payload_error(frame, f"{frame['protocol']} payload must start with a function code")
        function_code = frame["payload"][0]
        if function_code == 0 or function_code == 0x80:
            raise payload_error(frame, f"{frame['protocol']} function code {function_code} is invalid")
    return validate


common = {"max_payload": MAX_PDU, "fields": ["address"], "uses_device_address": True}

modbus_rtu_adapter = create_adapter({
    "protocol": "modbus-rtu",
    "validate": create_modbus_validator(247),
    **common,
})
modbus_tcp_adapter = create_adapter({
    "protocol": "modbus-tcp",
    "validate": create_modbus_validator(255),
    **common,
})
