from ..core.adapter import create_adapter
from .rules import check_range, payload_error, require_field


def validate(frame):
    require_field(frame, "identifier", "a frame identifier (slot)")
    check_range(frame, "identifier", 1, 2047, "slot identifier")
    if len(frame["payload"]) % 2 != 0:
        raise payload_error(frame,
                            "FlexRay payload length must be an even number of bytes (2-byte words)")


flexray_adapter = create_adapter({
    "protocol": "flexray",
    "max_payload": 254,
    "validate": validate,
    "fields": ["identifier"],
})
