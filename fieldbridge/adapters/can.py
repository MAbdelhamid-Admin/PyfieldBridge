from ..core.adapter import create_adapter
from ..core.errors import FieldbridgeError
from .rules import check_range, payload_error, require_field

MAX_STANDARD_ID = 0x7ff
MAX_EXTENDED_ID = 0x1fffffff
CAN_FD_LENGTHS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64}


def validate(frame):
    require_field(frame, "identifier", "an 11/29-bit identifier")
    extended = (frame.get("metadata") or {}).get("extended")
    check_range(frame, "identifier", 0,
                MAX_STANDARD_ID if extended is False else MAX_EXTENDED_ID)
    length = len(frame["payload"])
    fd = (frame.get("metadata") or {}).get("fd")
    if fd is False or (fd is None and length <= 8):
        if length > 8:
            raise payload_error(frame, "Classic CAN payload exceeds 8 bytes")
    elif length not in CAN_FD_LENGTHS:
        raise payload_error(frame,
                            f"CAN FD payload length {length} is not a valid DLC length (0-8, 12, 16, 20, 24, 32, 48, 64)")


can_adapter = create_adapter({
    "protocol": "can",
    "max_payload": 64,
    "validate": validate,
    "fields": ["identifier"],
})
