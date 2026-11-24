from ..core.adapter import create_adapter
from .rules import check_range

MAX_MAC = (1 << 48) - 1


def validate(frame):
    check_range(frame, "source_address", 0, MAX_MAC, "source MAC")
    check_range(frame, "destination_address", 0, MAX_MAC, "destination MAC")
    check_range(frame, "identifier", 0, 0xffff, "EtherType")


ethernet_adapter = create_adapter({
    "protocol": "ethernet",
    "max_payload": 1500,
    "validate": validate,
    "fields": ["source_address", "destination_address", "identifier"],
})
