from ..core.adapter import create_adapter
from .rules import check_range, payload_error, require_field


def validate(frame):
    require_field(frame, "identifier", "a 6-bit identifier")
    check_range(frame, "identifier", 0, 0x3f)
    if len(frame["payload"]) < 1:
        raise payload_error(frame, "LIN payload must contain 1..8 bytes")


lin_adapter = create_adapter({
    "protocol": "lin",
    "max_payload": 8,
    "validate": validate,
    "fields": ["identifier"],
})
